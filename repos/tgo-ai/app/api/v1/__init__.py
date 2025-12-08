"""API v1 routes."""

from fastapi import APIRouter

from app.api.v1 import agents, chat, teams, llm_providers, project_ai_configs, tools

api_router = APIRouter(prefix="/api/v1")

# Include route modules
api_router.include_router(teams.router, prefix="/teams", tags=["Teams"])
api_router.include_router(agents.router, prefix="/agents", tags=["Agents"])
api_router.include_router(tools.router)  # tools router carries its own prefix/tags
api_router.include_router(chat.router, prefix="/chat", tags=["Chat"])

api_router.include_router(llm_providers.router, prefix="/llm-providers", tags=["LLM Providers"])
api_router.include_router(project_ai_configs.router, prefix="/project-ai-configs", tags=["Project AI Configs"])