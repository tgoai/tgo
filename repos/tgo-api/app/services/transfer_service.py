"""Transfer to human service for visitor assignment."""

import json
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import List, Optional
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.models import (
    Visitor,
    VisitorServiceStatus,
    UNASSIGNED_STATUSES,
    VisitorSession,
    VisitorAssignmentHistory,
    VisitorAssignmentRule,
    VisitorWaitingQueue,
    WaitingStatus,
    QueueSource,
    AssignmentSource,
    SessionStatus,
    Staff,
    StaffRole,
    ChannelMember,
)
from app.services.wukongim_client import wukongim_client
from app.utils.encoding import build_visitor_channel_id, build_project_staff_channel_id
from app.utils.const import CHANNEL_TYPE_CUSTOMER_SERVICE, CHANNEL_TYPE_PROJECT_STAFF, MEMBER_TYPE_STAFF

logger = get_logger("services.transfer")


@dataclass
class TransferResult:
    """Result of transfer to human operation."""
    
    success: bool
    session: Optional[VisitorSession]
    assignment_history: Optional[VisitorAssignmentHistory]
    assigned_staff_id: Optional[UUID]
    candidate_staff_ids: Optional[List[UUID]]
    waiting_queue: Optional[VisitorWaitingQueue]
    queue_position: Optional[int]
    message: str


@dataclass
class StaffCandidate:
    """Staff candidate for assignment."""
    
    id: UUID
    name: Optional[str]
    nickname: Optional[str]
    description: Optional[str]
    status: str
    current_chat_count: int = 0


@dataclass
class StaffAssignmentResult:
    """Result of staff assignment operation."""
    
    assigned_staff_id: Optional[UUID]
    candidate_staff_ids: List[UUID]
    llm_response: Optional[str] = None
    llm_reasoning: Optional[str] = None
    candidate_scores: Optional[dict] = None
    model_used: Optional[str] = None
    prompt_used: Optional[str] = None


