# TGO Widget App AGENTS Guide

> 适用范围：`repos/tgo-widget-app`
> 最近校准：2026-03-10

## 1. 服务定位

`tgo-widget-app` 是访客侧嵌入式聊天组件，运行在 iframe 中，负责消息展示、输入、IM 通道与宿主页交互。

- 技术栈：React 18 + TypeScript 5.6 + Vite 5 + Emotion + Zustand 5
- 本地端口：`5174`（`yarn dev` 或工作区 `make dev-widget`）
- 姊妹项��：`tgo-web`（管理后台前端），两者的 json-render 组件需保持同步

---

## 2. 关键目录

```text
src/
├── App.tsx                        # 主入口，初始化 IM/平台/活动追踪
├── main.tsx                       # React 挂载，Emotion cache 配置
├── components/
│   ├── Header.tsx                 # 顶部导航
│   ├── MessageList.tsx            # 消息列表，无限滚动
│   ├── MessageInput.tsx           # 输入框，文件/表情支持
│   ├── MarkdownContent.tsx        # Markdown 渲染（DOMPurify 防 XSS）
│   ├── ImagePreview.tsx           # 图片预览弹窗
│   ├── jsonRender/                # json-render 富 UI 渲染系统
│   │   ├── JSONRenderSurface.tsx  # 核心渲染面，状态/动作管理
│   │   └── registry.tsx           # 组件注册表（20+ 组件）
│   └── messages/                  # 消息类型渲染器
│       ├── JSONRenderMessage.tsx  # json-render 消息（文本+规格交替）
│       ├── TextMessage.tsx
│       ├── ImageMessage.tsx
│       ├── FileMessage.tsx
│       ├── MixedMessage.tsx       # 混合消息（文本+图片+文件）
│       ├── SystemMessage.tsx
│       └── messageStyles.ts       # Emotion styled 组件（Bubble 等）
├── store/
│   ├── chatStore.ts               # 聊天状态，IM 消息收发/流式处理
│   └── platformStore.ts           # 平台配置，主题，展开/折叠
├── services/
│   ├── wukongim.ts                # WuKongIM IM 服务单例
│   ├── messageHistory.ts          # 历史消息拉取
│   ├── platform.ts                # 平台配置获取
│   ├── visitor.ts                 # 访客注册/加载
│   ├── upload.ts                  # 文件上传
│   └── visitorActivity.ts         # 活动追踪
├── types/
│   ├── chat.ts                    # ChatMessage, 消息 payload 联合类型
│   └── api.ts                     # API 请求/响应类型
├── contexts/
│   └── ThemeContext.tsx            # 明暗主题 Provider
├── i18n/locales/                  # zh.json, en.json
└── utils/                         # URL 解析、通知、Markdown 配置等
```

---

## 3. 强约束规范

### 3.1 iframe 与宿主通信

- `postMessage` 事件类型与 payload 结构需保持兼容。
- 不得变更宿主侧依赖的消息名（`tgo:visibility`、`TGO_WIDGET_UNREAD`、`TGO_SHOW_TOAST`、`TGO_WIDGET_CONFIG`）。

### 3.2 状态与 API 分层

- 组件不得直接发请求，统一走 `services/*` + `store/*`。
- 消息模型变更须同步 `types/chat.ts`、store 和渲染组件。

### 3.3 安全与内容渲染

- Markdown/HTML 渲染必须保持 XSS 防护（DOMPurify）。
- 外链、Action URI 与文件链接处理需保留白名单与校验逻辑。

### 3.4 样式规范

- Widget 使用 **Emotion + 内联 CSSProperties**，不使用 Tailwind。
- CSS 变量统一走 `--primary`、`--bg-primary`、`--text-primary` 等主题变量。
- `tgo-web` 使用 Tailwind，移植代码时须转为内联样式。

### 3.5 国际化与主题

- 用户可见文案优先写入 `i18n/locales/*`。
- 主题色、位置、展开状态与宿主页同步逻辑不可破坏。

