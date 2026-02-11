import os
import pandas as pd
from core.document_ingestor import DocumentIngestor
from api.core.exceptions import FileProcessingException
from api.core.logging import get_logger

logger = get_logger(__name__)


class SheetIngestor(DocumentIngestor):
    """
    Ingestor for spreadsheet-like data (CSV, XLSX).
    Extraction-only: returns rows as dictionaries.
    """

    def can_handle(self, file_path: str) -> bool:
        return file_path.lower().endswith((".csv", ".xlsx"))

    def ingest(self, file_path: str):
        logger.info(f"Processing spreadsheet: {file_path}")

        ext = os.path.splitext(file_path)[1].lower()

        if ext not in [".csv", ".xlsx"]:
            raise FileProcessingException(
                user_message=f"Unsupported spreadsheet format: {ext}",
                details={"file_path": file_path, "extension": ext},
                error_code="FILE_UNSUPPORTED_FORMAT"
            )

        try:
            if ext == ".csv":
                df = pd.read_csv(file_path)
            elif ext == ".xlsx":
                df = pd.read_excel(file_path)

            # Normalize column names
            df.columns = [str(c).strip() for c in df.columns]

            rows = []
            for idx, row in df.iterrows():
                row_dict = row.dropna().to_dict()
                row_dict["_row_index"] = idx
                rows.append(row_dict)

            logger.info(f"Successfully extracted {len(rows)} rows from spreadsheet: {file_path}")
            return rows
        except Exception as e:
            logger.error(
                f"Spreadsheet processing failed: {file_path}",
                exc_info=True,
                extra={"file_path": file_path, "error_type": type(e).__name__}
            )
            raise FileProcessingException(
                user_message=f"Failed to process spreadsheet file: {file_path.split('/')[-1]}",
                details={
                    "file_path": file_path,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "file_type": ext[1:]  # Remove the dot
                },
                error_code="FILE_SHEET_PROCESSING_ERROR"
            )