async def transfer_to_staff(
    db: Session,
    visitor_id: UUID,
    project_id: UUID,
    source: AssignmentSource = AssignmentSource.MANUAL,
    visitor_message: Optional[str] = None,
    assigned_by_staff_id: Optional[UUID] = None,
    target_staff_id: Optional[UUID] = None,
    session_id: Optional[UUID] = None,
    platform_id: Optional[UUID] = None,
    notes: Optional[str] = None,
    skip_queue_status_check: bool = False,
    auto_commit: bool = True,
    ai_disabled: Optional[bool] = None,
    add_to_queue_if_no_staff: bool = True,
    send_notification: bool = True,
) -> TransferResult:
    """
    Transfer a visitor to staff service.
    
    Assignment logic:
    1. If target_staff_id specified, assign directly
    2. Otherwise, get available staff candidates based on rules
    3. If candidates > 1 and LLM enabled, use LLM to select
    4. If candidates > 1 and LLM disabled, use load balancing
    5. If candidates = 1, assign directly
    6. If candidates = 0 and add_to_queue_if_no_staff=True, add to waiting queue
    
    Args:
        db: Database session
        visitor_id: ID of the visitor to transfer
        project_id: ID of the project
        source: Source of the transfer (MANUAL, LLM, RULE, TRANSFER)
        visitor_message: Message that triggered the transfer
        assigned_by_staff_id: Staff who initiated the transfer (for manual transfers)
        target_staff_id: Specific staff to assign (optional)
        session_id: Existing session ID (optional)
        platform_id: Platform ID for new sessions
        notes: Additional notes
        skip_queue_status_check: Skip visitor status check (for queue processing)
        auto_commit: Whether to auto-commit changes (default True)
        ai_disabled: Whether to disable AI responses (None=keep current, True=disable, False=enable)
        add_to_queue_if_no_staff: Whether to add to waiting queue if no staff available (default True)
        send_notification: Whether to send staff assigned system message (default True)
        
    Returns:
        TransferResult with success status and related objects
    """
    llm_response = None
    llm_reasoning = None
    candidate_staff_ids: List[UUID] = []
    candidate_scores: Optional[dict] = None
    model_used: Optional[str] = None
    prompt_used: Optional[str] = None
    waiting_queue_entry: Optional[VisitorWaitingQueue] = None
    queue_position: Optional[int] = None
    no_staff_reason: Optional[str] = None
    
    try:
        # 1. Validate visitor exists
        visitor = db.query(Visitor).filter(
            Visitor.id == visitor_id,
            Visitor.project_id == project_id,
            Visitor.deleted_at.is_(None),
        ).first()
        
        if not visitor:
            return TransferResult(
                success=False,
                session=None,
                assignment_history=None,
                assigned_staff_id=None,
                candidate_staff_ids=None,
                waiting_queue=None,
                queue_position=None,
                message="Visitor not found",
            )
        
        # 1.5. Check if visitor can enter queue (only for non-direct assignments)
        # Skip this check if:
        # - target_staff_id is specified (direct assignment)
        # - skip_queue_status_check is True (processing from queue)
        if not target_staff_id and not skip_queue_status_check and not visitor.is_unassigned:
            logger.info(
                f"Visitor {visitor_id} cannot enter queue, current status: {visitor.service_status}"
            )
            return TransferResult(
                success=False,
                session=None,
                assignment_history=None,
                assigned_staff_id=None,
                candidate_staff_ids=None,
                waiting_queue=None,
                queue_position=None,
                message=f"Visitor cannot enter queue (current status: {visitor.service_status}). Only NEW or CLOSED status allowed.",
            )
        
        # 2. Get or create session
        session = await _get_or_create_session(
            db=db,
            visitor_id=visitor_id,
            project_id=project_id,
            session_id=session_id,
            platform_id=platform_id or visitor.platform_id,
        )
        
        # 3. Get assignment rule for the project
        assignment_rule = db.query(VisitorAssignmentRule).filter(
            VisitorAssignmentRule.project_id == project_id,
        ).first()
        
        # 4. Determine staff assignment using assign_staff method
        previous_staff_id = session.staff_id  # Record previous staff for transfers
        
        assignment_result = await assign_staff(
            db=db,
            visitor_id=visitor_id,
            project_id=project_id,
            target_staff_id=target_staff_id,
            visitor_message=visitor_message,
            assignment_rule=assignment_rule,
        )
        
        assigned_staff_id = assignment_result.assigned_staff_id
        candidate_staff_ids = assignment_result.candidate_staff_ids
        llm_response = assignment_result.llm_response
        llm_reasoning = assignment_result.llm_reasoning
        candidate_scores = assignment_result.candidate_scores
        model_used = assignment_result.model_used
        prompt_used = assignment_result.prompt_used
        
        # 5. Handle case when no staff is assigned - optionally add to waiting queue
        if not assigned_staff_id and len(candidate_staff_ids) == 0 and add_to_queue_if_no_staff:
            waiting_queue_entry, queue_position = await _add_to_waiting_queue(
                db=db,
                project_id=project_id,
                visitor_id=visitor_id,
                visitor=visitor,
                session_id=session.id,
                visitor_message=visitor_message,
                reason="No available staff",
                assignment_rule=assignment_rule,
                ai_disabled=ai_disabled,
            )
        
        # 6. Update visitor - set AI disabled status (only if explicitly provided)
        if ai_disabled is not None:
            visitor.ai_disabled = ai_disabled
        if assigned_staff_id:
            # Staff assigned - set to ACTIVE
            visitor.set_status_active()
        # If not assigned (queued), status was already set to QUEUED above
        
        # 7. Update session with assigned staff
        if assigned_staff_id:
            session.staff_id = assigned_staff_id
        session.updated_at = datetime.utcnow()
        
        # 8. Create assignment history record
        assignment_history = _create_assignment_history(
            db=db,
            project_id=project_id,
            visitor_id=visitor_id,
            session_id=session.id,
            assigned_staff_id=assigned_staff_id,
            previous_staff_id=previous_staff_id,
            assigned_by_staff_id=assigned_by_staff_id,
            assignment_rule=assignment_rule,
            source=source,
            visitor_message=visitor_message,
            notes=notes,
            model_used=model_used,
            prompt_used=prompt_used,
            llm_response=llm_response,
            llm_reasoning=llm_reasoning,
            candidate_staff_ids=candidate_staff_ids,
            candidate_scores=candidate_scores,
        )
        
        # 9. Flush first to validate data and get IDs
        db.flush()
        
        # 10. Add staff to visitor's channel and send notification
        if assigned_staff_id:
            await _add_staff_to_channel(
                db=db,
                project_id=project_id,
                visitor_id=visitor_id,
                staff_id=assigned_staff_id,
                ai_disabled=visitor.ai_disabled or False,
                send_notification=send_notification,
            )
        
        # 11. Commit changes (if auto_commit enabled)
        if auto_commit:
            db.commit()
            db.refresh(session)
            db.refresh(assignment_history)
            if waiting_queue_entry:
                db.refresh(waiting_queue_entry)
        
        logger.info(
            f"Transferred visitor {visitor_id} to human service. "
            f"Session: {session.id}, Assigned staff: {assigned_staff_id}, Source: {source.value}, "
            f"Candidates: {len(candidate_staff_ids)}, In queue: {waiting_queue_entry is not None}"
        )
        
        # Determine message based on result
        if assigned_staff_id:
            message = "Transfer successful"
        elif waiting_queue_entry:
            message = f"Added to waiting queue at position {queue_position}"
        else:
            message = "Transfer successful, awaiting staff assignment"
        
        return TransferResult(
            success=True,
            session=session,
            assignment_history=assignment_history,
            assigned_staff_id=assigned_staff_id,
            candidate_staff_ids=candidate_staff_ids,
            waiting_queue=waiting_queue_entry,
            queue_position=queue_position,
            message=message,
        )
        
    except Exception as e:
        logger.error(f"Error transferring visitor {visitor_id} to human: {e}")
        db.rollback()
        return TransferResult(
            success=False,
            session=None,
            assignment_history=None,
            assigned_staff_id=None,
            candidate_staff_ids=None,
            waiting_queue=None,
            queue_position=None,
            message=f"Transfer failed: {str(e)}",
        )


