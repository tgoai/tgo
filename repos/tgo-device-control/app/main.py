"""FastAPI application entry point for TGO Device Control Service."""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.logging import setup_logging, startup_log

# Setup logging
setup_logging()


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Application lifespan manager."""
    # Startup logic
    from app.services.tcp_connection_manager import tcp_connection_manager
    from app.services.tcp_rpc_server import tcp_rpc_server

    startup_log("=" * 64)
    startup_log("🖥️  TGO Device Control Service Starting...")
    startup_log("=" * 64)
    
    # Debug: Log configuration
    startup_log(f"[DEBUG] Configuration:")
    startup_log(f"[DEBUG]   HTTP HOST: {settings.HOST}")
    startup_log(f"[DEBUG]   HTTP PORT: {settings.PORT}")
    startup_log(f"[DEBUG]   TCP_RPC_HOST: {settings.TCP_RPC_HOST}")
    startup_log(f"[DEBUG]   TCP_RPC_PORT: {settings.TCP_RPC_PORT}")
    startup_log(f"[DEBUG]   REDIS_URL: {settings.REDIS_URL}")
    startup_log(f"[DEBUG]   DATABASE_URL: {settings.DATABASE_URL[:50]}...")
    startup_log(f"[DEBUG]   ENVIRONMENT: {settings.ENVIRONMENT}")
    startup_log(f"[DEBUG]   DEBUG: {settings.DEBUG}")
    startup_log(f"[DEBUG]   LOG_LEVEL: {settings.LOG_LEVEL}")

    # Initialize TCP connection manager
    startup_log("[DEBUG] Initializing TCP connection manager...")
    await tcp_connection_manager.initialize()
    startup_log("[DEBUG] TCP connection manager initialized")

    # Start TCP RPC server
    startup_log("[DEBUG] Starting TCP RPC server...")
    await tcp_rpc_server.start()
    startup_log("[DEBUG] TCP RPC server started")

    startup_log(f"   📍 HTTP API: http://0.0.0.0:{settings.PORT}")
    startup_log(f"   🤖 TCP RPC: {settings.TCP_RPC_HOST}:{settings.TCP_RPC_PORT}")
    startup_log(f"   📚 API Docs: http://localhost:{settings.PORT}/docs")
    startup_log(f"   🏥 Health Check: http://localhost:{settings.PORT}/health")
    startup_log("")
    startup_log("🎉 Device Control Service is ready!")
    startup_log("=" * 64)

    yield

    # Shutdown logic
    startup_log("Shutting down Device Control Service...")
    await tcp_rpc_server.stop()
    await tcp_connection_manager.shutdown()


app = FastAPI(
    title=settings.SERVICE_NAME,
    description="Device Control Service for TGO - manages remote device connections for AI agents",
    version=settings.SERVICE_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": settings.SERVICE_NAME,
        "version": settings.SERVICE_VERSION,
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    from app.services.tcp_connection_manager import tcp_connection_manager
    from app.services.tcp_rpc_server import tcp_rpc_server

    tcp_server_status = "unknown"
    if tcp_rpc_server.server:
        tcp_server_status = "serving" if tcp_rpc_server.server.is_serving() else "not_serving"
    else:
        tcp_server_status = "not_started"

    return {
        "status": "healthy",
        "connected_devices": tcp_connection_manager.get_connected_count(),
        "tcp_server": {
            "status": tcp_server_status,
            "host": settings.TCP_RPC_HOST,
            "port": settings.TCP_RPC_PORT,
        },
    }


# Include API routes
from app.api.v1 import router as api_v1_router

app.include_router(api_v1_router, prefix="/v1")


@app.get("/debug/status")
async def debug_status():
    """Debug endpoint to check service status and connectivity."""
    from app.services.tcp_connection_manager import tcp_connection_manager
    from app.services.tcp_rpc_server import tcp_rpc_server
    from app.services.bind_code_service import bind_code_service
    import socket
    
    result = {
        "config": {
            "tcp_rpc_host": settings.TCP_RPC_HOST,
            "tcp_rpc_port": settings.TCP_RPC_PORT,
            "http_host": settings.HOST,
            "http_port": settings.PORT,
            "redis_url": settings.REDIS_URL,
            "environment": settings.ENVIRONMENT,
            "log_level": settings.LOG_LEVEL,
        },
        "tcp_server": {},
        "redis": {},
        "connections": [],
    }
    
    # TCP Server status
    if tcp_rpc_server.server:
        result["tcp_server"]["is_serving"] = tcp_rpc_server.server.is_serving()
        result["tcp_server"]["sockets"] = [
            str(s.getsockname()) for s in tcp_rpc_server.server.sockets
        ]
    else:
        result["tcp_server"]["is_serving"] = False
        result["tcp_server"]["error"] = "Server not started"
    
    # Test TCP port accessibility
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        local_result = sock.connect_ex(("127.0.0.1", settings.TCP_RPC_PORT))
        sock.close()
        result["tcp_server"]["local_port_check"] = "accessible" if local_result == 0 else f"error_code_{local_result}"
    except Exception as e:
        result["tcp_server"]["local_port_check"] = f"error: {e}"
    
    # Redis connectivity
    try:
        await bind_code_service.redis.ping()
        result["redis"]["status"] = "connected"
        # List bind codes
        keys = await bind_code_service.redis.keys("dc:bind_code:*")
        result["redis"]["active_bind_codes"] = len(keys)
        result["redis"]["bind_code_keys"] = keys[:10]  # Show first 10
    except Exception as e:
        result["redis"]["status"] = f"error: {e}"
    
    # Active connections
    connections = tcp_connection_manager.list_connections()
    result["connections"] = [
        {
            "agent_id": c.agent_id,
            "name": c.name,
            "version": c.version,
            "project_id": c.project_id,
            "connected_at": c.connected_at.isoformat(),
            "last_seen": c.last_seen.isoformat(),
        }
        for c in connections
    ]
    
    return result


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.is_development,
    )
