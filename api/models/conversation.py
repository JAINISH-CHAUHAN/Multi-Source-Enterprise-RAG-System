# /api/models/conversation.py

import sqlalchemy as sa
import uuid
from api.core.database import metadata

conversations = sa.Table(
    "conversations",
    metadata,

    sa.Column(
        "id",
        sa.UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    ),

    sa.Column(
        "project_id",
        sa.UUID(as_uuid=True),
        sa.ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    ),

    sa.Column(
        "user_id",
        sa.UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    ),

    # User-defined title for the conversation
    sa.Column(
        "title",
        sa.String(255),
        nullable=True,
    ),

    # LLM-generated rolling summary
    sa.Column(
        "summary",
        sa.Text,
        nullable=True,
    ),

    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    ),

    sa.Column(
        "updated_at",
        sa.DateTime(timezone=True),
        onupdate=sa.func.now(),
        nullable=True,
    ),
)

# Useful index: fetch conversations per project quickly
sa.Index(
    "idx_conversations_project_id",
    conversations.c.project_id,
)

# Useful index: fetch conversations per user quickly
sa.Index(
    "idx_conversations_user_id",
    conversations.c.user_id,
)
