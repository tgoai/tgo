"""
Configuration management for RAG service using Pydantic Settings v2.
"""

import os
from typing import Any, Dict, List, Optional

from pydantic import Field, PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application settings
    app_name: str = Field(default="TGO RAG Service", description="Application name")
    app_version: str = Field(default="0.1.0", description="Application version")
    environment: str = Field(default="development", description="Environment name")
    debug: bool = Field(default=False, description="Debug mode")
    log_level: str = Field(default="INFO", description="Logging level")

    # Server settings
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8082, description="Server port")
    workers: int = Field(default=1, description="Number of worker processes")
    reload: bool = Field(default=False, description="Auto-reload on code changes")

    # Database settings
    database_url: str = Field(
        default="postgresql+asyncpg://rag_user:rag_password@localhost:5432/rag_service",
        description="PostgreSQL database URL",
    )
    database_pool_size: int = Field(default=20, description="Database connection pool size")
    database_max_overflow: int = Field(default=30, description="Database max overflow connections")
    database_pool_timeout: int = Field(default=30, description="Database pool timeout in seconds")

    # Redis settings
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis URL for caching and task queue",
    )
    redis_password: Optional[str] = Field(default=None, description="Redis password")
    redis_db: int = Field(default=0, description="Redis database number")

    # Authentication settings (API key based)
    api_key_header: str = Field(default="X-API-Key", description="API key header name")
    api_key_cache_ttl: int = Field(default=300, description="API key cache TTL in seconds")

    # CORS settings
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8080"],
        description="Allowed CORS origins",
    )
    cors_allow_credentials: bool = Field(default=True, description="Allow CORS credentials")
    cors_allow_methods: List[str] = Field(
        default=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        description="Allowed CORS methods",
    )
    cors_allow_headers: List[str] = Field(
        default=["*"], description="Allowed CORS headers"
    )

    # File upload settings
    max_file_size: int = Field(default=100 * 1024 * 1024, description="Max file size in bytes (100MB)")
    upload_dir: str = Field(default="uploads", description="Upload directory path")
    allowed_file_types: List[str] = Field(
        default=[
            "application/pdf",
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "text/plain",
            "text/markdown",
            "text/html",
        ],
        description="Allowed file MIME types",
    )

    # Document processing settings
    chunk_size: int = Field(default=1000, description="Document chunk size in tokens")
    chunk_overlap: int = Field(default=200, description="Document chunk overlap in tokens")
    batch_size: int = Field(default=50, description="Batch size for processing")
    max_concurrent_tasks: int = Field(default=10, description="Max concurrent processing tasks")

    # Embedding settings
    embedding_provider: str = Field(
        default="openai",
        description="Embedding provider (openai, qwen3)"
    )
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API key")
    embedding_model: str = Field(
        default="text-embedding-ada-002", description="Embedding model name"
    )
    embedding_dimensions: int = Field(default=1536, description="Embedding vector dimensions")
    embedding_batch_size: int = Field(default=10, description="Embedding batch size (max 10 for Qwen3 compatibility)")

    # OpenAI-compatible settings
    openai_compatible_base_url: Optional[str] = Field(
        default=None,
        description="OpenAI-compatible Embeddings API base URL (e.g., http://localhost:11434/v1)"
    )

    # Qwen3-Embedding settings (Alibaba Cloud DashScope)
    qwen3_api_key: Optional[str] = Field(default=None, description="Alibaba Cloud DashScope API key")
    qwen3_base_url: str = Field(
        default="https://dashscope.aliyuncs.com/compatible-mode/v1",
        description="Qwen3-Embedding API base URL"
    )
    qwen3_model: str = Field(
        default="text-embedding-v4",
        description="Qwen3-Embedding model name"
    )
    qwen3_dimensions: int = Field(default=1536, description="Qwen3-Embedding vector dimensions")

    # Search settings
    default_search_limit: int = Field(default=20, description="Default search result limit")
    max_search_limit: int = Field(default=100, description="Maximum search result limit")
    min_similarity_score: float = Field(default=0.1, description="Minimum similarity score (filter low-quality results)")
    semantic_search_weight: float = Field(default=0.7, description="Semantic search weight in hybrid search")
    keyword_search_weight: float = Field(default=0.3, description="Keyword search weight in hybrid search")
    
    # Hybrid search settings
    rrf_k: int = Field(default=60, description="RRF fusion constant k")
    candidate_multiplier: int = Field(default=5, description="Candidate pool multiplier for hybrid search")
    
    # QA generation settings
    default_is_qa_mode: bool = Field(
        default=False,
        description="Default QA mode switch for file processing when request does not provide is_qa_mode",
    )
    qa_generation_batch_size: int = Field(default=5, description="Batch size for QA pair generation")

    # Rate limiting settings
    rate_limit_enabled: bool = Field(default=True, description="Enable rate limiting")
    rate_limit_requests: int = Field(default=100, description="Rate limit requests per window")
    rate_limit_window: int = Field(default=60, description="Rate limit window in seconds")

    # Monitoring settings
    metrics_enabled: bool = Field(default=True, description="Enable metrics collection")
    tracing_enabled: bool = Field(default=False, description="Enable distributed tracing")
    health_check_interval: int = Field(default=30, description="Health check interval in seconds")

    # Celery settings
    celery_broker_url: Optional[str] = Field(default=None, description="Celery broker URL")
    celery_result_backend: Optional[str] = Field(default=None, description="Celery result backend URL")
    celery_task_serializer: str = Field(default="json", description="Celery task serializer")
    celery_result_serializer: str = Field(default="json", description="Celery result serializer")
    celery_timezone: str = Field(default="UTC", description="Celery timezone")

    @field_validator("celery_broker_url", mode="before")
    @classmethod
    def set_celery_broker_url(cls, v: Optional[str], info) -> str:
        """Set Celery broker URL from Redis URL if not provided."""
        if v is not None:
            return v
        # Access other field values through info.data
        redis_url = info.data.get("redis_url", "redis://localhost:6379/0")
        return redis_url

    @field_validator("celery_result_backend", mode="before")
    @classmethod
    def set_celery_result_backend(cls, v: Optional[str], info) -> str:
        """Set Celery result backend URL from Redis URL if not provided."""
        if v is not None:
            return v
        # Access other field values through info.data
        redis_url = info.data.get("redis_url", "redis://localhost:6379/0")
        return redis_url

    @field_validator("upload_dir", mode="before")
    @classmethod
    def create_upload_dir(cls, v: str) -> str:
        """Create upload directory if it doesn't exist."""
        os.makedirs(v, exist_ok=True)
        return v


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get application settings instance."""
    return settings
