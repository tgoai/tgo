"""Application configuration using Pydantic Settings."""

from typing import List, Union

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.runtime.supervisor.config import SupervisorRuntimeSettings
from app.runtime.tools.config import ToolsRuntimeSettings

class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database Configuration
    database_url: str = Field(
        default="sqlite+aiosqlite:///./tgo_ai_service.db",
        description="Database URL (async driver)",
    )
    database_pool_size: int = Field(
        default=20, description="Database connection pool size"
    )
    database_max_overflow: int = Field(
        default=30, description="Database connection pool max overflow"
    )
    database_pool_timeout: int = Field(
        default=30, description="Database connection pool timeout in seconds"
    )
    database_pool_recycle: int = Field(
        default=3600, description="Database connection pool recycle time in seconds"
    )

    # Application Configuration
    secret_key: str = Field(
        default="your-super-secret-key-change-this-in-production",
        description="Secret key for JWT token signing",
    )
    api_key_prefix: str = Field(
        default="ak_", description="Prefix for API keys"
    )
    algorithm: str = Field(default="HS256", description="JWT algorithm")
    access_token_expire_minutes: int = Field(
        default=30, description="JWT token expiration time in minutes"
    )

    # RAG Service Configuration
    rag_service_url: str = Field(
        default="http://localhost:8085",
        description="Base URL for the RAG service"
    )


    # MCP Service Configuration
    mcp_service_url: str = Field(
        default="http://localhost:8082",
        description="Base URL for the MCP service"
    )

    # Workflow Service Configuration
    workflow_service_url: str = Field(
        default="http://localhost:8086",
        description="Base URL for the Workflow service"
    )


    # Agent Runtime Service Configuration
    agent_service_url: str = Field(
        default="http://localhost:8083",
        description="Base URL for the agent runtime service",
    )


    # API Service Configuration
    api_service_url: str = Field(
        default="http://localhost:8080",
        description="Base URL for the core API service (events ingestion)",
    )

    # Plugin Runtime Configuration
    plugin_runtime_url: str = Field(
        default="http://localhost:8090",
        description="Base URL for the plugin runtime service",
    )

    # Server Configuration
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8081, description="Server port")
    reload: bool = Field(default=False, description="Enable auto-reload in development")
    environment: str = Field(default="development", description="Environment name")

    # CORS Configuration
    cors_origins: List[str] = Field(
        default=[
            "http://localhost:3000",
            "http://localhost:8080",
            "https://app.tgo-tech.com",
        ],
        description="Allowed CORS origins",
    )
    cors_allow_credentials: bool = Field(
        default=True, description="Allow CORS credentials"
    )
    cors_allow_methods: List[str] = Field(
        default=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        description="Allowed CORS methods",
    )
    cors_allow_headers: List[str] = Field(
        default=["*"], description="Allowed CORS headers"
    )

    # Logging Configuration
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(default="json", description="Log format (json or text)")

    # Rate Limiting
    rate_limit_enabled: bool = Field(
        default=True, description="Enable rate limiting"
    )
    rate_limit_requests_per_minute: int = Field(
        default=100, description="Rate limit requests per minute"
    )

    # Feature Flags
    health_check_enabled: bool = Field(
        default=True, description="Enable health check endpoint"
    )
    metrics_enabled: bool = Field(
        default=True, description="Enable metrics collection"
    )
    metrics_path: str = Field(default="/metrics", description="Metrics endpoint path")
    docs_enabled: bool = Field(
        default=True, description="Enable API documentation"
    )
    redoc_enabled: bool = Field(
        default=True, description="Enable ReDoc documentation"
    )

    # Embedding sync retry scheduler configuration
    embedding_sync_retry_enabled: bool = Field(
        default=True, description="Enable periodic retry for embedding config sync"
    )
    embedding_sync_retry_interval_seconds: int = Field(
        default=60, description="Interval in seconds between retry runs"
    )
    embedding_sync_retry_max_attempts: int = Field(
        default=10, description="Maximum total retry attempts before giving up"
    )
    embedding_sync_retry_stale_pending_minutes: int = Field(
        default=10, description="Consider 'pending' records stale after this many minutes"
    )

    # Runtime configuration
    # Note: These nested settings will be loaded from environment variables
    # with the appropriate prefixes (SUPERVISOR_RUNTIME__ and TOOLS_RUNTIME__)
    supervisor_runtime: SupervisorRuntimeSettings = Field(
        default_factory=lambda: SupervisorRuntimeSettings(_env_file=".env"),
        description="Supervisor运行时配置",
    )
    tools_runtime: ToolsRuntimeSettings = Field(
        default_factory=lambda: ToolsRuntimeSettings(_env_file=".env"),
        description="工具智能体运行时配置",
    )

    # Testing Configuration
    test_database_url: str = Field(
        default="postgresql+asyncpg://postgres:password@localhost:5432/tgo_ai_service_test",
        description="Test database URL"
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        """Parse CORS origins from string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    @field_validator("cors_allow_methods", mode="before")
    @classmethod
    def parse_cors_methods(cls, v: Union[str, List[str]]) -> List[str]:
        """Parse CORS methods from string or list."""
        if isinstance(v, str):
            return [method.strip().upper() for method in v.split(",")]
        return v

    @field_validator("cors_allow_headers", mode="before")
    @classmethod
    def parse_cors_headers(cls, v: Union[str, List[str]]) -> List[str]:
        """Parse CORS headers from string or list."""
        if isinstance(v, str):
            return [header.strip() for header in v.split(",")]
        return v

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment.lower() in ("development", "dev", "local")

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment.lower() in ("production", "prod")

    @property
    def is_testing(self) -> bool:
        """Check if running in testing environment."""
        return self.environment.lower() in ("testing", "test")

    @property
    def database_url_sync(self) -> str:
        """Get synchronous database URL for Alembic."""
        return str(self.database_url).replace("+asyncpg", "")

    def get_database_url(self, *, sync: bool = False) -> str:
        """Get database URL with optional sync mode for migrations."""
        if sync:
            return self.database_url_sync
        return str(self.database_url)


# Global settings instance
settings = Settings()
