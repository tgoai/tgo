"""WebSocket endpoint for device connections."""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import Optional

from app.core.logging import get_logger
from app.services.device_manager import device_manager
from app.services.websocket_server import handle_device_connection

router = APIRouter()
logger = get_logger(__name__)


@router.websocket("/ws/device")
async def websocket_device_endpoint(
    websocket: WebSocket,
    bind_code: Optional[str] = Query(None),
    device_token: Optional[str] = Query(None),
):
    """
    WebSocket endpoint for device connections.
    
    Devices connect using either:
    - bind_code: For initial device registration
    - device_token: For reconnection of already registered devices
    """
    await websocket.accept()
    
    logger.info(f"New WebSocket connection from {websocket.client}")
    
    try:
        await handle_device_connection(
            websocket=websocket,
            bind_code=bind_code,
            device_token=device_token,
        )
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {websocket.client}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        # Cleanup handled by device_manager
        pass
