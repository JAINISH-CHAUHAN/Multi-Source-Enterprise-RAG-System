
# Multi-Source Enterprise RAG System  
## Copilot Operating Rules & Project Constraints

This document defines **strict development rules**, the **current system state**, and the **next implementation goals**.

Copilot MUST follow this file.

---

# 🔒 ARCHITECTURE & STRUCTURE RULES (STRICT)

## 1️⃣ Modular Architecture Is Mandatory

The project follows a strict layered architecture:


rag/ → RAG pipeline logic

api/
├── routers/ → HTTP layer only
├── services/ → Business logic
├── core/ → Security, config, AI factory, shared infra
├── models/ → Database models
├── schemas/ → Pydantic schemas
### Rules:

- Routers MUST contain:
  - Request validation
  - Dependency injection
  - Calling service layer
  - Returning responses
- Routers MUST NOT contain:
  - Business logic
  - RAG logic
  - Vector store logic
  - File processing logic

---

## 2️⃣ RAG & API Separation

- RAG logic must live only in `rag/`
- Business logic must live in `api/services/`
- Routers must never call vector store directly
- Routers must never manipulate embeddings directly

Separation must be preserved at all times.

---

## 3️⃣ Folder Integrity Rule

Copilot MUST NOT:

- Create new top-level folders
- Move files
- Rename files
- Restructure the project
- Introduce alternative architecture

Without explicit permission.

Breaking folder structure = HARD STOP.

---

## 4️⃣ No Unapproved Libraries

- No new libraries without explicit permission
- No silent addition of utilities
- No framework migration
- No dependency injection frameworks
- No background job libraries unless explicitly approved

If unsure → STOP and ask.

---

# 🧠 LLM USAGE RULES (STRICT)

Copilot MUST:

- Use `get_llm("primary")`
- Depend ONLY on `core.ai_factory` interfaces

Copilot MUST NOT:

- Instantiate OpenAI directly
- Instantiate HuggingFace directly
- Instantiate Ollama directly
- Reference provider SDKs directly

No provider coupling allowed.

---

# ⚠ ERROR HANDLING RULES

- Fail fast if vector store path does not exist
- Never swallow exceptions silently
- Never retry internally
- Always return clean structured error messages
- Do not crash the server process

Server must stay alive even if ingestion fails.

---

# 🤖 COPILOT BEHAVIOR RULES

Copilot MUST:

- Ask for clarification if unsure
- Keep code minimal
- Prefer clarity over cleverness
- Avoid premature optimization
- Follow existing naming conventions

Copilot MUST NOT:

- Add comments explaining obvious Python syntax
- Add unused helper functions
- Add unnecessary abstractions
- Over-engineer
- Rewrite working components

---

# 🏆 GOLDEN RULE

If a change risks breaking:

- Ingestion
- Vector storage
- Multi-tenancy isolation
- Authentication/session logic

STOP.

Ask for clarification.

---

# 📌 CURRENT PROJECT STATE

## Backend

- FastAPI backend operational
- Auth system working
- Multi-tenant isolation implemented
- Redis integration working
- Vector store working per organization
- Ingestion pipeline implemented
- LLM factory abstraction implemented
- Session-based query pipeline working
- Gemini provider integrated through abstraction

## Known Issues

1. File viewing not implemented
2. Vector store does not support per-file deletion
3. Updating files not supported
4. Error handling causes server stop on some failures
5. Ingestion status endpoint is blocking (not async)

---

# 🎯 IMPLEMENTATION GOALS

---

# 1️⃣ View Uploaded Files in Frontend

## Required Backend Changes

Backend must:

- Expose endpoint to list uploaded files per organization
- Expose endpoint to retrieve file metadata
- Possibly expose endpoint to stream file content (optional)

## Rules:

- Must respect multi-tenancy
- Must verify organization ownership
- Must not expose filesystem paths
- Must not leak server directory structure

File responses should return:

```json
{
  "id": "...",
  "filename": "...",
  "size": "...",
  "uploaded_at": "...",
  "status": "indexed | pending"
}
