# 统一等待队列设计文档

## 概述

统一等待队列（Unified Waiting Queue）是一个用于管理访客等待人工客服分配的系统。该系统将所有人工服务请求（包括 AI 发起的转人工请求、访客主动请求、系统自动转人工等）统一纳入一个队列进行管理和处理。

### 设计目标

1. **统一入口**：所有人工服务请求通过统一的队列处理
2. **高并发支持**：支持多线程并发消费队列
3. **实时响应**：支持主动触发立即处理，无需等待定时任务
4. **可靠性**：支持重试机制和过期处理
5. **可观测性**：完整的日志记录和状态追踪

## 架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                         请求入口                                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────────────────┐ │
│  │  AI Agent    │   │   访客请求    │   │  transfer_to_human()     │ │
│  │  请求转人工   │   │   人工服务    │   │  无可用客服时自动入队      │ │
│  └──────┬───────┘   └──────┬───────┘   └────────────┬─────────────┘ │
│         │                  │                        │               │
│         │ source:          │ source:                │ source:       │
│         │ ai_request       │ visitor                │ no_staff      │
│         │                  │                        │               │
│         └──────────────────┼────────────────────────┘               │
│                            ▼                                         │
│              ┌─────────────────────────────┐                        │
│              │   VisitorWaitingQueue       │                        │
│              │   (统一等待队列表)            │                        │
│              └─────────────┬───────────────┘                        │
│                            │                                         │
└────────────────────────────┼─────────────────────────────────────────┘
                             │
┌────────────────────────────┼─────────────────────────────────────────┐
│                            ▼                                         │
│              ┌─────────────────────────────┐                        │
│              │   process_waiting_queue.py  │                        │
│              │   (队列处理任务)              │                        │
│              └─────────────────────────────┘                        │
│                            │                                         │
│         ┌──────────────────┴──────────────────┐                     │
│         │                                      │                     │
│         ▼                                      ▼                     │
│  ┌──────────────────┐              ┌──────────────────┐             │
│  │   定时任务扫描    │              │   主动触发处理    │             │
│  │  (每5秒一次)      │              │  (立即处理)       │             │
│  └────────┬─────────┘              └────────┬─────────┘             │
│           │                                  │                       │
│           └──────────────┬───────────────────┘                      │
│                          ▼                                           │
│           ┌──────────────────────────────┐                          │
│           │  Semaphore 并发控制           │                          │
│           │  (最大 5 个并发 worker)       │                          │
│           └──────────────┬───────────────┘                          │
│                          ▼                                           │
│           ┌──────────────────────────────┐                          │
│           │  transfer_to_human()         │                          │
│           │  (尝试分配客服)               │                          │
│           └──────────────┬───────────────┘                          │
│                          │                                           │
│         ┌────────────────┼────────────────┐                         │
│         ▼                ▼                ▼                         │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐                │
│  │ 分配成功      │ │ 无可用客服    │ │ 分配失败      │                │
│  │ status:      │ │ 保持waiting  │ │ 重试或过期    │                │
│  │ assigned     │ │ retry_count++│ │              │                │
│  └──────────────┘ └──────────────┘ └──────────────┘                │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

## 数据模型

### VisitorWaitingQueue 表结构

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID | 主键 |
| `project_id` | UUID | 关联项目ID |
| `visitor_id` | UUID | 等待中的访客ID |
| `session_id` | UUID | 关联的会话ID（可选）|
| `assigned_staff_id` | UUID | 分配的客服ID（分配后填充）|
| `source` | String(20) | 入队来源 |
| `urgency` | String(10) | 紧急程度 |
| `position` | Integer | 队列位置（越小越靠前）|
| `priority` | Integer | 优先级（越大越优先）|
| `status` | String(20) | 队列状态 |
| `visitor_message` | Text | 触发转人工的消息内容 |
| `reason` | String(255) | 入队原因 |
| `channel_id` | String(255) | 通信频道ID |
| `channel_type` | Integer | 频道类型 |
| `extra_metadata` | JSONB | 额外元数据 |
| `retry_count` | Integer | 重试次数 |
| `last_attempt_at` | DateTime | 最后尝试时间 |
| `entered_at` | DateTime | 入队时间 |
| `assigned_at` | DateTime | 分配时间 |
| `exited_at` | DateTime | 出队时间 |
| `created_at` | DateTime | 创建时间 |
| `updated_at` | DateTime | 更新时间 |

