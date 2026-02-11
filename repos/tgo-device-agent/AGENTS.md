# tgo-device-agent – AI Agent Guide

## 概述

`tgo-device-agent` 是一个 Go 编写的被控端程序，运行在受管设备上，通过 TCP JSON-RPC 2.0 协议连接到 `tgo-device-control` 服务。它向 AI Agent 暴露文件读写和 Shell 执行等工具能力。

## 架构

```
cmd/agent/main.go          → 入口：CLI 参数解析、信号处理、启动 Client
internal/config/config.go  → 配置结构与加载
internal/protocol/         → JSON-RPC 2.0 消息类型（auth、tools/list、tools/call）
internal/transport/client.go → TCP 客户端：连接、认证、心跳、重连、消息派发
internal/tools/registry.go → 工具注册中心
internal/tools/fs_read.go  → fs_read 工具
internal/tools/fs_write.go → fs_write 工具
internal/tools/fs_edit.go  → fs_edit 工具
internal/tools/shell_exec.go → shell_exec 工具
internal/sandbox/sandbox.go → 安全沙箱：路径验证、命令过滤
```

## 核心协议

- 协议基础文档: `../tgo-device-control/docs/json-rpc.md`
- 消息格式: 换行符分隔的 JSON (`\n`-delimited JSON)
- 认证方法: `auth` (bindCode 或 deviceToken)
- 设备主动上报: `tools/list` 响应、`pong` 心跳
- 服务端下发: `tools/call`、`ping`

## 关键接口

### Tool 接口 (internal/tools/registry.go)

```go
type Tool interface {
    Name() string
    Definition() protocol.ToolDefinition
    Execute(ctx context.Context, args map[string]interface{}) *protocol.ToolCallResult
}
```

添加新工具时实现此接口并在 `NewRegistry()` 中调用 `r.Register()`。

## 开发注意事项

1. **不使用外部依赖** – 当前版本仅使用 Go 标准库。
2. **类型安全** – 所有 JSON-RPC 消息均有对应的 Go struct，不使用 `interface{}`（工具参数除外，因为 MCP 规范要求动态 schema）。
3. **安全优先** – 所有文件/命令操作必须经过 sandbox 验证。
4. **幂等重连** – TCP 断线后自动重连，DeviceToken 持久化确保身份不变。
