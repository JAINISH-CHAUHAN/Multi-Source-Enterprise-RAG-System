from fastapi import APIRouter
from api.core.redis import redis_client

router = APIRouter()

@router.get("/{job_id}")
async def get_job_status(job_id: str):
    data = await redis_client.hgetall(f"ingestion:{job_id}")
    return data or {"status": "unknown"}
