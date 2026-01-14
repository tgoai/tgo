from __future__ import annotations

from typing import Any, Optional, Sequence
from datetime import datetime

import httpx

from app.core.config import settings
from app.models.ai_provider import AIProvider
from app.utils.crypto import decrypt_str


def _map_kind_and_vendor(provider: str, config: Optional[dict] = None) -> tuple[str, Optional[str]]:
    p = (provider or "").lower()
    vendor_cfg = None
    if config and isinstance(config, dict):
        vendor_cfg = config.get("vendor")
    if p in {"openai", "oai", "gpt"}:
        return "openai", vendor_cfg or "openai"
    if p in {"anthropic", "claude"}:
        return "anthropic", vendor_cfg or "anthropic"
    if p in {"google", "gemini", "google_ai_studio", "vertex"}:
        return "google", vendor_cfg or "google"
    if p in {"azure_openai", "azure-openai", "azure"}:
        return "openai_compatible", vendor_cfg or "azure_openai"
    # default to openai_compatible with provider as vendor label
    return "openai_compatible", vendor_cfg or p or None


def _provider_to_upsert(item: AIProvider) -> dict[str, Any]:
    provider_kind, vendor = _map_kind_and_vendor(item.provider, item.config)
    org = None
    timeout = None
    if item.config and isinstance(item.config, dict):
        org = item.config.get("organization")
        timeout = item.config.get("timeout")
    alias = (item.name or item.provider or "").strip()[:80]
    api_key_plain = decrypt_str(item.api_key) if item.api_key else None
    
    # Available models for this provider
    models = []
    if item.models:
        for m in item.models:
            if m.deleted_at is None:
                models.append({
                    "model_id": str(m.model_id),
                    "model_name": str(m.model_name),
                    "model_type": str(m.model_type),
                    "is_active": bool(m.is_active),
                    "capabilities": dict(m.capabilities) if m.capabilities else {}
                })
    
    upsert: dict[str, Any] = {
        "id": str(item.id),  # required by tgo-ai LLMProviderUpsert schema
        "provider_kind": provider_kind,
        "vendor": vendor,
        "api_base_url": item.api_base_url,
        "organization": org,
        "timeout": timeout,
        "is_active": bool(item.is_active),
        "project_id": str(item.project_id),
        "alias": alias,
        "api_key": api_key_plain,
        "models": models,
    }
    # Remove keys with None to keep payload compact
    return {k: v for k, v in upsert.items() if v is not None}


def _build_headers() -> dict[str, str]:
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if settings.AI_SERVICE_API_KEY:
        headers["X-API-Key"] = settings.AI_SERVICE_API_KEY
    return headers


async def sync_providers(items: Sequence[AIProvider]) -> tuple[bool, Optional[str], Optional[dict]]:
    url = f"{settings.AI_SERVICE_URL.rstrip('/')}/api/v1/llm-providers/sync"
    payload = {"providers": [_provider_to_upsert(x) for x in items]}
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
    except Exception as e:  # pragma: no cover
        return False, f"unexpected_error: {e}", None


async def sync_provider(item: AIProvider) -> tuple[bool, Optional[str], Optional[dict]]:
    return await sync_providers([item])



# Retry helpers for syncing providers
async def sync_provider_with_retry(
    item: AIProvider,
    max_retries: Optional[int] = None,
    initial_delay: Optional[int] = None,
) -> tuple[bool, Optional[str], Optional[dict]]:
    """Sync a single provider with exponential backoff retry.

    Returns (ok, err_msg, response_data).
    """
    # Local imports to avoid changing module import header
    import asyncio
    from app.core.logging import get_logger

    logger = get_logger("services.ai_provider_sync")
    retries = settings.AI_PROVIDER_SYNC_RETRY_COUNT if max_retries is None else max_retries
    base_delay = settings.AI_PROVIDER_SYNC_RETRY_DELAY if initial_delay is None else initial_delay

    # Initial attempt
    ok, err, data = await sync_provider(item)
    if ok:
        return ok, err, data

    last_err = err
    # Exponential backoff retries: 3 retries by default (2s, 4s, 8s)
    for attempt in range(1, max(0, retries) + 1):
        delay = max(0, base_delay) * (2 ** (attempt - 1))
        logger.warning(
            "AIProvider sync failed; retrying",
            extra={
                "provider_id": str(item.id),
                "attempt": attempt,
                "max_retries": retries,
                "delay_sec": delay,
                "error": str(last_err),
            },
        )
        await asyncio.sleep(delay)
        ok, err, data = await sync_provider(item)
        if ok:
            return ok, err, data
        last_err = err

    # All retries failed
    return False, last_err, None


async def sync_providers_with_retry(
    items: Sequence[AIProvider],
    max_retries: Optional[int] = None,
    initial_delay: Optional[int] = None,
) -> tuple[bool, Optional[str], Optional[dict]]:
    """Batch sync providers with exponential backoff retry as a group."""
    import asyncio
    from app.core.logging import get_logger

    logger = get_logger("services.ai_provider_sync")
    retries = settings.AI_PROVIDER_SYNC_RETRY_COUNT if max_retries is None else max_retries
    base_delay = settings.AI_PROVIDER_SYNC_RETRY_DELAY if initial_delay is None else initial_delay

    ok, err, data = await sync_providers(items)
    if ok:
        return ok, err, data

    last_err = err
    for attempt in range(1, max(0, retries) + 1):
        delay = max(0, base_delay) * (2 ** (attempt - 1))
        logger.warning(
            "AIProvider batch sync failed; retrying",
            extra={
                "count": len(items),
                "attempt": attempt,
                "max_retries": retries,
                "delay_sec": delay,
                "error": str(last_err),
            },
        )
        await asyncio.sleep(delay)
        ok, err, data = await sync_providers(items)
        if ok:
            return ok, err, data
        last_err = err
    return False, last_err, None


async def sync_provider_with_retry_and_update(db, item: AIProvider) -> tuple[bool, Optional[str]]:
    """Sync one provider with retries and update its sync fields in DB.

    Returns (ok, err_msg).
    """
    from sqlalchemy.orm import Session  # local import to avoid header changes
    assert isinstance(db, Session)

    ok, err, _ = await sync_provider_with_retry(item)
    item.last_synced_at = datetime.utcnow()
    if ok:
        item.sync_status = "synced"
        item.sync_error = None
    else:
        item.sync_status = "failed"
        item.sync_error = str(err) if err else "unknown error"
    db.commit()
    try:
        db.refresh(item)
    except Exception:
        pass
    return ok, err
