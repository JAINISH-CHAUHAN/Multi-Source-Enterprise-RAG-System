# Error Handling Quick Reference

## Common Error Scenarios & Responses

### 1. LLM API Key Invalid/Expired

**What happens:**
- LLM provider (OpenAI/Gemini/Ollama) raises authentication error
- Caught in [providers/{provider}/llm.py](../providers/)
- Raised as `LLMException` with code `LLM_{PROVIDER}_ERROR`

**Frontend receives:**
```json
{
  "status": "error",
  "query": "What is X?",
  "answer": "",
  "sources": [],
  "error_code": "LLM_OPENAI_ERROR",
  "error_message": "AI model is temporarily unavailable. Please try again."
}
```

**Logged to file:**
```
[2026-02-11 10:23:45] [ERROR] [providers.openai.llm:invoke:XX] OpenAI LLM invocation failed: Invalid API key
extra: {"model": "gpt-4o-mini", "error_type": "AuthenticationError"}
[Full traceback...]
```

---

### 2. Embedding Service Down (CUDA/GPU Error)

**What happens:**
- Embedding provider fails during `embed_documents()` or `embed_query()`
- Caught in [providers/{provider}/embeddings.py](../providers/)
- Raised as `EmbeddingException` with code `EMBEDDING_{PROVIDER}_ERROR`

**During query:**
```json
{
  "error_code": "EMBEDDING_OPENAI_QUERY_ERROR",
  "error_message": "Failed to process your query. Please try again."
}
```

**During ingestion:**
- Job status: "failed"
- Error message in DB: "[EMBEDDING_OPENAI_ERROR] Failed to generate embeddings. Please try again."
- DB record includes full error context

---

### 3. Corrupted PDF Upload

**What happens:**
- PDF ingestor calls `partition_pdf()` → raises exception
- Caught in [providers/pdf_ingestor.py](../providers/pdf_ingestor.py)
- Raised as `FileProcessingException` with code `FILE_PDF_PROCESSING_ERROR`
- Ingestion pipeline catches it, logs, continues with other files

**Ingestion job result:**
```python
# Stored in PostgreSQL ingestion_jobs table
{
  "status": "completed",  # Job completes even with some failures
  "error_message": None   # Individual file errors tracked in logs
}
```

**Logged to file:**
```
[2026-02-11 10:25:30] [WARNING] [rag.ingestion.folder:ingest_folder:XX] Failed to process file corrupted.pdf: Failed to process PDF file: corrupted.pdf
[ERROR] [providers.pdf_ingestor:ingest:XX] PDF processing failed: corrupted.pdf
extra: {"file_path": "/path/to/corrupted.pdf", "error_type": "PDFException"}
```

---

### 4. ChromaDB Connection Failure

**What happens:**
- Vector store initialization or query fails
- Caught in [core/vector_store.py](../core/vector_store.py)
- Raised as `VectorStoreException` with code `VECTOR_STORE_{OPERATION}_ERROR`

**During query:**
```json
{
  "error_code": "VECTOR_STORE_LOAD_ERROR",
  "error_message": "Vector database is temporarily unavailable."
}
```

