"""WuKongIM webhook endpoints."""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models import Platform, Staff, Visitor, ChannelMember
from app.models.staff import StaffStatus
from app.services.ai_client import AIServiceClient
from app.services.wukongim_client import WuKongIMClient
from app.services.visitor_notifications import notify_visitor_profile_updated
from app.utils.encoding import parse_visitor_channel_id
from app.utils.const import MEMBER_TYPE_VISITOR
import httpx

logger = logging.getLogger("webhooks.wukongim")

router = APIRouter(tags=["WuKongIM Webhook"], prefix="/integrations/wukongim")

ai_client = AIServiceClient()
wukong_client = WuKongIMClient()

STAFF_UID_SUFFIX = "-staff"
VISITOR_UID_SUFFIX = "-vtr"
STAFF_API_CACHE_TTL = 300.0
STAFF_API_CACHE_MAX = 1024
STREAM_EVENT_FALLBACK = "ai.stream"

STAFF_API_CACHE: Dict[str, Tuple[str, float]] = {}
STAFF_API_CACHE_LOCK = asyncio.Lock()


def _resolve_messages(payload: Any) -> List[Dict[str, Any]]:
    """Normalize msg.notify payload into a list of message dictionaries."""
    if isinstance(payload, list):
        candidates = payload
    elif isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, list):
            candidates = data
        elif isinstance(data, dict):
            candidates = [data]
        elif payload.get("payload"):
            candidates = [payload]
        else:
            return []
    else:
        return []

    return [msg for msg in candidates if isinstance(msg, dict)]


def _normalize_status_events(payload: Any) -> List[Dict[str, Any]]:
    """Normalize user.onlinestatus payload into a list of event dicts."""
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]

    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if isinstance(data, dict):
            return [data]
        # Some payloads may place the record at top-level
        if any(key in payload for key in ("uid", "user_id", "userId", "userID")):
            return [payload]

    return []


def _extract_uid(entry: Dict[str, Any]) -> Optional[str]:
    """Extract UID from a status entry."""
    for key in ("uid", "user_id", "userId", "userID", "id"):
        value = entry.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _parse_online_flag(entry: Dict[str, Any]) -> Optional[bool]:
    """Derive online/offline flag from a status entry."""

    def _convert(value: Any) -> Optional[bool]:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"1", "true", "online", "login", "connected", "up"}:
                return True
            if lowered in {"0", "false", "offline", "logout", "disconnected", "down"}:
                return False
        return None

    if "user_total_online_devices" in entry:
        try:
            total = int(entry["user_total_online_devices"])
            return total > 0
        except Exception:
            pass

    if "device_online_count" in entry:
        try:
            device_count = int(entry["device_online_count"])
            return device_count > 0
        except Exception:
            pass

    for key in ("status", "state", "online", "is_online", "isOnline"):
        if key in entry:
            flag = _convert(entry[key])
            if flag is not None:
                return flag

    action = entry.get("action")
    if isinstance(action, str):
        lowered = action.lower()
        if lowered == "login":
            return True
        if lowered == "logout":
            return False

    event_state = entry.get("event")
    if isinstance(event_state, str):
        lowered = event_state.lower()
        if lowered == "online":
            return True
        if lowered == "offline":
            return False

    if "client_count" in entry:
        try:
            count = int(entry["client_count"])
            return count > 0
        except Exception:
            pass

    return None


async def _process_msg_notify(messages_payload: Any) -> None:
    """Background task entrypoint for processing msg.notify events."""
    db: Session = SessionLocal()
    try:
        await _handle_msg_notify(messages_payload, db)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Failed to process WuKongIM message batch: %s", exc)
    finally:
        db.close()