---

## 4. json-render 系统

### 4.1 架构概览

json-render 是 AI 驱动的富 UI 渲染系统，AI 在消息中嵌入 ```` ```spec ```` 围栏内的 JSONL 补丁流，前端解析后渲染为交互式 UI。

**数据流：**
```
AI 输出 → ``` spec 围栏内 JSONL 补丁 → MixedStreamParser → DataPart[]
→ useJsonRenderMessage() 构建 Spec → JSONRenderSurface 渲染
```

**依赖库：**
- `@json-render/core@^0.11.0` — Spec 类型、补丁应用
- `@json-render/react@^0.11.0` — `Renderer`、`StateProvider`、`ActionProvider`、`useJsonRenderMessage`、`useBoundProp`、`createStateStore`、`useActions`

### 4.2 三个核心文件

| 文件 | 职责 |
|------|------|
| `components/messages/JSONRenderMessage.tsx` | 从 `ChatMessage.uiParts` 提取 `DataPart[]`，按文本/规格分组交替渲染 |
| `components/jsonRender/JSONRenderSurface.tsx` | 接收 `Spec`，创建 state store，注册 action handler，调用 `Renderer` |
| `components/jsonRender/registry.tsx` | 组件注册表，将规格中的 `type` 映射到 React 组件 |

### 4.3 关键机制

**HandlerSync 模式：**
`ActionProvider` 内部用 `useState(initialHandlers)` 只在首次挂载读取 handlers。流式消息中新 action 元素陆续到达，必须通过 `HandlerSync` 组件调用 `registerHandler()` 同步。

**statePath 拦截：**
AI 可能用自定义 action 名但传 `{ statePath, value }` 参数（本意是更新状态而非提交）。handler 内检测 `statePath` 参数：
- 有 `statePath` → 调用 `store.set()` 更新本地状态
- 无 `statePath` → 触发 `onAction` 回调（提交行为）

**内置 action 过滤：**
`setState`、`pushState`、`removeState`、`validateForm` 为内置 action，由 `ActionProvider` 自动处理，`collectActionNames` 不为其注册自定义 handler。

**loading 状态：**
流式传输中元素定义可能尚未到达但已被引用为 children，传 `loading={true}` 给 `Renderer` 可抑制 "Missing element" 警告。

### 4.4 注册表组件

| 类型 | 别名 | 说明 |
|------|------|------|
| `Text` | — | 文本，自动识别 KV 对、标题、金额 |
| `Button` | — | 按钮，支持 `primary`/`danger`/`link` variant，`loading` 状态 |
| `ButtonGroup` | `Actions` | 按钮容器 |
| `Card` | — | 卡片，`order`/`invoice` variant 有渐变背景 |
| `Section` | `SectionCard` | 分组区块 |
| `KV` | `KeyValue` | 键值对行 |
| `PriceRow` | `AmountRow` | 价格行，支持强调/折扣样式 |
| `Badge` | `StatusBadge` | 状态标签 |
| `OrderItem` | `LineItem` | 订单商品行 |
| `Image` | — | 图片 |
| `Row` | — | 水平布局 |
| `Column` | — | 垂直布局 |
| `List` | — | 列表容器 |
| `Divider` | — | 分割线 |
| `Input` | `TextField` | 文本输入 |
| `Checkbox` | `CheckBox` | 复选框，接受 `value`/`checked`/`selected` 绑定 |
| `DateTimeInput` | — | 日期时间选择，接受 `value`/`date`/`selectedDate` 绑定，支持 `mode` prop |
| `MultipleChoice` | — | 单选下拉，接受 `value`/`selectedValue`/`selectedValues` 绑定，支持字符串选项简写 |

### 4.5 与 tgo-web 同步规则

