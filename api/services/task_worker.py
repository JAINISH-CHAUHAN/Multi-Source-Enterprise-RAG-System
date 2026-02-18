"""
Background task worker for processing ingestion and deletion tasks.

Polls the ingestion_tasks queue and executes tasks sequentially.
Uses PostgreSQL row-level locking to support multiple workers in the future.
"""
import asyncio
import os
from typing import Dict, Any
import logging

from api.core.database import database
from api.core.redis import redis_client
from api.models.document import documents
from api.models.ingestion_job import ingestion_jobs
from core.task_queue import get_next_task, mark_task_complete, mark_task_failed
from core.ingestion_pipeline import run_ingestion
from core.vector_store import VectorStoreManager
from core.file_router import FileRouter
from providers.pdf_ingestor import PDFIngestor
from providers.docx_ingestor import DocxIngestor
from providers.sheet_ingestor import SheetIngestor

logger = logging.getLogger(__name__)


async def process_ingestion_task(task: Dict[str, Any]) -> None:
    """
    Execute a single ingestion task.
    
    Args:
        task: Task record from ingestion_tasks table
    """
    task_id = task["id"]
    document_id = task["document_id"]
    job_id = task.get("job_id")
    
    logger.info(f"Processing ingestion task {task_id} for document {document_id}")
    
    # Fetch document record
    doc = await database.fetch_one(
        documents.select().where(documents.c.id == document_id)
    )
    
    if not doc:
        error_msg = f"Document {document_id} not found"
        logger.error(error_msg)
        await mark_task_failed(database, task_id, error_msg)
        return
    
    # Construct file path
    BASE_DIR = os.path.abspath("vector_stores")
    
    # Get workspace_id from project
    from api.models.project import projects
    project = await database.fetch_one(
        projects.select().where(projects.c.id == doc["project_id"])
    )
    
    if not project:
        error_msg = f"Project {doc['project_id']} not found"
        logger.error(error_msg)
        await mark_task_failed(database, task_id, error_msg)
        return
    
    workspace_id = project["workspace_id"]
    file_path = os.path.join(
        BASE_DIR,
        str(workspace_id),
        str(doc["project_id"]),
        "knowledge_base",
        doc["file_name"]
    )
    
    # Verify file exists
    if not os.path.exists(file_path):
        error_msg = f"File not found: {file_path}"
        logger.error(error_msg)
        await mark_task_failed(database, task_id, error_msg)
        return
    
    # Initialize vector store
    chroma_dir = os.path.join(
        BASE_DIR,
        str(workspace_id),
        str(doc["project_id"]),
        "chroma_db"
    )
    
    try:
        os.makedirs(chroma_dir, exist_ok=True)
    except Exception as e:
        error_msg = f"Failed to create chroma_db directory: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await mark_task_failed(database, task_id, error_msg)
        return
    
    vector_store = VectorStoreManager(persist_directory=chroma_dir)
    
    # Initialize file router
    file_router = FileRouter(
        ingestors=[PDFIngestor(), DocxIngestor(), SheetIngestor()]
    )
    
    # Run ingestion pipeline
    try:
        chunk_count = await run_ingestion(
            document=dict(doc),
            file_path=file_path,
            vector_store=vector_store,
            file_router=file_router,
            db=database,
        )
        
        logger.info(f"Ingestion task {task_id} completed: {chunk_count} chunks")
        
        # Mark task as complete
        await mark_task_complete(
            database,
            task_id,
            result_metadata={"chunk_count": chunk_count}
        )
        
        # Update Redis job status (non-critical)
        if job_id:
            try:
                await redis_client.hincrby(f"ingestion:{job_id}", "completed_files", 1)
            except Exception as e:
                logger.warning(f"Failed to update Redis job status: {str(e)}")
        
    except Exception as e:
        error_msg = f"Ingestion failed: {str(e)}"
        logger.error(f"Task {task_id} failed: {error_msg}", exc_info=True)
        await mark_task_failed(database, task_id, error_msg)
        
        # Update Redis job status (non-critical)
        if job_id:
            try:
                await redis_client.hincrby(f"ingestion:{job_id}", "failed_files", 1)
            except Exception as e:
                logger.warning(f"Failed to update Redis job status: {str(e)}")