async def assign_staff(
    db: Session,
    visitor_id: UUID,
    project_id: UUID,
    target_staff_id: Optional[UUID] = None,
    visitor_message: Optional[str] = None,
    assignment_rule: Optional[VisitorAssignmentRule] = None,
) -> StaffAssignmentResult:
    """
    Assign a staff member to handle a visitor.
    
    Assignment logic:
    1. If target_staff_id specified, assign directly
    2. Otherwise, get available staff candidates based on rules
    3. Prioritize last serving staff if available
    4. If candidates > 1 and LLM enabled, use LLM to select
    5. If candidates > 1 and LLM disabled, use load balancing
    6. If candidates = 1, assign directly
    7. If candidates = 0, return None
    
    Args:
        db: Database session
        visitor_id: ID of the visitor
        project_id: ID of the project
        target_staff_id: Specific staff to assign (optional)
        visitor_message: Message that triggered the transfer (for LLM context)
        assignment_rule: Assignment rule for the project (optional)
        
    Returns:
        StaffAssignmentResult with assigned_staff_id and candidate info
    """
    assigned_staff_id: Optional[UUID] = None
    candidate_staff_ids: List[UUID] = []
    llm_response: Optional[str] = None
    llm_reasoning: Optional[str] = None
    candidate_scores: Optional[dict] = None
    model_used: Optional[str] = None
    prompt_used: Optional[str] = None
    
    # Get visitor for LLM context
    visitor = db.query(Visitor).filter(
        Visitor.id == visitor_id,
        Visitor.project_id == project_id,
        Visitor.deleted_at.is_(None),
    ).first()
    
    if target_staff_id:
        # Direct assignment to specified staff
        staff = db.query(Staff).filter(
            Staff.id == target_staff_id,
            Staff.project_id == project_id,
            Staff.deleted_at.is_(None),
        ).first()
        
        if staff:
            assigned_staff_id = target_staff_id
            candidate_staff_ids = [target_staff_id]
            logger.info(f"Direct assignment to staff {target_staff_id}")
        else:
            logger.warning(f"Target staff {target_staff_id} not found, will try auto-assignment")
    
    # Auto-assignment if no target specified or target not found
    if not assigned_staff_id:
        # Get assignment rule if not provided
        if assignment_rule is None:
            assignment_rule = db.query(VisitorAssignmentRule).filter(
                VisitorAssignmentRule.project_id == project_id,
            ).first()
        
        # Get available staff candidates
        candidates = await _get_available_staff_candidates(
            db=db,
            project_id=project_id,
            assignment_rule=assignment_rule,
        )
        
        candidate_staff_ids = [c.id for c in candidates]
        
        if len(candidates) == 0:
            # No available staff
            logger.info(f"No available staff for project {project_id}")
            
        elif len(candidates) == 1:
            # Single candidate, assign directly
            assigned_staff_id = candidates[0].id
            logger.info(f"Single candidate {assigned_staff_id}, assigning directly")
            
        else:
            # Multiple candidates - first check for last serving staff
            last_session = db.query(VisitorSession).filter(
                VisitorSession.visitor_id == visitor_id,
                VisitorSession.project_id == project_id,
                VisitorSession.staff_id.isnot(None),
            ).order_by(VisitorSession.created_at.desc()).first()
            
            if last_session and last_session.staff_id:
                last_staff_id = last_session.staff_id
                # Check if last staff is among available candidates
                for candidate in candidates:
                    if candidate.id == last_staff_id:
                        assigned_staff_id = last_staff_id
                        logger.info(
                            f"Prioritizing last serving staff {last_staff_id} for visitor {visitor_id}",
                            extra={
                                "visitor_id": str(visitor_id),
                                "last_staff_id": str(last_staff_id),
                            }
                        )
                        break
            
            # If no last serving staff available, use LLM or load balancing
            if not assigned_staff_id:
                if assignment_rule and assignment_rule.llm_assignment_enabled and visitor:
                    # Use LLM to select
                    logger.info(f"Multiple candidates ({len(candidates)}), using LLM assignment")
                    result = await _llm_assign_staff(
                        db=db,
                        project_id=project_id,
                        visitor=visitor,
                        visitor_message=visitor_message,
                        candidates=candidates,
                        assignment_rule=assignment_rule,
                    )
                    assigned_staff_id = result.get("selected_staff_id")
                    llm_response = result.get("llm_response")
                    llm_reasoning = result.get("reasoning")
                    candidate_scores = result.get("scores")
                    model_used = result.get("model_used")
                    prompt_used = result.get("prompt_used")
                else:
                    # Use load balancing (select staff with least active chats)
                    logger.info(f"Multiple candidates ({len(candidates)}), using load balancing")
                    assigned_staff_id = await _load_balance_assign(candidates)
    
    return StaffAssignmentResult(
        assigned_staff_id=assigned_staff_id,
        candidate_staff_ids=candidate_staff_ids,
        llm_response=llm_response,
        llm_reasoning=llm_reasoning,
        candidate_scores=candidate_scores,
        model_used=model_used,
        prompt_used=prompt_used,
    )


