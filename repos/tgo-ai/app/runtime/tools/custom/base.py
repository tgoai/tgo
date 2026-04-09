"""Base utilities for agent-scoped custom tools.

Provides common functionality:
- Event posting to API Service
- UUID validation
- Error handling with friendly Chinese messages
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional
import uuid

import httpx

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# HTTP client configuration
DEFAULT_TIMEOUT = httpx.Timeout(10.0, connect=5.0, read=10.0)
EVENTS_ENDPOINT = "/internal/ai/events"


@dataclass
class ToolContext:
    """Context for agent-scoped tools."""

    agent_id: str
    session_id: Optional[str]
    user_id: Optional[str]
    project_id: Optional[str] = None
    request_id: Optional[str] = None

    def build_metadata(self, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Build payload metadata with tool context."""
        metadata = {**(extra or {}), "agent_id": self.agent_id, "user_id": self.user_id}
        if self.project_id:
            metadata["project_id"] = self.project_id
        if self.session_id:
            metadata["session_id"] = self.session_id
        if self.request_id:
            metadata["request_id"] = self.request_id
        return metadata



def uuid_or_none(value: Optional[str]) -> Optional[str]:
    """Convert value to UUID string, or None if invalid."""
    if not value:
        return None
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, TypeError):
        return None


@dataclass
class EventResult:
    """Result of posting an event."""

    success: bool
    message: str


class EventClient:
    """Client for posting events to API Service."""

    def __init__(self, ctx: ToolContext):
        self.ctx = ctx
        self._base_url = getattr(settings, "api_service_url", None)

    @property
    def is_configured(self) -> bool:
        """Check if API service URL is configured."""
        return bool(self._base_url)

    async def post_event(
        self,
        event_type: str,
        payload: Dict[str, Any],
        *,
        error_messages: Dict[str, str],
    ) -> EventResult:
        """Post an event to API Service.

        Args:
            event_type: Event type (e.g., "visitor_info.update")
            payload: Event payload data
            error_messages: Dict with keys 'not_configured', 'http_error', 'unexpected_error', 'api_error'

        Returns:
            EventResult with success status and message
        """
        if not self.is_configured:
            logger.warning(
                "api_service_url not configured; skipping API Service event call",
                extra={"agent_id": self.ctx.agent_id, "session_id": self.ctx.session_id},
            )
            return EventResult(success=False, message=error_messages["not_configured"])

        event_payload = {
            "event_type": event_type,
            "user_id": self.ctx.user_id,
            "payload": {
                **payload,
                "session_id": self.ctx.session_id,
                "metadata": self.ctx.build_metadata(payload.get("metadata")),
            },
        }
        # Remove nested metadata from payload if it was provided
        if "metadata" in event_payload["payload"]:
            del event_payload["payload"]["metadata"]
        event_payload["payload"]["metadata"] = self.ctx.build_metadata(payload.get("metadata"))

        url = f"{self._base_url.rstrip('/')}{EVENTS_ENDPOINT}"
        headers = {"Content-Type": "application/json"}

        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                resp = await client.post(url, json=event_payload, headers=headers)

                if resp.status_code >= 400:
                    self._log_api_error(event_type, resp)
                    return EventResult(success=False, message=error_messages["api_error"])

        except httpx.HTTPError as exc:
            logger.error(f"HTTP error sending {event_type} event", exc_info=exc)
            return EventResult(success=False, message=error_messages["http_error"])
        except Exception as exc:
            logger.error(f"Unexpected error sending {event_type} event", exc_info=exc)
            return EventResult(success=False, message=error_messages["unexpected_error"])

        logger.info(
            f"{event_type} event ingested",
            extra={"agent_id": self.ctx.agent_id, "session_id": self.ctx.session_id},
        )
        return EventResult(success=True, message="")

    def _log_api_error(self, event_type: str, resp: httpx.Response) -> None:
        """Log API error details."""
        try:
            details = resp.json()
        except Exception:
            details = {"text": resp.text}
        logger.error(
            f"Failed to ingest {event_type} event",
            extra={"status": resp.status_code, "details": details},
        )
