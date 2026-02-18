# Ingestion Pipeline Refactoring Instructions

## Overview

This document outlines the full refactoring plan for the RAG ingestion pipeline. The goal is
to introduce a **content-addressed file registry** with **deterministic vector IDs** and a
**status-driven state machine**, so that every upload, re-upload, deduplication, and deletion
scenario is handled safely, idempotently, and without orphaned vectors — while preserving the
existing chunking and embedding strategies and keeping the modular codebase structure intact.

---

## Guiding Principles

- **The file registry is the single source of truth.** The vector store is a derived artifact.
  The DB always reflects reality; the vector store is always reconstructable from it.
- **All ingestion is incremental.** Only the files that need processing get processed.
- **All operations are idempotent.** Running the same operation twice must produce the same
  result, with no duplicate vectors and no data loss.
- **The chunking and embedding logic is not touched.** Only the orchestration layer around it
  changes.
- **Modules stay modular.** Each concern (hashing, registry, ingestion, deletion) lives in its
  own layer and is injected where needed.

---

## Phase 1 — Database Schema Changes

### 1.1 Add `file_hash` and `status` to the `documents` table

The most important additions are a `file_hash` column for deduplication and a `status` column
for safe state transitions.

```sql
ALTER TABLE documents
    ADD COLUMN file_hash    TEXT,
    ADD COLUMN status       TEXT NOT NULL DEFAULT 'pending'
                            CHECK (status IN (
                                'pending', 'processing', 'active', 'deleting', 'failed'
                            )),
    ADD COLUMN chunk_count  INTEGER,
    ADD COLUMN ingested_at  TIMESTAMPTZ,
    ADD COLUMN deleted_at   TIMESTAMPTZ;

-- Enforce deduplication at the DB level per project
-- (same file content can exist in different projects, but not twice in the same one)
CREATE UNIQUE INDEX uix_documents_hash_project
    ON documents (file_hash, project_id)
    WHERE is_deleted = FALSE;
```

### 1.2 Create the `document_chunks` table

This table is the bridge between the DB and the vector store. It records every vector ID that
was written, scoped to the document that produced it.

```sql
CREATE TABLE document_chunks (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id   UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    vector_id     TEXT NOT NULL,
    chunk_index   INTEGER NOT NULL,
    chunk_text    TEXT,                -- optional: stored for audit/debug
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uix_document_chunk UNIQUE (document_id, chunk_index)
);

CREATE INDEX idx_chunks_document_id ON document_chunks (document_id);
```

> **Why store chunk_text?** During deletion you can verify what was in the vector store
> without re-reading the source file. During debugging you can inspect what the model
> actually saw. It can be omitted in storage-sensitive environments.

---

## Phase 2 — New Core Utilities

These are pure utility modules with no FastAPI or DB dependencies. They belong in `core/`.

### 2.1 `core/hashing.py`

```python
import hashlib

def compute_file_hash(file_bytes: bytes) -> str:
    """Compute a SHA-256 hex digest of raw file bytes."""
    return hashlib.sha256(file_bytes).hexdigest()

def make_vector_id(file_hash: str, chunk_index: int) -> str:
    """
    Produce a deterministic, collision-resistant vector ID.
    Using the same file_hash + chunk_index always yields the same ID,
    making vector upserts fully idempotent.
    """
    raw = f"{file_hash}:{chunk_index}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]
```

### 2.2 `core/ingestion_pipeline.py`

This module is the **only place** that orchestrates chunking → embedding → vector upsert.
It does not handle HTTP, routing, or DB record creation — it receives an already-validated
document record and processes it.

Keep the existing `chunker` and `embedder` calls exactly as they are inside this module.
Only the surrounding orchestration changes.

