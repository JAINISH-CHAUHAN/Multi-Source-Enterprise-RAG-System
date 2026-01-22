import redis.asyncio as redis
from api.core.config import settings

redis_client = redis.from_url(
    settings.REDIS_URL,
    decode_responses=True,
    socket_connect_timeout=2,
    socket_timeout=2,
)
