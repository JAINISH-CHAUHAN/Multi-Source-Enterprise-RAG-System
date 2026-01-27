# /api/services/conversation_service.py

import json
from datetime import datetime
from api.core.redis import redis_client


MAX_TURNS = 6  # hard cap to avoid prompt bloat


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
