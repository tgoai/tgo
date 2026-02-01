"""TCP JSON-RPC Server for Peekaboo device connections.

This module implements a TCP server that accepts connections from
Peekaboo devices using the JSON-RPC 2.0 protocol.

Protocol:
- Messages are newline-delimited JSON
- First message must be an 'auth' request with bindCode or deviceToken
- After auth, the server forwards tools/call requests to the device

Authentication:
- First-time registration: Use bindCode (obtained from web UI)
- Reconnection: Use deviceToken (obtained from first registration)
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, Optional, Tuple

from app.config import settings
from app.core.database import AsyncSessionLocal
from app.core.logging import get_logger
from app.models.device import DeviceStatus
from app.schemas.tcp_rpc import JsonRpcErrorCode
from app.services.bind_code_service import bind_code_service
from app.services.device_service import DeviceService
from app.services.tcp_connection_manager import tcp_connection_manager

logger = get_logger("services.tcp_rpc_server")


class TcpRpcServer:
    """TCP JSON-RPC Server for Peekaboo protocol.

    Listens for TCP connections from Peekaboo devices and handles
    the JSON-RPC 2.0 protocol for device control.

    Authentication is performed using bind codes (first-time registration)
    or device tokens (reconnection).
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 9876,
    ) -> None:
        """Initialize the TCP RPC server.

        Args:
            host: Host address to bind to.
            port: Port number to listen on.
        """
        self.host = host
        self.port = port
        self.server: Optional[asyncio.AbstractServer] = None
        self._serving_task: Optional[asyncio.Task[None]] = None

    async def start(self) -> None:
        """Start the TCP server."""
        self.server = await asyncio.start_server(
            self._handle_connection, self.host, self.port
        )
        addr = self.server.sockets[0].getsockname()
        logger.info(f"TCP RPC Server listening on {addr[0]}:{addr[1]}")

        # Start serving in background
        self._serving_task = asyncio.create_task(self.server.serve_forever())

    async def stop(self) -> None:
        """Stop the TCP server."""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            logger.info("TCP RPC Server stopped")

        if self._serving_task:
            self._serving_task.cancel()
            try:
                await self._serving_task
            except asyncio.CancelledError:
                pass

    async def _handle_connection(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """Handle a new TCP connection.

        Args:
            reader: Async stream reader.
            writer: Async stream writer.
        """
        addr = writer.get_extra_info("peername")
        logger.info(f"New TCP connection from {addr}")

        device_id: Optional[str] = None

        try:
            # 1. Wait for auth request
            message = await self._read_message(reader)
            if message is None:
                return

            if message.get("method") != "auth":
                logger.warning(f"First message from {addr} must be 'auth'")
                await self._send_error(
                    writer,
                    message.get("id"),
                    JsonRpcErrorCode.INVALID_REQUEST,
                    "First message must be 'auth'",
                )
                return

            # 2. Handle authentication (bind code or device token)
            params = message.get("params", {})
            auth_result = await self._authenticate(params, addr)

            if auth_result is None:
                # Authentication failed - error already sent in _authenticate
                await self._send_error(
                    writer,
                    message.get("id"),
                    JsonRpcErrorCode.AUTH_FAILED,
                    "Authentication failed: invalid bind code or device token",
                )
                return

            device_id, device_token, project_id, device_name, device_version, is_new_registration = auth_result

            # Register connection
            connection = await tcp_connection_manager.register_connection(
                agent_id=device_id,
                name=device_name,
                version=device_version,
                capabilities=["tools/call", "tools/list", "ping"],  # Default capabilities
                reader=reader,
                writer=writer,
                project_id=project_id,
                device_db_id=device_id,
            )

            # Build auth success response
            response_data: Dict[str, Any] = {
                "status": "ok",
                "deviceId": device_id,
                "projectId": project_id,
            }

            if is_new_registration and device_token:
                response_data["deviceToken"] = device_token
                response_data["message"] = "Device registered successfully"
            else:
                response_data["message"] = "Reconnected successfully"

            await self._send_response(writer, message.get("id"), response_data)

            logger.info(
                f"TCP device authenticated: {device_name} v{device_version} ({device_id})"
                f" [{'new' if is_new_registration else 'reconnected'}]"
            )

            # 3. Fetch tools list
            tools = await connection.list_tools(timeout=30)
            if tools:
                logger.info(f"Device {device_id} supports {len(tools)} tools")

            # 4. Main message loop
            while True:
                msg = await self._read_message(reader)
                if msg is None:
                    break

                # Handle response messages (from our requests to the device)
                if "result" in msg or "error" in msg:
                    connection.handle_response(msg)
                    continue

                # Handle incoming requests/notifications
                method = msg.get("method")
                msg_id = msg.get("id")

                if method == "ping":
                    # Respond to ping from device
                    tcp_connection_manager.update_heartbeat(device_id)
                    if msg_id is not None:
                        await self._send_response(
                            writer,
                            msg_id,
                            {"pong": True, "timestamp": int(asyncio.get_event_loop().time())},
                        )

                elif method == "pong":
                    # Handle pong response (notification)
                    tcp_connection_manager.update_heartbeat(device_id)

                elif method == "heartbeat":
                    # Handle heartbeat from device
                    tcp_connection_manager.update_heartbeat(device_id)
                    if msg_id is not None:
                        await self._send_response(writer, msg_id, {"status": "ok"})

                else:
                    logger.debug(
                        f"Received message from TCP device {device_id}: {method}"
                    )

        except ConnectionError:
            logger.info(f"TCP connection closed by {addr}")
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON from {addr}: {e}")
        except Exception as e:
            logger.error(f"Error handling TCP connection from {addr}: {e}")
        finally:
            if device_id:
                # Update device status to offline in database
                await self._update_device_offline(device_id)
                await tcp_connection_manager.unregister_connection(device_id)
            else:
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception:
                    pass

    async def _authenticate(
        self,
        params: Dict[str, Any],
        addr: Any,
    ) -> Optional[Tuple[str, Optional[str], str, str, str, bool]]:
        """Authenticate a device using bind code or device token.

        Args:
            params: Auth request parameters.
            addr: Client address (for logging).

        Returns:
            Tuple of (device_id, device_token, project_id, device_name, device_version, is_new_registration)
            or None if authentication failed.
        """
        bind_code = params.get("bindCode")
        device_token = params.get("deviceToken")
        device_info = params.get("deviceInfo", {})

        device_name = device_info.get("name", "Unknown Device")
        device_version = device_info.get("version", "unknown")

        if not bind_code and not device_token:
            logger.warning(f"Auth from {addr}: neither bindCode nor deviceToken provided")
            return None

        async with AsyncSessionLocal() as db:
            device_service = DeviceService(db)

            if bind_code:
                # First-time registration using bind code
                os_name = device_info.get("os")
                if not os_name:
                    logger.warning(f"Auth from {addr}: OS is required for first-time registration")
                    return None

                device = await device_service.register_device(
                    bind_code=bind_code,
                    device_name=device_name,
                    device_type="desktop",
                    os=os_name,
                    os_version=device_info.get("osVersion"),
                    screen_resolution=device_info.get("screenResolution"),
                )

                if not device:
                    logger.warning(f"Auth from {addr}: invalid or expired bind code")
                    return None

                logger.info(f"Device registered: {device_name} ({device.id}) for project {device.project_id}")
                return (
                    str(device.id),
                    device.device_token,
                    str(device.project_id),
                    device_name,
                    device_version,
                    True,  # is_new_registration
                )

            elif device_token:
                # Reconnection using device token
                device = await device_service.get_device_by_token(device_token)

                if not device:
                    logger.warning(f"Auth from {addr}: invalid device token")
                    return None

                # Update device status to online
                await device_service.update_device_status(device.id, DeviceStatus.ONLINE)

                logger.info(f"Device reconnected: {device.device_name} ({device.id})")
                return (
                    str(device.id),
                    None,  # Don't return token on reconnection
                    str(device.project_id),
                    device.device_name,
                    device_version,
                    False,  # is_new_registration
                )

        return None

    async def _update_device_offline(self, device_id: str) -> None:
        """Update device status to offline when connection closes.

        Args:
            device_id: Device ID to update.
        """
        try:
            import uuid as uuid_module
            async with AsyncSessionLocal() as db:
                device_service = DeviceService(db)
                await device_service.update_device_status(
                    uuid_module.UUID(device_id),
                    DeviceStatus.OFFLINE,
                )
                logger.debug(f"Device {device_id} status updated to offline")
        except Exception as e:
            logger.warning(f"Failed to update device {device_id} status to offline: {e}")

    async def _read_message(
        self, reader: asyncio.StreamReader
    ) -> Optional[Dict[str, Any]]:
        """Read a single JSON-RPC message from the stream.

        Args:
            reader: Async stream reader.

        Returns:
            Parsed message dict or None if connection closed.
        """
        try:
            line = await reader.readline()
            if not line:
                return None
            return json.loads(line.decode("utf-8").strip())
        except json.JSONDecodeError:
            raise
        except Exception:
            return None

    async def _send_message(
        self, writer: asyncio.StreamWriter, message: Dict[str, Any]
    ) -> None:
        """Send a JSON-RPC message.

        Args:
            writer: Async stream writer.
            message: Message to send.
        """
        data = (json.dumps(message) + "\n").encode("utf-8")
        writer.write(data)
        await writer.drain()

    async def _send_response(
        self,
        writer: asyncio.StreamWriter,
        msg_id: Any,
        result: Any,
    ) -> None:
        """Send a JSON-RPC success response.

        Args:
            writer: Async stream writer.
            msg_id: Request ID.
            result: Response result.
        """
        response = {"jsonrpc": "2.0", "id": msg_id, "result": result}
        await self._send_message(writer, response)

    async def _send_error(
        self,
        writer: asyncio.StreamWriter,
        msg_id: Any,
        code: int,
        message: str,
        data: Optional[Any] = None,
    ) -> None:
        """Send a JSON-RPC error response.

        Args:
            writer: Async stream writer.
            msg_id: Request ID.
            code: Error code.
            message: Error message.
            data: Optional error data.
        """
        error: Dict[str, Any] = {"code": code, "message": message}
        if data is not None:
            error["data"] = data
        response = {"jsonrpc": "2.0", "id": msg_id, "error": error}
        await self._send_message(writer, response)


# Global singleton instance
tcp_rpc_server = TcpRpcServer(
    host=settings.TCP_RPC_HOST,
    port=settings.TCP_RPC_PORT,
)
