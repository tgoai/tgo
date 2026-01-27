# TGO Device Control API Reference

本文档描述了 TGO Device Control 服务的 REST API 接口。

## Base URL

```
http://{host}:8085/v1
```

## 认证

所有 API 请求需要在 Header 中携带认证信息：

```
Authorization: Bearer {access_token}
```

---

## 设备管理 API

### 获取设备列表

获取项目下的所有设备。

**请求**

```
GET /devices?project_id={project_id}
```

**参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| project_id | UUID | 是 | 项目 ID |
| device_type | string | 否 | 设备类型：`desktop` / `mobile` |
| status | string | 否 | 状态：`online` / `offline` |
| skip | integer | 否 | 跳过数量，默认 0 |
| limit | integer | 否 | 返回数量，默认 50，最大 100 |

**响应**

```json
{
  "devices": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "project_id": "650e8400-e29b-41d4-a716-446655440001",
      "device_type": "desktop",
      "device_name": "MacBook Pro",
      "os": "darwin",
      "os_version": "14.2.1",
      "screen_resolution": "2560x1440",
      "status": "online",
      "last_seen_at": "2026-01-27T10:30:00Z",
      "created_at": "2026-01-27T09:00:00Z"
    }
  ],
  "total": 1
}
```

---

### 获取设备详情

获取单个设备的详细信息。

**请求**

```
GET /devices/{device_id}?project_id={project_id}
```

**参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| device_id | UUID | 是 | 设备 ID |
| project_id | UUID | 是 | 项目 ID |

**响应**

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "project_id": "650e8400-e29b-41d4-a716-446655440001",
  "device_type": "desktop",
  "device_name": "MacBook Pro",
  "os": "darwin",
  "os_version": "14.2.1",
  "screen_resolution": "2560x1440",
  "status": "online",
  "last_seen_at": "2026-01-27T10:30:00Z",
  "created_at": "2026-01-27T09:00:00Z"
}
```

---

### 生成绑定码

生成一个用于设备注册的绑定码。

**请求**

```
POST /devices/bind-code?project_id={project_id}
```

**参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| project_id | UUID | 是 | 项目 ID |

**响应**

```json
{
  "bind_code": "ABC123",
  "expires_at": "2026-01-27T10:35:00Z"
}
```

**说明**

- 绑定码为 6 位大写字母和数字组合
- 有效期为 5 分钟
- 绑定码为一次性使用

---

### 更新设备

更新设备信息（目前仅支持修改名称）。

**请求**

```
PATCH /devices/{device_id}?project_id={project_id}
```

**参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| device_id | UUID | 是 | 设备 ID |
| project_id | UUID | 是 | 项目 ID |

**请求体**

```json
{
  "device_name": "新设备名称"
}
```

**响应**

返回更新后的设备详情。

---

### 删除设备

删除（解绑）一个设备。

**请求**

```
DELETE /devices/{device_id}?project_id={project_id}
```

**参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| device_id | UUID | 是 | 设备 ID |
| project_id | UUID | 是 | 项目 ID |

**响应**

```json
{
  "success": true,
  "message": "Device deleted successfully"
}
```

---

### 断开设备连接

强制断开一个在线设备的连接。

**请求**

```
POST /devices/{device_id}/disconnect?project_id={project_id}
```

**参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| device_id | UUID | 是 | 设备 ID |
| project_id | UUID | 是 | 项目 ID |

**响应**

```json
{
  "success": true,
  "message": "Device disconnected"
}
```

---

## MCP 工具 API

### 获取工具列表

获取可用的设备控制工具定义。

**请求**

```
GET /mcp/tools?project_id={project_id}
```

**参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| project_id | UUID | 是 | 项目 ID |
| device_id | UUID | 否 | 指定设备 ID |

**响应**

```json
{
  "tools": [
    {
      "name": "computer_screenshot",
      "description": "Capture a screenshot of the device screen",
      "inputSchema": {
        "type": "object",
        "properties": {
          "device_id": {
            "type": "string",
            "description": "Device ID to capture screenshot from"
          },
          "region": {
            "type": "object",
            "description": "Optional region to capture",
            "properties": {
              "x": { "type": "integer" },
              "y": { "type": "integer" },
              "width": { "type": "integer" },
              "height": { "type": "integer" }
            }
          }
        },
        "required": ["device_id"]
      }
    }
  ]
}
```

---

### 调用工具

执行一个 MCP 工具调用。

**请求**

```
POST /mcp/tools/call
```

**请求体**

```json
{
  "name": "computer_screenshot",
  "arguments": {
    "device_id": "550e8400-e29b-41d4-a716-446655440000"
  },
  "project_id": "650e8400-e29b-41d4-a716-446655440001"
}
```

**响应**

```json
{
  "success": true,
  "content": {
    "screenshot_url": "https://...",
    "width": 2560,
    "height": 1440
  },
  "error": null
}
```

---

### MCP 协议端点

标准 MCP 协议端点，用于 AI Agent 集成。

**请求**

```
POST /mcp
Content-Type: application/json
```

**请求体 (initialize)**

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2024-11-05",
    "capabilities": {},
    "clientInfo": {
      "name": "tgo-ai",
      "version": "1.0.0"
    }
  }
}
```

**响应**

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "protocolVersion": "2024-11-05",
    "capabilities": {
      "tools": {}
    },
    "serverInfo": {
      "name": "tgo-device-control",
      "version": "1.0.0"
    }
  }
}
```

**请求体 (tools/list)**

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/list",
  "params": {}
}
```

**请求体 (tools/call)**

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "computer_screenshot",
    "arguments": {
      "device_id": "550e8400-e29b-41d4-a716-446655440000"
    }
  }
}
```

---

## 错误响应

所有错误响应遵循以下格式：

```json
{
  "detail": "Error message"
}
```

### HTTP 状态码

| 状态码 | 说明 |
|--------|------|
| 200 | 成功 |
| 400 | 请求参数错误 |
| 401 | 未认证 |
| 403 | 无权限 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |

---

## 数据模型

### Device

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 设备唯一标识 |
| project_id | UUID | 所属项目 ID |
| device_type | string | 设备类型：`desktop` / `mobile` |
| device_name | string | 设备名称 |
| os | string | 操作系统 |
| os_version | string | 系统版本 |
| screen_resolution | string | 屏幕分辨率 |
| status | string | 状态：`online` / `offline` |
| last_seen_at | datetime | 最后在线时间 |
| created_at | datetime | 创建时间 |

### BindCode

| 字段 | 类型 | 说明 |
|------|------|------|
| bind_code | string | 6位绑定码 |
| expires_at | datetime | 过期时间 |

### MCPTool

| 字段 | 类型 | 说明 |
|------|------|------|
| name | string | 工具名称 |
| description | string | 工具描述 |
| inputSchema | object | JSON Schema 格式的输入参数定义 |

---

*文档版本: 1.0.0*
*最后更新: 2026-01-27*
