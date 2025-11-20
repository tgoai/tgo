"""
Main FastAPI application for TGO RAG Service.
"""

import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict

from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from .config import get_settings
from .database import close_database, database_health_check, init_database
from .logging_config import get_logger, init_logging_from_settings, set_request_context, clear_request_context
from .routers import collections, files, health, monitoring, embedding_config
from .schemas.common import ErrorResponse
from .startup_banner import (
    print_startup_banner,
    print_config_info,
    print_startup_summary,
    log_startup_step,
    log_startup_success,
    log_startup_error,
    print_section_header,
    print_section_footer,
    Symbols
)

# Initialize centralized logging configuration
init_logging_from_settings()

# Get logger for this module
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager for startup and shutdown events with enhanced logging.
    """
    settings = get_settings()
    dev_project_created = False

    # Print beautiful startup banner
    print_startup_banner(settings.app_name, settings.app_version, settings.environment)

    # Show configuration information
    config_info = {
        "Environment": settings.environment,
        "Debug Mode": settings.debug,
        "Host": settings.host,
        "Port": settings.port,
        "Database URL": settings.database_url,
        "Redis URL": settings.redis_url,
        "Log Level": settings.log_level
    }
    print_config_info(config_info)

    # Startup process
    print_section_header("Initialization", Symbols.GEAR)
    log_startup_step("Starting TGO RAG Service initialization", version=settings.app_version, environment=settings.environment)

    try:
        # Initialize database
        log_startup_step("Initializing database connection...")
        await init_database()
        log_startup_success("Database initialized successfully")

        # Set up development environment if needed
        if settings.environment.lower() == "development":
            log_startup_step("Setting up development environment...")
            # Check if development project was created
            from .dev_utils import DEV_API_KEY
            from .database import get_db_session
            from .models.projects import Project
            from sqlalchemy import select

            async with get_db_session() as db:
                query = select(Project).where(Project.api_key == DEV_API_KEY)
                result = await db.execute(query)
                existing_project = result.scalar_one_or_none()


            # Check if project was created during setup
            async with get_db_session() as db:
                query = select(Project).where(Project.api_key == DEV_API_KEY)
                result = await db.execute(query)
                project_after = result.scalar_one_or_none()

            if not existing_project and project_after:
                dev_project_created = True
                log_startup_success("Development project created successfully")
            elif existing_project:
                log_startup_success("Development project already exists")

        # TODO: Initialize other services (Redis, Vector DB, etc.)
        log_startup_step("Initializing additional services...")
        log_startup_success("Additional services initialized")

        print_section_footer()

        # Print startup summary
        print_startup_summary(
            host=settings.host,
            port=settings.port,
            environment=settings.environment,
            docs_enabled=settings.debug,
            dev_project_created=dev_project_created
        )

        yield

    except Exception as e:
        log_startup_error("Failed to start application", error=str(e))
        print_section_footer()
        raise
    finally:
        # Shutdown
        print_section_header("Shutdown", Symbols.GEAR)
        log_startup_step("Shutting down TGO RAG Service")
        await close_database()
        log_startup_success("Application shutdown complete")
        print_section_footer()


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.

    Returns:
        FastAPI: Configured application instance
    """
    settings = get_settings()

    # Create FastAPI app with custom configuration and OpenAPI security scheme
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="TGO-Tech RAG (Retrieval-Augmented Generation) Service for document processing and semantic search",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # API Key security scheme removed (internal-only service)

    # Add middleware
    setup_middleware(app, settings)

    # Add routers
    setup_routers(app)

    # Add exception handlers
    setup_exception_handlers(app)

    # Root endpoint
    @app.get("/", include_in_schema=False)
    async def root():
        """Root endpoint with basic service information."""
        settings = get_settings()
        return {
            "service": settings.app_name,
            "version": settings.app_version,
            "environment": settings.environment,
            "status": "running",
            "docs_url": "/docs",
            "health_check": "/health",
        }

    return app




def setup_middleware(app: FastAPI, settings) -> None:
    """
    Configure application middleware.

    Args:
        app: FastAPI application instance
        settings: Application settings
    """
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=settings.cors_allow_methods,
        allow_headers=settings.cors_allow_headers,
    )

    # Trusted host middleware (security)
    if settings.environment == "production":
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=["*"]
        )

    # Request context and logging middleware
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        """
        Log all HTTP requests with timing information and set request context.

        Automatically generates a request_id and sets it in the logging context
        so all logs within this request will include the request_id.
        """
        start_time = time.time()

        # Generate unique request ID
        request_id = str(uuid.uuid4())

        # Set request context for automatic inclusion in all logs
        set_request_context(request_id=request_id)

        try:
            # Log request (will automatically include request_id from context)
            logger.info(
                "Request started",
                method=request.method,
                url=str(request.url),
                client_ip=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
            )

            # Process request
            response = await call_next(request)

            # Calculate processing time
            process_time = time.time() - start_time

            # Log response (will automatically include request_id from context)
            logger.info(
                "Request completed",
                method=request.method,
                url=str(request.url),
                status_code=response.status_code,
                process_time_ms=round(process_time * 1000, 2),
            )

            # Add timing and request ID headers
            response.headers["X-Process-Time"] = str(process_time)
            response.headers["X-Request-ID"] = request_id

            return response
        finally:
            # Clean up request context
            clear_request_context()


