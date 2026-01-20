from __future__ import annotations

from typing import Any, Optional, Sequence
from datetime import datetime

import httpx

from app.core.config import settings
from app.models.ai_model import AIModel


def _model_to_upsert(item: AIModel) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "provider_id": str(item.provider_id),
        "model_id": item.model_id,
        "model_name": item.model_name,
        "model_type": item.model_type,
        "description": item.description,
        "capabilities": dict(item.capabilities) if item.capabilities else {},
        "context_window": item.context_window,
        "max_tokens": item.max_tokens,
        "is_active": bool(item.is_active) and item.deleted_at is None,
        "store_resource_id": item.store_resource_id,
    }


def _build_headers() -> dict[str, str]:
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if settings.AI_SERVICE_API_KEY:
        headers["X-API-Key"] = settings.AI_SERVICE_API_KEY
    return headers


async def sync_models(items: Sequence[AIModel]) -> tuple[bool, Optional[str], Optional[dict]]:
    url = f"{settings.AI_SERVICE_URL.rstrip('/')}/api/v1/llm-models/sync"
    payload = {"models": [_model_to_upsert(x) for x in items]}
    try:
        async with httpx.AsyncClient(timeout=settings.AI_SERVICE_TIMEOUT) as client:
            resp = await client.post(url, json=payload, headers=_build_headers())
        if resp.status_code >= 400:
            return False, f"{resp.status_code} {resp.text}", None
        try:
            data = resp.json()
        except Exception:
            data = None
        return True, None, data
    except httpx.TimeoutException as te:
        return False, f"timeout: {te}", None
    except httpx.RequestError as re:
        return False, f"request_error: {re}", None
    except Exception as e:
        return False, f"unexpected_error: {e}", None


async def sync_model(item: AIModel) -> tuple[bool, Optional[str], Optional[dict]]:
    return await sync_models([item])
