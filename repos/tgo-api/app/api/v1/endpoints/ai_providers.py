"""AI Provider (LLM Provider) management endpoints."""

from datetime import datetime
from typing import Optional
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import or_, and_, select, exists, func
from sqlalchemy.orm import Session

from app.api.common_responses import CREATE_RESPONSES, CRUD_RESPONSES, LIST_RESPONSES, UPDATE_RESPONSES, DELETE_RESPONSES
from app.core.database import get_db
from app.core.logging import get_logger
from app.core.security import get_current_active_user
from app.models import AIProvider, Staff
from app.schemas import (
    AIProviderCreate,
    AIProviderListParams,
    AIProviderListResponse,
    AIProviderResponse,
    AIProviderUpdate,
)
from app.utils.crypto import decrypt_str, encrypt_str, mask_secret
from app.services.ai_provider_sync import sync_provider_with_retry_and_update

logger = get_logger("endpoints.ai_providers")


def _filter_models_by_type(models: Optional[list[str]], model_type: Optional[str]) -> list[str]:
    ms = list(models or [])
    if not model_type:
        return ms
    
    def is_embedding(m: str) -> bool:
        # 兼容商店模型：如果是 st- 开头，目前我们无法仅通过 ID 判断
        # 但如果是普通模型，通常 ID 包含 embedding
        return "embedding" in m.lower()

    if model_type == "embedding":
        return [m for m in ms if isinstance(m, str) and is_embedding(m)]
    if model_type == "chat":
        return [m for m in ms if isinstance(m, str) and not is_embedding(m)]
    return ms



def _to_response(item: AIProvider, model_type: Optional[str] = None) -> AIProviderResponse:
    plain = decrypt_str(item.api_key) if item.api_key else None
    masked = mask_secret(plain)
    
    # Derive available_models from related AIModel rows
    # IMPORTANT: Explicitly convert everything to basic types to avoid Pydantic trying to serialize ORM objects
    model_ids = []
    if item.models:
        for m in item.models:
            if m.deleted_at is None:
                model_ids.append(str(m.model_id))
    
    models = _filter_models_by_type(model_ids, model_type)
    
    # Build a clean data dict with ONLY basic Python types
    data = {
        "id": item.id,
        "project_id": item.project_id,
        "provider": str(item.provider),
        "name": str(item.name),
        "api_base_url": str(item.api_base_url) if item.api_base_url else None,
        "available_models": [str(m) for m in models],
        "default_model": str(item.default_model) if item.default_model else None,
        "config": dict(item.config) if item.config else None,
        "is_active": bool(item.is_active),
        "created_at": item.created_at,
        "updated_at": item.updated_at,
        "deleted_at": item.deleted_at,
        "has_api_key": bool(item.api_key),
        "api_key_masked": masked,
        "last_synced_at": item.last_synced_at,
        "sync_status": item.sync_status,
        "sync_error": item.sync_error,
    }
    
    # Validate using the clean dict
    return AIProviderResponse.model_validate(data)



def _normalize_base(base: Optional[str]) -> Optional[str]:
    if not base:
        return None
    return base.rstrip("/")


