"""
Document management service for deletion and file operations.

Implements content-addressed deletion using chunk tracking table
for precise vector removal without metadata filtering.
"""
import os
import logging
from datetime import datetime, timezone
from typing import Dict, Any
from uuid import UUID

from databases import Database
from api.core.database import database
from api.models.document import documents
from api.models.document_chunk import document_chunks
from api.models.project import projects
from core.vector_store import VectorStoreManager
from api.core.exceptions import DatabaseException, VectorStoreException

logger = logging.getLogger(__name__)


def safe_delete_file(file_path: str) -> bool:
    """
    Safely delete a file from disk.
    
    Args:
        file_path: Absolute path to file
        
    Returns:
        True if deleted successfully, False if file not found or error
    """
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Deleted file: {file_path}")
            return True
        else:
            logger.warning(f"File not found for deletion: {file_path}")
            return False
    except Exception as e:
        logger.error(f"Failed to delete file {file_path}: {str(e)}", exc_info=True)
        return False


async def delete_document(
    document_id: UUID,
    db: Database = None
) -> Dict[str, Any]:
    """
    Delete a document and all its associated vectors.
    
    Steps:
    1. Mark document as 'deleting' (crash-recovery anchor)
    2. Look up vector IDs from document_chunks table
    3. Delete vectors from ChromaDB by ID (precise, fast)
    4. Delete chunk records from database
    5. Mark document as deleted (soft delete)
    6. Delete file from disk
    
    Args:
        document_id: UUID of the document to delete
        db: Database connection (defaults to global database)
        
    Returns:
        {
            "document_id": str,
            "file_name": str,
            "chunks_deleted": int,
            "file_deleted": bool,
            "deleted_at": str (ISO format),
        }
        
    Raises:
        DatabaseException: Database operation failed
        VectorStoreException: Vector deletion failed
    """
    if db is None:
        db = database
    
    logger.info(f"Starting deletion for document {document_id}")
    
    # Fetch document record
    try:
        doc = await db.fetch_one(
            documents.select().where(documents.c.id == document_id)
        )
    except Exception as e:
        logger.error(f"Failed to fetch document {document_id}: {str(e)}", exc_info=True)
        raise DatabaseException(
            user_message="Failed to fetch document for deletion",
            details={"document_id": str(document_id), "error": str(e)},
            error_code="DATABASE_QUERY_ERROR"
        )
    
    if not doc:
        logger.error(f"Document {document_id} not found")
        raise DatabaseException(
            user_message="Document not found",
            details={"document_id": str(document_id)},
            error_code="DOCUMENT_NOT_FOUND"
        )
    
    # Step 0: Immediately mark as deleting (crash-recovery anchor)
    try:
        await db.execute(
            documents.update()
            .where(documents.c.id == document_id)
            .values(
                status="deleting",
                updated_at=datetime.now(timezone.utc)
            )
        )
        logger.debug(f"Document {document_id} marked as deleting")
    except Exception as e:
        logger.error(f"Failed to mark document as deleting: {str(e)}", exc_info=True)
        raise DatabaseException(
            user_message="Failed to update document status",
            details={"document_id": str(document_id), "error": str(e)},
            error_code="DATABASE_UPDATE_ERROR"
        )
    
    # Step 1: Look up vector IDs from chunk table
    try:
        chunk_rows = await db.fetch_all(
            document_chunks.select()
            .where(document_chunks.c.document_id == document_id)
        )
        vector_ids = [row["vector_id"] for row in chunk_rows]
        
        logger.info(f"Found {len(vector_ids)} chunks for document {document_id}")
    except Exception as e:
        logger.error(f"Failed to fetch chunks for document {document_id}: {str(e)}", exc_info=True)
        raise DatabaseException(
            user_message="Failed to fetch document chunks",
            details={"document_id": str(document_id), "error": str(e)},
            error_code="DATABASE_QUERY_ERROR"
        )
    
    # Step 2: Delete vectors from ChromaDB
    deleted_count = 0
    
    # Get workspace_id from project (needed for both vector and file deletion)
    try:
        project = await db.fetch_one(
            projects.select().where(projects.c.id == doc["project_id"])
        )
        
        if not project:
            raise DatabaseException(
                user_message="Project not found for document",
                details={"project_id": str(doc["project_id"])},
                error_code="PROJECT_NOT_FOUND"
            )
        
        workspace_id = project["workspace_id"]
        BASE_DIR = os.path.abspath("vector_stores")
        
    except DatabaseException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch project for document {document_id}: {str(e)}", exc_info=True)
        raise DatabaseException(
            user_message="Failed to fetch project information",
            details={"document_id": str(document_id), "error": str(e)},
            error_code="DATABASE_QUERY_ERROR"
        )
    
    if vector_ids:
        # Construct ChromaDB path
        try:
            chroma_dir = os.path.join(
                BASE_DIR,
                str(workspace_id),
                str(doc["project_id"]),
                "chroma_db"
            )
            
            # Initialize vector store
            vector_store = VectorStoreManager(persist_directory=chroma_dir)
            
            # Delete by IDs (precise and fast)
            deleted_count = vector_store.delete_by_ids(vector_ids)
            
            logger.info(f"Deleted {deleted_count} vectors from ChromaDB for document {document_id}")
            
        except VectorStoreException:
            raise
        except Exception as e:
            logger.error(f"Failed to delete vectors for document {document_id}: {str(e)}", exc_info=True)
            raise VectorStoreException(
                user_message="Failed to delete vectors from database",
                details={"document_id": str(document_id), "error": str(e)},
                error_code="VECTOR_DELETE_ERROR"
            )
    else:
        logger.warning(f"No chunks found for document {document_id}, skipping vector deletion")
    
    # Step 3: Delete chunk records from database
    try:
        await db.execute(
            document_chunks.delete()
            .where(document_chunks.c.document_id == document_id)
        )
        logger.debug(f"Deleted chunk records for document {document_id}")
    except Exception as e:
        logger.error(f"Failed to delete chunk records: {str(e)}", exc_info=True)
        # Non-critical, continue with document deletion
    
    # Step 4: Mark document as deleted (soft delete)
    try:
        await db.execute(
            documents.update()
            .where(documents.c.id == document_id)
            .values(
                is_deleted=True,
                deleted_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
        )
        logger.debug(f"Document {document_id} marked as deleted")
    except Exception as e:
        logger.error(f"Failed to mark document as deleted: {str(e)}", exc_info=True)
        raise DatabaseException(
            user_message="Failed to update document status",
            details={"document_id": str(document_id), "error": str(e)},
            error_code="DATABASE_UPDATE_ERROR"
        )
    
    # Step 5: Delete file from disk
    try:
        file_path = os.path.join(
            BASE_DIR,
            str(workspace_id),
            str(doc["project_id"]),
            "knowledge_base",
            doc["file_name"]
        )
        
        file_deleted = safe_delete_file(file_path)
    except Exception as e:
        logger.warning(f"Failed to construct file path for deletion: {str(e)}")
        file_deleted = False
    
    deleted_at = datetime.now(timezone.utc)
    
    result = {
        "document_id": str(document_id),
        "file_name": doc["file_name"],
        "chunks_deleted": deleted_count,
        "file_deleted": file_deleted,
        "deleted_at": deleted_at.isoformat(),
    }
    
    logger.info(f"Deletion complete for document {document_id}: {result}")
    
    return result
