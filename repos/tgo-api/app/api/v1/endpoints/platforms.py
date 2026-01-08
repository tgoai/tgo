"""Platform endpoints."""

from datetime import datetime
from typing import List, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Request, Response, Header, UploadFile, File
from sqlalchemy.orm import Session, joinedload, contains_eager

from app.core.database import get_db
from app.core.logging import get_logger
from app.core.security import generate_api_key, get_current_active_user, require_permission
from app.models import Platform, PlatformTypeDefinition, Staff
from app.schemas import (
    PlatformAPIKeyResponse,
    PlatformCreate,
    PlatformListItemResponse,
    PlatformListParams,
    PlatformListResponse,
    PlatformResponse,
    PlatformTypeDefinitionResponse,
    PlatformUpdate,
)
import httpx
from app.core.config import settings


logger = get_logger("endpoints.platforms")
router = APIRouter()


# Reuse a simple filename sanitizer (similar to chat upload)
import re
import os
import time
import secrets
import mimetypes
from pathlib import Path


def _sanitize_filename(name: str, limit: int = 100) -> str:
    name = (name or "upload.bin").replace("\\", "_").replace("/", "_").replace("..", ".")
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    if len(name) <= limit:
        return name
    if "." in name:
        base, ext = name.rsplit(".", 1)
        base = base[: max(1, limit - len(ext) - 1)]
        return f"{base}.{ext}"
    return name[:limit]


def _build_platform_list_item(platform: Platform, language: str = "zh") -> PlatformListItemResponse:
    """Build PlatformListItemResponse with language-aware name/display_name.

    Priority:
    1) If ``Platform.name`` is set, always use it.
    2) Otherwise, pick from the related PlatformTypeDefinition based on language:
       - ``zh`` (default): use ``name`` (Chinese), fallback to "未命名平台".
       - non-``zh``: use ``name_en`` when available, otherwise ``name``,
         finally "Unnamed Platform".
    """
    item = PlatformListItemResponse.model_validate(platform)
    try:
        if platform.name:
            localized_name = platform.name
        elif platform.platform_type:
            if language == "zh":
                localized_name = getattr(platform.platform_type, "name", None) or "未命名平台"
            else:
                localized_name = (
                    getattr(platform.platform_type, "name_en", None)
                    or getattr(platform.platform_type, "name", None)
                    or "Unnamed Platform"
                )
        else:
            localized_name = "未命名平台" if language == "zh" else "Unnamed Platform"

        item.name = localized_name
        item.display_name = localized_name
    except Exception:
        # In case anything unexpected happens, keep the original values.
        pass
    return item


def _build_platform_response(platform: Platform, language: str = "zh") -> PlatformResponse:
    """Build PlatformResponse with language-aware name/display_name."""
    response = PlatformResponse.model_validate(platform)
    try:
        if platform.name:
            localized_name = platform.name
        elif platform.platform_type:
            if language == "zh":
                localized_name = getattr(platform.platform_type, "name", None) or "未命名平台"
            else:
                localized_name = (
                    getattr(platform.platform_type, "name_en", None)
                    or getattr(platform.platform_type, "name", None)
                    or "Unnamed Platform"
                )
        else:
            localized_name = "未命名平台" if language == "zh" else "Unnamed Platform"

        response.name = localized_name
        response.display_name = localized_name
    except Exception:
        pass
    return response


@router.get("/types", response_model=list[PlatformTypeDefinitionResponse])
async def list_platform_types(
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_permission("platforms:list")),
    x_user_language: str = Header("zh", alias="X-User-Language"),
) -> list[PlatformTypeDefinitionResponse]:
    """List available platform type definitions. Requires platforms:list permission."""
    logger.info(f"User {current_user.username} listing platform types")

    platform_types = (
        db.query(PlatformTypeDefinition)
        .order_by(PlatformTypeDefinition.name)
        .all()
    )

    responses: list[PlatformTypeDefinitionResponse] = []
    for item in platform_types:
        resp = PlatformTypeDefinitionResponse.model_validate(item)
        try:
            if x_user_language == "zh":
                display_name = item.name or "未命名平台类型"
            else:
                display_name = (
                    item.name_en
                    or item.name
                    or "Unnamed Platform Type"
                )
            resp.display_name = display_name
        except Exception:
            # Best-effort: fall back to Chinese name or generic string
            resp.display_name = item.name or "Unnamed Platform Type"
        responses.append(resp)

    return responses