def setup_routers(app: FastAPI) -> None:
    """
    Configure application routers.

    Args:
        app: FastAPI application instance
    """
    # Health and monitoring endpoints
    app.include_router(health.router, tags=["Health"])
    app.include_router(monitoring.router, tags=["Monitoring"])

    # API v1 endpoints
    api_v1_prefix = "/v1"

    # Collections endpoints
    app.include_router(
        collections.router,
        prefix=f"{api_v1_prefix}/collections",
        tags=["Collections"]
    )

    # Files endpoints
    app.include_router(
        files.router,
        prefix=f"{api_v1_prefix}/files",
        tags=["Files"]
    )
    # Embedding configuration endpoints (no auth)
    app.include_router(
        embedding_config.router,
        prefix=f"{api_v1_prefix}/embedding-configs",
        tags=["Embedding Configs"],
    )


    # TODO: Add more routers (documents, search, etc.)


def setup_exception_handlers(app: FastAPI) -> None:
    """
    Configure global exception handlers to ensure consistent error response format.

    Args:
        app: FastAPI application instance
    """

    # Unified HTTP exception handler for both Starlette and FastAPI HTTP exceptions
    async def _http_exception_handler(request: Request, exc):
        """Handle HTTP exceptions with a single handler and consistent ErrorResponse format."""
        # DEBUG: Print to console to verify handler is called
        print(f"[DEBUG] HTTP exception handler called! Exception type: {type(exc).__name__}")

        error_code_map = {
            400: "BAD_REQUEST",
            401: "UNAUTHORIZED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            405: "METHOD_NOT_ALLOWED",
            409: "CONFLICT",
            413: "PAYLOAD_TOO_LARGE",
            415: "UNSUPPORTED_MEDIA_TYPE",
            422: "UNPROCESSABLE_ENTITY",
            429: "TOO_MANY_REQUESTS",
            500: "INTERNAL_SERVER_ERROR",
            502: "BAD_GATEWAY",
            503: "SERVICE_UNAVAILABLE",
            504: "GATEWAY_TIMEOUT",
        }

        status_code = getattr(exc, "status_code", 500)
        detail = getattr(exc, "detail", "HTTP error")
        error_code = error_code_map.get(status_code, "HTTP_ERROR")

        # DEBUG: Print before logging
        print(f"[DEBUG] About to log warning: status_code={status_code}, detail={detail}")

        logger.warning(
            "HTTP exception occurred",
            status_code=status_code,
            detail=detail,
            url=str(request.url),
            method=request.method,
        )

        # DEBUG: Print after logging
        print(f"[DEBUG] Warning logged successfully")

        return JSONResponse(
            status_code=status_code,
            content=ErrorResponse(
                error={
                    "code": error_code,
                    "message": detail,
                    "details": {"status_code": status_code},
                }
            ).model_dump(),
        )

    # Register the same handler for both FastAPI and Starlette HTTP exceptions to avoid duplication
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
    app.add_exception_handler(HTTPException, _http_exception_handler)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Handle Pydantic validation errors with consistent ErrorResponse format."""
        logger.warning(
            "Validation error occurred",
            errors=exc.errors(),
            url=str(request.url),
            method=request.method
        )

        return JSONResponse(
            status_code=422,
            content=ErrorResponse(
                error={
                    "code": "VALIDATION_ERROR",
                    "message": "Request validation failed",
                    "details": {
                        "validation_errors": exc.errors()
                    }
                }
            ).model_dump()
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        """Handle ValueError exceptions."""
        logger.error("ValueError occurred", error=str(exc), url=str(request.url))
        return JSONResponse(
            status_code=400,
            content=ErrorResponse(
                error={
                    "code": "VALIDATION_ERROR",
                    "message": str(exc),
                    "details": {"type": "ValueError"}
                }
            ).model_dump()
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Handle all other exceptions."""
        logger.error("Unhandled exception occurred", error=str(exc), url=str(request.url), exc_info=True)
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error={
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An internal server error occurred",
                    "details": {"type": type(exc).__name__}
                }
            ).model_dump()
        )


# Create the application instance
app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "src.rag_service.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        log_level=settings.log_level.lower(),
        # Disable uvicorn's log config to prevent it from overriding our logging setup
        # log_config=None,  # Uncomment this if warning logs don't appear
    )
