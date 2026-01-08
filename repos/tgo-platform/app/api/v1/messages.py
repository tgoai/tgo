from __future__ import annotations
from fastapi import APIRouter, Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.domain.services.normalizer import normalizer
from app.domain.services.dispatcher import process_message
from app.api.schemas import ErrorResponse

router = APIRouter()


@router.post("/ingest", responses={400: {"model": ErrorResponse}, 422: {"model": ErrorResponse}, 500: {"model": ErrorResponse}})
async def ingest(req: Request, db: AsyncSession = Depends(get_db)) -> dict:
    raw = await req.json()
    msg = await normalizer.normalize(raw)
    tgo_api_client = req.app.state.tgo_api_client
    sse_manager = req.app.state.sse_manager
    await process_message(msg, db, tgo_api_client, sse_manager)
    return {"ok": True}



from typing import Optional
import base64
import hashlib
import logging
import httpx
import uuid

from fastapi import status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.error_utils import error_response, get_request_id
from app.db.models import Platform

from app.api.wecom_utils import wecom_get_access_token, wecom_kf_send_msg, wecom_upload_temp_media, resolve_visitor_platform_open_id, resolve_wecom_open_kfid
from app.api.slack_utils import slack_send_text, slack_send_file, slack_get_dm_channel
from app.core.config import settings


def _internalize_url(url: str) -> str:
    """Map public/localhost download URLs to internal Docker service addresses."""
    if not url:
        return url
    
    # If URL is from localhost/api or localhost:8000, map it to internal settings.api_base
    internal_base = settings.api_base_url.rstrip('/')
    
    import re
    # Case 1: http://localhost:8000/v1/...
    transformed = re.sub(r'^https?://(localhost|127\.0\.0\.1):8000', internal_base, url)
    # Case 2: http://localhost/api/v1/... -> Strip /api and replace host
    if "/api/v1/" in transformed and ("localhost" in transformed or "127.0.0.1" in transformed):
        transformed = transformed.replace("/api/v1/", "/v1/")
        transformed = re.sub(r'^https?://(localhost|127\.0\.0\.1)', internal_base, transformed)
        
    return transformed


class SendMessageRequest(BaseModel):
    platform_api_key: str = Field(..., description="Per-platform API key")
    from_uid: str = Field(..., description="Sender user id (for logging)")
    channel_id: str = Field(..., description="Channel id in format '{visitor_id}-vtr'")
    channel_type: int = Field(..., description="Channel type (e.g., 251)")
    payload: dict = Field(..., description="Message payload (see formats)")
    client_msg_no: Optional[str] = Field(None, description="Client-provided idempotency key")


