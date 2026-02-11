from fastapi import APIRouter, Depends, BackgroundTasks, UploadFile, File
from api.core.dependencies import get_current_user
from api.core.logging import get_logger
from api.core.exceptions import BaseAppException
from api.services.ingestion_job_service import start_ingestion_job_with_files

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
    Upload files for ingestion.
    
    Files are saved synchronously, then processed in background.
    Returns job_id for status tracking.
    """
    try:
        # ✅ Router only validates & delegates to service
        job_id = await start_ingestion_job_with_files(
            project_id=project_id,
            workspace_id=user["workspace_id"],
            files=files,
            background_tasks=background_tasks,
        )

        return {"job_id": str(job_id)}
    
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