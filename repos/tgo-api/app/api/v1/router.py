"""Main API v1 router."""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    ai_agents,
    ai_models,
    ai_teams,
    ai_tools,
    assignments,
    diagnostics,
    email,
    platforms,
    projects,
    wukongim,
    wukongim_webhook,
    rag_collections,
    rag_files,
    staff,
    tags,
    visitors,
    chat,
    channels,
    search,
    ai_providers,
    ai_runs,
    setup,
    system,
)

api_router = APIRouter()

# Setup endpoints (no authentication required)
api_router.include_router(
    setup.router,
    prefix="/setup",
    tags=["Setup"]
)

# Include all endpoint routers
api_router.include_router(
    projects.router,
    prefix="/projects",
    tags=["Projects"]
)

api_router.include_router(
    staff.router,
    prefix="/staff",
    tags=["Staff"]
)

api_router.include_router(
    visitors.router,
    prefix="/visitors",
    tags=["Visitors"]
)

api_router.include_router(
    assignments.router,
    prefix="/assignments",
    tags=["Assignments"]
)

api_router.include_router(
    tags.router,
    prefix="/tags",
    tags=["Tags"]
)

api_router.include_router(
    platforms.router,
    prefix="/platforms",
    tags=["Platforms"]
)

api_router.include_router(
    ai_providers.router,
    prefix="/ai/providers",
    tags=["AI Providers"]
)

# RAG Service Proxy Endpoints
api_router.include_router(
    rag_collections.router,
    prefix="/rag/collections",
    tags=["RAG Collections"]
)

api_router.include_router(
    rag_files.router,
    prefix="/rag/files",
    tags=["RAG Files"]
)

# AI Service Proxy Endpoints
api_router.include_router(
    ai_models.router,
    prefix="/ai/models",
    tags=["AI Models"]
)

api_router.include_router(
    ai_teams.router,
    prefix="/ai/teams",
    tags=["AI Teams"]
)

api_router.include_router(
    ai_agents.router,
    prefix="/ai/agents",
    tags=["AI Agents"]
)

# AI Runs helper endpoints
api_router.include_router(
    ai_runs.router,
    prefix="/ai/runs",
    tags=["AI Runs"]
)

# AI Tools endpoints
api_router.include_router(
    ai_tools.router,
    prefix="/ai/tools",
    tags=["AI Tools"]
)


# WuKongIM Public Endpoints
api_router.include_router(
    wukongim.router,
    prefix="/wukongim",
    tags=["WuKongIM"]
)


api_router.include_router(
    wukongim_webhook.router
)

# Diagnostic endpoints (for debugging)
api_router.include_router(
    diagnostics.router,
    prefix="/diagnostics",
    tags=["Diagnostics"]
)

# Email endpoints
api_router.include_router(
    email.router,
    prefix="/email",
    tags=["Email"]
)

api_router.include_router(
    chat.router,
    prefix="/chat",
    tags=["Chat"],
)

api_router.include_router(
    channels.router,
    prefix="/channels",
    tags=["Channels"],
)

api_router.include_router(
    search.router,
    prefix="/search",
    tags=["Search"],
)

# System information endpoints
api_router.include_router(
    system.router,
    prefix="/system",
    tags=["System"],
)
