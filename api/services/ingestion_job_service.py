import os
import shutil
import uuid
from fastapi import BackgroundTasks, UploadFile, HTTPException, status
from api.core.database import database
from api.core.redis import redis_client
from api.models.ingestion_job import ingestion_jobs
from api.models.project import projects

from core.vector_store import VectorStoreManager
from core.file_router import FileRouter
from providers.pdf_ingestor import PDFIngestor
from providers.docx_ingestor import DocxIngestor
from providers.sheet_ingestor import SheetIngestor

from rag.ingestion.folder import ingest_folder


async def start_ingestion_job_with_files(
    project_id: str,
    workspace_id: str,
    files: list[UploadFile],
    background_tasks: BackgroundTasks,
):
    """
    ✅ SYNCHRONOUSLY saves uploaded files during request lifecycle,
    then starts background ingestion job.
    """
    
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
    
    # 2️⃣ Construct filesystem paths
    BASE_DIR = os.path.abspath("vector_stores")
    
    kb_folder = os.path.join(
        BASE_DIR,
        str(workspace_id),
        str(project_id),
        "knowledge_base"
    )
    
    # 3️⃣ Create directory structure
    os.makedirs(kb_folder, exist_ok=True)
    
    # 4️⃣ CRITICAL: Save uploaded files SYNCHRONOUSLY (while UploadFile streams are valid)
    for file in files:
        file_path = os.path.join(kb_folder, file.filename)
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
    
    # 5️⃣ Create job record
    job_id = uuid.uuid4()
    
    await database.execute(
        ingestion_jobs.insert().values(
            id=job_id,
            project_id=project_id,
            status="pending",
        )
    )
    
    # 6️⃣ Redis state (runtime)
    try:
        await redis_client.hset(
            f"ingestion:{job_id}",
            mapping={"status": "pending"}
        )
    except Exception:
        pass
    
    # 7️⃣ Background task receives ONLY filesystem paths
    background_tasks.add_task(
        run_ingestion_job,
        job_id,
        project_id,
        kb_folder,  # ← Files already on disk
    )
    
    return job_id


async def run_ingestion_job(job_id, project_id, folder_path):
    """
    Background task that operates ONLY on filesystem paths.
    No UploadFile objects, no request context.
    """
    try:
        await redis_client.hset(f"ingestion:{job_id}", "status", "running")

        # ✅ Ensure paths are absolute
        folder_path = os.path.abspath(folder_path)
        
        # ✅ Verify folder exists
        if not os.path.exists(folder_path):
            raise FileNotFoundError(f"Knowledge base folder not found: {folder_path}")
        
        # ✅ Create chroma_db directory
        chroma_dir = os.path.join(os.path.dirname(folder_path), "chroma_db")
        os.makedirs(chroma_dir, exist_ok=True)

        vector_store = VectorStoreManager(
            persist_directory=chroma_dir
        )

        file_router = FileRouter(
            ingestors=[PDFIngestor(), DocxIngestor(), SheetIngestor()]
        )

        # ✅ Process files that are ALREADY on disk
        ingest_folder(folder_path, vector_store, file_router)

        await redis_client.hset(f"ingestion:{job_id}", "status", "completed")

        await database.execute(
            ingestion_jobs.update()
            .where(ingestion_jobs.c.id == job_id)
            .values(status="completed")
        )

    except Exception as e:
        await redis_client.hset(
            f"ingestion:{job_id}",
            mapping={"status": "failed", "error": str(e)}
        )

        await database.execute(
            ingestion_jobs.update()
            .where(ingestion_jobs.c.id == job_id)
            .values(status="failed", error_message=str(e))
        )