"""
PostgreSQL-based persistent task queue for ingestion and deletion jobs.

Uses row-level locking (FOR UPDATE SKIP LOCKED) to enable concurrent workers
without duplicate processing. More robust than BackgroundTasks for crash recovery.
"""
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from uuid import UUID
import logging

from databases import Database
from api.models.ingestion_task import ingestion_tasks

logger = logging.getLogger(__name__)


async def enqueue_task(
    db: Database,
    task_type: str,
    document_id: UUID,
    job_id: Optional[UUID] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> UUID:
    """
    Create a new task in the queue.
    
    Args:
        db: Database connection
        task_type: Either 'ingest' or 'delete'
        document_id: ID of the document to process
        job_id: Optional link to ingestion_job for tracking
        metadata: Optional additional task-specific data
        
    Returns:
        UUID of the created task
    """
    import uuid as uuid_module
    
    task_id = uuid_module.uuid4()
    
    query = ingestion_tasks.insert().values(
        id=task_id,
        task_type=task_type,
        document_id=document_id,
        job_id=job_id,
        status="pending",
        retry_count=0,
        metadata=metadata,
        created_at=datetime.now(timezone.utc),
    )
    
    await db.execute(query)
    logger.info(f"Enqueued {task_type} task {task_id} for document {document_id}")
    
    return task_id


async def get_next_task(db: Database) -> Optional[Dict[str, Any]]:
    """
    Fetch the oldest pending task and mark it as processing.
    
    Uses PostgreSQL's FOR UPDATE SKIP LOCKED to prevent race conditions
    when multiple workers poll the queue simultaneously.
    
    Args:
        db: Database connection
        
    Returns:
        Task record dict or None if queue is empty
    """
    from datetime import datetime, timezone
    
    # Use raw SQL for FOR UPDATE SKIP LOCKED (not available in SQLAlchemy Core select)
    query = """
        UPDATE ingestion_tasks
        SET status = 'processing',
            started_at = :now,
            updated_at = :now
        WHERE id = (
            SELECT id FROM ingestion_tasks
            WHERE status = 'pending'
            ORDER BY created_at ASC
            LIMIT 1
            FOR UPDATE SKIP LOCKED
        )
        RETURNING *;
    """
    
    now = datetime.now(timezone.utc)
    task = await db.fetch_one(query, {"now": now})
    
    if task:
        logger.info(f"Fetched task {task['id']} ({task['task_type']}) for processing")
    
    return dict(task) if task else None


async def mark_task_complete(
    db: Database,
    task_id: UUID,
    result_metadata: Optional[Dict[str, Any]] = None
) -> None:
    """
    Mark a task as successfully completed.
    
    Args:
        db: Database connection
        task_id: ID of the task
        result_metadata: Optional result data to merge into task metadata
    """
    update_values = {
        "status": "completed",
        "completed_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    
    if result_metadata:
        # Merge result into existing metadata
        query = ingestion_tasks.select().where(ingestion_tasks.c.id == task_id)
        task = await db.fetch_one(query)
        if task and task["metadata"]:
            merged = {**task["metadata"], **result_metadata}
            update_values["metadata"] = merged
        else:
            update_values["metadata"] = result_metadata
    
    query = (
        ingestion_tasks.update()
        .where(ingestion_tasks.c.id == task_id)
        .values(**update_values)
    )
    
    await db.execute(query)
    logger.info(f"Task {task_id} marked as completed")


async def mark_task_failed(
    db: Database,
    task_id: UUID,
    error_message: str,
    max_retries: int = 3
) -> bool:
    """
    Mark a task as failed and optionally retry.
    
    Args:
        db: Database connection
        task_id: ID of the task
        error_message: Error description
        max_retries: Maximum retry attempts before permanent failure
        
    Returns:
        True if task will be retried, False if permanently failed
    """
    # Fetch current retry count
    query = ingestion_tasks.select().where(ingestion_tasks.c.id == task_id)
    task = await db.fetch_one(query)
    
    if not task:
        logger.error(f"Task {task_id} not found")
        return False
    
    retry_count = task["retry_count"] + 1
    will_retry = retry_count < max_retries
    
    update_values = {
        "retry_count": retry_count,
        "error_message": error_message,
        "updated_at": datetime.now(timezone.utc),
    }
    
    if will_retry:
        # Reset to pending for retry
        update_values["status"] = "pending"
        update_values["started_at"] = None
        logger.warning(f"Task {task_id} failed (attempt {retry_count}/{max_retries}), will retry: {error_message}")
    else:
        # Permanent failure
        update_values["status"] = "failed"
        update_values["completed_at"] = datetime.now(timezone.utc)
        logger.error(f"Task {task_id} permanently failed after {retry_count} attempts: {error_message}")
    
    query = (
        ingestion_tasks.update()
        .where(ingestion_tasks.c.id == task_id)
        .values(**update_values)
    )
    
    await db.execute(query)
    
    return will_retry


async def get_tasks_for_job(db: Database, job_id: UUID) -> list[Dict[str, Any]]:
    """
    Get all tasks associated with an ingestion job.
    
    Args:
        db: Database connection
        job_id: ID of the ingestion job
        
    Returns:
        List of task records
    """
    query = (
        ingestion_tasks.select()
        .where(ingestion_tasks.c.job_id == job_id)
        .order_by(ingestion_tasks.c.created_at)
    )
    
    tasks = await db.fetch_all(query)
    return [dict(task) for task in tasks]
