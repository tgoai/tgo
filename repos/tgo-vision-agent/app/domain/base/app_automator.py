"""Simplified App Automator that delegates to AgentLoop.

This module provides the base class for app-specific automation,
now greatly simplified by delegating complex logic to AgentLoop.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from app.domain.agent.agent_loop import AgentLoop
    from app.domain.agent.entities import AgentContext, AgentResult

logger = logging.getLogger(__name__)


class BaseAppAutomator(ABC):
    """Simplified App Automator that delegates to AgentLoop.

    Each supported app (WeChat, Douyin, etc.) extends this class
    and provides app-specific configuration. The actual automation
    logic is handled by AgentLoop.
    """

    app_type: str  # Must be set by subclass

    def __init__(
        self,
        agent: "AgentLoop",
        session_id: str,
    ):
        """Initialize the automator.

        Args:
            agent: AgentLoop instance for executing tasks
            session_id: AgentBay session ID
        """
        self.agent = agent
        self.session_id = session_id

    @abstractmethod
    def get_app_package_name(self) -> str:
        """Get the application package name.

        Returns:
            Package name (e.g., "com.tencent.mm" for WeChat)
        """
        pass

    @abstractmethod
    def get_app_display_name(self) -> str:
        """Get the human-readable app name.

        Returns:
            Display name (e.g., "微信")
        """
        pass

    async def install_app(self) -> "AgentResult":
        """Install the app from app store.

        Delegates to AgentLoop with appropriate goal.
        """
        from app.domain.agent.entities import AgentContext

        goal = f"在应用商店中搜索并安装 {self.get_app_display_name()}"
        return await self.agent.run_single_task(
            goal=goal,
            app_type=self.app_type,
            app_package=self.get_app_package_name(),
            max_steps=30,
        )

    async def ensure_app_running(self) -> "AgentResult":
        """Ensure the app is running and in foreground.

        Delegates to AgentLoop with appropriate goal.
        """
        goal = f"确保 {self.get_app_display_name()} 应用正在运行"
        return await self.agent.run_single_task(
            goal=goal,
            app_type=self.app_type,
            app_package=self.get_app_package_name(),
            max_steps=10,
        )

    async def ensure_logged_in(self) -> "AgentResult":
        """Ensure the app is logged in.

        Delegates to AgentLoop with appropriate goal.
        """
        goal = f"确保 {self.get_app_display_name()} 已登录，如果看到二维码则等待扫码"
        return await self.agent.run_single_task(
            goal=goal,
            app_type=self.app_type,
            app_package=self.get_app_package_name(),
            max_steps=15,
        )

    async def navigate_to_chat_list(self) -> "AgentResult":
        """Navigate to the chat/conversation list.

        Delegates to AgentLoop with appropriate goal.
        """
        goal = f"在 {self.get_app_display_name()} 中导航到聊天/会话列表页面"
        return await self.agent.run_single_task(
            goal=goal,
            app_type=self.app_type,
            app_package=self.get_app_package_name(),
            max_steps=10,
        )

    async def detect_new_messages(self) -> "AgentResult":
        """Detect contacts with new messages.

        Delegates to AgentLoop with appropriate goal.
        """
        goal = f"在 {self.get_app_display_name()} 的聊天列表中检测有未读消息的联系人"
        return await self.agent.run_single_task(
            goal=goal,
            app_type=self.app_type,
            app_package=self.get_app_package_name(),
            max_steps=5,
        )

    async def send_message(self, contact: str, content: str) -> "AgentResult":
        """Send a message to a contact.

        Args:
            contact: Contact name or ID
            content: Message content

        Returns:
            AgentResult with success status
        """
        goal = f"在 {self.get_app_display_name()} 中向 {contact} 发送消息: {content}"
        return await self.agent.run_single_task(
            goal=goal,
            app_type=self.app_type,
            app_package=self.get_app_package_name(),
            max_steps=15,
        )

    async def read_messages_from(self, contact: str) -> "AgentResult":
        """Read messages from a specific contact.

        Args:
            contact: Contact name or ID

        Returns:
            AgentResult with messages in data field
        """
        goal = f"在 {self.get_app_display_name()} 中打开与 {contact} 的聊天，提取最近的消息"
        return await self.agent.run_single_task(
            goal=goal,
            app_type=self.app_type,
            app_package=self.get_app_package_name(),
            max_steps=10,
        )

    async def run_custom_task(
        self,
        goal: str,
        max_steps: int = 20,
    ) -> "AgentResult":
        """Run a custom task with the given goal.

        Args:
            goal: Task goal description
            max_steps: Maximum steps allowed

        Returns:
            AgentResult
        """
        return await self.agent.run_single_task(
            goal=goal,
            app_type=self.app_type,
            app_package=self.get_app_package_name(),
            max_steps=max_steps,
        )


class AppAutomatorFactory:
    """Factory for creating app-specific automators."""

    _registry: dict[str, type[BaseAppAutomator]] = {}

    @classmethod
    def register(cls, app_type: str, automator_class: type[BaseAppAutomator]) -> None:
        """Register an automator class for an app type."""
        cls._registry[app_type] = automator_class
        logger.info(f"Registered automator for app type: {app_type}")

    @classmethod
    def create(
        cls,
        app_type: str,
        agent: "AgentLoop",
        session_id: str,
    ) -> BaseAppAutomator:
        """Create an automator instance.

        Args:
            app_type: Application type (wechat, douyin, etc.)
            agent: AgentLoop instance
            session_id: AgentBay session ID

        Returns:
            App-specific automator instance
        """
        if app_type not in cls._registry:
            available = ", ".join(cls._registry.keys()) or "none"
            raise ValueError(f"Unknown app type: {app_type}. Available: {available}")

        return cls._registry[app_type](agent, session_id)

    @classmethod
    def get_supported_apps(cls) -> list[str]:
        """Get list of supported app types."""
        return list(cls._registry.keys())