@router.get("", response_model=PlatformListResponse)
async def list_platforms(
    params: PlatformListParams = Depends(),
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_permission("platforms:list")),
    x_user_language: str = Header("zh", alias="X-User-Language"),
) -> PlatformListResponse:
    """
    List platforms.

    Retrieve a paginated list of communication platforms with optional filtering.
    Requires platforms:list permission.
    """
    logger.info(f"User {current_user.username} listing platforms")

    # Build query
    query = (
        db.query(Platform)
        .outerjoin(Platform.platform_type)
        .options(contains_eager(Platform.platform_type))
        .filter(
            Platform.project_id == current_user.project_id,
            Platform.deleted_at.is_(None),
        )
    )

    # Apply filters
    if params.type:
        query = query.filter(Platform.type == params.type)
    if params.is_active is not None:
        query = query.filter(Platform.is_active == params.is_active)

    # Get total count
    total = query.count()

    # Apply pagination and ordering
    platforms = (
        query
        .order_by(
            Platform.is_active.desc(),
            PlatformTypeDefinition.is_supported.desc(),
            Platform.created_at.desc(),
        )
        .offset(params.offset)
        .limit(params.limit)
        .all()
    )

    # Convert to response models (using list item schema without sensitive fields)
    platform_responses = [
        _build_platform_list_item(platform, language=x_user_language) for platform in platforms
    ]

    return PlatformListResponse(
        data=platform_responses,
        pagination={
            "total": total,
            "limit": params.limit,
            "offset": params.offset,
            "has_next": params.offset + params.limit < total,
            "has_prev": params.offset > 0,
        }
    )


@router.get(
    "/info",
    response_model=PlatformResponse,
    summary="Platform: Get Platform Info",
    description="Retrieve platform information using Platform API key (visitor-facing).",
)
async def get_platform_info(
    platform_api_key: str | None = None,
    db: Session = Depends(get_db),
    x_platform_api_key: str | None = Header(None, alias="X-Platform-API-Key"),
    x_user_language: str = Header("zh", alias="X-User-Language"),
) -> PlatformResponse:
    """Get platform information by Platform API key.

    - Auth: API key in query param `platform_api_key` or header `X-Platform-API-Key`
    - Returns: PlatformResponse on success
    - Errors: 401 (invalid/missing), 403 (disabled/deleted)
    """
    api_key = platform_api_key or x_platform_api_key
    if not api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing platform_api_key")

    # Look up by api_key (without status/deleted filters) to distinguish 401 vs 403 as required
    platform = db.query(Platform).filter(Platform.api_key == api_key).first()

    # Log attempt with sanitized key hash prefix
    try:
        import hashlib
        key_hash = hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:10]
    except Exception:
        key_hash = "unknown"

    if not platform:
        logger.warning("Platform info auth failed: invalid api key", extra={"api_key_sha256_prefix": key_hash})
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid platform_api_key")

    if platform.deleted_at is not None:
        logger.warning("Platform info access denied: platform deleted", extra={"platform_id": str(platform.id)})
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Platform is deleted")

    if not platform.is_active:
        logger.warning("Platform info access denied: platform disabled", extra={"platform_id": str(platform.id)})
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Platform is disabled")

    logger.info("Platform info retrieved", extra={"platform_id": str(platform.id)})
    return _build_platform_response(platform, language=x_user_language)


@router.post("", response_model=PlatformResponse, status_code=status.HTTP_201_CREATED)
async def create_platform(
    platform_data: PlatformCreate,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_permission("platforms:create")),
    x_user_language: str = Header("zh", alias="X-User-Language"),
) -> PlatformResponse:
    """
    Create platform.

    Create a new communication platform configuration.
    Requires platforms:create permission.
    """
    logger.info(f"User {current_user.username} creating platform: {platform_data.name or '[auto]'}")


    # Create platform
    platform = Platform(
        project_id=current_user.project_id,
        name=platform_data.name,
        type=platform_data.type,
        api_key=generate_api_key(),
        config=platform_data.config,
        is_active=platform_data.is_active,
        agent_ids=platform_data.agent_ids,
        ai_mode=platform_data.ai_mode.value if platform_data.ai_mode else None,
        fallback_to_ai_timeout=platform_data.fallback_to_ai_timeout,
    )

    db.add(platform)
    db.commit()
    db.refresh(platform)
    db.refresh(platform, attribute_names=["platform_type"])

    logger.info(f"Created platform {platform.id} with name: {platform.name}")

    return _build_platform_response(platform, language=x_user_language)


