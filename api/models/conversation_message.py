# /api/models/conversation_message.py

import sqlalchemy as sa
import uuid
from api.core.database import metadata

conversation_messages = sa.Table(
    "conversation_messages",
    metadata,

    sa.Column(
        "id",
        sa.UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    ),

    sa.Column(
        "conversation_id",
        sa.UUID(as_uuid=True),
        sa.ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    ),

    sa.Column(
        "role",
        sa.String,
        nullable=False,  # "user" | "assistant"
    ),

    sa.Column(
        "content",
        sa.Text,
        nullable=False,
    ),

    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    ),
)

# Fetch messages of a conversation efficiently (ordered by time)
sa.Index(
    "idx_conversation_messages_conversation_id_created_at",
    conversation_messages.c.conversation_id,
    conversation_messages.c.created_at,
)
