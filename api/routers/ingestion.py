from fastapi import APIRouter, Depends, UploadFile, File
from api.core.dependencies import get_current_user
from api.services.ingestion_service import ingest_files_for_project

router = APIRouter()

@router.post("/projects/{project_id}/ingest")
async def ingest_project_files(
    project_id: str,
    files: list[UploadFile] = File(...),
    user=Depends(get_current_user),
):
    return await ingest_files_for_project(
        workspace_id=user["workspace_id"],
        project_id=project_id,
        files=files,
    )