async def _handle_msg_notify(messages_payload: Any, db: Session) -> None:
    if not settings.WUKONGIM_ENABLED:
        logger.debug("WuKongIM integration disabled; ignoring webhook event")
        return

    messages = _resolve_messages(messages_payload)
    if not messages:
        logger.debug("Empty WuKongIM msg.notify payload")
        return
    # Collect visitor messages in customer service channels and forward in batches per platform
    try:
        platform_groups: Dict[str, List[Dict[str, Any]]] = {}
        visitor_cache: Dict[UUID, Optional[Visitor]] = {}
        for m in messages:
            try:
                if m.get("channel_type") != 251:
                    continue
                ch_id = str(m.get("channel_id") or "")
                visitor_uuid = parse_visitor_channel_id(ch_id)
                if visitor_uuid in visitor_cache:
                    visitor_obj = visitor_cache[visitor_uuid]
                else:
                    visitor_obj = (
                        db.query(Visitor)
                        .filter(
                            Visitor.id == visitor_uuid,
                            Visitor.deleted_at.is_(None),
                        )
                        .first()
                    )
                    visitor_cache[visitor_uuid] = visitor_obj

                if not visitor_obj:
                    logger.error("Visitor not found for channel_id", extra={"channel_id": ch_id})
                    continue
                pid = visitor_obj.platform_id
                if not pid:
                    logger.error("Visitor missing platform_id", extra={"visitor_id": str(visitor_uuid)})
                    continue
                pid_str = str(pid)

                # Add platform_open_id to the message
                enriched_msg = {
                    **m,
                    "platform_open_id": visitor_obj.platform_open_id,
                }
                platform_groups.setdefault(pid_str, []).append(enriched_msg)
            except Exception:
                logger.error("Error evaluating message for platform forwarding", extra={"message": m})
                continue

        # Forward batches per platform
        if platform_groups:
            async with httpx.AsyncClient(timeout=settings.PLATFORM_SERVICE_TIMEOUT) as client:
                for pid_str, msgs in platform_groups.items():
                    platform = None
                    try:
                        pid = UUID(pid_str)
                        platform = (
                            db.query(Platform)
                            .filter(
                                Platform.id == pid,
                                Platform.deleted_at.is_(None),
                                Platform.is_active.is_(True),
                            )
                            .first()
                        )
                    except Exception:
                        logger.error("Invalid platform_id while grouping messages", extra={"platform_id": pid_str})

                    if not platform:
                        logger.warning("Platform not found or inactive; skipping forwarding batch", extra={"platform_id": pid_str})
                        continue

                    target_url = f"{settings.PLATFORM_SERVICE_URL.rstrip('/')}/v1/platforms/callback/{platform.api_key}?event=msg.notify&source=wukongim"

                    try:
                        await client.post(target_url, json=msgs)
                    except httpx.TimeoutException:
                        logger.error("Platform Service timeout while forwarding batch", extra={"url": target_url, "platform_id": pid_str})
                    except httpx.RequestError as exc:
                        logger.error("Platform Service request error: %s", exc, extra={"url": target_url, "platform_id": pid_str})
    except Exception as exc:
        logger.error("Unexpected error while batch-forwarding to Platform Service: %s", exc)



async def _process_user_online_status(status_payload: Any) -> None:
    """Entry point for handling user.onlinestatus events."""
    db: Session = SessionLocal()
    try:
        await _handle_user_online_status(status_payload, db)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Failed to process WuKongIM user.onlinestatus event: %s", exc)
    finally:
        db.close()


