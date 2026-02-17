from fastapi import APIRouter, Depends, HTTPException, status
from api.services.conversation_service import (
    create_conversation,
    list_conversations,
    delete_conversation,
    rename_conversation,
    get_conversation_history,
)
from api.core.dependencies import get_current_user
from api.schemas.conversation import RenameConversationRequest, ConversationHistoryResponse

router = APIRouter()


@router.get("/conversations/{conversation_id}/history", response_model=ConversationHistoryResponse)
async def get_conversation_messages(
    conversation_id: str,
    current_user=Depends(get_current_user),
):
    """Get complete conversation history with all messages and citations"""
    history = await get_conversation_history(
        conversation_id=conversation_id,
        user_id=current_user["user_id"],
    )

    if not history:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found or unauthorized"
        )

    return history


@router.patch("/conversations/{conversation_id}/rename")
async def update_conversation_title(
    conversation_id: str,
    request: RenameConversationRequest,
    current_user=Depends(get_current_user),
):
    """Rename a conversation"""
    renamed = await rename_conversation(
        conversation_id=conversation_id,
        user_id=current_user["user_id"],
        new_title=request.title,
    )

    if not renamed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found or unauthorized"
        )

    return {
        "status": "success",
        "conversation_id": conversation_id,
        "title": request.title
    }


@router.post("/projects/{project_id}/conversations")
async def start_conversation(
    project_id: str,
    current_user=Depends(get_current_user),
):
    conversation_id = await create_conversation(
        project_id=project_id,
        user_id=current_user["user_id"],
    )

    return {
        "conversation_id": conversation_id
    }


@router.get("/projects/{project_id}/conversations")
async def get_conversations(
    project_id: str,
    current_user=Depends(get_current_user),
):
    conversations = await list_conversations(
        project_id=project_id,
        user_id=current_user["user_id"],
    )

    return {
        "conversations": conversations
    }


@router.delete("/conversations/{conversation_id}")
async def remove_conversation(
    conversation_id: str,
    current_user=Depends(get_current_user),
):
    deleted = await delete_conversation(
        conversation_id=conversation_id,
        user_id=current_user["user_id"],
    )

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )

    return {
        "status": "deleted",
        "conversation_id": conversation_id
    }
