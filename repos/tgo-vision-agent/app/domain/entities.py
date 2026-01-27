"""Domain entities for vision agent."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID


class AppType(str, Enum):
    """Supported application types."""

    WECHAT = "wechat"
    DOUYIN = "douyin"
    XIAOHONGSHU = "xiaohongshu"
    WHATSAPP = "whatsapp"


class MessageType(str, Enum):
    """Message content types."""

    TEXT = "text"
    IMAGE = "image"
    VOICE = "voice"
    VIDEO = "video"
    FILE = "file"
    OTHER = "other"


class MessageDirection(str, Enum):
    """Message direction."""

    INBOUND = "inbound"
    OUTBOUND = "outbound"


class SessionStatus(str, Enum):
    """AgentBay session status."""

    ACTIVE = "active"
    PAUSED = "paused"
    TERMINATED = "terminated"


class AppLoginStatus(str, Enum):
    """Application login status."""

    LOGGED_IN = "logged_in"           # 已登录，正常运行
    QR_PENDING = "qr_pending"         # 等待扫码登录
    OFFLINE = "offline"               # 离线（需要登录）
    EXPIRED = "expired"               # 二维码/登录已过期
    APP_NOT_INSTALLED = "app_not_installed"  # app 未安装
    APP_INSTALLING = "app_installing"        # app 正在安装中
    APP_NOT_RUNNING = "app_not_running"      # app 未运行（已关闭）


class ScreenType(str, Enum):
    """Screen type detected by VLM."""

    CONVERSATION_LIST = "conversation_list"
    CHAT = "chat"
    LOGIN = "login"
    QR_CODE = "qr_code"
    OTHER = "other"


@dataclass
class Position:
    """Screen position coordinates."""

    x: int
    y: int
    width: Optional[int] = None
    height: Optional[int] = None


@dataclass
class Contact:
    """Contact information extracted from UI."""

    contact_id: str
    name: str
    unread_count: int = 0
    last_message_preview: Optional[str] = None
    position: Optional[Position] = None
    avatar_url: Optional[str] = None


@dataclass
class Message:
    """Message extracted from chat UI."""

    content: str
    sender: str  # "self" or "other"
    message_type: MessageType = MessageType.TEXT
    timestamp: Optional[str] = None
    position_index: int = 0
    is_new: bool = False


@dataclass
class UIElement:
    """UI element position for automation."""

    element_type: str  # input_box, send_button, back_button, etc.
    position: Position
    is_visible: bool = True


@dataclass
class ScreenAnalysis:
    """Result of VLM screen analysis."""

    screen_type: ScreenType
    has_new_messages: bool = False
    conversations: list[Contact] = field(default_factory=list)
    messages: list[Message] = field(default_factory=list)
    ui_elements: dict[str, UIElement] = field(default_factory=dict)
    current_contact: Optional[Contact] = None
    qr_code_bounds: Optional[Position] = None
    raw_response: Optional[dict] = None


@dataclass
class AppState:
    """Current application state."""

    login_status: AppLoginStatus
    screen_type: ScreenType
    current_contact: Optional[Contact] = None
    qr_code_bounds: Optional[Position] = None


@dataclass
class SessionInfo:
    """Vision agent session information."""

    id: UUID
    platform_id: UUID
    app_type: AppType
    agentbay_session_id: str
    environment_type: str
    status: SessionStatus
    app_login_status: AppLoginStatus
    last_heartbeat: Optional[datetime] = None
    last_screenshot_at: Optional[datetime] = None
