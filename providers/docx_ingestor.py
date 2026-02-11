from unstructured.partition.docx import partition_docx
from core.document_ingestor import DocumentIngestor
from api.core.exceptions import FileProcessingException
from api.core.logging import get_logger

logger = get_logger(__name__)


class DocxIngestor(DocumentIngestor):
    """
    Ingestor for DOCX files.
    Responsible ONLY for extraction, not chunking or summarization.
    """

    def can_handle(self, file_path: str) -> bool:
        return file_path.lower().endswith(".docx")

    def ingest(self, file_path: str):
        logger.info(f"Processing DOCX: {file_path}")

        try:
            elements = partition_docx(
                filename=file_path
            )

            logger.info(f"Successfully extracted {len(elements)} elements from DOCX: {file_path}")
            return elements
        except Exception as e:
            logger.error(
                f"DOCX processing failed: {file_path}",
                exc_info=True,
                extra={"file_path": file_path, "error_type": type(e).__name__}
            )
            raise FileProcessingException(
                user_message=f"Failed to process DOCX file: {file_path.split('/')[-1]}",
                details={
                    "file_path": file_path,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "file_type": "docx"
                },
                error_code="FILE_DOCX_PROCESSING_ERROR"
            )
