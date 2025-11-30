"""Kafka consumer that forwards AI responses to WuKongIM.

Consumes tgo.ai.responses and forwards start/content/end events and final message to WuKongIM.
"""
from __future__ import annotations

import asyncio
import json
from app.core.logging import get_logger
from typing import Any, Dict, Optional

from app.core.config import settings
from app.services.wukongim_client import WuKongIMClient

logger = get_logger("consumers.wukong_forwarder")

try:
    from aiokafka import AIOKafkaConsumer  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    AIOKafkaConsumer = None  # type: ignore

_consumer_task: Optional[asyncio.Task] = None
_stop_event = asyncio.Event()

wukong_client = WuKongIMClient()


async def _handle_incoming(evt: Dict[str, Any]) -> None:
    """Handle messages from tgo.messages.incoming.

    Forward only when platform_type exists and is not 'website'.
    """
    platform_type: Optional[str] = evt.get("platform_type")
    if platform_type and platform_type != "website":
        try:
            print("recv incoming...",evt)
            await wukong_client.send_text_message(
                from_uid=str(evt.get("from_uid") or ""),
                channel_id=str(evt.get("channel_id") or ""),
                channel_type=int(evt.get("channel_type") or 0),
                content=str(evt.get("message_text") or ""),
                extra=evt.get("extra") or {},
                client_msg_no=evt.get("client_msg_no"),
            )
            logger.info(
                "Forwarded incoming message to WuKongIM",
                extra={
                    "platform_type": platform_type,
                    "channel_id": evt.get("channel_id"),
                },
            )
        except Exception as exc:  # pragma: no cover
            logger.error(
                "WuKong forward (incoming) error: %s", exc,
                extra={"evt_keys": list(evt.keys())},
            )
    else:
        logger.debug(
            "Skipping incoming message forwarding",
            extra={"platform_type": platform_type},
        )


async def _handle_ai_response(evt: Dict[str, Any]) -> None:
    """Handle messages from tgo.ai.responses (streaming AI events)."""
    session_id: str = str(evt.get("session_id") or "")
    client_msg_no: Optional[str] = evt.get("client_msg_no")
    recv_client_msg_no: Optional[str] = evt.get("recv_client_msg_no")
    event_type: str = str(evt.get("event_type") or "")
    data: Dict[str, Any] = evt.get("data") or {}
    from_uid: Optional[str] = evt.get("from_uid") 
    channel_id: Optional[str] = evt.get("channel_id")
    channel_type: int = evt.get("channel_type") or 0

    logger.info(
        f"WuKong forwarder: Handling AI response {event_type}",
    )

    print("evt---->",evt)

    try:
        if event_type == "team_run_started":
            await wukong_client.send_event(
                channel_id=channel_id,
                channel_type=channel_type,
                event_type="___TextMessageStart",
                data='{"type":100}',
                client_msg_no=recv_client_msg_no,
                from_uid=from_uid,
                force=True,
            )
        elif event_type == "team_run_content" :
            chunk_text = data.get("content") 
            if chunk_text is not None:
                await wukong_client.send_event(
                    channel_id=channel_id,
                    channel_type=channel_type,
                    event_type="___TextMessageContent",
                    data=str(chunk_text),
                    client_msg_no=recv_client_msg_no,
                    from_uid=from_uid,
                )
        elif event_type == "workflow_completed":
            await wukong_client.send_event(
                channel_id=channel_id,
                channel_type=channel_type,
                data="",
                event_type="___TextMessageEnd",
                client_msg_no=recv_client_msg_no,
                from_uid=from_uid,
            )
    except Exception as exc:  # pragma: no cover
        logger.error("WuKong forward (AI) error: %s", exc, extra={"session_id": session_id})


async def _run_consumer() -> None:
    if AIOKafkaConsumer is None:
        logger.warning("aiokafka not installed; WuKong forwarder consumer disabled")
        return

    topics = [settings.KAFKA_TOPIC_AI_RESPONSES, settings.KAFKA_TOPIC_INCOMING_MESSAGES]

    consumer = AIOKafkaConsumer(
        *topics,
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        group_id=settings.KAFKA_CONSUMER_GROUP_WUKONG_FORWARDER,
        enable_auto_commit=True,
        auto_offset_reset="earliest",  # ensure consumption of existing msgs when no committed offsets
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    )

    await consumer.start()
    logger.info("WuKong forwarder consumer started", extra={"topics": topics})
    try:
        async for msg in consumer:
            if _stop_event.is_set():
                break

            evt: Dict[str, Any] = msg.value or {}
            topic: Optional[str] = getattr(msg, "topic", None)

            if topic == settings.KAFKA_TOPIC_INCOMING_MESSAGES:
                await _handle_incoming(evt)
                continue

            await _handle_ai_response(evt)
    finally:
        await consumer.stop()
        logger.info("WuKong forwarder consumer stopped")


async def start_wukong_forwarder() -> None:
    global _consumer_task
    if _consumer_task and not _consumer_task.done():
        return
    _stop_event.clear()
    _consumer_task = asyncio.create_task(_run_consumer())


async def stop_wukong_forwarder() -> None:
    _stop_event.set()
    if _consumer_task:
        try:
            await asyncio.wait_for(_consumer_task, timeout=5)
        except Exception:
            _consumer_task.cancel()

