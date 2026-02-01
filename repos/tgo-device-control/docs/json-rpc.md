# JSON-RPC Remote Control Protocol

Peekaboo 支持作为 JSON-RPC 2.0 代理客户端连接到远程控制服务器，接收并执行自动化命令。这使得远程控制 macOS 桌面自动化成为可能。

## 架构概览

```
┌─────────────────┐                    ┌─────────────────┐
│  Control Server │◄──── TCP ────────►│  Peekaboo Agent │
│  (Your Server)  │   JSON-RPC 2.0    │  (peekaboo rpc) │
└─────────────────┘                    └─────────────────┘
        │                                      │
        │  1. Agent connects                   │
        │  2. Agent authenticates              │
        │  3. Server sends commands ──────────►│
        │  4. Agent executes & responds ◄──────│
        │                                      │
```

## 快速开始

## 协议规范

使用标准 JSON-RPC 2.0 协议，消息以换行符 (`\n`) 分隔。

### 连接流程

```
1. Agent 建立 TCP 连接
2. Agent 发送 auth 请求
3. Server 返回认证结果
4. 进入消息循环：Server 发请求，Agent 返响应
```

### 认证

支持两种认证方式：
- **首次注册**: 使用一次性绑定码 (`bindCode`)，设备将被注册到关联的项目
- **重新连接**: 使用设备令牌 (`deviceToken`)，已注册设备的重连认证

#### 首次注册 (使用 bindCode)

**Device → Server:**

```json
{
  "jsonrpc": "2.0",
  "method": "auth",
  "params": {
    "bindCode": "ABC123",
    "deviceInfo": {
      "name": "My MacBook Pro",
      "version": "3.0.0",
      "os": "macOS",
      "osVersion": "14.0",
      "screenResolution": "1920x1080"
    }
  },
  "id": 0
}
```

**Server → Device (成功):**

```json
{
  "jsonrpc": "2.0",
  "result": {
    "status": "ok",
    "deviceId": "550e8400-e29b-41d4-a716-446655440000",
    "deviceToken": "eyJhbGciOiJIUzI1NiIs...",
    "projectId": "660e8400-e29b-41d4-a716-446655440001",
    "message": "Device registered successfully"
  },
  "id": 0
}
```

> **重要**: 设备必须保存返回的 `deviceToken`，用于后续重新连接。

#### 重新连接 (使用 deviceToken)

**Device → Server:**

```json
{
  "jsonrpc": "2.0",
  "method": "auth",
  "params": {
    "deviceToken": "eyJhbGciOiJIUzI1NiIs...",
    "deviceInfo": {
      "name": "My MacBook Pro",
      "version": "3.0.0"
    }
  },
  "id": 0
}
```

**Server → Device (成功):**

```json
{
  "jsonrpc": "2.0",
  "result": {
    "status": "ok",
    "deviceId": "550e8400-e29b-41d4-a716-446655440000",
    "projectId": "660e8400-e29b-41d4-a716-446655440001",
    "message": "Reconnected successfully"
  },
  "id": 0
}
```

#### 认证失败

**Server → Device (无效绑定码):**

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32001,
    "message": "Authentication failed: invalid or expired bind code"
  },
  "id": 0
}
```

**Server → Device (无效设备令牌):**

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32001,
    "message": "Authentication failed: invalid device token"
  },
  "id": 0
}
```

#### 认证参数说明

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `bindCode` | string | 二选一 | 6位绑定码，首次注册时使用 |
| `deviceToken` | string | 二选一 | 设备令牌，重连时使用 |
| `deviceInfo.name` | string | 是 | 设备名称 |
| `deviceInfo.version` | string | 是 | 客户端版本号 |
| `deviceInfo.os` | string | 首次必填 | 操作系统名称 |
| `deviceInfo.osVersion` | string | 否 | 操作系统版本 |
| `deviceInfo.screenResolution` | string | 否 | 屏幕分辨率 (如 "1920x1080") |

#### 认证响应说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `status` | string | 固定为 "ok" |
| `deviceId` | string | 设备 UUID，用于后续操作 |
| `deviceToken` | string | 设备令牌，仅首次注册返回，设备需保存用于重连 |
| `projectId` | string | 设备所属项目 ID |
| `message` | string | 人类可读的状态消息 |

