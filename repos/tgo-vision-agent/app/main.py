"""TGO Vision Agent Service - FastAPI Application Entry Point."""
from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from app.core.config import settings

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s:%(name)s:%(message)s",
    force=True,  # Force reconfiguration even if already configured
)

# Explicitly set log level for app modules to ensure logs are visible
logging.getLogger("app").setLevel(logging.DEBUG)
logging.getLogger("app.workers").setLevel(logging.DEBUG)
logging.getLogger("app.domain").setLevel(logging.DEBUG)
logging.getLogger("app.services").setLevel(logging.DEBUG)

logger = logging.getLogger(__name__)

from app.api.v1 import health, sessions, messages, status, screenshots
from app.db.base import engine, Base

# Import models to ensure they are registered with SQLAlchemy
from app.db import models  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown."""
    logger.info("Starting TGO Vision Agent Service...")

    # Import automators to register them
    from app.domain.apps.wechat.automator import WeChatAutomator  # noqa: F401
    logger.info("Registered app automators: wechat")

    # Note: Database migrations are run via Alembic in Dockerfile/entrypoint
    # We create tables here as a fallback for development
    try:
        async with engine.begin() as conn:
            # Create all tables if they don't exist
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables verified/created")
    except Exception as e:
        logger.warning(f"Database initialization check failed (may be normal): {e}")

    # Initialize and restore workers for active sessions
    from app.workers.worker_manager import get_worker_manager
    worker_manager = get_worker_manager()
    try:
        restored_count = await worker_manager.restore_active_sessions()
        logger.info(f"Restored {restored_count} active session workers")
    except Exception as e:
        logger.error(f"Failed to restore session workers: {e}")

    try:
        yield
    finally:
        logger.info("Shutting down TGO Vision Agent Service...")

        # Shutdown all workers gracefully
        try:
            await worker_manager.shutdown()
            logger.info("All workers shut down")
        except Exception as e:
            logger.error(f"Error shutting down workers: {e}")

        # Cleanup: dispose of the database engine
        await engine.dispose()
        logger.info("Database connections closed")


app = FastAPI(
    title="TGO Vision Agent",
    description="Vision AI Agent Service for UI Automation using VLM + AgentBay",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/v1/docs",
    redoc_url="/v1/redoc",
)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Add request ID to all requests for tracing."""
    rid = request.headers.get("x-request-id") or str(uuid.uuid4())
    request.state.request_id = rid
    response = await call_next(request)
    response.headers["x-request-id"] = rid
    return response


# Include routers
app.include_router(health.router, tags=["health"])
app.include_router(sessions.router, prefix="/v1", tags=["sessions"])
app.include_router(messages.router, prefix="/v1", tags=["messages"])
app.include_router(status.router, prefix="/v1", tags=["status"])
app.include_router(screenshots.router, prefix="/v1", tags=["screenshots"])
