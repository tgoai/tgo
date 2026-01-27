"""AI Provider (LLM Provider) management endpoints."""

from datetime import datetime
from typing import Optional, Any
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy import or_, and_, select, exists, func
from sqlalchemy.orm import Session

from app.api.common_responses import CREATE_RESPONSES, CRUD_RESPONSES, LIST_RESPONSES, UPDATE_RESPONSES, DELETE_RESPONSES
from app.core.database import get_db
from app.core.logging import get_logger
from app.core.security import get_current_active_user
from app.models import AIProvider, AIModel, Staff
from app.schemas import (
    AIProviderCreate,
    AIProviderListParams,
    AIProviderListResponse,
    AIProviderResponse,
    AIProviderUpdate,
    AIModelInput,
)
from app.schemas.remote_model import RemoteModelListResponse, RemoteModelInfo
from app.utils.crypto import decrypt_str, encrypt_str, mask_secret
from app.services.ai_provider_sync import sync_provider_with_retry_and_update
from app.services.store_sync import sync_uninstall_models_to_store, sync_uninstall_all_provider_models

logger = get_logger("endpoints.ai_providers")


def _filter_models_by_type(models: Optional[list[str]], model_type: Optional[str]) -> list[str]:
    ms = list(models or [])
    if not model_type:
        return ms
    if model_type == "embedding":
        return [m for m in ms if isinstance(m, str) and "embedding" in m.lower()]
    if model_type == "chat":
        return [m for m in ms if isinstance(m, str) and "embedding" not in m.lower()]
    return ms



def _to_response(item: AIProvider, model_type: Optional[str] = None) -> AIProviderResponse:
    plain = decrypt_str(item.api_key) if item.api_key else None
    masked = mask_secret(plain)
    
    # Extract model_id from models relationship
    available_models_list = [m.model_id for m in item.models if m.deleted_at is None]
    models = _filter_models_by_type(available_models_list, model_type)
    
    # Build detailed model configs
    model_configs = [
        AIModelInput(
            model_id=m.model_id,
            model_type=m.model_type,
            capabilities=m.capabilities
        )
        for m in item.models if m.deleted_at is None
    ]
    
    return AIProviderResponse.model_validate({
        "id": item.id,
        "project_id": item.project_id,
        "provider": item.provider,
        "name": item.name,
        "api_base_url": item.api_base_url,
        "available_models": models,
        "model_configs": model_configs,
        "default_model": item.default_model,
        "config": item.config,
        "is_active": item.is_active,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
        "deleted_at": item.deleted_at,
        "has_api_key": bool(item.api_key),
        "api_key_masked": masked,
        "store_resource_id": str(item.store_resource_id) if item.store_resource_id else None,
        "is_from_store": bool(item.is_from_store),
        "last_synced_at": item.last_synced_at,
        "sync_status": item.sync_status,
        "sync_error": item.sync_error,
    })



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

def _parse_remote_models(provider: str, data: Any) -> list[RemoteModelInfo]:
    """Parse remote API response into a list of RemoteModelInfo."""
    models = []
    p = provider.lower()

    def get_caps(mid: str) -> dict:
        caps = {}
        mid_lower = mid.lower()
        # Basic vision detection for common models
        if any(x in mid_lower for x in ("vision", "vl", "gpt-4o", "claude-3-5", "claude-3-opus", "claude-3-sonnet")):
            caps["vision"] = True
        return caps

    if p in ("openai", "gpt", "gpt-4o", "oai", "dashscope", "ali", "aliyun") or "compatible" in p:
        # OpenAI style: { "data": [ { "id": "...", ... } ] }
        if isinstance(data, dict) and "data" in data:
            for m in data["data"]:
                if isinstance(m, dict) and "id" in m:
                    mid = m["id"]
                    mtype = "embedding" if "embedding" in mid.lower() else "chat"
                    models.append(RemoteModelInfo(
                        id=mid, 
                        name=mid, 
                        model_type=mtype,
                        capabilities=get_caps(mid)
                    ))
    
    elif p in ("anthropic", "claude"):
        # Anthropic style: { "data": [ { "id": "...", "display_name": "..." } ] }
        if isinstance(data, dict) and "data" in data:
            for m in data["data"]:
                if isinstance(m, dict) and "id" in m:
                    mid = m["id"]
                    models.append(RemoteModelInfo(
                        id=mid, 
                        name=m.get("display_name") or mid,
                        model_type="chat",
                        capabilities=get_caps(mid)
                    ))
    
    elif p in ("azure_openai", "azure-openai", "azure"):
        # Azure style: { "value": [ { "id": "...", "model": "..." } ] }
        if isinstance(data, dict) and "value" in data:
            for m in data["value"]:
                # Azure deployments often use 'id' or 'name' as the deployment name
                mid = m.get("id") or m.get("name")
                if mid:
                    # Model name might be in 'model' field
                    actual_model = m.get("model", mid)
                    mtype = "embedding" if "embedding" in actual_model.lower() else "chat"
                    models.append(RemoteModelInfo(
                        id=mid, 
                        name=f"{mid} ({actual_model})", 
                        model_type=mtype,
                        capabilities=get_caps(actual_model)
                    ))

    return models


