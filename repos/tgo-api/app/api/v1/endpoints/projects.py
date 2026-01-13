"""Project endpoints."""

from datetime import datetime
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.logging import get_logger
from app.core.security import generate_api_key, get_current_active_user
from app.models import Project, Staff
from app.schemas import (
    ProjectCreate,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdate,
    ProjectAIConfigUpdate,
    ProjectAIConfigResponse,
)
from app.api.common_responses import LIST_RESPONSES
from app.services.project_ai_config_sync import sync_config_with_retry_and_update

logger = get_logger("endpoints.projects")
router = APIRouter()


@router.get(
    "",
    response_model=ProjectListResponse,
    responses=LIST_RESPONSES
)
async def list_projects(
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user),
) -> ProjectListResponse:
    """
    List projects.

    Retrieve a list of projects. This endpoint is typically used by system administrators
    to manage multiple tenant projects.
    """
    logger.info(f"User {current_user.username} listing projects")

    # Query projects (non-deleted)
    projects = db.query(Project).filter(
        Project.deleted_at.is_(None)
    ).all()

    project_responses = [ProjectResponse.model_validate(project) for project in projects]

    return ProjectListResponse(data=project_responses)


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_data: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user),
) -> ProjectResponse:
    """
    Create project.

    Create a new project (tenant). This automatically generates an API key for the project
    and publishes a project creation event for AI Service synchronization.
    """
    logger.info(f"User {current_user.username} creating project: {project_data.name}")

    # Generate API key
    api_key = generate_api_key()

    # Create project
    project = Project(
        name=project_data.name,
        api_key=api_key,
    )

    db.add(project)
    db.commit()
    db.refresh(project)

    logger.info(f"Created project {project.id} with name: {project.name}")

    return ProjectResponse.model_validate(project)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: UUID,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user),
) -> ProjectResponse:
    """Get project details."""
    logger.info(f"User {current_user.username} getting project: {project_id}")

    project = db.query(Project).filter(
        Project.id == project_id,
        Project.deleted_at.is_(None)
    ).first()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    return ProjectResponse.model_validate(project)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: UUID,
    project_data: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user),
) -> ProjectResponse:
    """
    Update project.

    Update project information. This publishes a project update event
    for AI Service synchronization.
    """
    logger.info(f"User {current_user.username} updating project: {project_id}")

    project = db.query(Project).filter(
        Project.id == project_id,
        Project.deleted_at.is_(None)
    ).first()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    # Update fields
    update_data = project_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)

    project.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(project)

    logger.info(f"Updated project {project.id}")

    return ProjectResponse.model_validate(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: UUID,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user),
) -> None:
    """
    Delete project (soft delete).

    Soft delete a project. This publishes a project deletion event
    for AI Service synchronization and cleanup.
    """
    logger.info(f"User {current_user.username} deleting project: {project_id}")

    project = db.query(Project).filter(
        Project.id == project_id,
        Project.deleted_at.is_(None)
    ).first()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    # Soft delete
    project.deleted_at = datetime.utcnow()
    project.updated_at = datetime.utcnow()

    db.commit()

    logger.info(f"Deleted project {project.id}")

    return None


@router.get("/{project_id}/ai-config", response_model=ProjectAIConfigResponse)
async def get_project_ai_config(
    project_id: UUID,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user),
) -> ProjectAIConfigResponse:
    """Get default AI model configuration for a project.

    If a record does not exist yet, create an empty configuration and return it (HTTP 200).
    Validates that referenced provider IDs exist and are active; if not, returns None for those fields.
    """
    # Only allow accessing own project's config
    if current_user.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    project = db.query(Project).filter(Project.id == project_id, Project.deleted_at.is_(None)).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    from app.models import ProjectAIConfig, AIProvider  # local import to avoid circular

    cfg = (
        db.query(ProjectAIConfig)
        .filter(ProjectAIConfig.project_id == project_id, ProjectAIConfig.deleted_at.is_(None))
        .first()
    )
    if not cfg:
        # Auto-create empty config
        cfg = ProjectAIConfig(project_id=project_id)
        db.add(cfg)
        db.commit()
        db.refresh(cfg)

    # Build response from config
    response_data = {
        "id": cfg.id,
        "project_id": cfg.project_id,
        "default_chat_provider_id": cfg.default_chat_provider_id,
        "default_chat_model": cfg.default_chat_model,
        "default_embedding_provider_id": cfg.default_embedding_provider_id,
        "default_embedding_model": cfg.default_embedding_model,
        "created_at": cfg.created_at,
        "updated_at": cfg.updated_at,
        "deleted_at": cfg.deleted_at,
        "last_synced_at": cfg.last_synced_at,
        "sync_status": cfg.sync_status,
        "sync_error": cfg.sync_error,
    }

    # Collect provider IDs to validate in a single query
    provider_ids_to_check = []
    if cfg.default_chat_provider_id:
        provider_ids_to_check.append(cfg.default_chat_provider_id)
    if cfg.default_embedding_provider_id:
        provider_ids_to_check.append(cfg.default_embedding_provider_id)

    # Query all referenced providers at once (avoid N+1)
    valid_provider_ids = set()
    if provider_ids_to_check:
        valid_providers = (
            db.query(AIProvider.id)
            .filter(
                AIProvider.id.in_(provider_ids_to_check),
                AIProvider.project_id == project_id,
                AIProvider.is_active == True,  # noqa: E712
                AIProvider.deleted_at.is_(None),
            )
            .all()
        )
        valid_provider_ids = {p.id for p in valid_providers}

    # Validate chat provider
    if cfg.default_chat_provider_id and cfg.default_chat_provider_id not in valid_provider_ids:
        logger.warning(
            "Invalid or inactive default_chat_provider_id detected",
            extra={
                "project_id": str(project_id),
                "default_chat_provider_id": str(cfg.default_chat_provider_id),
            }
        )
        response_data["default_chat_provider_id"] = None
        response_data["default_chat_model"] = None

    # Validate embedding provider
    if cfg.default_embedding_provider_id and cfg.default_embedding_provider_id not in valid_provider_ids:
        logger.warning(
            "Invalid or inactive default_embedding_provider_id detected",
            extra={
                "project_id": str(project_id),
                "default_embedding_provider_id": str(cfg.default_embedding_provider_id),
            }
        )
        response_data["default_embedding_provider_id"] = None
        response_data["default_embedding_model"] = None

    return ProjectAIConfigResponse.model_validate(response_data)


