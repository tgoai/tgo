"""Internal AI events endpoint (no authentication required).

This endpoint is designed for the AI Service to send events to the TGO API
without requiring JWT authentication. It runs on a separate port (8001) and
should only be accessible from the internal network.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import (
    Project,
    Visitor,
    VisitorAIInsight,
    VisitorCustomerUpdate,
    Tag,
    VisitorTag,
    VisitorWaitingQueue,
    QueueSource,
    QueueUrgency,
    WaitingStatus,
)
from app.schemas.ai import (
    AIServiceEvent,
    ManualServiceRequestEvent,
    VisitorInfoUpdateEvent,
    VisitorSentimentUpdateEvent,
    VisitorTagEvent,
)
from app.services.visitor_notifications import notify_visitor_profile_updated
from app.utils.intent import localize_intent
from app.models.tag import TagCategory

logger = logging.getLogger("internal.ai_events")

# Event type constants
MANUAL_SERVICE_EVENT = "manual_service.request"
VISITOR_INFO_EVENT = "visitor_info.update"
VISITOR_SENTIMENT_EVENT = "visitor_sentiment.update"
VISITOR_TAG_EVENT = "visitor_tag.add"
MANUAL_SERVICE_TAG_NAME = "Manual Service"
MANUAL_SERVICE_TAG_NAME_ZH = "转人工"

# Visitor field mapping for info updates
VISITOR_FIELD_MAP = {
    "name": "name",
    "nickname": "nickname",
    "email": "email",
    "phone": "phone_number",
    "phone_number": "phone_number",
    "company": "company",
    "job_title": "job_title",
    "avatar": "avatar_url",
    "avatar_url": "avatar_url",
    "note": "note",
    "source": "source",
}

router = APIRouter()


def _ensure_manual_service_tag(db: Session, project_id, visitor: Visitor) -> None:
    """Ensure the visitor carries the manual service escalation tag."""
    tag_id = Tag.generate_id(MANUAL_SERVICE_TAG_NAME, TagCategory.VISITOR)
    tag = (
        db.query(Tag)
        .filter(Tag.id == tag_id, Tag.project_id == project_id)
        .first()
    )

    if tag is None:
        tag = Tag(
            name=MANUAL_SERVICE_TAG_NAME,
            category=TagCategory.VISITOR,
            project_id=project_id,
            name_zh=MANUAL_SERVICE_TAG_NAME_ZH,
            description="Flag visitors who requested human assistance",
        )
        db.add(tag)
    elif tag.deleted_at is not None:
        tag.deleted_at = None
        tag.updated_at = datetime.utcnow()

    visitor_tag = (
        db.query(VisitorTag)
        .filter(
            VisitorTag.visitor_id == visitor.id,
            VisitorTag.tag_id == tag.id,
        )
        .first()
    )

    if visitor_tag is None:
        visitor_tag = VisitorTag(
            project_id=project_id,
            visitor_id=visitor.id,
            tag_id=tag.id,
        )
        db.add(visitor_tag)
    elif visitor_tag.deleted_at is not None:
        visitor_tag.deleted_at = None
        visitor_tag.updated_at = datetime.utcnow()


def _handle_manual_service_request(event: AIServiceEvent, project: Project, db: Session) -> dict:
    """Persist a manual service request as a waiting queue entry."""
    payload = ManualServiceRequestEvent.model_validate(event.payload or {})

    visitor_id = None
    if event.visitor_id:
        visitor = (
            db.query(Visitor)
            .filter(Visitor.id == event.visitor_id, Visitor.deleted_at.is_(None))
            .first()
        )
        if not visitor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Visitor not found for manual service request",
            )
        if visitor.project_id != project.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Visitor does not belong to the specified project",
            )
        visitor_id = visitor.id
        _ensure_manual_service_tag(db, project.id, visitor)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="visitor_id is required for manual service requests",
        )

    reason = payload.reason.strip()
    if not reason:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Manual service request reason cannot be empty",
        )

    channel_id = None
    channel_type = None
    session_id_raw = (payload.session_id or "").strip()
    if session_id_raw:
        parts = session_id_raw.split("@")
        if len(parts) != 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="session_id must follow {channel_id}@{channel_type} format",
            )
        channel_id = parts[0].strip() or None
        channel_type_part = parts[1].strip()
        if channel_type_part:
            try:
                channel_type = int(channel_type_part)
            except Exception as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="channel_type must be an integer",
                ) from exc

    # Validate urgency and convert to priority
    urgency = payload.urgency or QueueUrgency.NORMAL.value
    if urgency not in [u.value for u in QueueUrgency]:
        urgency = QueueUrgency.NORMAL.value
    priority = VisitorWaitingQueue.urgency_to_priority(urgency)

    # Calculate queue position
    current_queue_count = db.query(VisitorWaitingQueue).filter(
        VisitorWaitingQueue.project_id == project.id,
        VisitorWaitingQueue.status == WaitingStatus.WAITING.value,
    ).count()
    position = current_queue_count + 1

    # Create waiting queue entry
    queue_entry = VisitorWaitingQueue(
        project_id=project.id,
        visitor_id=visitor_id,
        source=QueueSource.AI_REQUEST.value,
        urgency=urgency,
        priority=priority,
        position=position,
        status=WaitingStatus.WAITING.value,
        visitor_message=reason,
        reason="AI requested manual service",
        channel_id=channel_id,
        channel_type=channel_type,
        extra_metadata=payload.metadata or {},
    )
    db.add(queue_entry)
    db.commit()
    db.refresh(queue_entry)

    logger.info(
        "Manual service request added to waiting queue from AI event",
        extra={
            "project_id": str(project.id),
            "visitor_id": str(visitor_id),
            "entry_id": str(queue_entry.id),
            "urgency": urgency,
            "priority": priority,
            "position": position,
        },
    )

    # Trigger immediate processing (fire-and-forget)
    import asyncio
    from app.tasks.process_waiting_queue import trigger_process_entry
    asyncio.create_task(trigger_process_entry(queue_entry.id))

    return {
        "entry_id": str(queue_entry.id),
        "status": queue_entry.status,
        "position": queue_entry.position,
        "priority": queue_entry.priority,
        "channel_id": queue_entry.channel_id,
        "channel_type": queue_entry.channel_type,
    }


async def _handle_visitor_info_update(event: AIServiceEvent, project: Project, db: Session) -> dict:
    """Update visitor profile based on AI-provided visitor info."""
    payload = VisitorInfoUpdateEvent.model_validate(event.payload or {})

    if event.visitor_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="visitor_id is required for visitor_info.update events",
        )

    visitor = (
        db.query(Visitor)
        .filter(Visitor.id == event.visitor_id, Visitor.deleted_at.is_(None))
        .first()
    )
    if not visitor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Visitor not found")

    if visitor.project_id != project.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Visitor does not belong to the authenticated project",
        )

    visitor_snapshot = payload.visitor or {}
    if not isinstance(visitor_snapshot, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="visitor payload must be an object",
        )

    if not visitor_snapshot:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="visitor payload cannot be empty",
        )

    visitor_data = dict(visitor_snapshot)

    session_id_raw = (payload.session_id or "").strip()
    channel_id = None
    channel_type = None
    if session_id_raw:
        parts = session_id_raw.split("@")
        if len(parts) != 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="session_id must follow {channel_id}@{channel_type} format",
            )
        channel_id = parts[0].strip() or None
        channel_type_part = parts[1].strip()
        if channel_type_part:
            try:
                channel_type = int(channel_type_part)
            except Exception as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="channel_type must be an integer",
                ) from exc

    extra_info_raw = visitor_data.pop("extra_info", None)

    changes: Dict[str, Dict[str, Any]] = {}
    custom_attributes = dict(visitor.custom_attributes or {})
    custom_attrs_modified = False

    for key, value in visitor_data.items():
        mapped_field = VISITOR_FIELD_MAP.get(key)
        if mapped_field:
            old_value = getattr(visitor, mapped_field)
            if old_value != value:
                setattr(visitor, mapped_field, value)
                changes[mapped_field] = {"old": old_value, "new": value}
        else:
            old_value = custom_attributes.get(key)
            if old_value != value:
                custom_attributes[key] = value
                custom_attrs_modified = True
                changes[f"custom.{key}"] = {"old": old_value, "new": value}

    if isinstance(extra_info_raw, dict):
        for key, value in extra_info_raw.items():
            attr_key = key
            old_value = custom_attributes.get(attr_key)
            if old_value != value:
                custom_attributes[attr_key] = value
                custom_attrs_modified = True
                changes[f"custom.extra_info.{attr_key}"] = {"old": old_value, "new": value}
    elif extra_info_raw is not None:
        attr_key = "extra_info"
        old_value = custom_attributes.get(attr_key)
        if old_value != extra_info_raw:
            custom_attributes[attr_key] = extra_info_raw
            custom_attrs_modified = True
            changes[f"custom.extra_info"] = {"old": old_value, "new": extra_info_raw}

    if custom_attrs_modified:
        visitor.custom_attributes = custom_attributes

    update_entry = VisitorCustomerUpdate(
        project_id=project.id,
        visitor_id=visitor.id,
        source=VISITOR_INFO_EVENT,
        channel_id=channel_id,
        channel_type=channel_type,
        customer_snapshot=visitor_snapshot,
        changes_applied=changes,
        extra_metadata=payload.metadata or {},
    )
    db.add(update_entry)
    db.commit()
    db.refresh(visitor)
    db.refresh(update_entry)

    await notify_visitor_profile_updated(db, visitor)

    logger.info(
        "Visitor info updated",
        extra={
            "visitor_id": str(visitor.id),
            "project_id": str(project.id),
            "updated_fields": list(changes.keys()),
            "channel_id": channel_id,
        },
    )

    return {
        "visitor_id": str(visitor.id),
        "updated_fields": list(changes.keys()),
        "update_id": str(update_entry.id),
        "channel_id": channel_id,
        "channel_type": channel_type,
    }


async def _handle_visitor_sentiment_update(event: AIServiceEvent, project: Project, db: Session) -> dict:
    """Update visitor sentiment data based on AI-provided metrics."""
    payload = VisitorSentimentUpdateEvent.model_validate(event.payload or {})

    if event.visitor_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="visitor_id is required for visitor_sentiment.update events",
        )

    visitor = (
        db.query(Visitor)
        .filter(Visitor.id == event.visitor_id, Visitor.deleted_at.is_(None))
        .first()
    )
    if not visitor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Visitor not found")

    if visitor.project_id != project.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Visitor does not belong to the authenticated project",
        )

    sentiment = payload.sentiment or {}
    if not isinstance(sentiment, dict) or not sentiment:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="sentiment payload cannot be empty",
        )

    allowed_intent = sentiment.get("intent")
    satisfaction = sentiment.get("satisfaction")
    emotion = sentiment.get("emotion")

    def _validate_score(value: Any, field: str) -> Optional[int]:
        if value is None:
            return None
        if not isinstance(value, int):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field} must be an integer between 0 and 5",
            )
        if value < 0 or value > 5:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field} must be between 0 and 5",
            )
        return value

    satisfaction = _validate_score(satisfaction, "satisfaction")
    emotion = _validate_score(emotion, "emotion")

    session_id_raw = (payload.session_id or "").strip()
    channel_id = None
    channel_type = None
    if session_id_raw:
        parts = session_id_raw.split("@")
        if len(parts) != 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="session_id must follow {channel_id}@{channel_type} format",
            )
        channel_id = parts[0].strip() or None
        channel_type_part = parts[1].strip()
        if channel_type_part:
            try:
                channel_type = int(channel_type_part)
            except Exception as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="channel_type must be an integer",
                ) from exc

    metadata_payload = dict(payload.metadata or {})
    language = str(metadata_payload.get("language") or metadata_payload.get("locale") or "en").lower()
    intent_display = localize_intent(allowed_intent, language) if allowed_intent else None
    metadata_payload["intent_code"] = allowed_intent
    metadata_payload["intent_language"] = language
    metadata_payload["intent_display"] = intent_display

    sentiment_payload = {
        "satisfaction": satisfaction,
        "emotion": emotion,
        "intent": allowed_intent,
    }

    sentiment_payload = {k: v for k, v in sentiment_payload.items() if v is not None}

    ai_insight = visitor.ai_insight
    if not ai_insight:
        ai_insight = VisitorAIInsight(
            project_id=project.id,
            visitor_id=visitor.id,
        )
        visitor.ai_insight = ai_insight
        db.add(ai_insight)

    changes: Dict[str, Dict[str, Any]] = {}

    if satisfaction is not None and ai_insight.satisfaction_score != satisfaction:
        changes["ai_insight.satisfaction_score"] = {
            "old": ai_insight.satisfaction_score,
            "new": satisfaction,
        }
        ai_insight.satisfaction_score = satisfaction

    if emotion is not None and ai_insight.emotion_score != emotion:
        changes["ai_insight.emotion_score"] = {
            "old": ai_insight.emotion_score,
            "new": emotion,
        }
        ai_insight.emotion_score = emotion

    if allowed_intent is not None and ai_insight.intent != allowed_intent:
        changes["ai_insight.intent"] = {
            "old": ai_insight.intent,
            "new": allowed_intent,
        }
        ai_insight.intent = allowed_intent

    if metadata_payload != (ai_insight.insight_metadata or {}):
        changes.setdefault("ai_insight.metadata", {
            "old": ai_insight.insight_metadata,
            "new": metadata_payload,
        })
        ai_insight.insight_metadata = metadata_payload

    visitor.updated_at = datetime.utcnow()

    log_entry = VisitorCustomerUpdate(
        project_id=project.id,
        visitor_id=visitor.id,
        source=VISITOR_SENTIMENT_EVENT,
        channel_id=channel_id,
        channel_type=channel_type,
        customer_snapshot={"sentiment": sentiment_payload},
        changes_applied=changes,
        extra_metadata=metadata_payload,
    )
    db.add(log_entry)
    db.commit()
    db.refresh(visitor)
    db.refresh(log_entry)

    await notify_visitor_profile_updated(db, visitor)

    logger.info(
        "Visitor sentiment updated",
        extra={
            "visitor_id": str(visitor.id),
            "project_id": str(project.id),
            "updated_fields": list(changes.keys()),
        },
    )

    return {
        "visitor_id": str(visitor.id),
        "updated_fields": list(changes.keys()),
        "update_id": str(log_entry.id),
        "channel_id": channel_id,
        "channel_type": channel_type,
    }


def _handle_visitor_tag(event: AIServiceEvent, project: Project, db: Session) -> dict:
    """Add tags to a visitor based on AI-provided tag items."""
    payload = VisitorTagEvent.model_validate(event.payload or {})

    if event.visitor_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="visitor_id is required for visitor_tag.add events",
        )

    visitor = (
        db.query(Visitor)
        .filter(Visitor.id == event.visitor_id, Visitor.deleted_at.is_(None))
        .first()
    )
    if not visitor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Visitor not found")

    if visitor.project_id != project.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Visitor does not belong to the authenticated project",
        )

    tag_items = payload.tags or []
    if not tag_items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="tags list cannot be empty",
        )

    added_tags = []
    skipped_tags = []

    for tag_item in tag_items:
        tag_name = tag_item.name.strip()
        tag_name_zh = tag_item.name_zh.strip() if tag_item.name_zh else None
        if not tag_name:
            continue

        # Generate tag ID and find or create the tag
        tag_id = Tag.generate_id(tag_name, TagCategory.VISITOR)
        tag = (
            db.query(Tag)
            .filter(Tag.id == tag_id, Tag.project_id == project.id)
            .first()
        )

        if tag is None:
            # Create new tag with both name and name_zh
            tag = Tag(
                name=tag_name,
                category=TagCategory.VISITOR,
                project_id=project.id,
                name_zh=tag_name_zh,
                description="Auto-created by AI service",
            )
            db.add(tag)
        else:
            # Update name_zh if provided and tag exists
            if tag.deleted_at is not None:
                # Restore soft-deleted tag
                tag.deleted_at = None
                tag.updated_at = datetime.utcnow()
            # Update name_zh if provided and different
            if tag_name_zh and tag.name_zh != tag_name_zh:
                tag.name_zh = tag_name_zh
                tag.updated_at = datetime.utcnow()

        # Check if visitor already has this tag
        visitor_tag = (
            db.query(VisitorTag)
            .filter(
                VisitorTag.visitor_id == visitor.id,
                VisitorTag.tag_id == tag.id,
            )
            .first()
        )

        # Build tag info for response
        tag_info = {"name": tag_name}
        if tag_name_zh:
            tag_info["name_zh"] = tag_name_zh

        if visitor_tag is None:
            # Create new visitor-tag association
            visitor_tag = VisitorTag(
                project_id=project.id,
                visitor_id=visitor.id,
                tag_id=tag.id,
            )
            db.add(visitor_tag)
            added_tags.append(tag_info)
        elif visitor_tag.deleted_at is not None:
            # Restore soft-deleted association
            visitor_tag.deleted_at = None
            visitor_tag.updated_at = datetime.utcnow()
            added_tags.append(tag_info)
        else:
            # Tag already exists for this visitor
            skipped_tags.append(tag_info)

    db.commit()

    logger.info(
        "Visitor tags added",
        extra={
            "visitor_id": str(visitor.id),
            "project_id": str(project.id),
            "added_tags": added_tags,
            "skipped_tags": skipped_tags,
        },
    )

    return {
        "visitor_id": str(visitor.id),
        "added_tags": added_tags,
        "skipped_tags": skipped_tags,
        "total_requested": len(tag_items),
    }


INTERNAL_AI_EVENTS_DESCRIPTION = """
**Internal endpoint for AI Service (no authentication required).**