```python
async def run_ingestion(
    document: dict,          # the full DB record, already inserted with status='pending'
    file_bytes: bytes,
    vector_store: VectorStoreManager,
    db: Database,
) -> int:
    """
    Chunk, embed, and upsert a document into the vector store.
    Records every chunk in document_chunks.
    Returns the number of chunks written.

    This function is idempotent: if called twice for the same document,
    the deterministic vector IDs cause the vector store to upsert (not duplicate),
    and the document_chunks insert uses ON CONFLICT DO NOTHING.
    """
    document_id = document["id"]
    file_hash   = document["file_hash"]

    # Mark as processing
    await _set_status(db, document_id, "processing")

    try:
        # --- existing chunking logic (unchanged) ---
        chunks = chunk_document(file_bytes, document["file_name"])

        # --- existing embedding logic (unchanged) ---
        embeddings = embed_chunks([c.text for c in chunks])

        # --- upsert into vector store with deterministic IDs ---
        records = []
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            vector_id = make_vector_id(file_hash, i)
            records.append({
                "id":        vector_id,
                "embedding": embedding,
                "metadata": {
                    "document_id": str(document_id),
                    "project_id":  str(document["project_id"]),
                    "file_name":   document["file_name"],
                    "chunk_index": i,
                    "text":        chunk.text,
                }
            })

        vector_store.upsert(records)

        # --- persist chunk map to DB ---
        chunk_rows = [
            {
                "document_id": document_id,
                "vector_id":   r["id"],
                "chunk_index": i,
                "chunk_text":  chunks[i].text,
            }
            for i, r in enumerate(records)
        ]
        await _insert_chunks(db, chunk_rows)

        # --- mark active ---
        await _set_status(db, document_id, "active", chunk_count=len(records))
        return len(records)

    except Exception as e:
        await _set_status(db, document_id, "failed")
        raise
```

---

## Phase 3 — Refactor the Upload Service

The upload service (`api/services/document_upload.py` or equivalent) needs to be the
**entry point for all deduplication logic**. Nothing downstream needs to know about hashing.

### 3.1 New upload flow (step by step)

```
1.  Receive file bytes from the HTTP layer
2.  Compute SHA-256 hash of bytes
3.  Query documents WHERE file_hash = ? AND project_id = ? AND is_deleted = FALSE
        → If found with status='active'  : return 200 with existing document record (no-op)
        → If found with status='processing': return 202 "already being ingested"
        → If found with status='failed'  : proceed to re-ingest (treat as new attempt)
4.  Check for same filename, different hash (updated file scenario):
        → If found: mark old record status='deleting', enqueue deletion job for old vectors
5.  Save file bytes to object storage / knowledge_base folder
6.  Insert new documents row with status='pending', file_hash=<hash>
7.  Enqueue ingestion job (or run inline if synchronous)
8.  Return 202 Accepted with document_id
```

### 3.2 Pseudo-code

```python
async def upload_document(
    file_name: str,
    file_bytes: bytes,
    project_id: str,
    workspace_id: str,
):
    file_hash = compute_file_hash(file_bytes)

    # --- deduplication check ---
    existing = await db.fetch_one(
        documents.select().where(
            (documents.c.file_hash    == file_hash) &
            (documents.c.project_id  == project_id) &
            (documents.c.is_deleted  == False)
        )
    )

    if existing:
        if existing["status"] == "active":
            return {"document_id": existing["id"], "status": "already_exists"}
        if existing["status"] == "processing":
            return {"document_id": existing["id"], "status": "already_processing"}
        # status == 'failed': fall through and re-ingest

    # --- updated file check (same name, different content) ---
    old_version = await db.fetch_one(
        documents.select().where(
            (documents.c.file_name   == file_name) &
            (documents.c.project_id  == project_id) &
            (documents.c.is_deleted  == False) &
            (documents.c.file_hash   != file_hash)
        )
    )
    if old_version:
        # Kick off async deletion of old version's vectors before replacing
        await _mark_deleting(db, old_version["id"])
        await enqueue_deletion_job(old_version["id"])

    # --- save file ---
    save_file_to_storage(file_bytes, project_id, file_name)

    # --- insert registry record ---
    document_id = await db.execute(
        documents.insert().values(
            file_name   = file_name,
            file_hash   = file_hash,
            project_id  = project_id,
            status      = "pending",
            created_at  = datetime.now(timezone.utc),
        )
    )

    # --- trigger ingestion ---
    await enqueue_ingestion_job(document_id)

    return {"document_id": document_id, "status": "accepted"}
```

