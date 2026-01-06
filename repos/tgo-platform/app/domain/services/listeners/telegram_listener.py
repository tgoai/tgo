"""Telegram Bot message consumer using getUpdates polling.

This module implements a polling-based approach for Telegram messages:
- Uses Telegram's getUpdates API (long polling) instead of webhook
- Suitable for local development or servers without public HTTPS endpoints
- Automatically deletes webhook when starting and uses polling mode
"""
from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import settings
from app.db.models import Platform, TelegramInbox
from app.domain.entities import NormalizedMessage
from app.domain.ports import MessageNormalizer, TgoApiClient, SSEManager
from app.domain.services.dispatcher import process_message
from app.infra.visitor_client import VisitorService
from app.api.telegram_utils import telegram_get_file, telegram_download_file

TELEGRAM_API_BASE = "https://api.telegram.org"


class TelegramPlatformConfig(BaseModel):
    """Per-platform Telegram Bot configuration stored in Platform.config when type='telegram'."""

    bot_token: str = ""                    # Bot token from @BotFather
    webhook_secret: str | None = None      # Optional secret_token for webhook verification

    # Polling configuration
    polling_interval_seconds: int = 1      # How often to poll getUpdates
    polling_timeout_seconds: int = 30      # Long polling timeout (Telegram recommends 30+)
    processing_batch_size: int = 10
    max_retry_attempts: int = 3


@dataclass
class _PlatformEntry:
    id: uuid.UUID
    project_id: uuid.UUID
    api_key: str | None
    cfg: TelegramPlatformConfig
    last_update_id: int = 0  # Track last processed update_id for this platform


