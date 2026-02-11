from fastapi import APIRouter, Depends
from api.schemas.query import QueryRequest, QueryResponse
from api.services.query_service import query_project_knowledge_base
from api.core.dependencies import get_current_user
from api.core.logging import get_logger
from api.core.exceptions import (
    BaseAppException,
    VectorStoreException,
    LLMException,
    FileProcessingException
)

router = APIRouter()
logger = get_logger(__name__)


@router.post(
    "/projects/{project_id}/query",
    response_model=QueryResponse
)
async def query_project(
    project_id: str,
    payload: QueryRequest,
    current_user=Depends(get_current_user),
):
    """
    Query the project knowledge base.
    
    Returns QueryResponse with either:
    - Success: answer and sources populated
    - Failure: error_code and error_message populated
    """
    try:
        return await query_project_knowledge_base(
            workspace_id=current_user["workspace_id"],
            project_id=project_id,
            query=payload.query,
            top_k=payload.top_k,
            conversation_id=payload.conversation_id,
        )
    except BaseAppException as e:
        # Domain exceptions - return structured error in QueryResponse
        logger.warning(
            f"Query failed with domain exception: {e.error_code}",
            extra={"project_id": project_id, "error_code": e.error_code}
        )
        return QueryResponse(
            status="error",
            query=payload.query,
            answer="",
            sources=[],
            error_code=e.error_code,
            error_message=e.user_message
        )
    except Exception as e:
        # Unexpected exceptions - return generic error
        logger.error(f"Unexpected error in query endpoint: {str(e)}", exc_info=True)
        return QueryResponse(
            status="error",
            query=payload.query,
            answer="",
            sources=[],
            error_code="QUERY_UNEXPECTED_ERROR",
            error_message="An unexpected error occurred while processing your query."
        )
