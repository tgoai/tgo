"""Application configuration using Pydantic Settings."""

from typing import List, Optional

from pydantic import Field, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Project Information
    PROJECT_NAME: str = Field(
        default="TGO-Tech API Service",
        description="Name of the project"
    )
    PROJECT_DESCRIPTION: str = Field(
        default="Core Business Logic Microservice",
        description="Description of the project"
    )
    PROJECT_VERSION: str = Field(
        default="0.1.0",
        description="Version of the project"
    )

    # API Configuration
    API_V1_STR: str = Field(
        default="/v1",
        description="API v1 prefix"
    )
    API_BASE_URL: str = Field(
        default="http://localhost:8000",
        description="Public-facing base URL for this TGO API service (used to construct callback URLs)"
    )

    # Security
    SECRET_KEY: str = Field(
        ...,
        description="Secret key for JWT token generation",
        min_length=32
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=30,
        description="Access token expiration time in minutes",
        gt=0
    )
    ALGORITHM: str = Field(
        default="HS256",
        description="JWT algorithm"
    )

    # Database
    DATABASE_URL: PostgresDsn = Field(
        ...,
        description="PostgreSQL database URL"
    )
    DATABASE_POOL_SIZE: int = Field(
        default=10,
        description="Database connection pool size",
        gt=0
    )
    DATABASE_MAX_OVERFLOW: int = Field(
        default=20,
        description="Database connection pool max overflow",
        gt=0
    )
    DATABASE_POOL_TIMEOUT: int = Field(
        default=30,
        description="Database connection pool timeout in seconds",
        gt=0
    )
    DATABASE_POOL_RECYCLE: int = Field(
        default=3600,
        description="Database connection pool recycle time in seconds",
        gt=0
    )

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = Field(
        default_factory=lambda: [
            "*",
        ],
        description="List of allowed CORS origins"
    )

    # Internal Service Configuration
    INTERNAL_SERVICE_HOST: str = Field(
        default="127.0.0.1",
        description="Host for internal services (127.0.0.1 for localhost only, 0.0.0.0 for all interfaces in Docker)"
    )
    INTERNAL_SERVICE_PORT: int = Field(
        default=8001,
        description="Port for internal services (no authentication required)",
        gt=0
    )
    INTERNAL_CORS_ORIGINS: List[str] = Field(
        default_factory=lambda: [
            "*",
        ],
        description="List of allowed CORS origins for internal services"
    )

    # RAG Service settings
    RAG_SERVICE_URL: str = Field(
        default="http://localhost:8001",
        description="URL of the RAG service"
    )
    RAG_SERVICE_TIMEOUT: int = Field(
        default=30,
        description="Timeout for RAG service requests in seconds"
    )
    RAG_SERVICE_API_KEY: Optional[str] = Field(
        default=None,
        description="API key for RAG service authentication (if required)"
    )

    # AI Service settings
    AI_SERVICE_URL: str = Field(
        default="http://localhost:8002",
        description="URL of the AI service"
    )
    AI_SERVICE_TIMEOUT: int = Field(
        default=120,
        description="Timeout for AI service requests in seconds"
    )
    AI_SERVICE_API_KEY: Optional[str] = Field(
        default=None,
        description="API key for AI service authentication (if required)"
    )

    # Workflow Service settings
    WORKFLOW_SERVICE_URL: str = Field(
        default="http://localhost:8004",
        description="URL of the Workflow service"
    )
    WORKFLOW_SERVICE_TIMEOUT: int = Field(
        default=60,
        description="Timeout for Workflow service requests in seconds"
    )
    WORKFLOW_SERVICE_API_KEY: Optional[str] = Field(
        default=None,
        description="API key for Workflow service authentication (if required)"
    )


    # AI Provider sync settings
    AI_PROVIDER_SYNC_RETRY_COUNT: int = Field(
        default=3,
        description="Retry count for AIProvider sync failures (excludes initial attempt)",
        ge=0,
    )
    AI_PROVIDER_SYNC_RETRY_DELAY: int = Field(
        default=2,
        description="Initial delay in seconds for exponential backoff (2,4,8,...)",
        gt=0,
    )
    AI_PROVIDER_SYNC_INTERVAL_MINUTES: int = Field(
        default=5,
        description="Periodic sync interval in minutes",
        gt=0,
    )
    AI_PROVIDER_SYNC_ENABLED: bool = Field(
        default=True,
        description="Enable periodic background sync for AIProviders",
    )

    # Project AI Config sync settings
    PROJECT_AI_CONFIG_SYNC_RETRY_COUNT: int = Field(
        default=3,
        description="Retry count for ProjectAIConfig sync failures (excludes initial attempt)",
        ge=0,
    )
    PROJECT_AI_CONFIG_SYNC_RETRY_DELAY: int = Field(
        default=2,
        description="Initial delay in seconds for ProjectAIConfig exponential backoff (2,4,8,...)",
        gt=0,
    )
    PROJECT_AI_CONFIG_SYNC_INTERVAL_MINUTES: int = Field(
        default=5,
        description="Periodic sync interval in minutes for ProjectAIConfig",
        gt=0,
    )
    PROJECT_AI_CONFIG_SYNC_ENABLED: bool = Field(
        default=True,
        description="Enable periodic background sync for ProjectAIConfig",
    )

    # Queue Processing settings (event-driven with fallback)
    QUEUE_DEFAULT_TIMEOUT_MINUTES: int = Field(
        default=60*24, # 24 hours
        description="Default queue wait timeout in minutes if not configured per project",
        gt=0,
    )
    QUEUE_CLEANUP_INTERVAL_SECONDS: int = Field(
        default=300,
        description="Interval in seconds for expired queue entries cleanup (default 5 minutes)",
        gt=0,
    )
    QUEUE_FALLBACK_INTERVAL_SECONDS: int = Field(
        default=120,
        description="Interval in seconds for fallback queue processing (default 2 minutes)",
        gt=0,
    )
    QUEUE_FALLBACK_ENABLED: bool = Field(
        default=True,
        description="Enable fallback periodic processing for missed queue entries",
    )
    QUEUE_PROCESS_BATCH_SIZE: int = Field(
        default=50,
        description="Maximum number of queue entries to process per batch",
        gt=0,
    )
    QUEUE_PROCESS_MAX_WORKERS: int = Field(
        default=5,
        description="Maximum number of concurrent workers for queue processing",
        gt=0,
    )

    # Session timeout settings
    SESSION_TIMEOUT_CHECK_ENABLED: bool = Field(
        default=True,
        description="Enable periodic check for timed-out sessions",
    )
    SESSION_TIMEOUT_CHECK_INTERVAL_SECONDS: int = Field(
        default=300,
        description="Interval in seconds between session timeout checks (default 5 minutes)",
        gt=0,
    )
    SESSION_DEFAULT_TIMEOUT_HOURS: int = Field(
        default=48,
        description="Default session timeout in hours if not configured in VisitorAssignmentRule",
        gt=0,
    )
    SESSION_TIMEOUT_BATCH_SIZE: int = Field(
        default=50,
        description="Number of timed-out sessions to process per batch",
        gt=0,
    )

    # Visitor Assignment Rule defaults
    ASSIGNMENT_RULE_DEFAULT_TIMEZONE: str = Field(
        default="Asia/Shanghai",
        description="Default timezone for visitor assignment rules",
    )
    ASSIGNMENT_RULE_DEFAULT_WEEKDAYS: str = Field(
        default="1,2,3,4,5,6,7",
        description="Default service weekdays (comma-separated, 1=Monday to 7=Sunday)",
    )
    ASSIGNMENT_RULE_DEFAULT_START_TIME: str = Field(
        default="00:00",
        description="Default service start time (HH:MM format)",
    )
    ASSIGNMENT_RULE_DEFAULT_END_TIME: str = Field(
        default="23:59",
        description="Default service end time (HH:MM format, 23:59 for end of day)",
    )
    ASSIGNMENT_RULE_DEFAULT_MAX_CONCURRENT_CHATS: int = Field(
        default=50,
        description="Default maximum concurrent chats per staff",
        gt=0,
    )
    ASSIGNMENT_RULE_DEFAULT_AUTO_CLOSE_HOURS: int = Field(
        default=48,
        description="Default auto-close hours for sessions",
        gt=0,
    )

    # Platform Service settings (TGO Platform Service)
    PLATFORM_SERVICE_URL: str = Field(
        default="http://localhost:8003",
        description="URL of the TGO Platform Service",
    )
    PLATFORM_SERVICE_TIMEOUT: int = Field(
        default=15,
        description="Timeout for Platform Service requests in seconds",
        gt=0,
    )
    PLATFORM_SERVICE_API_KEY: Optional[str] = Field(
        default=None,
        description="API key for Platform Service authentication (if required)",
    )

    # Platform sync monitor settings
    PLATFORM_SYNC_RETRY_INTERVAL_SECONDS: int = Field(
        default=15,
        description="Base retry interval for platform sync (exponential backoff)",
        gt=1,
    )
    PLATFORM_SYNC_BATCH_LIMIT: int = Field(
        default=50,
        description="Max number of platforms to scan per retry cycle",
        gt=0,
    )

    # WuKongIM Service settings
    WUKONGIM_SERVICE_URL: str = Field(
        default="http://localhost:5001",
        description="URL of the WuKongIM service"
    )
    WUKONGIM_SERVICE_TIMEOUT: int = Field(
        default=10,
        description="Timeout for WuKongIM service requests in seconds"
    )
    WUKONGIM_ENABLED: bool = Field(
        default=True,
        description="Enable WuKongIM integration for instant messaging"
    )
    WUKONGIM_DEVICE_FLAG: int = Field(
        default=1,
        description="WuKongIM device flag (0=app, 1=web, 2=pc)"
    )
    WUKONGIM_DEVICE_LEVEL: int = Field(
        default=1,
        description="WuKongIM device level (0=secondary, 1=primary)"
    )

    # Logging
    LOG_LEVEL: str = Field(
        default="INFO",
        description="Logging level"
    )
    LOG_FORMAT: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Logging format"
    )

    # Redis (for caching and sessions)
    REDIS_URL: Optional[str] = Field(
        default=None,
        description="Redis URL for caching and sessions"
    )

    # GeoIP settings (for IP to location lookup)
    # Supports two providers: geoip2 (MaxMind GeoLite2) and ip2region
    GEOIP_PROVIDER: str = Field(
        default="ip2region",
        description="GeoIP provider: 'geoip2' (MaxMind) or 'ip2region' (lionsoul2014)"
    )
    GEOIP_DATABASE_PATH: Optional[str] = Field(
        default="resources/geoip",
        description="Path to GeoLite2-City.mmdb (geoip2) or ip2region directory/file (ip2region)"
    )
    GEOIP_ENABLED: bool = Field(
        default=True,
        description="Enable IP geolocation lookup (requires GEOIP_DATABASE_PATH)"
    )

    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = Field(
        default=True,
        description="Enable rate limiting"
    )
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = Field(
        default=100,
        description="Rate limit requests per minute",
        gt=0
    )

    # Pagination
    DEFAULT_PAGE_SIZE: int = Field(
        default=20,
        description="Default page size for paginated responses",
        gt=0,
        le=100
    )
    MAX_PAGE_SIZE: int = Field(
        default=100,
        description="Maximum page size for paginated responses",
        gt=0
    )

    # Visitor online status sync settings
    VISITOR_ONLINE_SYNC_ENABLED: bool = Field(
        default=True,
        description="Enable periodic sync of visitor online status with WuKongIM",
    )
    VISITOR_ONLINE_SYNC_INTERVAL_SECONDS: int = Field(
        default=60,
        description="Interval in seconds for visitor online status sync (default 1 minute)",
        gt=0,
    )
    VISITOR_ONLINE_SYNC_BATCH_SIZE: int = Field(
        default=100,
        description="Number of visitors to check per batch in online status sync",
        gt=0,
    )

    # Unknown Platform Fallback
    UNKNOWN_PLATFORM_ID: str = Field(
        default="00000000-0000-0000-0000-000000000000",
        description="UUID for the unknown/fallback platform when platform data is missing"
    )
    UNKNOWN_PLATFORM_NAME: str = Field(
        default="未知平台",
        description="Display name for the unknown/fallback platform"
    )

    # File Upload (legacy)
    MAX_FILE_SIZE: int = Field(
        default=10 * 1024 * 1024,  # 10MB
        description="Maximum file upload size in bytes",
        gt=0
    )
    ALLOWED_FILE_TYPES: List[str] = Field(
        # default_factory=lambda: [
        #     "image/jpeg",
        #     "image/png",
        #     "image/gif",
        #     "image/webp",
        #     "application/pdf",
        #     "text/plain",
        # ],
        default_factory=lambda: [],
        description="Allowed file MIME types"
    )

    # Chat Upload Settings (preferred)
    UPLOAD_BASE_DIR: str = Field(
        default="./uploads",
        description="Base directory for file uploads",
    )
    MAX_UPLOAD_SIZE_MB: int = Field(
        default=10,
        description="Maximum upload file size in MB",
        gt=0,
    )
    ALLOWED_UPLOAD_EXTENSIONS: List[str] = Field(
        # default_factory=lambda: [
        #     "jpg", "jpeg", "png", "gif", "webp",
        #     "pdf", "doc", "docx", "txt", "zip",
        # ],
        default_factory=lambda: [],
        description="Allowed file extensions for uploads",
    )


    # Platform Logo Upload Settings
    PLATFORM_LOGO_UPLOAD_DIR: str = Field(
        default="./uploads/platform_logos",
        description="Base directory for platform logo uploads",
    )
    PLATFORM_LOGO_MAX_SIZE_MB: int = Field(
        default=5,
        description="Maximum size for platform logo uploads in MB",
        gt=0,
    )
    PLATFORM_LOGO_ALLOWED_TYPES: List[str] = Field(
        default_factory=lambda: [
            "image/png",
            "image/jpeg",
            "image/jpg",
            "image/svg+xml",
            "image/gif",
        ],
        description="Allowed MIME types for platform logo uploads",
    )

    # Plugin Runtime Service Settings
    PLUGIN_ENABLED: bool = Field(
        default=True,
        description="Enable plugin system",
    )
    PLUGIN_RUNTIME_URL: str = Field(
        default="http://localhost:8090",
        description="URL of the tgo-plugin-runtime service",
    )
    PLUGIN_RUNTIME_TIMEOUT: int = Field(
        default=35,
        description="Timeout in seconds for plugin runtime requests",
        gt=0,
    )

    # Environment
    ENVIRONMENT: str = Field(
        default="development",
        description="Application environment"
    )
    DEBUG: bool = Field(
        default=False,
        description="Debug mode"
    )

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.ENVIRONMENT.lower() in ("development", "dev", "local")

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.ENVIRONMENT.lower() in ("production", "prod")

    @property
    def database_url_sync(self) -> str:
        """Get synchronous database URL (force psycopg2 driver)."""
        url = str(self.DATABASE_URL)
        if "postgresql+asyncpg://" in url:
            return url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
        if "postgresql+psycopg2://" in url:
            return url
        if "postgresql://" in url:
            return url.replace("postgresql://", "postgresql+psycopg2://")
        # Fallback: enforce psycopg2
        scheme, rest = url.split("://", 1)
        return f"postgresql+psycopg2://{rest}"

    @property
    def database_url_async(self) -> str:
        """Get asynchronous database URL (force asyncpg driver)."""
        url = str(self.DATABASE_URL)
        if "postgresql+asyncpg://" in url:
            return url
        if "postgresql+psycopg2://" in url:
            return url.replace("postgresql+psycopg2://", "postgresql+asyncpg://")
        if "postgresql://" in url:
            return url.replace("postgresql://", "postgresql+asyncpg://")
        # Fallback: enforce asyncpg
        scheme, rest = url.split("://", 1)
        return f"postgresql+asyncpg://{rest}"


# Create global settings instance
settings = Settings()
