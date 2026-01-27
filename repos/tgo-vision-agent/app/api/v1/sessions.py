"""AgentBay session management API endpoints with dual-model support."""

from __future__ import annotations

import base64
import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.services.session_service import SessionService
from app.domain.entities import SessionStatus

router = APIRouter()
logger = logging.getLogger(__name__)


class CreateSessionRequest(BaseModel):
    """Request body for creating a new AgentBay session."""

    platform_id: UUID = Field(..., description="Platform ID from tgo-api")
    app_type: str = Field(..., description="Application type: wechat, douyin, etc.")
    environment_type: str = Field(
        default="mobile",
        description="Environment type: mobile (cloud phone) or desktop (cloud desktop)",
    )
    image_id: Optional[str] = Field(
        default=None,
        description="AgentBay image ID",
    )
    agentbay_api_key: Optional[str] = Field(
        default=None,
        description="AgentBay API key",
    )
    # Vision model configuration (required)
    vision_provider_id: str = Field(
        ...,
        description="Vision model provider ID for screen analysis",
    )
    vision_model_id: str = Field(
        ...,
        description="Vision model ID for screen analysis (e.g., qwen-vl-plus)",
    )
    # Reasoning model configuration (required)
    reasoning_provider_id: str = Field(
        ...,
        description="Reasoning model provider ID for decision making",
    )
    reasoning_model_id: str = Field(
        ...,
        description="Reasoning model ID for decision making (e.g., qwen-plus)",
    )


class SessionResponse(BaseModel):
    """Response body for session operations."""

    id: UUID
    platform_id: UUID
    app_type: str
    agentbay_session_id: str
    environment_type: str
    status: str
    app_login_status: str


class SessionStatusResponse(BaseModel):
    """Response body for session status."""

    id: UUID
    status: str
    app_login_status: str
    last_heartbeat: Optional[str] = None
    qr_code_base64: Optional[str] = None