async def _add_to_waiting_queue(
    db: Session,
    project_id: UUID,
    visitor_id: UUID,
    visitor: Visitor,
    session_id: UUID,
    visitor_message: Optional[str],
    reason: str,
    assignment_rule: Optional[VisitorAssignmentRule],
    ai_disabled: Optional[bool],
) -> tuple[VisitorWaitingQueue, int]:
    """
    Add visitor to the waiting queue.
    
    Args:
        db: Database session
        project_id: Project ID
        visitor_id: Visitor ID
        visitor: Visitor object
        session_id: Session ID
        visitor_message: Message that triggered the transfer
        reason: Reason for entering queue
        assignment_rule: Assignment rule for timeout config
        ai_disabled: AI disabled flag
        
    Returns:
        Tuple of (waiting_queue_entry, queue_position)
    """
    # Check if already in waiting queue
    existing_queue = db.query(VisitorWaitingQueue).filter(
        VisitorWaitingQueue.visitor_id == visitor_id,
        VisitorWaitingQueue.project_id == project_id,
        VisitorWaitingQueue.status == WaitingStatus.WAITING.value,
    ).first()
    
    if existing_queue:
        logger.info(f"Visitor {visitor_id} already in waiting queue at position {existing_queue.position}")
        return existing_queue, existing_queue.position
    
    # Calculate queue position
    current_queue_count = db.query(VisitorWaitingQueue).filter(
        VisitorWaitingQueue.project_id == project_id,
        VisitorWaitingQueue.status == WaitingStatus.WAITING.value,
    ).count()
    queue_position = current_queue_count + 1
    
    # Calculate expiration time
    timeout_minutes = settings.QUEUE_DEFAULT_TIMEOUT_MINUTES
    if assignment_rule and assignment_rule.queue_wait_timeout_minutes:
        timeout_minutes = assignment_rule.queue_wait_timeout_minutes
    expired_at = datetime.utcnow() + timedelta(minutes=timeout_minutes)
    
    # Create queue entry
    waiting_queue_entry = VisitorWaitingQueue(
        project_id=project_id,
        visitor_id=visitor_id,
        session_id=session_id,
        source=QueueSource.NO_STAFF.value,
        position=queue_position,
        priority=0,
        status=WaitingStatus.WAITING.value,
        visitor_message=visitor_message,
        reason=reason,
        expired_at=expired_at,
        ai_disabled=ai_disabled,
    )
    db.add(waiting_queue_entry)
    
    # Update visitor status to QUEUED
    visitor.set_status_queued()
    
    logger.info(
        f"Added visitor {visitor_id} to waiting queue at position {queue_position}",
        extra={
            "visitor_id": str(visitor_id),
            "queue_position": queue_position,
            "expired_at": str(expired_at),
            "timeout_minutes": timeout_minutes,
        }
    )
    
    # Send queue updated event
    try:
        staff_channel_id = build_project_staff_channel_id(project_id)
        await wukongim_client.send_queue_updated_event(
            channel_id=staff_channel_id,
            channel_type=CHANNEL_TYPE_PROJECT_STAFF,
            project_id=str(project_id),
            waiting_count=queue_position,
        )
    except Exception as e:
        logger.error(f"Failed to send queue updated event: {e}")
    
    return waiting_queue_entry, queue_position


