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

    # Initialize TCP connection manager
    await tcp_connection_manager.initialize()

    # Start TCP RPC server
    await tcp_rpc_server.start()

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

    return {
        "status": "healthy",
        "connected_devices": tcp_connection_manager.get_connected_count(),
    }


# Include API routes
from app.api.v1 import router as api_v1_router

app.include_router(api_v1_router, prefix="/v1")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.is_development,
    )
