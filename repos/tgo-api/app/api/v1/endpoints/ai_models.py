"""AI Model catalog endpoints - fetches models from provider APIs."""

from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.common_responses import LIST_RESPONSES
from app.core.logging import get_logger
from app.core.security import get_current_active_user
from app.models import Staff

logger = get_logger("endpoints.ai_models")
router = APIRouter()


class ModelInfo(BaseModel):
    """Model information from provider API."""
    id: str = Field(..., description="Model identifier")
    name: Optional[str] = Field(None, description="Model display name")
    owned_by: Optional[str] = Field(None, description="Model owner/provider")
    model_type: Optional[str] = Field(None, description="Model type (chat/embedding)")
    created: Optional[int] = Field(None, description="Creation timestamp")


class ModelListRequest(BaseModel):
    """Request body for fetching models from provider."""
    provider: str = Field(..., description="Provider type (openai, anthropic, dashscope, azure, etc.)")
    api_key: Optional[str] = Field(None, description="API key for the provider (optional, returns default models if not provided)")
    api_base_url: Optional[str] = Field(None, description="Custom API base URL (optional)")
    config: Optional[Dict[str, Any]] = Field(None, description="Additional provider-specific config (e.g., anthropic_version, api_version)")


class ModelListResponse(BaseModel):
    """Response for model list from provider."""
    provider: str = Field(..., description="Provider type (openai, anthropic, etc.)")
    models: list[ModelInfo] = Field(default_factory=list, description="List of available models")
    is_fallback: bool = Field(False, description="True if using fallback default models (API fetch failed or returned empty)")


# Default/fallback models for each provider when API fetch fails or returns empty
DEFAULT_MODELS: dict[str, list[dict]] = {
    "openai": [
        {"id": "gpt-4o", "name": "GPT-4o", "model_type": "chat"},
        {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "model_type": "chat"},
        {"id": "gpt-4-turbo", "name": "GPT-4 Turbo", "model_type": "chat"},
        {"id": "gpt-4", "name": "GPT-4", "model_type": "chat"},
        {"id": "gpt-3.5-turbo", "name": "GPT-3.5 Turbo", "model_type": "chat"},
        {"id": "text-embedding-3-large", "name": "Text Embedding 3 Large", "model_type": "embedding"},
        {"id": "text-embedding-3-small", "name": "Text Embedding 3 Small", "model_type": "embedding"},
        {"id": "text-embedding-ada-002", "name": "Text Embedding Ada 002", "model_type": "embedding"},
    ],
    "anthropic": [
        {"id": "claude-sonnet-4-20250514", "name": "Claude Sonnet 4", "model_type": "chat"},
        {"id": "claude-3-7-sonnet-20250219", "name": "Claude 3.7 Sonnet", "model_type": "chat"},
        {"id": "claude-3-5-sonnet-20241022", "name": "Claude 3.5 Sonnet", "model_type": "chat"},
        {"id": "claude-3-5-haiku-20241022", "name": "Claude 3.5 Haiku", "model_type": "chat"},
        {"id": "claude-3-opus-20240229", "name": "Claude 3 Opus", "model_type": "chat"},
        {"id": "claude-3-sonnet-20240229", "name": "Claude 3 Sonnet", "model_type": "chat"},
        {"id": "claude-3-haiku-20240307", "name": "Claude 3 Haiku", "model_type": "chat"},
    ],
    "dashscope": [
        {"id": "qwen-max", "name": "Qwen Max", "model_type": "chat"},
        {"id": "qwen-plus", "name": "Qwen Plus", "model_type": "chat"},
        {"id": "qwen-turbo", "name": "Qwen Turbo", "model_type": "chat"},
        {"id": "qwen-long", "name": "Qwen Long", "model_type": "chat"},
        {"id": "qwen2.5-72b-instruct", "name": "Qwen 2.5 72B", "model_type": "chat"},
        {"id": "qwen2.5-32b-instruct", "name": "Qwen 2.5 32B", "model_type": "chat"},
        {"id": "qwen2.5-14b-instruct", "name": "Qwen 2.5 14B", "model_type": "chat"},
        {"id": "qwen2.5-7b-instruct", "name": "Qwen 2.5 7B", "model_type": "chat"},
        {"id": "text-embedding-v3", "name": "Text Embedding V3", "model_type": "embedding"},
        {"id": "text-embedding-v2", "name": "Text Embedding V2", "model_type": "embedding"},
    ],
    "azure": [
        {"id": "gpt-4o", "name": "GPT-4o", "model_type": "chat"},
        {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "model_type": "chat"},
        {"id": "gpt-4-turbo", "name": "GPT-4 Turbo", "model_type": "chat"},
        {"id": "gpt-4", "name": "GPT-4", "model_type": "chat"},
        {"id": "gpt-35-turbo", "name": "GPT-3.5 Turbo", "model_type": "chat"},
        {"id": "text-embedding-3-large", "name": "Text Embedding 3 Large", "model_type": "embedding"},
        {"id": "text-embedding-3-small", "name": "Text Embedding 3 Small", "model_type": "embedding"},
        {"id": "text-embedding-ada-002", "name": "Text Embedding Ada 002", "model_type": "embedding"},
    ],
    # Generic fallback for OpenAI-compatible providers
    "default": [
        {"id": "gpt-4o", "name": "GPT-4o", "model_type": "chat"},
        {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "model_type": "chat"},
        {"id": "gpt-3.5-turbo", "name": "GPT-3.5 Turbo", "model_type": "chat"},
    ],
}


