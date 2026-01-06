"""Plugin Tool Sync Service - Sync plugin tools to tgo-ai service."""

from typing import Any, Dict, List

import httpx

from app.config import settings
from app.core.logging import get_logger
from app.services.plugin_manager import PluginConnection

logger = get_logger("services.tool_sync")


class PluginToolSyncService:
    """Service for synchronizing plugin MCP tools to the AI service."""

    def __init__(self):
        self.ai_base_url = settings.AI_SERVICE_URL.rstrip("/")
        self.timeout = settings.AI_SERVICE_TIMEOUT

    async def sync_plugin_tools(self, plugin: PluginConnection):
        """
        Sync plugin tools to tgo-ai when a plugin connects.
        
        This creates/updates tool records in tgo-ai for each MCP tool the plugin provides.
        """
        if not plugin.project_id:
            logger.info(f"Skipping tool sync for plugin {plugin.name} (id={plugin.id}): no project_id associated.")
            return

        logger.info(f"Syncing tools for plugin: {plugin.name} (id={plugin.id}) in project {plugin.project_id}")

        for cap in plugin.capabilities:
            if cap.type == "mcp_tools" and cap.tools:
                for tool in cap.tools:
                    tool_data = {
                        "name": f"plugin:{plugin.id}:{tool.name}",
                        "description": tool.description or tool.title,
                        "tool_type": "MCP",
                        "transport_type": "plugin",
                        "endpoint": f"plugin://{plugin.id}",
                        "project_id": plugin.project_id,  # Add project_id here
                        "config": {
                            "plugin_id": plugin.id,
                            "tool_name": tool.name,
                            "parameters": [p.model_dump() for p in (tool.parameters or [])],
                        }
                    }
                    await self._register_tool(tool_data)

    async def remove_plugin_tools(self, plugin_id: str):
        """
        Remove plugin tools from tgo-ai when a plugin disconnects.
        """
        logger.info(f"Removing tools for plugin: {plugin_id}")
        await self._delete_tools_by_prefix(f"plugin:{plugin_id}:")

    async def _register_tool(self, tool_data: Dict[str, Any]):
        """Register a tool in tgo-ai (create or update across all projects)."""
        url = f"{self.ai_base_url}/api/v1/tools/plugin"
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    url,
                    json=tool_data,
                    headers={"Content-Type": "application/json"},
                )
                
                if response.status_code in (200, 201):
                    logger.info(f"Synced tool: {tool_data['name']}")
                else:
                    logger.warning(f"Failed to sync tool {tool_data['name']}: {response.status_code} {response.text}")
        except Exception as e:
            logger.error(f"Error syncing tool {tool_data['name']}: {e}")

    async def _delete_tools_by_prefix(self, prefix: str):
        """Delete tools with names starting with prefix."""
        url = f"{self.ai_base_url}/api/v1/tools/plugin/by-prefix"
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.delete(
                    url,
                    params={"prefix": prefix},
                )
                
                if response.status_code in (200, 204):
                    logger.info(f"Removed tools with prefix: {prefix}")
                else:
                    logger.warning(f"Failed to remove tools with prefix {prefix}: {response.status_code} {response.text}")
        except Exception as e:
            logger.error(f"Error removing tools with prefix {prefix}: {e}")


# Global instance
plugin_tool_sync = PluginToolSyncService()


def setup_tool_sync():
    """Setup tool sync with plugin manager."""
    from app.services.plugin_manager import plugin_manager
    plugin_manager.set_tool_sync(plugin_tool_sync)

