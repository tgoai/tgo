"""Platform callback service for notifying tgo-platform about new messages."""
from __future__ import annotations

import logging
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class PlatformCallbackService:
    """Service for sending callbacks to tgo-platform.

    When new messages are detected via UI automation, this service
    notifies tgo-platform so the message can be processed by AI.
    """

    def __init__(
        self,
        platform_url: Optional[str] = None,
        timeout: float = 30.0,
    ):
        self.platform_url = (platform_url or settings.platform_url).rstrip("/")
        self.timeout = timeout

    async def notify_new_message(
        self,
        platform_id: str,
        platform_api_key: str,
        contact_id: str,
        contact_name: str,
        message_content: str,
        message_type: str = "text",
        app_type: str = "wechat",
    ) -> bool:
        """Notify tgo-platform about a new incoming message.

        This will trigger the AI processing pipeline in tgo-platform,
        which will route the message to the configured AI agent.

        Args:
            platform_id: Platform ID from tgo-api
            platform_api_key: API key for the platform
            contact_id: Contact identifier
            contact_name: Contact display name
            message_content: Message content
            message_type: Type of message (text, image, etc.)
            app_type: Application type (wechat, douyin, etc.)

        Returns:
            True if callback was successful
        """
        # Build normalized message payload
        # This matches the expected format in tgo-platform
        payload = {
            "platform_id": platform_id,
            "platform_type": f"{app_type}_personal",  # e.g., "wechat_personal"
            "from_uid": contact_id,
            "content": message_content,
            "msg_type": 1 if message_type == "text" else 2,  # 1=text, 2=other
            "extra": {
                "contact_name": contact_name,
                "app_type": app_type,
                "source": "vision_agent",
            },
        }

        headers = {
            "Content-Type": "application/json",
            "X-Platform-API-Key": platform_api_key,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.platform_url}/internal/vision-agent/inbound",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()

                logger.info(
                    f"Notified tgo-platform about message from {contact_name} "
                    f"({contact_id}) on platform {platform_id}"
                )
                return True

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Platform callback failed with status {e.response.status_code}: "
                f"{e.response.text}"
            )
            return False
        except Exception as e:
            logger.error(f"Platform callback failed: {e}")
            return False

    async def notify_login_status_change(
        self,
        platform_id: str,
        status: str,
        qr_code_base64: Optional[str] = None,
    ) -> bool:
        """Notify tgo-platform about a login status change.

        This can be used to update the platform configuration in tgo-api
        with the current login status.

        Args:
            platform_id: Platform ID
            status: New login status (logged_in, qr_pending, offline, etc.)
            qr_code_base64: Optional QR code image as base64

        Returns:
            True if callback was successful
        """
        payload = {
            "platform_id": platform_id,
            "login_status": status,
        }
        if qr_code_base64:
            payload["qr_code_base64"] = qr_code_base64

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.platform_url}/v1/vision-agent/login-status",
                    json=payload,
                )
                response.raise_for_status()

                logger.info(
                    f"Notified tgo-platform about login status change "
                    f"for platform {platform_id}: {status}"
                )
                return True

        except httpx.HTTPStatusError as e:
            # This endpoint might not exist yet, so just log warning
            logger.warning(
                f"Login status callback failed with status {e.response.status_code}"
            )
            return False
        except Exception as e:
            logger.warning(f"Login status callback failed: {e}")
            return False

    async def notify_status_change(
        self,
        platform_id: str,
        status: str,
        message: str,
    ) -> bool:
        """Notify tgo-platform about app status change.

        This is a general status notification that can be used for various
        app states like not_installed, installing, not_running, logged_in, etc.

        Args:
            platform_id: Platform ID from tgo-api
            status: New status string (e.g., "app_not_installed", "logged_in")
            message: Human-readable status message

        Returns:
            True if notification was successful
        """
        payload = {
            "platform_id": platform_id,
            "status": status,
            "message": message,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.platform_url}/internal/vision-agent/status",
                    json=payload,
                )
                response.raise_for_status()

                logger.info(
                    f"Notified tgo-platform about status change "
                    f"for platform {platform_id}: {status} - {message}"
                )
                return True

        except httpx.HTTPStatusError as e:
            # This endpoint might not exist yet, so just log warning
            logger.warning(
                f"Status change callback failed with status {e.response.status_code}: "
                f"{e.response.text}"
            )
            return False
        except Exception as e:
            logger.warning(f"Status change callback failed: {e}")
            return False
