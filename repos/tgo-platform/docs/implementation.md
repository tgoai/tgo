## tgo-platform Implementation Guide (Python/FastAPI)

本指南将 docs/architecture.md 的架构设计映射为可落地的 Python 3.11+ 实现方案，覆盖技术栈、目录结构、核心组件抽象、数据库与配置、接口与 SSE 实现、依赖与版本建议。

---

### 1) 技术栈说明（依赖与选型）
- 语言与运行时
  - Python: 3.11+
- Web 框架
  - FastAPI: ^0.110（高性能 ASGI、类型友好、原生 async/await）
  - Uvicorn: ^0.27（ASGI 服务器）
- ORM 与数据库
  - SQLAlchemy: >=2.0,<3.0（2.x 新式 API：DeclarativeBase、Mapped、mapped_column）
  - asyncpg: ^0.29（PostgreSQL 异步驱动）
  - 参考：
    - SQLAlchemy asyncio: https://docs.sqlalchemy.org/en/latest/orm/extensions/asyncio.html
    - Declarative + mapped_column: https://docs.sqlalchemy.org/en/latest/orm/declarative_tables.html
- 配置管理
  - pydantic: ^2.7
  - pydantic-settings: ^2.3（BaseSettings、分层/多源配置）
  - 参考：Pydantic Settings v2 文档 https://docs.pydantic.dev/latest/concepts/pydantic_settings/
- HTTP 客户端
  - httpx: ^0.27（异步 HTTP/SSE 拉流）
- SSE 实现
  - 首选 sse-starlette: ^1.6（EventSourceResponse），或使用 FastAPI 的 StreamingResponse 手动封装 SSE 帧
- 其它
  - Poetry（依赖与打包）：1.7+

选型理由
- 全异步链路：渠道监听 → tgo-api（SSE）→ 平台适配，需 async/await 优先（FastAPI、httpx、SQLAlchemy asyncio）。
- SQLAlchemy 2.x 新 API 与类型注解良好契合，降低心智负担并提升可维护性。
- pydantic v2 与 Settings 2.x 提供强大的分层配置、dotenv、Secrets、云密钥管理扩展能力。

---

### 2) 项目结构（参考 FastAPI 最佳实践）
```
app/
  api/
    __init__.py
    routes/
      __init__.py
      health.py
      messages.py            # 对外 API（可选）
  core/
    __init__.py
    config.py                # Pydantic Settings
    logging.py               # 结构化日志/trace id 注入
  db/
    __init__.py
    base.py                  # DeclarativeBase、engine、session
    models.py                # ORM 实体
    schemas.py               # Pydantic DTO（如需）
  domain/
    __init__.py
    ports.py                 # 核心接口/Protocol/ABC
    entities.py              # 领域模型（可选）
    services/
      __init__.py
      dispatcher.py          # 调用 tgo-api 客户端
      sse_manager.py         # SSE 连接管理与事件聚合
      normalizer.py          # 消息标准化
      listeners/
        __init__.py
        smtp_listener.py     # SMTP/IMAP/POP3 封装（占位）
        webhook_listener.py  # Webhook 入口
      adapters/
        __init__.py
        base.py              # 平台适配基类/策略
        wecom.py
        whatsapp.py
        telegram.py
        email.py
  infra/
    __init__.py
    http.py                  # httpx 客户端工厂、重试/超时
    sse.py                   # sse-starlette 或 StreamingResponse 工具
    tracing.py               # request_id/correlation_id
  main.py                    # FastAPI 应用入口

pyproject.toml
.env.example
```

---

### 3) 核心组件设计

#### 3.1 Channel Listener（渠道监听器）
职责：从 SMTP/Webhook 等来源接入消息，去重/幂等，转交给 Message Normalizer。
关键点：异步回调、背压控制、幂等键（Message-ID、事件 id）。

接口抽象：
```python
from typing import Protocol, AsyncIterator

class ChannelListener(Protocol):
    async def listen(self) -> AsyncIterator[dict]:
        """异步产出原始消息事件（字典或原始协议对象）。"""
```

#### 3.2 Message Normalizer（消息标准化）
职责：将多渠道原始消息映射为统一消息模型。
```python
from pydantic import BaseModel

class NormalizedMessage(BaseModel):
    source: str
    from_uid: str
    channel_id: str
    channel_type: int  # 1=personal, 2=group
    content: str
    extra: dict | None = None
```
```python
class MessageNormalizer(Protocol):
    async def normalize(self, raw: dict) -> NormalizedMessage: ...
```

