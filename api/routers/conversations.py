from fastapi import APIRouter, Depends
from api.services.conversation_service import create_conversation
from api.core.dependencies import get_current_user

router = APIRouter()


@router.post("/projects/{project_id}/conversations")
async def start_conversation(
    project_id: str,
    current_user=Depends(get_current_user),
):
    conversation_id = await create_conversation(
        project_id=project_id,
        user_id=current_user["user_id"]
    )

    return {
        "conversation_id": conversation_id
    }
