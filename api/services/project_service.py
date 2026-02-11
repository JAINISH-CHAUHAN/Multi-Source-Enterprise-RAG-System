import os
import uuid
import shutil
from datetime import datetime
from fastapi import HTTPException, status

from api.core.database import database
from api.models.project import projects
from api.core.logging import get_logger
from api.core.exceptions import FileProcessingException, DatabaseException

logger = get_logger(__name__)

VECTOR_BASE_DIR = "vector_stores"


async def create_project(workspace_id: str, name: str):
    logger.info(f"Creating project '{name}' for workspace {workspace_id}")
    
    try:
        existing = await database.fetch_one(
            projects.select().where(
                (projects.c.workspace_id == workspace_id) &
                (projects.c.name == name) &
                (projects.c.is_deleted == False)
            )
        )
    except Exception as e:
        logger.error(f"Database query failed: {str(e)}", exc_info=True)
        raise DatabaseException(
            user_message="Failed to check existing projects.",
            details={"workspace_id": workspace_id, "name": name, "error": str(e)},
            error_code="DATABASE_QUERY_ERROR"
        )

    if existing:
        logger.warning(f"Project with name '{name}' already exists")
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

    try:
        os.makedirs(vector_store_path, exist_ok=True)
        logger.debug(f"Created vector store directory: {vector_store_path}")
    except Exception as e:
        logger.error(f"Failed to create directory: {vector_store_path}", exc_info=True)
        raise FileProcessingException(
            user_message="Failed to create project directory.",
            details={"vector_store_path": vector_store_path, "error": str(e)},
            error_code="FILE_DIRECTORY_CREATION_ERROR"
        )

    try:
        await database.execute(
            projects.insert().values(
                id=project_id,
                workspace_id=workspace_id,
                name=name,
                vector_store_path=vector_store_path,
                is_deleted=False
            )
        )
        logger.info(f"Project created successfully: {project_id}")
    except Exception as e:
        logger.error(f"Failed to insert project record: {str(e)}", exc_info=True)
        # Clean up directory if DB insert fails
        try:
            if os.path.exists(vector_store_path):
                shutil.rmtree(vector_store_path)
        except Exception as cleanup_error:
            logger.warning(f"Failed to cleanup directory after DB error: {cleanup_error}")
        
        raise DatabaseException(
            user_message="Failed to create project record.",
            details={"project_id": str(project_id), "error": str(e)},
            error_code="DATABASE_INSERT_ERROR"
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
    logger.info(f"Deleting project {project_id}")
    
    try:
        project = await database.fetch_one(
            projects.select().where(
                (projects.c.id == project_id) &
                (projects.c.workspace_id == workspace_id)
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    if project["is_deleted"]:
        logger.warning(f"Project already deleted: {project_id}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Project already deleted"
        )

    # 1️⃣ Soft delete in DB
    try:
        await database.execute(
            projects.update()
            .where(projects.c.id == project_id)
            .values(
                is_deleted=True,
                deleted_at=datetime.utcnow()
            )
        )
        logger.info(f"Project soft deleted: {project_id}")
    except Exception as e:
        logger.error(f"Failed to soft delete project: {str(e)}", exc_info=True)
        raise DatabaseException(
            user_message="Failed to delete project.",
            details={"project_id": project_id, "error": str(e)},
            error_code="DATABASE_UPDATE_ERROR"
        )

    # 2️⃣ Vector store cleanup (safe - log but don't fail)
    vector_path = project["vector_store_path"]
    if vector_path and os.path.exists(vector_path):
        try:
            shutil.rmtree(vector_path)
            logger.info(f"Vector store directory removed: {vector_path}")
        except Exception as e:
            logger.error(
                f"Failed to delete vector store directory: {vector_path}",
                exc_info=True,
                extra={"vector_path": vector_path, "error": str(e)}
            )
            # Don't fail the deletion if filesystem cleanup fails

    return {"message": "Project deleted successfully"}
