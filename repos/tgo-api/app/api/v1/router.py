"""Main API v1 router."""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    ai_agents,
    ai_models,
    ai_teams,
    ai_tools,
    ai_workflows,
    conversations,
    docs,
    email,
    onboarding,
    platforms,
    plugins,
    projects,
    wukongim,
    wukongim_webhook,
    rag_collections,
    rag_files,
    rag_qa_pairs,
    rag_websites,
    sessions,
    staff,
    tags,
    visitors,
    visitor_assignment_rules,
    visitor_waiting_queue,
    chat,
    channels,
    search,
    ai_providers,
    ai_runs,
    setup,
    system,
    utils,
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

# Onboarding endpoints (JWT auth, project_id from current_user)
api_router.include_router(
    onboarding.router,
    prefix="/onboarding",
    tags=["Onboarding"]
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
    visitor_assignment_rules.router,
    prefix="/visitor-assignment-rules",
    tags=["Visitor Assignment Rules"]
)

api_router.include_router(
    visitor_waiting_queue.router,
    prefix="/visitor-waiting-queue",
    tags=["Visitor Waiting Queue"]
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

api_router.include_router(
    rag_websites.router,
    prefix="/rag/websites",
    tags=["RAG Websites"]
)

api_router.include_router(
    rag_qa_pairs.router,
    prefix="/rag",
    tags=["RAG QA Pairs"]
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

# AI Workflows endpoints
api_router.include_router(
    ai_workflows.router,
    prefix="/ai/workflows",
    tags=["AI Workflows"]
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
    conversations.router,
    prefix="/conversations",
    tags=["Conversations"],
)

api_router.include_router(
    sessions.router,
    prefix="/sessions",
    tags=["Sessions"],
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

# Unified documentation endpoints
api_router.include_router(
    docs.router,
    tags=["Documentation"],
)

# Utility endpoints
api_router.include_router(
    utils.router,
    prefix="/utils",
    tags=["Utils"],
)

# Plugin endpoints
api_router.include_router(
    plugins.router,
    prefix="/plugins",
    tags=["Plugins"],
)