async def process_deletion_task(task: Dict[str, Any]) -> None:
    """
    Execute a single deletion task.
    
    Args:
        task: Task record from ingestion_tasks table
    """
    task_id = task["id"]
    document_id = task["document_id"]
    
    logger.info(f"Processing deletion task {task_id} for document {document_id}")
    
    # Import deletion service (will be created in Phase 5)
    try:
        from api.services.document_service import delete_document
        
        result = await delete_document(document_id)
        
        logger.info(f"Deletion task {task_id} completed: {result}")
        
        await mark_task_complete(
            database,
            task_id,
            result_metadata=result
        )
        
    except ImportError:
        # Deletion service not yet implemented
        error_msg = "Deletion service not yet implemented"
        logger.warning(error_msg)
        await mark_task_failed(database, task_id, error_msg, max_retries=0)
        
    except Exception as e:
        error_msg = f"Deletion failed: {str(e)}"
        logger.error(f"Task {task_id} failed: {error_msg}", exc_info=True)
        await mark_task_failed(database, task_id, error_msg)


async def process_one_task() -> bool:
    """
    Process a single task from the queue.
    
    Returns:
        True if a task was processed, False if queue was empty
    """
    task = await get_next_task(database)
    
    if not task:
        return False
    
    task_type = task["task_type"]
    
    try:
        if task_type == "ingest":
            await process_ingestion_task(task)
        elif task_type == "delete":
            await process_deletion_task(task)
        else:
            logger.error(f"Unknown task type: {task_type}")
            await mark_task_failed(
                database,
                task["id"],
                f"Unknown task type: {task_type}",
                max_retries=0
            )
    except Exception as e:
        logger.error(f"Unexpected error processing task {task['id']}: {str(e)}", exc_info=True)
        await mark_task_failed(database, task["id"], str(e))
    
    return True


async def poll_queue(poll_interval: float = 2.0):
    """
    Continuously poll the task queue and process tasks.
    
    This runs as a background coroutine in the FastAPI app.
    
    Args:
        poll_interval: Seconds to wait between polls when queue is empty
    """
    logger.info("Task queue processor started")
    
    while True:
        try:
            # Process all available tasks
            while await process_one_task():
                # Continue processing without delay while queue has tasks
                pass
            
            # Queue is empty, wait before next poll
            await asyncio.sleep(poll_interval)
            
        except Exception as e:
            logger.error(f"Error in task queue polling loop: {str(e)}", exc_info=True)
            # Wait before retry to avoid tight error loop
            await asyncio.sleep(poll_interval)


async def update_job_statuses():
    """
    Periodically update job statuses based on their tasks.
    
    A job is complete when all its tasks are complete or failed.
    """
    try:
        # Find running jobs
        query = ingestion_jobs.select().where(ingestion_jobs.c.status == "running")
        running_jobs = await database.fetch_all(query)
        
        for job in running_jobs:
            job_id = job["id"]
            
            # Get tasks for this job
            from core.task_queue import get_tasks_for_job
            tasks = await get_tasks_for_job(database, job_id)
            
            if not tasks:
                # No tasks, mark job as completed
                await database.execute(
                    ingestion_jobs.update()
                    .where(ingestion_jobs.c.id == job_id)
                    .values(status="completed")
                )
                continue
            
            # Check if all tasks are done
            statuses = [t["status"] for t in tasks]
            
            if all(s in ("completed", "failed") for s in statuses):
                # All tasks done
                if any(s == "failed" for s in statuses):
                    # At least one failure
                    await database.execute(
                        ingestion_jobs.update()
                        .where(ingestion_jobs.c.id == job_id)
                        .values(
                            status="completed",
                            error_message="Some files failed to ingest"
                        )
                    )
                    
                    # Update Redis
                    try:
                        await redis_client.hset(f"ingestion:{job_id}", "status", "completed_with_errors")
                    except Exception:
                        pass
                else:
                    # All succeeded
                    await database.execute(
                        ingestion_jobs.update()
                        .where(ingestion_jobs.c.id == job_id)
                        .values(status="completed")
                    )
                    
                    # Update Redis
                    try:
                        await redis_client.hset(f"ingestion:{job_id}", "status", "completed")
                    except Exception:
                        pass
                
                logger.info(f"Job {job_id} marked as completed")
    
    except Exception as e:
        logger.error(f"Error updating job statuses: {str(e)}", exc_info=True)
