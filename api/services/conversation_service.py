import uuid
from api.core.database import database
from api.models.conversation import conversations
from api.models.conversation_message import conversation_messages
from api.core.logging import get_logger
from api.core.exceptions import LLMException
from core.ai_factory import get_llm
from langchain_core.messages import HumanMessage
from sqlalchemy import desc

logger = get_logger(__name__)


MAX_TURNS_FOR_SUMMARY = 12


async def create_conversation(project_id: str, user_id: str) -> str:
    conversation_id = str(uuid.uuid4())

    await database.execute(
        conversations.insert().values(
            id=conversation_id,
            project_id=project_id,
            user_id=user_id,
        )
    )

    return conversation_id


async def append_turn(conversation_id: str, role: str, content: str, sources: list = None):
    await database.execute(
        conversation_messages.insert().values(
            id=str(uuid.uuid4()),
            conversation_id=conversation_id,
            role=role,
            content=content,
            sources=sources,
        )
    )


async def get_recent_turns(conversation_id: str) -> list[dict]:
    query = (
        conversation_messages.select()
        .where(conversation_messages.c.conversation_id == conversation_id)
        .order_by(conversation_messages.c.created_at.desc())
        .limit(MAX_TURNS_FOR_SUMMARY)
    )

    rows = await database.fetch_all(query)
    return list(reversed([dict(r) for r in rows]))


async def get_conversation_summary(conversation_id: str) -> str | None:
    row = await database.fetch_one(
        conversations.select().where(conversations.c.id == conversation_id)
    )
    return row["summary"] if row else None


async def update_conversation_summary(conversation_id: str, turns: list[dict]):
    """
    Update conversation summary using LLM.
    
    Logs errors but doesn't fail if summarization fails (non-critical operation).
    """
    if not turns:
        return

    transcript = "\n".join(
        f"{t['role'].upper()}: {t['content']}"
        for t in turns
    )

    prompt = f"""
You are summarizing a conversation for context preservation.

RULES:
- Do NOT add information
- Do NOT infer
- Preserve intent and terminology
- Keep concise

CONVERSATION:
{transcript}

SUMMARY:
""".strip()

    try:
        llm = get_llm("primary")
        response = llm.invoke([
            HumanMessage(content=[{"type": "text", "text": prompt}])
        ])

        await database.execute(
            conversations.update()
            .where(conversations.c.id == conversation_id)
            .values(summary=str(response))
        )
        
        logger.debug(f"Updated conversation summary for {conversation_id}")
        
    except LLMException as e:
        logger.warning(
            f"Failed to generate conversation summary (LLM error): {e.user_message}",
            extra={"conversation_id": conversation_id, "error_code": e.error_code}
        )
        # Don't fail - conversation can continue without summary
    except Exception as e:
        logger.error(
            f"Unexpected error updating conversation summary: {str(e)}",
            exc_info=True,
            extra={"conversation_id": conversation_id}
        )
        # Don't fail - conversation can continue without summary


async def list_conversations(project_id: str, user_id: str) -> list[dict]:
    query = (
        conversations.select()
        .where(
            (conversations.c.project_id == project_id) &
            (conversations.c.user_id == user_id)
        )
        .order_by(desc(conversations.c.updated_at), desc(conversations.c.created_at))
    )

    rows = await database.fetch_all(query)
    return [dict(r) for r in rows]


async def delete_conversation(conversation_id: str, user_id: str) -> bool:
    """
    Delete a conversation owned by the user.
    Returns True if deleted, False if not found.
    """

    # ✅ Step 1: Check existence + ownership
    conversation = await database.fetch_one(
        conversations.select().where(
            (conversations.c.id == conversation_id) &
            (conversations.c.user_id == user_id)
        )
    )

    if not conversation:
        return False

    # ✅ Step 2: Delete
    await database.execute(
        conversations.delete().where(conversations.c.id == conversation_id)
    )

    return True


async def rename_conversation(
    conversation_id: str, 
    user_id: str, 
    new_title: str
) -> bool:
    """
    Rename a conversation owned by the user.
    Returns True if renamed, False if not found or unauthorized.
    """
    # Verify ownership before updating
    conversation = await database.fetch_one(
        conversations.select().where(
            (conversations.c.id == conversation_id) &
            (conversations.c.user_id == user_id)
        )
    )

    if not conversation:
        return False

    # Update the title
    await database.execute(
        conversations.update()
        .where(conversations.c.id == conversation_id)
        .values(title=new_title.strip())
    )

    logger.info(
        f"Conversation {conversation_id} renamed to '{new_title}'",
        extra={"conversation_id": conversation_id, "user_id": user_id}
    )

    return True


async def get_conversation_history(conversation_id: str, user_id: str) -> dict | None:
    """
    Get complete conversation history with all messages and citations.
    Returns None if conversation not found or unauthorized.
    """
    # Verify ownership
    conversation = await database.fetch_one(
        conversations.select().where(
            (conversations.c.id == conversation_id) &
            (conversations.c.user_id == user_id)
        )
    )

    if not conversation:
        return None

    # Fetch all messages ordered by creation time
    query = (
        conversation_messages.select()
        .where(conversation_messages.c.conversation_id == conversation_id)
        .order_by(conversation_messages.c.created_at.asc())
    )

    messages = await database.fetch_all(query)

    return {
        "conversation_id": conversation["id"],
        "title": conversation["title"],
        "messages": [dict(msg) for msg in messages]
    }
