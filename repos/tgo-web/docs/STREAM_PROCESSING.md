# AI 流式消息前端处理规范

本文档描述前端如何处理服务器发送的 AI 流式消息，包含实时流和历史消息两条路径。目标读者是需要在其他平台/语言实现相同功能的前端开发者。

---

## 一、总览

AI 回复采用流式输出，内容可能包含：
- **纯文本**（Markdown 格式）
- **json-render spec**（用 `` ```spec `` 围栏包裹的 JSONL patches，用于渲染交互式 UI 组件）

两者在流中**交替出现**，前端需要按原始顺序渲染「文字 → UI 组件 → 文字 → …」。

前端需要处理两个场景：
1. **实时流**：通过 WebSocket 接收增量 chunk，逐步解析并渲染
2. **历史消息**：通过 HTTP API 获取完整文本，一次性解析后渲染

---

## 二、服务器端协议

### 2.1 实时流 — WebSocket 事件

流式消息基于 WuKongIM Stream API v2，通过 WebSocket 接收以下事件：

| 事件类型 | 含义 | 关键字段 |
|---------|------|---------|
| `stream.delta` | 增量内容片段 | `payload.delta`（字符串） |
| `stream.close` | 单个事件通道关闭 | `error`（可选，错误信息） |
| `stream.error` | 流出错 | `error`（错误信息） |
| `stream.cancel` | 流被取消 | — |
| `stream.finish` | 整个消息的所有通道全部完成 | — |

每个事件都携带 `clientMsgNo`（客户端消息编号），用于关联到同一条消息。

**流的起点**：收到一条 `payload.type = 100`（STREAM 类型）的普通消息，表示 AI 开始流式回复。此后该 `clientMsgNo` 对应的 `stream.delta` 事件陆续到达。

### 2.2 历史消息 — HTTP API

请求历史消息时需要携带以下参数，以获取流式消息的最终内容：

```
include_event_meta: 1
event_summary_mode: "full"
```

服务器返回的每条消息中，流式消息会包含 `event_meta` 字段：

```json
{
  "event_meta": {
    "has_events": true,
    "completed": true,
    "open_event_count": 0,
    "events": [
      {
        "event_key": "main",
        "status": "closed",
        "snapshot": {
          "kind": "text",
          "text": "这是完整的流内容，可能包含 ```spec 围栏..."
        }
      }
    ]
  }
}
```

关键字段说明：

| 字段 | 说明 |
|------|------|
| `has_events` | 是否是流式消息 |
| `completed` | 流是否已全部完成 |
| `open_event_count` | 仍在进行中的通道数（>0 表示还在流式输出中） |
| `events[].event_key` | 通道名称，`"main"` 为主内容通道 |
| `events[].status` | `"closed"` / `"open"` / `"error"` / `"cancelled"` |
| `events[].snapshot.text` | 该通道的**完整累积文本**（含 `` ```spec `` 围栏） |

---

## 三、混合内容格式

无论实时流还是历史快照，文本内容格式相同。AI 输出的原始文本可能像这样：

```
这是第一段文字，下面是一个 UI 组件：

```spec
{"op":"replace","path":"/type","value":"card"}
{"op":"replace","path":"/title","value":"订单详情"}
```

以上是订单卡片，继续说明...
```

规则：
- `` ```spec `` 独占一行，标记 JSON Render patch 区域开始
- 围栏内每行是一个独立的 JSON 对象（JSONL 格式），代表一个 JSON Patch 操作
- `` ``` `` 独占一行，标记围栏结束
- 围栏外的内容都是普通 Markdown 文本

---

## 四、实时流处理流程

### 步骤 1：接收流起始消息

收到 `payload.type = 100` 的消息时：
- 创建一条新消息记录，标记为「流式输出中」
- 记录 `clientMsgNo` 用于后续 delta 关联

### 步骤 2：为每条消息创建解析器

每个 `clientMsgNo` 需要一个独立的**混合流解析器**实例。解析器是一个逐行状态机：

- **状态 A（普通文本）**：逐行读取，遇到 `` ```spec `` 行则切换到状态 B，否则将该行作为文本输出
- **状态 B（围栏内）**：逐行读取，遇到 `` ``` `` 行则切换回状态 A，否则将该行解析为 JSON 对象作为 patch 输出

解析器有两种输出：
- **文本片段**：普通文字行
- **patch 片段**：围栏内的 JSON patch 对象

### 步骤 3：处理 stream.delta

每次收到 `stream.delta` 事件：

1. **预处理**：将 `delta` 中紧贴在文字后面的 `` ```spec `` 拆到新行
   - 例如 `"文字```spec"` → `"文字\n```spec"`
   - 正则：`/([^\n])```spec/g` → `$1\n```spec`
   - 原因：解析器只在行首识别围栏标记，LLM 有时不会在围栏前换行

2. **喂入解析器**：将预处理后的文本推入解析器

3. **收集输出**：解析器会通过回调产出文本片段或 patch 片段，按顺序追加到消息的「部件列表」（`ui_parts`）中

4. **合并连续文本**：如果新片段是文本，且列表最后一个也是文本，合并为同一个条目（减少渲染开销）

5. **更新消息状态**：
   - 从 `ui_parts` 中提取纯文本部分拼接，更新消息的纯文本内容（用于会话列表预览和搜索）
   - 标记消息为「流式输出中」

### 步骤 4：处理 stream.close

收到 `stream.close` 事件：

1. **Flush 解析器**：调用解析器的 flush 方法，输出缓冲区中残留的内容
2. **销毁解析器**：释放该 `clientMsgNo` 对应的解析器实例
3. **更新消息状态**：标记流已结束（`is_streaming = false`）
4. 如果事件携带 `error`，记录错误信息

### 步骤 5：处理 stream.finish

收到 `stream.finish` 事件：

- 标记消息「全部完成」（`stream_completed = true`）
- `stream.finish` 表示所有通道都已关闭，整个消息输出完毕

### 生命周期总结

```
payload.type=100 消息到达
    → 创建消息记录 + 解析器实例

