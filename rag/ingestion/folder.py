import os
import uuid
from core.file_router import FileRouter
from rag.ingestion.chunking import create_chunks_by_title
from rag.ingestion.rows import rows_to_documents
from rag.ingestion.summarization import summarise_chunks


def ingest_folder(folder_path, vector_store, file_router: FileRouter):
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        if not os.path.isfile(file_path):
            continue

        run_complete_ingestion_pipeline(file_path, vector_store, file_router)

    vector_store.persist()


def run_complete_ingestion_pipeline(file_path, vector_store, file_router):
    source_id = str(uuid.uuid4())
    source_file = os.path.basename(file_path)

    ingestor = file_router.route(file_path)
    source_type = ingestor.__class__.__name__.replace("Ingestor", "").lower()

    extracted = ingestor.ingest(file_path)

    if source_type == "sheet":
        documents = rows_to_documents(
            extracted, source_id, source_file, source_type
        )
    else:
        chunks = create_chunks_by_title(extracted)
        documents = summarise_chunks(
            chunks, source_id, source_file, source_type
        )

    vector_store.add_documents(documents)
