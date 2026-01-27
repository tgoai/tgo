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
    SERVICE_NAME: str = Field(default="TGO Device Control")
    SERVICE_VERSION: str = Field(default="1.0.0")

    # Server Configuration
    HOST: str = Field(default="0.0.0.0")
    PORT: int = Field(default=8085)

    # WebSocket Configuration
    WS_HEARTBEAT_INTERVAL: int = Field(
        default=30,
        description="Heartbeat interval in seconds for WebSocket connections",
    )
    WS_HEARTBEAT_TIMEOUT: int = Field(
        default=90,
        description="Timeout in seconds before considering a connection dead",
    )
    WS_REQUEST_TIMEOUT: int = Field(
        default=60,
        description="Timeout in seconds for device requests",
    )

    # Bind Code Configuration
    BIND_CODE_LENGTH: int = Field(default=6, description="Length of device bind code")
    BIND_CODE_EXPIRY_MINUTES: int = Field(
        default=5,
        description="Bind code expiry time in minutes",
    )

    # AI Service Configuration (for MCP tool registration)
    AI_SERVICE_URL: str = Field(
        default="http://localhost:8081",
        description="URL of the TGO AI service",
    )
    AI_SERVICE_TIMEOUT: int = Field(
        default=30,
        description="Timeout for AI service requests in seconds",
    )

    # API Service Configuration
    API_SERVICE_URL: str = Field(
        default="http://localhost:8000",
        description="URL of the TGO API service",
    )

    # Database Configuration
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://tgo:tgo@localhost:5432/tgo",
        description="PostgreSQL database URL",
    )
    DATABASE_POOL_SIZE: int = Field(default=5)
    DATABASE_MAX_OVERFLOW: int = Field(default=10)

    # Redis Configuration
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis URL for caching and pub/sub",
    )

    # File Storage Configuration (for screenshots)
    STORAGE_TYPE: str = Field(
        default="local",
        description="Storage type: local, s3, minio",
    )
    STORAGE_LOCAL_PATH: str = Field(
        default="/var/lib/tgo/device-control/screenshots",
        description="Local storage path for screenshots",
    )
    STORAGE_S3_BUCKET: Optional[str] = Field(default=None)
    STORAGE_S3_ENDPOINT: Optional[str] = Field(default=None)
    STORAGE_S3_ACCESS_KEY: Optional[str] = Field(default=None)
    STORAGE_S3_SECRET_KEY: Optional[str] = Field(default=None)

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
