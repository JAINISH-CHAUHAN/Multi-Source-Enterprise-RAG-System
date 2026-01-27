# /api/services/citation_service.py

import os
from fastapi import HTTPException, status
from api.models.project import projects
from api.core.database import database
from core.vector_store import VectorStoreManager


def extract_highlight(content: str) -> dict:
    """
    Deterministically extract the most meaningful sentence
    from the chunk (longest non-empty sentence).
    """

    sentences = [s.strip() for s in content.split("\n") if s.strip()]

    if not sentences:
        return {}

    best_sentence = max(sentences, key=len)

    start = content.find(best_sentence)
    end = start + len(best_sentence)

    return {
        "highlight_text": best_sentence,
        "highlight_start": start,
        "highlight_end": end,
    }


async def resolve_citation(
    workspace_id: str,
    project_id: str,
    source_file: str,
    chunk_index: int,
):
    # 1️⃣ Validate project ownership
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

    # 2️⃣ Resolve Chroma path
    chroma_path = os.path.join(
        project["vector_store_path"],
        "chroma_db"
    )

    if not os.path.exists(chroma_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base not found"
        )

    # 3️⃣ Load vector store (read-only)
    vector_store = VectorStoreManager(persist_directory=chroma_path)
    db = vector_store.load_or_create()

    # 4️⃣ Query by metadata (exact match)
    results = db.get(
        where={
            "$and": [
                {"source_file": source_file},
                {"chunk_index": chunk_index},
            ]
        }
    )

    if not results or not results.get("documents"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Citation not found"
        )

    # 5️⃣ Extract content safely
    content = results["documents"][0]

    # 6️⃣ Deterministic highlight
    highlight = extract_highlight(content)

    return {
        "source_file": source_file,
        "chunk_index": chunk_index,
        "content": content,
        **highlight,
        "reason": "This excerpt directly supports the answer to the user's question."
    }
