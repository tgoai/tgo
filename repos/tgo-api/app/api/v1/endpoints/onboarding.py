"""Onboarding progress endpoints."""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.logging import get_logger
from app.core.security import get_current_active_user
from app.models import Project, Staff, ProjectOnboardingProgress
from app.schemas.onboarding import (
    ONBOARDING_STEPS,
    OnboardingProgressResponse,
    OnboardingStepStatus,
    SkipOnboardingRequest,
)
from app.services.onboarding_service import check_all_steps

logger = get_logger("endpoints.onboarding")
router = APIRouter()


def _get_or_create_progress(
    db: Session, project_id: UUID
) -> ProjectOnboardingProgress:
    """Get or create onboarding progress record for a project."""
    progress = (
        db.query(ProjectOnboardingProgress)
        .filter(
            ProjectOnboardingProgress.project_id == project_id,
            ProjectOnboardingProgress.deleted_at.is_(None),
        )
        .first()
    )
    if not progress:
        progress = ProjectOnboardingProgress(project_id=project_id)
        db.add(progress)
        db.commit()
        db.refresh(progress)
    return progress


@router.get(
    "",
    response_model=OnboardingProgressResponse,
    summary="Get onboarding progress",
    description="""
    Get the current onboarding progress for the authenticated user's project.

    Automatically detects completion status for each step:
    - Step 1: AI Provider configured
    - Step 2: Default models set
    - Step 3: RAG Collection created
    - Step 4: Agent with knowledge base created
    - Step 5: First chat started

    If the record does not exist, creates an initial empty record.
    """,
)
async def get_onboarding_progress(
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user),
) -> OnboardingProgressResponse:
    """Get onboarding progress for the current user's project."""
    project_id = current_user.project_id

    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.deleted_at.is_(None))
        .first()
    )
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )

    # Get or create progress record
    progress = _get_or_create_progress(db, project_id)

    # If already marked as completed (skipped), return current state without re-checking
    if progress.is_completed:
        step_statuses = [
            progress.step_1_completed,
            progress.step_2_completed,
            progress.step_3_completed,
            progress.step_4_completed,
            progress.step_5_completed,  # Read from database (may be skipped by user)
        ]
        # Only count action steps (1-4) for progress
        completed_count = sum(1 for s in step_statuses[:4] if s)
        current_step = 5
        for i in range(4):  # Only check steps 1-4
            if not step_statuses[i]:
                current_step = i + 1
                break
    else:
        # Check all steps and update progress
        step_statuses, current_step, _ = await check_all_steps(db, project_id)

        # Update progress record (only action steps 1-4)
        progress.step_1_completed = step_statuses[0]
        progress.step_2_completed = step_statuses[1]
        progress.step_3_completed = step_statuses[2]
        progress.step_4_completed = step_statuses[3]
        # Step 5 is 'notify' type - read from database (may be skipped by user)
        step_statuses[4] = progress.step_5_completed

        # Done when steps 1-4 pass; step 5 is notify-only (not auto-detected).
        if all(step_statuses[:4]):
            progress.is_completed = True
            progress.completed_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(progress)
        completed_count = sum(1 for s in step_statuses[:4] if s)

    # Build step status list
    steps = []
    for i, step_def in enumerate(ONBOARDING_STEPS):
        steps.append(
            OnboardingStepStatus(
                step_number=step_def["step_number"],
                step_name=step_def["step_name"],
                is_completed=step_statuses[i] if i < len(step_statuses) else False,
                description=step_def["description"],
                description_zh=step_def["description_zh"],
                route=step_def["route"],
                step_type=step_def["step_type"],
                title=step_def["title"] if "title" in step_def else None,
                title_zh=step_def["title_zh"] if "title_zh" in step_def else None,
            )
        )

    # Progress percentage based on steps 1-4 (action steps only)
    progress_percentage = int((completed_count / 4) * 100)

    return OnboardingProgressResponse(
        id=progress.id,
        project_id=progress.project_id,
        steps=steps,
        current_step=current_step,
        progress_percentage=progress_percentage,
        is_completed=progress.is_completed,
        completed_at=progress.completed_at,
        created_at=progress.created_at,
        updated_at=progress.updated_at,
    )


@router.post(
    "/skip",
    response_model=OnboardingProgressResponse,
    summary="Skip onboarding step(s)",
    description="""
    Skip onboarding step(s) for the authenticated user's project.

    - If `step_number` is provided (1-5), only that specific step is skipped.
    - If `step_number` is not provided, the entire onboarding is skipped (all steps marked as completed).

    This allows users to dismiss individual steps or the entire onboarding guide.
    """,
)
async def skip_onboarding(
    request: SkipOnboardingRequest = None,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user),
) -> OnboardingProgressResponse:
    """Skip onboarding step(s) for the current user's project."""
    project_id = current_user.project_id

    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.deleted_at.is_(None))
        .first()
    )
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )

    progress = _get_or_create_progress(db, project_id)

    # Get step_number from request body (if provided)
    step_number = request.step_number if request else None

    if step_number is not None:
        # Skip specific step
        step_attr = f"step_{step_number}_completed"
        setattr(progress, step_attr, True)

        logger.info(
            "Onboarding step skipped",
            extra={
                "project_id": str(project_id),
                "user_id": str(current_user.id),
                "step_number": step_number,
            },
        )

        # Check if all action steps (1-4) are now completed
        if all([
            progress.step_1_completed,
            progress.step_2_completed,
            progress.step_3_completed,
            progress.step_4_completed,
        ]):
            progress.is_completed = True
            progress.completed_at = datetime.now(timezone.utc)
    else:
        # Skip all steps
        progress.step_1_completed = True
        progress.step_2_completed = True
        progress.step_3_completed = True
        progress.step_4_completed = True
        progress.step_5_completed = True
        progress.is_completed = True
        progress.completed_at = datetime.now(timezone.utc)

        logger.info(
            "Onboarding skipped (all steps)",
            extra={"project_id": str(project_id), "user_id": str(current_user.id)},
        )

    db.commit()
    db.refresh(progress)

    # Return updated progress
    return await get_onboarding_progress(db, current_user)


@router.post(
    "/reset",
    response_model=OnboardingProgressResponse,
    summary="Reset onboarding",
    description="""
    Reset the onboarding progress for the authenticated user's project.

    Clears all step completion statuses and allows the user to restart
    the onboarding process. Useful for testing or when users want to
    review the onboarding steps again.
    """,
)
async def reset_onboarding(
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user),
) -> OnboardingProgressResponse:
    """Reset onboarding progress for the current user's project."""
    project_id = current_user.project_id

    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.deleted_at.is_(None))
        .first()
    )
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )

    progress = _get_or_create_progress(db, project_id)
    progress.step_1_completed = False
    progress.step_2_completed = False
    progress.step_3_completed = False
    progress.step_4_completed = False
    progress.step_5_completed = False
    progress.is_completed = False
    progress.completed_at = None
    db.commit()
    db.refresh(progress)

    logger.info(
        "Onboarding reset",
        extra={"project_id": str(project_id), "user_id": str(current_user.id)},
    )

    # Return updated progress (will re-check actual step statuses)
    return await get_onboarding_progress(db, current_user)
