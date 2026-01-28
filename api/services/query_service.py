import os
from rag.retrieval.answer import answer_query
from api.models.project import projects
from api.core.database import database
from fastapi import HTTPException, status
from api.services.conversation_service import (
    append_turn,
    get_conversation_summary,
    update_conversation_summary,
    get_recent_turns,
)


async def query_project_knowledge_base(
    workspace_id: str,
    project_id: str,
    query: str,
    top_k: int,
    conversation_id: str | None = None
):
    project = await database.fetch_one(
        projects.select().where(
            (projects.c.id == project_id) &
            (projects.c.workspace_id == workspace_id) &
            (projects.c.is_deleted == False)
        )
    )

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    chroma_path = os.path.join(project["vector_store_path"], "chroma_db")

    if not os.path.exists(chroma_path):
        raise HTTPException(
            status_code=400,
            detail="Knowledge base not ingested yet"
        )

    conversation_context = ""
    if conversation_id:
        summary = await get_conversation_summary(conversation_id)
        if summary:
            conversation_context = summary

    result = answer_query(
        query=query,
        persist_directory=chroma_path,
        k=top_k,
        conversation_context=conversation_context,
    )

    if conversation_id:
        await append_turn(conversation_id, "user", query)
        await append_turn(conversation_id, "assistant", result["answer"])

        turns = await get_recent_turns(conversation_id)
        await update_conversation_summary(conversation_id, turns)

    return {
        "status": "success",
        "query": query,
        "answer": result["answer"],
        "sources": result["sources"],
        "confidence": "high"
    }
