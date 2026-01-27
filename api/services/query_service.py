# /api/services/query_service.py

import os
from rag.retrieval.answer import answer_query
from api.models.project import projects
from api.core.database import database
from fastapi import HTTPException, status
from api.services.conversation_service import (
    append_turn,
    get_recent_turns
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    chroma_path = os.path.join(
        project["vector_store_path"],
        "chroma_db"
    )

    if not os.path.exists(chroma_path):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Knowledge base not ingested yet"
        )


    conversation_context = ""

    if conversation_id:
        turns = await get_recent_turns(conversation_id)
        conversation_context = "\n".join(
            f"{t['role'].upper()}: {t['content']}"
            for t in turns
        )


    result = answer_query(
        query=query,
        persist_directory=chroma_path,
        k=top_k,
        conversation_context=conversation_context,
    )

    if conversation_id:
        await append_turn(conversation_id, "user", query)
        await append_turn(conversation_id, "assistant", result["answer"])


    return {
        "status": "success",
        "query": query,
        "answer": result["answer"],
        "sources": result["sources"],
        "confidence": "high"
    }
