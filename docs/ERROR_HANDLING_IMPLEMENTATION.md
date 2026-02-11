# Error Handling System - Implementation Summary

## Overview

A comprehensive three-layer error handling system has been implemented to ensure the RAG backend fails safely without crashing the server. All errors are now caught, logged, and returned as structured responses to the frontend.

---

## Architecture

### 1. Global Layer (Application-Wide)
**Location:** [api/main.py](api/main.py)

Three global exception handlers intercept all unhandled errors:

- `@app.exception_handler(BaseAppException)` - Domain exceptions (LLM, VectorStore, etc.)
- `@app.exception_handler(HTTPException)` - FastAPI validation/auth errors
- `@app.exception_handler(Exception)` - Catch-all for unexpected errors

**Behavior:**
- Full tracebacks logged to `logs/app.log` for debugging
- Clean JSON errors sent to frontend (no internal details exposed)
- Server never crashes - all requests return valid HTTP responses

### 2. Service Layer (Business Logic)
**Locations:**
- [api/services/query_service.py](api/services/query_service.py) - Query processing
- [api/services/ingestion_job_service.py](api/services/ingestion_job_service.py) - Background ingestion
- [api/services/conversation_service.py](api/services/conversation_service.py) - LLM summarization
- [api/services/citation_service.py](api/services/citation_service.py) - Citation resolution
- [api/services/project_service.py](api/services/project_service.py) - Project CRUD

**Behavior:**
- Wraps external calls (DB, file I/O, API calls)
- Raises domain-specific exceptions (`LLMException`, `DatabaseException`, etc.)
- Logs failures with full context
- Non-critical failures degrade gracefully (e.g., conversation summary skipped if LLM fails)

### 3. Provider Layer (External Integrations)
**Locations:**
- **LLM Providers:** [providers/openai/llm.py](providers/openai/llm.py), [providers/gemini/llm.py](providers/gemini/llm.py), [providers/ollama/llm.py](providers/ollama/llm.py)
- **Embedding Providers:** [providers/openai/embeddings.py](providers/openai/embeddings.py), [providers/gemini/embeddings.py](providers/gemini/embeddings.py), [providers/huggingface/embeddings.py](providers/huggingface/embeddings.py)
- **Document Ingestors:** [providers/pdf_ingestor.py](providers/pdf_ingestor.py), [providers/docx_ingestor.py](providers/docx_ingestor.py), [providers/sheet_ingestor.py](providers/sheet_ingestor.py)
- **Vector Store:** [core/vector_store.py](core/vector_store.py)
- **AI Factory:** [core/ai_factory.py](core/ai_factory.py)

**Behavior:**
- Every external API call wrapped in try/except
- Provider-specific errors converted to domain exceptions
- Detailed error context preserved in `details` field

---

## Exception Hierarchy

**File:** [api/core/exceptions.py](api/core/exceptions.py)

```
BaseAppException (root)
├── LLMException - Language model failures
├── EmbeddingException - Embedding generation failures
├── VectorStoreException - ChromaDB operation failures
├── IngestionException - Document processing pipeline failures
├── FileProcessingException - File I/O and parsing failures
└── DatabaseException - PostgreSQL query/connection failures
```

**Each exception contains:**
- `error_code`: Machine-readable identifier (e.g., "LLM_OPENAI_ERROR")
- `user_message`: Frontend-safe error description
- `details`: Dict with debugging context (provider, model, original error, etc.)

---

## Logging Infrastructure

**File:** [api/core/logging.py](api/core/logging.py)

**Dual output:**
1. **Console (stdout)** - Level: INFO - Real-time monitoring
2. **File (`logs/app.log`)** - Level: DEBUG - Rotating logs (10MB max, 5 backups)

**Format:** `[timestamp] [LEVEL] [module:function:line] message`

**Usage in all modules:**
```python
from api.core.logging import get_logger
logger = get_logger(__name__)

logger.info("Processing started")
logger.error("Failed to connect", exc_info=True)  # Includes traceback
```

---

## Response Schema Extensions

**Files:**
- [api/schemas/query.py](api/schemas/query.py)
- [api/schemas/project.py](api/schemas/project.py)
- [api/schemas/auth.py](api/schemas/auth.py)

**Added fields (optional):**
```python
error_code: Optional[str] = None
error_message: Optional[str] = None
```

**Success response:** Error fields are `None`
**Failure response:** Error fields populated with code/message

**Example:**
```json
{
  "status": "error",
  "query": "What is the capital?",
  "answer": "",
  "sources": [],
  "error_code": "LLM_OPENAI_ERROR",
  "error_message": "AI model is temporarily unavailable. Please try again."
}
```

---

## Router Layer Error Handling

### Query Router ([api/routers/query.py](api/routers/query.py))
- Catches domain exceptions
- Returns `QueryResponse` with error fields populated
- Returns HTTP 200 with error status (frontend checks `status` field)

### Ingestion Router ([api/routers/ingestion.py](api/routers/ingestion.py))
- Catches exceptions during file upload/save
- Re-raises to global handler (returns HTTP 500 with error JSON)
- Background job errors tracked in DB and Redis