def _get_default_models(provider: str) -> list[ModelInfo]:
    """Get default/fallback models for a provider."""
    provider_lower = provider.lower()
    
    # Map provider aliases to canonical names
    if provider_lower in ("openai", "gpt", "gpt-4o", "oai"):
        key = "openai"
    elif provider_lower in ("anthropic", "claude"):
        key = "anthropic"
    elif provider_lower in ("dashscope", "ali", "aliyun"):
        key = "dashscope"
    elif provider_lower in ("azure_openai", "azure-openai", "azure"):
        key = "azure"
    else:
        key = "default"
    
    models_data = DEFAULT_MODELS.get(key, DEFAULT_MODELS["default"])
    return [
        ModelInfo(
            id=m["id"],
            name=m["name"],
            owned_by=provider,
            model_type=m["model_type"],
            created=None,
        )
        for m in models_data
    ]


def _normalize_base(base: Optional[str]) -> Optional[str]:
    if not base:
        return None
    return base.rstrip("/")


def _infer_model_type(model_id: str) -> str:
    """Infer model type from model ID."""
    model_lower = model_id.lower()
    if "embedding" in model_lower or "embed" in model_lower:
        return "embedding"
    return "chat"


async def _fetch_models_from_provider(
    provider: str,
    api_key: str,
    api_base_url: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
) -> tuple[list[ModelInfo], bool]:
    """Fetch models from provider API and return normalized list.
    
    Args:
        provider: Provider type (openai, anthropic, dashscope, azure, etc.)
        api_key: API key for the provider
        api_base_url: Custom API base URL (optional)
        config: Additional provider-specific config (optional)
    
    Returns:
        tuple[list[ModelInfo], bool]: (models, is_from_api)
        - models: List of models (from API or fallback defaults)
        - is_from_api: True if models are from API, False if using fallback defaults
    """
    provider_lower = provider.lower()
    base = _normalize_base(api_base_url)
    headers: dict[str, str] = {}
    method = "GET"
    url = ""
    cfg = config or {}

    # Build request based on provider type
    if provider_lower in ("openai", "gpt", "gpt-4o", "oai"):
        base = base or "https://api.openai.com/v1"
        url = f"{base}/models"
        headers = {"Authorization": f"Bearer {api_key}"}

    elif provider_lower in ("anthropic", "claude"):
        base = base or "https://api.anthropic.com"
        url = f"{base}/v1/models"
        version = cfg.get("anthropic_version") or "2023-06-01"
        headers = {"x-api-key": api_key, "anthropic-version": version}

    elif provider_lower in ("dashscope", "ali", "aliyun"):
        if base and "compatible-mode" in base:
            compat = base
        else:
            compat = (base or "https://dashscope.aliyuncs.com") + "/compatible-mode/v1"
        url = f"{compat}/models"
        headers = {"Authorization": f"Bearer {api_key}"}

    elif provider_lower in ("azure_openai", "azure-openai", "azure"):
        if not base:
            # Azure requires base URL, return defaults
            logger.warning("Azure OpenAI requires api_base_url, returning default models")
            return _get_default_models(provider), False
        root = base if "/openai" in base else f"{base}/openai"
        api_version = cfg.get("api_version") or "2023-12-01-preview"
        url = f"{root}/deployments?api-version={api_version}"
        headers = {"api-key": api_key}

    elif base:
        # Fallback: try OpenAI-compatible with provided base
        url = f"{base}/models"
        headers = {"Authorization": f"Bearer {api_key}"}

    else:
        # Unsupported provider without base URL, return defaults
        logger.warning(f"Unsupported provider '{provider}' without api_base_url, returning default models")
        return _get_default_models(provider), False

    # Make request
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.request(method, url, headers=headers)

        if resp.status_code >= 400:
            detail = resp.text
            try:
                detail = resp.json()
            except Exception:
                pass
            logger.warning(
                f"Provider API error ({resp.status_code}), returning default models",
                extra={"provider": provider, "detail": str(detail)[:200]}
            )
            return _get_default_models(provider), False

        data = resp.json()

    except httpx.RequestError as e:
        logger.warning(
            "Failed to fetch models from provider, returning default models",
            extra={"provider": provider, "error": str(e)}
        )
        return _get_default_models(provider), False
    except Exception as e:
        logger.warning(
            "Unexpected error fetching models, returning default models",
            extra={"provider": provider, "error": str(e)}
        )
        return _get_default_models(provider), False

    # Parse response based on provider type
    models: list[ModelInfo] = []

    if provider_lower in ("azure_openai", "azure-openai", "azure"):
        # Azure returns deployments
        deployments = data.get("data") or data.get("value") or []
        for dep in deployments:
            model_id = dep.get("id") or dep.get("model") or ""
            if model_id:
                models.append(ModelInfo(
                    id=model_id,
                    name=dep.get("model") or model_id,
                    owned_by="azure",
                    model_type=_infer_model_type(model_id),
                    created=None,
                ))
    else:
        # OpenAI-compatible format
        model_list = data.get("data") or []
        for m in model_list:
            model_id = m.get("id") or ""
            if model_id:
                models.append(ModelInfo(
                    id=model_id,
                    name=model_id,
                    owned_by=m.get("owned_by"),
                    model_type=_infer_model_type(model_id),
                    created=m.get("created"),
                ))

    # If no models returned from API, use defaults
    if not models:
        logger.info("Provider API returned empty model list, returning default models")
        return _get_default_models(provider), False

    return models, True


