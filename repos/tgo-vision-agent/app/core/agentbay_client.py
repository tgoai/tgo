"""AgentBay client factory and management."""
from __future__ import annotations

import logging
from typing import Optional

from app.core.config import settings
from app.adapters.agentbay.mobile_controller import MobileController
from app.adapters.agentbay.desktop_controller import DesktopController
from app.domain.ports import AgentBayController

logger = logging.getLogger(__name__)


class AgentBayClientFactory:
    """Factory for creating AgentBay controller instances.
    
    Controllers are cached by (api_key, environment_type) to ensure
    session data is shared across requests using the same credentials.
    """

    # Cache controllers by (api_key, environment_type) tuple
    _controllers: dict[tuple[str, str], AgentBayController] = {}

    @classmethod
    def get_controller(
        cls,
        environment_type: str,
        api_key: Optional[str] = None,
    ) -> AgentBayController:
        """Get an AgentBay controller for the specified environment type.

        Controllers are cached by API key to ensure session data is shared.

        Args:
            environment_type: "mobile" or "desktop"
            api_key: Optional API key (uses settings if not provided)

        Returns:
            AgentBayController instance (cached)

        Raises:
            ValueError: If environment_type is invalid
        """
        key = api_key or settings.agentbay_api_key

        if not key:
            raise ValueError(
                "AgentBay API key not configured. "
                "Set TGO_AGENTBAY_API_KEY environment variable."
            )

        if environment_type not in ("mobile", "desktop"):
            raise ValueError(
                f"Invalid environment type: {environment_type}. "
                "Must be 'mobile' or 'desktop'."
            )

        cache_key = (key, environment_type)
        
        if cache_key not in cls._controllers:
            if environment_type == "mobile":
                cls._controllers[cache_key] = MobileController(api_key=key)
            else:
                cls._controllers[cache_key] = DesktopController(api_key=key)
            logger.debug(f"Created new {environment_type} controller for API key")

        return cls._controllers[cache_key]

    @classmethod
    def create_controller(
        cls,
        environment_type: str,
        api_key: str,
    ) -> AgentBayController:
        """Get or create an AgentBay controller instance.

        This method now returns a cached instance (same as get_controller)
        to ensure session data is shared across all operations.

        Args:
            environment_type: "mobile" or "desktop"
            api_key: AgentBay API key

        Returns:
            AgentBayController instance (cached by api_key)
        """
        return cls.get_controller(environment_type=environment_type, api_key=api_key)

    @classmethod
    def reset(cls) -> None:
        """Reset the factory state (for testing)."""
        cls._controllers.clear()