### 枚举定义

#### QueueSource（入队来源）

| 值 | 说明 |
|------|------|
| `ai_request` | AI Agent 发起的人工请求 |
| `visitor` | 访客主动请求人工服务 |
| `transfer` | 客服转接 |
| `system` | 系统自动（如超时转人工）|
| `no_staff` | 无可用客服时自动入队 |

#### QueueUrgency（紧急程度）

| 值 | 优先级 | 说明 |
|------|------|------|
| `low` | 0 | 低优先级 |
| `normal` | 1 | 普通（默认）|
| `high` | 2 | 高优先级 |
| `urgent` | 3 | 紧急 |

#### WaitingStatus（队列状态）

| 值 | 说明 |
|------|------|
| `waiting` | 等待中 |
| `assigned` | 已分配 |
| `cancelled` | 已取消（访客离开）|
| `expired` | 已过期（超过最大重试次数）|

## 核心流程

### 1. AI 请求转人工流程

当 AI Agent 需要将访客转给人工客服时：

```python
# app/api/internal/endpoints/ai_events.py

def _handle_manual_service_request(event, project, db):
    # 1. 验证访客
    visitor = db.query(Visitor).filter(Visitor.id == event.visitor_id).first()
    
    # 2. 解析紧急程度并转换为优先级
    urgency = payload.urgency or "normal"
    priority = VisitorWaitingQueue.urgency_to_priority(urgency)
    
    # 3. 计算队列位置
    position = db.query(VisitorWaitingQueue).filter(
        VisitorWaitingQueue.project_id == project.id,
        VisitorWaitingQueue.status == "waiting"
    ).count() + 1
    
    # 4. 创建队列条目
    queue_entry = VisitorWaitingQueue(
        project_id=project.id,
        visitor_id=visitor_id,
        source=QueueSource.AI_REQUEST.value,
        urgency=urgency,
        priority=priority,
        position=position,
        status=WaitingStatus.WAITING.value,
        visitor_message=reason,
        channel_id=channel_id,
        channel_type=channel_type,
        extra_metadata=payload.metadata,
    )
    db.add(queue_entry)
    db.commit()
    
    # 5. 主动触发处理（不阻塞）
    asyncio.create_task(trigger_process_entry(queue_entry.id))
```

### 2. 无可用客服自动入队流程

当 `transfer_to_human()` 找不到可用客服时：

```python
# app/services/transfer_service.py

async def transfer_to_human(...):
    # 获取可用客服候选
    candidates = await _get_available_staff_candidates(db, project_id, assignment_rule)
    
    if len(candidates) == 0:
        # 无可用客服，加入等待队列
        queue_entry = VisitorWaitingQueue(
            project_id=project_id,
            visitor_id=visitor_id,
            session_id=session.id,
            source=QueueSource.NO_STAFF.value,
            position=queue_position,
            status=WaitingStatus.WAITING.value,
            visitor_message=visitor_message,
            reason="No available staff",
        )
        db.add(queue_entry)
        
        return TransferResult(
            success=True,
            message="Added to waiting queue",
            waiting_queue=queue_entry,
            queue_position=queue_position,
        )
```

### 3. 队列处理流程

#### 定时批量处理

```python
# app/tasks/process_waiting_queue.py

async def _process_waiting_queue_batch():
    # 1. 查询待处理条目（排除最近尝试过的）
    entries = db.query(VisitorWaitingQueue).filter(
        VisitorWaitingQueue.status == "waiting",
        (VisitorWaitingQueue.last_attempt_at.is_(None)) |
        (VisitorWaitingQueue.last_attempt_at < cutoff_time)
    ).order_by(
        VisitorWaitingQueue.priority.desc(),  # 高优先级优先
        VisitorWaitingQueue.position.asc(),   # 先来先服务
    ).limit(BATCH_SIZE).all()
    
    # 2. 过滤正在处理中的条目
    entries_to_process = [e for e in entries if e.id not in _processing_ids]
    
    # 3. 并行处理（使用 Semaphore 控制并发数）
    tasks = [process_with_semaphore(e) for e in entries_to_process]
    await asyncio.gather(*tasks)
```