@router.get("/{platform_id}", response_model=PlatformResponse)
async def get_platform(
    platform_id: UUID,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_permission("platforms:read")),
    x_user_language: str = Header("zh", alias="X-User-Language"),
) -> PlatformResponse:
    """Get platform details. Requires platforms:read permission."""
    logger.info(f"User {current_user.username} getting platform: {platform_id}")

    platform = (
        db.query(Platform)
        .options(joinedload(Platform.platform_type))
        .filter(
            Platform.id == platform_id,
            Platform.project_id == current_user.project_id,
            Platform.deleted_at.is_(None),
        )
        .first()
    )

    if not platform:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Platform not found"
        )

    return _build_platform_response(platform, language=x_user_language)


@router.patch("/{platform_id}", response_model=PlatformResponse)
async def update_platform(
    platform_id: UUID,
    platform_data: PlatformUpdate,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_permission("platforms:update")),
    x_user_language: str = Header("zh", alias="X-User-Language"),
) -> PlatformResponse:
    """
    Update platform.

    Update platform configuration and settings.
    Requires platforms:update permission.
    """
    logger.info(f"User {current_user.username} updating platform: {platform_id}")

    platform = (
        db.query(Platform)
        .options(joinedload(Platform.platform_type))
        .filter(
            Platform.id == platform_id,
            Platform.project_id == current_user.project_id,
            Platform.deleted_at.is_(None),
        )
        .first()
    )

    if not platform:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Platform not found"
        )

    # Check if new name conflicts with existing platform
    if platform_data.name and platform_data.name != platform.name:
        existing_platform = db.query(Platform).filter(
            Platform.project_id == current_user.project_id,
            Platform.name == platform_data.name,
            Platform.id != platform_id,
            Platform.deleted_at.is_(None)
        ).first()

        if existing_platform:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Platform name already exists"
            )

    # Update fields
    update_data = platform_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(platform, field, value)

    platform.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(platform)
    db.refresh(platform, attribute_names=["platform_type"])

    logger.info(f"Updated platform {platform.id}")

    return _build_platform_response(platform, language=x_user_language)


@router.delete("/{platform_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_platform(
    platform_id: UUID,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_permission("platforms:delete")),
) -> None:
    """
    Delete platform (soft delete).

    Soft delete a platform. This also affects all visitors associated with this platform.
    Requires platforms:delete permission.
    """
    logger.info(f"User {current_user.username} deleting platform: {platform_id}")

    platform = db.query(Platform).filter(
        Platform.id == platform_id,
        Platform.project_id == current_user.project_id,
        Platform.deleted_at.is_(None)
    ).first()

    if not platform:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Platform not found"
        )

    # Soft delete
    platform.deleted_at = datetime.utcnow()
    platform.updated_at = datetime.utcnow()

    db.commit()

    logger.info(f"Deleted platform {platform.id}")

    return None


@router.post("/{platform_id}/regenerate_api_key", response_model=PlatformAPIKeyResponse)
async def regenerate_platform_api_key(
    platform_id: UUID,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_permission("platforms:update")),
) -> PlatformAPIKeyResponse:
    """Regenerate the API key for a platform. Requires platforms:update permission."""
    logger.info(f"User {current_user.username} regenerating API key for platform: {platform_id}")

    platform = (
        db.query(Platform)
        .filter(
            Platform.id == platform_id,
            Platform.project_id == current_user.project_id,
            Platform.deleted_at.is_(None),
        )
        .first()
    )

    if not platform:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Platform not found"
        )

    platform.api_key = generate_api_key()
    platform.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(platform)


    logger.info(f"Regenerated API key for platform {platform.id}")

    return PlatformAPIKeyResponse(id=platform.id, api_key=platform.api_key)



