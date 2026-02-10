from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from api.core.config import settings
from api.core.database import database
from api.models.session import sessions
from datetime import datetime, timezone

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    token = credentials.credentials
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=["HS256"]
        )
        session_id = payload["session_id"]
        
        # Validate session exists and hasn't expired
        session = await database.fetch_one(
            sessions.select().where(sessions.c.id == session_id)
        )
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )
        
        if session["expires_at"] < datetime.now(timezone.utc):  
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session expired",
            )
        
        return {
            "user_id": payload["sub"],
            "workspace_id": payload["org_id"],
            "session_id": payload["session_id"],
        }
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
