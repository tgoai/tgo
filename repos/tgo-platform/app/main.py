from __future__ import annotations
import asyncio
import uuid
import logging
from contextlib import asynccontextmanager, suppress
from fastapi import FastAPI, Request
from app.api.error_utils import register_exception_handlers

from app.core.config import settings

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s:%(name)s:%(message)s",
)

from app.api.v1 import health, messages
from app.api.v1 import platforms as platforms_v1
from app.api.v1 import callbacks as callbacks_v1
from app.infra.http import HttpxTgoApiClient
from app.infra.sse import DefaultSSEManager
from app.db.base import SessionLocal
from app.domain.services.normalizer import normalizer
from app.domain.services.listeners import EmailChannelListener
from app.domain.services.listeners.wecom_listener import WeComChannelListener
from app.domain.services.listeners.wukongim_listener import WuKongIMChannelListener
from app.domain.services.listeners.feishu_listener import FeishuChannelListener
from app.domain.services.listeners.dingtalk_listener import DingTalkChannelListener
from app.domain.services.listeners.telegram_listener import TelegramChannelListener



@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create shared clients
    app.state.tgo_api_client = HttpxTgoApiClient(settings.api_base_url, timeout=settings.request_timeout_seconds)
    app.state.sse_manager = DefaultSSEManager()

    # Start multi-tenant Email listener supervisor (dynamic; safe if no email platforms exist)
    app.state.email_listener = EmailChannelListener(
        session_factory=SessionLocal,
        normalizer=normalizer,
        tgo_api_client=app.state.tgo_api_client,
        sse_manager=app.state.sse_manager,
    )
    app.state.email_listener_task = asyncio.create_task(app.state.email_listener.start())

    # Start WeCom consumer (processes pending wecom_inbox messages)
    app.state.wecom_listener = WeComChannelListener(
        session_factory=SessionLocal,
        normalizer=normalizer,
        tgo_api_client=app.state.tgo_api_client,
        sse_manager=app.state.sse_manager,
    )
    # Start WuKongIM consumer (processes pending wukongim_inbox messages)
    app.state.wukongim_listener = WuKongIMChannelListener(
        session_factory=SessionLocal,
        normalizer=normalizer,
        tgo_api_client=app.state.tgo_api_client,
        sse_manager=app.state.sse_manager,
    )

    # Start Feishu Bot consumer (processes pending feishu_inbox messages)
    app.state.feishu_listener = FeishuChannelListener(
        session_factory=SessionLocal,
        normalizer=normalizer,
        tgo_api_client=app.state.tgo_api_client,
        sse_manager=app.state.sse_manager,
    )

    # Start DingTalk Bot consumer (processes pending dingtalk_inbox messages)
    app.state.dingtalk_listener = DingTalkChannelListener(
        session_factory=SessionLocal,
        normalizer=normalizer,
        tgo_api_client=app.state.tgo_api_client,
        sse_manager=app.state.sse_manager,
    )

    # Start Telegram Bot consumer (uses getUpdates polling)
    app.state.telegram_listener = TelegramChannelListener(
        session_factory=SessionLocal,
        normalizer=normalizer,
        tgo_api_client=app.state.tgo_api_client,
        sse_manager=app.state.sse_manager,
    )

    app.state.wukongim_listener_task = asyncio.create_task(app.state.wukongim_listener.start())
    app.state.feishu_listener_task = asyncio.create_task(app.state.feishu_listener.start())
    app.state.dingtalk_listener_task = asyncio.create_task(app.state.dingtalk_listener.start())
    app.state.telegram_listener_task = asyncio.create_task(app.state.telegram_listener.start())
    app.state.wecom_listener_task = asyncio.create_task(app.state.wecom_listener.start())


    try:
        yield
    finally:
        # Shutdown: stop listeners and close http client
        await app.state.email_listener.stop()
        await app.state.wecom_listener.stop()
        await app.state.wukongim_listener.stop()
        await app.state.feishu_listener.stop()
        await app.state.dingtalk_listener.stop()
        await app.state.telegram_listener.stop()
        app.state.email_listener_task.cancel()
        app.state.wecom_listener_task.cancel()
        app.state.wukongim_listener_task.cancel()
        app.state.feishu_listener_task.cancel()
        app.state.dingtalk_listener_task.cancel()
        app.state.telegram_listener_task.cancel()
        with suppress(asyncio.CancelledError):
            await app.state.email_listener_task
        with suppress(asyncio.CancelledError):
            await app.state.wecom_listener_task
        with suppress(asyncio.CancelledError):
            await app.state.wukongim_listener_task
        with suppress(asyncio.CancelledError):
            await app.state.feishu_listener_task
        with suppress(asyncio.CancelledError):
            await app.state.dingtalk_listener_task
        with suppress(asyncio.CancelledError):
            await app.state.telegram_listener_task
        await app.state.tgo_api_client.aclose()

app = FastAPI(lifespan=lifespan, docs_url="/v1/docs", redoc_url="/v1/redoc")

# Register global exception handlers and request ID middleware
register_exception_handlers(app)

@app.middleware("http")
async def add_request_id(request: Request, call_next):
    rid = request.headers.get("x-request-id") or str(uuid.uuid4())
    request.state.request_id = rid
    response = await call_next(request)
    response.headers["x-request-id"] = rid
    return response





app.include_router(health.router, tags=["health"])
app.include_router(messages.router, tags=["messages"])
app.include_router(platforms_v1.router, tags=["platforms"])
app.include_router(callbacks_v1.router, tags=["callbacks"])

