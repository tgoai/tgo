"""WebSocket Server - Handles device WebSocket connections."""

import json
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect

from app.core.database import AsyncSessionLocal
from app.core.logging import get_logger
from app.models.device import DeviceStatus
from app.services.device_manager import device_manager
from app.services.device_service import DeviceService

logger = get_logger("services.websocket_server")


async def handle_device_connection(
    websocket: WebSocket,
    bind_code: Optional[str] = None,
    device_token: Optional[str] = None,
) -> None:
    """
    Handle a device WebSocket connection.

    Devices connect using either:
    - bind_code: For initial device registration
    - device_token: For reconnection of already registered devices
    """
    device_id: Optional[str] = None
    project_id: Optional[str] = None

    try:
        # Wait for registration message
        message = await websocket.receive_json()

        if message.get("method") != "register":
            await websocket.send_json({
                "jsonrpc": "2.0",
                "id": message.get("id"),
                "error": {
                    "code": -32600,
                    "message": "First message must be 'register'",
                },
            })
            return

        params = message.get("params", {})

        async with AsyncSessionLocal() as db:
            service = DeviceService(db)

            if device_token:
                # Reconnection with token
                device = await service.get_device_by_token(device_token)
                if not device:
                    await websocket.send_json({
                        "jsonrpc": "2.0",
                        "id": message.get("id"),
                        "error": {
                            "code": -32001,
                            "message": "Invalid device token",
                        },
                    })
                    return

                device_id = str(device.id)
                project_id = str(device.project_id)

                # Update device status
                await service.update_device_status(device.id, DeviceStatus.ONLINE)

                # Update device info if provided
                if params.get("screen_resolution"):
                    device.screen_resolution = params["screen_resolution"]
                    await db.commit()

            elif bind_code or params.get("bind_code"):
                # New device registration with bind code
                code = bind_code or params.get("bind_code")

                device = await service.register_device(
                    bind_code=code,
                    device_name=params.get("device_name", "Unknown Device"),
                    device_type=params.get("device_type", "desktop"),
                    os=params.get("os", "unknown"),
                    os_version=params.get("os_version"),
                    screen_resolution=params.get("screen_resolution"),
                )

                if not device:
                    await websocket.send_json({
                        "jsonrpc": "2.0",
                        "id": message.get("id"),
                        "error": {
                            "code": -32002,
                            "message": "Invalid or expired bind code",
                        },
                    })
                    return

                device_id = str(device.id)
                project_id = str(device.project_id)
                device_token = device.device_token

            else:
                await websocket.send_json({
                    "jsonrpc": "2.0",
                    "id": message.get("id"),
                    "error": {
                        "code": -32600,
                        "message": "Either bind_code or device_token is required",
                    },
                })
                return

        # Register device connection
        connection = await device_manager.register_device(
            device_id=device_id,
            project_id=project_id,
            device_name=params.get("device_name", "Unknown Device"),
            device_type=params.get("device_type", "desktop"),
            os=params.get("os", "unknown"),
            os_version=params.get("os_version"),
            screen_resolution=params.get("screen_resolution"),
            websocket=websocket,
        )

        # Send success response
        await websocket.send_json({
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "result": {
                "success": True,
                "device_id": device_id,
                "device_token": device_token,
            },
        })

        logger.info(f"Device connected: {device_id}")

        # Main message loop
        while True:
            try:
                message = await websocket.receive_json()

                # Handle pong response
                if message.get("method") == "pong":
                    device_manager.update_heartbeat(device_id)
                    continue

                # Handle response messages (from our requests to the device)
                if "result" in message or "error" in message:
                    connection.handle_response(message)
                    continue

                # Handle other methods if needed
                method = message.get("method")
                if method == "heartbeat":
                    device_manager.update_heartbeat(device_id)
                    await websocket.send_json({
                        "jsonrpc": "2.0",
                        "id": message.get("id"),
                        "result": {"status": "ok"},
                    })
                else:
                    logger.warning(f"Unknown method from device {device_id}: {method}")

            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON from device {device_id}")
                continue

    except WebSocketDisconnect:
        logger.info(f"Device disconnected during registration")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        # Cleanup
        if device_id:
            await device_manager.unregister_device(device_id)

            # Update device status in database
            async with AsyncSessionLocal() as db:
                service = DeviceService(db)
                await service.update_device_status(
                    device_id=device_id,
                    status=DeviceStatus.OFFLINE,
                )

            logger.info(f"Device cleanup complete: {device_id}")
