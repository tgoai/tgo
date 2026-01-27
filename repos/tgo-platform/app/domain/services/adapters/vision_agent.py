"""Vision Agent adapter for platforms that use UI automation (WeChat Personal, etc.)."""
from __future__ import annotations

import logging
from typing import Optional

import httpx

from app.domain.entities import StreamEvent
from app.domain.services.adapters.base import BasePlatformAdapter

logger = logging.getLogger(__name__)


class VisionAgentAdapter(BasePlatformAdapter):
    """Adapter for sending messages via tgo-vision-agent service.

    This adapter is used for platforms that don't have an API and require
    UI automation (e.g., personal WeChat, Douyin, Xiaohongshu).

    The adapter sends messages to tgo-vision-agent which then uses
    VLM + AgentBay to automate the UI operations.
    """

    supports_stream: bool = False  # Vision Agent doesn't support streaming

    def __init__(
        self,
        vision_agent_url: str,
        platform_id: str,
        app_type: str,
        contact_id: str,
        contact_name: Optional[str] = None,
    ):
        """Initialize the Vision Agent adapter.

        Args:
            vision_agent_url: Base URL of tgo-vision-agent service
            platform_id: Platform ID from tgo-api
            app_type: Application type (wechat, douyin, xiaohongshu, etc.)
            contact_id: Contact ID within the application
            contact_name: Optional contact display name
        """
        self.vision_agent_url = vision_agent_url.rstrip("/")
        self.platform_id = platform_id
        self.app_type = app_type
        self.contact_id = contact_id
        self.contact_name = contact_name

    async def send_incremental(self, ev: StreamEvent) -> None:
        """Not supported - Vision Agent doesn't support streaming."""
        logger.debug("VisionAgentAdapter: incremental send not supported")

    async def send_final(self, content: dict) -> None:
        """Send the final message content via tgo-vision-agent.

        Args:
            content: Dictionary with "text" key containing the message
        """
        text = content.get("text", "")
        if not text:
            logger.warning("VisionAgentAdapter: empty message content, skipping")
            return

        payload = {
            "platform_id": self.platform_id,
            "app_type": self.app_type,
            "contact_id": self.contact_id,
            "content": text,
            "message_type": "text",
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.vision_agent_url}/v1/messages/send",
                    json=payload,
                )
                response.raise_for_status()
                result = response.json()

                if result.get("success"):
                    logger.info(
                        "VisionAgentAdapter: message sent to %s (%s)",
                        self.contact_name or self.contact_id,
                        self.app_type,
                    )
                else:
                    logger.error(
                        "VisionAgentAdapter: failed to send message: %s",
                        result.get("error", "unknown error"),
                    )

        except httpx.HTTPStatusError as e:
            logger.error(
                "VisionAgentAdapter: HTTP error %s: %s",
                e.response.status_code,
                e.response.text,
            )
        except Exception as e:
            logger.error("VisionAgentAdapter: failed to send message: %s", e)