### Citations Router ([api/routers/citations.py](api/routers/citations.py))
- Catches vector store/DB errors
- Re-raises to global handler

### Projects Router ([api/routers/projects.py](api/routers/projects.py))
- Delegates to service layer
- Service layer raises exceptions for file/DB failures

---

## Ingestion Pipeline Error Handling

**File:** [rag/ingestion/folder.py](rag/ingestion/folder.py)

**Per-file error isolation:**
- Each file processed independently
- File processing errors logged and added to `failed_files` list
- Other files continue processing

**Returns ingestion summary:**
```python
{
  "total_files": 10,
  "processed": 8,
  "failed": 2,
  "processed_files": ["file1.pdf", "file2.docx", ...],
  "failed_files": [
    {
      "filename": "corrupted.pdf",
      "error_code": "FILE_PDF_PROCESSING_ERROR",
      "error_message": "Failed to process PDF file: corrupted.pdf"
    }
  ]
}
```

**Vector store failures:**
- Fail entire job (can't partially store documents)
- Job status updated to "failed" in DB and Redis
- Full error details logged

---

## RAG Retrieval Error Handling

**File:** [rag/retrieval/answer.py](rag/retrieval/answer.py)

**Protected operations:**
1. Vector store existence check → `FileProcessingException`
2. Vector store initialization → `VectorStoreException`
3. Similarity search → `VectorStoreException` (embedding failures propagate)
4. LLM invocation → `LLMException`

**Behavior:**
- Errors propagate to service → router → global handler
- Full query context logged (truncated query text)

---

## Conversation Error Handling

**File:** [api/services/conversation_service.py](api/services/conversation_service.py)

**Non-critical operation:**
- Conversation summary updates wrapped in try/except
- LLM failures logged as warnings
- Query response still succeeds (conversation continues without summary)

**Critical operations:**
- Append message to DB → failure propagates
- Fetch conversation → failure propagates

---

## Multi-Tenancy Isolation

**Error handling preserves workspace isolation:**

✅ Database queries always filter by `workspace_id` + `project_id`
✅ Errors in one tenant don't affect others
✅ File paths scoped to `vector_stores/{workspace_id}/{project_id}/`
✅ Background jobs track failures per-job (Redis + DB)

---

## What Changed vs. Before

### Before ❌
- Raw exceptions crashed the server
- Stack traces exposed to frontend
- No logging infrastructure
- print() statements for debugging
- One bad file failed entire ingestion batch
- LLM/embedding failures = unhandled 500 errors
- Redis errors silently swallowed with `pass`

### After ✅
- All errors caught and logged
- Clean JSON errors returned to frontend
- Structured logging to console + rotating files
- Per-file error handling in ingestion
- Domain-specific exceptions with context
- Redis errors logged but don't block operations
- Server never crashes - requests always return valid responses

---

## Critical Paths Protected

### 1. Query Path
**Flow:** router → service → answer_query → vector_store + LLM
**Protected:**
- DB query for project validation
- Vector store loading
- Similarity search (embedding + ChromaDB)
- LLM invocation
- Conversation summary update (non-critical)

### 2. Ingestion Path
**Flow:** router → service → background job → ingest_folder → providers
**Protected:**
- File upload/save (synchronous)
- Directory creation
- Per-file processing (isolated failures)
- Vector store operations
- Redis status updates (non-critical)
- DB status updates (critical)

### 3. Citation Path
**Flow:** router → service → vector_store query
**Protected:**
- DB query for project validation
- Vector store loading
- Metadata query

### 4. Project CRUD
**Flow:** router → service → DB + filesystem
**Protected:**
- Directory creation
- DB inserts/updates
- Directory cleanup (soft-delete)

---

## Testing Checklist

### Unit Tests Needed
- [ ] Mock LLM to raise exception → verify structured error response
- [ ] Mock embedding API failure → verify ingestion continues with error tracking
- [ ] Corrupt PDF upload → verify file marked as failed, others processed
- [ ] Invalid API key → verify clean error message returned
- [ ] Vector store unavailable → verify query fails gracefully

### Manual Testing
- [ ] Stop Ollama (if configured) → query should return "Local AI model unavailable"
- [ ] Invalid OpenAI key → ingestion should fail with clear error
- [ ] Upload 10 PDFs, corrupt 2 → verify 8 succeed, 2 failed tracked in logs
- [ ] Query during ChromaDB permission error → verify structured error
- [ ] Check `logs/app.log` for full tracebacks

### Multi-Tenancy Testing
- [ ] Error in tenant A doesn't affect tenant B queries
- [ ] Workspace isolation maintained in all error paths
- [ ] Job failures tracked separately per project

---

## Files Created

1. [api/core/exceptions.py](api/core/exceptions.py) - Exception hierarchy
2. [api/core/logging.py](api/core/logging.py) - Logging setup
3. [logs/](logs/) - Log directory (auto-created)
4. [api/schemas/__init__.py](api/schemas/__init__.py) - ErrorDetail schema

---

## Files Modified

### Core Infrastructure
- [api/main.py](api/main.py) - Global exception handlers, logging init
- [core/ai_factory.py](core/ai_factory.py) - Provider initialization error handling
- [core/vector_store.py](core/vector_store.py) - All operations wrapped

### Routers
- [api/routers/query.py](api/routers/query.py) - Catch domain exceptions
- [api/routers/ingestion.py](api/routers/ingestion.py) - Logging + exception handling
- [api/routers/citations.py](api/routers/citations.py) - Logging + exception handling
- [api/routers/projects.py](api/routers/projects.py) - No changes (service handles errors)

### Services
- [api/services/query_service.py](api/services/query_service.py) - DB + file checks
- [api/services/ingestion_job_service.py](api/services/ingestion_job_service.py) - Comprehensive error tracking
- [api/services/conversation_service.py](api/services/conversation_service.py) - Non-critical LLM failure handling
- [api/services/citation_service.py](api/services/citation_service.py) - DB + vector store wrapping
- [api/services/project_service.py](api/services/project_service.py) - File + DB error handling

### RAG Layer
- [rag/retrieval/answer.py](rag/retrieval/answer.py) - All operations wrapped
- [rag/ingestion/folder.py](rag/ingestion/folder.py) - Per-file error isolation
- [rag/ingestion/summarization.py](rag/ingestion/summarization.py) - LLM fallback with logging

### Providers
- [providers/openai/llm.py](providers/openai/llm.py) - invoke() wrapped
- [providers/openai/embeddings.py](providers/openai/embeddings.py) - Both methods wrapped
- [providers/gemini/llm.py](providers/gemini/llm.py) - invoke() wrapped
- [providers/gemini/embeddings.py](providers/gemini/embeddings.py) - Both methods wrapped
- [providers/ollama/llm.py](providers/ollama/llm.py) - invoke() wrapped
- [providers/huggingface/embeddings.py](providers/huggingface/embeddings.py) - Both methods wrapped
- [providers/pdf_ingestor.py](providers/pdf_ingestor.py) - ingest() wrapped
- [providers/docx_ingestor.py](providers/docx_ingestor.py) - ingest() wrapped
- [providers/sheet_ingestor.py](providers/sheet_ingestor.py) - ingest() wrapped

### Schemas
- [api/schemas/query.py](api/schemas/query.py) - Added error_code, error_message
- [api/schemas/project.py](api/schemas/project.py) - Added error_code, error_message
- [api/schemas/auth.py](api/schemas/auth.py) - Added error_code, error_message

---

## Key Design Decisions

### 1. Extend vs. New Schemas
**Decision:** Extended existing response schemas with optional error fields
**Rationale:** Simpler frontend integration - same response type always returned

### 2. Fail-Safe vs. Fail-Fast
**Decision:**
- **Fail-safe:** Ingestion (per-file), conversation summary, Redis
- **Fail-fast:** Queries, citations, critical DB operations
**Rationale:** Balance between user experience and data integrity

### 3. Logging Levels
**Decision:** INFO for console, DEBUG for file
**Rationale:** Production-ready defaults - detailed logs available when needed

### 4. No Request IDs
**Decision:** Kept logging simple without request tracking
**Rationale:** User preference - can be added later if needed

### 5. Router Error Handling Pattern
**Decision:**
- Query: Returns error in response body (HTTP 200)
- Other endpoints: Re-raise to global handler (HTTP 500)
**Rationale:** Query responses need structured data; others use standard HTTP errors

---

## Maintenance Notes

### Adding New Exceptions
1. Define in [api/core/exceptions.py](api/core/exceptions.py)
2. Inherit from `BaseAppException`
3. Set appropriate `error_code` prefix

### Adding New Providers
1. Wrap all external calls in try/except
2. Raise domain exception on failure
3. Import and use logger: `logger = get_logger(__name__)`

### Debugging Tips
- Check `logs/app.log` for full tracebacks
- Search logs by `error_code` to find specific failures
- Use `extra={}` parameter in logger calls for structured data

---

## Open Questions / Future Enhancements

1. **Metrics/Alerting:** Add Prometheus metrics for error rates?
2. **Request IDs:** Add X-Request-ID middleware for distributed tracing?
3. **Retry Logic:** Should LLM/embedding calls auto-retry on transient failures?
4. **Circuit Breaker:** Implement circuit breaker for external API calls?
5. **Error Recovery:** Should ingestion jobs support resume-from-failure?

---

## Summary

The RAG backend now has production-grade error handling with:

✅ **Three-layer failure boundaries** (global → service → provider)
✅ **Structured error responses** with codes and user-friendly messages
✅ **Comprehensive logging** to console and rotating files
✅ **Per-file error isolation** in ingestion pipeline
✅ **Multi-tenancy preservation** in all error paths
✅ **No server crashes** - all requests return valid HTTP responses
✅ **Full observability** - all errors logged with context

**Business logic unchanged** - only error handling added around existing code.
