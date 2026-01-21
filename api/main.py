"""
Docstring for api.main
FILE PURPOSE:
Entry point for the FastAPI backend application.

RESPONSIBILITIES:
- Initialize FastAPI application
- Expose a health check endpoint for monitoring
- Load environment-specific configuration
- Act as the ASGI application entrypoint

ARCHITECTURE RULES:
- No business logic should live in this file
- No database connections should be created here
- No authentication or authorization logic here
- Only lightweight routing and app setup

TECH STACK:
- FastAPI
- Pydantic-based configuration

COPILOT INSTRUCTIONS:
- Keep this file minimal and readable
- Prefer explicit imports over wildcard imports
- Do not introduce unnecessary middleware

"""

from fastapi import FastAPI
from api.core.database import database
from api.routers import auth

app = FastAPI(title="rag-backend")

@app.on_event("startup")
async def startup():
    await database.connect()

@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()

app.include_router(auth.router, prefix="/auth", tags=["Auth"])

@app.get("/health")
async def health():
    return {"status": "ok"}


