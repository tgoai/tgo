"""Plugin Manager - Registry and request dispatcher."""

from __future__ import annotations

import asyncio
import json
import struct
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.plugin import (
    PluginCapability,
    PluginInfo,
    ChatToolbarButton,
    PluginPanelItem,
    PluginRenderResponse,
    VisitorInfo,
)

logger = get_logger("services.plugin_manager")



@dataclass
class PluginConnection:
    """Represents a connected plugin."""
    id: str
    name: str
    version: str
    description: Optional[str] = None
    author: Optional[str] = None
    capabilities: List[PluginCapability] = field(default_factory=list)
    connected_at: datetime = field(default_factory=datetime.utcnow)
    reader: Optional[asyncio.StreamReader] = None
    writer: Optional[asyncio.StreamWriter] = None
    _request_id: int = 0
    _pending_requests: Dict[int, asyncio.Future] = field(default_factory=dict)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def next_request_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def to_info(self) -> PluginInfo:
        return PluginInfo(
            id=self.id,
            name=self.name,
            version=self.version,
            description=self.description,
            author=self.author,
            capabilities=self.capabilities,
            connected_at=self.connected_at,
            status="connected" if self.writer and not self.writer.is_closing() else "disconnected"
        )


class PluginManager:
    """
    Singleton Plugin Manager.
    
    Manages plugin connections, registration, and request dispatching.
    """
    _instance: Optional["PluginManager"] = None
    
    def __new__(cls) -> "PluginManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._plugins: Dict[str, PluginConnection] = {}
        self._lock = asyncio.Lock()
        logger.info("PluginManager initialized")

    @property
    def plugins(self) -> Dict[str, PluginConnection]:
        return self._plugins

    async def register(
        self,
        name: str,
        version: str,
        capabilities: List[Dict[str, Any]],
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        plugin_id: Optional[str] = None,
        description: Optional[str] = None,
        author: Optional[str] = None,
    ) -> Tuple[str, PluginConnection]:
        """Register a new plugin connection."""
        if not plugin_id:
            plugin_id = f"plugin_{uuid.uuid4().hex[:8]}"
        
        caps = [PluginCapability(**c) for c in capabilities]
        
        plugin = PluginConnection(
            id=plugin_id,
            name=name,
            version=version,
            description=description,
            author=author,
            capabilities=caps,
            reader=reader,
            writer=writer,
        )
        
        async with self._lock:
            self._plugins[plugin_id] = plugin
        
        logger.info(
            f"Plugin registered: {name} v{version} (id={plugin_id})",
            extra={"plugin_id": plugin_id, "capabilities": [c.type for c in caps]}
        )
        return plugin_id, plugin

    async def unregister(self, plugin_id: str):
        """Unregister a plugin."""
        async with self._lock:
            plugin = self._plugins.pop(plugin_id, None)
        
        if plugin:
            logger.info(f"Plugin unregistered: {plugin.name} (id={plugin_id})")
            # Cancel pending requests
            for future in plugin._pending_requests.values():
                if not future.done():
                    future.cancel()
            # Close writer
            if plugin.writer and not plugin.writer.is_closing():
                plugin.writer.close()
                try:
                    await plugin.writer.wait_closed()
                except Exception:
                    pass

    def get_plugin(self, plugin_id: str) -> Optional[PluginConnection]:
        """Get a plugin by ID."""
        return self._plugins.get(plugin_id)

    def get_all_plugins(self) -> List[PluginInfo]:
        """Get all registered plugins."""
        return [p.to_info() for p in self._plugins.values()]

    def get_plugins_by_type(self, extension_type: str) -> List[PluginConnection]:
        """Get plugins that support a specific extension type."""
        result = []
        for plugin in self._plugins.values():
            for cap in plugin.capabilities:
                if cap.type == extension_type:
                    result.append(plugin)
                    break
        return result

    def get_chat_toolbar_buttons(self) -> List[ChatToolbarButton]:
        """Get all chat toolbar buttons from registered plugins."""
        buttons = []
        for plugin in self._plugins.values():
            for cap in plugin.capabilities:
                if cap.type == "chat_toolbar":
                    buttons.append(ChatToolbarButton(
                        plugin_id=plugin.id,
                        title=cap.title,
                        icon=cap.icon,
                        tooltip=cap.tooltip,
                        shortcut=cap.shortcut,
                    ))
        return buttons

    async def send_request(
        self,
        plugin_id: str,
        method: str,
        params: Dict[str, Any],
        timeout: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Send a JSON-RPC request to a plugin and wait for response.
        
        Returns the result dict or None on error.
        """
        plugin = self.get_plugin(plugin_id)
        if not plugin or not plugin.writer or plugin.writer.is_closing():
            logger.warning(f"Plugin not available: {plugin_id}")
            return None

        timeout = timeout or settings.PLUGIN_REQUEST_TIMEOUT
        request_id = plugin.next_request_id()
        
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params,
        }

        # Create future for response
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        plugin._pending_requests[request_id] = future

        try:
            # Send message
            await self._send_message(plugin.writer, request)
            
            # Wait for response
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            logger.error(f"Plugin request timeout: {plugin_id} {method}")
            return None
        except Exception as e:
            logger.error(f"Plugin request error: {plugin_id} {method}: {e}")
            return None
        finally:
            plugin._pending_requests.pop(request_id, None)

    async def handle_response(self, plugin: PluginConnection, message: Dict[str, Any]):
        """Handle a JSON-RPC response from a plugin."""
        request_id = message.get("id")
        if request_id is None:
            return

        future = plugin._pending_requests.get(request_id)
        if future and not future.done():
            if "error" in message:
                error = message["error"]
                logger.warning(f"Plugin error response: {error}")
                future.set_result(None)
            else:
                future.set_result(message.get("result"))

    async def _send_message(self, writer: asyncio.StreamWriter, message: Dict[str, Any]):
        """Send a length-prefixed JSON message."""
        json_bytes = json.dumps(message, ensure_ascii=False).encode("utf-8")
        length_prefix = struct.pack(">I", len(json_bytes))
        writer.write(length_prefix + json_bytes)
        await writer.drain()

    async def render_visitor_panels(
        self,
        visitor_id: str,
        session_id: Optional[str],
        visitor: Optional[VisitorInfo],
        context: Dict[str, Any],
        language: Optional[str] = None,
    ) -> List[PluginPanelItem]:
        """
        Render all visitor panel plugins.
        
        Returns list of PluginPanelItem.
        """
        plugins = self.get_plugins_by_type("visitor_panel")
        if not plugins:
            return []

        params = {
            "visitor_id": visitor_id,
            "session_id": session_id,
            "visitor": visitor.model_dump(exclude_none=True) if visitor else {},
            "context": context,
            "language": language,
        }

        async def render_one(plugin: PluginConnection) -> Optional[PluginPanelItem]:
            result = await self.send_request(plugin.id, "visitor_panel/render", params)
            if result:
                # result is expected to be a dict matching PluginRenderResponse
                try:
                    ui_resp = PluginRenderResponse(**result)
                    # Find the capability for title/icon
                    cap = next((c for c in plugin.capabilities if c.type == "visitor_panel"), None)
                    return PluginPanelItem(
                        plugin_id=plugin.id,
                        title=cap.title if cap else plugin.name,
                        icon=cap.icon if cap else None,
                        priority=cap.priority if cap else 10,
                        ui=ui_resp,
                    )
                except Exception as e:
                    logger.error(f"Failed to parse plugin render response from {plugin.id}: {e}")
                    return None
            return None

        # Render all in parallel
        tasks = [render_one(p) for p in plugins]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        panels = []
        for r in results:
            if isinstance(r, PluginPanelItem):
                panels.append(r)
            elif isinstance(r, Exception):
                logger.error(f"Error rendering visitor panel: {r}")

        # Sort by priority
        panels.sort(key=lambda x: x.priority)
        return panels


    async def shutdown_all(self):
        """Shutdown all plugin connections gracefully."""
        logger.info(f"Shutting down {len(self._plugins)} plugins...")
        
        async def shutdown_one(plugin_id: str, plugin: PluginConnection):
            try:
                await self.send_request(plugin_id, "shutdown", {}, timeout=5)
            except Exception:
                pass
            await self.unregister(plugin_id)

        tasks = [shutdown_one(pid, p) for pid, p in list(self._plugins.items())]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        logger.info("All plugins shut down")


# Global singleton instance
plugin_manager = PluginManager()

