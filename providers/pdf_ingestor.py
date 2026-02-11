from unstructured.partition.pdf import partition_pdf
from core.document_ingestor import DocumentIngestor
from api.core.exceptions import FileProcessingException
from api.core.logging import get_logger

logger = get_logger(__name__)


class PDFIngestor(DocumentIngestor):
    def can_handle(self, file_path: str) -> bool:
        return file_path.lower().endswith(".pdf")

    def ingest(self, file_path: str):
        logger.info(f"Processing PDF: {file_path}")

        try:
            elements = partition_pdf(
                filename=file_path,
                strategy="hi_res",
                infer_table_structure=True,
                extract_image_block_types=["Image"],
                extract_image_block_to_payload=True
            )

            logger.info(f"Successfully extracted {len(elements)} elements from PDF: {file_path}")
            return elements
        except Exception as e:
            logger.error(
                f"PDF processing failed: {file_path}",
                exc_info=True,
                extra={"file_path": file_path, "error_type": type(e).__name__}
            )
            raise FileProcessingException(
                user_message=f"Failed to process PDF file: {file_path.split('/')[-1]}",
                details={
                    "file_path": file_path,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "file_type": "pdf"
                },
                error_code="FILE_PDF_PROCESSING_ERROR"
            )
