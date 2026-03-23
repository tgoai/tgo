"""Onboarding progress service for checking step completion status."""

from typing import List, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models import AIProvider, ProjectAIConfig
from app.services.ai_client import AIServiceClient
from app.services.rag_client import RAGServiceClient

logger = get_logger("services.onboarding")


async def check_step_1_ai_provider(db: Session, project_id: UUID) -> bool:
    """Check if project has at least one active AI provider."""
    count = (
        db.query(AIProvider.id)
        .filter(
            AIProvider.project_id == project_id,
            AIProvider.is_active == True,  # noqa: E712
            AIProvider.deleted_at.is_(None),
        )
        .count()
    )
    return count > 0


async def check_step_2_default_models(db: Session, project_id: UUID) -> bool:
    """Check if project has configured default chat and embedding models."""
    cfg = (
        db.query(ProjectAIConfig)
        .filter(
            ProjectAIConfig.project_id == project_id,
            ProjectAIConfig.deleted_at.is_(None),
        )
        .first()
    )
    if not cfg:
        return False

    # All four fields must be set
    if not all([
        cfg.default_chat_provider_id,
        cfg.default_chat_model,
        cfg.default_embedding_provider_id,
        cfg.default_embedding_model,
    ]):
        return False

    # Each referenced provider must exist and be active. Chat and embedding
    # may share one provider — validate distinct IDs only.
    provider_ids = [
        cfg.default_chat_provider_id,
        cfg.default_embedding_provider_id,
    ]
    unique_provider_ids = list(
        {pid for pid in provider_ids if pid is not None}
    )
    valid_count = (
        db.query(AIProvider.id)
        .filter(
            AIProvider.id.in_(unique_provider_ids),
            AIProvider.project_id == project_id,
            AIProvider.is_active == True,  # noqa: E712
            AIProvider.deleted_at.is_(None),
        )
        .count()
    )
    return valid_count == len(unique_provider_ids)


async def check_step_3_rag_collection(project_id: UUID) -> bool:
    """Check if project has at least one RAG collection."""
    try:
        rag_client = RAGServiceClient()
        result = await rag_client.list_collections(
            project_id=str(project_id),
            limit=1,
            offset=0,
        )
        total = result.get("pagination", {}).get("total", 0)
        return total > 0
    except Exception as e:
        logger.warning(
            "Failed to check RAG collections for onboarding",
            extra={"project_id": str(project_id), "error": str(e)},
        )
        return False


async def check_step_4_agent_created(project_id: UUID) -> bool:
    """Check if project has at least one agent."""
    try:
        ai_client = AIServiceClient()
        result = await ai_client.list_agents(
            project_id=str(project_id),
            limit=1,
            offset=0,
        )
        agents = result.get("data", [])
        return len(agents) > 0
    except Exception as e:
        logger.warning(
            "Failed to check agents for onboarding",
            extra={"project_id": str(project_id), "error": str(e)},
        )
        return False


async def check_all_steps(
    db: Session, project_id: UUID
) -> Tuple[List[bool], int, int]:
    """Check all onboarding steps and return status.

    Note: Step 5 is a 'notify' type step, always returns False as it's
    just a reminder to the user, not an action to be completed.

    Returns:
        Tuple of (step_statuses, current_step, progress_percentage)
    """
    step_1 = await check_step_1_ai_provider(db, project_id)
    step_2 = await check_step_2_default_models(db, project_id)
    step_3 = await check_step_3_rag_collection(project_id)
    step_4 = await check_step_4_agent_created(project_id)
    # Step 5 is 'notify' type, no actual completion check needed
    step_5 = False

    steps = [step_1, step_2, step_3, step_4, step_5]

    # First incomplete action step, or 5 when steps 1-4 are done.
    # Step 5 is UI-only; progress uses steps 1-4 only.
    current_step = 5
    for i in range(4):  # Only check steps 1-4
        if not steps[i]:
            current_step = i + 1
            break

    # Calculate progress percentage (based on steps 1-4 only)
    completed_count = sum(1 for s in steps[:4] if s)
    progress_percentage = int((completed_count / 4) * 100)

    return steps, current_step, progress_percentage