#### 3.3 Dispatcher/Router（路由触发器）
职责：调用 tgo-api /v1/wukongim/messages/send-stream 建立 SSE，产出事件流。
```python
from typing import AsyncIterator

class SendStreamRequest(BaseModel):
    api_key: str
    message: str
    channel_id: str
    channel_type: int
    from_uid: str
    extra: dict | None = None
    timeout_seconds: int | None = 120

class TgoApiClient(Protocol):
    async def send_stream(self, req: SendStreamRequest) -> AsyncIterator[bytes]:
        """返回 SSE 原始帧字节流（逐行/逐事件）。"""
```

实现要点（httpx）：
- 使用 AsyncClient.stream("POST", url, json=..., timeout=..., headers=...)
- 逐行读取（aiter_lines()），组合为 SSE 事件（event:, data:, id:, retry:）。

#### 3.4 SSE Manager（连接管理与聚合）
职责：
- 解析 tgo-api 的 SSE：connected|event|error|disconnected
- 为“非流式平台”聚合内容事件（team_member_content、team_run_content 等），在完成事件后输出一次性消息
- 超时/中止、错误回退
```python
from typing import AsyncIterator

class StreamEvent(BaseModel):
    event: str  # connected/event/error/disconnected
    payload: dict | None = None

class SSEManager(Protocol):
    async def stream_events(self, frames: AsyncIterator[bytes]) -> AsyncIterator[StreamEvent]:
        ...

    async def aggregate(self, events: AsyncIterator[StreamEvent]) -> dict:
        """将 event 序列聚合成最终文本/富内容。"""
```

#### 3.5 Platform Adapters（平台适配器，策略模式）
职责：根据平台能力（是否支持流式）选择直出或聚合后发送。
```python
from abc import ABC, abstractmethod

class PlatformAdapter(ABC):
    supports_stream: bool = False

    @abstractmethod
    async def send_incremental(self, ev: StreamEvent) -> None: ...

    @abstractmethod
    async def send_final(self, content: dict) -> None: ...
```
策略选择：supports_stream=True → 按事件实时输出；否则缓存到完成事件后 send_final。

#### 3.6 Database Models（SQLAlchemy 2.x 声明式）
- platforms：第三方平台配置与能力（多租户、软删除、密钥）

```python
import uuid
from datetime import datetime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func

class Base(DeclarativeBase):
    pass

class Platform(Base):
    """第三方平台模型：多租户隔离、软删除、平台密钥与配置。"""
    __tablename__ = "pt_platforms"

    # 主键 UUID
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # 所属项目（租户）
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)

    # 平台标识
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)

    # 可选配置（平台特定）
    config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # 启用状态
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    # 审计字段
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # 平台级 API 密钥（可选）
    api_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
```

#### 3.7 Configuration（Pydantic Settings 2.x）
```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    api_base_url: str  # tgo-api base url


    database_url: str    # e.g. postgresql+asyncpg://user:pass@host:5432/db
    sse_backpressure_limit: int = 1000
    request_timeout_seconds: int = 120
```
可按需扩展：Secrets、dotenv、优先级自定义、pyproject.toml 等（详见官方文档链接）。

---

### 4) 接口抽象与伪代码（关键方法）

渠道监听（Webhook 示例）
```python
from fastapi import APIRouter, Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession
router = APIRouter()

@router.post("/webhooks/inbound")
async def inbound(req: Request, db: AsyncSession = Depends(get_db)):
    raw = await req.json()
    norm = await normalizer.normalize(raw)
    await orchestrate(norm, db)
    return {"ok": True}
```

编排与分发
```python
import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

async def orchestrate(msg: NormalizedMessage, db: AsyncSession) -> None:
    """端到端编排：查库取平台配置（含 api_key）→ 调用 tgo-api（SSE）→ 平台适配输出。"""
    for attempt in range(3):  # 简单重试
        try:
            # 1) 查询平台配置（含 api_key）
            stmt = (
                select(Platform)
                .where(
                    Platform.project_id == msg.extra.get("project_id"),
                    Platform.type == msg.extra.get("platform_type"),
                    Platform.is_active.is_(True),
                )
                .limit(1)
            )
            platform = await db.scalar(stmt)
            if not platform or not platform.api_key:
                raise RuntimeError("platform not configured or missing api_key")

            # 2) 调用 tgo-api 建立 SSE
            req = SendStreamRequest(
                api_key=platform.api_key,  # 从数据库获取
                message=msg.content,
                channel_id=msg.channel_id,
                channel_type=msg.channel_type,
                from_uid=msg.from_uid,
                extra=msg.extra,
                timeout_seconds=settings.request_timeout_seconds,
            )
            frames = tgo_api_client.send_stream(req)
            events = sse_manager.stream_events(frames)

            # 3) 平台适配器（将 api_key 传入以便平台侧鉴权）
            adapter = select_adapter_for_target(msg, credentials=platform.api_key)

            # 4) 输出策略
            if adapter.supports_stream:
                async for ev in events:
                    await adapter.send_incremental(ev)
            else:
                final = await sse_manager.aggregate(events)
                await adapter.send_final(final)
            return
        except Exception:
            if attempt == 2:
                raise
            await asyncio.sleep(2 ** attempt)  # 指数退避后重试

```

