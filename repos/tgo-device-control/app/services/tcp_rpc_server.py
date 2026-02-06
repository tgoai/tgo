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
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple

from app.config import settings
from app.core.database import AsyncSessionLocal
from app.core.logging import get_logger
from app.models.device import DeviceStatus
from app.schemas.tcp_rpc import JsonRpcErrorCode
from app.services.bind_code_service import bind_code_service
from app.services.device_service import DeviceService
from app.services.tcp_connection_manager import tcp_connection_manager

if TYPE_CHECKING:
    from app.services.tcp_connection_manager import TcpDeviceConnection

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
        logger.info(f"[DEBUG] Starting TCP RPC Server on {self.host}:{self.port}...")
        try:
            self.server = await asyncio.start_server(
                self._handle_connection, self.host, self.port
            )
            addr = self.server.sockets[0].getsockname()
            logger.info(f"TCP RPC Server listening on {addr[0]}:{addr[1]}")
            logger.info(f"[DEBUG] TCP Server socket info: {self.server.sockets}")
            logger.info(f"[DEBUG] TCP Server is_serving: {self.server.is_serving()}")

            # Start serving in background
            self._serving_task = asyncio.create_task(self.server.serve_forever())
            logger.info("[DEBUG] TCP Server serve_forever task started")
        except Exception as e:
            logger.error(f"[DEBUG] Failed to start TCP RPC Server: {e}", exc_info=True)

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
        socket_info = writer.get_extra_info("socket")
        logger.info(f"[DEBUG] New TCP connection from {addr}")
        logger.info(f"[DEBUG] Socket info: {socket_info}")
        logger.info(f"[DEBUG] Connection extra info - sockname: {writer.get_extra_info('sockname')}")

        device_id: Optional[str] = None

        try:
            # 1. Wait for auth request
            logger.info(f"[DEBUG] Waiting for auth message from {addr}...")
            message = await self._read_message(reader)
            logger.info(f"[DEBUG] Received message from {addr}: {message}")
            if message is None:
                logger.warning(f"[DEBUG] No message received from {addr}, connection may have closed")
                return

            if message.get("method") != "auth":
                logger.warning(f"[DEBUG] First message from {addr} must be 'auth', got: {message.get('method')}")
                await self._send_error(
                    writer,
                    message.get("id"),
                    JsonRpcErrorCode.INVALID_REQUEST,
                    "First message must be 'auth'",
                )
                return

            # 2. Handle authentication (bind code or device token)
            params = message.get("params", {})
            logger.info(f"[DEBUG] Auth params from {addr}: bindCode={params.get('bindCode')}, hasDeviceToken={bool(params.get('deviceToken'))}")
            auth_result = await self._authenticate(params, addr)

            if auth_result is None:
                # Authentication failed - error already sent in _authenticate
                logger.warning(f"[DEBUG] Authentication failed for {addr}")
                await self._send_error(
                    writer,
                    message.get("id"),
                    JsonRpcErrorCode.AUTH_FAILED,
                    "Authentication failed: invalid bind code or device token",
                )
                return

            device_id, device_token, project_id, device_name, device_version, is_new_registration = auth_result
            logger.info(f"[DEBUG] Auth successful: device_id={device_id}, project_id={project_id}, is_new={is_new_registration}")

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

            # 3. Start message reader task in background
            # This is needed because list_tools() sends a request and waits for response,
            # but the response is read in the message loop. We need concurrent reading.
            reader_task = asyncio.create_task(
                self._message_reader_loop(reader, writer, connection, device_id)
            )

            # 4. Fetch tools list (now the reader task can handle the response)
            try:
                tools = await connection.list_tools(timeout=30)
                if tools:
                    logger.info(f"Device {device_id} supports {len(tools)} tools")
            except Exception as e:
                logger.warning(f"Failed to fetch tools list for device {device_id}: {e}")

            # 5. Wait for the reader task to complete (connection closed)
            await reader_task

        except ConnectionError as e:
            logger.info(f"[DEBUG] TCP connection closed by {addr}: {e}")
        except json.JSONDecodeError as e:
            logger.warning(f"[DEBUG] Invalid JSON from {addr}: {e}")
        except Exception as e:
            logger.error(f"[DEBUG] Error handling TCP connection from {addr}: {e}", exc_info=True)
        finally:
            logger.info(f"[DEBUG] Connection cleanup for {addr}, device_id={device_id}")
            if device_id:
                # Update device status to offline in database
                await self._update_device_offline(device_id)
                await tcp_connection_manager.unregister_connection(device_id)
            else:
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception as close_error:
                    logger.warning(f"[DEBUG] Error closing writer for {addr}: {close_error}")

    async def _message_reader_loop(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        connection: TcpDeviceConnection,
        device_id: str,
    ) -> None:
        """Background task to read and process messages from the device.

        This runs concurrently with any outgoing requests (like list_tools),
        allowing responses to be received while we wait for them.

        Args:
            reader: Async stream reader.
            writer: Async stream writer.
            connection: TcpDeviceConnection instance.
            device_id: Device ID for logging and heartbeat updates.
        """
        while True:
            try:
                msg = await self._read_message(reader)
                if msg is None:
                    break

                # Update heartbeat on ANY message received from device
                # This is more robust than only updating on specific heartbeat messages
                tcp_connection_manager.update_heartbeat(device_id)

                # Handle response messages (from our requests to the device)
                if "result" in msg or "error" in msg:
                    connection.handle_response(msg)
                    continue

                # Handle incoming requests/notifications
                method = msg.get("method")
                msg_id = msg.get("id")

                if method == "ping":
                    # Respond to ping from device
                    if msg_id is not None:
                        await self._send_response(
                            writer,
                            msg_id,
                            {"pong": True, "timestamp": int(asyncio.get_event_loop().time())},
                        )

                elif method == "pong":
                    # Handle pong response (notification) - heartbeat already updated above
                    pass

                elif method == "heartbeat":
                    # Handle heartbeat from device
                    if msg_id is not None:
                        await self._send_response(writer, msg_id, {"status": "ok"})

                else:
                    logger.debug(
                        f"Received message from TCP device {device_id}: {method}"
                    )
            except Exception as e:
                logger.warning(f"Error in message reader loop for {device_id}: {e}")
                break

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

        logger.info(f"[DEBUG] _authenticate called from {addr}")
        logger.info(f"[DEBUG] bind_code={bind_code}, has_device_token={bool(device_token)}")
        logger.info(f"[DEBUG] device_info={device_info}")

        if not bind_code and not device_token:
            logger.warning(f"[DEBUG] Auth from {addr}: neither bindCode nor deviceToken provided")
            return None

        try:
            async with AsyncSessionLocal() as db:
                logger.info(f"[DEBUG] Database session created for auth from {addr}")
                device_service = DeviceService(db)

                if bind_code:
                    # First-time registration using bind code
                    logger.info(f"[DEBUG] Processing bind_code registration from {addr}")
                    os_name = device_info.get("os")
                    if not os_name:
                        logger.warning(f"[DEBUG] Auth from {addr}: OS is required for first-time registration")
                        return None

                    logger.info(f"[DEBUG] Calling device_service.register_device with bind_code={bind_code}")
                    device = await device_service.register_device(
                        bind_code=bind_code,
                        device_name=device_name,
                        device_type="desktop",
                        os=os_name,
                        os_version=device_info.get("osVersion"),
                        screen_resolution=device_info.get("screenResolution"),
                    )

                    if not device:
                        logger.warning(f"[DEBUG] Auth from {addr}: invalid or expired bind code '{bind_code}'")
                        return None

                    logger.info(f"[DEBUG] Device registered: {device_name} ({device.id}) for project {device.project_id}")
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
                    logger.info(f"[DEBUG] Processing device_token reconnection from {addr}")
                    device = await device_service.get_device_by_token(device_token)

                    if not device:
                        logger.warning(f"[DEBUG] Auth from {addr}: invalid device token")
                        return None

                    # Update device status to online
                    await device_service.update_device_status(device.id, DeviceStatus.ONLINE)

                    logger.info(f"[DEBUG] Device reconnected: {device.device_name} ({device.id})")
                    return (
                        str(device.id),
                        None,  # Don't return token on reconnection
                        str(device.project_id),
                        device.device_name,
                        device_version,
                        False,  # is_new_registration
                    )
        except Exception as e:
            logger.error(f"[DEBUG] Exception in _authenticate from {addr}: {e}", exc_info=True)
            return None

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
            logger.debug("[DEBUG] _read_message: waiting for readline...")
            line = await reader.readline()
            if not line:
                logger.debug("[DEBUG] _read_message: received empty line (connection closed)")
                return None
            decoded = line.decode("utf-8").strip()
            logger.debug(f"[DEBUG] _read_message: received raw data ({len(line)} bytes): {decoded[:200]}...")
            result = json.loads(decoded)
            logger.debug(f"[DEBUG] _read_message: parsed JSON successfully")
            return result
        except json.JSONDecodeError as e:
            logger.warning(f"[DEBUG] _read_message: JSON decode error: {e}")
            raise
        except Exception as e:
            logger.warning(f"[DEBUG] _read_message: unexpected error: {e}")
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
