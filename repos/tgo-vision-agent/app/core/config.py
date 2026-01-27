"""Application configuration settings."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env.

    Uses Pydantic Settings 2.x. All fields are validated and typed.
    """

    model_config = SettingsConfigDict(env_file=".env", env_prefix="TGO_", extra="ignore")

    # PostgreSQL DSN for SQLAlchemy async engine
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/tgo"

    # Redis URL for caching
    redis_url: str = "redis://localhost:6379/0"

    # AgentBay API Key (default for development, should be overridden in production)
    agentbay_api_key: str = ""

    # TGO API Configuration
    api_url: str = "http://localhost:8000"
    # TGO API Internal Service URL (for fetching AI provider config)
    api_internal_url: str = "http://localhost:8001"

    # TGO Platform Configuration (for message callbacks)
    platform_url: str = "http://localhost:8003"

    # Logging
    log_level: str = "INFO"

    # Message polling configuration
    default_poll_interval_seconds: int = 10

    # Screenshot storage
    screenshot_storage_path: str = "./screenshots"


settings = Settings()