@router.post(
    "/v1/messages/send",
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def send_message(req_body: SendMessageRequest, request: Request, db: AsyncSession = Depends(get_db)) -> dict:
    """Send a message to a third-party platform (WeCom, Email, etc.).

    - Auth: requires platform_api_key in body (platform must exist and be active)
    - channel_id: '{visitor_id}-vtr' (visitor_id extracted by removing '-vtr')
    - payload types:
      * Text: {"type":1, "content":"..."}
      * Image: {"type":2, "url":"http://...", "width":..., "height":...}
    """
    request_id = get_request_id(request)
    client_msg_no = req_body.client_msg_no or ""

    # Lookup platform by api_key
    platform = await db.scalar(select(Platform).where(Platform.api_key == req_body.platform_api_key, Platform.is_active.is_(True)))
    if not platform:
        return error_response(status.HTTP_404_NOT_FOUND, code="PLATFORM_NOT_FOUND", message="Platform not found", request_id=request_id)

    platform_type = (platform.type or "").lower()
    cfg = platform.config or {}

    # Extract visitor_id from channel_id
    channel_id = req_body.channel_id or ""
    visitor_id = channel_id[:-4] if channel_id.endswith("-vtr") else channel_id

    # Resolve helpers via shared utils (Redis + DB)

    # Validate payload
    payload: dict = req_body.payload or {}
    msg_type = int(payload.get("type", 1))

    try:
        if platform_type == "custom":
            # Custom platform: forward message to third-party callback URL
            callback_url = (cfg.get("callback_url") or "").strip()
            if not callback_url:
                return error_response(
                    status.HTTP_400_BAD_REQUEST,
                    code="PLATFORM_CONFIG_INVALID",
                    message="Custom platform requires callback_url in config",
                    request_id=request_id
                )

            # Extract platform_api_key from config (try both field names)
            platform_api_key_value = cfg.get("platform_api_key") or cfg.get("api_key") or ""

            # Extract platform_open_id from request body
            platform_open_id = req_body.payload.get("platform_open_id") if isinstance(req_body.payload, dict) else None
            if not platform_open_id:
                # Try to resolve from visitor_id if not in payload
                try:
                    platform_open_id = await resolve_visitor_platform_open_id(visitor_id)
                except Exception:
                    platform_open_id = visitor_id  # Fallback to visitor_id

            # Generate unique IDs
            message_id = str(uuid.uuid4())
            client_msg_no_generated = req_body.client_msg_no or str(uuid.uuid4())

            # Build request payload
            custom_payload = {
                "platform_api_key": platform_api_key_value,
                "message_id": message_id,
                "channel_id": req_body.channel_id,
                "channel_type": req_body.channel_type,
                "platform_open_id": platform_open_id,
                "client_msg_no": client_msg_no_generated,
                "payload": req_body.payload,
            }

            # Send POST request to callback URL
            async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
                response = await client.post(callback_url, json=custom_payload)
                response.raise_for_status()

            logging.info(
                "[SEND] client_msg_no=%s custom platform message sent to %s",
                client_msg_no_generated,
                callback_url
            )
            return {
                "ok": True,
                "client_msg_no": client_msg_no_generated,
                "message_id": message_id,
                "message": "Message sent successfully to custom platform"
            }

        if platform_type == "wecom":
            corp_id = (cfg.get("corp_id") or "").strip()
            app_secret = (cfg.get("app_secret") or "").strip()
            if not (corp_id and app_secret):
                return error_response(status.HTTP_400_BAD_REQUEST, code="PLATFORM_CONFIG_INVALID", message="WeCom requires corp_id and app_secret", request_id=request_id)

            access_token = await wecom_get_access_token(corp_id, app_secret)
            # Resolve destination
            external_userid = await resolve_visitor_platform_open_id(visitor_id)
            open_kfid = await resolve_wecom_open_kfid(visitor_id, platform.id, db)

            if msg_type == 1:
                # Text
                content_text = str(payload.get("content") or "")
                await wecom_kf_send_msg(access_token, open_kfid=open_kfid, external_userid=external_userid, msgtype="text", content={"content": content_text[:2048]})
                logging.info("[SEND] client_msg_no=%s wecom text sent to %s", client_msg_no, external_userid)
                return {"ok": True, "client_msg_no": client_msg_no, "message": "Message sent successfully"}
            elif msg_type == 2:
                # Image
                url = str(payload.get("url") or "")
                if not url:
                    return error_response(status.HTTP_400_BAD_REQUEST, code="INVALID_PAYLOAD", message="Image url is required", request_id=request_id)
                # Download image
                download_url = _internalize_url(url)
                logging.info("[SEND] downloading image for wecom from: %s (original: %s)", download_url, url)
                async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
                    r = await client.get(download_url)
                    r.raise_for_status()
                    file_bytes = r.content
                    content_type = r.headers.get("content-type") or "image/jpeg"
                # Derive filename
                try:
                    filename = url.rsplit("/", 1)[-1] or "image.jpg"
                except Exception:
                    filename = "image.jpg"
                # Upload media and send
                media_id = await wecom_upload_temp_media(access_token, file_bytes, media_type="image", filename=filename, content_type=content_type)
                await wecom_kf_send_msg(access_token, open_kfid=open_kfid, external_userid=external_userid, msgtype="image", content={"media_id": media_id})
                logging.info("[SEND] client_msg_no=%s wecom image sent to %s", client_msg_no, external_userid)
                return {"ok": True, "client_msg_no": client_msg_no, "message": "Message sent successfully"}
            else:
                return error_response(status.HTTP_400_BAD_REQUEST, code="UNSUPPORTED_MESSAGE_TYPE", message=f"Unsupported payload type for WeCom: {msg_type}", request_id=request_id)

        if platform_type == "wecom_bot":
            # WeCom Bot (智能机器人) - direct message sending is not supported
            # Messages can only be sent as replies via response_url from incoming callbacks
            return error_response(
                status.HTTP_400_BAD_REQUEST,
                code="PLATFORM_TYPE_UNSUPPORTED",
                message="WeCom Bot does not support direct message sending. Messages can only be sent as replies to incoming messages.",
                request_id=request_id,
            )

        if platform_type == "email":
            # Resolve target email address for visitor
            target_email = await resolve_visitor_platform_open_id(visitor_id)
            # SMTP config: from per-platform configuration
            smtp_host = cfg.get("smtp_host")
            smtp_port = int(cfg.get("smtp_port", 587))
            smtp_username = cfg.get("smtp_username")
            smtp_password = cfg.get("smtp_password")
            smtp_use_tls = bool(cfg.get("smtp_use_tls", False))
            if not (smtp_host and smtp_port and smtp_username and smtp_password):
                return error_response(status.HTTP_400_BAD_REQUEST, code="PLATFORM_CONFIG_INVALID", message="Email requires SMTP configuration in platform config", request_id=request_id)
            # Only text currently supported via this API
            if msg_type != 1:
                return error_response(status.HTTP_400_BAD_REQUEST, code="UNSUPPORTED_MESSAGE_TYPE", message="Email supports only text (type=1)", request_id=request_id)
            content_text = str(payload.get("content") or "")
            from app.domain.services.adapters.email import EmailAdapter  # local import to avoid circulars
            adapter = EmailAdapter(
                smtp_host=smtp_host,
                smtp_port=smtp_port,
                smtp_username=smtp_username,
                smtp_password=smtp_password,
                smtp_use_tls=smtp_use_tls,
                to_addr=target_email,
                from_addr=smtp_username,
                subject="",
            )
            await adapter.send_final({"text": content_text})
            logging.info("[SEND] client_msg_no=%s email sent to %s", client_msg_no, target_email)
            return {"ok": True, "client_msg_no": client_msg_no, "message": "Message sent successfully"}

        if platform_type == "telegram":
            # Get bot token and visitor's chat_id
            bot_token = (cfg.get("bot_token") or "").strip()
            if not bot_token:
                return error_response(
                    status.HTTP_400_BAD_REQUEST,
                    code="PLATFORM_CONFIG_INVALID",
                    message="Telegram requires bot_token in config",
                    request_id=request_id,
                )
            
            # Resolve target chat_id for visitor
            chat_id = await resolve_visitor_platform_open_id(visitor_id)
            if not chat_id:
                return error_response(
                    status.HTTP_400_BAD_REQUEST,
                    code="VISITOR_NOT_FOUND",
                    message="Could not resolve Telegram chat_id for visitor",
                    request_id=request_id,
                )
            
            if msg_type == 1:
                # Text message
                content_text = str(payload.get("content") or "")
                if not content_text:
                    return error_response(
                        status.HTTP_400_BAD_REQUEST,
                        code="INVALID_PAYLOAD",
                        message="Text content is required",
                        request_id=request_id,
                    )
                
                from app.api.telegram_utils import telegram_send_text
                result = await telegram_send_text(
                    bot_token=bot_token,
                    chat_id=chat_id,
                    text=content_text[:4096],
                )
                
                if result.get("ok"):
                    logging.info("[SEND] client_msg_no=%s telegram text sent to %s", client_msg_no, chat_id)
                    return {"ok": True, "client_msg_no": client_msg_no, "message": "Message sent successfully"}
                else:
                    return error_response(
                        status.HTTP_502_BAD_GATEWAY,
                        code="TELEGRAM_ERROR",
                        message=result.get("description", "Unknown Telegram error"),
                        request_id=request_id,
                    )
            elif msg_type == 2:
                # Image
                url = str(payload.get("url") or "")
                if not url:
                    return error_response(
                        status.HTTP_400_BAD_REQUEST,
                        code="INVALID_PAYLOAD",
                        message="Image url is required",
                        request_id=request_id,
                    )
                
                # Download image first (Telegram servers might not be able to access local URLs)
                try:
                    download_url = _internalize_url(url)
                    logging.info("[SEND] downloading image for telegram from: %s (original: %s)", download_url, url)
                    async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
                        r = await client.get(download_url)
                        r.raise_for_status()
                        file_bytes = r.content
                except Exception as e:
                    logging.error("[SEND] failed to download image for telegram: %s", e)
                    return error_response(
                        status.HTTP_400_BAD_REQUEST,
                        code="IMAGE_DOWNLOAD_FAILED",
                        message=str(e),
                        request_id=request_id,
                    )
                
                from app.api.telegram_utils import telegram_send_photo
                result = await telegram_send_photo(
                    bot_token=bot_token,
                    chat_id=chat_id,
                    photo=file_bytes,
                )
                
                if result.get("ok"):
                    logging.info("[SEND] client_msg_no=%s telegram photo sent to %s", client_msg_no, chat_id)
                    return {"ok": True, "client_msg_no": client_msg_no, "message": "Message sent successfully"}
                else:
                    return error_response(
                        status.HTTP_502_BAD_GATEWAY,
                        code="TELEGRAM_ERROR",
                        message=result.get("description", "Unknown Telegram error"),
                        request_id=request_id,
                    )
            else:
                return error_response(
                    status.HTTP_400_BAD_REQUEST,
                    code="UNSUPPORTED_MESSAGE_TYPE",
                    message=f"Telegram currently supports only text (type=1), got: {msg_type}",
                    request_id=request_id,
                )

        if platform_type == "slack":
            # Get bot token and visitor's Slack user ID/channel
            bot_token = (cfg.get("bot_token") or "").strip()
            if not bot_token:
                return error_response(
                    status.HTTP_400_BAD_REQUEST,
                    code="PLATFORM_CONFIG_INVALID",
                    message="Slack requires bot_token in config",
                    request_id=request_id,
                )
            
            # Resolve target user_id/channel for visitor
            target_id = await resolve_visitor_platform_open_id(visitor_id)
            if not target_id:
                return error_response(
                    status.HTTP_400_BAD_REQUEST,
                    code="VISITOR_NOT_FOUND",
                    message="Could not resolve Slack user_id for visitor",
                    request_id=request_id,
                )
            
            if msg_type == 1:
                # Text message
                content_text = str(payload.get("content") or "")
                if not content_text:
                    return error_response(
                        status.HTTP_400_BAD_REQUEST,
                        code="INVALID_PAYLOAD",
                        message="Text content is required",
                        request_id=request_id,
                    )
                
                result = await slack_send_text(
                    bot_token=bot_token,
                    channel=target_id,
                    text=content_text,
                )
                
                if result.get("ok"):
                    logging.info("[SEND] client_msg_no=%s slack text sent to %s", client_msg_no, target_id)
                    return {"ok": True, "client_msg_no": client_msg_no, "message": "Message sent successfully"}
                else:
                    return error_response(
                        status.HTTP_502_BAD_GATEWAY,
                        code="SLACK_ERROR",
                        message=result.get("error", "Unknown Slack error"),
                        request_id=request_id,
                    )
            elif msg_type == 2:
                # Image
                url = str(payload.get("url") or "")
                if not url:
                    return error_response(
                        status.HTTP_400_BAD_REQUEST,
                        code="INVALID_PAYLOAD",
                        message="Image url is required",
                        request_id=request_id,
                    )
                
                # Download image
                try:
                    download_url = _internalize_url(url)
                    logging.info("[SEND] downloading image for slack from: %s (original: %s)", download_url, url)
                    async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
                        r = await client.get(download_url)
                        r.raise_for_status()
                        file_bytes = r.content
                except Exception as e:
                    logging.error("[SEND] failed to download image for slack: %s", e)
                    return error_response(
                        status.HTTP_400_BAD_REQUEST,
                        code="IMAGE_DOWNLOAD_FAILED",
                        message=str(e),
                        request_id=request_id,
                    )
                
                # Derive filename
                try:
                    filename = url.rsplit("/", 1)[-1] or "image.png"
                    if "?" in filename:
                        filename = filename.split("?")[0]
                except Exception:
                    filename = "image.png"
                
                # Slack files_upload_v2 requires a real channel ID (starts with D, C, G)
                # If target_id is a User ID (starts with U), resolve it to a DM channel ID
                if target_id.startswith("U"):
                    target_id = await slack_get_dm_channel(bot_token, target_id)

                result = await slack_send_file(
                    bot_token=bot_token,
                    channel=target_id,
                    file_bytes=file_bytes,
                    filename=filename,
                    initial_comment=str(payload.get("content") or ""),
                )
                
                if result.get("ok"):
                    logging.info("[SEND] client_msg_no=%s slack photo sent to %s", client_msg_no, target_id)
                    return {"ok": True, "client_msg_no": client_msg_no, "message": "Message sent successfully"}
                else:
                    return error_response(
                        status.HTTP_502_BAD_GATEWAY,
                        code="SLACK_ERROR",
                        message=result.get("error", "Unknown Slack error"),
                        request_id=request_id,
                    )
            else:
                return error_response(
                    status.HTTP_400_BAD_REQUEST,
                    code="UNSUPPORTED_MESSAGE_TYPE",
                    message=f"Slack supports text(1) and image(2), got: {msg_type}",
                    request_id=request_id,
                )

        return error_response(status.HTTP_400_BAD_REQUEST, code="PLATFORM_TYPE_UNSUPPORTED", message=f"Unsupported platform type: {platform.type}", request_id=request_id)

    except httpx.HTTPStatusError as e:
        logging.error("[SEND] HTTP error: %s", e)
        return error_response(status.HTTP_502_BAD_GATEWAY, code="HTTP_ERROR", message=str(e), request_id=request_id)
    except Exception as e:
        logging.error("[SEND] error: %s", e)
        return error_response(status.HTTP_500_INTERNAL_SERVER_ERROR, code="SEND_FAILED", message=str(e), request_id=request_id)
