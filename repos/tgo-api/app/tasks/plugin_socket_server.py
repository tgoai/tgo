"""Plugin Socket Server - Unix Socket server for plugin communication."""

from __future__ import annotations

import asyncio
import json
import os
import struct
from typing import Optional

from app.core.config import settings
from app.core.logging import get_logger
from app.services.plugin_manager import plugin_manager, PluginConnection

logger = get_logger("tasks.plugin_socket_server")

# Global state
_server: Optional[asyncio.AbstractServer] = None
_server_task: Optional[asyncio.Task] = None


async def _recv_message(reader: asyncio.StreamReader) -> Optional[dict]:
    """Receive a length-prefixed JSON message."""
    try:
        # Read 4-byte length prefix (big-endian)
        length_bytes = await reader.readexactly(4)
        length = struct.unpack(">I", length_bytes)[0]
        
        # Read JSON data
        json_bytes = await reader.readexactly(length)
        return json.loads(json_bytes.decode("utf-8"))
    except asyncio.IncompleteReadError:
        return None
    except Exception as e:
        logger.error(f"Error receiving message: {e}")
        return None


async def _send_message(writer: asyncio.StreamWriter, message: dict):
    """Send a length-prefixed JSON message."""
    json_bytes = json.dumps(message, ensure_ascii=False).encode("utf-8")
    length_prefix = struct.pack(">I", len(json_bytes))
    writer.write(length_prefix + json_bytes)
    await writer.drain()


async def _handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    """Handle a single plugin connection."""
    plugin_id: Optional[str] = None
    plugin: Optional[PluginConnection] = None
    peer = writer.get_extra_info("peername") or "unknown"
    
    logger.info(f"New plugin connection from {peer}")
    
    try:
        # First message must be a 'register' request
        first_msg = await asyncio.wait_for(_recv_message(reader), timeout=30)
        if not first_msg or first_msg.get("method") != "register":
            logger.warning(f"Invalid first message from {peer}, expected 'register'")
            await _send_message(writer, {
                "jsonrpc": "2.0",
                "id": first_msg.get("id") if first_msg else None,
                "error": {"code": -32600, "message": "First message must be 'register'"}
            })
            return
        
        # Extract registration info
        params = first_msg.get("params", {})
        pid = params.get("id")
        name = params.get("name", "unknown")
        version = params.get("version", "0.0.0")
        capabilities = params.get("capabilities", [])
        description = params.get("description")
        author = params.get("author")
        
        # Register the plugin
        plugin_id, plugin = await plugin_manager.register(
            plugin_id=pid,
            name=name,
            version=version,
            capabilities=capabilities,
            reader=reader,
            writer=writer,
            description=description,
            author=author,
        )
        
        # Send success response
        await _send_message(writer, {
            "jsonrpc": "2.0",
            "id": first_msg.get("id"),
            "result": {
                "success": True,
                "plugin_id": plugin_id,
                "host_version": settings.PROJECT_VERSION,
            }
        })
        
        logger.info(f"Plugin {name} v{version} registered as {plugin_id}")
        
        # Main message loop
        while True:
            message = await _recv_message(reader)
            if message is None:
                logger.info(f"Plugin {plugin_id} disconnected")
                break
            
            # Handle response (from our requests to the plugin)
            if "result" in message or "error" in message:
                await plugin_manager.handle_response(plugin, message)
            else:
                # This shouldn't happen in normal flow - plugins only respond
                logger.warning(f"Unexpected message from plugin {plugin_id}: {message.get('method')}")
    
    except asyncio.TimeoutError:
        logger.warning(f"Plugin connection from {peer} timed out during registration")
    except asyncio.CancelledError:
        logger.info(f"Plugin connection handler cancelled for {plugin_id or peer}")
    except Exception as e:
        logger.error(f"Error handling plugin connection {plugin_id or peer}: {e}")
    finally:
        # Cleanup
        if plugin_id:
            await plugin_manager.unregister(plugin_id)
        
        if not writer.is_closing():
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass


async def start_plugin_socket_server():
    """Start the plugin socket server as a background task."""
    global _server, _server_task
    
    if not settings.PLUGIN_ENABLED:
        logger.info("Plugin system is disabled")
        return
    
    if _server_task is not None and not _server_task.done():
        logger.warning("Plugin socket server is already running")
        return
    
    try:
        socket_path = settings.PLUGIN_SOCKET_PATH
        tcp_port = settings.PLUGIN_TCP_PORT
        
        if tcp_port:
            _server = await asyncio.start_server(
                _handle_client,
                host="0.0.0.0",
                port=tcp_port,
            )
            logger.info(f"Plugin socket server listening on TCP 0.0.0.0:{tcp_port}")
        else:
            # Ensure directory exists
            socket_dir = os.path.dirname(socket_path)
            if socket_dir and not os.path.exists(socket_dir):
                os.makedirs(socket_dir, exist_ok=True)
            
            # Remove existing socket file
            if os.path.exists(socket_path):
                try:
                    os.unlink(socket_path)
                except Exception as e:
                    logger.error(f"Failed to remove existing socket file {socket_path}: {e}")
            
            _server = await asyncio.start_unix_server(
                _handle_client,
                path=socket_path,
            )
            
            # Set socket permissions (readable/writable by all)
            try:
                os.chmod(socket_path, 0o666)
            except Exception as e:
                logger.warning(f"Failed to set socket permissions: {e}")
            
            logger.info(f"Plugin socket server listening on UNIX {socket_path}")
        
        # Run the server loop in a background task
        async def serve():
            async with _server:
                await _server.serve_forever()
                
        _server_task = asyncio.create_task(serve())
        logger.info("Plugin socket server task started")
    except Exception as e:
        logger.exception(f"Failed to start plugin socket server: {e}")



async def stop_plugin_socket_server():
    """Stop the plugin socket server."""
    global _server, _server_task
    
    # Shutdown all plugins gracefully
    await plugin_manager.shutdown_all()
    
    # Stop the server
    if _server:
        _server.close()
        try:
            await _server.wait_closed()
        except Exception:
            pass
        _server = None
    
    # Cancel the task
    if _server_task:
        _server_task.cancel()
        try:
            await _server_task
        except asyncio.CancelledError:
            pass
        _server_task = None
    
    # Remove socket file
    if os.path.exists(settings.PLUGIN_SOCKET_PATH):
        try:
            os.unlink(settings.PLUGIN_SOCKET_PATH)
        except Exception:
            pass
    
    logger.info("Plugin socket server stopped")

