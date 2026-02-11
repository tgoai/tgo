# tgo-device-agent

被控端 Agent — 运行在受管设备上，通过 TCP 长连接接入 `tgo-device-control` 服务，向 AI Agent 提供文件读写、编辑和 Shell 执行能力。

## 功能特性

- **TCP JSON-RPC 2.0** 长连接，与 `tgo-device-control` 实时通信
- **自动认证**: 首次使用 `bindCode` 注册，之后凭 `deviceToken` 自动重连
- **指数退避重连**: 断线自动重连，避免服务端过载
- **4 个内置工具**:
  - `fs_read` – 读取文件内容（支持行号范围）
  - `fs_write` – 创建/覆盖/追加文件
  - `fs_edit` – 精确字符串替换
  - `shell_exec` – 执行 Shell 命令
- **安全沙箱**: 路径白名单、命令黑名单、输出截断、超时控制
- **可扩展**: 通过 `Tool` 接口注册自定义工具

## 快速开始

### 构建

```bash
make build
```

### 首次运行（使用绑定码）

```bash
./bin/tgo-device-agent \
  --server your-control-server:9876 \
  --bind-code ABC123 \
  --work-root /path/to/workspace \
  --log-level info
```

### 后续运行（自动使用已保存的 Token）

```bash
./bin/tgo-device-agent \
  --server your-control-server:9876 \
  --work-root /path/to/workspace
```

### 使用配置文件

```bash
./bin/tgo-device-agent --config configs/config.json
```

## 启动参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--server` | 控制服务地址 `host:port` | `localhost:9876` |
| `--bind-code` | 首次注册绑定码 | – |
| `--name` | 设备显示名称 | 主机名 |
| `--work-root` | 文件操作根目录 | `.` |
| `--log-level` | 日志级别: debug/info/warn/error | `info` |
| `--config` | JSON 配置文件路径 | – |
| `--version` | 显示版本 | – |

## 认证流程

```
┌──────────────┐                    ┌──────────────────┐
│ device-agent │                    │ device-control   │
└──────┬───────┘                    └────────┬─────────┘
       │  TCP connect                        │
       │ ──────────────────────────────────> │
       │                                     │
       │  auth(bindCode / deviceToken)       │
       │ ──────────────────────────────────> │
       │                                     │
       │  {deviceId, deviceToken, projectId} │
       │ <────────────────────────────────── │
       │                                     │
       │  ← 保存 deviceToken 到本地文件       │
       │                                     │
       │  tools/list (服务端请求)             │
       │ <────────────────────────────────── │
       │                                     │
       │  {tools: [...]}                     │
       │ ──────────────────────────────────> │
       │                                     │
       │  heartbeat (周期性 pong)             │
       │ ──────────────────────────────────> │
```

## 工具 Schema

### fs_read

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `path` | string | 是 | 文件路径 |
| `offset` | int | 否 | 起始行号（1-based，负数从尾部计算） |
| `limit` | int | 否 | 读取行数 |

### fs_write

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `path` | string | 是 | 文件路径 |
| `content` | string | 是 | 写入内容 |
| `mode` | string | 否 | `overwrite`（默认）或 `append` |
| `create_dirs` | bool | 否 | 是否自动创建父目录（默认 true） |

### fs_edit

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `path` | string | 是 | 文件路径 |
| `old_string` | string | 是 | 要替换的精确文本 |
| `new_string` | string | 是 | 替换后的文本 |
| `replace_all` | bool | 否 | 替换所有匹配（默认 false） |

### shell_exec

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `command` | string | 是 | Shell 命令 |
| `cwd` | string | 否 | 工作目录（默认 work_root） |
| `timeout_sec` | int | 否 | 超时秒数（默认 60，上限 300） |
| `env` | object | 否 | 额外环境变量 |

## 安全机制

### 文件沙箱
- 所有文件操作只允许在 `work_root` 及 `allowed_paths` 内执行
- 自动解析符号链接防止路径逃逸
- 阻止写入系统关键路径（`/etc`、`/usr`、`/bin` 等）
- 读写均有大小限制（默认 10 MB）

### 命令安全
- 内置危险命令黑名单（`rm -rf /`、`mkfs`、`dd if=/dev/zero` 等）
- 检测危险模式（`curl | sh`、`chmod -R 777 /` 等）
- 输出截断（默认 1 MB）
- 执行超时（默认 60 秒，上限 5 分钟）

## 故障排查

| 问题 | 排查方向 |
|------|---------|
| 连接超时 | 检查服务地址和端口，防火墙规则 |
| 认证失败 | 确认 bindCode 未过期，或 deviceToken 文件未损坏 |
| 工具不可见 | 检查 device-control 日志中的 `tools/list` 调用 |
| 路径拒绝 | 确认 `--work-root` 设置正确，路径在白名单内 |
| 命令被拦截 | 检查 `blocked_commands` 配置 |

## 项目结构

```
tgo-device-agent/
├── cmd/agent/          # 程序入口
│   └── main.go
├── internal/
│   ├── config/         # 配置加载
│   ├── protocol/       # JSON-RPC 消息类型
│   ├── transport/      # TCP 客户端、重连、心跳
│   ├── tools/          # 工具注册中心 & 4 个工具实现
│   └── sandbox/        # 安全沙箱（路径验证、命令过滤）
├── configs/            # 配置示例
├── Dockerfile
├── Makefile
└── README.md
```

## 扩展工具

实现 `tools.Tool` 接口并在 `Registry` 中注册：

```go
type MyTool struct{}

func (t *MyTool) Name() string { return "my_tool" }
func (t *MyTool) Definition() protocol.ToolDefinition { /* ... */ }
func (t *MyTool) Execute(ctx context.Context, args map[string]interface{}) *protocol.ToolCallResult { /* ... */ }

// 在 NewRegistry() 中添加:
// r.Register(&MyTool{})
```

## 与 tgo 生态集成

```
tgo-ai (Agent) ──MCP──> tgo-device-control ──TCP──> tgo-device-agent
    │                         │                          │
    │  bound_device_id        │  MCP 透传                │  工具执行
    │  POST /mcp/{device_id}  │  tools/call              │  fs_read / shell_exec
```
