# Step 3.0.2 — Retrieval + Answer Generation (RAG Runtime Core)

## STATUS
Planned — NOT YET IMPLEMENTED

This file defines **exact, narrow instructions** for implementing **Phase 3.0.2** of the RAG system.

This step focuses **only** on runtime retrieval and answer generation logic using an **already-ingested Chroma vector store**.

---

## 🔗 CONTEXT ANCHOR (MANDATORY)

This step **inherits ALL constraints** from:

- `copilot-instructions.md` (Phase 3.0.1)

If there is **any conflict**, **Phase 3.0.1 instructions take precedence**.

Copilot MUST assume:
- Ingestion is COMPLETE and WORKING
- Chroma DB already exists on disk
- Embeddings + LLM factory are correctly configured
- No ingestion, indexing, or file-system creation is required here

---

## 🎯 GOAL OF STEP 3.0.2 (STRICT)

Implement **retrieval + answer generation logic only**, such that:

- Given a user query
- Relevant documents are retrieved from a **project-scoped Chroma DB**
- An LLM generates a **final grounded answer**
- The logic is reusable, testable, and framework-agnostic

This is **NOT** an API layer.
This is **NOT** a router.
This is **NOT** chat memory.
This is **NOT** streaming.
This is **NOT** authentication.

---

## 📂 ALLOWED SCOPE (HARD BOUNDARY)

Copilot is allowed to **MODIFY OR CREATE CODE ONLY IN**:

/rag/retrieval/answer.py


Copilot is **NOT ALLOWED TO**:
- Modify `/api/*`
- Modify `/core/*`
- Modify `/rag/ingestion/*`
- Modify vector store code
- Modify database models
- Introduce new background jobs
- Introduce new queues or caches
- Introduce new environment variables

---

## 📌 EXISTING STRUCTURE (DO NOT CHANGE)

Current structure (MUST REMAIN INTACT):

/rag
├── ingestion/
└── retrieval/
└── answer.py


- No new folders
- No renaming
- No moving files

---

## 🧠 BUSINESS LOGIC (WHAT THIS STEP DOES)

### Input
- `query: str`
- `persist_directory: str` (path to existing Chroma DB)

### Process
1. Load the **existing** Chroma vector store
2. Perform similarity search (top-k, default k=3)
3. Build a grounded prompt using retrieved documents
4. Call LLM via `get_llm("primary")`
5. Generate a final answer

### Output
- A single string answer
- NO metadata persistence
- NO side effects

---

## 🧩 TECHNICAL CONSTRAINTS

### ✅ Must use
- `VectorStoreManager`
- `get_embeddings("default")`
- `get_llm("primary")`
- LangChain `Document` objects

### ❌ Must NOT
- Recreate vector stores
- Write to disk
- Add documents
- Persist anything
- Add logging frameworks
- Add retries / fallbacks
- Add citations logic (future phase)

---

## 🧪 EXPECTED FUNCTION SIGNATURE (REFERENCE)

Copilot MAY implement something equivalent to:

```python
def answer_query(
    query: str,
    persist_directory: str,
    k: int = 3
) -> str:
    ...
