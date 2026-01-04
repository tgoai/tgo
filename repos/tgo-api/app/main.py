"""FastAPI application entry point."""

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError
from fastapi.openapi.utils import get_openapi

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.dev_data import log_startup_banner, ensure_permissions_seed
from app.core.exceptions import (
    TGOAPIException,
    general_exception_handler,
    http_exception_handler,
    tgo_api_exception_handler,
    validation_exception_handler,
)
from app.schemas.base import ErrorResponse
from app.core.logging import setup_logging
from app.services.platform_type_seed import ensure_platform_types_seed


# Setup logging
setup_logging()

# Configure uvicorn logging for cleaner startup
import logging
logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
logging.getLogger("uvicorn").setLevel(logging.WARNING)

app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.PROJECT_DESCRIPTION,
    version=settings.PROJECT_VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
)

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add exception handlers
app.add_exception_handler(TGOAPIException, tgo_api_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(ValidationError, validation_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

# Include API router

app.include_router(api_router, prefix=settings.API_V1_STR)


def custom_openapi() -> dict:
    """Generate OpenAPI schema with unified error responses."""
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=settings.PROJECT_NAME,
        version=settings.PROJECT_VERSION,
        description=settings.PROJECT_DESCRIPTION,
        routes=app.routes,
    )

    components = openapi_schema.setdefault("components", {}).setdefault("schemas", {})
    error_schema = ErrorResponse.model_json_schema(ref_template="#/components/schemas/{model}")
    defs = error_schema.pop("$defs", {})
    for name, schema in defs.items():
        components[name] = schema
    components["ErrorResponse"] = error_schema

    # Remove FastAPI's default validation schemas
    components.pop("HTTPValidationError", None)
    components.pop("ValidationError", None)

    for path_item in openapi_schema.get("paths", {}).values():
        for operation in list(path_item.values()):
            if not isinstance(operation, dict):
                continue
            responses = operation.setdefault("responses", {})
            for status_code, response in list(responses.items()):
                content = response.get("content")
                if not content:
                    continue
                for content_type, media in list(content.items()):
                    schema = media.get("schema")
                    if not schema:
                        continue
                    ref = schema.get("$ref")
                    if ref and ref.endswith("HTTPValidationError"):
                        media["schema"] = {"$ref": "#/components/schemas/ErrorResponse"}
            if "422" in responses:
                responses["422"] = {
                    "description": "Validation Error",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                        }
                    },
                }

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


@app.on_event("startup")
async def startup_event():
    """Application startup event."""
    from app.core.logging import startup_log

    # Display startup banner
    log_startup_banner()

    # Database connection
    # Ensure platform types seeded (idempotent)
    try:
        ensure_platform_types_seed()
    except Exception:
        # best-effort; don't block startup
        pass

    # Ensure permission definitions seeded (idempotent)
    try:
        ensure_permissions_seed()
    except Exception:
        # best-effort; don't block startup
        pass


    startup_log("🗄️  Connecting to database...")


    # Start background sync monitor
    try:
        from app.services.platform_sync import start_sync_monitor
        start_sync_monitor()
    except Exception:
        # best-effort; don't block startup
        pass

    # Start periodic AIProvider sync task (best-effort)
    try:
        from app.tasks.sync_ai_providers import start_ai_provider_sync_task
        start_ai_provider_sync_task()
    except Exception:
        # best-effort; don't block startup
        pass

    # Start periodic ProjectAIConfig sync task (best-effort)
    try:
        from app.tasks.sync_project_ai_configs import start_project_ai_config_sync_task
        start_project_ai_config_sync_task()
    except Exception:
        # best-effort; don't block startup
        pass

    # Start periodic waiting queue processor task (best-effort)
    try:
        from app.tasks.process_waiting_queue import start_queue_processor
        start_queue_processor()
    except Exception:
        # best-effort; don't block startup
        pass

    # Start periodic session timeout check task (best-effort)
    try:
        from app.tasks.close_timeout_sessions import start_session_timeout_task
        await start_session_timeout_task()
    except Exception:
        # best-effort; don't block startup
        pass

    # Start periodic visitor online status sync task (best-effort)
    try:
        from app.tasks.sync_visitor_online_status import start_visitor_online_sync_task
        await start_visitor_online_sync_task()
    except Exception:
        # best-effort; don't block startup
        pass

    # Start periodic auto AI fallback task (best-effort)
    try:
        from app.tasks.auto_fallback_to_ai import start_auto_fallback_to_ai_task
        await start_auto_fallback_to_ai_task()
    except Exception:
        # best-effort; don't block startup
        pass

    # Start plugin socket server (best-effort)
    try:
        from app.tasks.plugin_socket_server import start_plugin_socket_server
        await start_plugin_socket_server()
    except Exception:
        # best-effort; don't block startup
        pass

    # Server ready
    startup_log("🌐 Server starting...")
    startup_log(f"   📍 Listening on: http://0.0.0.0:8000")
    startup_log(f"   📚 API Docs: http://localhost:8000/v1/docs")
    startup_log(f"   🏥 Health Check: http://localhost:8000/health")
    startup_log("")
    startup_log("🎉 TGO-Tech API Service is ready!")
    startup_log("═" * 64)


@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event: stop background tasks."""
    # Stop periodic AIProvider sync task (best-effort)
    try:
        from app.tasks.sync_ai_providers import stop_ai_provider_sync_task
        await stop_ai_provider_sync_task()
    except Exception:
        pass

    # Stop periodic ProjectAIConfig sync task (best-effort)
    try:
        from app.tasks.sync_project_ai_configs import stop_project_ai_config_sync_task
        await stop_project_ai_config_sync_task()
    except Exception:
        pass

    # Stop periodic waiting queue processor task (best-effort)
    try:
        from app.tasks.process_waiting_queue import stop_queue_processor
        await stop_queue_processor()
    except Exception:
        pass

    # Stop periodic session timeout check task (best-effort)
    try:
        from app.tasks.close_timeout_sessions import stop_session_timeout_task
        await stop_session_timeout_task()
    except Exception:
        pass

    # Stop periodic visitor online status sync task (best-effort)
    try:
        from app.tasks.sync_visitor_online_status import stop_visitor_online_sync_task
        await stop_visitor_online_sync_task()
    except Exception:
        pass

    # Stop periodic auto AI fallback task (best-effort)
    try:
        from app.tasks.auto_fallback_to_ai import stop_auto_fallback_to_ai_task
        await stop_auto_fallback_to_ai_task()
    except Exception:
        pass

    # Stop plugin socket server (best-effort)
    try:
        from app.tasks.plugin_socket_server import stop_plugin_socket_server
        await stop_plugin_socket_server()
    except Exception:
        pass


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {"message": "TGO-Tech API Service", "version": settings.PROJECT_VERSION}


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
