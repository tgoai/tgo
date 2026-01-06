"""Application configuration using Pydantic Settings."""

from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Service Info
    SERVICE_NAME: str = Field(default="TGO Plugin Runtime")
    SERVICE_VERSION: str = Field(default="1.0.0")

    # Server Configuration
    HOST: str = Field(default="0.0.0.0")
    PORT: int = Field(default=8090)

    # Plugin Socket Configuration
    PLUGIN_SOCKET_PATH: str = Field(
        default="/var/run/tgo/tgo.sock",
        description="Unix socket path for plugin communication",
    )
    PLUGIN_TCP_PORT: Optional[int] = Field(
        default=None,
        description="TCP port for plugin communication (alternative to Unix socket)",
    )
    PLUGIN_REQUEST_TIMEOUT: int = Field(
        default=30,
        description="Timeout in seconds for plugin requests",
    )
    PLUGIN_PING_INTERVAL: int = Field(
        default=30,
        description="Interval in seconds for plugin heartbeat ping",
    )

    # AI Service Configuration (for tool sync)
    AI_SERVICE_URL: str = Field(
        default="http://localhost:8081",
        description="URL of the TGO AI service for tool sync",
    )
    AI_SERVICE_TIMEOUT: int = Field(
        default=30,
        description="Timeout for AI service requests in seconds",
    )

    # Database Configuration
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/tgo",
        description="PostgreSQL database URL",
    )
    DATABASE_POOL_SIZE: int = Field(default=5)
    DATABASE_MAX_OVERFLOW: int = Field(default=10)

    # Security
    SECRET_KEY: str = Field(
        default="secret-key-at-least-32-chars-long!!",
        description="Secret key for JWT verification (must match tgo-api)",
    )

    # Logging
    LOG_LEVEL: str = Field(default="INFO")

    # Environment
    ENVIRONMENT: str = Field(default="development")
    DEBUG: bool = Field(default=False)

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT.lower() in ("development", "dev", "local")

    @property
    def database_url_sync(self) -> str:
        """Get synchronous database URL."""
        url = str(self.DATABASE_URL)
        if "postgresql+asyncpg://" in url:
            return url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
        return url

    @property
    def database_url_async(self) -> str:
        """Get asynchronous database URL."""
        return str(self.DATABASE_URL)


# Global settings instance
settings = Settings()

