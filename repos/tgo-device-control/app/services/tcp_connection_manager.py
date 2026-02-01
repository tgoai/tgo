"""TCP Connection Manager for Peekaboo device connections.

This module manages active TCP connections from Peekaboo agents,
providing methods to send requests and call tools on connected devices.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from app.config import settings
from app.core.logging import get_logger

logger = get_logger("services.tcp_connection_manager")


@dataclass
class TcpDeviceConnection:
    """Represents an active TCP connection from a Peekaboo device."""

    agent_id: str  # Also serves as device_id (UUID)
    name: str
    version: str
    capabilities: List[str]
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter
    connected_at: datetime = field(default_factory=datetime.utcnow)
    last_seen: datetime = field(default_factory=datetime.utcnow)
    tools: List[Dict[str, Any]] = field(default_factory=list)
    project_id: Optional[str] = None  # Associated project ID
    device_db_id: Optional[str] = None  # Database device ID (same as agent_id for new auth)
    _request_id: int = 0
    _pending_requests: Dict[Union[int, str], asyncio.Future[Any]] = field(
        default_factory=dict
    )

    def next_request_id(self) -> int:
        """Generate the next request ID."""
        self._request_id += 1
        return self._request_id

    async def send_message(self, message: Dict[str, Any]) -> None:
        """Send a JSON message to the device.

        Args:
            message: JSON-serializable message to send.
        """
        data = (json.dumps(message) + "\n").encode("utf-8")
        self.writer.write(data)
        await self.writer.drain()

    async def send_request(
        self,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """Send a JSON-RPC request and wait for response.

        Args:
            method: RPC method name.
            params: Optional method parameters.
            timeout: Optional timeout in seconds.

        Returns:
            Response result or None on timeout/error.
        """
        timeout = timeout or settings.TCP_RPC_TIMEOUT
        request_id = self.next_request_id()

        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params or {},
        }

        future: asyncio.Future[Any] = asyncio.get_event_loop().create_future()
        self._pending_requests[request_id] = future

        try:
            await self.send_message(request)
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            logger.error(
                f"TCP request timeout: agent={self.agent_id}, method={method}"
            )
            return None
        except Exception as e:
            logger.error(
                f"TCP request error: agent={self.agent_id}, method={method}: {e}"
            )
            return None
        finally:
            self._pending_requests.pop(request_id, None)

    async def call_tool(
        self,
        name: str,
        arguments: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """Call a tool on the device using tools/call method.

        Args:
            name: Tool name to call.
            arguments: Tool arguments.
            timeout: Optional timeout in seconds.

        Returns:
            Tool call result or None on timeout/error.
        """
        params = {"name": name, "arguments": arguments or {}}
        return await self.send_request("tools/call", params, timeout)

    async def list_tools(
        self, timeout: Optional[int] = None
    ) -> Optional[List[Dict[str, Any]]]:
        """Get list of available tools from the device.

        Args:
            timeout: Optional timeout in seconds.

        Returns:
            List of tool definitions or None on error.
        """
        result = await self.send_request("tools/list", {}, timeout)
        if result and "tools" in result:
            self.tools = result["tools"]
            return result["tools"]
        return None

    async def ping(self, timeout: Optional[int] = None) -> bool:
        """Send a ping request to check connection.

        Args:
            timeout: Optional timeout in seconds.

        Returns:
            True if pong received, False otherwise.
        """
        result = await self.send_request("ping", {}, timeout or 10)
        return result is not None and result.get("pong", False)

    def handle_response(self, message: Dict[str, Any]) -> None:
        """Handle a JSON-RPC response from the device.

        Args:
            message: Response message with id, result/error.
        """
        request_id = message.get("id")
        if request_id is None:
            return

        future = self._pending_requests.get(request_id)
        if future and not future.done():
            if "error" in message:
                error = message["error"]
                logger.warning(f"TCP device error response: {error}")
                future.set_result({"error": error})
            else:
                future.set_result(message.get("result"))


class TcpConnectionManager:
    """Singleton manager for TCP device connections.

    Manages active TCP connections from Peekaboo agents,
    providing device lookup and connection lifecycle management.
    """

    _instance: Optional["TcpConnectionManager"] = None

    def __new__(cls) -> "TcpConnectionManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._connections: Dict[str, TcpDeviceConnection] = {}
        self._lock = asyncio.Lock()
        self._heartbeat_task: Optional[asyncio.Task[None]] = None
        logger.info("TcpConnectionManager initialized")

    async def initialize(self) -> None:
        """Initialize the connection manager and start heartbeat monitor."""
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.info("TcpConnectionManager heartbeat monitor started")

    async def shutdown(self) -> None:
        """Shutdown the connection manager and close all connections."""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        for agent_id in list(self._connections.keys()):
            await self.unregister_connection(agent_id)

        logger.info("TcpConnectionManager shutdown complete")

    async def register_connection(
        self,
        agent_id: str,
        name: str,
        version: str,
        capabilities: List[str],
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        project_id: Optional[str] = None,
        device_db_id: Optional[str] = None,
    ) -> TcpDeviceConnection:
        """Register a new TCP connection.

        Args:
            agent_id: Unique agent/device identifier (UUID).
            name: Device name.
            version: Client version.
            capabilities: List of supported capabilities.
            reader: Async stream reader.
            writer: Async stream writer.
            project_id: Associated project ID (from bind code or device record).
            device_db_id: Database device ID (same as agent_id for registered devices).

        Returns:
            The registered TcpDeviceConnection.
        """
        connection = TcpDeviceConnection(
            agent_id=agent_id,
            name=name,
            version=version,
            capabilities=capabilities,
            reader=reader,
            writer=writer,
            project_id=project_id,
            device_db_id=device_db_id,
        )

        async with self._lock:
            # Close existing connection if any
            if agent_id in self._connections:
                old_conn = self._connections[agent_id]
                try:
                    old_conn.writer.close()
                    await old_conn.writer.wait_closed()
                except Exception:
                    pass

            self._connections[agent_id] = connection

        logger.info(f"TCP device registered: {name} ({agent_id})")
        return connection

    async def unregister_connection(self, agent_id: str) -> None:
        """Unregister and close a TCP connection.

        Args:
            agent_id: Agent identifier to unregister.
        """
        async with self._lock:
            connection = self._connections.pop(agent_id, None)

        if connection:
            logger.info(
                f"TCP device unregistered: {connection.name} ({agent_id})"
            )
            # Cancel pending requests
            for future in connection._pending_requests.values():
                if not future.done():
                    future.cancel()

            try:
                connection.writer.close()
                await connection.writer.wait_closed()
            except Exception:
                pass

    def get_connection(self, agent_id: str) -> Optional[TcpDeviceConnection]:
        """Get a TCP connection by agent ID.

        Args:
            agent_id: Agent identifier.

        Returns:
            TcpDeviceConnection or None if not found.
        """
        return self._connections.get(agent_id)

    def list_connections(self) -> List[TcpDeviceConnection]:
        """List all active TCP connections.

        Returns:
            List of active connections.
        """
        return list(self._connections.values())

    def get_connected_count(self) -> int:
        """Get the number of connected TCP devices.

        Returns:
            Number of active connections.
        """
        return len(self._connections)

    def update_heartbeat(self, agent_id: str) -> None:
        """Update the last seen timestamp for a connection.

        Args:
            agent_id: Agent identifier.
        """
        connection = self._connections.get(agent_id)
        if connection:
            connection.last_seen = datetime.utcnow()

    async def _heartbeat_loop(self) -> None:
        """Background task to monitor connection heartbeats."""
        while True:
            try:
                await asyncio.sleep(settings.WS_HEARTBEAT_INTERVAL)

                now = datetime.utcnow()
                timeout = settings.WS_HEARTBEAT_TIMEOUT
                disconnected: List[str] = []

                for agent_id, connection in list(self._connections.items()):
                    elapsed = (now - connection.last_seen).total_seconds()
                    if elapsed > timeout:
                        logger.warning(
                            f"TCP device heartbeat timeout: "
                            f"{connection.name} ({agent_id})"
                        )
                        disconnected.append(agent_id)
                    else:
                        # Send ping
                        try:
                            await connection.send_message(
                                {"jsonrpc": "2.0", "method": "ping", "params": {}}
                            )
                        except Exception as e:
                            logger.warning(
                                f"Failed to ping TCP device {agent_id}: {e}"
                            )
                            disconnected.append(agent_id)

                # Disconnect timed out devices
                for agent_id in disconnected:
                    await self.unregister_connection(agent_id)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"TCP heartbeat loop error: {e}")


# Global singleton instance
tcp_connection_manager = TcpConnectionManager()
