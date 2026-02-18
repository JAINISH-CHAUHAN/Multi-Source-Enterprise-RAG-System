"""
Document management endpoints.

Provides CRUD operations for documents including listing, details,
deletion, and retry functionality.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Dict, Any
from uuid import UUID

from api.core.dependencies import get_current_user
from api.core.database import database
from api.core.logging import get_logger
from api.core.exceptions import BaseAppException
from api.models.document import documents
from api.models.project import projects
from api.services.document_service import delete_document
from core.task_queue import enqueue_task

router = APIRouter()
logger = get_logger(__name__)


@router.get("/projects/{project_id}/documents")
async def list_documents(
    project_id: str,
    user=Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """
    List all documents in a project.
    
    Returns document metadata including status, chunk count, and file hash.
    Excludes deleted documents by default.
    """
    try:
        # Verify project ownership
        project = await database.fetch_one(
            projects.select().where(
                (projects.c.id == project_id) &
                (projects.c.workspace_id == user["workspace_id"]) &
                (projects.c.is_deleted == False)
            )
        )
        
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        
        # Fetch documents
        docs = await database.fetch_all(
            documents.select()
            .where(
                (documents.c.project_id == project_id) &
                (documents.c.is_deleted == False)
            )
            .order_by(documents.c.created_at.desc())
        )
        
        # Return summarized info (don't expose full hash for security)
        result = []
        for doc in docs:
            result.append({
                "id": str(doc["id"]),
                "file_name": doc["file_name"],
                "source_type": doc["source_type"],
                "status": doc["status"],
                "chunk_count": doc["chunk_count"],
                "created_at": doc["created_at"].isoformat() if doc["created_at"] else None,
                "ingested_at": doc["ingested_at"].isoformat() if doc["ingested_at"] else None,
            })
        
        logger.info(f"Listed {len(result)} documents for project {project_id}")
        
        return result
        
    except HTTPException:
        raise
    except BaseAppException as e:
        logger.warning(f"Failed to list documents: {e.error_code}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error listing documents: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list documents"
        )


@router.get("/projects/{project_id}/documents/{document_id}")
async def get_document(
    project_id: str,
    document_id: str,
    user=Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Get detailed information about a single document.
    
    Includes full status, chunk count, and timestamps.
    """
    try:
        # Verify project ownership
        project = await database.fetch_one(
            projects.select().where(
                (projects.c.id == project_id) &
                (projects.c.workspace_id == user["workspace_id"]) &
                (projects.c.is_deleted == False)
            )
        )
        
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        
        # Fetch document
        doc = await database.fetch_one(
            documents.select().where(
                (documents.c.id == document_id) &
                (documents.c.project_id == project_id)
            )
        )
        
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        result = {
            "id": str(doc["id"]),
            "project_id": str(doc["project_id"]),
            "file_name": doc["file_name"],
            "source_type": doc["source_type"],
            "status": doc["status"],
            "chunk_count": doc["chunk_count"],
            "is_deleted": doc["is_deleted"],
            "created_at": doc["created_at"].isoformat() if doc["created_at"] else None,
            "ingested_at": doc["ingested_at"].isoformat() if doc["ingested_at"] else None,
            "deleted_at": doc["deleted_at"].isoformat() if doc["deleted_at"] else None,
            "updated_at": doc["updated_at"].isoformat() if doc["updated_at"] else None,
        }
        
        logger.info(f"Retrieved document {document_id}")
        
        return result
        
    except HTTPException:
        raise
    except BaseAppException as e:
        logger.warning(f"Failed to get document: {e.error_code}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error getting document: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get document"
        )


@router.delete("/projects/{project_id}/documents/{document_id}")
async def delete_document_endpoint(
    project_id: str,
    document_id: str,
    user=Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Delete a document and all its vectors.
    
    This operation:
    1. Marks document as 'deleting'
    2. Looks up vector IDs from chunk table
    3. Deletes vectors from ChromaDB
    4. Deletes chunk records
    5. Soft-deletes document
    6. Removes file from disk
    """
    try:
        # Verify project ownership
        project = await database.fetch_one(
            projects.select().where(
                (projects.c.id == project_id) &
                (projects.c.workspace_id == user["workspace_id"]) &
                (projects.c.is_deleted == False)
            )
        )
        
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        
        # Verify document belongs to project
        doc = await database.fetch_one(
            documents.select().where(
                (documents.c.id == document_id) &
                (documents.c.project_id == project_id)
            )
        )
        
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        if doc["is_deleted"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Document already deleted"
            )
        
        # Perform deletion
        result = await delete_document(UUID(document_id))
        
        logger.info(f"Deleted document {document_id}: {result['chunks_deleted']} chunks")
        
        return {
            "message": "Document deleted successfully",
            **result
        }
        
    except HTTPException:
        raise
    except BaseAppException as e:
        logger.warning(f"Failed to delete document: {e.error_code}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error deleting document: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete document"
        )


@router.post("/projects/{project_id}/documents/{document_id}/retry")
async def retry_ingestion(
    project_id: str,
    document_id: str,
    user=Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Retry ingestion for a failed document.
    
    This re-enqueues the document for processing.
    Only works for documents with status='failed'.
    """
    try:
        # Verify project ownership
        project = await database.fetch_one(
            projects.select().where(
                (projects.c.id == project_id) &
                (projects.c.workspace_id == user["workspace_id"]) &
                (projects.c.is_deleted == False)
            )
        )
        
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        
        # Verify document
        doc = await database.fetch_one(
            documents.select().where(
                (documents.c.id == document_id) &
                (documents.c.project_id == project_id)
            )
        )
        
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        if doc["status"] != "failed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot retry document with status '{doc['status']}'. Only 'failed' documents can be retried."
            )
        
        # Reset status to pending
        await database.execute(
            documents.update()
            .where(documents.c.id == document_id)
            .values(status="pending")
        )
        
        # Enqueue new task
        task_id = await enqueue_task(
            database,
            task_type="ingest",
            document_id=UUID(document_id),
            metadata={"retry": True, "file_name": doc["file_name"]}
        )
        
        logger.info(f"Enqueued retry task {task_id} for document {document_id}")
        
        return {
            "message": "Document retry queued",
            "document_id": document_id,
            "task_id": str(task_id),
            "status": "pending"
        }
        
    except HTTPException:
        raise
    except BaseAppException as e:
        logger.warning(f"Failed to retry document: {e.error_code}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error retrying document: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retry document"
        )