This endpoint is designed for inter-service communication and should only be
accessible from the internal network. It does NOT require JWT authentication.

**Security Note**: This endpoint runs on a separate port (8001) and should be
protected by network-level security (firewall, VPC, etc.).

Supported event types:

* `manual_service.request` — create a manual service request record.
* `visitor_info.update` — update visitor profile using provided visitor data.
* `visitor_sentiment.update` — update visitor sentiment metrics.
* `visitor_tag.add` — add tags to a visitor.

**Required Fields**:
- `event_type`: The type of event (see above)
- `visitor_id`: The UUID of the visitor (required - used to determine the project)
- `payload`: Event-specific payload

**Note**: The project is automatically determined from the visitor's project association.
You do not need to provide `project_id` in the request.

**Example Request**:

```json
{
  "event_type": "manual_service.request",
  "visitor_id": "ffffffff-gggg-hhhh-iiii-jjjjjjjjjjjj",
  "payload": {
    "reason": "User explicitly requested to talk to a human agent.",
    "urgency": "high",
    "channel": "phone",
    "notification_type": "sms",
    "session_id": "ffffffff-gggg-hhhh-iiii-jjjjjjjjjjjj-vtr@251",
    "metadata": {
      "conversation_id": "conv-12345"
    }
  }
}
```
"""


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest AI-generated events (Internal - No Auth)",
    description=INTERNAL_AI_EVENTS_DESCRIPTION,
)
async def ingest_ai_event_internal(
    event: AIServiceEvent,
    db: Session = Depends(get_db),
) -> dict:
    """
    Ingest events from AI service (internal endpoint, no authentication required).

    This endpoint is designed for the AI Service to send events without JWT authentication.
    The project is automatically determined from the visitor's project association.

    Security: This endpoint should only be accessible from the internal network.
    """
    # Validate visitor_id is provided (required to determine project)
    if not event.visitor_id:
        logger.error("Internal AI event missing visitor_id", extra={"event_type": event.event_type})
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="visitor_id is required in event payload for internal calls",
        )

    # Query visitor to get project
    visitor = (
        db.query(Visitor)
        .filter(Visitor.id == event.visitor_id, Visitor.deleted_at.is_(None))
        .first()
    )
    if not visitor:
        logger.error(
            "Visitor not found for internal AI event",
            extra={"visitor_id": str(event.visitor_id), "event_type": event.event_type},
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Visitor not found: {event.visitor_id}",
        )

    # Get project from visitor
    project = (
        db.query(Project)
        .filter(Project.id == visitor.project_id, Project.deleted_at.is_(None))
        .first()
    )
    if not project:
        logger.error(
            "Project not found for visitor",
            extra={"visitor_id": str(visitor.id), "project_id": str(visitor.project_id), "event_type": event.event_type},
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project not found for visitor: {visitor.project_id}",
        )

    event_type = event.event_type.strip().lower()

    logger.info(
        "Processing internal AI event",
        extra={
            "event_type": event_type,
            "project_id": str(project.id),
            "visitor_id": str(event.visitor_id) if event.visitor_id else None,
        },
    )

    # Reuse existing event handlers
    if event_type == MANUAL_SERVICE_EVENT:
        result = _handle_manual_service_request(event, project, db)
        return {"event_type": event_type, "result": result}

    if event_type == VISITOR_INFO_EVENT:
        result = await _handle_visitor_info_update(event, project, db)
        return {"event_type": event_type, "result": result}

    if event_type == VISITOR_SENTIMENT_EVENT:
        result = await _handle_visitor_sentiment_update(event, project, db)
        return {"event_type": event_type, "result": result}

    if event_type == VISITOR_TAG_EVENT:
        result = _handle_visitor_tag(event, project, db)
        return {"event_type": event_type, "result": result}

    logger.warning(
        "Unsupported AI event type received on internal endpoint",
        extra={"event_type": event.event_type},
    )
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Unsupported AI event_type: {event.event_type}",
    )

