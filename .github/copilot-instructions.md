# Copilot Instructions — Phase 3.0 (Retrieval Runtime)

## PURPOSE OF THIS FILE
This file defines STRICT constraints, boundaries, and context for GitHub Copilot
to safely implement Phase 3.0 of the RAG system without breaking existing logic.

Copilot MUST follow every rule below.
If a rule conflicts with a suggestion, the rule WINS.

---

## CURRENT PROJECT STATE (FACTS — DO NOT GUESS)

### What is WORKING
1. Document ingestion pipeline is COMPLETE and VERIFIED
2. Files are correctly saved to:
   vector_stores/{workspace_id}/{project_id}/knowledge_base
3. ChromaDB is correctly created at:
   vector_stores/{workspace_id}/{project_id}/chroma_db
4. Embeddings are successfully generated and persisted
5. Redis jobs work and ingestion completes with status = completed
6. VectorStoreManager correctly loads existing ChromaDB instances
7. Multi-tenant isolation (workspace → project) is enforced

### Proof of correctness
- chroma.sqlite3 exists
- HNSW binary files exist
- Retrieval test returns document count
- No ingestion errors
- No missing embeddings

---

## BUSINESS LOGIC (DO NOT CHANGE)

### Core Architecture
- Multi-tenant RAG backend
- Workspace → Project → Knowledge Base
- Each project has its OWN vector store
- No global or shared embeddings
- Retrieval must be project-scoped

### Retrieval Philosophy
- Retrieval ≠ ingestion
- Retrieval must NEVER modify stored data
- Retrieval is read-only
- Retrieval must be deterministic and repeatable

---

## MODULAR CODE STRUCTURE (CRITICAL)

### Existing structure (LOCKED)
/rag
├── ingestion/
│ ├── chunking.py
│ ├── content.py
│ ├── folder.py
│ ├── normalization.py
│ ├── rows.py
│ └── summarization.py
└── retrieval/
├── init.py
└── answer.py

### Meaning
- `/rag/ingestion` → WRITE ONCE, READ NEVER
- `/rag/retrieval` → READ ONLY, NEVER INGEST

Copilot MUST respect this separation.

---

## SCOPE OF PHASE 3.0 (WHAT IS ALLOWED)

### ALLOWED
✅ Retrieval logic  
✅ Query handling  
✅ Prompt construction  
✅ LLM invocation  
✅ Source attribution  
✅ Read-only vector store access  

### NOT ALLOWED
❌ Modifying ingestion code  
❌ Modifying VectorStoreManager behavior  
❌ Creating new ingestion logic  
❌ Adding new embeddings  
❌ Adding new dependencies  
❌ Changing providers  
❌ Changing environment variables  
❌ Changing database schemas  

---

## FILE CREATION RULES (VERY IMPORTANT)

### Copilot MAY:
- Modify existing files ONLY if explicitly instructed
- Create NEW files ONLY when explicitly told
- Follow given file paths EXACTLY

### Copilot MUST NOT:
- Create files without permission
- Move files
- Rename files
- Merge modules
- Break folder boundaries

---

## PHASE 3.0 TARGET (HIGH LEVEL)

Implement QUERY-TIME RAG ONLY:

1. Accept user query
2. Load project-scoped vector store
3. Retrieve top-k documents
4. Assemble context
5. Call LLM via ai_factory
6. Return answer + sources

NO memory. NO chat history. NO streaming.

---

## LLM USAGE RULES

- MUST use get_llm("primary")
- MUST NOT instantiate providers directly
- MUST NOT reference OpenAI / HF / Ollama directly
- MUST only depend on core.ai_factory interfaces

---

## ERROR HANDLING RULES

- Fail fast if vector store path does not exist
- Return clean error messages
- Do NOT swallow exceptions silently
- Do NOT retry internally

---

## COPILOT BEHAVIOR RULES (STRICT)

Copilot MUST:
- Ask for clarification if unsure
- Keep code minimal
- Prefer clarity over cleverness
- Avoid premature optimization

Copilot MUST NOT:
- Add comments explaining obvious Python syntax
- Add unused helper functions
- Add abstractions not requested

---

## GOLDEN RULE
If a change risks breaking ingestion, vector storage, or multi-tenancy,
DO NOT IMPLEMENT IT.

Stop and ask for clarification.

---

## END OF INSTRUCTIONS