def _build_test_request(item: AIProvider, plain_key: Optional[str]) -> tuple[str, str, dict]:
    """Return (method, url, headers) for a lightweight connectivity check.
    Raises HTTPException on unsupported provider or missing key.
    """
    if not plain_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="API key is not set for this provider")

    provider = (item.provider or "").lower()
    base = _normalize_base(item.api_base_url)
    headers: dict[str, str] = {}

    if provider in ("openai", "gpt", "gpt-4o", "oai"):
        base = base or "https://api.openai.com/v1"
        url = f"{base}/models"
        headers = {"Authorization": f"Bearer {plain_key}"}
        return ("GET", url, headers)

    if provider in ("anthropic", "claude"):
        base = base or "https://api.anthropic.com"
        url = f"{base}/v1/models"
        version = (item.config or {}).get("anthropic_version") or "2023-06-01"
        headers = {"x-api-key": plain_key, "anthropic-version": version}
        return ("GET", url, headers)

    if provider in ("dashscope", "ali", "aliyun"):
        # Prefer OpenAI-compatible endpoint if base not provided
        if base and "compatible-mode" in base:
            compat = base
        else:
            compat = (base or "https://dashscope.aliyuncs.com") + "/compatible-mode/v1"
        url = f"{compat}/models"
        headers = {"Authorization": f"Bearer {plain_key}"}
        return ("GET", url, headers)

    if provider in ("azure_openai", "azure-openai", "azure"):
        if not base:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="api_base_url is required for Azure OpenAI")
        root = base if "/openai" in base else f"{base}/openai"
        api_version = (item.config or {}).get("api_version") or "2023-12-01-preview"
        url = f"{root}/deployments?api-version={api_version}"
        headers = {"api-key": plain_key}
        return ("GET", url, headers)

    # Fallback: try OpenAI-compatible with provided base
    if base:
        url = f"{base}/models"
        headers = {"Authorization": f"Bearer {plain_key}"}
        return ("GET", url, headers)

    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unsupported provider: {item.provider}")

router = APIRouter()


@router.get("", response_model=AIProviderListResponse, responses=LIST_RESPONSES)
async def list_ai_providers(
    params: AIProviderListParams = Depends(),
    model_type: Optional[str] = Query(None, pattern="^(chat|embedding)$"),
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user),
) -> AIProviderListResponse:
    """List AI providers with pagination and optional filtering/search."""

    query = db.query(AIProvider).filter(
        AIProvider.project_id == current_user.project_id,
        AIProvider.deleted_at.is_(None),
    )

    if params.provider:
        query = query.filter(AIProvider.provider == params.provider)
    if params.is_active is not None:
        query = query.filter(AIProvider.is_active == params.is_active)
    if params.search:
        like = f"%{params.search}%"
        query = query.filter(
            or_(
                AIProvider.name.ilike(like),
                AIProvider.default_model.ilike(like),
            )
        )

    # Optional filter by inferred model_type from related AIModel rows
    if model_type:
        from app.models import AIModel
        if model_type == "embedding":
            query = query.filter(
                or_(
                    ~AIProvider.models.any(),
                    AIProvider.models.any(and_(AIModel.model_type == "embedding", AIModel.deleted_at.is_(None)))
                )
            )
        elif model_type == "chat":
            query = query.filter(
                or_(
                    ~AIProvider.models.any(),
                    AIProvider.models.any(and_(AIModel.model_type == "chat", AIModel.deleted_at.is_(None)))
                )
            )


    total = query.count()
    items = (
        query.order_by(AIProvider.created_at.desc())
        .offset(params.offset)
        .limit(params.limit)
        .all()
    )

    data = [_to_response(x, model_type) for x in items]
    return AIProviderListResponse(
        data=data,
        pagination={
            "total": total,
            "limit": params.limit,
            "offset": params.offset,
            "has_next": params.offset + params.limit < total,
            "has_prev": params.offset > 0,
        },
    )


@router.post(
    "",
    response_model=AIProviderResponse,
    status_code=status.HTTP_201_CREATED,
    responses=CREATE_RESPONSES,
)
async def create_ai_provider(
    payload: AIProviderCreate,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user),
) -> AIProviderResponse:
    """Create a new AI provider configuration for current project."""


    # Validate default_model within available_models if provided
    if payload.default_model and payload.available_models and payload.default_model not in payload.available_models:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="default_model must be in available_models")

    item = AIProvider(
        project_id=current_user.project_id,
        provider=payload.provider,
        name=payload.name,
        api_key=encrypt_str(payload.api_key),
        api_base_url=payload.api_base_url,
        default_model=payload.default_model,
        config=payload.config,
        is_active=payload.is_active,
    )

    # Sync available_models to AIModel records
    from app.models import AIModel
    if payload.available_models:
        for mid in payload.available_models:
            model_type = "embedding" if "embedding" in mid.lower() else "chat"
            m = AIModel(
                provider_id=item.id,
                provider=payload.provider,
                model_id=mid,
                model_name=mid,
                model_type=model_type,
                is_active=True
            )
            item.models.append(m)

    db.add(item)
    db.commit()
    db.refresh(item)

    logger.info("Created AIProvider", extra={"id": str(item.id), "project_id": str(item.project_id)})

    # Attempt to sync to tgo-ai with retry (non-blocking for main flow)
    try:
        await sync_provider_with_retry_and_update(db, item)
    except Exception as e:
        logger.warning("AIProvider sync after create failed", extra={"id": str(item.id), "error": str(e)})

    return _to_response(item)


