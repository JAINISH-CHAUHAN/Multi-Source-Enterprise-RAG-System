# /api/schemas/conversation.py

from pydantic import BaseModel, Field


class RenameConversationRequest(BaseModel):
    """Request body for renaming a conversation"""
    title: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="New title for the conversation"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "title": "Q&A about Product Requirements"
            }
        }
