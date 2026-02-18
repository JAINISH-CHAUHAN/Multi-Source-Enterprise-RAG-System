from fastapi import APIRouter, Depends, BackgroundTasks, UploadFile, File
from api.core.dependencies import get_current_user
from api.core.logging import get_logger
from api.core.exceptions import BaseAppException
from api.services.ingestion_job_service import (
    start_ingestion_job_with_files,
    create_and_run_ingestion_job_v2
)

router = APIRouter()
logger = get_logger(__name__)

@router.post("/projects/{project_id}/ingest")
async def ingest_project(
    project_id: str,
    files: list[UploadFile] = File(...),
    background_tasks: BackgroundTasks = None,
    user=Depends(get_current_user),
):
    """
    Upload files for ingestion with content-addressed deduplication.
    
    NEW (V2): This endpoint now:
    - Computes file hashes for deduplication
    - Skips files already ingested (same content)
    - Detects and replaces updated files (same name, different content)
    - Creates document records before ingestion
    - Uses persistent task queue for background processing
    
    Returns job_id and upload summary.
    """
    try:
        # Use V2 service with content-addressed deduplication
        result = await create_and_run_ingestion_job_v2(
            project_id=project_id,
            workspace_id=user["workspace_id"],
            files=files,
            background_tasks=background_tasks,
        )

        return result
    
    except BaseAppException as e:
        # Domain exceptions - already logged by service layer
        logger.warning(
            f"Ingestion job creation failed: {e.error_code}",
            extra={"project_id": project_id, "error_code": e.error_code}
        )
        # Re-raise to be handled by global exception handler
        raise
    except Exception as e:
        # Unexpected exceptions
        logger.error(f"Unexpected error in ingestion endpoint: {str(e)}", exc_info=True)
        raise


@router.post("/projects/{project_id}/ingest/legacy")
async def ingest_project_legacy(
    project_id: str,
    files: list[UploadFile] = File(...),
    background_tasks: BackgroundTasks = None,
    user=Depends(get_current_user),
):
    """
    Legacy upload endpoint (V1) - for backward compatibility.
    
    This uses the old direct ingestion without deduplication.
    Will be deprecated in future versions.
    """
    try:
        job_id = await start_ingestion_job_with_files(
            project_id=project_id,
            workspace_id=user["workspace_id"],
            files=files,
            background_tasks=background_tasks,
        )

        return {"job_id": str(job_id)}
    
    except BaseAppException as e:
        logger.warning(
            f"Ingestion job creation failed: {e.error_code}",
            extra={"project_id": project_id, "error_code": e.error_code}
        )
        raise
    except Exception as e:
        logger.error(f"Unexpected error in ingestion endpoint: {str(e)}", exc_info=True)
        raise
