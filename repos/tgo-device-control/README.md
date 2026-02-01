# TGO Device Control Service

TGO Device Control 是一个设备控制服务，允许 AI Agent 远程控制用户的电脑或移动设备。

## 功能特性

- **设备连接管理**：通过 TCP JSON-RPC 协议管理设备连接，支持 Peekaboo 协议
- **MCP Agent**：内置基于 LLM 的自主 Agent，支持动态加载设备工具并进行推理决策
- **多设备支持**：支持桌面电脑（macOS 等）和移动设备
- **安全认证**：支持绑定码（首次注册）和设备令牌（重连）的双重认证机制
- **AgentOS 兼容**：兼容 `agno` (原 phidata) 的 RemoteAgent 协议

## 快速开始

### 环境要求

- Python 3.11+
- PostgreSQL 14+ (需支持 pgvector)
- Redis 6+
- OpenAI API Key (用于 MCP Agent 推理)

### 安装

```bash
# 安装依赖
poetry install

# 复制环境配置
cp .env.example .env

# 运行数据库迁移
alembic upgrade head

# 启动服务
uvicorn app.main:app --host 0.0.0.0 --port 8085 --reload
```

### Docker 部署

```bash
# 构建镜像
make build SERVICE=tgo-device-control

# 或者手动构建
docker build -t tgo-device-control .
```

## API 文档

服务启动后访问：
- Swagger UI: http://localhost:8085/docs
- ReDoc: http://localhost:8085/redoc
- TCP RPC 端口: 9876 (Peekaboo 设备连接)
- AgentOS 端口: 7778 (RemoteAgent 接口)

## 架构说明

```
app/
├── api/              # API 路由
│   └── v1/           # v1 版本 API
│       ├── agent.py      # MCP Agent API (运行、工具列表)
│       └── devices.py    # 设备管理 API
├── core/             # 核心模块
│   ├── database.py   # 数据库连接
│   └── logging.py    # 日志配置
├── models/           # 数据库模型
│   └── device.py     # 设备模型
├── schemas/          # Pydantic 模型
│   ├── agent_events.py # Agent 运行事件
│   ├── device.py     # 设备 Schema
│   └── tcp_rpc.py    # TCP JSON-RPC Schema
├── services/         # 业务服务
│   ├── computer_use/ # Agent 核心逻辑
│   │   └── mcp_agent.py  # 自主 MCP Agent 实现
│   ├── bind_code_service.py # 绑定码服务 (Redis)
│   ├── device_service.py    # 设备数据库服务
│   ├── tcp_connection_manager.py # TCP 连接管理
│   └── tcp_rpc_server.py    # TCP JSON-RPC 服务器 (Peekaboo)
├── agentos_server.py # AgentOS 兼容服务器
├── config.py         # 配置
└── main.py           # 应用入口
```

## 设备连接流程 (Peekaboo)

1. **生成绑定码**：用户在管理后台生成 6 位绑定码
2. **设备认证**：
   - **首次注册**：设备发送 `auth` 请求，携带 `bindCode` 和 `deviceInfo`
   - **获取令牌**：服务端验证成功后返回 `deviceToken` 和 `deviceId`
3. **重连机制**：设备断线后，使用 `deviceToken` 进行快速重连认证
4. **工具发现**：服务端通过 `tools/list` 动态获取设备支持的控制指令
5. **指令执行**：Agent 通过 `tools/call` 下发控制命令

## MCP Agent

系统内置了 `McpAgent`，它能够：
1. 自动发现已连接设备支持的所有工具
2. 将工具定义转换为 OpenAI Function Calling 格式
3. 利用 LLM (如 GPT-4o) 进行多轮思考和自主决策
4. 实时流式输出执行状态和推理过程

## 许可证

Copyright © 2026 TGO-Tech
