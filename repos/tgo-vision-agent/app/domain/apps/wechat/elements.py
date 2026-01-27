"""WeChat UI element definitions and constants."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class WeChatUIConfig:
    """Configuration for WeChat UI elements.

    These values may need adjustment based on:
    - Screen resolution
    - WeChat version
    - Android/Windows platform
    """

    # Common tap delays (milliseconds)
    tap_delay: int = 300
    typing_delay: int = 100
    animation_delay: int = 500
    page_load_delay: int = 1000

    # Search behavior
    search_result_wait: int = 1500

    # Message sending
    send_verification_delay: int = 500


# Default configurations
MOBILE_CONFIG = WeChatUIConfig(
    tap_delay=300,
    typing_delay=100,
    animation_delay=500,
    page_load_delay=1000,
)

DESKTOP_CONFIG = WeChatUIConfig(
    tap_delay=200,
    typing_delay=50,
    animation_delay=300,
    page_load_delay=800,
)


# WeChat-specific constants
class WeChatConstants:
    """WeChat-specific constants."""

    # Package names
    ANDROID_PACKAGE = "com.tencent.mm"
    ANDROID_MAIN_ACTIVITY = "com.tencent.mm.ui.LauncherUI"

    # Windows
    WINDOWS_PROCESS_NAME = "WeChat.exe"
    WINDOWS_WINDOW_CLASS = "WeChatMainWndForPC"

    # Timeouts (seconds)
    LOGIN_TIMEOUT = 120  # Time to wait for QR scan
    MESSAGE_SEND_TIMEOUT = 30
    NAVIGATION_TIMEOUT = 10

    # Limits
    MAX_MESSAGE_LENGTH = 2000
    MAX_RETRY_COUNT = 3

    # File types supported for sending
    SUPPORTED_IMAGE_TYPES = [".jpg", ".jpeg", ".png", ".gif", ".bmp"]
    SUPPORTED_VIDEO_TYPES = [".mp4", ".mov", ".avi"]
    SUPPORTED_FILE_TYPES = [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".txt"]
