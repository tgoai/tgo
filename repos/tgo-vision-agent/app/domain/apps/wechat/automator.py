"""WeChat automator implementation.

Simplified version that delegates to AgentLoop for all complex logic.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.domain.base.app_automator import BaseAppAutomator, AppAutomatorFactory

if TYPE_CHECKING:
    from app.domain.agent.agent_loop import AgentLoop

logger = logging.getLogger(__name__)


class WeChatAutomator(BaseAppAutomator):
    """WeChat-specific automator.

    Provides WeChat-specific configuration while delegating
    actual automation logic to AgentLoop.
    """

    app_type = "wechat"

    # Package names
    ANDROID_PACKAGE = "com.tencent.mm"
    DISPLAY_NAME = "微信"

    def get_app_package_name(self) -> str:
        """Get WeChat package name."""
        return self.ANDROID_PACKAGE

    def get_app_display_name(self) -> str:
        """Get WeChat display name."""
        return self.DISPLAY_NAME


# Register the automator
AppAutomatorFactory.register("wechat", WeChatAutomator)