async def _handle_user_online_status(events_payload: Any, db: Session) -> None:
    if not settings.WUKONGIM_ENABLED:
        logger.debug("WuKongIM integration disabled; ignoring online status event")
        return
    events = _normalize_status_events(events_payload)
    if not events and isinstance(events_payload, list):
        # Handle compact list format like ["uid-deviceFlag-onlineFlag-connectionId-deviceOnlineCount-totalOnlineCount"]
        normalized = []
        for item in events_payload:
            if not isinstance(item, str):
                continue
            parts = item.rsplit("-", 5)
            if len(parts) != 6:
                continue
            uid_part, device_flag, online_flag, connection_id, device_online_str, total_online_str = parts

            def _safe_int(value: str) -> Optional[int]:
                try:
                    return int(value)
                except (TypeError, ValueError):
                    return None

            device_online_count = _safe_int(device_online_str)
            user_total_devices = _safe_int(total_online_str)

            normalized.append({
                "uid": uid_part,
                "device_flag": device_flag,
                "connection_id": connection_id,
                "status": online_flag,
                "device_online_count": device_online_count,
                "user_total_online_devices": user_total_devices,
            })
        events = normalized

    if not events:
        logger.debug("WuKongIM user.onlinestatus payload empty or unsupported format")
        return

    now = datetime.utcnow()
    dirty = False
    visitor_updates = 0
    staff_updates = 0
    channel_events: List[Dict[str, Any]] = []
    visitors_to_notify: Dict[str, Visitor] = {}

    for entry in events:
        uid_raw = _extract_uid(entry)
        if not uid_raw:
            logger.warning("WuKongIM user.onlinestatus entry missing uid", extra={"entry": entry})
            continue

        is_staff = False
        is_visitor = False
        uid_str = uid_raw
        if uid_raw.endswith(STAFF_UID_SUFFIX):
            is_staff = True
            uid_str = uid_raw[:-len(STAFF_UID_SUFFIX)]
        if uid_str.endswith(VISITOR_UID_SUFFIX):
            is_visitor = True
            uid_str = uid_str[:-len(VISITOR_UID_SUFFIX)]

        try:
            uid = UUID(uid_str)
        except Exception:
            logger.warning("WuKongIM user.onlinestatus entry contains invalid UID", extra={"uid": uid_raw})
            continue

        is_online = _parse_online_flag(entry)
        if is_online is None:
            logger.warning(
                "WuKongIM user.onlinestatus entry missing status indicator",
                extra={"uid": uid_raw, "entry": entry},
            )
            continue

        if is_staff:
            staff = (
                db.query(Staff)
                .filter(Staff.id == uid, Staff.deleted_at.is_(None))
                .first()
            )
            if not staff:
                logger.debug("Staff not found for online status update", extra={"staff_id": uid_str})
                continue

            desired_status = StaffStatus.ONLINE.value if is_online else StaffStatus.OFFLINE.value
            if staff.status != desired_status:
                staff.status = desired_status
                dirty = True
                staff_updates += 1
        elif is_visitor:
            visitor = (
                db.query(Visitor)
                .filter(Visitor.id == uid, Visitor.deleted_at.is_(None))
                .first()
            )
            if not visitor:
                logger.debug("Visitor not found for online status update", extra={"visitor_id": uid_str})
                continue

            record_changed = False
            if visitor.is_online != is_online:
                visitor.is_online = is_online
                record_changed = True

            if is_online:
                visitor.last_visit_time = now
                record_changed = True
            else:
                visitor.last_offline_time = now
                record_changed = True

            if record_changed:
                dirty = True
                visitor_updates += 1
                visitors_to_notify[str(visitor.id)] = visitor
                memberships = (
                    db.query(ChannelMember.channel_id, ChannelMember.channel_type)
                    .filter(
                        ChannelMember.member_id == visitor.id,
                        ChannelMember.member_type == MEMBER_TYPE_VISITOR,
                        ChannelMember.deleted_at.is_(None),
                    )
                    .all()
                )

                if memberships:
                    event_type = "visitor.online" if is_online else "visitor.offline"
                    event_payload = {
                        "visitor_id": str(visitor.id),
                        "status": "online" if is_online else "offline",
                        "is_online": is_online,
                        "timestamp": now.isoformat() + "Z",
                        "device_flag": entry.get("device_flag"),
                        "connection_id": entry.get("connection_id"),
                        "device_online_count": entry.get("device_online_count"),
                        "user_total_online_devices": entry.get("user_total_online_devices"),
                    }
                    for channel_id, channel_type in memberships:
                        payload_with_channel = {
                            **event_payload,
                            "channel_id": channel_id,
                            "channel_type": channel_type,
                        }
                        client_msg_no = f"presence-{visitor.id}-{uuid.uuid4().hex}"
                        channel_events.append(
                            {
                                "channel_id": channel_id,
                                "channel_type": channel_type,
                                "event_type": event_type,
                                "data": payload_with_channel,
                                "client_msg_no": client_msg_no,
                                "from_uid": str(visitor.id),
                            }
                        )

    if not dirty:
        logger.debug("WuKongIM user.onlinestatus processed with no state changes")
        return

    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("Failed to commit WuKongIM user.onlinestatus updates: %s", exc)
        return

    for evt in channel_events:
        try:
            await wukong_client.send_event(
                channel_id=evt["channel_id"],
                channel_type=evt["channel_type"],
                event_type=evt["event_type"],
                data=evt["data"],
                client_msg_no=evt.get("client_msg_no"),
                from_uid=evt.get("from_uid"),
                force=False,
            )
        except Exception as exc:
            logger.error(
                "Failed to dispatch visitor presence event",
                extra={
                    "channel_id": evt["channel_id"],
                    "event_type": evt["event_type"],
                    "error": str(exc),
                },
            )

    logger.info(
        "WuKongIM user.onlinestatus applied",
        extra={"visitor_updates": visitor_updates, "staff_updates": staff_updates},
    )

    if visitors_to_notify:
        notify_results = await asyncio.gather(
            *[
                notify_visitor_profile_updated(db, visitor)
                for visitor in visitors_to_notify.values()
            ],
            return_exceptions=True,
        )
        for result in notify_results:
            if isinstance(result, Exception):
                logger.error(
                    "Failed to dispatch visitor profile update notification after status change",
                    exc_info=result,
                )


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def wukongim_webhook(request: Request, background_tasks: BackgroundTasks) -> Dict[str, Any]:
    """Handle WuKongIM webhook callbacks."""

    event = request.query_params.get("event")
    logger.info("WuKongIM webhook received", extra={"event": event})

    if event == "user.onlinestatus":
        try:
            body = await request.json()
        except Exception as exc:
            logger.error("Failed to parse WuKongIM user.onlinestatus payload: %s", exc)
            return {"code": 400, "message": "invalid payload"}
        await _process_user_online_status(body)

    return {"code": 0, "message": "ok"}
