import json
from langchain_core.documents import Document
from rag.ingestion.normalization import normalize_for_json


def rows_to_documents(rows, source_id, source_file, source_type):
    documents = []

    for row in rows:
        row_index = row.pop("_row_index", None)

        normalized_row = {
            key: normalize_for_json(value)
            for key, value in row.items()
        }

        text = ". ".join(f"{k}: {v}" for k, v in normalized_row.items())

        documents.append(
            Document(
                page_content=text,
                metadata={
                    "source_id": source_id,
                    "source_file": source_file,
                    "source_type": source_type,
                    "row_index": row_index,
                    "columns": ",".join(normalized_row.keys()),
                    "original_row": json.dumps(normalized_row),
                },
            )
        )

    return documents