async def _add_staff_to_channel(
    db: Session,
    project_id: UUID,
    visitor_id: UUID,
    staff_id: UUID,
    ai_disabled: bool = False,
    send_notification: bool = True,
) -> None:
    """
    Add staff to visitor's channel (both DB and WuKongIM) and send notification.
    Removes any existing staff from the channel first.
    
    Args:
        db: Database session
        project_id: Project ID
        visitor_id: Visitor ID
        staff_id: Staff ID to add
        ai_disabled: Whether AI is disabled (only send message when True)
        send_notification: Whether to send staff assigned system message
    """
    visitor_channel_id = build_visitor_channel_id(visitor_id)
    staff_uid = f"{staff_id}-staff"
    
    # 1. Remove existing staff members from the channel (both DB and WuKongIM)
    existing_staff_members = db.query(ChannelMember).filter(
        ChannelMember.channel_id == visitor_channel_id,
        ChannelMember.channel_type == CHANNEL_TYPE_CUSTOMER_SERVICE,
        ChannelMember.member_type == MEMBER_TYPE_STAFF,
        ChannelMember.member_id != staff_id,  # Don't remove the new staff
        ChannelMember.deleted_at.is_(None),
    ).all()
    
    for old_member in existing_staff_members:
        old_member.deleted_at = datetime.utcnow()
        old_staff_uid = f"{old_member.member_id}-staff"
        
        # Remove from WuKongIM
        try:
            await wukongim_client.remove_channel_subscribers(
                channel_id=visitor_channel_id,
                channel_type=CHANNEL_TYPE_CUSTOMER_SERVICE,
                subscribers=[old_staff_uid],
            )
        except Exception as e:
            logger.warning(f"Failed to remove old staff {old_member.member_id} from WuKongIM: {e}")
        
        logger.info(
            f"Removed old staff {old_member.member_id} from channel",
            extra={"visitor_id": str(visitor_id), "old_staff_id": str(old_member.member_id)},
        )
    
    if existing_staff_members:
        db.flush()
    
    # 2. Add new staff to ChannelMember table if not exists
    existing_member = db.query(ChannelMember).filter(
        ChannelMember.channel_id == visitor_channel_id,
        ChannelMember.member_id == staff_id,
        ChannelMember.deleted_at.is_(None),
    ).first()
    
    if not existing_member:
        channel_member = ChannelMember(
            project_id=project_id,
            channel_id=visitor_channel_id,
            channel_type=CHANNEL_TYPE_CUSTOMER_SERVICE,
            member_id=staff_id,
            member_type=MEMBER_TYPE_STAFF,
        )
        db.add(channel_member)
        db.flush()
        
        logger.info(
            f"Added staff {staff_id} to ChannelMember table",
            extra={"visitor_id": str(visitor_id), "staff_id": str(staff_id)},
        )
    
    # 3. Add to WuKongIM channel
    await wukongim_client.add_channel_subscribers(
        channel_id=visitor_channel_id,
        channel_type=CHANNEL_TYPE_CUSTOMER_SERVICE,
        subscribers=[staff_uid],
    )
    
    logger.info(
        f"Added staff {staff_id} to WuKongIM channel {visitor_channel_id}",
        extra={"visitor_id": str(visitor_id), "staff_id": str(staff_id)},
    )
    
    # Send staff assigned system message only when AI is disabled and notification is enabled
    if ai_disabled and send_notification:
        assigned_staff = db.query(Staff).filter(Staff.id == staff_id).first()
        staff_display_name = assigned_staff.name or assigned_staff.username if assigned_staff else str(staff_id)
        
        await wukongim_client.send_staff_assigned_message(
            from_uid=staff_uid,
            channel_id=visitor_channel_id,
            channel_type=CHANNEL_TYPE_CUSTOMER_SERVICE,
            staff_uid=staff_uid,
            staff_name=staff_display_name,
        )
        
        logger.info(
            f"Sent staff assigned message",
            extra={"visitor_id": str(visitor_id), "staff_id": str(staff_id), "staff_name": staff_display_name},
        )


def _create_assignment_history(
    db: Session,
    project_id: UUID,
    visitor_id: UUID,
    session_id: UUID,
    assigned_staff_id: Optional[UUID],
    previous_staff_id: Optional[UUID],
    assigned_by_staff_id: Optional[UUID],
    assignment_rule: Optional[VisitorAssignmentRule],
    source: AssignmentSource,
    visitor_message: Optional[str],
    notes: Optional[str],
    model_used: Optional[str],
    prompt_used: Optional[str],
    llm_response: Optional[str],
    llm_reasoning: Optional[str],
    candidate_staff_ids: List[UUID],
    candidate_scores: Optional[dict],
) -> VisitorAssignmentHistory:
    """
    Create assignment history record.
    
    Returns:
        VisitorAssignmentHistory object (not yet committed)
    """
    assignment_history = VisitorAssignmentHistory(
        project_id=project_id,
        visitor_id=visitor_id,
        session_id=session_id,
        assigned_staff_id=assigned_staff_id,
        previous_staff_id=previous_staff_id,
        assigned_by_staff_id=assigned_by_staff_id,
        assignment_rule_id=assignment_rule.id if assignment_rule else None,
        source=source.value,
        visitor_message=visitor_message,
        notes=notes,
        model_used=model_used,
        prompt_used=prompt_used,
        llm_response=llm_response,
        reasoning=llm_reasoning,
        candidate_staff_ids=[str(sid) for sid in candidate_staff_ids] if candidate_staff_ids else None,
        candidate_scores=candidate_scores,
    )
    db.add(assignment_history)
    return assignment_history


