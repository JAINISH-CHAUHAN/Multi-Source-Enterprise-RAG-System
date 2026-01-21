from fastapi import APIRouter, Depends
from api.schemas.project import ProjectCreateRequest, ProjectResponse
from api.services.project_service import (
    create_project,
    list_projects,
    delete_project,
)
from api.core.dependencies import get_current_user

router = APIRouter()

@router.post("/", response_model=ProjectResponse)
async def create_project_route(
    payload: ProjectCreateRequest,
    user=Depends(get_current_user),
):
    return await create_project(
        workspace_id=user["workspace_id"],
        name=payload.name,
    )


@router.get("/", response_model=list[ProjectResponse])
async def list_projects_route(
    user=Depends(get_current_user),
):
    return await list_projects(
        workspace_id=user["workspace_id"]
    )


@router.delete("/{project_id}")
async def delete_project_route(
    project_id: str,
    user=Depends(get_current_user),
):
    return await delete_project(
        workspace_id=user["workspace_id"],
        project_id=project_id
    )
