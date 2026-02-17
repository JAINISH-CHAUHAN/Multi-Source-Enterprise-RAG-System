# /api/schemas/conversation.py

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID


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


class Source(BaseModel):
    """Citation source reference"""
    source_file: str
    chunk_index: int


class ConversationMessage(BaseModel):
    """Single message in a conversation"""
    id: UUID
    role: str
    content: str
    sources: Optional[List[Source]] = None
    created_at: datetime


class ConversationHistoryResponse(BaseModel):
    """Complete conversation history with messages and citations"""
    conversation_id: UUID
    title: Optional[str] = None
    messages: List[ConversationMessage]
