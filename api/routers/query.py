from fastapi import APIRouter, Depends
from api.schemas.query import QueryRequest, QueryResponse
from api.services.query_service import query_project_knowledge_base
from api.core.dependencies import get_current_user

router = APIRouter()


@router.post(
    "/projects/{project_id}/query",
    response_model=QueryResponse
)
async def query_project(
    project_id: str,
    payload: QueryRequest,
    current_user=Depends(get_current_user),
):
    return await query_project_knowledge_base(
        workspace_id=current_user["workspace_id"],
        project_id=project_id,
        query=payload.query,
        top_k=payload.top_k,
    )
