"""Transfer to human service for visitor assignment."""

import json
from dataclasses import dataclass
from datetime import datetime, time
from typing import List, Optional
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models import (
    Visitor,
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
)

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


async def transfer_to_human(
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
) -> TransferResult:
    """
    Transfer a visitor to human service.
    
    Assignment logic:
    1. If target_staff_id specified, assign directly
    2. Otherwise, get available staff candidates based on rules
    3. If candidates > 1 and LLM enabled, use LLM to select
    4. If candidates > 1 and LLM disabled, use load balancing
    5. If candidates = 1, assign directly
    6. If candidates = 0, leave unassigned
    
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
        
        # 4. Determine staff assignment
        assigned_staff_id = None
        previous_staff_id = session.staff_id  # Record previous staff for transfers
        
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
            else:
                logger.warning(f"Target staff {target_staff_id} not found, will try auto-assignment")
        
        # Auto-assignment if no target specified or target not found
        if not assigned_staff_id:
            # Get available staff candidates
            candidates = await _get_available_staff_candidates(
                db=db,
                project_id=project_id,
                assignment_rule=assignment_rule,
            )
            
            candidate_staff_ids = [c.id for c in candidates]
            
            if len(candidates) == 0:
                # No available staff - add to waiting queue
                logger.info(f"No available staff for project {project_id}, adding to waiting queue")
                no_staff_reason = "No available staff"
                
                # Check if already in waiting queue
                existing_queue = db.query(VisitorWaitingQueue).filter(
                    VisitorWaitingQueue.visitor_id == visitor_id,
                    VisitorWaitingQueue.project_id == project_id,
                    VisitorWaitingQueue.status == WaitingStatus.WAITING.value,
                ).first()
                
                if existing_queue:
                    # Already in queue, update position info
                    waiting_queue_entry = existing_queue
                    queue_position = existing_queue.position
                    logger.info(f"Visitor {visitor_id} already in waiting queue at position {queue_position}")
                else:
                    # Calculate queue position (count waiting visitors + 1)
                    current_queue_count = db.query(VisitorWaitingQueue).filter(
                        VisitorWaitingQueue.project_id == project_id,
                        VisitorWaitingQueue.status == WaitingStatus.WAITING.value,
                    ).count()
                    queue_position = current_queue_count + 1
                    
                    # Add to waiting queue
                    waiting_queue_entry = VisitorWaitingQueue(
                        project_id=project_id,
                        visitor_id=visitor_id,
                        session_id=session.id,
                        source=QueueSource.NO_STAFF.value,
                        position=queue_position,
                        priority=0,  # Default priority, can be adjusted for VIP
                        status=WaitingStatus.WAITING.value,
                        visitor_message=visitor_message,
                        reason=no_staff_reason,
                    )
                    db.add(waiting_queue_entry)
                    logger.info(f"Added visitor {visitor_id} to waiting queue at position {queue_position}")
            
            elif len(candidates) == 1:
                # Single candidate, assign directly
                assigned_staff_id = candidates[0].id
                logger.info(f"Single candidate {assigned_staff_id}, assigning directly")
            
            else:
                # Multiple candidates
                if assignment_rule and assignment_rule.llm_assignment_enabled:
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
        
        # 5. Update visitor - disable AI responses
        visitor.ai_disabled = True
        visitor.updated_at = datetime.utcnow()
        
        # 6. Update session with assigned staff
        if assigned_staff_id:
            session.staff_id = assigned_staff_id
        session.updated_at = datetime.utcnow()
        
        # 7. Create assignment history record
        assignment_history = VisitorAssignmentHistory(
            project_id=project_id,
            visitor_id=visitor_id,
            session_id=session.id,
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
            candidate_staff_ids=candidate_staff_ids if candidate_staff_ids else None,
            candidate_scores=candidate_scores,
        )
        db.add(assignment_history)
        
        # 8. Commit changes
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


def _is_within_service_hours(assignment_rule: Optional[VisitorAssignmentRule]) -> bool:
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
    if not _is_within_service_hours(assignment_rule):
        logger.info(f"Outside service hours for project {project_id}")
        return []
    
    # Get max concurrent chats from rule
    max_concurrent = None
    if assignment_rule and assignment_rule.max_concurrent_chats:
        max_concurrent = assignment_rule.max_concurrent_chats
    
    # Query available staff (only user role, not admin or agent)
    staff_query = db.query(Staff).filter(
        Staff.project_id == project_id,
        Staff.deleted_at.is_(None),
        Staff.role == StaffRole.USER.value,
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
    return await transfer_to_human(
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
    result = await transfer_to_human(
        db=db,
        visitor_id=queue_entry.visitor_id,
        project_id=project_id,
        source=AssignmentSource.RULE,
        target_staff_id=staff_id,
        session_id=queue_entry.session_id,
        visitor_message=queue_entry.visitor_message,
        notes=f"Assigned from waiting queue (position: {queue_entry.position})",
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