class TelegramChannelListener:
    """Telegram Bot consumer using getUpdates long polling.

    This approach:
    1. Calls Telegram's getUpdates API to fetch new messages
    2. Processes each message via dispatcher
    3. Stores to TelegramInbox for audit/retry purposes
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        normalizer: MessageNormalizer,
        tgo_api_client: TgoApiClient,
        sse_manager: SSEManager,
    ) -> None:
        self._session_factory = session_factory
        self._normalizer = normalizer
        self._tgo_api_client = tgo_api_client
        self._sse_manager = sse_manager
        self._stop_event = asyncio.Event()
        self._consumer_task: asyncio.Task | None = None
        self._visitor_service = VisitorService(
            base_url=settings.api_base_url,
            cache_ttl_seconds=300,
            redis_url=settings.redis_url,
        )
        # Track last_update_id per platform to avoid duplicate processing
        self._platform_offsets: dict[uuid.UUID, int] = {}

    async def start(self) -> None:
        if self._consumer_task is None or self._consumer_task.done():
            self._consumer_task = asyncio.create_task(self._consumer_loop())

    async def stop(self) -> None:
        self._stop_event.set()
        if self._consumer_task:
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass

    async def _load_active_telegram_platforms(self) -> list[_PlatformEntry]:
        """Load all active Telegram platforms."""
        async with self._session_factory() as session:
            rows = (
                await session.execute(
                    select(Platform.id, Platform.project_id, Platform.api_key, Platform.config)
                    .where(Platform.is_active.is_(True), Platform.type == "telegram")
                )
            ).all()
        platforms: list[_PlatformEntry] = []
        for pid, project_id, api_key, cfg_dict in rows:
            try:
                cfg = TelegramPlatformConfig(**(cfg_dict or {}))
                if not cfg.bot_token:
                    print(f"[TELEGRAM] Skip platform {pid}: missing bot_token")
                    continue
                # Get last_update_id from memory or start at 0
                last_id = self._platform_offsets.get(pid, 0)
                platforms.append(_PlatformEntry(
                    id=pid,
                    project_id=project_id,
                    api_key=api_key,
                    cfg=cfg,
                    last_update_id=last_id,
                ))
            except Exception as e:
                print(f"[TELEGRAM] Skip platform {pid}: invalid config: {e}")
        return platforms

    async def _delete_webhook_if_exists(self, bot_token: str) -> None:
        """Delete any existing webhook to enable getUpdates mode."""
        try:
            url = f"{TELEGRAM_API_BASE}/bot{bot_token}/deleteWebhook"
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(url)
                result = resp.json()
                if result.get("ok"):
                    print(f"[TELEGRAM] Webhook deleted, switching to polling mode")
        except Exception as e:
            print(f"[TELEGRAM] Warning: Could not delete webhook: {e}")

    async def _get_updates(
        self,
        bot_token: str,
        offset: int,
        timeout: int = 30,
    ) -> list[dict[str, Any]]:
        """Call Telegram getUpdates API with long polling."""
        url = f"{TELEGRAM_API_BASE}/bot{bot_token}/getUpdates"
        params = {
            "offset": offset,
            "timeout": timeout,
            "allowed_updates": ["message", "edited_message"],
        }
        
        try:
            async with httpx.AsyncClient(timeout=timeout + 10) as client:
                resp = await client.get(url, params=params)
                result = resp.json()
                
                if result.get("ok"):
                    return result.get("result", [])
                else:
                    error_desc = result.get("description", "Unknown error")
                    print(f"[TELEGRAM] getUpdates error: {error_desc}")
                    return []
        except httpx.TimeoutException:
            # Normal for long polling when no messages
            return []
        except Exception as e:
            print(f"[TELEGRAM] getUpdates request failed: {e}")
            return []

    def _extract_message_data(self, update: dict[str, Any]) -> dict[str, Any] | None:
        """Extract message data from a Telegram Update object."""
        message = update.get("message") or update.get("edited_message")
        if not message:
            return None
        
        from_user = message.get("from", {})
        chat = message.get("chat", {})
        
        # Get message content (text, caption, or type indicator)
        content = ""
        msg_type = "text"
        
        if "text" in message:
            content = message["text"]
            msg_type = 1 # TEXT
        elif "photo" in message:
            # Picking the largest photo
            photos = message.get("photo", [])
            if photos:
                largest = photos[-1]
                content = message.get("caption") or "[Photo]"
                msg_type = 2 # IMAGE
                file_id = largest.get("file_id")
            else:
                content = "[Photo]"
                msg_type = 1
                file_id = None
        elif "document" in message:
            content = message.get("caption", "[Document]")
            msg_type = 3 # FILE
        elif "sticker" in message:
            content = message.get("sticker", {}).get("emoji", "[Sticker]")
            msg_type = 1
        elif "voice" in message:
            content = "[Voice message]"
            msg_type = 4 # VOICE
        elif "video" in message:
            content = message.get("caption", "[Video]")
            msg_type = 5 # VIDEO
        else:
            content = "[Unsupported message type]"
            msg_type = 1
        
        return {
            "update_id": update.get("update_id"),
            "message_id": message.get("message_id"),
            "from_user": str(from_user.get("id", "")),
            "from_username": from_user.get("username"),
            "from_display_name": " ".join(filter(None, [
                from_user.get("first_name"),
                from_user.get("last_name"),
            ])) or from_user.get("username") or str(from_user.get("id", "")),
            "chat_id": str(chat.get("id", "")),
            "chat_type": chat.get("type", "private"),
            "content": content,
            "msg_type": msg_type,
            "file_id": file_id if msg_type == 2 else None,
            "raw_payload": update,
            "date": message.get("date"),
        }

    async def _store_to_inbox(
        self,
        session: AsyncSession,
        platform: _PlatformEntry,
        msg_data: dict[str, Any],
    ) -> TelegramInbox:
        """Store message to TelegramInbox for audit purposes."""
        record = TelegramInbox(
            platform_id=platform.id,
            update_id=msg_data["update_id"],
            message_id=str(msg_data["message_id"]),
            from_user=msg_data["from_user"],
            from_username=msg_data.get("from_username"),
            from_display_name=msg_data.get("from_display_name"),
            chat_id=msg_data["chat_id"],
            chat_type=msg_data["chat_type"],
            msg_type=str(msg_data["msg_type"]),
            content=msg_data["content"],
            raw_payload=msg_data["raw_payload"],
            status="processing",
            fetched_at=datetime.now(timezone.utc),
        )
        session.add(record)
        await session.flush()
        return record

    def _build_mapped_message(self, platform: _PlatformEntry, msg_data: dict[str, Any]) -> dict[str, Any]:
        """Build the NormalizedMessage-like raw dict for downstream normalization."""
        telegram_ctx: dict[str, Any] = {
            "chat_id": msg_data["chat_id"],
            "chat_type": msg_data["chat_type"],
            "from_username": msg_data.get("from_username"),
            "from_display_name": msg_data.get("from_display_name"),
            "msg_type": msg_data["msg_type"],
            "bot_token": platform.cfg.bot_token,
        }

        return {
            "source": "telegram",
            "from_uid": msg_data["from_user"],
            "content": msg_data["content"] or "",
            "platform_api_key": platform.api_key or "",
            "platform_type": "telegram",
            "platform_id": str(platform.id),
            "extra": {
                "project_id": str(platform.project_id),
                "msg_type": msg_data["msg_type"],
                "telegram": telegram_ctx,
            },
        }

    async def _get_or_register_visitor(
        self,
        platform: _PlatformEntry,
        msg_data: dict[str, Any],
    ) -> tuple[Any | None, str | None, str | None]:
        """Visitor retrieval/registration with cache-first approach."""
        display_name: str | None = msg_data.get("from_display_name") or msg_data.get("from_username") or msg_data["from_user"]
        avatar_url: str | None = None
        visitor = None

        # Check cache first
        try:
            cache_key = self._visitor_service.make_cache_key(str(platform.project_id), "telegram", msg_data["from_user"])
            cached = await self._visitor_service.get_cached(cache_key)
            if cached:
                display_name = cached.nickname or cached.name or display_name
                avatar_url = cached.avatar_url
                return cached, display_name, avatar_url
        except Exception as e:
            print(f"[TELEGRAM] Visitor cache lookup failed for {platform.id}: {e}")

        # Register or get visitor via tgo-api
        if platform.api_key:
            try:
                visitor = await self._visitor_service.register_or_get(
                    platform_api_key=platform.api_key,
                    project_id=str(platform.project_id),
                    platform_type="telegram",
                    platform_open_id=msg_data["from_user"],
                    nickname=display_name,
                    avatar_url=avatar_url,
                )
            except Exception as e:
                print(f"[TELEGRAM] Visitor registration failed for {platform.id}: {e}")

        return visitor, display_name, avatar_url

    async def _process_update(
        self,
        platform: _PlatformEntry,
        update: dict[str, Any],
    ) -> None:
        """Process a single Telegram update."""
        msg_data = self._extract_message_data(update)
        if not msg_data:
            return
        
        print(f"[TELEGRAM] Processing message from {msg_data['from_display_name']} in {msg_data['chat_type']}: {msg_data['content'][:50]}...")

        async with self._session_factory() as db:
            try:
                # 1) Get/register visitor FIRST to get the official UUID from tgo-api
                visitor, display_name, avatar_url = await self._get_or_register_visitor(platform, msg_data)
                
                # 2) If it's an image, download from Telegram and upload to tgo-api
                if msg_data["msg_type"] == 2 and msg_data.get("file_id") and visitor:
                    try:
                        # a) Get file path from Telegram
                        file_info = await telegram_get_file(platform.cfg.bot_token, msg_data["file_id"])
                        if file_info.get("ok"):
                            file_path = file_info["result"].get("file_path")
                            if file_path:
                                # b) Download file bytes
                                file_bytes = await telegram_download_file(platform.cfg.bot_token, file_path)
                                
                                # c) Upload to tgo-api using the real visitor.channel_id
                                upload_url = f"{settings.api_base_url.rstrip('/')}/v1/chat/upload"
                                channel_id = visitor.channel_id or f"{visitor.id}-vtr"
                                
                                print(f"[TELEGRAM] Uploading image for visitor {visitor.id}, channel {channel_id}...")
                                async with httpx.AsyncClient(timeout=60) as client:
                                    files = {"file": ("image.jpg", file_bytes, "image/jpeg")}
                                    data = {
                                        "channel_id": channel_id,
                                        "channel_type": 251,  # CHANNEL_TYPE_CUSTOMER_SERVICE
                                        "platform_api_key": platform.api_key or "",
                                    }
                                    resp = await client.post(upload_url, data=data, files=files)
                                    if resp.status_code == 200:
                                        upload_result = resp.json()
                                        # Use "file_url" from ChatFileUploadResponse
                                        new_url = upload_result.get("file_url") or upload_result.get("url")
                                        if new_url:
                                            msg_data["content"] = new_url
                                            print(f"[TELEGRAM] Image uploaded successfully: {msg_data['content']}")
                                        else:
                                            print(f"[TELEGRAM] Image upload response missing URL: {upload_result}")
                                    else:
                                        print(f"[TELEGRAM] Failed to upload image to tgo-api (status {resp.status_code}): {resp.text}")
                    except Exception as e:
                        print(f"[TELEGRAM] Error handling image from Telegram: {e}")
                # Store to inbox for audit
                record = await self._store_to_inbox(db, platform, msg_data)
                
                # Build mapped message
                mapped_raw = self._build_mapped_message(platform, msg_data)
                
                # 3) Normalize and process
                if display_name or avatar_url:
                    extra = mapped_raw.get("extra") or {}
                    extra["visitor_profile"] = {"nickname": display_name, "avatar_url": avatar_url}
                    mapped_raw["extra"] = extra
                
                # Normalize and process
                msg: NormalizedMessage = await self._normalizer.normalize(mapped_raw)
                reply_text = await process_message(
                    msg=msg,
                    db=db,
                    tgo_api_client=self._tgo_api_client,
                    sse_manager=self._sse_manager,
                )
                
                # Mark as completed
                record.ai_reply = reply_text
                record.status = "completed"
                record.processed_at = datetime.now(timezone.utc)
                await db.commit()
                
                print(f"[TELEGRAM] Reply sent to {msg_data['chat_id']}")
                
            except Exception as e:
                print(f"[TELEGRAM] Processing failed: {e}")
                await db.rollback()

    async def _poll_platform(self, platform: _PlatformEntry) -> int:
        """Poll a single platform for new messages. Returns new offset."""
        offset = platform.last_update_id + 1 if platform.last_update_id else 0
        timeout = platform.cfg.polling_timeout_seconds
        
        updates = await self._get_updates(platform.cfg.bot_token, offset, timeout)
        
        new_offset = platform.last_update_id
        for update in updates:
            update_id = update.get("update_id", 0)
            if update_id > new_offset:
                new_offset = update_id
            
            try:
                await self._process_update(platform, update)
            except Exception as e:
                print(f"[TELEGRAM] Error processing update {update_id}: {e}")
        
        return new_offset

    async def _consumer_loop(self) -> None:
        """Main consumer loop - polls all active Telegram platforms."""
        print("[TELEGRAM] Consumer loop started (polling mode)")
        
        # Initial load and delete webhooks
        platforms = await self._load_active_telegram_platforms()
        for p in platforms:
            await self._delete_webhook_if_exists(p.cfg.bot_token)
        
        while not self._stop_event.is_set():
            try:
                platforms = await self._load_active_telegram_platforms()
                
                if not platforms:
                    await asyncio.sleep(5)
                    continue
                
                # Poll each platform concurrently
                tasks = []
                for p in platforms:
                    tasks.append(self._poll_platform(p))
                
                if tasks:
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    
                    # Update offsets
                    for i, p in enumerate(platforms):
                        if isinstance(results[i], int):
                            self._platform_offsets[p.id] = results[i]
                
                # Short sleep between polling cycles
                interval = platforms[0].cfg.polling_interval_seconds if platforms else 1
                await asyncio.sleep(max(0.5, interval))
                
            except Exception as e:
                print(f"[TELEGRAM] Consumer loop error: {e}")
                await asyncio.sleep(5)
        
        print("[TELEGRAM] Consumer loop stopped")
