"""
Authentication dependencies for API key-based multi-tenant access.
"""

from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..database import get_db_session_dependency
from ..logging_config import get_logger
from ..models.projects import Project
from .models import ApiKeyValidationResult, ProjectAccess
from .security import SecurityAuditLogger

logger = get_logger(__name__)

# Define the API key security scheme for OpenAPI documentation
api_key_header = APIKeyHeader(
    name="X-API-Key",
    description="API key for project authentication. Each project has a unique API key that provides access to project-scoped resources."
)


async def get_api_key_from_header(
    api_key: str = Depends(api_key_header)
) -> str:
    """
    Extract API key from request header using FastAPI security scheme.

    Args:
        api_key: API key from X-API-Key header (automatically extracted by FastAPI)

    Returns:
        API key string

    Raises:
        HTTPException: If API key is missing (handled automatically by FastAPI)
    """
    if not api_key:
        logger.warning("API key missing from request")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required. Please provide X-API-Key header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return api_key


async def validate_api_key(
    api_key: str,
    db: AsyncSession,
    request: Optional[Request] = None
) -> ApiKeyValidationResult:
    """
    Validate API key against the projects table with security logging.

    Args:
        api_key: API key to validate
        db: Database session
        request: FastAPI request object for audit logging

    Returns:
        ApiKeyValidationResult with validation status and project info
    """
    api_key_prefix = api_key[:8] if len(api_key) >= 8 else api_key
    ip_address = request.client.host if request and request.client else None
    user_agent = request.headers.get("user-agent") if request else None

    try:
        # Query project by API key
        query = select(Project).where(
            Project.api_key == api_key,
            Project.deleted_at.is_(None)
        )

        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            # Log security violation
            SecurityAuditLogger.log_api_key_validation(
                api_key_prefix=api_key_prefix,
                project_id=None,
                success=False,
                ip_address=ip_address,
                user_agent=user_agent
            )
            SecurityAuditLogger.log_security_violation(
                violation_type="invalid_api_key",
                details=f"Invalid API key attempted: {api_key_prefix}...",
                api_key_prefix=api_key_prefix,
                ip_address=ip_address
            )

            return ApiKeyValidationResult(
                is_valid=False,
                error="Invalid API key"
            )

        # Create project access info
        project_access = ProjectAccess(
            project_id=project.id,
            api_key=project.api_key,
            name=project.name,
            is_active=True
        )

        # Log successful validation
        SecurityAuditLogger.log_api_key_validation(
            api_key_prefix=api_key_prefix,
            project_id=project.id,
            success=True,
            ip_address=ip_address,
            user_agent=user_agent
        )

        return ApiKeyValidationResult(
            is_valid=True,
            project=project_access
        )

    except Exception as e:
        logger.error("Error validating API key", error=str(e), api_key_prefix=api_key_prefix)
        SecurityAuditLogger.log_security_violation(
            violation_type="api_key_validation_error",
            details=f"API key validation failed: {str(e)}",
            api_key_prefix=api_key_prefix,
            ip_address=ip_address
        )

        return ApiKeyValidationResult(
            is_valid=False,
            error="API key validation failed"
        )


async def get_current_project(
    request: Request,
    api_key: str = Depends(get_api_key_from_header),
    db: AsyncSession = Depends(get_db_session_dependency)
) -> ProjectAccess:
    """
    Get current project from API key authentication with security logging.

    This dependency validates the API key and returns the associated project.
    All authenticated endpoints should use this dependency to ensure proper
    multi-tenant data isolation.

    Args:
        request: FastAPI request object for audit logging
        api_key: API key from header
        db: Database session

    Returns:
        ProjectAccess with project information

    Raises:
        HTTPException: If API key is invalid or project not found
    """
    validation_result = await validate_api_key(api_key, db, request)

    if not validation_result.is_valid:
        logger.warning("Authentication failed", error=validation_result.error)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=validation_result.error or "Authentication failed",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return validation_result.project


async def require_api_key(
    project: ProjectAccess = Depends(get_current_project)
) -> ProjectAccess:
    """
    Require valid API key authentication.
    
    This is an alias for get_current_project that makes the intent clearer
    when used in endpoints that require authentication.
    
    Args:
        project: Project from get_current_project dependency
        
    Returns:
        ProjectAccess with project information
    """
    return project


def get_project_id(
    project: ProjectAccess = Depends(get_current_project)
) -> UUID:
    """
    Extract project ID from authenticated project.
    
    This dependency provides just the project ID for use in database queries
    and other operations that need project-scoped access.
    
    Args:
        project: Project from get_current_project dependency
        
    Returns:
        Project UUID
    """
    return project.project_id
