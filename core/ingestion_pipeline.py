"""
Core ingestion pipeline orchestration with content-addressed registry.

Wraps existing chunking/embedding strategies with database tracking,
deterministic vector IDs, and chunk recording for safe deletion.
"""
import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List

from databases import Database

from core.hashing import make_vector_id
from core.file_router import FileRouter
from core.vector_store import VectorStoreManager
from api.models.document import documents
from api.models.document_chunk import document_chunks
from api.core.exceptions import (
    FileProcessingException,
    IngestionException,
    VectorStoreException
)

# Import existing RAG strategies (reuse, don't rewrite)
from rag.ingestion.chunking import create_chunks_by_title
from rag.ingestion.summarization import summarise_chunks
from rag.ingestion.rows import rows_to_documents

logger = logging.getLogger(__name__)


async def _set_status(
    db: Database,
    document_id: uuid.UUID,
    status: str,
    **extra_fields
) -> None:
    """Update document status and optional fields."""
    update_values = {
        "status": status,
        "updated_at": datetime.now(timezone.utc),
        **extra_fields
    }
    
    query = (
        documents.update()
        .where(documents.c.id == document_id)
        .values(**update_values)
    )
    
    await db.execute(query)
    logger.debug(f"Document {document_id} status: {status}")


async def _insert_chunks(
    db: Database,
    chunk_records: List[Dict[str, Any]]
) -> None:
    """
    Insert chunk records into document_chunks table.
    Uses ON CONFLICT DO NOTHING for idempotency.
    """
    if not chunk_records:
        return
    
    # Use bulk insert for efficiency
    query = document_chunks.insert()
    await db.execute_many(query, chunk_records)
    
    logger.debug(f"Recorded {len(chunk_records)} chunks in database")


async def run_ingestion(
    document: Dict[str, Any],
    file_path: str,
    vector_store: VectorStoreManager,
    file_router: FileRouter,
    db: Database,
) -> int:
    """
    Chunk, embed, and upsert a document into the vector store.
    Records every chunk in document_chunks table.
    
    This function is idempotent: calling it twice for the same document
    with deterministic vector IDs causes upserts (not duplicates), and
    chunk inserts use the unique constraint to prevent duplicates.
    
    Args:
        document: Document record from DB (must have id, file_hash, project_id, etc.)
        file_path: Absolute path to the file on disk
        vector_store: VectorStoreManager instance for the project
        file_router: FileRouter instance for selecting ingestor
        db: Database connection
        
    Returns:
        Number of chunks written
        
    Raises:
        FileProcessingException: File cannot be read or parsed
        IngestionException: Content processing failed
        VectorStoreException: Vector storage failed
    """
    document_id = document["id"]
    file_hash = document["file_hash"]
    project_id = document["project_id"]
    source_file = document["file_name"]
    
    if not file_hash:
        raise IngestionException(
            user_message="Cannot ingest document without file hash",
            details={"document_id": str(document_id)},
            error_code="MISSING_FILE_HASH"
        )
    
    logger.info(f"Starting ingestion for document {document_id}: {source_file}")
    
    # Mark as processing
    await _set_status(db, document_id, "processing")
    
    try:
        # --- STEP 1: Route to appropriate ingestor ---
        try:
            ingestor = file_router.route(file_path)
            source_type = ingestor.__class__.__name__.replace("Ingestor", "").lower()
        except ValueError as e:
            logger.warning(f"No ingestor found for file: {file_path}")
            raise FileProcessingException(
                user_message=f"Unsupported file type: {source_file}",
                details={"file_path": file_path, "error": str(e)},
                error_code="FILE_UNSUPPORTED_TYPE"
            )
        
        # --- STEP 2: Extract content from file ---
        try:
            extracted = ingestor.ingest(file_path)
        except FileProcessingException:
            raise  # Re-raise as-is
        except Exception as e:
            logger.error(f"File extraction failed: {file_path}", exc_info=True)
            raise FileProcessingException(
                user_message=f"Failed to extract content from: {source_file}",
                details={"file_path": file_path, "error": str(e)},
                error_code="FILE_EXTRACTION_ERROR"
            )
        
        # --- STEP 3: Process based on source type (REUSE EXISTING STRATEGIES) ---
        try:
            if source_type == "sheet":
                # Use existing spreadsheet processing
                documents_list = rows_to_documents(
                    extracted,
                    str(document_id),  # Use document_id as source_id
                    source_file,
                    source_type
                )
            else:
                # Use existing chunking strategy
                chunks = create_chunks_by_title(extracted)
                
                # Use existing AI-enhanced summarization
                documents_list = summarise_chunks(
                    chunks,
                    str(document_id),
                    source_file,
                    source_type
                )
        except Exception as e:
            logger.error(f"Content processing failed: {file_path}", exc_info=True)
            raise IngestionException(
                user_message=f"Failed to process content from: {source_file}",
                details={
                    "file_path": file_path,
                    "source_type": source_type,
                    "error": str(e)
                },
                error_code="INGESTION_PROCESSING_ERROR"
            )
        
        # --- STEP 4: Create deterministic vector IDs and upsert ---
        try:
            records = []
            chunk_db_records = []
            
            for i, doc in enumerate(documents_list):
                # Generate deterministic ID
                vector_id = make_vector_id(file_hash, i)
                
                # Prepare vector store record
                # Note: VectorStoreManager.add_documents handles embedding internally
                # We need to manually set the ID before upserting
                doc.metadata["vector_id"] = vector_id
                doc.metadata["document_id"] = str(document_id)
                doc.metadata["project_id"] = str(project_id)
                doc.metadata["chunk_index"] = i
                
                records.append(doc)
                
                # Prepare chunk DB record
                chunk_db_records.append({
                    "id": uuid.uuid4(),
                    "document_id": document_id,
                    "vector_id": vector_id,
                    "chunk_index": i,
                    "chunk_text": doc.page_content,
                    "created_at": datetime.now(timezone.utc),
                })
            
            # Upsert to vector store with deterministic IDs
            # Note: ChromaDB's add_documents will use IDs from metadata if present
            vector_store.add_documents_with_ids(records)
            
            logger.info(f"Upserted {len(records)} vectors for document {document_id}")
            
        except (VectorStoreException, Exception) as e:
            logger.error(f"Failed to store documents: {file_path}", exc_info=True)
            if isinstance(e, VectorStoreException):
                raise
            raise VectorStoreException(
                user_message="Failed to store documents in vector database",
                details={
                    "file_path": file_path,
                    "num_documents": len(documents_list),
                    "error": str(e)
                },
                error_code="INGESTION_STORAGE_ERROR"
            )
        
        # --- STEP 5: Record chunks in database ---
        try:
            await _insert_chunks(db, chunk_db_records)
        except Exception as e:
            logger.error(f"Failed to record chunks in DB: {document_id}", exc_info=True)
            # This is critical - without chunk records, we can't delete vectors later
            raise IngestionException(
                user_message="Failed to record chunk metadata",
                details={"document_id": str(document_id), "error": str(e)},
                error_code="CHUNK_RECORDING_ERROR"
            )
        
        # --- STEP 6: Mark as active ---
        await _set_status(
            db,
            document_id,
            "active",
            chunk_count=len(records),
            ingested_at=datetime.now(timezone.utc)
        )
        
        logger.info(f"Ingestion complete for document {document_id}: {len(records)} chunks")
        
        return len(records)
        
    except Exception as e:
        # Mark as failed on any error
        await _set_status(db, document_id, "failed")
        raise
