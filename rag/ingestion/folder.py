import os
import uuid
from typing import Dict, List, Any
from core.file_router import FileRouter
from rag.ingestion.chunking import create_chunks_by_title
from rag.ingestion.rows import rows_to_documents
from rag.ingestion.summarization import summarise_chunks
from api.core.exceptions import FileProcessingException, VectorStoreException, IngestionException
from api.core.logging import get_logger

logger = get_logger(__name__)


def ingest_folder(folder_path, vector_store, file_router: FileRouter) -> Dict[str, Any]:
    """
    Ingest all files in a folder with per-file error handling.
    
    Returns a summary with counts of processed, failed, and error details.
    """
    logger.info(f"Starting folder ingestion: {folder_path}")
    
    processed_files = []
    failed_files = []
    
    try:
        files = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))]
        logger.info(f"Found {len(files)} files to process")
    except Exception as e:
        logger.error(f"Failed to list directory: {folder_path}", exc_info=True)
        raise IngestionException(
            user_message=f"Failed to access directory: {folder_path}",
            details={"folder_path": folder_path, "error": str(e)},
            error_code="INGESTION_DIRECTORY_ERROR"
        )
    
    for filename in files:
        file_path = os.path.join(folder_path, filename)
        
        try:
            logger.info(f"Processing file: {filename}")
            run_complete_ingestion_pipeline(file_path, vector_store, file_router)
            processed_files.append(filename)
            logger.info(f"Successfully processed: {filename}")
        except FileProcessingException as e:
            # Log and continue with other files
            logger.warning(f"Failed to process file {filename}: {e.user_message}")
            failed_files.append({
                "filename": filename,
                "error_code": e.error_code,
                "error_message": e.user_message
            })
        except Exception as e:
            # Catch-all for unexpected errors
            logger.error(f"Unexpected error processing {filename}", exc_info=True)
            failed_files.append({
                "filename": filename,
                "error_code": "INGESTION_UNEXPECTED_ERROR",
                "error_message": f"Unexpected error: {str(e)}"
            })
    
    # Persist vector store after all files processed
    try:
        vector_store.persist()
        logger.info("Vector store persisted successfully")
    except Exception as e:
        logger.error("Failed to persist vector store", exc_info=True)
        # Don't fail the entire job if persistence fails (Chroma auto-persists)
    
    summary = {
        "total_files": len(files),
        "processed": len(processed_files),
        "failed": len(failed_files),
        "processed_files": processed_files,
        "failed_files": failed_files
    }
    
    logger.info(f"Folder ingestion complete: {summary['processed']}/{summary['total_files']} succeeded")
    
    return summary


def run_complete_ingestion_pipeline(file_path, vector_store, file_router):
    """
    Complete ingestion pipeline for a single file.
    
    Raises domain-specific exceptions on failure.
    """
    source_id = str(uuid.uuid4())
    source_file = os.path.basename(file_path)

    try:
        # Route to appropriate ingestor
        ingestor = file_router.route(file_path)
        source_type = ingestor.__class__.__name__.replace("Ingestor", "").lower()
    except ValueError as e:
        logger.warning(f"No ingestor found for file: {file_path}")
        raise FileProcessingException(
            user_message=f"Unsupported file type: {source_file}",
            details={"file_path": file_path, "error": str(e)},
            error_code="FILE_UNSUPPORTED_TYPE"
        )
    
    try:
        # Extract content from file
        extracted = ingestor.ingest(file_path)
    except FileProcessingException:
        # Re-raise file processing exceptions from ingestors
        raise
    except Exception as e:
        logger.error(f"File extraction failed: {file_path}", exc_info=True)
        raise FileProcessingException(
            user_message=f"Failed to extract content from: {source_file}",
            details={"file_path": file_path, "error": str(e), "error_type": type(e).__name__},
            error_code="FILE_EXTRACTION_ERROR"
        )
    
    try:
        # Process based on source type
        if source_type == "sheet":
            documents = rows_to_documents(
                extracted, source_id, source_file, source_type
            )
        else:
            # Chunk the content
            chunks = create_chunks_by_title(extracted)
            
            # Create AI-enhanced summaries
            documents = summarise_chunks(
                chunks, source_id, source_file, source_type
            )
    except Exception as e:
        logger.error(f"Content processing failed: {file_path}", exc_info=True)
        raise IngestionException(
            user_message=f"Failed to process content from: {source_file}",
            details={
                "file_path": file_path,
                "source_type": source_type,
                "error": str(e),
                "error_type": type(e).__name__
            },
            error_code="INGESTION_PROCESSING_ERROR"
        )
    
    try:
        # Add documents to vector store
        vector_store.add_documents(documents)
        logger.debug(f"Added {len(documents)} documents to vector store for {source_file}")
    except (VectorStoreException, Exception) as e:
        logger.error(f"Failed to store documents: {file_path}", exc_info=True)
        # If we can't store documents, this is a critical failure
        if isinstance(e, VectorStoreException):
            raise
        raise VectorStoreException(
            user_message="Failed to store documents in vector database.",
            details={
                "file_path": file_path,
                "num_documents": len(documents),
                "error": str(e),
                "error_type": type(e).__name__
            },
            error_code="INGESTION_STORAGE_ERROR"
        )
