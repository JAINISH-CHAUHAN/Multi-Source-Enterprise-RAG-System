# /rag/retrieval/answer.py

import os
from langchain_core.messages import HumanMessage
from core.ai_factory import get_llm
from core.vector_store import VectorStoreManager


def answer_query(
    query: str,
    persist_directory: str,
    k: int = 3,
    conversation_context: str = ""
) -> dict:
    """
    Generate a source-aware answer using retrieved chunks.
    """

    if not os.path.exists(persist_directory):
        raise FileNotFoundError(
            f"Vector store not found at: {persist_directory}"
        )

    vector_store_manager = VectorStoreManager(
        persist_directory=persist_directory
    )
    db = vector_store_manager.load_or_create()

    retrieved_docs = db.similarity_search(query, k=k)

    if not retrieved_docs:
        return {
            "answer": "No relevant documents found in the knowledge base.",
            "sources": []
        }

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

    llm = get_llm("primary")
    response = llm.invoke([
        HumanMessage(content=[{"type": "text", "text": prompt}])
    ])

    return {
        "answer": response,
        "sources": sources
    }
