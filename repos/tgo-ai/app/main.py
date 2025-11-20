"""FastAPI application entry point."""

import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.api import api_router
from app.config import settings
from app.database import close_db, init_db
from app.exceptions import TGOAIServiceException


request_logger = logging.getLogger("app.requests")
request_logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    # Startup
    await init_db()

    # Start periodic embedding sync retry loop (if enabled)
    from app.tasks.embedding_sync_retry import start_embedding_sync_retry_loop
    stop_event = asyncio.Event()
    task = asyncio.create_task(start_embedding_sync_retry_loop(stop_event))

    try:
        yield
    finally:
        # Shutdown
        stop_event.set()
        try:
            await asyncio.wait_for(task, timeout=5)
        except Exception:
            task.cancel()
        await close_db()


# Create FastAPI application
app = FastAPI(
    title="TGO-Tech AI Service",
    description="AI/ML Operations Microservice for TGO-Tech customer service platform",
    version=__version__,
    docs_url="/docs" if settings.docs_enabled else None,
    redoc_url="/redoc" if settings.redoc_enabled else None,
    lifespan=lifespan,
    # OpenAPI security schemas
    openapi_tags=[
        {
            "name": "Authentication",
            "description": "Authentication endpoints and utilities",
        },
        {
            "name": "Teams",
            "description": "Team management operations",
        },
        {
            "name": "Agents",
            "description": "AI agent management operations",
        },
    ],
)

# Configure OpenAPI security schemas
def custom_openapi():
    """Custom OpenAPI schema with security definitions."""
    if app.openapi_schema:
        return app.openapi_schema

    from fastapi.openapi.utils import get_openapi

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )


    # Add error response schemas
    if "schemas" not in openapi_schema["components"]:
        openapi_schema["components"]["schemas"] = {}

    openapi_schema["components"]["schemas"]["ErrorDetail"] = {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Error code",
                "examples": ["TEAM_NOT_FOUND", "AGENT_NOT_FOUND", "AUTHENTICATION_FAILED"]
            },
            "message": {
                "type": "string",
                "description": "Human-readable error message",
                "examples": ["The specified team was not found"]
            },
            "details": {
                "type": "object",
                "nullable": True,
                "description": "Additional error context and details",
                "examples": [{"team_id": "123e4567-e89b-12d3-a456-426614174000"}]
            }
        },
        "required": ["code", "message", "details"]
    }

    openapi_schema["components"]["schemas"]["Error"] = {
        "type": "object",
        "properties": {
            "error": {
                "$ref": "#/components/schemas/ErrorDetail"
            },
            "request_id": {
                "type": "string",
                "format": "uuid",
                "description": "Unique request identifier for tracking"
            }
        },
        "required": ["error", "request_id"]
    }


    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log incoming requests and their outcomes."""
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id

    client_host = request.client.host if request.client else "unknown"
    method = request.method
    path = request.url.path
    query_string = request.url.query
    start_time = time.perf_counter()

    request_logger.info(
        "request.start request_id=%s method=%s path=%s query=%s client=%s",
        request_id,
        method,
        path,
        query_string or "-",
        client_host,
    )

    try:
        response = await call_next(request)
    except Exception:
        duration_ms = (time.perf_counter() - start_time) * 1000
        request_logger.exception(
            "request.error request_id=%s method=%s path=%s duration_ms=%.2f",
            request_id,
            method,
            path,
            duration_ms,
        )
        raise

    duration_ms = (time.perf_counter() - start_time) * 1000
    response.headers["X-Request-ID"] = request_id
    response_length = response.headers.get("content-length", "-")

    request_logger.info(
        "request.end request_id=%s method=%s path=%s status=%s duration_ms=%.2f response_length=%s",
        request_id,
        method,
        path,
        response.status_code,
        duration_ms,
        response_length,
    )

    return response


# Global exception handler
@app.exception_handler(TGOAIServiceException)
async def tgo_ai_service_exception_handler(
    request: Request, exc: TGOAIServiceException
) -> JSONResponse:
    """Handle custom TGO AI Service exceptions."""
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    
    # Map exception types to HTTP status codes
    if exc.code == "AUTHENTICATION_FAILED":
        status_code = status.HTTP_401_UNAUTHORIZED
    elif exc.code == "ACCESS_DENIED":
        status_code = status.HTTP_403_FORBIDDEN
    elif exc.code.endswith("_NOT_FOUND"):
        status_code = status.HTTP_404_NOT_FOUND
    elif exc.code == "VALIDATION_ERROR":
        status_code = status.HTTP_400_BAD_REQUEST
    elif exc.code.endswith("_CONFLICT"):
        status_code = status.HTTP_409_CONFLICT
    elif exc.code == "RATE_LIMIT_EXCEEDED":
        status_code = status.HTTP_429_TOO_MANY_REQUESTS

    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))

    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            },
            "request_id": request_id,
        },
        headers={"X-Request-ID": request_id},
    )


# Global HTTP exception handler
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle FastAPI HTTP exceptions."""
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": "HTTP_ERROR",
                "message": exc.detail,
                "details": {},
            },
            "request_id": request_id,
        },
        headers={"X-Request-ID": request_id},
    )


# Health check endpoint
@app.get("/health", include_in_schema=settings.health_check_enabled)
async def health_check() -> dict:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "tgo-ai-service",
        "version": __version__,
        "environment": settings.environment,
    }


# Root endpoint
@app.get("/", include_in_schema=False)
async def root() -> dict:
    """Root endpoint with service information."""
    return {
        "service": "TGO-Tech AI Service",
        "version": __version__,
        "description": "AI/ML Operations Microservice",
        "docs_url": "/docs" if settings.docs_enabled else None,
        "health_url": "/health",
    }


# Include API routes
app.include_router(api_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        log_level=settings.log_level.lower(),
    )
