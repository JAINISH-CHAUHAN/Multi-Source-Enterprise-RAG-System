import os
import shutil
import uuid
import traceback
from fastapi import BackgroundTasks, UploadFile, HTTPException, status
from api.core.database import database
from api.core.redis import redis_client
from api.models.ingestion_job import ingestion_jobs
from api.models.project import projects
from api.core.logging import get_logger
from api.core.exceptions import (
    VectorStoreException, 
    FileProcessingException, 
    IngestionException,
    DatabaseException
)

from core.vector_store import VectorStoreManager
from core.file_router import FileRouter
from providers.pdf_ingestor import PDFIngestor
from providers.docx_ingestor import DocxIngestor
from providers.sheet_ingestor import SheetIngestor

from rag.ingestion.folder import ingest_folder

logger = get_logger(__name__)


async def start_ingestion_job_with_files(
    project_id: str,
    workspace_id: str,
    files: list[UploadFile],
    background_tasks: BackgroundTasks,
):
    """
    ✅ SYNCHRONOUSLY saves uploaded files during request lifecycle,
    then starts background ingestion job.
    """
    
    logger.info(f"Starting ingestion job for project {project_id} with {len(files)} files")
    
    # 1️⃣ Validate project ownership
    try:
        project = await database.fetch_one(
            projects.select().where(
                (projects.c.id == project_id) &
                (projects.c.workspace_id == workspace_id) &
                (projects.c.is_deleted == False)
            )
        )
    except Exception as e:
        logger.error(f"Database query failed for project validation: {str(e)}", exc_info=True)
        raise DatabaseException(
            user_message="Failed to validate project. Please try again.",
            details={"project_id": project_id, "error": str(e)},
            error_code="DATABASE_QUERY_ERROR"
        )
    
    if not project:
        logger.warning(f"Project not found: {project_id} for workspace {workspace_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # 2️⃣ Construct filesystem paths
    BASE_DIR = os.path.abspath("vector_stores")
    
    kb_folder = os.path.join(
        BASE_DIR,
        str(workspace_id),
        str(project_id),
        "knowledge_base"
    )
    
    # 3️⃣ Create directory structure
    try:
        os.makedirs(kb_folder, exist_ok=True)
        logger.debug(f"Created directory: {kb_folder}")
    except Exception as e:
        logger.error(f"Failed to create directory {kb_folder}: {str(e)}", exc_info=True)
        raise FileProcessingException(
            user_message="Failed to create storage directory. Please contact support.",
            details={"kb_folder": kb_folder, "error": str(e)},
            error_code="FILE_DIRECTORY_CREATION_ERROR"
        )
    
    # 4️⃣ CRITICAL: Save uploaded files SYNCHRONOUSLY (while UploadFile streams are valid)
    saved_files = []
    try:
        for file in files:
            file_path = os.path.join(kb_folder, file.filename)
            with open(file_path, "wb") as f:
                shutil.copyfileobj(file.file, f)
            saved_files.append(file.filename)
            logger.debug(f"Saved file: {file.filename}")
        
        logger.info(f"Successfully saved {len(saved_files)} files to disk")
    except Exception as e:
        logger.error(f"Failed to save uploaded files: {str(e)}", exc_info=True)
        raise FileProcessingException(
            user_message="Failed to save uploaded files. Please try again.",
            details={
                "kb_folder": kb_folder,
                "saved_files": saved_files,
                "error": str(e)
            },
            error_code="FILE_UPLOAD_SAVE_ERROR"
        )
    
    # 5️⃣ Create job record
    job_id = uuid.uuid4()
    
    try:
        await database.execute(
            ingestion_jobs.insert().values(
                id=job_id,
                project_id=project_id,
                status="pending",
            )
        )
        logger.info(f"Created ingestion job record: {job_id}")
    except Exception as e:
        logger.error(f"Failed to create job record: {str(e)}", exc_info=True)
        raise DatabaseException(
            user_message="Failed to create ingestion job. Please try again.",
            details={"job_id": str(job_id), "error": str(e)},
            error_code="DATABASE_INSERT_ERROR"
        )
    
    # 6️⃣ Redis state (runtime) - non-critical, log but don't fail
    try:
        await redis_client.hset(
            f"ingestion:{job_id}",
            mapping={"status": "pending"}
        )
        logger.debug(f"Set Redis state for job: {job_id}")
    except Exception as e:
        logger.warning(f"Failed to set Redis state for job {job_id}: {str(e)}")
        # Continue - Redis failure shouldn't block job creation
    
    # 7️⃣ Background task receives ONLY filesystem paths
    background_tasks.add_task(
        run_ingestion_job,
        job_id,
        project_id,
        kb_folder,  # ← Files already on disk
    )
    
    logger.info(f"Ingestion job {job_id} queued for background processing")
    
    return job_id


async def run_ingestion_job(job_id, project_id, folder_path):
    """
    Background task that operates ONLY on filesystem paths.
    No UploadFile objects, no request context.
    """
    logger.info(f"Starting background ingestion job: {job_id}")
    
    try:
        # Update job status to running
        try:
            await redis_client.hset(f"ingestion:{job_id}", "status", "running")
        except Exception as e:
            logger.warning(f"Failed to update Redis status to running: {str(e)}")

        # ✅ Ensure paths are absolute
        folder_path = os.path.abspath(folder_path)
        
        # ✅ Verify folder exists
        if not os.path.exists(folder_path):
            raise FileProcessingException(
                user_message="Knowledge base folder not found",
                details={"folder_path": folder_path},
                error_code="KNOWLEDGE_BASE_FOLDER_NOT_FOUND"
            )
        
        # ✅ Create chroma_db directory
        chroma_dir = os.path.join(os.path.dirname(folder_path), "chroma_db")
        try:
            os.makedirs(chroma_dir, exist_ok=True)
            logger.debug(f"Created/verified chroma_db directory: {chroma_dir}")
        except Exception as e:
            raise FileProcessingException(
                user_message="Failed to create vector database directory",
                details={"chroma_dir": chroma_dir, "error": str(e)},
                error_code="CHROMA_DIRECTORY_ERROR"
            )

        # ✅ Initialize vector store
        vector_store = VectorStoreManager(
            persist_directory=chroma_dir
        )

        # ✅ Initialize file router
        file_router = FileRouter(
            ingestors=[PDFIngestor(), DocxIngestor(), SheetIngestor()]
        )

        # ✅ Process files that are ALREADY on disk
        ingestion_summary = ingest_folder(folder_path, vector_store, file_router)
        
        logger.info(
            f"Ingestion completed for job {job_id}: "
            f"{ingestion_summary['processed']}/{ingestion_summary['total_files']} files succeeded"
        )

        # Update job status to completed
        try:
            await redis_client.hset(f"ingestion:{job_id}", "status", "completed")
        except Exception as e:
            logger.warning(f"Failed to update Redis status to completed: {str(e)}")

        await database.execute(
            ingestion_jobs.update()
            .where(ingestion_jobs.c.id == job_id)
            .values(
                status="completed",
                error_message=None  # Clear any previous errors
            )
        )
        
        logger.info(f"Ingestion job {job_id} completed successfully")

    except (VectorStoreException, FileProcessingException, IngestionException) as e:
        # Domain-specific exceptions with structured error information
        error_details = {
            "job_id": str(job_id),
            "error_code": e.error_code,
            "error_message": e.user_message,
            "error_type": type(e).__name__,
            "details": e.details,
            "traceback": traceback.format_exc()
        }
        
        logger.error(
            f"Ingestion job {job_id} failed with {e.error_code}",
            extra=error_details,
            exc_info=True
        )
        
        # Update Redis status
        try:
            await redis_client.hset(
                f"ingestion:{job_id}",
                mapping={
                    "status": "failed",
                    "error": e.user_message,
                    "error_code": e.error_code
                }
            )
        except Exception as redis_error:
            logger.warning(f"Failed to update Redis error status: {str(redis_error)}")

        # Update database
        await database.execute(
            ingestion_jobs.update()
            .where(ingestion_jobs.c.id == job_id)
            .values(
                status="failed",
                error_message=f"[{e.error_code}] {e.user_message}"
            )
        )
        
    except Exception as e:
        # Unexpected exceptions
        error_details = {
            "job_id": str(job_id),
            "error_message": str(e),
            "error_type": type(e).__name__,
            "traceback": traceback.format_exc()
        }
        
        logger.critical(
            f"Unexpected error in ingestion job {job_id}",
            extra=error_details,
            exc_info=True
        )
        
        # Update Redis status
        try:
            await redis_client.hset(
                f"ingestion:{job_id}",
                mapping={
                    "status": "failed",
                    "error": f"Unexpected error: {str(e)}",
                    "error_code": "INGESTION_UNEXPECTED_ERROR"
                }
            )
        except Exception as redis_error:
            logger.warning(f"Failed to update Redis error status: {str(redis_error)}")

        # Update database
        await database.execute(
            ingestion_jobs.update()
            .where(ingestion_jobs.c.id == job_id)
            .values(
                status="failed",
                error_message=f"[INGESTION_UNEXPECTED_ERROR] {str(e)}"
            )
        )