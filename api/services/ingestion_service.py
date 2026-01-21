import os
import shutil
import uuid
from fastapi import HTTPException, status, UploadFile
from api.core.database import database
from api.models.project import projects
from api.models.document import documents

from core.vector_store import VectorStoreManager
from core.file_router import FileRouter
from providers.pdf_ingestor import PDFIngestor
from providers.docx_ingestor import DocxIngestor
from providers.sheet_ingestor import SheetIngestor

from ingestion import ingest_folder


async def ingest_files_for_project(
    workspace_id: str,
    project_id: str,
    files: list[UploadFile],
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

    # 2️⃣ Prepare folders
    project_root = project["vector_store_path"]
    kb_folder = os.path.join(project_root, "knowledge_base")
    os.makedirs(kb_folder, exist_ok=True)

    # 3️⃣ Save uploaded files
    for file in files:
        file_path = os.path.join(kb_folder, file.filename)

        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

    # 4️⃣ Initialize vector store (PROJECT SCOPED)
    vector_store = VectorStoreManager(
        persist_directory=os.path.join(project_root, "chroma_db")
    )

    # 5️⃣ File router (reuse your design)
    file_router = FileRouter(
        ingestors=[
            PDFIngestor(),
            DocxIngestor(),
            SheetIngestor(),
        ]
    )

    # 6️⃣ Run YOUR existing folder ingestion pipeline
    ingest_folder(
        folder_path=kb_folder,
        vector_store=vector_store,
        file_router=file_router
    )

    # 7️⃣ Store document metadata
    for file in files:
        await database.execute(
            documents.insert().values(
            id=uuid.uuid4(),
            project_id=project_id,
            file_name=file.filename,
            source_type=file.filename.split(".")[-1].lower()
    )
)

    return {"message": "Files ingested successfully"}
