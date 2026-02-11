import os
from rag.retrieval.answer import answer_query
from api.models.project import projects
from api.core.database import database
from api.core.logging import get_logger
from api.core.exceptions import DatabaseException, FileProcessingException
from fastapi import HTTPException, status
from api.services.conversation_service import (
    append_turn,
    get_conversation_summary,
    update_conversation_summary,
    get_recent_turns,
)

logger = get_logger(__name__)


async def query_project_knowledge_base(
    workspace_id: str,
    project_id: str,
    query: str,
    top_k: int,
    conversation_id: str | None = None
):
    logger.info(f"Processing query for project {project_id}")
    
    # Validate project ownership
    try:
        project = await database.fetch_one(
            projects.select().where(
                (projects.c.id == project_id) &
                (projects.c.workspace_id == workspace_id) &
                (projects.c.is_deleted == False)
            )
        )
    except Exception as e:
        logger.error(f"Database query failed: {str(e)}", exc_info=True)
        raise DatabaseException(
            user_message="Failed to access project information.",
            details={"project_id": project_id, "error": str(e)},
            error_code="DATABASE_QUERY_ERROR"
        )

    if not project:
        logger.warning(f"Project not found: {project_id}")
        raise HTTPException(status_code=404, detail="Project not found")

    chroma_path = os.path.join(project["vector_store_path"], "chroma_db")

    if not os.path.exists(chroma_path):
        logger.warning(f"Knowledge base not found: {chroma_path}")
        raise HTTPException(
            status_code=400,
            detail="Knowledge base not ingested yet"
        )

    # Get conversation context if available
    conversation_context = ""
    if conversation_id:
        try:
            summary = await get_conversation_summary(conversation_id)
            if summary:
                conversation_context = summary
        except Exception as e:
            logger.warning(f"Failed to get conversation summary: {str(e)}")
            # Continue without conversation context

    # Perform the query (domain exceptions will propagate)
    result = answer_query(
        query=query,
        persist_directory=chroma_path,
        k=top_k,
        conversation_context=conversation_context,
    )

    # Update conversation history if applicable
    if conversation_id:
        try:
            await append_turn(conversation_id, "user", query)
            await append_turn(conversation_id, "assistant", result["answer"])

            turns = await get_recent_turns(conversation_id)
            await update_conversation_summary(conversation_id, turns)
        except Exception as e:
            logger.error(f"Failed to update conversation: {str(e)}", exc_info=True)
            # Don't fail the query if conversation update fails

    logger.info(f"Query processed successfully for project {project_id}")
    
    return {
        "status": "success",
        "query": query,
        "answer": result["answer"],
        "sources": result["sources"],
        "confidence": "high"
    }