@router.post("/{platform_id}/enable", response_model=PlatformResponse)
async def enable_platform(
    platform_id: UUID,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_permission("platforms:update")),
    x_user_language: str = Header("zh", alias="X-User-Language"),
) -> PlatformResponse:
    """Enable a platform (set is_active=True). Requires platforms:update permission."""
    logger.info("User %s enabling platform %s", current_user.username, str(platform_id))

    platform = (
        db.query(Platform)
        .options(joinedload(Platform.platform_type))
        .filter(
            Platform.id == platform_id,
            Platform.project_id == current_user.project_id,
            Platform.deleted_at.is_(None),
        )
        .first()
    )
    if not platform:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Platform not found")

    platform.is_active = True
    platform.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(platform)

    # Auto-configure Telegram webhook when platform is enabled
    if platform.type == "telegram":
        await _setup_telegram_webhook(platform)

    # Notify tgo-platform to start Slack Socket Mode handler
    if platform.type == "slack":
        await _notify_slack_platform_reload(platform)

    logger.info("Platform %s enabled by user %s", str(platform.id), current_user.username)
    return _build_platform_response(platform, language=x_user_language)


@router.post("/{platform_id}/disable", response_model=PlatformResponse)
async def disable_platform(
    platform_id: UUID,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_permission("platforms:update")),
    x_user_language: str = Header("zh", alias="X-User-Language"),
) -> PlatformResponse:
    """Disable a platform (set is_active=False). Requires platforms:update permission."""
    logger.info("User %s disabling platform %s", current_user.username, str(platform_id))

    platform = (
        db.query(Platform)
        .options(joinedload(Platform.platform_type))
        .filter(
            Platform.id == platform_id,
            Platform.project_id == current_user.project_id,
            Platform.deleted_at.is_(None),
        )
        .first()
    )
    if not platform:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Platform not found")

    # Delete Telegram webhook when platform is disabled
    if platform.type == "telegram":
        await _delete_telegram_webhook(platform)

    # Notify tgo-platform to stop Slack Socket Mode handler
    if platform.type == "slack":
        await _notify_slack_platform_stop(str(platform.id))

    platform.is_active = False
    platform.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(platform)

    logger.info("Platform %s disabled by user %s", str(platform.id), current_user.username)
    return _build_platform_response(platform, language=x_user_language)


async def _setup_telegram_webhook(platform: Platform) -> None:
    """Auto-configure Telegram Bot webhook when platform is enabled."""
    config = platform.config or {}
    bot_token = config.get("bot_token")
    
    if not bot_token:
        logger.warning(
            "Telegram platform %s enabled but no bot_token configured",
            str(platform.id)
        )
        return
    
    # Build webhook URL
    webhook_url = f"{settings.API_BASE_URL.rstrip('/')}/v1/platforms/callback/{platform.api_key}"
    webhook_secret = config.get("webhook_secret")
    
    try:
        # Call Telegram setWebhook API
        payload: dict[str, Any] = {"url": webhook_url}
        if webhook_secret:
            payload["secret_token"] = webhook_secret
        
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"https://api.telegram.org/bot{bot_token}/setWebhook",
                json=payload
            )
            result = response.json()
            
            if result.get("ok"):
                logger.info(
                    "Telegram webhook set for platform %s: %s",
                    str(platform.id), webhook_url
                )
            else:
                logger.error(
                    "Failed to set Telegram webhook for platform %s: %s",
                    str(platform.id), result.get("description", "Unknown error")
                )
    except Exception as e:
        logger.error(
            "Error setting Telegram webhook for platform %s: %s",
            str(platform.id), str(e)
        )


async def _delete_telegram_webhook(platform: Platform) -> None:
    """Delete Telegram Bot webhook when platform is disabled."""
    config = platform.config or {}
    bot_token = config.get("bot_token")
    
    if not bot_token:
        return
    
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"https://api.telegram.org/bot{bot_token}/deleteWebhook"
            )
            result = response.json()
            
            if result.get("ok"):
                logger.info("Telegram webhook deleted for platform %s", str(platform.id))
            else:
                logger.warning(
                    "Failed to delete Telegram webhook for platform %s: %s",
                    str(platform.id), result.get("description", "Unknown error")
                )
    except Exception as e:
        logger.warning(
            "Error deleting Telegram webhook for platform %s: %s",
            str(platform.id), str(e)
        )


