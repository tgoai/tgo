"""Scheduled task for automatic AI fallback in assist mode."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional
from uuid import uuid4

from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.core.database import SessionLocal
from app.models import Platform, Visitor, VisitorServiceStatus, VisitorSession, SessionStatus
from app.services.chat_service import handle_ai_response_non_stream
from app.services.wukongim_client import wukongim_client
from app.utils.encoding import build_visitor_channel_id, get_session_id
from app.utils.const import CHANNEL_TYPE_CUSTOMER_SERVICE

logger = logging.getLogger(__name__)

_auto_fallback_task: Optional[asyncio.Task] = None

# Constants for retry logic
MAX_AI_FALLBACK_RETRIES = 3

async def start_auto_fallback_to_ai_task(interval_seconds: int = 60):
    """Start the periodic auto fallback check task."""
    global _auto_fallback_task
    if _auto_fallback_task is not None:
        return

    async def _loop():
        while True:
            try:
                await check_and_fallback_to_ai()
            except Exception as e:
                logger.error(f"Error in auto_fallback_to_ai loop: {e}")
            await asyncio.sleep(interval_seconds)

    _auto_fallback_task = asyncio.create_task(_loop())
    logger.info("Started auto fallback to AI periodic task")

async def stop_auto_fallback_to_ai_task():
    """Stop the periodic auto fallback check task."""
    global _auto_fallback_task
    if _auto_fallback_task:
        _auto_fallback_task.cancel()
        try:
            await _auto_fallback_task
        except asyncio.CancelledError:
            pass
        _auto_fallback_task = None
        logger.info("Stopped auto fallback to AI periodic task")

async def check_and_fallback_to_ai():
    """
    Scheduled task to check for visitors waiting too long in 'assist' mode platforms
    and trigger AI fallback.
    """
    db: Session = SessionLocal()
    try:
        # 1) Get platforms in assist mode with timeout > 0
        platforms = db.query(Platform).filter(
            Platform.ai_mode == "assist",
            Platform.fallback_to_ai_timeout > 0,
            Platform.is_active.is_(True),
            Platform.deleted_at.is_(None)
        ).all()

        if not platforms:
            return

        for platform in platforms:
            timeout_seconds = platform.fallback_to_ai_timeout
            cutoff_time = datetime.utcnow() - timedelta(seconds=timeout_seconds)

            # 2) Find visitors who:
            # - belong to this platform
            # - are NOT closed
            # - last message was from visitor
            # - last message was sent before cutoff_time
            # - have a valid last_client_msg_no to query
            # - have not exceeded the max retry count
            # - ai_disabled is not True
            visitors = db.query(Visitor).filter(
                Visitor.platform_id == platform.id,
                Visitor.service_status == VisitorServiceStatus.ACTIVE.value,
                Visitor.is_last_message_from_visitor.is_(True),
                Visitor.last_message_at < cutoff_time,
                Visitor.last_client_msg_no.isnot(None),
                Visitor.ai_fallback_retry_count < MAX_AI_FALLBACK_RETRIES,
                Visitor.deleted_at.is_(None),
                or_(Visitor.ai_disabled.is_(None), Visitor.ai_disabled.is_(False))
            ).all()

            for visitor in visitors:
                logger.info(f"Triggering AI fallback for visitor {visitor.id} on platform {platform.name}")
                
                # 3) Retrieve last message from WuKongIM via /message API using client_msg_no
                channel_id = build_visitor_channel_id(visitor.id)
                channel_type = CHANNEL_TYPE_CUSTOMER_SERVICE
                
                try:
                    # Query message by client_msg_no
                    last_msg = await wukongim_client.get_message_by_client_msg_no(
                        channel_id=channel_id,
                        channel_type=channel_type,
                        client_msg_no=visitor.last_client_msg_no
                    )
                    
                    if not last_msg:
                        logger.warning(f"No message found for visitor {visitor.id} with client_msg_no {visitor.last_client_msg_no}")
                        # If message not found, it's a permanent error for this message, stop retrying
                        visitor.ai_fallback_retry_count = MAX_AI_FALLBACK_RETRIES
                        db.add(visitor)
                        db.commit()
                        continue
                    
                    message_content = ""
                    if last_msg.payload:
                        message_content = last_msg.payload.get("content", "")
                    
                    if not message_content:
                        logger.warning(f"Last message for visitor {visitor.id} has no content or not a text message")
                        # If message content empty, stop retrying
                        visitor.ai_fallback_retry_count = MAX_AI_FALLBACK_RETRIES
                        db.add(visitor)
                        db.commit()
                        continue

                    # 4) Prepare for AI interaction (Identify from_uid)
                    response_client_msg_no = f"ai_fallback_{uuid4().hex}"
                    
                    # Check for an active session to get assigned staff
                    session = db.query(VisitorSession).filter(
                        VisitorSession.visitor_id == visitor.id,
                        VisitorSession.status == SessionStatus.OPEN.value,
                        VisitorSession.staff_id.isnot(None)
                    ).first()
                    
                    if session and session.staff_id:
                        from_uid = f"{session.staff_id}-staff"
                    else:
                        # Fallback to AI UID if no staff assigned yet
                        logger.debug(f"No staff assigned to visitor {visitor.id}, using fallback AI UID")
                        visitor.ai_fallback_retry_count = MAX_AI_FALLBACK_RETRIES
                        db.add(visitor)
                        db.commit()
                        continue

                    # 5) Call AI synchronously and wait for result
                    agent_runtime_kwargs: dict[str, str] = {}
                    if platform.agent_id is not None:
                        agent_runtime_kwargs["agent_id"] = str(platform.agent_id)
                    
                    try:
                        # Call AI and wait for completion (not background task)
                        ai_result = await handle_ai_response_non_stream(
                            project_id=str(platform.project_id),
                            visitor_id=str(visitor.id),
                            message=message_content,
                            channel_id=channel_id,
                            channel_type=channel_type,
                            client_msg_no=response_client_msg_no,
                            from_uid=from_uid,
                            session_id=get_session_id(from_uid, channel_id, channel_type),
                            **agent_runtime_kwargs,
                        )
                        
                        # 6) AI succeeded, update visitor state to prevent duplicate triggers
                        if ai_result:
                            visitor.is_last_message_from_ai = True
                            visitor.is_last_message_from_visitor = False
                            visitor.last_client_msg_no = response_client_msg_no
                            visitor.ai_fallback_retry_count = 0  # Reset retry count on success
                            db.add(visitor)
                            db.commit()
                            logger.info(f"AI fallback completed for visitor {visitor.id}")
                        else:
                            # If handle_ai_response_non_stream returns None without exception
                            logger.warning(f"AI fallback returned no result for visitor {visitor.id}, incrementing retry count")
                            visitor.ai_fallback_retry_count += 1
                            db.add(visitor)
                            db.commit()
                            
                    except Exception as ai_error:
                        # AI request failed. Increment retry count.
                        logger.error(f"AI fallback failed for visitor {visitor.id}: {ai_error}")
                        visitor.ai_fallback_retry_count += 1
                        db.add(visitor)
                        db.commit()
                        continue
                    
                except Exception as e:
                    logger.error(f"Failed to process AI fallback for visitor {visitor.id}: {e}")
                    db.rollback()
                    continue

    except Exception as e:
        logger.error(f"Error in check_and_fallback_to_ai task: {e}", exc_info=True)
    finally:
        db.close()
