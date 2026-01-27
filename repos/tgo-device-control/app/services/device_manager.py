"""Device Manager - Manages WebSocket connections and device state."""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import WebSocket

from app.config import settings
from app.core.logging import get_logger

logger = get_logger("services.device_manager")


@dataclass
class DeviceConnection:
    """Represents an active device connection."""

    device_id: str
    project_id: str
    device_name: str
    device_type: str
    os: str
    os_version: Optional[str]
    screen_resolution: Optional[str]
    websocket: WebSocket
    connected_at: datetime = field(default_factory=datetime.utcnow)
    last_heartbeat: datetime = field(default_factory=datetime.utcnow)
    _request_id: int = 0
    _pending_requests: Dict[int, asyncio.Future] = field(default_factory=dict)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def next_request_id(self) -> int:
        """Generate next request ID."""
        self._request_id += 1
        return self._request_id

    async def send_message(self, message: Dict[str, Any]) -> None:
        """Send a JSON message to the device."""
        await self.websocket.send_json(message)

    async def send_request(
        self,
        method: str,
        params: Dict[str, Any],
        timeout: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """Send a JSON-RPC request and wait for response."""
        timeout = timeout or settings.WS_REQUEST_TIMEOUT
        request_id = self.next_request_id()

        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params,
        }

        # Create future for response
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending_requests[request_id] = future

        try:
            await self.send_message(request)
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            logger.error(f"Request timeout: device={self.device_id}, method={method}")
            return None
        except Exception as e:
            logger.error(f"Request error: device={self.device_id}, method={method}: {e}")
            return None
        finally:
            self._pending_requests.pop(request_id, None)

    def handle_response(self, message: Dict[str, Any]) -> None:
        """Handle a JSON-RPC response from the device."""
        request_id = message.get("id")
        if request_id is None:
            return

        future = self._pending_requests.get(request_id)
        if future and not future.done():
            if "error" in message:
                error = message["error"]
                logger.warning(f"Device error response: {error}")
                future.set_result(None)
            else:
                future.set_result(message.get("result"))


class DeviceManager:
    """
    Singleton Device Manager.

    Manages active device connections, heartbeats, and request dispatching.
    """

    _instance: Optional["DeviceManager"] = None

    def __new__(cls) -> "DeviceManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._devices: Dict[str, DeviceConnection] = {}
        self._lock = asyncio.Lock()
        self._heartbeat_task: Optional[asyncio.Task] = None
        logger.info("DeviceManager initialized")

    async def initialize(self) -> None:
        """Initialize the device manager."""
        # Start heartbeat monitor
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.info("DeviceManager heartbeat monitor started")

    async def shutdown(self) -> None:
        """Shutdown the device manager."""
        # Cancel heartbeat task
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        # Disconnect all devices
        for device_id in list(self._devices.keys()):
            await self.disconnect_device(device_id)

        logger.info("DeviceManager shutdown complete")

    async def register_device(
        self,
        device_id: str,
        project_id: str,
        device_name: str,
        device_type: str,
        os: str,
        os_version: Optional[str],
        screen_resolution: Optional[str],
        websocket: WebSocket,
    ) -> DeviceConnection:
        """Register a new device connection."""
        connection = DeviceConnection(
            device_id=device_id,
            project_id=project_id,
            device_name=device_name,
            device_type=device_type,
            os=os,
            os_version=os_version,
            screen_resolution=screen_resolution,
            websocket=websocket,
        )

        async with self._lock:
            # Disconnect existing connection if any
            if device_id in self._devices:
                old_conn = self._devices[device_id]
                try:
                    await old_conn.websocket.close()
                except Exception:
                    pass

            self._devices[device_id] = connection

        logger.info(f"Device registered: {device_name} ({device_id})")
        return connection

    async def unregister_device(self, device_id: str) -> None:
        """Unregister a device connection."""
        async with self._lock:
            connection = self._devices.pop(device_id, None)

        if connection:
            logger.info(f"Device unregistered: {connection.device_name} ({device_id})")
            # Cancel pending requests
            for future in connection._pending_requests.values():
                if not future.done():
                    future.cancel()

    async def disconnect_device(self, device_id: str) -> None:
        """Disconnect a device."""
        async with self._lock:
            connection = self._devices.get(device_id)

        if connection:
            try:
                await connection.websocket.close()
            except Exception:
                pass
            await self.unregister_device(device_id)

    def get_device(
        self,
        device_id: str,
        project_id: Optional[str] = None,
    ) -> Optional[DeviceConnection]:
        """Get a device connection by ID."""
        connection = self._devices.get(device_id)
        if connection and project_id and connection.project_id != project_id:
            return None
        return connection

    def get_devices_by_project(self, project_id: str) -> list[DeviceConnection]:
        """Get all device connections for a project."""
        return [
            conn for conn in self._devices.values() if conn.project_id == project_id
        ]

    def get_connected_count(self) -> int:
        """Get the number of connected devices."""
        return len(self._devices)

    def update_heartbeat(self, device_id: str) -> None:
        """Update device heartbeat timestamp."""
        connection = self._devices.get(device_id)
        if connection:
            connection.last_heartbeat = datetime.utcnow()

    async def _heartbeat_loop(self) -> None:
        """Background task to monitor device heartbeats."""
        while True:
            try:
                await asyncio.sleep(settings.WS_HEARTBEAT_INTERVAL)

                now = datetime.utcnow()
                timeout = settings.WS_HEARTBEAT_TIMEOUT
                disconnected = []

                for device_id, connection in list(self._devices.items()):
                    elapsed = (now - connection.last_heartbeat).total_seconds()
                    if elapsed > timeout:
                        logger.warning(
                            f"Device heartbeat timeout: {connection.device_name} ({device_id})"
                        )
                        disconnected.append(device_id)
                    else:
                        # Send ping
                        try:
                            await connection.send_message({
                                "jsonrpc": "2.0",
                                "method": "ping",
                                "params": {},
                            })
                        except Exception as e:
                            logger.warning(f"Failed to ping device {device_id}: {e}")
                            disconnected.append(device_id)

                # Disconnect timed out devices
                for device_id in disconnected:
                    await self.disconnect_device(device_id)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat loop error: {e}")


# Global singleton instance
device_manager = DeviceManager()