## 支持的方法

### `tools/list` - 列出可用工具

返回所有可用的自动化工具及其参数定义。

**Server → Agent:**

```json
{
  "jsonrpc": "2.0",
  "method": "tools/list",
  "params": {},
  "id": 1
}
```

**Agent → Server:**

```json
{
  "jsonrpc": "2.0",
  "result": {
    "tools": [
      {
        "name": "see",
        "description": "Capture UI state with optional annotation",
        "inputSchema": {
          "type": "object",
          "properties": {
            "app_target": { "type": "string", "description": "Target app name or bundle ID" },
            "annotate": { "type": "boolean", "description": "Add element annotations" }
          }
        }
      },
      {
        "name": "click",
        "description": "Click on an element or coordinates",
        "inputSchema": {
          "type": "object",
          "properties": {
            "query": { "type": "string", "description": "Element query or ID" },
            "coords": { "type": "string", "description": "x,y coordinates" }
          }
        }
      }
    ]
  },
  "id": 1
}
```

### `tools/call` - 执行工具

调用指定的自动化工具。

**Server → Agent:**

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "see",
    "arguments": {
      "app_target": "Safari",
      "annotate": true
    }
  },
  "id": 2
}
```

**Agent → Server (成功):**

```json
{
  "jsonrpc": "2.0",
  "result": {
    "content": [
      {
        "type": "text",
        "text": "Captured Safari window with 15 UI elements"
      },
      {
        "type": "image",
        "data": "iVBORw0KGgoAAAANSUhEUgAA...",
        "mimeType": "image/png"
      }
    ],
    "isError": false
  },
  "id": 2
}
```

**Agent → Server (工具执行错误):**

```json
{
  "jsonrpc": "2.0",
  "result": {
    "content": [
      {
        "type": "text",
        "text": "Error: Application Safari is not running"
      }
    ],
    "isError": true
  },
  "id": 2
}
```

### `ping` - 健康检查

用于心跳检测和连接保活。

**Server → Agent:**

```json
{
  "jsonrpc": "2.0",
  "method": "ping",
  "id": 3
}
```

**Agent → Server:**

```json
{
  "jsonrpc": "2.0",
  "result": {
    "pong": true,
    "timestamp": 1706428800
  },
  "id": 3
}
```

## 可用工具列表

| 工具名 | 描述 | 关键参数 |
|--------|------|----------|
| `see` | 捕获 UI 状态并标注元素 | `app_target`, `annotate`, `path` |
| `image` | 截图 | `mode`, `app_target`, `retina` |
| `click` | 点击元素或坐标 | `query`, `on`, `coords`, `double`, `right` |
| `type` | 输入文本 | `text`, `clear`, `delay_ms` |
| `scroll` | 滚动 | `direction`, `ticks`, `on` |
| `hotkey` | 快捷键组合 | `keys` |
| `swipe` | 滑动手势 | `from`, `to`, `duration` |
| `drag` | 拖拽 | `from`, `to`, `modifiers` |
| `move` | 移动光标 | `to`, `coords` |
| `app` | 应用管理 | `action`, `name`, `bundle_id` |
| `window` | 窗口管理 | `action`, `app`, `title` |
| `menu` | 菜单操作 | `action`, `app`, `path` |
| `dock` | Dock 操作 | `action`, `app` |
| `dialog` | 对话框处理 | `action`, `button` |
| `space` | 桌面空间管理 | `action`, `index` |
| `clipboard` | 剪贴板操作 | `action`, `text` |
| `paste` | 粘贴 | `text`, `target` |
| `list` | 列出信息 | `type` |
| `permissions` | 权限检查 | `action` |
| `sleep` | 延迟 | `ms` |
| `analyze` | AI 分析 | `prompt`, `image` |

## 错误码

| 错误码 | 名称 | 描述 |
|--------|------|------|
| `-32700` | Parse error | 无效的 JSON |
| `-32600` | Invalid Request | 无效的 JSON-RPC 请求 |
| `-32601` | Method not found | 方法不存在 |
| `-32602` | Invalid params | 无效的参数 |
| `-32603` | Internal error | 内部错误 |
| `-32001` | Auth failed | 认证失败 |
| `-32002` | Tool not found | 工具不存在 |
| `-32003` | Tool execution failed | 工具执行失败 |
| `-32004` | Connection closed | 连接已关闭 |

## 客户端连接示例

### Python 客户端示例

```python
import socket
import json

