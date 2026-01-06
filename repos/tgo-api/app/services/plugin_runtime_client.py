"""Client for communicating with tgo-plugin-runtime service."""

from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("services.plugin_runtime_client")


class PluginRuntimeClient:
    """HTTP client for tgo-plugin-runtime service."""

    def __init__(self):
        self.base_url = settings.PLUGIN_RUNTIME_URL.rstrip("/")
        self.timeout = settings.PLUGIN_RUNTIME_TIMEOUT

    async def _request(
        self,
        method: str,
        path: str,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Make an HTTP request to plugin-runtime."""
        url = f"{self.base_url}{path}"
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    json=json,
                    params=params,
                    headers={"Content-Type": "application/json"},
                )
                
                if response.status_code == 404:
                    return None
                
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Plugin runtime HTTP error: {e.response.status_code} {e.response.text}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Plugin runtime request error: {e}")
            raise

    # ==================== Plugin List ====================

    async def list_plugins(self, project_id: Optional[str] = None) -> Dict[str, Any]:
        """Get all registered plugins."""
        params = {"project_id": project_id} if project_id else None
        return await self._request("GET", "/plugins", params=params) or {"plugins": [], "total": 0}

    async def get_plugin(self, plugin_id: str, project_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get a specific plugin by ID."""
        params = {"project_id": project_id} if project_id else None
        return await self._request("GET", f"/plugins/{plugin_id}", params=params)

    # ==================== Chat Toolbar ====================

    async def get_chat_toolbar_buttons(self, project_id: Optional[str] = None) -> Dict[str, Any]:
        """Get chat toolbar buttons from all plugins."""
        params = {"project_id": project_id} if project_id else None
        return await self._request("GET", "/plugins/chat-toolbar/buttons", params=params) or {"buttons": []}

    async def render_chat_toolbar(
        self,
        plugin_id: str,
        request_data: Dict[str, Any],
        project_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Render chat toolbar plugin content."""
        params = {"project_id": project_id} if project_id else None
        return await self._request(
            "POST",
            f"/plugins/chat-toolbar/{plugin_id}/render",
            json=request_data,
            params=params,
        )

    async def send_chat_toolbar_event(
        self,
        plugin_id: str,
        request_data: Dict[str, Any],
        project_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Send event to chat toolbar plugin."""
        params = {"project_id": project_id} if project_id else None
        return await self._request(
            "POST",
            f"/plugins/chat-toolbar/{plugin_id}/event",
            json=request_data,
            params=params,
        )

    # ==================== Visitor Panel ====================

    async def render_visitor_panels(
        self,
        request_data: Dict[str, Any],
        project_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Render all visitor panel plugins."""
        params = {"project_id": project_id} if project_id else None
        return await self._request(
            "POST",
            "/plugins/visitor-panel/render",
            json=request_data,
            params=params,
        ) or {"panels": []}

    # ==================== Generic Plugin Routes ====================

    async def render_plugin(
        self,
        plugin_id: str,
        request_data: Dict[str, Any],
        project_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Render a plugin's UI."""
        params = {"project_id": project_id} if project_id else None
        return await self._request(
            "POST",
            f"/plugins/{plugin_id}/render",
            json=request_data,
            params=params,
        )

    async def send_plugin_event(
        self,
        plugin_id: str,
        request_data: Dict[str, Any],
        project_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Send event to a plugin."""
        params = {"project_id": project_id} if project_id else None
        return await self._request(
            "POST",
            f"/plugins/{plugin_id}/event",
            json=request_data,
            params=params,
        )

    # ==================== Tool Execution ====================

    async def execute_tool(
        self,
        plugin_id: str,
        tool_name: str,
        request_data: Dict[str, Any],
        project_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Execute a plugin MCP tool."""
        params = {"project_id": project_id} if project_id else None
        return await self._request(
            "POST",
            f"/plugins/tools/execute/{plugin_id}/{tool_name}",
            json=request_data,
            params=params,
        )

    # ==================== Installation & Lifecycle ====================

    async def list_installed_plugins(self, project_id: Optional[str] = None) -> Dict[str, Any]:
        """Get all installed plugins."""
        params = {"project_id": project_id} if project_id else None
        return await self._request("GET", "/plugins/installed", params=params) or {"plugins": [], "total": 0}

    async def fetch_plugin_info(self, url: str) -> Optional[Dict[str, Any]]:
        """Fetch plugin info from a URL."""
        return await self._request(
            "POST",
            "/plugins/fetch-info",
            json={"url": url},
        )

    async def install_plugin(self, request_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Install a plugin from YAML."""
        return await self._request(
            "POST",
            "/plugins/install",
            json=request_data,
        )

    async def uninstall_plugin(self, plugin_id: str, project_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Uninstall a plugin."""
        params = {"project_id": project_id} if project_id else None
        return await self._request(
            "DELETE",
            f"/plugins/{plugin_id}/uninstall",
            params=params,
        )

    async def start_plugin(self, plugin_id: str, request_data: Dict[str, Any], project_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Start a plugin process."""
        params = {"project_id": project_id} if project_id else None
        return await self._request(
            "POST",
            f"/plugins/{plugin_id}/start",
            json=request_data,
            params=params,
        )

    async def stop_plugin(self, plugin_id: str, project_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Stop a plugin process."""
        params = {"project_id": project_id} if project_id else None
        return await self._request(
            "POST",
            f"/plugins/{plugin_id}/stop",
            params=params,
        )

    async def restart_plugin(self, plugin_id: str, project_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Restart a plugin process."""
        params = {"project_id": project_id} if project_id else None
        return await self._request(
            "POST",
            f"/plugins/{plugin_id}/restart",
            params=params,
        )

    async def get_plugin_logs(self, plugin_id: str, project_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get plugin logs."""
        params = {"project_id": project_id} if project_id else None
        return await self._request(
            "GET",
            f"/plugins/{plugin_id}/logs",
            params=params,
        )

    async def get_plugin_status(self, plugin_id: str, project_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get plugin status from runtime."""
        params = {"project_id": project_id} if project_id else None
        return await self._request(
            "GET",
            f"/plugins/{plugin_id}/status",
            params=params,
        )


# Global client instance
plugin_runtime_client = PluginRuntimeClient()