@router.put("/{project_id}/ai-config", response_model=ProjectAIConfigResponse)
async def upsert_project_ai_config(
    project_id: UUID,
    payload: ProjectAIConfigUpdate,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user),
) -> ProjectAIConfigResponse:
    """Upsert default AI model configuration for a project.

    - Validates provider IDs belong to the same project
    - Optionally validates model is in provider.available_models when both provided
    """
    if current_user.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    project = db.query(Project).filter(Project.id == project_id, Project.deleted_at.is_(None)).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    from app.models import ProjectAIConfig, AIProvider  # local import to avoid circular

    data = payload.model_dump(exclude_unset=True)

    # Validate providers
    chat_pid = data.get("default_chat_provider_id")
    emb_pid = data.get("default_embedding_provider_id")

    def _validate_provider(provider_id: UUID, model_key: str | None) -> None:
        prov = (
            db.query(AIProvider)
            .filter(
                AIProvider.id == provider_id,
                AIProvider.project_id == project_id,
                AIProvider.deleted_at.is_(None),
            )
            .first()
        )
        if not prov:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid provider for this project")
        if model_key:
            model_value = data.get(model_key)
            # Fetch available models from relation
            available_models = [m.model_id for m in prov.models if m.deleted_at is None]
            if model_value and available_models and model_value not in available_models:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Model '{model_value}' not in selected provider's available models",
                )

    if chat_pid:
        _validate_provider(chat_pid, "default_chat_model")
    if emb_pid:
        _validate_provider(emb_pid, "default_embedding_model")

    cfg = (
        db.query(ProjectAIConfig)
        .filter(ProjectAIConfig.project_id == project_id, ProjectAIConfig.deleted_at.is_(None))
        .first()
    )

    if cfg:
        for k, v in data.items():
            setattr(cfg, k, v)
        cfg.updated_at = datetime.utcnow()
    else:
        cfg = ProjectAIConfig(project_id=project_id, **data)
        db.add(cfg)

    db.commit()
    db.refresh(cfg)

    # Attempt to sync to AI service with retry (non-blocking for main flow)
    try:
        await sync_config_with_retry_and_update(db, cfg)
    except Exception as e:
        logger.warning("ProjectAIConfig sync after upsert failed", extra={"project_id": str(project_id), "error": str(e)})

    return ProjectAIConfigResponse.model_validate(cfg)


@router.post("/{project_id}/ai-config/sync", response_model=ProjectAIConfigResponse)
async def sync_project_ai_config_now(
    project_id: UUID,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user),
) -> ProjectAIConfigResponse:
    """Manually trigger sync of a project's AI config to AI service."""
    if current_user.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    from app.models import ProjectAIConfig  # local import to avoid circular

    cfg = (
        db.query(ProjectAIConfig)
        .filter(ProjectAIConfig.project_id == project_id, ProjectAIConfig.deleted_at.is_(None))
        .first()
    )
    if not cfg:
        # Auto-create empty config then sync
        cfg = ProjectAIConfig(project_id=project_id)
        db.add(cfg)
        db.commit()
        db.refresh(cfg)

    try:
        await sync_config_with_retry_and_update(db, cfg)
    except Exception as e:
        logger.warning("ProjectAIConfig manual sync failed", extra={"project_id": str(project_id), "error": str(e)})

    return ProjectAIConfigResponse.model_validate(cfg)
