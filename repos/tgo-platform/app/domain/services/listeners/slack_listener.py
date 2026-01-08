"""Slack Bot message consumer using Socket Mode.

This module implements a Socket Mode approach for Slack messages:
- Uses Slack's Socket Mode (WebSocket) instead of HTTP webhooks
- Suitable for local development or servers behind firewalls
- No public HTTPS endpoint required
- Uses synchronous HTTP calls to tgo-api to avoid asyncio event loop conflicts

Requires:
- Bot Token (xoxb-...) with appropriate scopes
- App-Level Token (xapp-...) with connections:write scope
"""
from __future__ import annotations

import asyncio
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import requests
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import settings
from app.db.models import Platform


class SlackPlatformConfig(BaseModel):
    """Per-platform Slack configuration stored in Platform.config when type='slack'."""

    bot_token: str = ""        # Bot User OAuth Token (xoxb-...)
    app_token: str = ""        # App-Level Token for Socket Mode (xapp-...)
    signing_secret: str = ""   # Signing secret for webhook verification (optional)


@dataclass
class _SlackPlatformEntry:
    id: uuid.UUID
    project_id: uuid.UUID
    api_key: str | None
    cfg: SlackPlatformConfig


class SlackChannelListener:
    """Slack Bot consumer using Socket Mode (WebSocket).

    This approach:
    1. Connects to Slack via WebSocket using App-Level Token
    2. Receives events in real-time (no public endpoint needed)
    3. Sends messages to tgo-api via synchronous HTTP (avoids asyncio conflicts)
    4. tgo-api handles visitor registration, chat processing, and reply sending
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        normalizer: Any,  # Not used directly anymore
        tgo_api_client: Any,  # Not used directly anymore
        sse_manager: Any,  # Not used directly anymore
    ) -> None:
        self._session_factory = session_factory
        self._stop_event = asyncio.Event()
        self._socket_handlers: dict[uuid.UUID, Any] = {}  # Platform ID -> SocketModeHandler
        self._handler_threads: dict[uuid.UUID, threading.Thread] = {}

    async def start(self) -> None:
        """Start Socket Mode handlers for all active Slack platforms."""
        platforms = await self._load_active_slack_platforms()
        print(f"[SLACK] Starting listeners for {len(platforms)} platforms")

        for platform in platforms:
            await self._start_platform_handler(platform)

    async def stop(self) -> None:
        """Stop all Socket Mode handlers."""
        self._stop_event.set()
        for platform_id, handler in self._socket_handlers.items():
            try:
                handler.close()
                print(f"[SLACK] Stopped handler for platform {platform_id}")
            except Exception as e:
                print(f"[SLACK] Error stopping handler for {platform_id}: {e}")
        self._socket_handlers.clear()

    async def reload_platform(self, platform_id: str) -> bool:
        """Hot-reload a single platform (legacy, use reload_platform_with_config)."""
        return False
    
    async def reload_platform_with_config(
        self,
        platform_id: str,
        project_id: str,
        api_key: str | None,
        bot_token: str,
        app_token: str,
        signing_secret: str | None = None,
    ) -> bool:
        """Hot-reload a Slack platform with config passed directly from tgo-api."""
        platform_uuid = uuid.UUID(platform_id)
        project_uuid = uuid.UUID(project_id)
        
        # Stop existing handler if any
        await self.stop_platform(platform_id)
        
        if not bot_token or not app_token:
            print(f"[SLACK] reload_platform_with_config: platform {platform_id} missing bot_token or app_token")
            return False
        
        try:
            cfg = SlackPlatformConfig(
                bot_token=bot_token,
                app_token=app_token,
                signing_secret=signing_secret or "",
            )
            platform_entry = _SlackPlatformEntry(
                id=platform_uuid,
                project_id=project_uuid,
                api_key=api_key,
                cfg=cfg,
            )
            await self._start_platform_handler(platform_entry)
            print(f"[SLACK] reload_platform_with_config: successfully started handler for {platform_id}")
            return True
        except Exception as e:
            print(f"[SLACK] reload_platform_with_config: failed to start handler for {platform_id}: {e}")
            return False
    
    async def stop_platform(self, platform_id: str) -> bool:
        """Stop a single platform's listener."""
        platform_uuid = uuid.UUID(platform_id)
        
        if platform_uuid not in self._socket_handlers:
            return False
        
        try:
            handler = self._socket_handlers[platform_uuid]
            handler.close()
            del self._socket_handlers[platform_uuid]
            if platform_uuid in self._handler_threads:
                del self._handler_threads[platform_uuid]
            print(f"[SLACK] stop_platform: stopped handler for {platform_id}")
            return True
        except Exception as e:
            print(f"[SLACK] stop_platform: error stopping handler for {platform_id}: {e}")
            return False

    async def _load_active_slack_platforms(self) -> list[_SlackPlatformEntry]:
        """Load all active Slack platforms from database."""
        async with self._session_factory() as session:
            rows = (
                await session.execute(
                    select(Platform.id, Platform.project_id, Platform.api_key, Platform.config)
                    .where(Platform.is_active.is_(True), Platform.type == "slack")
                )
            ).all()

        platforms: list[_SlackPlatformEntry] = []
        for pid, project_id, api_key, cfg_dict in rows:
            try:
                cfg = SlackPlatformConfig(**(cfg_dict or {}))
                if not cfg.bot_token or not cfg.app_token:
                    print(f"[SLACK] Skip platform {pid}: missing bot_token or app_token")
                    continue
                platforms.append(_SlackPlatformEntry(
                    id=pid,
                    project_id=project_id,
                    api_key=api_key,
                    cfg=cfg,
                ))
            except Exception as e:
                print(f"[SLACK] Skip platform {pid}: invalid config: {e}")
        return platforms

    async def _start_platform_handler(self, platform: _SlackPlatformEntry) -> None:
        """Start Socket Mode handler for a single platform."""
        try:
            from slack_bolt import App
            from slack_bolt.adapter.socket_mode import SocketModeHandler

            # Create Bolt App
            app = App(
                token=platform.cfg.bot_token,
                signing_secret=platform.cfg.signing_secret or None,
            )

            # Register message handlers - using synchronous processing
            @app.event("message")
            def handle_message(event, say, client):
                """Handle incoming messages (DMs and channel mentions)."""
                print(f"[SLACK] Raw event received: {event}")
                self._process_slack_message_sync(platform, event, client)

            @app.event("app_mention")
            def handle_mention(event, say, client):
                """Handle @mentions of the bot."""
                self._process_slack_message_sync(platform, event, client)

            # Create Socket Mode handler
            handler = SocketModeHandler(app, platform.cfg.app_token)

            # Store handler
            self._socket_handlers[platform.id] = handler

            # Start handler in a separate thread (Socket Mode is blocking)
            def run_handler():
                try:
                    handler.start()
                except Exception as e:
                    print(f"[SLACK] Handler error for platform {platform.id}: {e}")

            thread = threading.Thread(target=run_handler, daemon=True)
            thread.start()
            self._handler_threads[platform.id] = thread

            print(f"[SLACK] Started Socket Mode handler for platform {platform.id}")

        except Exception as e:
            print(f"[SLACK] Failed to start handler for platform {platform.id}: {e}")

    def _process_slack_message_sync(
        self,
        platform: _SlackPlatformEntry,
        event: dict[str, Any],
        client: Any,
    ) -> None:
        """Process an incoming Slack message event using synchronous HTTP calls."""
        try:
            # Extract message data
            user_id = event.get("user")
            channel = event.get("channel")
            text = event.get("text", "")
            ts = event.get("ts")
            thread_ts = event.get("thread_ts")
            files = event.get("files", [])

            # Ignore bot messages to prevent loops
            if event.get("bot_id") or event.get("subtype") == "bot_message":
                return

            if not user_id or (not text and not files):
                return

            msg_preview = text[:50] if text else f"[File: {len(files)} files]"
            print(f"[SLACK] Received message from {user_id} in {channel}: {msg_preview}...")

            # Get user info
            try:
                user_info_resp = client.users_info(user=user_id)
                user_data = user_info_resp.get("user", {})
                profile = user_data.get("profile", {})
                
                # Try multiple fields in order of preference
                display_name = profile.get("display_name") or ""
                real_name = user_data.get("real_name") or profile.get("real_name") or ""
                name = user_data.get("name") or ""  # Slack username
                
                # Use first non-empty value, falling back to user_id
                final_display_name = display_name.strip() or real_name.strip() or name.strip() or user_id
                
                avatar_url = profile.get("image_72") or profile.get("image_48") or ""
                
                print(f"[SLACK] User info for {user_id}: display_name='{display_name}', real_name='{real_name}', name='{name}', final='{final_display_name}'")
                display_name = final_display_name
            except Exception as e:
                print(f"[SLACK] Failed to get user info: {e}")
                display_name = user_id
                avatar_url = ""

            # 1. Register or get visitor to obtain channel_id (required for file upload)
            register_url = f"{settings.api_base_url.rstrip('/')}/v1/visitors/register"
            reg_payload = {
                "platform_api_key": platform.api_key or "",
                "platform_open_id": user_id,
                "nickname": display_name,
                "avatar_url": avatar_url,
            }
            channel_id = ""
            try:
                reg_resp = requests.post(register_url, json=reg_payload, timeout=10)
                if reg_resp.status_code in (200, 201):
                    channel_id = reg_resp.json().get("channel_id")
            except Exception as e:
                print(f"[SLACK] Failed to register visitor: {e}")

            # 2. Determine message type & handle file attachments
            msg_type = 1  # Default to text
            content = text

            if files:
                first_file = files[0]
                mimetype = first_file.get("mimetype", "")
                file_url = first_file.get("url_private")
                filename = first_file.get("name", "image.png")

                if mimetype.startswith("image/") and file_url and channel_id:
                    # Download from Slack
                    try:
                        slack_headers = {"Authorization": f"Bearer {platform.cfg.bot_token}"}
                        img_resp = requests.get(file_url, headers=slack_headers, timeout=30)
                        img_resp.raise_for_status()
                        file_bytes = img_resp.content

                        # Upload to TGO-API
                        upload_url = f"{settings.api_base_url.rstrip('/')}/v1/chat/upload"
                        files_payload = {
                            "file": (filename, file_bytes, mimetype)
                        }
                        data_payload = {
                            "channel_id": channel_id,
                            "channel_type": 251, # CHANNEL_TYPE_CUSTOMER_SERVICE
                            "platform_api_key": platform.api_key or "",
                        }
                        
                        ul_resp = requests.post(upload_url, files=files_payload, data=data_payload, timeout=30)
                        if ul_resp.status_code in (200, 201):
                            uploaded_url = ul_resp.json().get("file_url")
                            if uploaded_url:
                                msg_type = 2 # Image
                                # Use relative URL and let tgo-api resolve it via settings.API_BASE_URL
                                content = uploaded_url
                                print(f"[SLACK] Image processed and uploaded: {uploaded_url}")
                        else:
                            print(f"[SLACK] Image upload to TGO-API failed: {ul_resp.text}")
                    except Exception as e:
                        print(f"[SLACK] Image download/upload chain failed: {e}")

            # 3. Call tgo-api chat endpoint using synchronous HTTP
            api_url = f"{settings.api_base_url.rstrip('/')}/v1/chat/completion"
            
            payload = {
                "api_key": platform.api_key or "",
                "message": content,
                "from_uid": user_id,
                "visitor_name": display_name,
                "visitor_avatar": avatar_url,
                "msg_type": msg_type,
                "stream": False,
                "extra": {
                    "slack": {
                        "user_id": user_id,
                        "channel": channel,
                        "ts": ts,
                        "thread_ts": thread_ts,
                        "bot_token": platform.cfg.bot_token,
                    }
                }
            }

            try:
                resp = requests.post(
                    api_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=60,
                )
                
                if resp.status_code == 200:
                    result = resp.json()
                    print(f"[SLACK] API result: {result}")
                    
                    # Check if this is an AI disabled response - don't send to user
                    event_type = result.get("event_type")
                    success = result.get("success", True)  # Default to True for backwards compatibility
                    
                    if event_type in {"ai_disabled", "assist_mode"} or success is False:
                        print(f"[SLACK] AI disabled or error response, not sending to user: {event_type}")
                        return  # Silently ignore - customer service will handle via WuKongIM
                    
                    # Correctly extract reply from TGO native response
                    reply_content = result.get("message") or ""
                    
                    if reply_content:
                        # Send reply to Slack
                        try:
                            client.chat_postMessage(
                                channel=channel,
                                text=reply_content,
                                thread_ts=thread_ts or ts,  # Reply in thread if applicable
                            )
                            print(f"[SLACK] Reply sent to {channel}: {reply_content[:50]}...")
                        except Exception as e:
                            print(f"[SLACK] Failed to send reply: {e}")
                else:
                    print(f"[SLACK] API call failed with status {resp.status_code}: {resp.text[:200]}")
                    
            except Exception as e:
                print(f"[SLACK] Error calling tgo-api: {e}")

        except Exception as e:
            print(f"[SLACK] Error processing message: {e}")
            import traceback
            traceback.print_exc()