@router.get("/{provider_id}", response_model=AIProviderResponse, responses=CRUD_RESPONSES)
async def get_ai_provider(
    provider_id: UUID,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user),
) -> AIProviderResponse:
    """Get a single AI provider by ID."""

    item = (
        db.query(AIProvider)
        .filter(
            AIProvider.id == provider_id,
            AIProvider.project_id == current_user.project_id,
            AIProvider.deleted_at.is_(None),
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI provider not found")
    return _to_response(item)


@router.patch("/{provider_id}", response_model=AIProviderResponse, responses=UPDATE_RESPONSES)
async def update_ai_provider(
    provider_id: UUID,
    payload: AIProviderUpdate,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user),
) -> AIProviderResponse:
    """Update an AI provider configuration."""

    item = (
        db.query(AIProvider)
        .filter(
            AIProvider.id == provider_id,
            AIProvider.project_id == current_user.project_id,
            AIProvider.deleted_at.is_(None),
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI provider not found")

    data = payload.model_dump(exclude_unset=True)

    # If changing name, ensure uniqueness within project
    if "name" in data and data["name"] != item.name:
        exists = (
            db.query(AIProvider)
            .filter(
                AIProvider.project_id == current_user.project_id,
                AIProvider.name == data["name"],
                AIProvider.deleted_at.is_(None),
                AIProvider.id != item.id,
            )
            .first()
        )
        if exists:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Provider name already exists")

    # Validate default_model within available_models if both provided
    current_model_ids = [m.model_id for m in item.models if m.deleted_at is None]
    new_available = data.get("available_models", current_model_ids)
    new_default = data.get("default_model", item.default_model)
    if new_default and new_available and new_default not in new_available:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="default_model must be in available_models")

    # Sync available_models to AIModel records
    if "available_models" in data:
        new_mids = data.pop("available_models") or []
        from app.models import AIModel
        current_models = {m.model_id: m for m in item.models if m.deleted_at is None}
        
        # Add new models
        for mid in new_mids:
            if mid not in current_models:
                model_type = "embedding" if "embedding" in mid.lower() else "chat"
                m = AIModel(
                    provider_id=item.id,
                    provider=item.provider,
                    model_id=mid,
                    model_name=mid,
                    model_type=model_type,
                    is_active=True
                )
                db.add(m)
        
        # Remove old models
        for mid, m in current_models.items():
            if mid not in new_mids:
                db.delete(m)

    # Handle secret update with encryption (ignore empty to keep existing)
    if "api_key" in data:
        raw = data.pop("api_key")
        if raw is not None and raw != "":
            item.api_key = encrypt_str(raw)

    for field, value in data.items():
        setattr(item, field, value)
    item.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(item)

    logger.info("Updated AIProvider", extra={"id": str(item.id)})

    # Attempt to sync to tgo-ai (non-blocking)
    try:
        await sync_provider_with_retry_and_update(db, item)
    except Exception as e:
        logger.warning("AIProvider sync after update failed", extra={"id": str(item.id), "error": str(e)})

    return _to_response(item)


@router.delete("/{provider_id}", status_code=status.HTTP_204_NO_CONTENT, responses=DELETE_RESPONSES)
async def delete_ai_provider(
    provider_id: UUID,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user),
) -> None:
    """Soft delete an AI provider."""

    item = (
        db.query(AIProvider)
        .filter(
            AIProvider.id == provider_id,
            AIProvider.project_id == current_user.project_id,
            AIProvider.deleted_at.is_(None),
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI provider not found")

    # Soft delete and mark inactive, then sync remote as inactive
    item.is_active = False
    item.deleted_at = datetime.utcnow()
    item.updated_at = datetime.utcnow()

    db.commit()

    # Try to sync deletion as deactivation with retry
    try:
        await sync_provider_with_retry_and_update(db, item)
    except Exception as e:
        logger.warning("AIProvider sync after delete failed", extra={"id": str(item.id), "error": str(e)})

    logger.info("Deleted AIProvider", extra={"id": str(provider_id)})
    return None


@router.post("/{provider_id}/enable", response_model=AIProviderResponse, responses=UPDATE_RESPONSES)
async def enable_ai_provider(
    provider_id: UUID,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user),
) -> AIProviderResponse:
    """Enable an AI provider."""

    item = (
        db.query(AIProvider)
        .filter(
            AIProvider.id == provider_id,
            AIProvider.project_id == current_user.project_id,
            AIProvider.deleted_at.is_(None),
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI provider not found")

    item.is_active = True
    item.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(item)

    # Sync status to tgo-ai with retry (non-blocking)
    try:
        await sync_provider_with_retry_and_update(db, item)
    except Exception as e:
        logger.warning("AIProvider sync after enable failed", extra={"id": str(item.id), "error": str(e)})
        db.refresh(item)


@router.post("/{provider_id}/sync", response_model=AIProviderResponse, responses=UPDATE_RESPONSES)
async def sync_ai_provider_now(
    provider_id: UUID,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user),
) -> AIProviderResponse:
    """Manually trigger sync of a single AI provider to tgo-ai."""

    item = (
        db.query(AIProvider)
        .filter(
            AIProvider.id == provider_id,
            AIProvider.project_id == current_user.project_id,
            AIProvider.deleted_at.is_(None),
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI provider not found")

    try:
        await sync_provider_with_retry_and_update(db, item)
    except Exception as e:
        logger.warning("AIProvider manual sync failed", extra={"id": str(item.id), "error": str(e)})

    return _to_response(item)


@router.post("/{provider_id}/disable", response_model=AIProviderResponse, responses=UPDATE_RESPONSES)
async def disable_ai_provider(
    provider_id: UUID,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user),
) -> AIProviderResponse:
    """Disable an AI provider."""

    item = (
        db.query(AIProvider)
        .filter(
            AIProvider.id == provider_id,
            AIProvider.project_id == current_user.project_id,
            AIProvider.deleted_at.is_(None),
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI provider not found")

    item.is_active = False
    item.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(item)

    # Sync status to tgo-ai with retry (non-blocking)
    try:
        await sync_provider_with_retry_and_update(db, item)
    except Exception as e:
        logger.warning("AIProvider sync after disable failed", extra={"id": str(item.id), "error": str(e)})

    return _to_response(item)


@router.post("/{provider_id}/test", responses=CRUD_RESPONSES)
async def test_ai_provider_connection(
    provider_id: UUID,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user),
):
    """Test connection/credentials for an AI provider.

    Performs a lightweight GET request to provider's models/list endpoint
    using the stored API key. Returns success flag and message.
    """
    item = (
        db.query(AIProvider)
        .filter(
            AIProvider.id == provider_id,
            AIProvider.project_id == current_user.project_id,
            AIProvider.deleted_at.is_(None),
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI provider not found")

    plain_key = decrypt_str(item.api_key) if item.api_key else None
    method, url, headers = _build_test_request(item, plain_key)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.request(method, url, headers=headers)
        ok = 200 <= resp.status_code < 300
        detail = None
        try:
            detail = resp.json()
        except Exception:
            detail = resp.text
        if ok:
            return {"success": True, "message": "Connection test passed", "status": resp.status_code, "details": detail}
        else:
            return {"success": False, "message": f"HTTP {resp.status_code}", "status": resp.status_code, "details": detail}
    except httpx.RequestError as e:
        logger.warning("AIProvider test request error", extra={"id": str(item.id), "error": str(e)})
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Connection failed: {e}")

