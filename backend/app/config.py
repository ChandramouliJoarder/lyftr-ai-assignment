import os
from typing import List, Tuple
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    LLM_API_KEYS: str = Field(default="", description="Comma-separated API key pool")
    LLM_MODEL: str = Field(default="gemini/gemini-2.0-flash", description="LiteLLM model string")
    DATABASE_URL: str = Field(default="sqlite:///./app.db", description="SQLite database URL")
    ALLOWED_ORIGINS: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000,https://your-frontend.vercel.app",
        description="Comma-separated allowed CORS origins",
    )
    ENABLE_FAILURE_SIMULATION: bool = Field(
        default=True,
        description="Enable failover test hook via X-Simulate-Failure header",
    )
    DEFAULT_SYSTEM_PROMPT: str = Field(
        default="You are a helpful, concise assistant.",
        description="Default system prompt for new sessions",
    )
    CACHE_DIR: str = Field(default="./cache", description="Directory for LiteLLM disk cache")
    REQUEST_TIMEOUT_SECONDS: int = Field(default=30, description="Per-call timeout for LLM provider")

    @property
    def key_pool(self) -> List[Tuple[str, str]]:
        """
        Parse LLM_API_KEYS into ordered list of (key_id, raw_key).
        Key ids are key_1, key_2, ... in that order. Ignore empty entries, trim whitespace.
        """
        raw_keys = [k.strip() for k in self.LLM_API_KEYS.split(",") if k.strip()]
        return [(f"key_{i + 1}", key) for i, key in enumerate(raw_keys)]

    @property
    def keys_configured(self) -> int:
        """Return the number of configured API keys."""
        return len(self.key_pool)

    @property
    def cors_origins(self) -> List[str]:
        """Parse ALLOWED_ORIGINS into a clean list of origins."""
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]


settings = Settings()