---

## Phase 4 — Refactor the Deletion Service

The existing `delete_document` service is structurally sound but needs the following changes
to align with the new design. **Do not rewrite it from scratch** — patch the gaps.

### 4.1 Add status guard at the very start

Before touching vectors or files, flip the record to `deleting`. This is your crash-recovery
anchor. Any background recovery job can find all `status='deleting'` records and resume them.

```python
# Step 0 — immediately mark as deleting (add this before any other operation)
await database.execute(
    documents.update()
    .where(documents.c.id == document_id)
    .values(status="deleting", updated_at=datetime.now(timezone.utc))
)
```

### 4.2 Replace metadata-filter vector deletion with chunk-table-based deletion

Instead of relying on a metadata filter (which is a full scan in ChromaDB), look up the
exact vector IDs from `document_chunks` and delete by ID. This is faster and fully precise.

```python
# Replace the current vector_store.delete(where={"document_id": ...}) call with:

chunk_rows = await database.fetch_all(
    document_chunks.select()
    .where(document_chunks.c.document_id == document_id)
)
vector_ids = [row["vector_id"] for row in chunk_rows]

if vector_ids:
    deleted_count = vector_store.delete_by_ids(vector_ids)
else:
    deleted_count = 0
    logger.warning(f"No chunk records found for document {document_id}")
```

### 4.3 Fix `datetime.utcnow()` → timezone-aware

```python
# Replace
deleted_at=datetime.utcnow()

# With
deleted_at=datetime.now(timezone.utc)
```

### 4.4 Enrich the return payload

```python
return {
    "message":           "Document deleted successfully",
    "document_id":       document_id,
    "file_name":         document["file_name"],
    "embeddings_deleted": deleted_count,
    "deleted_at":        datetime.now(timezone.utc).isoformat(),
}
```

### 4.5 Surface `safe_delete_file` failures

Change `safe_delete_file` to return a boolean success flag (or raise a non-fatal warning
exception), then include the result in the return payload so callers and monitoring systems
can detect orphaned files without reading logs.

---

## Phase 5 — Background Recovery Job

Add a periodic task (Celery beat, APScheduler, or a cron-triggered endpoint) that heals
any documents that got stuck mid-transition.

```python
async def recover_stuck_documents():
    """
    Run periodically (e.g., every 5 minutes).
    Resumes documents that crashed mid-ingestion or mid-deletion.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=10)

    # Resume stuck ingestions
    stuck_ingesting = await db.fetch_all(
        documents.select().where(
            documents.c.status.in_(["pending", "processing"]) &
            (documents.c.updated_at < cutoff)
        )
    )
    for doc in stuck_ingesting:
        logger.warning(f"Resuming stuck ingestion for document {doc['id']}")
        await enqueue_ingestion_job(doc["id"])

    # Resume stuck deletions
    stuck_deleting = await db.fetch_all(
        documents.select().where(
            (documents.c.status == "deleting") &
            (documents.c.updated_at < cutoff)
        )
    )
    for doc in stuck_deleting:
        logger.warning(f"Resuming stuck deletion for document {doc['id']}")
        await enqueue_deletion_job(doc["id"])
```

---

## Phase 6 — VectorStoreManager Interface Changes

The `VectorStoreManager` in `core/vector_store.py` needs one new method. Everything else
stays the same.

### 6.1 Add `delete_by_ids`

```python
def delete_by_ids(self, vector_ids: list[str]) -> int:
    """
    Delete vectors by their exact IDs.
    Returns the count of vectors deleted.
    Prefer this over metadata-filter deletion — it is O(n) not O(collection).
    """
    if not vector_ids:
        return 0
    self.collection.delete(ids=vector_ids)
    return len(vector_ids)
```

The existing `delete(where=...)` method can stay for any other use cases — do not remove it.

### 6.2 Inject VectorStoreManager via dependency injection

Stop constructing `VectorStoreManager` inline in service functions. Add a FastAPI dependency:

```python
# api/dependencies.py

from functools import lru_cache
from core.vector_store import VectorStoreManager

# One instance per (workspace_id, project_id) pair, cached for the process lifetime
_vector_store_cache: dict[str, VectorStoreManager] = {}

def get_vector_store(workspace_id: str, project_id: str) -> VectorStoreManager:
    key = f"{workspace_id}:{project_id}"
    if key not in _vector_store_cache:
        chroma_dir = os.path.join(VECTOR_BASE_DIR, workspace_id, project_id, "chroma_db")
        _vector_store_cache[key] = VectorStoreManager(persist_directory=chroma_dir)
    return _vector_store_cache[key]
```

Inject it in route handlers:

```python
@router.delete("/documents/{document_id}")
async def delete_document_route(
    document_id: str,
    workspace_id: str,
    vector_store: VectorStoreManager = Depends(
        lambda: get_vector_store(workspace_id, project_id)
    ),
):
    ...
```

---

## Phase 7 — New API Endpoints

Add these endpoints alongside the existing ones. Do not modify existing route signatures.

```
POST   /projects/{project_id}/documents/upload
           → hash → dedup check → save → insert registry → enqueue ingestion

DELETE /projects/{project_id}/documents/{document_id}
           → existing endpoint, patched per Phase 4

GET    /projects/{project_id}/documents
           → list all documents with status field exposed

GET    /projects/{project_id}/documents/{document_id}
           → single document detail including chunk_count and status

POST   /projects/{project_id}/documents/{document_id}/retry
           → re-trigger ingestion for documents with status='failed'

GET    /projects/{project_id}/documents/{document_id}/chunks
           → list all chunk records (debug/audit endpoint, guard behind admin or dev flag)
```

---

## Execution Order

Perform the refactoring in this exact sequence to avoid breaking the running system:

1. **Schema migration** — add columns and create `document_chunks` table. All new columns
   are nullable or have defaults so existing rows are unaffected.
2. **Add `core/hashing.py`** — pure utility, no side effects, safe to add any time.
3. **Add `delete_by_ids` to VectorStoreManager** — additive change, nothing breaks.
4. **Patch `delete_document` service** — apply Phase 4 changes. Covered by existing tests.
5. **Add `document_chunks` insert to the existing ingestion path** — add the chunk recording
   step after the existing embed-and-upsert block. The ingestion logic itself does not change.
6. **Add `file_hash` computation to the existing upload path** — compute and persist the hash
   on every new upload. Existing records get `NULL` hash (acceptable during migration).
7. **Add deduplication check to upload service** — once hashes are being written, the dedup
   guard can be activated.
8. **Add `core/ingestion_pipeline.py`** — consolidate the orchestration into this module and
   update the upload service to call it.
9. **Add VectorStoreManager dependency injection** — refactor call sites one by one.
10. **Add recovery job** — final safety net, deploy after all the above is stable.

---

## What Does NOT Change

| Component                        | Status     |
|----------------------------------|------------|
| Chunking strategy / chunk sizes  | Unchanged  |
| Embedding model / call signature | Unchanged  |
| `VectorStoreManager.upsert()`    | Unchanged  |
| Existing route paths and methods | Unchanged  |
| Existing auth / ownership checks | Unchanged  |
| Project / workspace scoping      | Unchanged  |
| ChromaDB as vector store         | Unchanged  |
| File storage path conventions    | Unchanged  |

---

## Success Criteria

The refactoring is complete when all of the following hold:

- Uploading the same file twice to the same project returns `already_exists` and writes
  zero new vectors.
- Uploading an updated version of a file (same name, different content) automatically
  removes the old vectors before ingesting the new ones.
- Deleting a document removes **exactly** the vectors that belong to it, verified by
  querying `document_chunks` before and after.
- Killing the process mid-ingestion and restarting causes the recovery job to resume
  ingestion cleanly with no duplicate vectors.
- Killing the process mid-deletion and restarting causes the recovery job to complete
  the deletion cleanly with no orphaned vectors.
- Every document row in the DB has a corresponding set of rows in `document_chunks`
  when `status = 'active'`.