async def _get_or_create_session(
    db: Session,
    visitor_id: UUID,
    project_id: UUID,
    session_id: Optional[UUID] = None,
    platform_id: Optional[UUID] = None,
) -> VisitorSession:
    """
    Get existing session or create a new one.
    """
    # If session_id provided, try to get it
    if session_id:
        session = db.query(VisitorSession).filter(
            VisitorSession.id == session_id,
            VisitorSession.project_id == project_id,
        ).first()
        if session:
            return session
    
    # Try to find an open session for this visitor
    session = db.query(VisitorSession).filter(
        VisitorSession.visitor_id == visitor_id,
        VisitorSession.project_id == project_id,
        VisitorSession.status == SessionStatus.OPEN.value,
    ).order_by(VisitorSession.created_at.desc()).first()
    
    if session:
        return session
    
    # Create new session
    session = VisitorSession(
        project_id=project_id,
        visitor_id=visitor_id,
        platform_id=platform_id,
        status=SessionStatus.OPEN.value,
    )
    db.add(session)
    db.flush()
    
    logger.info(f"Created new session {session.id} for visitor {visitor_id}")
    return session


def is_within_service_hours(assignment_rule: Optional[VisitorAssignmentRule]) -> bool:
    """
    Check if current time is within configured service hours.
    
    The service hours are evaluated in the configured timezone (default: Asia/Shanghai).
    
    Returns True if:
    - No assignment rule configured
    - Service hours not configured (all fields are None)
    - Current time is within service hours (in the configured timezone)
    """
    if not assignment_rule:
        return True
    
    # Get the configured timezone, default to Asia/Shanghai
    tz_name = assignment_rule.timezone or "Asia/Shanghai"
    try:
        tz = ZoneInfo(tz_name)
    except Exception as e:
        logger.warning(f"Invalid timezone '{tz_name}': {e}, using Asia/Shanghai")
        tz = ZoneInfo("Asia/Shanghai")
    
    # Get current time in the configured timezone
    now = datetime.now(tz)
    
    # Check weekday (1=Monday, 7=Sunday in our config; Python: 0=Monday, 6=Sunday)
    if assignment_rule.service_weekdays:
        # Convert Python weekday (0-6) to our format (1-7)
        current_weekday = now.weekday() + 1
        if current_weekday not in assignment_rule.service_weekdays:
            logger.debug(f"Current weekday {current_weekday} (tz={tz_name}) not in service weekdays {assignment_rule.service_weekdays}")
            return False
    
    # Check time range
    if assignment_rule.service_start_time and assignment_rule.service_end_time:
        try:
            start_parts = assignment_rule.service_start_time.split(":")
            end_parts = assignment_rule.service_end_time.split(":")
            
            start_time = time(int(start_parts[0]), int(start_parts[1]))
            end_time = time(int(end_parts[0]), int(end_parts[1]))
            current_time = now.time()
            
            # Handle normal case (e.g., 09:00 - 18:00)
            if start_time <= end_time:
                if not (start_time <= current_time <= end_time):
                    logger.debug(f"Current time {current_time} (tz={tz_name}) not in service hours {start_time}-{end_time}")
                    return False
            else:
                # Handle overnight case (e.g., 22:00 - 06:00)
                if not (current_time >= start_time or current_time <= end_time):
                    logger.debug(f"Current time {current_time} (tz={tz_name}) not in overnight service hours {start_time}-{end_time}")
                    return False
        except (ValueError, IndexError) as e:
            logger.warning(f"Invalid service time format: {e}")
            # If time format is invalid, don't block assignment
            return True
    
    return True


async def _get_available_staff_candidates(
    db: Session,
    project_id: UUID,
    assignment_rule: Optional[VisitorAssignmentRule] = None,
) -> List[StaffCandidate]:
    """
    Get available staff candidates for assignment.
    
    Filters:
    - Not deleted
    - Role is user only (not admin or agent)
    - Within service hours (if configured)
    - Within max_concurrent_chats limit (if configured)
    """
    # Check if within service hours
    if not is_within_service_hours(assignment_rule):
        logger.info(f"Outside service hours for project {project_id}")
        return []
    
    # Get max concurrent chats from rule
    max_concurrent = None
    if assignment_rule and assignment_rule.max_concurrent_chats:
        max_concurrent = assignment_rule.max_concurrent_chats
    
    # Query available staff (only user role, not admin or agent, active and not paused)
    staff_query = db.query(Staff).filter(
        Staff.project_id == project_id,
        Staff.deleted_at.is_(None),
        Staff.is_active == True,  # noqa: E712 - SQLAlchemy requires == for boolean
        Staff.service_paused == False,  # noqa: E712 - SQLAlchemy requires == for boolean
    )
    
    available_staff = staff_query.all()
    
    if not available_staff:
        return []
    
    # Get current active chat count for each staff
    candidates = []
    for staff in available_staff:
        # Count active sessions for this staff
        active_session_count = db.query(func.count(VisitorSession.id)).filter(
            VisitorSession.staff_id == staff.id,
            VisitorSession.status == SessionStatus.OPEN.value,
        ).scalar() or 0
        
        # Skip if at max capacity
        if max_concurrent and active_session_count >= max_concurrent:
            logger.debug(f"Staff {staff.id} at max capacity ({active_session_count}/{max_concurrent})")
            continue
        
        candidates.append(StaffCandidate(
            id=staff.id,
            name=staff.name,
            nickname=staff.nickname,
            description=staff.description,
            status=staff.status,
            current_chat_count=active_session_count,
        ))
    
    return candidates