两个项目的 json-render 组件逻辑须保持一致，差异仅限：
- **样式**：widget 用内联 CSSProperties + CSS 变量，web 用 Tailwind
- **消息类型**：widget 用 `ChatMessage`（`uiParts`、`streamData`），web 用 `Message`（`metadata.ui_parts`、`metadata.stream_end`）
- **回调模式**：widget 用 `onAction(name, context)` 回调，web 用 `onSendMessage(text)` 格式化文本

**同步时需注意：**
1. 从 web 移植 bug fix 时，保留 widget 的内联样式和回调模式
2. `registry.tsx` 中的组件 prop 兼容逻辑（别名、容错）必须完全一致
3. `JSONRenderSurface.tsx` 中的 handler 逻辑（HandlerSync、statePath 拦截、内置 action 过滤）必须完全一致

---

## 5. 消息系统

### 5.1 消息类型

| `payload.type` | 类型 | 渲染器 |
|---------------:|------|--------|
| 1 | 文本 | `TextMessage` |
| 2 | 图片 | `ImageMessage` |
| 3 | 文件 | `FileMessage` |
| 12 | 混合（文本+图片+文件） | `MixedMessage` |
| 99 | 命令 | — |
| 100 | AI 加载中 | 加载动画 |
| 1000-2000 | 系统通知 | `SystemMessage` |

### 5.2 流式消息处理

1. WuKongIM 收到消息 → `chatStore.onMessage` 触发
2. 流式消息通过 `MixedStreamParser` 解析为 `DataPart[]`
3. `DataPart` 增量追加到 `ChatMessage.uiParts`
4. `JSONRenderMessage` 检测到 `uiParts` 变化 → 重新分组渲染
5. `showCursor` 为 `true` 时处于流式状态，传 `loading` 给渲染器

### 5.3 历史消息 vs 流式消息

两条路径产生 `uiParts`：
- **历史消息**：`chatStore` 加载时，对 `streamContent` 调用 `MixedStreamParser` 一次性解析
- **流式消息**：WebSocket 实时推送 `DataPart`，逐个追加到 `uiParts`

两条路径的渲染结果应完全一致。

---

## 6. 高频改动入口

| 场景 | 文件 |
|------|------|
| 主流程/初始化 | `src/App.tsx` |
| 聊天状态/IM | `src/store/chatStore.ts` |
| 平台配置/主题 | `src/store/platformStore.ts` |
| IM 接入 | `src/services/wukongim.ts` |
| json-render 渲染 | `src/components/jsonRender/JSONRenderSurface.tsx` |
| json-render 组件 | `src/components/jsonRender/registry.tsx` |
| json-render 消息 | `src/components/messages/JSONRenderMessage.tsx` |
| 消息列表 | `src/components/MessageList.tsx` |
| 输入框 | `src/components/MessageInput.tsx` |
| 消息类型定义 | `src/types/chat.ts` |

---

## 7. 本地开发命令

```bash
# 安装依赖
yarn install

# 开发
yarn dev

# 构建与预览
yarn build
yarn preview
```

当前项目未内置 lint/type-check 独立脚本，改动后至少完成 `yarn build`（含 tsc 检查）并做页面交互回归。

---

## 8. AI 代理改动流程

1. 先确认改动在消息渲染、状态层还是宿主交互层。
2. 先改类型与 store，再改 UI 组件。
3. 涉及消息协议改动时，验证历史消息与流式消息两条路径。
4. 涉及 iframe 通信改动时，联调宿主页事件。
5. 涉及 json-render 改动时，同步检查 `tgo-web` 对应文件是否需要同步。
6. 提交前执行 `yarn build` 确认无类型错误。

---

## 9. 变更自检清单

- [ ] 是否破坏宿主 `postMessage` 协议兼容？
- [ ] 是否引入未清洗的富文本渲染路径？
- [ ] 是否改了消息结构但漏改 store/renderer/types？
- [ ] json-render 改动是否与 tgo-web 保持同步？
- [ ] 样式是否使用内联 CSSProperties（而非 Tailwind）？
- [ ] 是否完成构建并验证主交互链路？
