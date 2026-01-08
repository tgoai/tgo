"""Slack Bot outbound adapter.

Sends messages to Slack using the Web API chat.postMessage endpoint.
"""
from __future__ import annotations

from app.domain.entities import StreamEvent
from app.domain.services.adapters.base import BasePlatformAdapter
from app.core.config import settings

from app.api.slack_utils import slack_send_text


class SlackAdapter(BasePlatformAdapter):
    """Outbound adapter for Slack Bot.

    - Non-streaming: sends the final aggregated content via chat.postMessage API
    - Uses channel ID from incoming message to reply
    - Requires bot_token for authentication

    Docs:
    - chat.postMessage: https://api.slack.com/methods/chat.postMessage
    """

    supports_stream = False

    def __init__(
        self,
        bot_token: str,
        channel: str,
        thread_ts: str | None = None,
        http_timeout: int | None = None,
    ) -> None:
        """Initialize Slack adapter.

        Args:
            bot_token: Bot User OAuth Token (xoxb-...)
            channel: Target channel ID or user ID for DM
            thread_ts: Optional thread timestamp for threaded replies
            http_timeout: Request timeout in seconds
        """
        self.bot_token = bot_token
        self.channel = channel
        self.thread_ts = thread_ts
        self.http_timeout = http_timeout or settings.request_timeout_seconds

    async def send_incremental(self, ev: StreamEvent) -> None:
        # Slack adapter does not support streaming output; ignore incremental events
        return

    async def send_final(self, content: dict) -> None:
        """Send final message to Slack channel/DM.

        Args:
            content: Dict with 'text' key containing the message

        Raises:
            RuntimeError: If bot_token or channel is missing
        """
        text = (content or {}).get("text") or ""
        print(f"[SLACK ADAPTER] send_final called with text length: {len(text)}")

        if not text:
            print("[SLACK ADAPTER] Empty text, skipping send")
            return

        if not self.bot_token:
            raise RuntimeError("Slack adapter requires bot_token")

        if not self.channel:
            raise RuntimeError("Slack adapter requires channel")

        print(f"[SLACK ADAPTER] Sending to channel={self.channel}: {text[:100]}...")

        # Send text message via Slack Web API
        result = await slack_send_text(
            bot_token=self.bot_token,
            channel=self.channel,
            text=text,
            thread_ts=self.thread_ts,
        )

        if result:
            print(f"[SLACK ADAPTER] Reply sent to {self.channel}")
        else:
            print(f"[SLACK ADAPTER] Failed to send reply to {self.channel}")
