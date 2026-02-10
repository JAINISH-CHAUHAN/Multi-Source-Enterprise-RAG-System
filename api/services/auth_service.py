from api.core.database import database
from api.models.user import users
from api.models.organization import organizations
from api.models.session import sessions
from api.core.security import hash_password, verify_password, create_access_token
from datetime import datetime, timedelta, timezone
from sqlalchemy.exc import IntegrityError

import uuid


async def register_user(email: str, password: str, org_name: str):
    existing_user = await database.fetch_one(
        users.select().where(users.c.email == email)
    )

    if existing_user:
        raise ValueError("USER_ALREADY_EXISTS")

    org_id = uuid.uuid4()

    await database.execute(
        organizations.insert().values(
            id=org_id,
            name=org_name
        )
    )

    user_id = uuid.uuid4()

    await database.execute(
        users.insert().values(
            id=user_id,
            email=email,
            password_hash=hash_password(password),
            org_id=org_id
        )
    )

    return {"user_id": user_id}



async def authenticate_user(email: str, password: str):
    user = await database.fetch_one(
        users.select().where(users.c.email == email)
    )

    if not user:
        raise ValueError("USER_NOT_FOUND")

    if not verify_password(password, user["password_hash"]):
        return None

    session_id = uuid.uuid4()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

    await database.execute(
        sessions.insert().values(
            id=session_id,
            user_id=user["id"],
            expires_at=expires_at
        )
    )

    token = create_access_token({
        "sub": str(user["id"]),
        "org_id": str(user["org_id"]),
        "session_id": str(session_id)
    })

    return token


async def logout_user(session_id: str):
    """Delete user session to invalidate token"""
    result = await database.execute(
        sessions.delete().where(sessions.c.id == session_id)
    )
    
    if result == 0:
        raise ValueError("SESSION_NOT_FOUND")
    
    return {"message": "Logged out successfully"}