async def _load_balance_assign(candidates: List[StaffCandidate]) -> Optional[UUID]:
    """
    Select staff with lowest current chat count (load balancing).
    """
    if not candidates:
        return None
    
    # Sort by current chat count ascending
    sorted_candidates = sorted(candidates, key=lambda c: c.current_chat_count)
    return sorted_candidates[0].id


async def _llm_assign_staff(
    db: Session,
    project_id: UUID,
    visitor: Visitor,
    visitor_message: Optional[str],
    candidates: List[StaffCandidate],
    assignment_rule: VisitorAssignmentRule,
) -> dict:
    """
    Use LLM to select the best staff for the visitor.
    
    Returns:
        Dict with selected_staff_id, llm_response, reasoning, scores, model_used, prompt_used
    """
    result = {
        "selected_staff_id": None,
        "llm_response": None,
        "reasoning": None,
        "scores": None,
        "model_used": None,
        "prompt_used": None,
    }
    
    # Validate assignment rule has LLM config
    if not assignment_rule.ai_provider_id:
        logger.warning("LLM assignment enabled but no ai_provider_id configured, falling back to load balancing")
        result["selected_staff_id"] = await _load_balance_assign(candidates)
        result["reasoning"] = "Fallback to load balancing: no AI provider configured"
        return result
    
    # Build staff info for prompt
    staff_info_list = []
    for i, c in enumerate(candidates, 1):
        name = c.name or c.nickname or f"Staff_{c.id}"
        desc = c.description or "No description available"
        staff_info_list.append(f"{i}. ID: {c.id}\n   Name: {name}\n   Description: {desc}\n   Current chats: {c.current_chat_count}")
    
    staff_info = "\n".join(staff_info_list)
    
    # Build visitor info
    visitor_name = visitor.name or visitor.nickname or "Unknown"
    visitor_info = f"Name: {visitor_name}"
    if visitor_message:
        visitor_info += f"\nMessage: {visitor_message}"
    
    # Get the prompt
    system_prompt = assignment_rule.effective_prompt
    
    # Build the user message
    user_message = f"""请根据以下信息，选择最合适的客服人员来处理此访客。

## 访客信息
{visitor_info}

## 可用客服列表
{staff_info}

请返回JSON格式的结果：
{{
  "selected_staff_id": "选中的客服ID",
  "reasoning": "选择理由"
}}

只返回JSON，不要其他内容。"""

    result["prompt_used"] = f"System: {system_prompt}\n\nUser: {user_message}"
    result["model_used"] = assignment_rule.model
    
    try:
        from app.services.ai_client import ai_client
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
        
        response = await ai_client.chat_completions(
            project_id=str(project_id),
            provider_id=str(assignment_rule.ai_provider_id),
            model=assignment_rule.model or "gpt-4",
            messages=messages,
            temperature=0.3,
            max_tokens=500,
        )
        
        # Parse response
        if response and "choices" in response and len(response["choices"]) > 0:
            content = response["choices"][0].get("message", {}).get("content", "")
            result["llm_response"] = content
            
            # Try to parse JSON from response
            try:
                # Handle markdown code blocks
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                
                parsed = json.loads(content)
                selected_id = parsed.get("selected_staff_id")
                result["reasoning"] = parsed.get("reasoning")
                
                # Validate selected_id is in candidates
                candidate_ids = [str(c.id) for c in candidates]
                if selected_id and str(selected_id) in candidate_ids:
                    result["selected_staff_id"] = UUID(str(selected_id))
                    logger.info(f"LLM selected staff {selected_id}: {result['reasoning']}")
                else:
                    logger.warning(f"LLM returned invalid staff_id {selected_id}, falling back to load balancing")
                    result["selected_staff_id"] = await _load_balance_assign(candidates)
                    result["reasoning"] = f"LLM returned invalid ID, fallback to load balancing. Original: {result['reasoning']}"
                    
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Failed to parse LLM response: {e}, falling back to load balancing")
                result["selected_staff_id"] = await _load_balance_assign(candidates)
                result["reasoning"] = f"Failed to parse LLM response, fallback to load balancing"
        else:
            logger.warning("Empty LLM response, falling back to load balancing")
            result["selected_staff_id"] = await _load_balance_assign(candidates)
            result["reasoning"] = "Empty LLM response, fallback to load balancing"
            
    except Exception as e:
        logger.error(f"LLM assignment failed: {e}, falling back to load balancing")
        result["selected_staff_id"] = await _load_balance_assign(candidates)
        result["reasoning"] = f"LLM assignment failed: {str(e)}, fallback to load balancing"
    
    return result


