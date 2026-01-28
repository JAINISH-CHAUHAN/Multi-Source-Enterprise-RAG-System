import uuid
from api.core.database import database
from api.models.conversation import conversations
from api.models.conversation_message import conversation_messages
from core.ai_factory import get_llm
from langchain_core.messages import HumanMessage


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


async def append_turn(conversation_id: str, role: str, content: str):
    await database.execute(
        conversation_messages.insert().values(
            id=str(uuid.uuid4()),
            conversation_id=conversation_id,
            role=role,
            content=content,
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

    llm = get_llm("primary")
    response = llm.invoke([
        HumanMessage(content=[{"type": "text", "text": prompt}])
    ])

    await database.execute(
        conversations.update()
        .where(conversations.c.id == conversation_id)
        .values(summary=str(response))
    )
