"""FastAPI dependencies for authentication and database access."""

import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncIterator, Optional
from functools import lru_cache

from fastapi import Depends, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.api_key import get_project_from_api_key
from app.auth.jwt import get_project_from_jwt
from app.config import settings
from app.database import AsyncSessionLocal, get_db
from app.exceptions import AuthenticationError
from app.models.project import Project
from app.runtime.supervisor.application.service import SupervisorRuntimeService
from app.runtime.tools.executor.service import ToolsRuntimeService
from app.services.agent_service import AgentService
from app.services.llm_provider_service import LLMProviderService

# Security scheme for JWT tokens
security = HTTPBearer(auto_error=False)


@asynccontextmanager
async def _get_session_from_app(request: Request) -> AsyncIterator[AsyncSession]:
    """Acquire a DB session respecting dependency overrides on the FastAPI app."""

    dependency = request.app.dependency_overrides.get(get_db, get_db)
    generator = dependency()
    try:
        session = await generator.__anext__()
    except StopAsyncIteration as exc:  # pragma: no cover - defensive
        raise RuntimeError("Database dependency did not yield a session") from exc
    try:
        yield session  # type: ignore[generator-type]
    finally:
        await generator.aclose()


async def get_current_project(
    request: Request,
    authorization: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Project:
    """
    Get the current project from either JWT token or API key.

    Supports two authentication methods:
    1. JWT token in Authorization header: Bearer <token>
    2. API key in X-API-Key header

    Args:
        request: FastAPI request object
        authorization: JWT authorization credentials
        db: Database session

    Returns:
        Authenticated project

    Raises:
        HTTPException: If authentication fails
    """
    # Try JWT authentication first
    if authorization and authorization.credentials:
        async with _get_session_from_app(request) as session:
            return await get_project_from_jwt(authorization.credentials, session)

    # Try API key authentication
    x_api_key = request.headers.get("X-API-Key")
    if x_api_key:
        async with _get_session_from_app(request) as session:
            return await get_project_from_api_key(x_api_key, session)

    # No authentication provided
    raise AuthenticationError("No authentication provided")


async def get_current_project_id(
    project: Project = Depends(get_current_project),
) -> uuid.UUID:
    """
    Get the current project ID.
    
    Args:
        project: Current authenticated project
        
    Returns:
        Project UUID
    """
    return project.id


def get_pagination_params(
    limit: int = Query(default=20, ge=1, le=100, description="Number of items to return"),
    offset: int = Query(default=0, ge=0, description="Number of items to skip"),
) -> tuple[int, int]:
    """
    Get pagination parameters with validation.

    Args:
        limit: Number of items to return (1-100)
        offset: Number of items to skip (>=0)

    Returns:
        Tuple of (limit, offset)
    """
    return limit, offset


def get_agent_service(db: AsyncSession = Depends(get_db)) -> AgentService:
    """
    Get AgentService instance.

    Args:
        db: Database session

    Returns:
        AgentService instance
    """
    return AgentService(db)


def get_llm_provider_service(db: AsyncSession = Depends(get_db)) -> LLMProviderService:
    """Get LLMProviderService instance."""
    return LLMProviderService(db)


@lru_cache
def get_tools_runtime_service() -> ToolsRuntimeService:
    """获取工具智能体运行时服务实例 (singleton)."""
    return ToolsRuntimeService(runtime_settings=settings.tools_runtime)


@lru_cache
def get_supervisor_runtime_service() -> SupervisorRuntimeService:
    """获取Supervisor运行时服务实例 (singleton)."""
    return SupervisorRuntimeService(
        session_factory=AsyncSessionLocal,
        tools_runtime_service=get_tools_runtime_service(),
    )
