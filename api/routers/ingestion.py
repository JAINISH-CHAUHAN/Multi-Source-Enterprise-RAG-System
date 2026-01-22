from fastapi import APIRouter, Depends, BackgroundTasks, UploadFile, File
from api.core.dependencies import get_current_user
from api.services.ingestion_job_service import start_ingestion_job_with_files

router = APIRouter()

@router.post("/projects/{project_id}/ingest")
async def ingest_project(
    project_id: str,
    files: list[UploadFile] = File(...),
    background_tasks: BackgroundTasks = None,
    user=Depends(get_current_user),
):
    # ✅ Router only validates & delegates to service
    job_id = await start_ingestion_job_with_files(
        project_id=project_id,
        workspace_id=user["workspace_id"],
        files=files,
        background_tasks=background_tasks,
    )

    return {"job_id": str(job_id)}