import json
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage
from core.ai_factory import get_llm
from rag.ingestion.content import separate_content_types
from api.core.logging import get_logger

logger = get_logger(__name__)


def create_ai_enhanced_summary(text, tables, images):
    """
    Create AI-enhanced summary for document chunk.
    
    Falls back to truncated text if LLM fails (logs error but doesn't halt ingestion).
    """
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

        summary = llm.invoke([HumanMessage(content=message)])
        logger.debug("AI-enhanced summary created successfully")
        return summary

    except Exception as e:
        logger.warning(
            f"Failed to create AI-enhanced summary, falling back to truncated text: {str(e)}",
            extra={"error_type": type(e).__name__}
        )
        # Fallback: use truncated original text
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
