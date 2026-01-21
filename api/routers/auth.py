from fastapi import APIRouter, HTTPException
from api.schemas.auth import RegisterRequest, LoginRequest, TokenResponse
from api.services.auth_service import register_user, authenticate_user



router = APIRouter()

@router.post("/register", status_code=201)
async def register(payload: RegisterRequest):
    try:
        await register_user(
            payload.email,
            payload.password,
            payload.organization_name
        )
    except ValueError as e:
        if str(e) == "USER_ALREADY_EXISTS":
            raise HTTPException(
                status_code=409,
                detail="User already exists"
            )
        raise

    return {"message": "User registered"}



@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest):
    try:
        token = await authenticate_user(payload.email, payload.password)
    except ValueError as e:
        if str(e) == "USER_NOT_FOUND":
            raise HTTPException(
                status_code=404,
                detail="User does not exist"
            )
        raise

    if not token:
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials"
        )

    return {"access_token": token}

