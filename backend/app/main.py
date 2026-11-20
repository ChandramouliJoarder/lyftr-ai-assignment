import logging
import time
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.db import db
from app.llm import (
    AllProvidersUnavailableError,
    cache_enabled,
    execute_llm_request,
)
from app.schemas import (
    ChatRequest,
    ChatResponse,
    HealthResponse,
    SessionMessagesResponse,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize SQLite database schema on startup."""
    logger.info("Initializing database schema...")
    db.init_schema()
    logger.info("Database schema initialized. Keys configured: %d", settings.keys_configured)
    yield


app = FastAPI(
    title="LLM Chatbot with Key Failover and Caching",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# Exception Handlers to guarantee uniform JSON responses without stack traces
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": jsonable_encoder(exc.errors())},
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled server error: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "internal server error"},
    )


@app.get("/health", response_model=HealthResponse)
def get_health():
    """Health check endpoint checking database and key configuration."""
    db_healthy = db.check_health()
    if not db_healthy:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="database unreachable",
        )
    return HealthResponse(
        status="ok",
        keys_configured=settings.keys_configured,
        cache_enabled=cache_enabled,
    )


@app.post("/chat", response_model=ChatResponse)
def post_chat(
    req: ChatRequest,
    x_simulate_failure: Optional[str] = Header(None, alias="X-Simulate-Failure"),
):
    """
    Chat endpoint with multi-turn history, key failover, and caching.
    """
    start_time = time.perf_counter()

    # Load session history (WITHOUT system prompt)
    history = db.get_session_history(req.session_id)

    # Determine effective system prompt
    if req.system_prompt:
        system_prompt = req.system_prompt
    else:
        existing_prompt = db.get_session_system_prompt(req.session_id)
        system_prompt = existing_prompt or settings.DEFAULT_SYSTEM_PROMPT

    # Build prompt messages: [system prompt] + history + [new user message]
    llm_messages = [{"role": "system", "content": system_prompt}]
    for msg in history:
        llm_messages.append({"role": msg["role"], "content": msg["content"]})
    llm_messages.append({"role": "user", "content": req.message})

    # Execute LLM request with caching and failover
    try:
        reply, metadata = execute_llm_request(
            llm_messages,
            simulate_header=x_simulate_failure,
        )
    except AllProvidersUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="all providers unavailable",
        )
    except Exception as e:
        logger.exception("Error executing LLM request: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="all providers unavailable",
        )

    # Server-measured total latency in milliseconds
    latency_ms = max(1, int((time.perf_counter() - start_time) * 1000))
    metadata["latency_ms"] = latency_ms

    # Save turn to SQLite in one transaction ONLY AFTER successful LLM call
    db.save_turn(
        session_id=req.session_id,
        user_content=req.message,
        assistant_content=reply,
        assistant_metadata=metadata,
        system_prompt=req.system_prompt,
    )

    return ChatResponse(
        session_id=req.session_id,
        reply=reply,
        metadata=metadata,
    )


@app.get("/sessions/{session_id}/messages", response_model=SessionMessagesResponse)
def get_session_messages(session_id: str):
    """
    Return stored history for a session, oldest first, without system prompt.
    Returns 404 if session does not exist.
    """
    if not db.session_exists(session_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="session not found",
        )

    messages = db.get_session_history(session_id)
    return SessionMessagesResponse(
        session_id=session_id,
        messages=messages,
    )
