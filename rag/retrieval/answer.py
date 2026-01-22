import json
from langchain_core.messages import HumanMessage
from core.ai_factory import get_llm


def generate_final_answer(chunks, query):
    llm = get_llm("primary")

    prompt = f"Answer the question using the documents:\n{query}\n\n"

    for chunk in chunks:
        prompt += chunk.page_content + "\n\n"

    return llm.invoke([HumanMessage(content=[{"type": "text", "text": prompt}])])