router = APIRouter()


@router.get("/{provider_id}/remote-models", response_model=RemoteModelListResponse)
async def get_provider_remote_models(
    provider_id: UUID,
    model_type: Optional[str] = Query(None, pattern="^(chat|embedding)$"),
    capabilities: Optional[str] = Query(None, description="Filter by capabilities, e.g., 'vision:true'"),
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user),
):
    """Fetch available models from the provider's remote API using stored credentials."""
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
    if not plain_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="API key is not set for this provider")

    method, url, headers = _build_test_request(item, plain_key)

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.request(method, url, headers=headers)
        
        resp.raise_for_status()
        remote_data = resp.json()
        
        models = _parse_remote_models(item.provider, remote_data)
        
        # Apply filtering
        if model_type:
            models = [m for m in models if m.model_type == model_type]
        
        if capabilities:
            try:
                # Parse capabilities filter, e.g., "vision:true,function_calling:true"
                filters = {}
                for part in capabilities.split(","):
                    if ":" in part:
                        k, v = part.split(":", 1)
                        filters[k.strip()] = v.strip().lower() == "true"
                
                if filters:
                    filtered_models = []
                    for m in models:
                        m_caps = m.capabilities or {}
                        match = True
                        for fk, fv in filters.items():
                            if m_caps.get(fk) != fv:
                                match = False
                                break
                        if match:
                            filtered_models.append(m)
                    models = filtered_models
            except Exception as e:
                logger.warning(f"Failed to parse capabilities filter '{capabilities}': {e}")

        return RemoteModelListResponse(
            provider=item.provider,
            models=models,
            is_fallback=False
        )
    except Exception as e:
        logger.warning(f"Failed to fetch remote models for {provider_id}: {str(e)}")
        # Return empty list or handle as fallback if needed
        return RemoteModelListResponse(
            provider=item.provider,
            models=[],
            is_fallback=True
        )


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

    # Determine model type filter logic
    filter_func = None
    if model_type:
        def check_model_type(provider: AIProvider) -> bool:
            # Check models relationship instead of available_models
            models = [m.model_id for m in provider.models if m.deleted_at is None]
            if not isinstance(models, list) or not models:
                # Keep empty/undefined providers in list
                return True
            
            has_embedding = any("embedding" in str(m).lower() for m in models)
            
            if model_type == "embedding":
                return has_embedding
            elif model_type == "chat":
                # Chat providers are those that have at least one non-embedding model
                # or have no embedding models found (defaulting to chat)
                has_chat = any("embedding" not in str(m).lower() for m in models)
                return has_chat or (not has_embedding)
            return True
        filter_func = check_model_type

    # Fetch all candidates first (filtered by basic params)
    # Since specific model filtering is complex in SQL with mixed types, we do it in Python
    # This is safe because the number of providers per project is typically small (< 50)
    candidates = query.order_by(AIProvider.created_at.desc()).all()

    # Apply python-side filtering
    if filter_func:
        candidates = [c for c in candidates if filter_func(c)]

    total = len(candidates)
    
    # Apply pagination in memory
    start = params.offset
    end = params.offset + params.limit
    items = candidates[start:end]

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

    db.add(item)
    db.flush()  # To get item.id

    # Create AIModel records from available_models
    if payload.available_models:
        for m in payload.available_models:
            if isinstance(m, str):
                m_id = m
                m_type = "embedding" if "embedding" in m_id.lower() else "chat"
                m_caps = None
            else:
                m_id = m.model_id
                m_type = m.model_type
                m_caps = m.capabilities

            model_record = AIModel(
                provider_id=item.id,
                provider=item.provider,
                model_id=m_id,
                model_name=m_id,  # Use ID as name if not specified
                model_type=m_type,
                capabilities=m_caps,
                is_active=True
            )
            db.add(model_record)

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
    background_tasks: BackgroundTasks,
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
    current_available = [m.model_id for m in item.models if m.deleted_at is None]
    new_available_input = data.get("available_models")
    
    if new_available_input is not None:
        # Extract model IDs from input (which can be list[str | AIModelInput])
        new_available_ids = []
        for m in new_available_input:
            if isinstance(m, str):
                new_available_ids.append(m)
            else:
                # It's an AIModelInput object/dict
                m_id = m.model_id if hasattr(m, "model_id") else m["model_id"]
                new_available_ids.append(m_id)
        new_available = new_available_ids
    else:
        new_available = current_available

    new_default = data.get("default_model", item.default_model)
    if new_default and new_available and new_default not in new_available:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="default_model must be in available_models")

    # Handle secret update with encryption (ignore empty to keep existing)
    if "api_key" in data:
        raw = data.pop("api_key")
        if raw is not None and raw != "":
            item.api_key = encrypt_str(raw)

    # Handle available_models update
    if "available_models" in data:
        new_models_input = data.pop("available_models") or []
        new_model_ids = []
        model_type_map = {}
        model_caps_map = {}
        
        for m in new_models_input:
            if isinstance(m, str):
                m_id = m
                m_type = "embedding" if "embedding" in m_id.lower() else "chat"
                m_caps = None
            elif isinstance(m, dict):
                m_id = m["model_id"]
                m_type = m.get("model_type", "chat")
                m_caps = m.get("capabilities")
            else:
                # It's an AIModelInput object
                m_id = m.model_id
                m_type = m.model_type
                m_caps = m.capabilities
            
            new_model_ids.append(m_id)
            model_type_map[m_id] = m_type
            model_caps_map[m_id] = m_caps

        existing_models = {m.model_id: m for m in item.models if m.deleted_at is None}
        
        # Deactivate models not in new list
        for m_id, m_obj in existing_models.items():
            if m_id not in new_model_ids:
                m_obj.deleted_at = datetime.utcnow()
                db.add(m_obj)
        
        # Add new models or update existing ones' types/caps if needed
        for m_id in new_model_ids:
            m_type = model_type_map[m_id]
            m_caps = model_caps_map[m_id]
            if m_id not in existing_models:
                new_model = AIModel(
                    provider_id=item.id,
                    provider=item.provider,
                    model_id=m_id,
                    model_name=m_id,
                    model_type=m_type,
                    capabilities=m_caps,
                    is_active=True
                )
                db.add(new_model)
            else:
                # Update type/caps if they changed
                existing_model = existing_models[m_id]
                changed = False
                if existing_model.model_type != m_type:
                    existing_model.model_type = m_type
                    changed = True
                
                # Normalize caps for comparison
                current_caps = existing_model.capabilities or {}
                new_caps = m_caps or {}
                
                # Ensure we are comparing dicts
                if isinstance(current_caps, str):
                    import json
                    try:
                        current_caps = json.loads(current_caps)
                    except:
                        current_caps = {}
                
                if current_caps != new_caps:
                    existing_model.capabilities = new_caps
                    changed = True
                
                if changed:
                    db.add(existing_model)

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
    background_tasks: BackgroundTasks,
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
    now = datetime.utcnow()
    item.is_active = False
    item.deleted_at = now
    item.updated_at = now
    
    # Also soft delete related models
    for m in item.models:
        if m.deleted_at is None:
            m.deleted_at = now
            db.add(m)

    db.commit()

    # Async uninstall all provider models from Store
    background_tasks.add_task(
        sync_uninstall_all_provider_models,
        db,
        current_user.project_id,
        provider_id
    )

    # Try to sync deletion as deactivation with retry
    try:
        await sync_provider_with_retry_and_update(db, item)
    except Exception as e:
        logger.warning("AIProvider sync after delete failed", extra={"id": str(item.id), "error": str(e)})

    logger.info("Deleted AIProvider", extra={"id": str(provider_id)})
    return None


@router.delete("/{provider_id}/models/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provider_model(
    provider_id: UUID,
    model_id: str,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user),
) -> None:
    """Delete a single model from provider."""
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

    model = (
        db.query(AIModel)
        .filter(
            AIModel.provider_id == provider_id,
            AIModel.model_id == model_id,
            AIModel.deleted_at.is_(None),
        )
        .first()
    )
    if not model:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")

    model.deleted_at = datetime.utcnow()
    db.add(model)
    db.commit()

    logger.info("Deleted model from provider", extra={"provider_id": str(provider_id), "model_id": model_id})
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
