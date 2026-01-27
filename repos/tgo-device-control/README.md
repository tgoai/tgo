# TGO Device Control Service

TGO Device Control 是一个设备控制服务，允许 AI 员工远程控制用户的电脑或移动设备。

## 功能特性

- **设备连接管理**：通过 WebSocket 管理设备连接
- **MCP 工具接口**：为 AI 员工提供标准的 MCP 工具接口
- **多设备支持**：支持桌面电脑和移动设备
- **安全认证**：使用绑定码进行设备注册

## 快速开始

### 环境要求

- Python 3.11+
- PostgreSQL 14+
- Redis 6+

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
docker build -t tgo-device-control .

# 运行容器
docker run -p 8085:8085 --env-file .env tgo-device-control
```

## API 文档

服务启动后访问：
- Swagger UI: http://localhost:8085/docs
- ReDoc: http://localhost:8085/redoc

## 架构说明

```
app/
├── api/              # API 路由
│   ├── v1/           # v1 版本 API
│   │   ├── devices.py    # 设备管理 API
│   │   └── mcp.py        # MCP 工具 API
│   └── websocket.py  # WebSocket 端点
├── core/             # 核心模块
│   ├── database.py   # 数据库连接
│   └── logging.py    # 日志配置
├── models/           # 数据库模型
│   └── device.py     # 设备模型
├── schemas/          # Pydantic 模型
│   ├── device.py     # 设备 Schema
│   └── mcp.py        # MCP Schema
├── services/         # 业务服务
│   ├── device_manager.py     # 设备连接管理
│   ├── device_service.py     # 设备数据库服务
│   ├── mcp_server.py         # MCP 服务
│   └── websocket_server.py   # WebSocket 处理
├── config.py         # 配置
└── main.py           # 应用入口
```

## MCP 工具列表

| 工具名 | 描述 |
|--------|------|
| `computer_screenshot` | 截取屏幕 |
| `computer_mouse_click` | 鼠标点击 |
| `computer_mouse_double_click` | 鼠标双击 |
| `computer_mouse_move` | 移动鼠标 |
| `computer_mouse_drag` | 鼠标拖拽 |
| `computer_keyboard_type` | 键盘输入 |
| `computer_keyboard_hotkey` | 组合键 |
| `computer_keyboard_press` | 按键 |
| `computer_scroll` | 滚动 |
| `computer_get_screen_size` | 获取屏幕尺寸 |
| `computer_get_cursor_position` | 获取鼠标位置 |

## 设备连接流程

1. 用户在管理后台生成绑定码
2. 用户在控制端输入绑定码
3. 控制端通过 WebSocket 连接到服务
4. 服务验证绑定码并注册设备
5. 设备保持连接，等待指令

## 许可证

Copyright © 2026 TGO-Tech