tgo-api 客户端（httpx）
```python
import httpx
from contextlib import asynccontextmanager

class HttpxTgoApiClient:
    def __init__(self, base_url: str):
        self._client = httpx.AsyncClient(base_url=base_url, timeout=None)

    async def send_stream(self, req: SendStreamRequest):
        url = "/v1/wukongim/messages/send-stream"
        async with self._client.stream("POST", url, json=req.model_dump()) as r:
            r.raise_for_status()
            async for line in r.aiter_lines():
                if line:  # 逐行原样透传，交由 SSEManager 解析
                    yield line.encode()
```

SSE 解析与聚合（示意）
```python
class DefaultSSEManager:
    async def stream_events(self, frames):
        buffer = {}
        async for b in frames:
            line = b.decode("utf-8")
            # 解析 event: / data: / id:
            # 简化示例：仅处理 event/data
            if line.startswith("event:"):
                buffer["event"] = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                payload = line.split(":", 1)[1].strip()
                yield StreamEvent(event=buffer.get("event", "event"), payload=_json_or_text(payload))
                buffer.clear()

    async def aggregate(self, events):
        chunks: list[str] = []
        async for ev in events:
            if ev.event == "event":
                et = ev.payload.get("event_type") if isinstance(ev.payload, dict) else None
                if et in {"team_member_content", "team_run_content"}:
                    text = ev.payload.get("data", {}).get("content") or ev.payload.get("data", {}).get("content_chunk")
                    if text:
                        chunks.append(text)
                if et in {"workflow_completed", "team_run_completed", "workflow_failed"}:
                    break
            elif ev.event in {"error", "disconnected"}:
                break
        return {"text": "".join(chunks)}
```

平台适配（策略示例）
```python
class WeComAdapter(PlatformAdapter):
    supports_stream = True
    async def send_incremental(self, ev: StreamEvent) -> None: ...
    async def send_final(self, content: dict) -> None: ...

class TelegramAdapter(PlatformAdapter):
    supports_stream = False
    async def send_incremental(self, ev: StreamEvent) -> None: pass  # 不使用
    async def send_final(self, content: dict) -> None: ...
```

SSE 响应直出（sse-starlette）
```python
from sse_starlette.sse import EventSourceResponse

@router.get("/debug/pipe")
async def debug_pipe():
    async def event_gen():
        async for ev in sse_manager.stream_events(tgo_api_client.send_stream(...)):
            yield {"event": ev.event, "data": ev.payload}
    return EventSourceResponse(event_gen())
```

---

### 5) 数据库设计（PostgreSQL 14+）
- 主表与要点
  - platforms：id(UUID, PK)、project_id(UUID)、name(String(100))、type(String(20))、config(JSONB, 可空)、is_active(Boolean)、created_at/updated_at/deleted_at(DateTime)、api_key(String(255), 可空)
- 事务与会话
  - SQLAlchemy 2.x asyncio：create_async_engine + async_sessionmaker
  - 单请求单会话（FastAPI 依赖注入），并发安全：每协程单独 Session

会话与 Engine 初始化
```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def get_db() -> AsyncSession:
    async with SessionLocal() as session:
        yield session
```

---

### 6) 配置示例（Pydantic Settings 2.x）
.env.example
```
API_BASE_URL=https://tgo-api.example.com

DATABASE_URL=postgresql+asyncpg://user:pass@127.0.0.1:5432/tgo
REQUEST_TIMEOUT_SECONDS=120

# Global SMTP (outbound email)
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=no-reply@example.com
SMTP_PASSWORD=changeme
SMTP_USE_TLS=true
SMTP_FROM_ADDRESS=no-reply@example.com
```

> 注：出站邮件（SMTP 发送）采用全局账户配置（如上 SMTP_*），不再从 pt_platforms.config 读取 SMTP 凭据；平台表 email 类型仅保留 IMAP 收件相关字段（imap_host/port/username/password/use_ssl/mailbox 等）用于入站拉取。


使用
```python
settings = Settings()  # 自动加载 .env / 环境变量 / Secrets
```

---

### 7) 依赖管理（Poetry，pyproject.toml 片段）
```toml
[tool.poetry]
name = "tgo-platform"
version = "0.1.0"
package-mode = true

[tool.poetry.dependencies]
python = ">=3.11,<3.13"
fastapi = ">=0.110,<1.0"
uvicorn = {version = ">=0.27,<1.0", extras=["standard"]}
sqlalchemy = ">=2.0,<3.0"
asyncpg = ">=0.29,<1.0"
httpx = ">=0.27,<1.0"
pydantic = ">=2.7,<3.0"
pydantic-settings = ">=2.3,<3.0"
sse-starlette = ">=1.6,<2.0"
python-dotenv = ">=1.0,<2.0"

[tool.poetry.group.dev.dependencies]
pytest = ">=7.4,<9.0"
pytest-asyncio = ">=0.23,<1.0"
ruff = ">=0.5,<1.0"
```

