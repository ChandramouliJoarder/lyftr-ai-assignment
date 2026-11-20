from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, field_validator


class HealthResponse(BaseModel):
    """Health check response schema."""
    status: str = "ok"
    keys_configured: int
    cache_enabled: bool


class ChatRequest(BaseModel):
    """Chat request payload."""
    session_id: str
    message: str
    system_prompt: Optional[str] = None

    @field_validator("session_id")
    @classmethod
    def validate_session_id(cls, v: str) -> str:
        trimmed = v.strip() if isinstance(v, str) else ""
        if not trimmed or len(v) < 1 or len(v) > 128:
            raise ValueError("session_id must be between 1 and 128 characters and non-blank")
        return v

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        trimmed = v.strip() if isinstance(v, str) else ""
        if not trimmed:
            raise ValueError("message must not be empty or whitespace only")
        if len(trimmed) > 4000:
            raise ValueError("message must not exceed 4000 characters after trimming")
        return trimmed

    @field_validator("system_prompt")
    @classmethod
    def validate_system_prompt(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            trimmed = v.strip()
            return trimmed if trimmed else None
        return None


class AssistantMetadata(BaseModel):
    """Metadata for assistant reply."""
    resolution_source: Literal["LIVE_INFERENCE", "LLM_CACHE"]
    model: str
    latency_ms: int
    input_tokens: int
    output_tokens: int
    key_id: Optional[str] = None
    fallback_attempts: int = 0


class ChatResponse(BaseModel):
    """Chat response payload."""
    session_id: str
    reply: str
    metadata: AssistantMetadata


class MessageItem(BaseModel):
    """Stored chat message item."""
    role: Literal["user", "assistant"]
    content: str
    metadata: Optional[Dict[str, Any]] = None


class SessionMessagesResponse(BaseModel):
    """Chat history response for a session."""
    session_id: str
    messages: List[MessageItem]


class ErrorResponse(BaseModel):
    """Standard JSON error format."""
    detail: Any
