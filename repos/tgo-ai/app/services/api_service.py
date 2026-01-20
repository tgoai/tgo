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
        # Use docker service name instead of localhost for internal communication
        self.api_base_url = settings.api_service_url
        
        # Determine internal URL - Internal API always runs on port 8001 by convention
        base = self.api_base_url.rstrip('/')
        if ":8000" in base:
            self.internal_api_url = f"{base.replace(':8000', ':8001')}/internal"
        elif ":8080" in base:
            self.internal_api_url = f"{base.replace(':8080', ':8001')}/internal"
        else:
            # Fallback if port is not explicitly in URL
            self.internal_api_url = f"{base}/internal"
            
        self.plugin_runtime_url = settings.plugin_runtime_url
        self.timeout = 30.0

    async def get_store_credential(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch store credential for a project from the internal API.
        """
        # Candidate internal URLs:
        # Priority 1: SaaS combined mode (internal router mounted on main API at port 8000)
        # Priority 2: Standard Internal API port 8001 (separate internal service)
        # Priority 3: Configured internal_api_url as fallback
        urls = [
            f"http://tgo-api-saas:8000/internal/store/{project_id}/credential",
            f"http://tgo-api-saas:8001/internal/store/{project_id}/credential",
            f"{self.internal_api_url}/store/{project_id}/credential"
        ]
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for url in urls:
                # Clean up any accidental double slashes or /api/v1 prefixes
                url = url.replace("/api/v1/internal", "/internal")
                
                try:
                    response = await client.get(url)
                    if response.status_code == 200:
                        return response.json()
                except Exception:
                    continue
            
            logger.error(f"Failed to fetch store credential from all candidate URLs for project {project_id}")
            return None

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
            context: Context containing user_id, session_id, agent_id, etc.

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