---

### 8) 上线与运行要点
- 观测性：日志注入 request_id/correlation_id，记录关键事件（connected/event/error/disconnected）与耗时
- 可靠性：
  - tgo-api 超时使用 timeout_seconds，与平台适配回退策略对齐
  - httpx 重试（幂等场景）与指数退避；SSE 断线重连（按需）
- 安全：平台凭据 api_key 存储于 pt_platforms 表（建议加密/脱敏展示）；路由入站校验签名（Webhook）
- 迁移：Alembic（可选）管理 DDL 与版本

---

### 9) 完整调用流程（端到端伪代码）

```python
from __future__ import annotations
import asyncio
from typing import Protocol, AsyncIterator
from fastapi import APIRouter, Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

router = APIRouter()

# 公用编排逻辑：接收已标准化消息，查询平台配置并执行流式/非流式输出
async def process_message(msg: NormalizedMessage, db: AsyncSession) -> None:
    for attempt in range(3):  # 简单重试（指数退避）
        try:
            # 1) 查询平台配置（含 api_key）
            stmt = (
                select(Platform)
                .where(
                    Platform.project_id == msg.extra.get("project_id"),
                    Platform.type == msg.extra.get("platform_type"),
                    Platform.is_active.is_(True),
                )
                .limit(1)
            )
            platform = await db.scalar(stmt)
            if not platform or not platform.api_key:
                raise RuntimeError("platform not configured or missing api_key")

            # 2) 调用 tgo-api 建立 SSE
            req_body = SendStreamRequest(
                api_key=platform.api_key,  # 来自数据库的 per-platform API Key
                message=msg.content,
                channel_id=msg.channel_id,
                channel_type=msg.channel_type,
                from_uid=msg.from_uid,
                extra=msg.extra,
                timeout_seconds=settings.request_timeout_seconds,
            )
            frames = tgo_api_client.send_stream(req_body)
            events = sse_manager.stream_events(frames)

            # 3) 平台适配（传入凭据）
            adapter = select_adapter_for_target(msg, credentials=platform.api_key)

            # 4) 输出策略
            if adapter.supports_stream:
                async for ev in events:
                    await adapter.send_incremental(ev)
            else:
                final = await sse_manager.aggregate(events)
                await adapter.send_final(final)
            return
        except Exception:
            if attempt == 2:
                raise
            await asyncio.sleep(2 ** attempt)

# 推送式：Webhook -> 标准化 -> 编排
@router.post("/ingest")
async def ingest(req: Request, db: AsyncSession = Depends(get_db)):
    raw = await req.json()
    msg: NormalizedMessage = await normalizer.normalize(raw)
    await process_message(msg, db)
    return {"ok": True}

# 拉取式：SMTP Channel Listener（实现 ChannelListener 协议）
class ChannelListener(Protocol):
    async def listen(self) -> AsyncIterator[dict]:
        """异步产出原始消息事件。"""

class SmtpChannelListener:
    """
    职责：
    - 异步监听/轮询 SMTP 收件箱，产出原始消息事件
    - 基于 Message-ID 实现幂等去重
    - 不做业务编排，仅触发后续标准化与处理
    """
    def __init__(self, config: dict):
        self.config = config

    async def listen(self) -> AsyncIterator[dict]:
        while True:
            # 伪代码：拉取新邮件（省略具体 SMTP/IMAP 实现）
            for raw in await fetch_new_emails(self.config):
                mid = raw.get("Message-ID")
                if await idempotency_store.seen(mid):
                    continue  # 幂等去重
                await idempotency_store.mark(mid)
                yield raw
            await asyncio.sleep(2)  # 轮询间隔

# 监听循环：从监听器产出 -> 标准化 -> 编排
async def run_smtp_listener(listener: ChannelListener) -> None:
    async for raw in listener.listen():
        try:
            msg: NormalizedMessage = await normalizer.normalize(raw)
            # 每次处理单独获取会话，确保资源回收
            async with SessionLocal() as db:
                await process_message(msg, db)
        except Exception:
            # 记录错误并继续下一条，必要时可添加重试/告警
            continue
```


参考
- SQLAlchemy asyncio: https://docs.sqlalchemy.org/en/latest/orm/extensions/asyncio.html
- SQLAlchemy Declarative + mapped_column: https://docs.sqlalchemy.org/en/latest/orm/declarative_tables.html
- Pydantic Settings v2: https://docs.pydantic.dev/latest/concepts/pydantic_settings/

