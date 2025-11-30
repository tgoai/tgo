"""Unified documentation access for multiple microservices.

Provides access to OpenAPI/Swagger documentation for:
- /docs/api - Current API service (tgo-api)
- /docs/ai - AI service
- /docs/rag - RAG service
- /docs/platform - Platform service
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("docs")

router = APIRouter(prefix="/docs", tags=["Documentation"])

# Service configuration mapping
SERVICES = {
    "api": {
        "name": "TGO API Service",
        "url": None,  # Local service, use internal openapi
        "openapi_path": f"{settings.API_V1_STR}/openapi.json",
    },
    "ai": {
        "name": "AI Service",
        "url": settings.AI_SERVICE_URL,
        "openapi_path": "/openapi.json",
    },
    "rag": {
        "name": "RAG Service",
        "url": settings.RAG_SERVICE_URL,
        "openapi_path": "/openapi.json",
    },
    "platform": {
        "name": "Platform Service",
        "url": settings.PLATFORM_SERVICE_URL,
        "openapi_path": "/openapi.json",
    },
}


def _swagger_ui_html(title: str, openapi_url: str) -> str:
    """Generate Swagger UI HTML page."""
    return f"""
<!DOCTYPE html>
<html>
<head>
    <title>{title} - Swagger UI</title>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="stylesheet" type="text/css" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css">
</head>
<body>
    <div id="swagger-ui"></div>
    <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
    <script>
        SwaggerUIBundle({{
            url: "{openapi_url}",
            dom_id: '#swagger-ui',
            presets: [SwaggerUIBundle.presets.apis, SwaggerUIBundle.SwaggerUIStandalonePreset],
            layout: "StandaloneLayout"
        }});
    </script>
</body>
</html>
"""


def _error_html(title: str, message: str) -> str:
    """Generate error page HTML."""
    return f"""
<!DOCTYPE html>
<html>
<head>
    <title>{title} - Error</title>
    <style>
        body {{ font-family: Arial, sans-serif; padding: 40px; background: #f5f5f5; }}
        .error {{ background: white; padding: 30px; border-radius: 8px; max-width: 600px; margin: 0 auto; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        h1 {{ color: #e74c3c; }}
        p {{ color: #666; }}
    </style>
</head>
<body>
    <div class="error">
        <h1>⚠️ {title}</h1>
        <p>{message}</p>
    </div>
</body>
</html>
"""


@router.get("", response_class=HTMLResponse, summary="Documentation Index")
async def docs_index():
    """List all available service documentation."""
    links = "".join(
        f'<li><a href="/v1/docs/{key}">{svc["name"]}</a></li>'
        for key, svc in SERVICES.items()
    )
    return f"""
<!DOCTYPE html>
<html>
<head><title>API Documentation</title>
<style>
    body {{ font-family: Arial, sans-serif; padding: 40px; background: #f5f5f5; }}
    .container {{ background: white; padding: 30px; border-radius: 8px; max-width: 600px; margin: 0 auto; }}
    h1 {{ color: #333; }} ul {{ line-height: 2; }} a {{ color: #3498db; }}
</style>
</head>
<body><div class="container"><h1>📚 API Documentation</h1><ul>{links}</ul></div></body>
</html>
"""


@router.get("/api", response_class=HTMLResponse, summary="TGO API Documentation")
async def docs_api():
    """Swagger UI for the current TGO API service."""
    return HTMLResponse(_swagger_ui_html("TGO API Service", f"{settings.API_V1_STR}/openapi.json"))


@router.get("/{service}/openapi.json", summary="Proxy OpenAPI JSON")
async def proxy_openapi_json(service: str):
    """Proxy OpenAPI JSON from remote service."""
    if service not in SERVICES or service == "api":
        raise HTTPException(status_code=404, detail="Service not found")
    
    svc = SERVICES[service]
    url = f"{svc['url'].rstrip('/')}{svc['openapi_path']}"
    
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.warning(f"Failed to fetch OpenAPI from {service}: {e}")
        raise HTTPException(status_code=503, detail=f"Service unavailable: {svc['name']}")


@router.get("/{service}", response_class=HTMLResponse, summary="Service Documentation")
async def docs_service(service: str):
    """Swagger UI for a remote microservice."""
    if service not in SERVICES:
        return HTMLResponse(_error_html("Not Found", f"Service '{service}' not found."), status_code=404)
    
    if service == "api":
        return HTMLResponse(_swagger_ui_html("TGO API Service", f"{settings.API_V1_STR}/openapi.json"))
    
    svc = SERVICES[service]
    # Use proxied openapi.json to avoid CORS issues
    openapi_url = f"/v1/docs/{service}/openapi.json"
    return HTMLResponse(_swagger_ui_html(svc["name"], openapi_url))