def connect_to_server(host="localhost", port=9876, device_token=None, bind_code=None):
    """连接到 TGO Device Control 服务器"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))
    print(f"Connected to {host}:{port}")

    # 构建认证请求
    auth_params = {
        "deviceInfo": {
            "name": "My MacBook Pro",
            "version": "3.0.0",
            "os": "macOS",
            "osVersion": "14.0",
            "screenResolution": "1920x1080"
        }
    }

    if device_token:
        auth_params["deviceToken"] = device_token
    elif bind_code:
        auth_params["bindCode"] = bind_code
    else:
        raise ValueError("Either device_token or bind_code is required")

    auth_request = {
        "jsonrpc": "2.0",
        "method": "auth",
        "params": auth_params,
        "id": 0
    }

    sock.send(json.dumps(auth_request).encode() + b"\n")
    response = json.loads(sock.recv(4096).decode())

    if "error" in response:
        print(f"Auth failed: {response['error']['message']}")
        sock.close()
        return None

    result = response["result"]
    print(f"Authenticated! Device ID: {result['deviceId']}")

    # 首次注册时保存 device_token
    if "deviceToken" in result:
        print(f"Save this token for reconnection: {result['deviceToken']}")

    return sock

if __name__ == "__main__":
    # 首次注册 (从 Web UI 获取绑定码)
    # sock = connect_to_server(bind_code="ABC123")

    # 重新连接 (使用保存的设备令牌)
    sock = connect_to_server(device_token="your-saved-device-token")
```

> **注意**: 以上是客户端示例。服务端由 TGO Device Control 服务实现，使用绑定码/设备令牌进行认证。

## 断线重连

Agent 默认启用自动重连，使用指数退避策略：

1. 初始延迟：`--retry-delay` 秒（默认 1 秒）
2. 每次失败后延迟翻倍
3. 最大延迟：30 秒
4. 最大重试次数：`--max-retries`（0 表示无限重试）

禁用重连：

```bash
peekaboo rpc connect --host server.example.com --token "xxx" --no-reconnect
```

## 安全建议

1. **绑定码安全**: 绑定码有效期默认为 5 分钟，且为一次性使用
2. **设备令牌保护**: 设备应安全存储 deviceToken，避免泄露
3. **限制网络访问**: 通过防火墙限制可连接的 IP 地址
4. **使用 TLS**: 在生产环境中，通过 TLS 隧道（如 stunnel）加密连接
5. **监控连接**: 记录所有连接尝试和命令执行
6. **设备管理**: 可通过 Web UI 随时撤销设备的访问权限

## 与 MCP 的区别

| 特性 | MCP (`peekaboo mcp`) | JSON-RPC (`peekaboo rpc`) |
|------|----------------------|---------------------------|
| 连接方向 | 客户端连接 Peekaboo | Peekaboo 连接服务器 |
| 传输协议 | stdio (管道) | TCP socket |
| 主要用途 | Claude Desktop/Cursor 集成 | 远程自动化控制 |
| 认证 | 无（本地进程） | 绑定码 / 设备令牌 |
| 重连 | 不适用 | 支持自动重连 |

## 故障排除

### 连接失败

```
Error: Connection failed: Failed to resolve host
```

- 检查主机名是否正确
- 确认网络连接正常
- 验证防火墙设置

### 绑定码认证失败

```
Error: Authentication failed: invalid or expired bind code
```

- 确认绑定码未过期（有效期 5 分钟）
- 确认绑定码未被使用（一次性使用）
- 从 Web UI 重新生成绑定码

### 设备令牌认证失败

```
Error: Authentication failed: invalid device token
```

- 确认设备令牌正确
- 检查设备是否已被管理员从项目中移除
- 使用新的绑定码重新注册设备

### 工具执行失败

```
Error: Tool execution failed: ...
```

- 确认 macOS 权限已授予（`peekaboo permissions status`）
- 检查目标应用是否正在运行
- 查看详细错误信息
