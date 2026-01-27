from __future__ import annotations
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env.

    Uses Pydantic Settings 2.x. All fields are validated and typed.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # tgo-api base URL
    api_base_url: str

    # PostgreSQL DSN for SQLAlchemy async engine
    database_url: str  # e.g. postgresql+asyncpg://user:pass@host:5432/db

    # SSE and HTTP behavior
    sse_backpressure_limit: int = 1000
    request_timeout_seconds: int = 120

    # Redis (optional) for caching
    redis_url: str | None = None  # e.g. redis://127.0.0.1:6379/0
    visitor_cache_ttl_seconds: int = 24 * 60 * 60

    # Logging
    log_level: str = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL



settings = Settings()