**During ingestion:**
- Job status: "failed"
- All files skipped (can't store partially)
- Error message: "[VECTOR_STORE_INIT_ERROR] Failed to initialize vector store..."

---

### 5. Disk Space Full (Directory Creation)

**What happens:**
- `os.makedirs()` fails in project creation or ingestion
- Caught in service layer
- Raised as `FileProcessingException` with code `FILE_DIRECTORY_CREATION_ERROR`

**Response:**
```json
{
  "error_code": "FILE_DIRECTORY_CREATION_ERROR",
  "error_message": "Failed to create storage directory. Please contact support."
}
```

---

### 6. Database Connection Lost

**What happens:**
- PostgreSQL query fails (timeout, connection lost, etc.)
- Caught in service layer
- Raised as `DatabaseException` with code `DATABASE_{OPERATION}_ERROR`

**Response:**
```json
{
  "error_code": "DATABASE_QUERY_ERROR",
  "error_message": "Failed to access project information."
}
```

**Global handler logs:**
```
[2026-02-11 10:30:00] [CRITICAL] [api.main:handle_unexpected_exception:XX] Unhandled exception: connection already closed
extra: {"exception_type": "InterfaceError", "path": "/projects/123/query", "traceback": "..."}
```

---

### 7. Ollama Not Running (Local LLM)

**What happens:**
- Ollama client initialization or invoke fails
- Caught in [providers/ollama/llm.py](../providers/ollama/llm.py)
- Raised as `LLMException` with code `LLM_OLLAMA_ERROR`

**Response:**
```json
{
  "error_code": "LLM_OLLAMA_ERROR",
  "error_message": "Local AI model is unavailable. Please ensure Ollama is running."
}
```

---

### 8. Background Job Failure (Ingestion)

**What happens:**
- Background task encounters unhandled exception
- Caught in [api/services/ingestion_job_service.py](../api/services/ingestion_job_service.py) `run_ingestion_job()`
- Updates Redis + DB with error details

**Database record:**
```sql
SELECT * FROM ingestion_jobs WHERE id = 'job-uuid';
-- status: "failed"
-- error_message: "[VECTOR_STORE_ADD_ERROR] Failed to store documents in vector database."
```

**Redis state:**
```python
redis_client.hgetall("ingestion:job-uuid")
# {
#   "status": "failed",
#   "error": "Failed to store documents in vector database.",
#   "error_code": "VECTOR_STORE_ADD_ERROR"
# }
```

**Logged to file:**
```
[2026-02-11 10:35:00] [ERROR] [api.services.ingestion_job_service:run_ingestion_job:XX] Ingestion job job-uuid failed with VECTOR_STORE_ADD_ERROR
extra: {
  "job_id": "job-uuid",
  "error_code": "VECTOR_STORE_ADD_ERROR",
  "error_message": "Failed to store documents in vector database.",
  "details": {...},
  "traceback": "..."
}
```

---

## Error Code Reference

### LLM Errors
- `LLM_OPENAI_ERROR` - OpenAI API failure
- `LLM_GEMINI_ERROR` - Google Gemini API failure
- `LLM_OLLAMA_ERROR` - Ollama connection/model failure
- `LLM_INIT_ERROR` - Provider initialization failed

### Embedding Errors
- `EMBEDDING_OPENAI_ERROR` - OpenAI embeddings (batch)
- `EMBEDDING_OPENAI_QUERY_ERROR` - OpenAI embeddings (single query)
- `EMBEDDING_GEMINI_ERROR` - Gemini embeddings (batch)
- `EMBEDDING_GEMINI_QUERY_ERROR` - Gemini embeddings (single query)
- `EMBEDDING_HUGGINGFACE_ERROR` - HuggingFace embeddings (batch)
- `EMBEDDING_HUGGINGFACE_QUERY_ERROR` - HuggingFace embeddings (single)
- `EMBEDDING_INIT_ERROR` - Provider initialization failed

### Vector Store Errors
- `VECTOR_STORE_INIT_ERROR` - Failed to initialize ChromaDB
- `VECTOR_STORE_LOAD_ERROR` - Failed to load existing vector store
- `VECTOR_STORE_ADD_ERROR` - Failed to add documents
- `VECTOR_STORE_QUERY_ERROR` - Failed to query/search
- `VECTOR_STORE_RETRIEVER_ERROR` - Failed to create retriever interface

### File Processing Errors
- `FILE_PDF_PROCESSING_ERROR` - PDF parsing failed
- `FILE_DOCX_PROCESSING_ERROR` - DOCX parsing failed
- `FILE_SHEET_PROCESSING_ERROR` - CSV/XLSX parsing failed
- `FILE_UNSUPPORTED_FORMAT` - File type not supported
- `FILE_DIRECTORY_CREATION_ERROR` - Failed to create directory
- `FILE_UPLOAD_SAVE_ERROR` - Failed to save uploaded file

### Ingestion Errors
- `INGESTION_DIRECTORY_ERROR` - Failed to access folder
- `INGESTION_PROCESSING_ERROR` - Content processing failed
- `INGESTION_STORAGE_ERROR` - Failed to store in vector DB
- `INGESTION_UNEXPECTED_ERROR` - Unhandled error in background job
- `KNOWLEDGE_BASE_NOT_FOUND` - Vector store directory missing
- `KNOWLEDGE_BASE_FOLDER_NOT_FOUND` - Ingestion source folder missing

### Database Errors
- `DATABASE_QUERY_ERROR` - SELECT query failed
- `DATABASE_INSERT_ERROR` - INSERT failed
- `DATABASE_UPDATE_ERROR` - UPDATE failed

### Query Errors
- `QUERY_PROCESSING_ERROR` - Unexpected error during query
- `QUERY_UNEXPECTED_ERROR` - Catch-all for query endpoint

---

## Debugging Workflow

### Step 1: Check Frontend Error
```javascript
// Frontend receives
{
  "error_code": "LLM_OPENAI_ERROR",
  "error_message": "AI model is temporarily unavailable. Please try again."
}
```

### Step 2: Search Logs by Error Code
```bash
cd logs
grep "LLM_OPENAI_ERROR" app.log
```

### Step 3: Find Full Traceback
```bash
# Look for ERROR or CRITICAL level around that timestamp
grep -A 20 "2026-02-11 10:23:45" app.log
```

### Step 4: Check Provider Details
```bash
# Search for the specific provider module
grep "providers.openai.llm" app.log | tail -n 30
```

---

## Testing Error Scenarios Locally

### Simulate LLM Failure
```bash
# Set invalid API key
export OPENAI_API_KEY="invalid_key"
python -m uvicorn api.main:app --reload

# Test query endpoint
curl -X POST "http://localhost:8000/projects/{id}/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "test"}'

# Check logs/app.log for error details
```

### Simulate Vector Store Failure
```bash
# Delete ChromaDB directory while service running
rm -rf vector_stores/{workspace_id}/{project_id}/chroma_db

# Query should return VECTOR_STORE_LOAD_ERROR
```

### Simulate Corrupted File
```bash
# Upload a .pdf with garbage content
echo "not a pdf" > fake.pdf
# Upload via API - should fail with FILE_PDF_PROCESSING_ERROR
# Check that other files in batch still process
```

---

## Production Monitoring

### Key Metrics to Track
1. **Error rates by code:**
   - `grep -c "error_code" logs/app.log | sort | uniq -c`
2. **LLM failure rate:**
   - `grep -c "LLM_.*_ERROR" logs/app.log`
3. **Failed ingestion jobs:**
   - `SELECT COUNT(*) FROM ingestion_jobs WHERE status='failed'`
4. **Most common errors:**
   - `grep "error_code" logs/app.log | cut -d":" -f2 | sort | uniq -c | sort -rn | head -10`

### Alerting Thresholds (Recommended)
- **Critical:** `INTERNAL_ERROR` or `DATABASE_.*_ERROR` > 5/min
- **Warning:** `LLM_.*_ERROR` > 20/min (API issues)
- **Info:** `FILE_.*_PROCESSING_ERROR` (expected user errors)

---

## Error Recovery Procedures

### LLM Provider Down
1. Check API status pages (OpenAI, Google Cloud)
2. Switch to fallback provider if configured
3. If Ollama: `ollama serve` and restart

### Database Connection Lost
1. Check PostgreSQL status: `systemctl status postgresql`
2. Check connection pool: `SELECT count(*) FROM pg_stat_activity`
3. Restart if needed - FastAPI reconnects automatically

### Disk Space Full
1. Check: `df -h`
2. Clean old log files: `find logs/ -name "app.log.*" -mtime +7 -delete`
3. Archive old vector stores if needed

### Background Jobs Stuck
1. Check Redis: `redis-cli KEYS "ingestion:*"`
2. Query DB: `SELECT * FROM ingestion_jobs WHERE status='running' AND created_at < NOW() - INTERVAL '1 hour'`
3. Manually mark as failed if truly stuck

---

## FAQ

**Q: Will errors in one tenant affect others?**
A: No - all errors are scoped to workspace_id/project_id. Background jobs run independently.

**Q: What happens if Redis goes down?**
A: Errors logged but not fatal. Job status still tracked in PostgreSQL. Real-time status unavailable.

**Q: Can I disable file rotation?**
A: Yes - edit [api/core/logging.py](../api/core/logging.py) and replace `RotatingFileHandler` with regular `FileHandler`.

**Q: How do I add custom error codes?**
A: Define in [api/core/exceptions.py](../api/core/exceptions.py), then raise in appropriate layer with that code.

**Q: Why HTTP 200 for query errors?**
A: Query endpoint returns structured data. Frontend checks `status` field. Other endpoints use standard HTTP error codes.