stream.delta (多次)
    → 预处理 → 解析器 → 文本/patch 片段 → 追加到 ui_parts

stream.close
    → flush 解析器 → 销毁解析器 → 标记流结束

stream.finish
    → 标记消息全部完成
```

---

## 五、历史消息处理流程

### 步骤 1：提取内容

从消息的 `event_meta` 中提取完整文本：

1. 查找 `events` 数组中 `event_key === "main"` 的条目
2. 取 `snapshot.text` 作为完整内容
3. 如果没有 `event_meta`，回退到 `payload.content`

### 步骤 2：判断是否为流式消息

- `event_meta.has_events === true` → 是流式消息
- `event_meta.open_event_count > 0` → 流尚未完成（仍在输出中）

### 步骤 3：解析混合内容

如果是流式消息且有内容，用同样的混合流解析器**一次性**解析：

1. **预处理**：同实时流的 `` ```spec `` 换行处理
2. 将完整文本一次性推入解析器
3. 调用 flush，收集所有文本片段和 patch 片段
4. 结果存为 `ui_parts` 列表

### 步骤 4：向后兼容（旧版消息）

旧版消息可能存在 `event_key === "json_render"` 的单独事件通道，其 `snapshot.text` 包含拼接的 JSON patch 数组（格式如 `[{...}][{...}]`）。处理方式：

1. 查找 `json_render` 事件通道
2. 将 `][` 替换为 `,` 以合并为单个 JSON 数组
3. 解析后将有效的 patch 追加到 `ui_parts` 末尾

### 步骤 5：生成预览文本

从 `ui_parts` 中提取所有 `type === "text"` 的片段，拼接为纯文本，用于会话列表显示和搜索。

---

## 六、渲染规则

### 6.1 消息类型判定

| 条件 | 渲染方式 |
|------|---------|
| `ui_parts` 非空 | 交叉渲染（文本 + UI 组件） |
| `ui_parts` 为空，`has_stream_data = true` | Markdown 渲染 |
| `ui_parts` 为空，`has_stream_data = false` | 纯文本渲染 |

### 6.2 交叉渲染（ui_parts 非空时）

将 `ui_parts` 按类型**分组**，连续相同类型的部件合并为一组：

```
输入 ui_parts:
  text, text, spec, spec, spec, text, text

分组结果:
  Group 1: { type: "text",  text: "合并后的文字" }
  Group 2: { type: "spec",  parts: [spec1, spec2, spec3] }
  Group 3: { type: "text",  text: "合并后的文字" }
```

按组顺序渲染：
- **text 组** → 用 Markdown 渲染器显示
- **spec 组** → 将该组的 patch 列表交给 json-render 引擎构建 spec，然后渲染为交互式 UI 组件

效果：

```
┌──────────────────────────────┐
│ 这是 AI 的文字回复（Markdown）│
│                              │
│ ┌──────────────────────────┐ │
│ │   JSON Render UI 组件     │ │
│ │   [按钮]  [表单]  [卡片]  │ │
│ └──────────────────────────┘ │
│                              │
│ 以上是分析结果...             │
└──────────────────────────────┘
```

### 6.3 流式光标

当消息处于「流式输出中」状态时，在最后一个文本组的末尾显示一个闪烁光标动画，表示内容仍在生成中。

### 6.4 Fallback 处理

当 `ui_parts` 为空但消息有文本内容时：
- 检查内容中是否包含 `` ```spec ``
- 如果包含，剥离围栏及其内容后再显示（防止原始 JSON 泄漏到界面上）
- 剥离规则：移除 `` ```spec...``` `` 完整围栏，以及末尾未闭合的 `` ```spec... `` 片段

---

## 七、消息状态标志

每条消息维护以下状态标志：

| 标志 | 类型 | 说明 |
|------|------|------|
| `has_stream_data` | bool | 该消息是否来自流式输出 |
| `is_streaming` | bool | 是否正在接收流数据 |
| `stream_started` | bool | 是否已收到第一个 chunk |
| `stream_completed` | bool | 所有通道是否全部完成 |
| `stream_end` | 0/1 | 主通道是否关闭（1=已关闭） |
| `error` | string? | 错误信息 |
| `ui_parts` | array | 有序的文本/patch 部件列表 |

状态流转：

```
消息创建
  has_stream_data = true
  is_streaming = true

收到第一个 delta
  stream_started = true

收到 stream.close
  is_streaming = false
  stream_end = 1

收到 stream.finish
  stream_completed = true
```

---

## 八、实现要点总结

1. **解析器是逐行状态机**：按 `\n` 分行，跟踪是否在 `` ```spec `` 围栏内，围栏内按 JSONL 解析 patch，围栏外作为文本输出
2. **预处理不可省略**：必须将 `"文字```spec"` 拆成两行，否则围栏标记不会被识别
3. **每条消息独立解析器**：不同消息的流是独立的，解析器实例不能共享
4. **flush 不可省略**：流结束时必须 flush 解析器，否则最后一个不完整行会丢失
5. **合并连续文本**：连续的文本片段应合并，减少不必要的 DOM 节点
6. **历史消息与实时流用同一个解析器**：区别只是历史消息一次性推入全文并 flush，实时流分多次推入
7. **纯文本也能走解析器**：如果流中没有 `` ```spec `` 围栏，解析器只输出文本片段，效果等同于纯文本追加，无需提前判断消息类型
