"""Visitor Assignment Rule endpoints."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.logging import get_logger
from app.core.security import get_current_active_user, require_permission
from app.models import Staff, VisitorAssignmentRule, AIProvider, DEFAULT_ASSIGNMENT_PROMPT
from app.schemas import (
    VisitorAssignmentRuleUpdate,
    VisitorAssignmentRuleResponse,
)

logger = get_logger("endpoints.visitor_assignment_rules")
router = APIRouter()


@router.get("", response_model=VisitorAssignmentRuleResponse)
async def get_visitor_assignment_rule(
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_permission("visitor_assignment_rules:read")),
) -> VisitorAssignmentRuleResponse:
    """
    Get visitor assignment rule for current project.

    Returns the assignment rule configuration for the current project.
    If no rule exists, returns a default configuration with llm_assignment_enabled=False.
    The effective_prompt field contains the actual prompt to use (custom or system default).
    Requires visitor_assignment_rules:read permission.
    """
    logger.info(f"User {current_user.username} getting visitor assignment rule")

    rule = db.query(VisitorAssignmentRule).filter(
        VisitorAssignmentRule.project_id == current_user.project_id
    ).first()

    if rule:
        return VisitorAssignmentRuleResponse(
            id=rule.id,
            project_id=rule.project_id,
            ai_provider_id=rule.ai_provider_id,
            model=rule.model,
            prompt=rule.prompt,
            effective_prompt=rule.effective_prompt,
            llm_assignment_enabled=rule.llm_assignment_enabled,
            timezone=rule.timezone,
            service_weekdays=rule.service_weekdays,
            service_start_time=rule.service_start_time,
            service_end_time=rule.service_end_time,
            max_concurrent_chats=rule.max_concurrent_chats,
            auto_close_hours=rule.auto_close_hours,
            created_at=rule.created_at,
            updated_at=rule.updated_at,
        )

    # Return default configuration if no rule exists
    # Use a placeholder UUID for the response (frontend should handle this)
    from uuid import uuid4
    now = datetime.utcnow()
    return VisitorAssignmentRuleResponse(
        id=uuid4(),  # Placeholder, will be replaced on first update
        project_id=current_user.project_id,
        ai_provider_id=None,
        model=None,
        prompt=None,
        effective_prompt=DEFAULT_ASSIGNMENT_PROMPT,
        llm_assignment_enabled=False,  # Default to disabled
        timezone=settings.ASSIGNMENT_RULE_DEFAULT_TIMEZONE,
        service_weekdays=settings.ASSIGNMENT_RULE_DEFAULT_WEEKDAYS,
        service_start_time=settings.ASSIGNMENT_RULE_DEFAULT_START_TIME,
        service_end_time=settings.ASSIGNMENT_RULE_DEFAULT_END_TIME,
        max_concurrent_chats=settings.ASSIGNMENT_RULE_DEFAULT_MAX_CONCURRENT_CHATS,
        auto_close_hours=settings.ASSIGNMENT_RULE_DEFAULT_AUTO_CLOSE_HOURS,
        created_at=now,
        updated_at=now,
    )


@router.put("", response_model=VisitorAssignmentRuleResponse)
async def update_visitor_assignment_rule(
    rule_data: VisitorAssignmentRuleUpdate,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_permission("visitor_assignment_rules:update")),
) -> VisitorAssignmentRuleResponse:
    """
    Update or create visitor assignment rule for current project.

    This endpoint performs an upsert operation:
    - If a rule exists for the project, it updates the existing rule
    - If no rule exists, it creates a new one

    Only provided fields will be updated (PATCH-like behavior).
    Requires visitor_assignment_rules:update permission.
    """
    logger.info(f"User {current_user.username} updating visitor assignment rule")

    # Validate ai_provider_id if provided
    if rule_data.ai_provider_id is not None:
        provider = db.query(AIProvider).filter(
            AIProvider.id == rule_data.ai_provider_id,
            AIProvider.project_id == current_user.project_id,
            AIProvider.deleted_at.is_(None),
        ).first()

        if not provider:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="AI provider not found or does not belong to this project"
            )

    # Try to find existing rule
    rule = db.query(VisitorAssignmentRule).filter(
        VisitorAssignmentRule.project_id == current_user.project_id
    ).first()

    if rule:
        # Update existing rule
        update_data = rule_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(rule, field, value)
        rule.updated_at = datetime.utcnow()
        logger.info(f"Updated visitor assignment rule {rule.id}")
    else:
        # Parse default weekdays from config if not provided
        default_weekdays = [
            int(d.strip()) 
            for d in settings.ASSIGNMENT_RULE_DEFAULT_WEEKDAYS.split(",") 
            if d.strip().isdigit()
        ]
        
        # Create new rule with config defaults
        rule = VisitorAssignmentRule(
            project_id=current_user.project_id,
            ai_provider_id=rule_data.ai_provider_id,
            model=rule_data.model,
            prompt=rule_data.prompt,
            llm_assignment_enabled=rule_data.llm_assignment_enabled if rule_data.llm_assignment_enabled is not None else True,
            timezone=rule_data.timezone if rule_data.timezone is not None else settings.ASSIGNMENT_RULE_DEFAULT_TIMEZONE,
            service_weekdays=rule_data.service_weekdays if rule_data.service_weekdays is not None else default_weekdays,
            service_start_time=rule_data.service_start_time if rule_data.service_start_time is not None else settings.ASSIGNMENT_RULE_DEFAULT_START_TIME,
            service_end_time=rule_data.service_end_time if rule_data.service_end_time is not None else settings.ASSIGNMENT_RULE_DEFAULT_END_TIME,
            max_concurrent_chats=rule_data.max_concurrent_chats if rule_data.max_concurrent_chats is not None else settings.ASSIGNMENT_RULE_DEFAULT_MAX_CONCURRENT_CHATS,
            auto_close_hours=rule_data.auto_close_hours if rule_data.auto_close_hours is not None else settings.ASSIGNMENT_RULE_DEFAULT_AUTO_CLOSE_HOURS,
        )
        db.add(rule)
        logger.info(f"Created new visitor assignment rule for project {current_user.project_id}")

    db.commit()
    db.refresh(rule)

    return VisitorAssignmentRuleResponse(
        id=rule.id,
        project_id=rule.project_id,
        ai_provider_id=rule.ai_provider_id,
        model=rule.model,
        prompt=rule.prompt,
        effective_prompt=rule.effective_prompt,
        llm_assignment_enabled=rule.llm_assignment_enabled,
        timezone=rule.timezone,
        service_weekdays=rule.service_weekdays,
        service_start_time=rule.service_start_time,
        service_end_time=rule.service_end_time,
        max_concurrent_chats=rule.max_concurrent_chats,
        auto_close_hours=rule.auto_close_hours,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
    )


@router.get("/default-prompt", response_model=dict)
async def get_default_prompt(
    current_user: Staff = Depends(require_permission("visitor_assignment_rules:read")),
) -> dict:
    """
    Get the system default prompt for visitor assignment.

    This endpoint returns the default prompt that will be used when
    no custom prompt is configured for the project.
    Requires visitor_assignment_rules:read permission.
    """
    return {
        "default_prompt": DEFAULT_ASSIGNMENT_PROMPT
    }
