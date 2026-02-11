// Package tools provides the tool registry and built-in tool implementations
// (fs_read, fs_write, fs_edit, shell_exec).
package tools

import (
	"context"
	"fmt"
	"log/slog"

	"github.com/tgoai/tgo-device-agent/internal/config"
	"github.com/tgoai/tgo-device-agent/internal/protocol"
	"github.com/tgoai/tgo-device-agent/internal/sandbox"
)

// Tool is the interface that all tools must implement.
type Tool interface {
	// Name returns the unique tool name (e.g. "fs_read").
	Name() string
	// Definition returns the MCP-compatible tool definition with JSON Schema.
	Definition() protocol.ToolDefinition
	// Execute runs the tool with the given arguments and returns a result.
	Execute(ctx context.Context, args map[string]interface{}) *protocol.ToolCallResult
}

// Registry holds registered tools and dispatches calls.
type Registry struct {
	tools map[string]Tool
	order []string // preserve registration order for listing
}

// NewRegistry creates a Registry with all built-in tools registered.
func NewRegistry(cfg *config.Config) *Registry {
	sb := sandbox.New(cfg)
	r := &Registry{
		tools: make(map[string]Tool),
	}

	// Register built-in tools
	r.Register(NewFSRead(sb, cfg))
	r.Register(NewFSWrite(sb, cfg))
	r.Register(NewFSEdit(sb, cfg))
	r.Register(NewShellExec(sb, cfg))

	slog.Info("tool registry initialized", "tool_count", len(r.tools))
	return r
}

// Register adds a tool to the registry.
func (r *Registry) Register(t Tool) {
	name := t.Name()
	r.tools[name] = t
	r.order = append(r.order, name)
	slog.Debug("tool registered", "name", name)
}

// ListTools returns all tool definitions in registration order.
func (r *Registry) ListTools() []protocol.ToolDefinition {
	defs := make([]protocol.ToolDefinition, 0, len(r.order))
	for _, name := range r.order {
		defs = append(defs, r.tools[name].Definition())
	}
	return defs
}

// CallTool dispatches a tool call by name.
func (r *Registry) CallTool(ctx context.Context, name string, args map[string]interface{}) *protocol.ToolCallResult {
	t, ok := r.tools[name]
	if !ok {
		return protocol.TextResult(
			fmt.Sprintf("Error: tool '%s' not found. Available tools: %v", name, r.order),
			true,
		)
	}
	return t.Execute(ctx, args)
}
