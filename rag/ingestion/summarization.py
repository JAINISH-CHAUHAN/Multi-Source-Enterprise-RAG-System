import json
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage
from core.ai_factory import get_llm
from rag.ingestion.content import separate_content_types


def create_ai_enhanced_summary(text, tables, images):
    try:
        llm = get_llm("primary")

        prompt = f"""
You are creating a searchable description for document retrieval.

TEXT:
{text}
"""

        if tables:
            for i, table in enumerate(tables):
                prompt += f"\nTable {i+1}:\n{table}\n"

        message = [{"type": "text", "text": prompt}]

        for img in images:
            message.append(
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img}"}}
            )

        return llm.invoke([HumanMessage(content=message)])

    except Exception:
        return text[:300] + "..."


def summarise_chunks(chunks, source_id, source_file, source_type):
    documents = []

    for i, chunk in enumerate(chunks):
        content = separate_content_types(chunk)

        enhanced = (
            create_ai_enhanced_summary(
                content["text"], content["tables"], content["images"]
            )
            if content["tables"] or content["images"]
            else content["text"]
        )

        documents.append(
            Document(
                page_content=enhanced,
                metadata={
                    "source_id": source_id,
                    "source_file": source_file,
                    "source_type": source_type,
                    "chunk_index": i + 1,
                    "total_chunks": len(chunks),
                    "original_content": json.dumps(
                        {
                            "raw_text": content["text"],
                            "tables_html": content["tables"],
                            "images_base64": content["images"],
                        }
                    ),
                },
            )
        )

    return documents
