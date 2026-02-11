# /api/routers/citations.py

from fastapi import APIRouter, Depends
from api.core.dependencies import get_current_user
from api.core.logging import get_logger
from api.core.exceptions import BaseAppException
from api.services.citation_service import resolve_citation
from api.schemas.query import CitationDetail

router = APIRouter()
logger = get_logger(__name__)


@router.get(
    "/projects/{project_id}/citations/{source_file}/{chunk_index}",
    response_model=CitationDetail
)
async def get_citation(
    project_id: str,
    source_file: str,
    chunk_index: int,
    current_user=Depends(get_current_user),
):
    """
    Resolve a specific citation to its full content.
    
    Returns citation details or raises HTTPException on failure.
    """
    try:
        return await resolve_citation(
            workspace_id=current_user["workspace_id"],
            project_id=project_id,
            source_file=source_file,
            chunk_index=chunk_index,
        )
    except BaseAppException as e:
        # Domain exceptions - already logged by service layer
        logger.warning(
            f"Citation resolution failed: {e.error_code}",
            extra={
                "project_id": project_id,
                "source_file": source_file,
                "chunk_index": chunk_index,
                "error_code": e.error_code
            }
        )
        # Re-raise to be handled by global exception handler
        raise
    except Exception as e:
        # Unexpected exceptions
        logger.error(f"Unexpected error in citations endpoint: {str(e)}", exc_info=True)
        raise
