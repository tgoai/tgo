# TGO 开源项目指南 - AI Agents Guide

本文件旨在为 AI 代理（如 Cursor, GitHub Copilot, Claude 等）提供 TGO 开源项目的整体架构、微服务组成和开发指南。

---

## 1. 项目简介

TGO 是一个开源的 AI Agent 客服平台，致力于帮助企业“构建客服 AI Agent 团队”。它集成了多渠道接入、Agent 编排、知识库管理 (RAG) 和人工客服协作。

### 核心功能
- **AI Agent 编排**: 多智能体支持，集成多种 LLM 模型，流式响应。
- **知识库 (RAG)**: 支持文档、问答、网站等多种知识库类型，基于向量检索。
- **MCP 工具集成**: 内置工具商店，支持自定义工具和 OpenAPI Schema 解析。
- **多渠道接入**: Web Widget、微信公众号、小程序等统一管理。
- **实时通讯**: 基于 WuKongIM 的稳定长连接。

---

## 2. 系统架构

TGO 采用微服务架构，前端与多个后端微服务通过 RESTful API 进行交互。

```mermaid
graph TB
    subgraph Frontend [Frontend Services]
        WEB[tgo-web - Admin Dashboard]
        WIDGET[tgo-widget-app - Chat Widget]
    end
    
    subgraph Backend [Backend Services]
        API[tgo-api - Core API Gateway]
        AI[tgo-ai - LLM Interface Service]
        RAG[tgo-rag - Knowledge Base Service]
        PLATFORM[tgo-platform - Multi-channel Sync]
        WORKFLOW[tgo-workflow - Automation Workflow]
        PLUGIN[tgo-plugin-runtime - Extension Runtime]
    end
    
    subgraph Infrastructure [Infrastructure]
        PostgreSQL[(PostgreSQL + pgvector)]
        Redis[(Redis)]
        WuKongIM[WuKongIM - IM Engine]
        Celery[Celery - Async Workers]
    end
    
    WEB --> API
    WIDGET --> API
    API --> AI
    API --> RAG
    API --> PLATFORM
    API --> WORKFLOW
    AI --> PLUGIN
    Backend --> Infrastructure
```

---

## 3. 微服务清单

| 服务名称 | 源码目录 | 默认端口 | 核心职责 |
| :--- | :--- | :--- | :--- |
| **tgo-api** | `repos/tgo-api` | 8000 | 核心业务逻辑、多租户管理、API 网关。 |
| **tgo-ai** | `repos/tgo-ai` | 8081 | 统一 LLM 调用接口、Agent 逻辑处理。 |
| **tgo-rag** | `repos/tgo-rag` | 8082 | 知识库解析、向量化、检索增强生成。 |
| **tgo-platform** | `repos/tgo-platform` | 8003 | 微信、企业微信等第三方渠道消息同步。 |
| **tgo-workflow** | `repos/tgo-workflow` | 8004 | 节点化工作流编排与执行引擎。 |
| **tgo-plugin-runtime** | `repos/tgo-plugin-runtime` | 8090 | MCP 工具及自定义插件的执行环境。 |
| **tgo-web** | `repos/tgo-web` | 80 | 管理后台前端，负责 Agent、知识库、设置等配置。 |
| **tgo-widget-app** | `repos/tgo-widget-app` | 80 | 嵌入在访客网站中的聊天对话框组件。 |

---

## 4. 技术栈

- **后端服务**:
  - 语言: Python 3.11+
  - 框架: FastAPI, SQLAlchemy 2.0
  - 异步任务: Celery + Redis
- **前端应用**:
  - 框架: React 19, TypeScript
  - 构建工具: Vite 7.x
  - 状态管理: Zustand
  - 样式: Tailwind CSS 4.x
- **基础设施**:
  - 数据库: PostgreSQL + pgvector (向量检索)
  - 缓存: Redis
  - 即时通讯: WuKongIM

---

## 5. 开发规范 (核心)

### 5.1 类型安全 (严格执行)
- **后端 (Python)**: 严禁使用 `dict` 传递业务数据，严禁使用 `Any` 类型。所有 API 接口、Service 方法必须定义明确的 Pydantic 模型或类型注解。
- **前端 (TypeScript)**: 严禁使用 `any` 类型。所有组件 Props、API 响应数据、状态管理必须定义完整的 Interface 或 Type。

---

## 5. 目录结构

```text
tgo/
├── repos/                  # 微服务源代码目录
│   ├── tgo-api/            # 核心服务
│   ├── tgo-web/            # 后台前端
│   ├── ...                 # 其他微服务
├── envs.docker/            # 生产环境 Docker 环境变量
├── envs.example/           # 环境变量配置模板
├── resources/              # 文档资源、架构图、截图
├── scripts/                # 部署和运维脚本
├── docs-site/              # 官方文档站点源码
├── Makefile                # 便捷构建指令
└── AGENTS.md               # 本文件 (AI 助手指南)
```

---

## 6. 常用开发命令

| 命令 | 描述 |
| :--- | :--- |
| `make build-all` | 构建并重启所有微服务镜像。 |
| `make build SERVICE=tgo-api` | 构建并重启指定的微服务镜像。 |
| `./tgo.sh` | 交互式部署与管理脚本。 |
| `docker compose up -d` | 使用默认配置启动所有服务。 |

---

## 7. 给 AI 代理的建议

1. **查阅分级文档**: 每一个核心微服务（如 `repos/tgo-api`, `repos/tgo-web`）都有其独立的 `AGENTS.md` 文件。在进行具体代码修改前，请务必阅读对应目录下的指南。
2. **遵循微服务边界**: 避免在不相关的服务间引入硬编码依赖。通过内部 API 进行跨服务通信。
3. **数据库迁移**: 所有的数据库变更必须通过 Alembic 生成迁移文件。后端服务通常在 `migrations/` 或 `alembic/` 目录下管理脚本。
4. **前端组件规范**: 遵循 React 19 最佳实践，UI 组件库主要使用 Tailwind CSS 构建。

---
*Created on 2026-01-12*