async def _notify_slack_platform_reload(platform: Platform) -> None:
    """Notify tgo-platform to start Slack Socket Mode handler for a platform."""
    platform_base_url = settings.PLATFORM_BASE_URL if hasattr(settings, 'PLATFORM_BASE_URL') else "http://tgo-platform:8003"
    url = f"{platform_base_url.rstrip('/')}/internal/slack/reload"
    
    config = platform.config or {}
    payload = {
        "platform_id": str(platform.id),
        "project_id": str(platform.project_id),
        "api_key": platform.api_key,
        "bot_token": config.get("bot_token", ""),
        "app_token": config.get("app_token", ""),
        "signing_secret": config.get("signing_secret", ""),
    }
    
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(url, json=payload)
            if response.status_code == 200:
                result = response.json()
                if result.get("success"):
                    logger.info("Slack platform %s reload triggered successfully", str(platform.id))
                else:
                    logger.warning("Slack platform %s reload returned failure: %s", str(platform.id), result.get("message"))
            else:
                logger.warning("Failed to notify tgo-platform for Slack reload: %s", response.text)
    except Exception as e:
        logger.warning("Error notifying tgo-platform for Slack reload: %s", str(e))


async def _notify_slack_platform_stop(platform_id: str) -> None:
    """Notify tgo-platform to stop Slack Socket Mode handler for a platform."""
    platform_base_url = settings.PLATFORM_BASE_URL if hasattr(settings, 'PLATFORM_BASE_URL') else "http://tgo-platform:8003"
    url = f"{platform_base_url.rstrip('/')}/internal/slack/stop/{platform_id}"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(url)
            if response.status_code == 200:
                result = response.json()
                logger.info("Slack platform %s stop triggered: %s", platform_id, result.get("message"))
            else:
                logger.warning("Failed to notify tgo-platform for Slack stop: %s", response.text)
    except Exception as e:
        logger.warning("Error notifying tgo-platform for Slack stop: %s", str(e))


@router.post("/{platform_id}/enable-ai", response_model=PlatformResponse)
async def enable_ai_for_platform(
    platform_id: UUID,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_permission("platforms:update")),
    x_user_language: str = Header("zh", alias="X-User-Language"),
) -> PlatformResponse:
    """Enable AI for a platform (set ai_mode=auto). Requires platforms:update permission."""
    logger.info("User %s enabling AI for platform %s", current_user.username, str(platform_id))

    platform = (
        db.query(Platform)
        .options(joinedload(Platform.platform_type))
        .filter(
            Platform.id == platform_id,
            Platform.project_id == current_user.project_id,
            Platform.deleted_at.is_(None),
        )
        .first()
    )
    if not platform:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Platform not found")

    platform.ai_mode = "auto"
    platform.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(platform)

    logger.info("Platform %s AI enabled (ai_mode=auto) by user %s", str(platform.id), current_user.username)
    return _build_platform_response(platform, language=x_user_language)


@router.post("/{platform_id}/disable-ai", response_model=PlatformResponse)
async def disable_ai_for_platform(
    platform_id: UUID,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_permission("platforms:update")),
    x_user_language: str = Header("zh", alias="X-User-Language"),
) -> PlatformResponse:
    """Disable AI for a platform (set ai_mode=off). Requires platforms:update permission."""
    logger.info("User %s disabling AI for platform %s", current_user.username, str(platform_id))

    platform = (
        db.query(Platform)
        .options(joinedload(Platform.platform_type))
        .filter(
            Platform.id == platform_id,
            Platform.project_id == current_user.project_id,
            Platform.deleted_at.is_(None),
        )
        .first()
    )
    if not platform:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Platform not found")

    platform.ai_mode = "off"
    platform.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(platform)

    logger.info("Platform %s AI disabled (ai_mode=off) by user %s", str(platform.id), current_user.username)
    return _build_platform_response(platform, language=x_user_language)


