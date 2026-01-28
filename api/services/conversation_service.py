# /api/services/conversation_service.py

import json
from datetime import datetime
from api.core.redis import redis_client
from core.ai_factory import get_llm
from langchain_core.messages import HumanMessage


MAX_TURNS = 6
SUMMARY_KEY_PREFIX = "conversation_summary"


async def append_turn(conversation_id: str, role: str, content: str):
    payload = {
        "role": role,
        "content": content,
        "timestamp": datetime.utcnow().isoformat()
    }

    key = f"conversation:{conversation_id}"
    await redis_client.rpush(key, json.dumps(payload))
    await redis_client.ltrim(key, -MAX_TURNS, -1)


async def get_recent_turns(conversation_id: str) -> list[dict]:
    key = f"conversation:{conversation_id}"
    raw = await redis_client.lrange(key, 0, -1)
    return [json.loads(item) for item in raw]


async def get_conversation_summary(conversation_id: str) -> str | None:
    key = f"{SUMMARY_KEY_PREFIX}:{conversation_id}"
    summary = await redis_client.get(key)
    return summary


async def update_conversation_summary(conversation_id: str, turns: list[dict]):
    """
    Deterministically summarize conversation turns using LLM.
    """
    if not turns:
        return

    transcript = "\n".join(
        f"{t['role'].upper()}: {t['content']}"
        for t in turns
    )

    prompt = f"""
You are summarizing a conversation for context preservation.

STRICT RULES:
- Do NOT add new information.
- Do NOT infer or assume.
- Keep summary factual and concise.
- Preserve entities, terminology, and intent.

CONVERSATION:
{transcript}

SUMMARY:
""".strip()

    llm = get_llm("primary")
    response = llm.invoke([
        HumanMessage(content=[{"type": "text", "text": prompt}])
    ])

    key = f"{SUMMARY_KEY_PREFIX}:{conversation_id}"
    await redis_client.set(key, str(response))
# /api/services/conversation_service.py

import json
from datetime import datetime
from api.core.redis import redis_client
from core.ai_factory import get_llm
from langchain_core.messages import HumanMessage


MAX_TURNS = 6
SUMMARY_KEY_PREFIX = "conversation_summary"


async def append_turn(conversation_id: str, role: str, content: str):
    payload = {
        "role": role,
        "content": content,
        "timestamp": datetime.utcnow().isoformat()
    }

    key = f"conversation:{conversation_id}"
    await redis_client.rpush(key, json.dumps(payload))
    await redis_client.ltrim(key, -MAX_TURNS, -1)


async def get_recent_turns(conversation_id: str) -> list[dict]:
    key = f"conversation:{conversation_id}"
    raw = await redis_client.lrange(key, 0, -1)
    return [json.loads(item) for item in raw]


async def get_conversation_summary(conversation_id: str) -> str | None:
    key = f"{SUMMARY_KEY_PREFIX}:{conversation_id}"
    summary = await redis_client.get(key)
    return summary


async def update_conversation_summary(conversation_id: str, turns: list[dict]):
    """
    Deterministically summarize conversation turns using LLM.
    """
    if not turns:
        return

    transcript = "\n".join(
        f"{t['role'].upper()}: {t['content']}"
        for t in turns
    )

    prompt = f"""
You are summarizing a conversation for context preservation.

STRICT RULES:
- Do NOT add new information.
- Do NOT infer or assume.
- Keep summary factual and concise.
- Preserve entities, terminology, and intent.

CONVERSATION:
{transcript}

SUMMARY:
""".strip()

    llm = get_llm("primary")
    response = llm.invoke([
        HumanMessage(content=[{"type": "text", "text": prompt}])
    ])

    key = f"{SUMMARY_KEY_PREFIX}:{conversation_id}"
    await redis_client.set(key, str(response))
