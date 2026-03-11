# TGO SaaS - 项目总览

TGO 是一个 AI 驱动的全渠道客服平台，采用微服务架构，包含 8 个 Python 后端服务、1 个 Go Agent、2 个 React 前端、1 个微信小程序组件和 2 个 Node.js CLI 工具。

## 项目列表

| 项目 | 简介 | 技术栈 | 端口 |
|------|------|--------|------|
| [tgo-api](#tgo-api) | 核心业务 API | Python / FastAPI | 8000, 8001 |
| [tgo-ai](#tgo-ai) | AI 服务 (Agent / 知识库 / 用量) | Python / FastAPI | 8081 |
| [tgo-platform](#tgo-platform) | 多渠道消息集成 | Python / FastAPI | 8003 |
| [tgo-rag](#tgo-rag) | RAG 检索增强生成 | Python / FastAPI | 8082 |
| [tgo-workflow](#tgo-workflow) | 工作流引擎 | Python / FastAPI / Celery | 8000 |
| [tgo-plugin-runtime](#tgo-plugin-runtime) | 插件运行时 | Python / FastAPI | 8090 |
| [tgo-device-control](#tgo-device-control) | 设备远程控制服务 | Python / FastAPI | 8085, 9876 |
| [tgo-device-agent](#tgo-device-agent) | 设备端 Agent | Go | TCP 客户端 |
| [tgo-web](#tgo-web) | 客服工作台前端 | React 19 / TypeScript / Vite | 5173 |
| [tgo-widget-js](#tgo-widget-js) | 网页嵌入式聊天组件 | React 18 / TypeScript / Vite | 5173 |
| [tgo-widget-miniprogram](#tgo-widget-miniprogram) | 微信小程序聊天组件 | 微信小程序 / JS | npm 包 |
| [tgo-cli](#tgo-cli) | 命令行工具 + MCP Server (客服端) | Node.js / TypeScript | CLI / stdio |
| [tgo-widget-cli](#tgo-widget-cli) | 命令行工具 + MCP Server (访客端) | Node.js / TypeScript | CLI / stdio |

## 各项目详情

### tgo-api

核心业务 API 服务，处理用户管理、访客管理、会话分配、标签系统、平台集成等核心业务逻辑。

- **技术栈**: Python 3.11+, FastAPI, PostgreSQL, SQLAlchemy, Alembic, Redis, Kafka
- **端口**: 8000 (对外 API), 8001 (内部服务)
- **职责**: 用户/访客 CRUD、会话路由与分配、多租户隔离、WuKongIM 集成

### tgo-ai

AI/ML 运营微服务，管理 AI Agent 配置、知识库操作、工具集成和用量统计。

- **技术栈**: Python 3.11+, FastAPI, PostgreSQL, SQLAlchemy, agno, MCP
- **端口**: 8081
- **职责**: AI Agent CRUD、Team 管理、多模型支持 (OpenAI / Anthropic / Gemini / Qwen)、工具集成、用量分析
- **认证**: JWT + API Key 双认证

### tgo-platform

多渠道消息集成与归一化服务，将来自不同平台的消息统一转换为内部格式。

- **技术栈**: Python 3.11+, FastAPI, PostgreSQL, SQLAlchemy, Redis
- **端口**: 8003
- **支持渠道**: 微信公众号、企业微信、Slack、Telegram、邮件、WuKongIM (网站)
- **职责**: 平台回调接收、消息格式归一化、SSE 推送、Channel Listener 生命周期管理

### tgo-rag

检索增强生成 (RAG) 服务，提供文档处理、向量化和语义搜索能力。

- **技术栈**: Python 3.11+, FastAPI, PostgreSQL 16 + pgvector, Redis, Celery, LangChain
- **端口**: 8082
- **职责**: 文档处理 (PDF/Word/文本/Markdown/HTML)、混合搜索 (向量+关键词)、多供应商 Embedding、异步文档处理

### tgo-workflow

AI Agent 工作流引擎，支持 DAG 拓扑编排和可视化执行。

- **技术栈**: Python 3.10+, FastAPI, Celery, Redis, PostgreSQL, SQLAlchemy
- **端口**: 8000
- **职责**: DAG 工作流编排、多节点类型 (起始/结束/LLM/API/条件/分类/Agent/工具)、变量系统、异步执行、执行追踪

### tgo-plugin-runtime

插件安装、进程托管和工具同步服务。

- **技术栈**: Python 3.11+, FastAPI, PostgreSQL, SQLAlchemy
- **端口**: 8090
- **职责**: 插件生命周期管理、Unix Socket/TCP 通信、进程管理、工具同步至 tgo-ai

### tgo-device-control

设备远程控制服务，允许 AI Agent 远程操控用户电脑/移动设备。

- **技术栈**: Python 3.11+, FastAPI, PostgreSQL (pgvector), Redis, WebSocket
- **端口**: 8085 (HTTP API), 9876 (TCP RPC / Peekaboo), 7778 (AgentOS)
- **职责**: 设备连接管理、MCP Agent、多设备支持、Peekaboo 协议

### tgo-device-agent

运行在受管设备上的客户端 Agent，通过 TCP 连接提供文件操作和 Shell 执行能力。

- **技术栈**: Go 1.22
- **协议**: TCP JSON-RPC 2.0，连接至 tgo-device-control 的 9876 端口
- **内置工具**: `fs_read`, `fs_write`, `fs_edit`, `shell_exec`
- **职责**: 自动认证、安全沙箱、远程命令执行

### tgo-web

客服工作台前端，提供实时聊天、AI 交互、知识库管理等完整客服操作界面。

- **技术栈**: React 19, TypeScript 5.9, Vite 7, Zustand, Tailwind CSS 4, WuKongIM SDK, i18next
- **端口**: 5173 (开发), 80 (生产)
- **职责**: 实时聊天 (WuKongIM WebSocket)、AI 流式响应 (SSE)、访客/会话管理、知识库管理、MCP 工具集成

### tgo-widget-js

类 Intercom 的网页嵌入式客服聊天组件。

- **技术栈**: React 18, TypeScript, Vite 5, Emotion, json-render
- **端口**: 5173 (开发), 5174 (预览)
- **职责**: 访客端聊天界面、消息气泡、AI 流式回复、嵌入式部署

### tgo-widget-miniprogram

微信小程序端的聊天组件，以 npm 包形式提供。

- **技术栈**: 微信小程序, JavaScript, easyjssdk, marked, json-render
- **分发**: npm 包 (`tgo-widget-miniprogram`)
- **职责**: 文本/图片消息、AI 流式回复、Markdown 渲染、历史消息加载、IM 自动重连

### tgo-cli

AI Agent 客服操作命令行工具，同时提供 MCP Server 模式供 Claude Code / Cursor 等 AI 工具调用。

- **技术栈**: Node.js 18+, TypeScript, Commander.js, MCP SDK, easyjssdk (WuKongIM)
- **模式**: CLI 命令行 / MCP Server (stdio)
- **职责**: 40+ 命令覆盖会话/聊天/访客/Agent/知识库/工作流等全部操作、WuKongIM WebSocket 消息收发
- **命令参考**: 详见 [`tgo-cli/COMMANDS.md`](./tgo-cli/COMMANDS.md)

### tgo-widget-cli

访客端命令行工具 + MCP Server，让 AI Agent 或自动化测试系统能以"访客"身份与客服系统交互。

- **技术栈**: Node.js 18+, TypeScript, Commander.js, MCP SDK, easyjssdk (WuKongIM)
- **模式**: CLI 命令行 / MCP Server (stdio)
- **认证**: Platform API Key + 访客注册 (非 JWT)
- **职责**: 访客注册、消息发送 (SSE 流式 AI 回复)、消息历史、文件上传、活动记录、WuKongIM 实时消息
- **命令参考**: 详见 [`tgo-widget-cli/COMMANDS.md`](./tgo-widget-cli/COMMANDS.md)

## 基础设施依赖

| 组件 | 用途 |
|------|------|
| PostgreSQL 16 | 主数据库，pgvector 扩展用于 AI 向量存储 |
| Redis | 缓存、消息队列 (Celery broker)、会话状态 |
| Kafka | 事件流 (tgo-api ↔ 各服务间异步通信) |
| WuKongIM | 即时通讯引擎，WebSocket 消息收发 |
| Celery | 异步任务 (tgo-rag 文档处理、tgo-workflow 工作流执行) |