@router.post("/sessions", response_model=SessionResponse)
async def create_session(
    request: CreateSessionRequest,
    db: AsyncSession = Depends(get_db),
) -> SessionResponse:
    """Create a new AgentBay session with dual-model configuration.

    This will:
    1. Create a new AgentBay cloud phone/desktop session
    2. Initialize reasoning and vision models
    3. Start the agent loop for automation
    """
    service = SessionService(db)

    try:
        session = await service.create_session(
            platform_id=request.platform_id,
            app_type=request.app_type,
            environment_type=request.environment_type,
            image_id=request.image_id,
            agentbay_api_key=request.agentbay_api_key,
            vision_provider_id=request.vision_provider_id,
            vision_model_id=request.vision_model_id,
            reasoning_provider_id=request.reasoning_provider_id,
            reasoning_model_id=request.reasoning_model_id,
        )

        # Start workers with dual model configuration
        from app.workers.worker_manager import get_worker_manager
        from app.core.config import settings

        worker_manager = get_worker_manager()
        success = await worker_manager.start_workers_for_session(
            platform_id=session.platform_id,
            app_type=session.app_type,
            agentbay_session_id=session.agentbay_session_id,
            environment_type=session.environment_type,
            api_key=request.agentbay_api_key,
            vision_provider_id=request.vision_provider_id,
            vision_model_id=request.vision_model_id,
            reasoning_provider_id=request.reasoning_provider_id,
            reasoning_model_id=request.reasoning_model_id,
            poll_interval=settings.default_poll_interval_seconds,
        )

        if not success:
            logger.warning(f"Failed to start workers for new session {session.id}")

        return SessionResponse(
            id=session.id,
            platform_id=session.platform_id,
            app_type=session.app_type,
            agentbay_session_id=session.agentbay_session_id,
            environment_type=session.environment_type,
            status=session.status,
            app_login_status=session.app_login_status,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create session: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create session: {e}")


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> SessionResponse:
    """Get session details by ID."""
    service = SessionService(db)
    session = await service.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return SessionResponse(
        id=session.id,
        platform_id=session.platform_id,
        app_type=session.app_type,
        agentbay_session_id=session.agentbay_session_id,
        environment_type=session.environment_type,
        status=session.status,
        app_login_status=session.app_login_status,
    )


@router.get("/sessions/platform/{platform_id}", response_model=SessionResponse)
async def get_session_by_platform(
    platform_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> SessionResponse:
    """Get session details by platform ID."""
    service = SessionService(db)
    session = await service.get_session_by_platform(platform_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found for this platform")

    return SessionResponse(
        id=session.id,
        platform_id=session.platform_id,
        app_type=session.app_type,
        agentbay_session_id=session.agentbay_session_id,
        environment_type=session.environment_type,
        status=session.status,
        app_login_status=session.app_login_status,
    )


@router.get("/sessions/{session_id}/status", response_model=SessionStatusResponse)
async def get_session_status(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> SessionStatusResponse:
    """Get current session status."""
    service = SessionService(db)
    session = await service.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return SessionStatusResponse(
        id=session.id,
        status=session.status,
        app_login_status=session.app_login_status,
        last_heartbeat=session.last_heartbeat.isoformat() if session.last_heartbeat else None,
    )


@router.post("/sessions/{session_id}/start")
async def start_session(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Start/resume message polling for a session."""
    from app.workers.worker_manager import get_worker_manager
    from app.core.config import settings
    from app.core.encryption import decrypt_api_key

    service = SessionService(db)
    session = await service.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.status == SessionStatus.TERMINATED.value:
        raise HTTPException(status_code=400, detail="Session is terminated")

    await service.update_session_status(session_id, status=SessionStatus.ACTIVE.value)

    worker_manager = get_worker_manager()
    config = session.config or {}

    encrypted_key = config.get("agentbay_api_key")
    api_key = decrypt_api_key(encrypted_key) if encrypted_key else None

    success = await worker_manager.start_workers_for_session(
        platform_id=session.platform_id,
        app_type=session.app_type,
        agentbay_session_id=session.agentbay_session_id,
        environment_type=session.environment_type,
        api_key=api_key,
        vision_provider_id=config.get("vision_provider_id"),
        vision_model_id=config.get("vision_model_id"),
        reasoning_provider_id=config.get("reasoning_provider_id"),
        reasoning_model_id=config.get("reasoning_model_id"),
        poll_interval=settings.default_poll_interval_seconds,
    )

    return {
        "success": True,
        "message": f"Session {session_id} started",
        "status": SessionStatus.ACTIVE.value,
        "workers_started": success,
    }


@router.post("/sessions/{session_id}/stop")
async def stop_session(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Stop message polling for a session (keeps session alive)."""
    from app.workers.worker_manager import get_worker_manager

    service = SessionService(db)
    session = await service.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    worker_manager = get_worker_manager()
    await worker_manager.stop_workers_for_session(session.platform_id)

    await service.update_session_status(session_id, status=SessionStatus.PAUSED.value)

    return {
        "success": True,
        "message": f"Session {session_id} stopped",
        "status": SessionStatus.PAUSED.value,
    }


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Terminate and delete a session."""
    from app.workers.worker_manager import get_worker_manager

    service = SessionService(db)
    session = await service.get_session(session_id)

    if session:
        worker_manager = get_worker_manager()
        await worker_manager.stop_workers_for_session(session.platform_id)

    success = await service.delete_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "success": True,
        "message": f"Session {session_id} deleted",
    }


@router.post("/sessions/{session_id}/run-task")
async def run_task(
    session_id: UUID,
    goal: str,
    max_steps: int = 20,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Run a custom task on the session using AgentLoop.

    This endpoint allows running arbitrary automation tasks
    specified by a natural language goal.
    """
    from app.workers.worker_manager import get_worker_manager

    service = SessionService(db)
    session = await service.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    worker_manager = get_worker_manager()
    agent = worker_manager.get_agent(session.platform_id)

    if not agent:
        raise HTTPException(
            status_code=400,
            detail="No active agent for this session. Start the session first."
        )

    try:
        result = await agent.run_single_task(
            goal=goal,
            app_type=session.app_type,
            max_steps=max_steps,
        )

        return {
            "success": result.success,
            "message": result.message,
            "steps_taken": result.steps_taken,
            "history": [
                {
                    "action": str(step.action),
                    "result": step.result.success,
                    "error": step.result.error,
                }
                for step in result.history[-5:]  # Last 5 steps
            ],
        }

    except Exception as e:
        logger.error(f"Task execution failed: {e}")
        raise HTTPException(status_code=500, detail=f"Task execution failed: {e}")