@router.post("/{platform_id}/logo", response_model=PlatformResponse)
async def upload_platform_logo(
    platform_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_permission("platforms:update")),
    x_user_language: str = Header("zh", alias="X-User-Language"),
) -> PlatformResponse:
    """Upload or replace the logo image for a platform. Requires platforms:update permission.

    - Auth: JWT staff via get_current_active_user
    - File: multipart/form-data field 'file'
    - Validates MIME type and file size; stores under PLATFORM_LOGO_UPLOAD_DIR/{platform_id}/
    """
    # 1) Lookup platform and authz
    platform = (
        db.query(Platform)
        .filter(
            Platform.id == platform_id,
            Platform.deleted_at.is_(None),
        )
        .first()
    )
    if not platform:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Platform not found")
    if platform.project_id != current_user.project_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this platform")

    # 2) Validate MIME type
    allowed_types = set(settings.PLATFORM_LOGO_ALLOWED_TYPES or [])
    mime = (file.content_type or "").lower()
    if not mime or (allowed_types and mime not in allowed_types):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or unsupported image type")

    # 3) Build destination path
    original_name = _sanitize_filename(file.filename or "logo")
    # Prefer extension by MIME type
    guessed_ext = mimetypes.guess_extension(mime) or ""
    if guessed_ext.startswith("."):
        guessed_ext = guessed_ext[1:]
    ext = (original_name.rsplit(".", 1)[-1].lower() if "." in original_name else guessed_ext or "png")
    ts_ms = int(time.time() * 1000)
    fname = f"{platform_id}_logo_{ts_ms}.{ext}"

    base_dir = Path(settings.PLATFORM_LOGO_UPLOAD_DIR).resolve()
    dest_path = base_dir / str(platform_id) / fname
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    # 4) Save file with size limit
    max_bytes = int(settings.PLATFORM_LOGO_MAX_SIZE_MB) * 1024 * 1024
    total = 0
    try:
        with open(dest_path, "wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    try:
                        out.flush()
                        out.close()
                    finally:
                        try:
                            if dest_path.exists():
                                os.unlink(dest_path)
                        except Exception:
                            pass
                    raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File too large")
                out.write(chunk)
    except HTTPException:
        raise
    except Exception as e:
        # Cleanup on failure
        try:
            if dest_path.exists():
                os.unlink(dest_path)
        except Exception:
            pass
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Logo storage failed: {e}")

    # 5) Remove previous logo if present
    try:
        if getattr(platform, "logo_path", None):
            old_base = Path(settings.PLATFORM_LOGO_UPLOAD_DIR).resolve()
            old_path = (old_base / platform.logo_path).resolve()
            try:
                old_path.relative_to(old_base)
                if old_path.exists() and old_path.is_file():
                    os.unlink(old_path)
            except Exception:
                pass
    except Exception:
        pass

    # 6) Persist new path (relative to PLATFORM_LOGO_UPLOAD_DIR)
    rel_path = f"{platform_id}/{fname}"
    platform.logo_path = rel_path
    db.commit()
    db.refresh(platform)

    logger.info("Platform logo uploaded", extra={"platform_id": str(platform.id), "size": total, "mime": mime})
    return _build_platform_response(platform, language=x_user_language)


@router.get("/{platform_id}/logo")
async def get_platform_logo(
    platform_id: UUID,
    db: Session = Depends(get_db),
):
    """Serve the stored logo image for a platform (public access)."""
    platform = (
        db.query(Platform)
        .filter(Platform.id == platform_id, Platform.deleted_at.is_(None))
        .first()
    )
    if not platform or not getattr(platform, "logo_path", None):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Logo not found")

    base_dir = Path(settings.PLATFORM_LOGO_UPLOAD_DIR).resolve()
    file_path = (base_dir / platform.logo_path).resolve()
    try:
        file_path.relative_to(base_dir)
    except Exception:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Invalid logo path")

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Logo missing from storage")

    mime = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    headers = {"Cache-Control": "public, max-age=86400"}

    from fastapi.responses import FileResponse  # local import to avoid global weight
    return FileResponse(path=str(file_path), media_type=mime, headers=headers)


@router.get("/callback/{platform_api_key}")
async def wecom_callback_verify(
    platform_api_key: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Response:
    """WeCom (企业微信/企业微信机器人) callback URL verification (GET).

    WeCom sends msg_signature, timestamp, nonce, and echostr for verification.
    We verify the signature and decrypt echostr (if encryption enabled), then
    return the decrypted plain text as the response body.
    
    Supports both 'wecom' (企业微信) and 'wecom_bot' (企业微信机器人) platform types.
    """
    # 1) Validate platform
    platform = (
        db.query(Platform)
        .filter(
            Platform.api_key == platform_api_key,
            Platform.deleted_at.is_(None),
            Platform.is_active.is_(True),
            Platform.type.in_(["wecom", "wecom_bot"]),
        )
        .first()
    )
    if not platform:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid platform_api_key")

    # 2) Extract required query params
    qp = request.query_params
    msg_signature = qp.get("msg_signature")
    timestamp = qp.get("timestamp")
    nonce = qp.get("nonce")
    echostr = qp.get("echostr")
    if not all([msg_signature, timestamp, nonce, echostr]):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing required query parameters")

    # 3) Load WeCom config
    cfg = platform.config or {}
    token = cfg.get("token")
    encoding_aes_key = (cfg.get("encoding_aes_key") or "").strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="WeCom token not configured")

    # 4) Verify signature (SHA1 of sorted token,timestamp,nonce,echostr)
    import hashlib

    parts = [token, timestamp, nonce, echostr]
    parts.sort()
    sha = hashlib.sha1()
    sha.update("".join(parts).encode("utf-8"))
    calc_sig = sha.hexdigest()
    if calc_sig != msg_signature:
        logger.warning("WeCom URL verify signature mismatch", extra={"platform_id": str(platform.id)})
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid signature")

    # 5) Decrypt echostr if AES key provided; otherwise echo as-is
    try:
        if encoding_aes_key and len(encoding_aes_key) >= 43:
            import base64
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

            # Build AES key and IV
            aes_key = base64.b64decode(encoding_aes_key + "=")
            iv = aes_key[:16]
            cipher_text = base64.b64decode(echostr)

            cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv))
            decryptor = cipher.decryptor()
            plain_padded = decryptor.update(cipher_text) + decryptor.finalize()

            # PKCS#7 unpad
            pad = plain_padded[-1]
            if isinstance(pad, str):
                pad = ord(pad)
            if pad < 1 or pad > 32:
                raise ValueError("Invalid padding")
            plain = plain_padded[:-pad]

            # Plain format: 16 random bytes + 4 bytes msg_len (network order) + msg + corp_id
            if len(plain) < 20:
                raise ValueError("Plaintext too short")
            msg_len = int.from_bytes(plain[16:20], byteorder="big")
            msg = plain[20 : 20 + msg_len]
            # corp_id = plain[20 + msg_len : ]  # not used here
            result = msg.decode("utf-8", errors="ignore")
        else:
            result = echostr

        logger.info("WeCom URL verify succeeded", extra={"platform_id": str(platform.id)})
        return Response(content=result, media_type="text/plain")
    except Exception as exc:  # pragma: no cover
        logger.error("WeCom URL verify failed: %s", exc, extra={"platform_id": str(platform.id)})
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Verification failed")

