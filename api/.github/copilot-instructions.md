
# copilot-instructions.md

## PROJECT CONTEXT

This repository implements a **production-grade, job-based RAG ingestion backend** using:

- FastAPI
- PostgreSQL (async)
- Redis (job state only, no Celery)
- LangChain + Chroma
- Modular ingestion pipeline (PDF / DOCX / Sheets)
- Per-workspace + per-project isolated vector stores

The system is intentionally designed with **clean architecture boundaries**:
- API layer → validation & orchestration only
- Service layer → business logic
- Core layer → reusable infrastructure (AI, vector store, routing)
- Providers → pluggable ingestion implementations

This is a **long-term, scalable system**, not a prototype.

---

## BUSINESS LOGIC OVERVIEW

### Core Concepts

- **Organization ≈ Workspace**
- **Workspace contains Projects**
- **Each Project has:**
  - `vector_store_path`
  - `knowledge_base/` (raw uploaded files)
  - `chroma_db/` (embeddings)

### Ingestion Flow (INTENDED)

1. Client uploads files via API
2. Files are saved to disk under:
vector_stores/{workspace_id}/{project_id}/knowledge_base/
3. An ingestion job is created
4. Background task processes files:
- Routes files to correct ingestor
- Extracts content
- Generates embeddings
- Writes to project-scoped Chroma DB
5. Job status is updated in Redis
6. Client polls job status

---

## CURRENT PROGRESS (WHAT IS WORKING)

✅ Authentication & authorization  
✅ Project creation and ownership validation  
✅ Correct vector store directory structure  
✅ Redis-backed ingestion job lifecycle  
✅ Background task execution  
✅ File router + ingestors are implemented  
✅ Chroma vector store manager is implemented  
✅ No filesystem path errors (WinError resolved)  

**Current directory structure is correct and intentional.**

---

## CURRENT PROBLEM (CRITICAL)

### Observed Behavior

- Ingestion job returns `"status": "completed"`
- Project directories are created
- BUT:
- `knowledge_base/` is empty
- `chroma_db/` is empty
- User uploaded multiple files via Postman

### Root Cause (IMPORTANT)

The ingestion process is executed **inside a background task**, but:

- `UploadFile` objects are **request-scoped**
- When the background task runs:
- The HTTP request is already completed
- `UploadFile.file` streams are closed or exhausted
- Result:
- Files are never actually written to disk
- Ingestion runs on an empty folder
- No embeddings are generated
- Job still completes successfully (no exception)

This is a **known, real-world backend pitfall**, not a logic bug.

---

## DESIGN RULE (NON-NEGOTIABLE)

> **Background tasks must NEVER depend on request-scoped objects**

This includes:
- `UploadFile`
- Request bodies
- File streams
- FastAPI request context

---

## REQUIRED FIX (HIGH-LEVEL)

### Correct Architecture

1. **Synchronously save uploaded files during the request**
- While `UploadFile` streams are valid
- Inside the API/service layer
2. **Background task must receive ONLY filesystem paths**
- `workspace_id`
- `project_id`
- `knowledge_base` directory path
3. Background task must:
- Read files from disk
- Run `ingest_folder(...)`
- Update job status

---

## STRICT CONSTRAINTS (DO NOT VIOLATE)

### ❌ DO NOT
- ❌ Do NOT introduce new Python packages
- ❌ Do NOT introduce Celery, RQ, or new queues
- ❌ Do NOT refactor unrelated modules
- ❌ Do NOT move or rename existing folders
- ❌ Do NOT change ingestion logic internals
- ❌ Do NOT bypass Redis job tracking
- ❌ Do NOT embed logic inside `api.main`
- ❌ Do NOT change the vector store design
- ❌ Do NOT add temporary hacks or flags
- ❌ Do NOT silently swallow failures

### ✅ ALLOWED
- ✅ Move file-saving logic to request lifecycle
- ✅ Pass filesystem paths to background jobs
- ✅ Add minimal validation/logging
- ✅ Update service-layer logic only if required
- ✅ Keep modular structure intact
- ✅ Follow FastAPI best practices

---

## EXPECTED END STATE

After the fix:

- `knowledge_base/` contains uploaded files
- `chroma_db/` contains persisted embeddings
- Ingestion job status reflects real processing
- No background task depends on `UploadFile`
- Architecture remains clean and extensible

---

## COPILOT PROMPT (PASTE THIS EXACTLY)

> You are working on a production FastAPI backend with Redis-based background ingestion jobs.
>
> The current issue is that ingestion jobs complete successfully but do not ingest any files.
> Root cause: `UploadFile` objects are passed into background tasks, which run after the request lifecycle, so file streams are empty.
>
> FIX THIS BY:
> - Saving uploaded files synchronously during the request lifecycle
> - Passing ONLY filesystem paths to background tasks
> - Keeping the existing modular architecture intact
>
> CONSTRAINTS:
> - Do NOT introduce new libraries
> - Do NOT refactor unrelated code
> - Do NOT change ingestion internals
> - Do NOT change vector store design
> - Do NOT use Celery or new queues
>
> Apply the minimal, industry-standard fix so that:
> - Files are persisted before background execution
> - Background tasks operate only on disk paths
> - `ingest_folder()` processes real files
>
> Produce clean, production-quality code only.

---

## FINAL NOTE

This fix is **architectural**, not experimental.

It is required for:
- Reliability
- Scalability
- Cloud deployment
- Future integrations (Google Drive, S3, SharePoint)

Treat this as a **boundary correction**, not a redesign.
