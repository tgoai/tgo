"""Port interfaces (protocols) for dependency injection.

Simplified interfaces for the new Agent architecture.
"""

from __future__ import annotations

from typing import Protocol, Optional


class AgentBayController(Protocol):
    """Protocol for AgentBay session controller."""

    async def create_session(
        self,
        environment_type: str,
        image_id: Optional[str] = None,
    ) -> str:
        """Create a new AgentBay session, return session ID."""
        ...

    async def restore_session(self, session_id: str) -> bool:
        """Restore/reconnect to an existing AgentBay session."""
        ...

    def has_session(self, session_id: str) -> bool:
        """Check if a session is loaded in memory."""
        ...

    async def delete_session(self, session_id: str) -> bool:
        """Delete/terminate an AgentBay session."""
        ...

    async def take_screenshot(self, session_id: str) -> bytes:
        """Take a screenshot of the current screen."""
        ...

    async def click(self, session_id: str, x: int, y: int) -> bool:
        """Click at the specified coordinates."""
        ...

    async def type_text(self, session_id: str, text: str) -> bool:
        """Type text into the current focused element."""
        ...

    async def swipe(
        self,
        session_id: str,
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int,
        duration_ms: int = 300,
    ) -> bool:
        """Swipe from start to end coordinates."""
        ...

    async def press_back(self, session_id: str) -> bool:
        """Press the back button."""
        ...

    async def launch_app(self, session_id: str, package_name: str) -> bool:
        """Launch an application by package name."""
        ...

    async def get_installed_apps(self, session_id: str) -> list[str]:
        """Get list of installed application package names."""
        ...


class MessageCallback(Protocol):
    """Protocol for message callback to tgo-platform."""

    async def notify_new_message(
        self,
        platform_id: str,
        contact_id: str,
        contact_name: str,
        message_content: str,
        message_type: str,
    ) -> bool:
        """Notify tgo-platform about a new incoming message."""
        ...

    async def notify_status_change(
        self,
        platform_id: str,
        status: str,
        message: str,
    ) -> bool:
        """Notify tgo-platform about app status change."""
        ...
