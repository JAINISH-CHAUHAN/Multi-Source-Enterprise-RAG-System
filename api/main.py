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

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException
from api.core.database import database
from api.core.logging import setup_logging, get_logger
from api.core.exceptions import BaseAppException
from api.routers import (
    auth,
    projects,
    ingestion,
    ingestion_jobs,
    query,
    citations,
    conversations,
    documents,   
)
import traceback
import asyncio


logger = get_logger(__name__)


# Global task queue coroutine handle
_task_worker_task = None




app = FastAPI(title="rag-backend")



# Add this BEFORE your routes
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# GLOBAL EXCEPTION HANDLERS
# ============================================================================

@app.exception_handler(BaseAppException)
async def handle_app_exception(request: Request, exc: BaseAppException):
    """
    Handle all domain-specific exceptions (LLM, VectorStore, Ingestion, etc.)
    
    Returns structured JSON response with error details.
    Logs full context for debugging while sending clean message to frontend.
    """
    logger.error(
        f"Application error: {exc.error_code}",
        extra={
            "error_code": exc.error_code,
            "user_message": exc.user_message,
            "details": exc.details,
            "path": request.url.path
        },
        exc_info=True
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=exc.to_dict()
    )


@app.exception_handler(HTTPException)
async def handle_http_exception(request: Request, exc: HTTPException):
    """
    Handle FastAPI's HTTPException (validation, 404, auth errors, etc.)
    
    Preserves FastAPI's default behavior but adds logging.
    """
    logger.warning(
        f"HTTP exception: {exc.status_code} - {exc.detail}",
        extra={
            "status_code": exc.status_code,
            "detail": exc.detail,
            "path": request.url.path
        }
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )


@app.exception_handler(Exception)
async def handle_unexpected_exception(request: Request, exc: Exception):
    """
    Catch-all handler for unhandled exceptions.
    
    Prevents server crashes by intercepting unexpected errors.
    Logs full traceback for debugging.
    Returns generic error message to frontend (no internal details exposed).
    """
    # Log full traceback for debugging
    logger.critical(
        f"Unhandled exception: {str(exc)}",
        extra={
            "exception_type": type(exc).__name__,
            "path": request.url.path,
            "traceback": traceback.format_exc()
        },
        exc_info=True
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error_code": "INTERNAL_ERROR",
            "error_message": "An unexpected error occurred. Please try again later.",
            "details": {}
        }
    )


# ============================================================================
# EVENT HANDLERS
# ============================================================================

@app.on_event("startup")
async def startup():
    global _task_worker_task
    
    # Initialize logging infrastructure
    setup_logging(log_level="INFO")
    logger.info("Starting RAG Backend Application")
    
    # Connect to database
    await database.connect()
    logger.info("Database connection established")
    
    # Start task queue processor
    try:
        from api.services.task_worker import poll_queue
        _task_worker_task = asyncio.create_task(poll_queue())
        logger.info("Task queue processor started")
    except Exception as e:
        logger.error(f"Failed to start task queue processor: {str(e)}", exc_info=True)

@app.on_event("shutdown")
async def shutdown():
    global _task_worker_task
    
    # Stop task queue processor
    if _task_worker_task:
        _task_worker_task.cancel()
        try:
            await _task_worker_task
        except asyncio.CancelledError:
            logger.info("Task queue processor stopped")
    
    await database.disconnect()
    logger.info("Database connection closed")
    logger.info("Application shutdown complete")


# ============================================================================
# ROUTERS
# ============================================================================

app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(projects.router, prefix="/projects", tags=["Projects"])
app.include_router(ingestion.router, tags=["Ingestion"])
app.include_router(ingestion_jobs.router, prefix="/ingestion-jobs", tags=["Ingestion Jobs"])
app.include_router(documents.router, tags=["Documents"])
app.include_router(query.router, tags=["Query"])
app.include_router(citations.router, tags=["Citations"])
app.include_router(conversations.router, tags=["Conversations"])


@app.get("/health")
async def health():
    return {"status": "ok"}