#### 单条目处理

```python
async def _process_single_entry_internal(db, entry):
    # 1. 记录本次尝试
    entry.record_attempt()
    
    # 2. 调用 transfer_to_human 尝试分配
    result = await transfer_to_human(
        db=db,
        visitor_id=entry.visitor_id,
        project_id=entry.project_id,
        source=AssignmentSource.RULE,
        session_id=entry.session_id,
    )
    
    # 3. 处理结果
    if result.success and result.assigned_staff_id:
        # 分配成功
        entry.assign_to_staff(result.assigned_staff_id)
    elif entry.retry_count >= MAX_RETRIES:
        # 超过最大重试次数，标记为过期
        entry.expire()
    # else: 保持 waiting 状态，等待下次处理
    
    db.commit()
```

## 并发控制

### 防止重复处理

使用 `asyncio.Lock` 和 `Set` 跟踪正在处理的条目：

```python
_processing_lock = asyncio.Lock()
_processing_ids: Set[UUID] = set()

async def process_queue_entry(entry_id):
    # 加锁检查是否已在处理
    async with _processing_lock:
        if entry_id in _processing_ids:
            return False  # 已在处理中，跳过
        _processing_ids.add(entry_id)
    
    try:
        # 处理逻辑...
    finally:
        # 处理完成，从集合移除
        async with _processing_lock:
            _processing_ids.discard(entry_id)
```

### 并发数控制

使用 `asyncio.Semaphore` 限制并发 worker 数量：

```python
_semaphore = asyncio.Semaphore(MAX_WORKERS)  # 默认 5

async def process_with_semaphore(entry):
    async with _semaphore:  # 获取许可
        # 处理逻辑...
        pass
    # 自动释放许可
```

## 配置项

在 `app/core/config.py` 中配置：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `QUEUE_PROCESS_ENABLED` | `True` | 是否启用队列处理任务 |
| `QUEUE_PROCESS_INTERVAL_SECONDS` | `5` | 定时扫描间隔（秒）|
| `QUEUE_PROCESS_BATCH_SIZE` | `50` | 每批最大处理数量 |
| `QUEUE_PROCESS_MAX_WORKERS` | `5` | 最大并发 worker 数 |
| `QUEUE_PROCESS_MAX_RETRIES` | `3` | 最大重试次数 |
| `QUEUE_PROCESS_RETRY_DELAY_SECONDS` | `60` | 重试间隔（秒）|

## API 接口

### 内部接口：AI 事件处理

**POST** `/internal/ai/events`

处理 AI Agent 发送的事件，包括转人工请求。

**请求示例：**
```json
{
  "event_type": "manual_service.request",
  "project_id": "uuid",
  "visitor_id": "uuid",
  "payload": {
    "reason": "访客需要人工帮助",
    "urgency": "high",
    "session_id": "channel_123@1",
    "metadata": {}
  }
}
```

**响应示例：**
```json
{
  "entry_id": "uuid",
  "status": "waiting",
  "position": 3,
  "priority": 2,
  "channel_id": "channel_123",
  "channel_type": 1
}
```

## 文件清单

| 文件 | 说明 |
|------|------|
| `app/models/visitor_waiting_queue.py` | 队列数据模型定义 |
| `app/tasks/process_waiting_queue.py` | 队列处理任务 |
| `app/api/internal/endpoints/ai_events.py` | AI 事件处理接口 |
| `app/services/transfer_service.py` | 转人工服务（含入队逻辑）|
| `app/core/config.py` | 配置项定义 |
| `app/main.py` | 任务启动/停止 |
| `alembic/versions/0006_*.py` | 数据库迁移 |

## 注意事项

1. **主动触发与定时任务协调**：使用 `_processing_ids` 集合确保同一条目不会被重复处理
2. **重试间隔**：条目被处理后需等待 `RETRY_DELAY_SECONDS` 才会再次被定时任务扫描
3. **优先级排序**：高优先级（urgent > high > normal > low）和先入队的条目优先处理
4. **过期处理**：超过最大重试次数的条目将被标记为 `expired`，不再处理
5. **会话关联**：队列条目可关联 `VisitorSession`，便于追踪完整的会话流程
