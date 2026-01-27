"""AgentBay Mobile (Cloud Phone) Controller."""
from __future__ import annotations

import logging
from typing import Any, Optional

from app.domain.ports import AgentBayController

logger = logging.getLogger(__name__)


class MobileController(AgentBayController):
    """Controller for AgentBay MobileUse (cloud phone) environment.

    Wraps the AgentBay SDK to provide a consistent interface for
    mobile device automation.

    Session Lifecycle:
        Sessions are ephemeral and stored only in memory. The AgentBay SDK
        does not support session restore/reconnect after service restart.
        If a session is lost from memory, it must be recreated.
    """

    def __init__(self, api_key: str):
        """Initialize the mobile controller.

        Args:
            api_key: AgentBay API key
        """
        self.api_key = api_key
        self._agentbay: Any = None
        self._sessions: dict[str, Any] = {}

    async def _get_agentbay(self) -> Any:
        """Lazy initialization of AgentBay client."""
        if self._agentbay is None:
            try:
                from agentbay import AgentBay
                self._agentbay = AgentBay(api_key=self.api_key)
            except ImportError:
                logger.error("AgentBay SDK not installed. Install with: pip install wuying-agentbay-sdk")
                raise
        return self._agentbay

    async def restore_session(self, session_id: str) -> bool:
        """Attempt to restore a session.

        Note: AgentBay SDK does not support session restore/reconnect.
        Sessions are ephemeral and cannot be recovered after service restart.
        This method always returns False for sessions not in memory.

        Args:
            session_id: The AgentBay session ID to restore

        Returns:
            True if session is already in memory, False otherwise
        """
        if session_id in self._sessions:
            logger.debug(f"Session {session_id} already in memory")
            return True

        # AgentBay SDK does not support session restore
        # Sessions must be recreated after service restart
        logger.warning(
            f"Cannot restore session {session_id}: AgentBay SDK does not support "
            "session restore. The session needs to be recreated."
        )
        return False

    def has_session(self, session_id: str) -> bool:
        """Check if a session is loaded in memory.

        Args:
            session_id: Session ID to check

        Returns:
            True if session is in memory
        """
        return session_id in self._sessions

    async def _ensure_session(self, session_id: str) -> Any:
        """Ensure session is in memory, restore if needed.

        Args:
            session_id: Session ID

        Returns:
            Session object

        Raises:
            ValueError: If session cannot be found or restored
        """
        if session_id not in self._sessions:
            # Try to restore the session
            restored = await self.restore_session(session_id)
            if not restored:
                raise ValueError(f"Session not found and could not be restored: {session_id}")
        return self._sessions[session_id]

    async def create_session(
        self,
        environment_type: str = "mobile",
        image_id: Optional[str] = None,
    ) -> str:
        """Create a new AgentBay mobile session.

        Args:
            environment_type: Should be "mobile" for this controller
            image_id: Optional image ID (e.g., "android_latest")

        Returns:
            Session ID string

        Raises:
            ValueError: If session creation fails with meaningful error message
        """
        agentbay = await self._get_agentbay()

        try:
            from agentbay import CreateSessionParams

            # image_id is required - AgentBay needs a valid image from user's account
            if not image_id:
                raise ValueError(
                    "AgentBay 镜像 ID (Image ID) 未配置。\n"
                    "请在 AgentBay 控制台创建云手机镜像，并在平台配置中填写镜像 ID。\n"
                    "参考文档: https://help.aliyun.com/document_detail/2618946.html"
                )
            
            params = CreateSessionParams(
                image_id=image_id
            )
            result = agentbay.create(params)
            
            # Check if session was created successfully
            # Note: AgentBay SDK catches API errors internally and returns None
            # instead of re-raising, so we cannot get the specific error message
            if result is None or result.session is None:
                image_hint = f" (当前配置: {image_id or 'android_latest'})" if image_id else ""
                raise ValueError(
                    f"AgentBay 会话创建失败，请检查：\n"
                    f"1. AgentBay API Key 是否正确\n"
                    f"2. Image ID 是否存在{image_hint}\n"
                    f"3. 账号配额是否充足\n"
                    f"详情请查看 tgo-vision-agent 服务日志"
                )
            
            session = result.session

            # Store session reference
            session_id = str(session.session_id)
            self._sessions[session_id] = session

            logger.info(f"Created mobile session: {session_id}")
            return session_id

        except ImportError as e:
            logger.error(f"AgentBay SDK import error: {e}")
            raise ValueError("AgentBay SDK 未安装或导入失败") from e
        except ValueError:
            raise  # Re-raise ValueError as-is
        except Exception as e:
            # Extract meaningful error message from AgentBay exceptions
            error_msg = self._extract_agentbay_error(e)
            logger.error(f"Failed to create mobile session: {error_msg}")
            raise ValueError(error_msg) from e

    def _extract_agentbay_error(self, exception: Exception) -> str:
        """Extract a user-friendly error message from AgentBay exceptions.
        
        Args:
            exception: The exception from AgentBay SDK
            
        Returns:
            User-friendly error message in Chinese
        """
        error_str = str(exception)
        
        # Check for common AgentBay error codes
        if "Image.NotExist" in error_str:
            return "镜像不存在，请检查 Image ID 配置或留空使用默认镜像"
        if "InvalidAccessKeyId" in error_str or "InvalidSecretKey" in error_str:
            return "AgentBay API Key 无效，请检查配置"
        if "Forbidden" in error_str or "AccessDenied" in error_str:
            return "AgentBay API 访问被拒绝，请检查账号权限"
        if "QuotaExceeded" in error_str or "LimitExceeded" in error_str:
            return "AgentBay 配额已用尽，请检查账号余额或配额"
        if "ServiceUnavailable" in error_str:
            return "AgentBay 服务暂不可用，请稍后重试"
        if "Timeout" in error_str or "timeout" in error_str.lower():
            return "AgentBay 服务连接超时，请稍后重试"
        if "Connection" in error_str or "Network" in error_str:
            return "无法连接到 AgentBay 服务，请检查网络"
        
        # Return original error if no specific match
        return f"AgentBay 错误: {error_str[:200]}"

    async def delete_session(self, session_id: str) -> bool:
        """Delete/terminate an AgentBay session.

        Args:
            session_id: Session ID to delete

        Returns:
            True if successful (or session not in memory)
        """
        # If session not in memory, consider it already deleted
        if session_id not in self._sessions:
            logger.info(f"Session {session_id} not in memory, treating as deleted")
            return True

        try:
            session = self._sessions[session_id]
            agentbay = await self._get_agentbay()
            agentbay.delete(session)
            del self._sessions[session_id]
            logger.info(f"Deleted session: {session_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete session {session_id}: {e}")
            # Still remove from memory even if cloud delete fails
            self._sessions.pop(session_id, None)
            return False

    async def take_screenshot(self, session_id: str) -> bytes:
        """Take a screenshot of the current screen.

        Args:
            session_id: Session ID

        Returns:
            Screenshot as PNG bytes
        """
        session = await self._ensure_session(session_id)

        try:
            # Use AgentBay's screenshot capability
            # Note: The SDK returns an OperationResult object.
            # result.data contains the screenshot data.
            # In some versions/environments, this might be a base64 string.
            result = session.mobile.screenshot()
            
            if result.success:
                data = result.data
                
                # Debug logging
                logger.debug(f"Screenshot result.data type: {type(data)}")
                if isinstance(data, str):
                    logger.debug(f"Screenshot data (first 100 chars): {data[:100]}")
                elif isinstance(data, bytes):
                    logger.debug(f"Screenshot data size: {len(data)} bytes, header: {data[:20]}")
                
                # Handle different data types
                if data is None:
                    raise ValueError("Screenshot data is None")
                
                if isinstance(data, str):
                    # Check if it's a URL
                    if data.startswith(('http://', 'https://')):
                        # Download image from URL
                        import httpx
                        async with httpx.AsyncClient(timeout=30.0) as client:
                            resp = await client.get(data)
                            resp.raise_for_status()
                            return resp.content
                    else:
                        # Assume base64 encoded
                        import base64
                        try:
                            return base64.b64decode(data)
                        except Exception as e:
                            logger.error(f"Failed to decode base64 screenshot: {e}")
                            raise ValueError(f"Invalid screenshot data format: {e}")
                
                # Validate bytes data
                if isinstance(data, bytes):
                    if len(data) < 100:
                        raise ValueError(f"Screenshot data too small: {len(data)} bytes")
                    # Check for common image headers
                    if not (data.startswith(b'\x89PNG') or 
                            data.startswith(b'\xff\xd8') or
                            data.startswith(b'GIF8') or
                            (data.startswith(b"RIFF") and b"WEBP" in data[:12])):
                        logger.warning(f"Unknown image format, header: {data[:20]}")
                    return data
                
                raise ValueError(f"Unexpected screenshot data type: {type(data)}")
            else:
                raise ValueError(f"Failed to take screenshot: {result.error_message}")
        except Exception as e:
            logger.error(f"Failed to take screenshot: {e}")
            raise

    async def click(self, session_id: str, x: int, y: int) -> bool:
        """Click at the specified coordinates.

        Args:
            session_id: Session ID
            x: X coordinate
            y: Y coordinate

        Returns:
            True if successful
        """
        session = await self._ensure_session(session_id)

        try:
            result = session.mobile.tap(x, y)
            if result.success:
                logger.debug(f"Clicked at ({x}, {y})")
                return True
            else:
                logger.error(f"Failed to click at ({x}, {y}): {result.error_message}")
                return False
        except Exception as e:
            logger.error(f"Failed to click at ({x}, {y}): {e}")
            return False

    async def type_text(self, session_id: str, text: str) -> bool:
        """Type text into the current focused element.

        Args:
            session_id: Session ID
            text: Text to type

        Returns:
            True if successful
        """
        session = await self._ensure_session(session_id)

        try:
            # Use input_text for mobile
            result = session.mobile.input_text(text)
            if result.success:
                logger.debug(f"Typed text: {text[:50]}...")
                return True
            else:
                logger.error(f"Failed to type text: {result.error_message}")
                return False
        except Exception as e:
            logger.error(f"Failed to type text: {e}")
            return False

    async def swipe(
        self,
        session_id: str,
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int,
        duration_ms: int = 300,
    ) -> bool:
        """Swipe from start to end coordinates.

        Args:
            session_id: Session ID
            start_x: Start X coordinate
            start_y: Start Y coordinate
            end_x: End X coordinate
            end_y: End Y coordinate
            duration_ms: Swipe duration in milliseconds

        Returns:
            True if successful
        """
        session = await self._ensure_session(session_id)

        try:
            result = session.mobile.swipe(start_x, start_y, end_x, end_y, duration_ms)
            if result.success:
                logger.debug(f"Swiped from ({start_x}, {start_y}) to ({end_x}, {end_y})")
                return True
            else:
                logger.error(f"Failed to swipe: {result.error_message}")
                return False
        except Exception as e:
            logger.error(f"Failed to swipe: {e}")
            return False

    async def press_back(self, session_id: str) -> bool:
        """Press the back button.

        Args:
            session_id: Session ID

        Returns:
            True if successful
        """
        session = await self._ensure_session(session_id)

        try:
            # Try to get KeyCode from agentbay
            try:
                from agentbay import KeyCode
                # Use BACK if available, otherwise fallback to 4 (Android BACK keycode)
                back_key = getattr(KeyCode, 'BACK', 4)
            except (ImportError, AttributeError):
                back_key = 4  # Standard Android BACK keycode

            result = session.mobile.send_key(back_key)
            if result.success:
                logger.debug(f"Pressed back button (keycode: {back_key})")
                return True
            else:
                logger.error(f"Failed to press back: {result.error_message}")
                return False
        except Exception as e:
            logger.error(f"Failed to press back: {e}")
            return False

    async def launch_app(self, session_id: str, package_name: str) -> bool:
        """Launch an application by package name.

        Args:
            session_id: Session ID
            package_name: Android package name (e.g., com.tencent.mm)

        Returns:
            True if successful
        """
        session = await self._ensure_session(session_id)

        try:
            # Use "monkey -p <package_name> 1" format for starting apps on Android
            start_cmd = f"monkey -p {package_name} 1"
            result = session.mobile.start_app(start_cmd)
            if result.success:
                logger.info(f"Launched app: {package_name}")
                return True
            else:
                logger.error(f"Failed to launch app {package_name}: {result.error_message}")
                return False
        except Exception as e:
            logger.error(f"Failed to launch app {package_name}: {e}")
            return False

    async def get_installed_apps(self, session_id: str) -> list[str]:
        """Get list of installed application package names.

        Args:
            session_id: Session ID

        Returns:
            List of package names
        """
        session = await self._ensure_session(session_id)

        try:
            # Note: start_menu=True, desktop=False, ignore_system_apps=True is recommended
            result = session.mobile.get_installed_apps(
                start_menu=True,
                desktop=False,
                ignore_system_apps=True
            )
            if result.success:
                # result.data is a list of InstalledApp objects
                # app.start_cmd usually contains the package name or full command
                apps = [app.start_cmd for app in result.data if app.start_cmd]
                logger.debug(f"Found {len(apps)} installed apps")
                return apps
            else:
                logger.error(f"Failed to get installed apps: {result.error_message}")
                return []
        except Exception as e:
            logger.error(f"Failed to get installed apps: {e}")
            return []