@router.post("", response_model=ModelListResponse, responses=LIST_RESPONSES)
async def list_ai_models(
    request: ModelListRequest,
    model_type: Optional[str] = Query(None, pattern="^(chat|embedding)$", description="Filter by model type"),
    current_user: Staff = Depends(get_current_active_user),
) -> ModelListResponse:
    """Fetch available models from a provider API.
    
    This endpoint calls the provider's API directly to get the current list
    of available models. If api_key is not provided, returns default/common
    models for the specified provider.
    
    **Use Case**: Call this endpoint before creating an AIProvider to let
    users select which models they want to use.
    """
    provider = request.provider
    api_key = request.api_key
    api_base_url = request.api_base_url
    config = request.config

    # If no API key provided, return default models
    if not api_key:
        logger.info(f"No API key provided for provider '{provider}', returning default models")
        models = _get_default_models(provider)
        is_from_api = False
    else:
        # Fetch models from provider API
        models, is_from_api = await _fetch_models_from_provider(
            provider=provider,
            api_key=api_key,
            api_base_url=api_base_url,
            config=config,
        )

    # Filter by model_type if specified
    if model_type:
        models = [m for m in models if m.model_type == model_type]

    return ModelListResponse(
        provider=provider,
        models=models,
        is_fallback=not is_from_api,
    )
