# /rag/retrieval/answer.py

import os
from langchain_core.messages import HumanMessage
from core.ai_factory import get_llm
from core.vector_store import VectorStoreManager
from api.core.exceptions import VectorStoreException, LLMException, FileProcessingException
from api.core.logging import get_logger

logger = get_logger(__name__)


def answer_query(
    query: str,
    persist_directory: str,
    k: int = 3,
    conversation_context: str = ""
) -> dict:
    """
    Generate a source-aware answer using retrieved chunks.
    """
    
    logger.info(f"Processing query with k={k}, persist_directory={persist_directory}")

    # Check if vector store exists
    if not os.path.exists(persist_directory):
        logger.warning(f"Vector store not found at: {persist_directory}")
        raise FileProcessingException(
            user_message="Knowledge base not found. Please ensure documents have been ingested.",
            details={"persist_directory": persist_directory},
            error_code="KNOWLEDGE_BASE_NOT_FOUND"
        )

    try:
        # Initialize vector store
        vector_store_manager = VectorStoreManager(
            persist_directory=persist_directory
        )
        db = vector_store_manager.load_or_create()

        # Perform similarity search
        retrieved_docs = db.similarity_search(query, k=k)
        
        logger.info(f"Retrieved {len(retrieved_docs)} documents for query")

        if not retrieved_docs:
            logger.info("No relevant documents found")
            return {
                "answer": "No relevant documents found in the knowledge base.",
                "sources": []
            }

        # Build context from retrieved documents
        context_blocks = []
        sources = []

        for idx, doc in enumerate(retrieved_docs):
            source_file = doc.metadata.get("source_file", "unknown")
            chunk_index = doc.metadata.get("chunk_index", idx)

            context_blocks.append(
                f"[SOURCE_FILE: {source_file} | CHUNK_INDEX: {chunk_index}]\n"
                f"{doc.page_content}"
            )

            sources.append({
                "source_file": source_file,
                "chunk_index": chunk_index
            })

        context = "\n\n".join(context_blocks)

        memory_block = ""
        if conversation_context:
            memory_block = f"""
CONVERSATION CONTEXT SUMMARY:
{conversation_context}
"""

        prompt = f"""
{memory_block}

You are a document-grounded question answering system.

STRICT RULES:
- Use ONLY the information present in the provided document excerpts.
- Do NOT use prior knowledge.
- Do NOT infer, assume, or guess.
- If the answer is not explicitly stated in the excerpts, respond with:
  "The provided documents do not contain this information."
- Do NOT add explanations beyond what is asked.

CITATION RULES (MANDATORY):
- Every factual statement MUST include an inline citation.
- Citations MUST use this exact format:
  [source_file#chunk_index]
- Use ONLY citations that appear in the provided document excerpts.
- Do NOT invent citations.
- You may reuse the same citation multiple times.


QUESTION:
{query}

DOCUMENT EXCERPTS:
{context}

ANSWER:
""".strip()

        # Invoke LLM
        llm = get_llm("primary")
        response = llm.invoke([
            HumanMessage(content=[{"type": "text", "text": prompt}])
        ])
        
        logger.info("Query answered successfully")

        return {
            "answer": response,
            "sources": sources
        }
    
    except (VectorStoreException, LLMException):
        # Re-raise domain exceptions (already logged by lower layers)
        raise
    except FileProcessingException:
        # Re-raise file processing exceptions
        raise
    except Exception as e:
        logger.error(
            f"Unexpected error in answer_query: {str(e)}",
            exc_info=True,
            extra={"query": query[:100], "error_type": type(e).__name__}
        )
        raise VectorStoreException(
            user_message="Failed to process your query. Please try again.",
            details={
                "error": str(e),
                "error_type": type(e).__name__
            },
            error_code="QUERY_PROCESSING_ERROR"
        )
