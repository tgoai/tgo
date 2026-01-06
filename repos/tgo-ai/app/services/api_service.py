"""API Service client for interacting with the core TGO API service."""

import logging
from typing import Any, Dict, Optional

import httpx
from app.config import settings

logger = logging.getLogger("services.api_service")

class APIServiceClient:
    """Client for interacting with the core TGO API service."""

    def __init__(self):
        """Initialize the API service client."""
        self.api_base_url = settings.api_service_url
        self.plugin_runtime_url = settings.plugin_runtime_url
        self.timeout = 30.0

    async def execute_plugin_tool(
        self,
        plugin_id: str,
        tool_name: str,
        arguments: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute a plugin tool via the TGO Plugin Runtime service.

        Args:
            plugin_id: Unique plugin ID
            tool_name: Name of the tool to execute
            arguments: Tool arguments from LLM
            context: Context containing visitor_id, session_id, agent_id, etc.

        Returns:
            Tool result dictionary
        """
        url = f"{self.plugin_runtime_url}/plugins/tools/execute/{plugin_id}/{tool_name}"
        
        payload = {
            "arguments": arguments,
            "context": context,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(f"API service error executing plugin tool: {response.status_code} {response.text}")
                    return {
                        "success": False,
                        "error": f"API service error: {response.status_code}",
                        "content": f"工具执行失败 (HTTP {response.status_code})"
                    }

            except httpx.RequestError as e:
                logger.error(f"Unable to connect to API service: {str(e)}")
                return {
                    "success": False,
                    "error": str(e),
                    "content": "无法连接到 TGO API 服务"
                }

# Global API service client instance
api_service_client = APIServiceClient()

