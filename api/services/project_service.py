import os
import uuid
import shutil
from datetime import datetime
from fastapi import HTTPException, status

from api.core.database import database
from api.models.project import projects

VECTOR_BASE_DIR = "vector_stores"


async def create_project(workspace_id: str, name: str):
    existing = await database.fetch_one(
        projects.select().where(
            (projects.c.workspace_id == workspace_id) &
            (projects.c.name == name) &
            (projects.c.is_deleted == False)
        )
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Project with this name already exists in your workspace"
        )

    project_id = uuid.uuid4()

    vector_store_path = os.path.join(
        VECTOR_BASE_DIR,
        workspace_id,
        str(project_id)
    )

    os.makedirs(vector_store_path, exist_ok=True)

    await database.execute(
        projects.insert().values(
            id=project_id,
            workspace_id=workspace_id,
            name=name,
            vector_store_path=vector_store_path,
            is_deleted=False
        )
    )

    return {"id": project_id, "name": name}


async def list_projects(workspace_id: str):
    rows = await database.fetch_all(
        projects.select().where(
            (projects.c.workspace_id == workspace_id) &
            (projects.c.is_deleted == False)
        )
    )

    return [{"id": r["id"], "name": r["name"]} for r in rows]


async def delete_project(workspace_id: str, project_id: str):
    project = await database.fetch_one(
        projects.select().where(
            (projects.c.id == project_id) &
            (projects.c.workspace_id == workspace_id)
        )
    )

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    if project["is_deleted"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Project already deleted"
        )

    # 1️⃣ Soft delete in DB
    await database.execute(
        projects.update()
        .where(projects.c.id == project_id)
        .values(
            is_deleted=True,
            deleted_at=datetime.utcnow()
        )
    )

    # 2️⃣ Vector store cleanup (safe)
    vector_path = project["vector_store_path"]
    if vector_path and os.path.exists(vector_path):
        shutil.rmtree(vector_path)

    return {"message": "Project deleted successfully"}
