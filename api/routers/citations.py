# /api/routers/citations.py

from fastapi import APIRouter, Depends
from api.core.dependencies import get_current_user
from api.services.citation_service import resolve_citation

router = APIRouter()


@router.get(
    "/projects/{project_id}/citations/{source_file}/{chunk_index}"
)
async def get_citation(
    project_id: str,
    source_file: str,
    chunk_index: int,
    current_user=Depends(get_current_user),
):
    return await resolve_citation(
        workspace_id=current_user["workspace_id"],
        project_id=project_id,
        source_file=source_file,
        chunk_index=chunk_index,
    )
