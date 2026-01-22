import uuid
from fastapi import BackgroundTasks
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


async def start_ingestion_job(
    project_id: str,
    workspace_id: str,
    folder_path: str,
    background_tasks: BackgroundTasks,
):
    job_id = uuid.uuid4()

    # DB record (source of truth)
    await database.execute(
        ingestion_jobs.insert().values(
            id=job_id,
            project_id=project_id,
            status="pending",
        )
    )

    # Redis state (runtime)
    try:
        await redis_client.hset(
            f"ingestion:{job_id}",
            mapping={"status": "pending"}
        )
    except Exception:
        # Redis unavailable → continue, DB is still source of truth
        pass

    background_tasks.add_task(
        run_ingestion_job,
        job_id,
        project_id,
        folder_path,
    )

    return job_id


async def run_ingestion_job(job_id, project_id, folder_path):
    try:
        await redis_client.hset(f"ingestion:{job_id}", "status", "running")

        vector_store = VectorStoreManager(
            persist_directory=f"{folder_path}/../chroma_db"
        )

        file_router = FileRouter(
            ingestors=[PDFIngestor(), DocxIngestor(), SheetIngestor()]
        )

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