async def reassign_to_staff(
    db: Session,
    visitor_id: UUID,
    project_id: UUID,
    new_staff_id: UUID,
    assigned_by_staff_id: Optional[UUID] = None,
    session_id: Optional[UUID] = None,
    notes: Optional[str] = None,
) -> TransferResult:
    """
    Reassign a visitor to a different staff member.
    """
    return await transfer_to_staff(
        db=db,
        visitor_id=visitor_id,
        project_id=project_id,
        source=AssignmentSource.TRANSFER,
        target_staff_id=new_staff_id,
        assigned_by_staff_id=assigned_by_staff_id,
        session_id=session_id,
        notes=notes,
    )


async def assign_from_waiting_queue(
    db: Session,
    staff_id: UUID,
    project_id: UUID,
    queue_entry_id: Optional[UUID] = None,
) -> Optional[TransferResult]:
    """
    Assign the next visitor from waiting queue to a staff member.
    
    Args:
        db: Database session
        staff_id: Staff member to assign visitor to
        project_id: Project ID
        queue_entry_id: Specific queue entry to assign (optional, defaults to next in line)
        
    Returns:
        TransferResult if successful, None if queue is empty
    """
    # Validate staff exists
    staff = db.query(Staff).filter(
        Staff.id == staff_id,
        Staff.project_id == project_id,
        Staff.deleted_at.is_(None),
    ).first()
    
    if not staff:
        logger.warning(f"Staff {staff_id} not found for queue assignment")
        return None
    
    # Get the queue entry
    if queue_entry_id:
        queue_entry = db.query(VisitorWaitingQueue).filter(
            VisitorWaitingQueue.id == queue_entry_id,
            VisitorWaitingQueue.project_id == project_id,
            VisitorWaitingQueue.status == WaitingStatus.WAITING.value,
        ).first()
    else:
        # Get the next visitor in queue (ordered by priority desc, position asc)
        queue_entry = db.query(VisitorWaitingQueue).filter(
            VisitorWaitingQueue.project_id == project_id,
            VisitorWaitingQueue.status == WaitingStatus.WAITING.value,
        ).order_by(
            VisitorWaitingQueue.priority.desc(),
            VisitorWaitingQueue.position.asc(),
        ).first()
    
    if not queue_entry:
        logger.info(f"No visitors in waiting queue for project {project_id}")
        return None
    
    # Mark queue entry as assigned
    queue_entry.assign_to_staff(staff_id)
    db.flush()
    
    logger.info(
        f"Assigning visitor {queue_entry.visitor_id} from queue to staff {staff_id}"
    )
    
    # Transfer the visitor to the staff
    result = await transfer_to_staff(
        db=db,
        visitor_id=queue_entry.visitor_id,
        project_id=project_id,
        source=AssignmentSource.RULE,
        target_staff_id=staff_id,
        session_id=queue_entry.session_id,
        visitor_message=queue_entry.visitor_message,
        notes=f"Assigned from waiting queue (position: {queue_entry.position})",
        ai_disabled=queue_entry.ai_disabled,
    )
    
    return result


def get_waiting_queue_count(db: Session, project_id: UUID) -> int:
    """Get the number of visitors waiting in queue for a project."""
    return db.query(VisitorWaitingQueue).filter(
        VisitorWaitingQueue.project_id == project_id,
        VisitorWaitingQueue.status == WaitingStatus.WAITING.value,
    ).count()


def get_visitor_queue_position(
    db: Session, 
    visitor_id: UUID, 
    project_id: UUID
) -> Optional[int]:
    """Get a visitor's position in the waiting queue, or None if not in queue."""
    queue_entry = db.query(VisitorWaitingQueue).filter(
        VisitorWaitingQueue.visitor_id == visitor_id,
        VisitorWaitingQueue.project_id == project_id,
        VisitorWaitingQueue.status == WaitingStatus.WAITING.value,
    ).first()
    
    if not queue_entry:
        return None
    
    # Count how many visitors are ahead (higher priority or lower position)
    position = db.query(VisitorWaitingQueue).filter(
        VisitorWaitingQueue.project_id == project_id,
        VisitorWaitingQueue.status == WaitingStatus.WAITING.value,
        (
            (VisitorWaitingQueue.priority > queue_entry.priority) |
            (
                (VisitorWaitingQueue.priority == queue_entry.priority) &
                (VisitorWaitingQueue.position < queue_entry.position)
            )
        )
    ).count() + 1
    
    return position


async def cancel_visitor_from_queue(
    db: Session,
    visitor_id: UUID,
    project_id: UUID,
) -> bool:
    """
    Cancel a visitor's waiting queue entry.
    
    Returns True if cancelled, False if not in queue.
    """
    queue_entry = db.query(VisitorWaitingQueue).filter(
        VisitorWaitingQueue.visitor_id == visitor_id,
        VisitorWaitingQueue.project_id == project_id,
        VisitorWaitingQueue.status == WaitingStatus.WAITING.value,
    ).first()
    
    if not queue_entry:
        return False
    
    queue_entry.cancel()
    db.commit()
    
    logger.info(f"Cancelled visitor {visitor_id} from waiting queue")
    return True
