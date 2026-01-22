from fastapi import APIRouter, Depends, BackgroundTasks
from api.core.dependencies import get_current_user
from api.services.ingestion_job_service import start_ingestion_job

router = APIRouter()

@router.post("/projects/{project_id}/ingest")
async def ingest_project(
    project_id: str,
    background_tasks: BackgroundTasks,
    user=Depends(get_current_user),
):
    folder_path = f"vector_stores/{user['workspace_id']}/{project_id}/knowledge_base"

    job_id = await start_ingestion_job(
        project_id=project_id,
        workspace_id=user["workspace_id"],
        folder_path=folder_path,
        background_tasks=background_tasks,
    )

    return {"job_id": str(job_id)}