@router.post("/callback/{platform_api_key}")
async def platform_callback_forward(
    platform_api_key: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Response:
    """Forward third-party platform callbacks to the TGO Platform Service.

    - Validates the platform_api_key against platforms table (must be active and not soft-deleted)
    - Forwards body and query parameters to Platform Service
    - Returns Platform Service response verbatim (status, headers, body)
    """
    print("platform_api_key: %s", platform_api_key)
    # Validate platform_api_key
    platform = (
        db.query(Platform)
        .filter(
            Platform.api_key == platform_api_key,
            Platform.deleted_at.is_(None),
            Platform.is_active.is_(True),
        )
        .first()
    )
    if not platform:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid platform_api_key")

    # Build target URL
    target_url = f"{settings.PLATFORM_SERVICE_URL.rstrip('/')}/v1/platforms/callback/{platform_api_key}"

    # Read original request
    body = await request.body()

    # Forward minimal safe headers (avoid hop-by-hop headers)
    forward_headers: dict[str, str] = {}
    ct = request.headers.get("content-type")
    if ct:
        forward_headers["content-type"] = ct
    accept = request.headers.get("accept")
    if accept:
        forward_headers["accept"] = accept

    # Do the POST forward
    try:
        async with httpx.AsyncClient(timeout=settings.PLATFORM_SERVICE_TIMEOUT) as client:
            resp = await client.post(
                target_url,
                params=dict(request.query_params),
                content=body,
                headers=forward_headers,
            )
    except httpx.TimeoutException:
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="Platform Service timeout")
    except httpx.RequestError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Platform Service request error: {exc}")

    # Prepare response headers (filter hop-by-hop)
    hop_by_hop = {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
        "content-length",  # let FastAPI compute
    }
    passthrough_headers = {k: v for k, v in resp.headers.items() if k.lower() not in hop_by_hop}

    # Build FastAPI Response; set media_type explicitly
    media_type = resp.headers.get("content-type")
    return Response(content=resp.content, status_code=resp.status_code, headers=passthrough_headers, media_type=media_type)
