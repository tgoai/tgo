"""Agent entities for ReAct-style UI automation.

This module defines all data classes used by the AgentLoop:
- Observation: Result from VisionClient analyzing a screenshot
- Action: Decision from ReasoningClient on what to do next
- Step: A single iteration in the agent loop (observation -> action -> result)
- AgentContext: Execution context with goal, history, etc.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class ActionType(str, Enum):
    """Types of actions the agent can take."""

    CLICK = "click"
    TYPE = "type"
    LAUNCH_APP = "launch_app"
    PRESS_BACK = "press_back"
    SCROLL = "scroll"
    WAIT = "wait"
    SWIPE = "swipe"
    COMPLETE = "complete"  # Task completed successfully
    FAIL = "fail"  # Task failed, cannot continue


class LoginStatus(str, Enum):
    """Application login status."""

    LOGGED_IN = "logged_in"
    QR_PENDING = "qr_pending"
    OFFLINE = "offline"
    EXPIRED = "expired"
    UNKNOWN = "unknown"


@dataclass
class Position:
    """UI element position coordinates.

    Note: x, y are the CENTER point coordinates of the element,
    not the top-left corner. This is the position to click.
    """

    x: int  # Center X coordinate
    y: int  # Center Y coordinate
    width: Optional[int] = None
    height: Optional[int] = None
    found: bool = True
    confidence: float = 1.0
    description: str = ""
    enabled: bool = True  # Whether the element is clickable/enabled

    @property
    def center_x(self) -> int:
        """Get center X coordinate (same as x since x is already center)."""
        return self.x

    @property
    def center_y(self) -> int:
        """Get center Y coordinate (same as y since y is already center)."""
        return self.y


@dataclass
class UIElement:
    """A visible UI element on the screen."""

    element_type: str  # "button", "input", "text", "image", etc.
    text: Optional[str] = None
    position: Optional[Position] = None
    clickable: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UIElement":
        """Create from dictionary."""
        if not isinstance(data, dict):
            return cls(element_type="unknown")

        position = None
        if "position" in data and data["position"]:
            pos = data["position"]
            if isinstance(pos, dict):
                position = Position(
                    x=pos.get("x", 0),
                    y=pos.get("y", 0),
                    width=pos.get("width"),
                    height=pos.get("height"),
                )

        return cls(
            element_type=data.get("type", "unknown"),
            text=data.get("text"),
            position=position,
            clickable=data.get("clickable", True),
        )


@dataclass
class AppState:
    """Current state of the application."""

    app_name: Optional[str] = None
    is_foreground: bool = True
    login_status: LoginStatus = LoginStatus.UNKNOWN
    screen_type: Optional[str] = None

    def to_string(self) -> str:
        """Convert to readable string."""
        parts = []
        if self.app_name:
            parts.append(f"应用: {self.app_name}")
        parts.append(f"前台: {'是' if self.is_foreground else '否'}")
        parts.append(f"登录状态: {self.login_status.value}")
        if self.screen_type:
            parts.append(f"屏幕: {self.screen_type}")
        return ", ".join(parts)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppState":
        """Create from dictionary."""
        if not isinstance(data, dict):
            return cls(login_status=LoginStatus.UNKNOWN)

        login_status = LoginStatus.UNKNOWN
        status_str = data.get("login_status", "unknown")
        try:
            login_status = LoginStatus(status_str)
        except ValueError:
            pass

        return cls(
            app_name=data.get("app_name"),
            is_foreground=data.get("is_foreground", True),
            login_status=login_status,
            screen_type=data.get("screen_type"),
        )


@dataclass
class Observation:
    """Result from VisionClient analyzing a screenshot."""

    screen_type: str  # "app_store_home", "chat_list", "qr_code", "login", "other"
    app_state: Optional[AppState] = None
    visible_elements: list[UIElement] = field(default_factory=list)
    suggested_actions: list[str] = field(default_factory=list)
    raw_description: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Observation":
        """Create from dictionary."""
        if not isinstance(data, dict):
            logger.error(f"Invalid data type for Observation.from_dict: {type(data)}")
            return cls(screen_type="unknown", raw_description=str(data))

        app_state = None
        if "app_state" in data and data["app_state"]:
            app_state = AppState.from_dict(data["app_state"])

        visible_elements = []
        for elem in data.get("visible_elements", []):
            if isinstance(elem, dict):
                visible_elements.append(UIElement.from_dict(elem))

        return cls(
            screen_type=data.get("screen_type", "unknown"),
            app_state=app_state,
            visible_elements=visible_elements,
            suggested_actions=data.get("suggested_actions", []),
            raw_description=data.get("raw_description", ""),
        )


@dataclass
class Action:
    """Decision from ReasoningClient on what to do next."""

    action_type: ActionType
    target: Optional[str] = None  # Element description for click/type
    parameters: dict[str, Any] = field(default_factory=dict)
    reasoning: str = ""  # Why this action was chosen

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Action":
        """Create from dictionary."""
        if not isinstance(data, dict):
            return cls(action_type=ActionType.FAIL, reasoning=f"Invalid data type: {type(data)}")

        action_type_str = data.get("action_type", "fail")
        try:
            action_type = ActionType(action_type_str)
        except ValueError:
            action_type = ActionType.FAIL

        return cls(
            action_type=action_type,
            target=data.get("target"),
            parameters=data.get("parameters", {}),
            reasoning=data.get("reasoning", ""),
        )

    def __str__(self) -> str:
        """String representation."""
        result = f"{self.action_type.value}"
        if self.target:
            result += f"({self.target})"
        if self.parameters:
            params = ", ".join(f"{k}={v}" for k, v in self.parameters.items())
            result += f" [{params}]"
        return result


@dataclass
class StepResult:
    """Result of executing a single action."""

    success: bool
    error: Optional[str] = None
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class Step:
    """A single iteration in the agent loop."""

    observation: Observation
    action: Action
    result: StepResult
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class AgentContext:
    """Execution context for the agent."""

    goal: str  # Task goal to achieve
    app_type: str  # Application type (wechat, douyin, etc.)
    session_id: str  # AgentBay session ID
    installed_apps: list[str] = field(default_factory=list)
    history: list[Step] = field(default_factory=list)
    max_steps: int = 20  # Maximum steps before timeout
    app_package: Optional[str] = None  # Target app package name

    @property
    def step_count(self) -> int:
        """Get current step count."""
        return len(self.history)


@dataclass
class AgentResult:
    """Final result of agent execution."""

    success: bool
    message: str
    steps_taken: int = 0
    data: dict[str, Any] = field(default_factory=dict)
    history: list[Step] = field(default_factory=list)
