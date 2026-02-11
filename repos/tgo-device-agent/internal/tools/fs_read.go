package tools

import (
	"context"
	"fmt"
	"os"
	"strings"

	"github.com/tgoai/tgo-device-agent/internal/config"
	"github.com/tgoai/tgo-device-agent/internal/protocol"
	"github.com/tgoai/tgo-device-agent/internal/sandbox"
)

// FSRead implements the fs_read tool – reads file contents.
type FSRead struct {
	sb  *sandbox.Sandbox
	cfg *config.Config
}

// NewFSRead creates a new FSRead tool.
func NewFSRead(sb *sandbox.Sandbox, cfg *config.Config) *FSRead {
	return &FSRead{sb: sb, cfg: cfg}
}

func (t *FSRead) Name() string { return "fs_read" }

func (t *FSRead) Definition() protocol.ToolDefinition {
	return protocol.ToolDefinition{
		Name:        "fs_read",
		Description: "Read the contents of a file. Supports optional line offset and limit for partial reads. Returns the file content as text.",
		InputSchema: map[string]interface{}{
			"type": "object",
			"properties": map[string]interface{}{
				"path": map[string]interface{}{
					"type":        "string",
					"description": "Absolute or relative path to the file to read",
				},
				"offset": map[string]interface{}{
					"type":        "integer",
					"description": "Line number to start reading from (1-based). If negative, counts from end. Optional.",
				},
				"limit": map[string]interface{}{
					"type":        "integer",
					"description": "Maximum number of lines to read. Optional – reads entire file if omitted.",
				},
				"encoding": map[string]interface{}{
					"type":        "string",
					"description": "File encoding. Default: utf-8",
					"default":     "utf-8",
				},
			},
			"required": []string{"path"},
		},
	}
}

func (t *FSRead) Execute(_ context.Context, args map[string]interface{}) *protocol.ToolCallResult {
	path, _ := args["path"].(string)
	if path == "" {
		return protocol.TextResult("Error: 'path' argument is required", true)
	}

	// Sandbox validation
	resolved, err := t.sb.ResolvePath(path)
	if err != nil {
		return protocol.TextResult(fmt.Sprintf("Error: %v", err), true)
	}

	// Check file exists and size
	info, err := os.Stat(resolved)
	if err != nil {
		if os.IsNotExist(err) {
			return protocol.TextResult(fmt.Sprintf("Error: file not found: %s", path), true)
		}
		return protocol.TextResult(fmt.Sprintf("Error: %v", err), true)
	}
	if info.IsDir() {
		return protocol.TextResult(fmt.Sprintf("Error: '%s' is a directory, not a file", path), true)
	}
	if info.Size() > t.cfg.MaxReadBytes {
		return protocol.TextResult(
			fmt.Sprintf("Error: file too large (%d bytes, max %d bytes)", info.Size(), t.cfg.MaxReadBytes),
			true,
		)
	}

	// Read file
	data, err := os.ReadFile(resolved)
	if err != nil {
		return protocol.TextResult(fmt.Sprintf("Error reading file: %v", err), true)
	}

	content := string(data)

	// Apply offset/limit if provided
	offset := intArg(args, "offset", 0)
	limit := intArg(args, "limit", 0)

	if offset != 0 || limit > 0 {
		lines := strings.Split(content, "\n")
		totalLines := len(lines)

		startLine := 0
		if offset > 0 {
			startLine = offset - 1 // 1-based to 0-based
		} else if offset < 0 {
			startLine = totalLines + offset
		}
		if startLine < 0 {
			startLine = 0
		}
		if startLine > totalLines {
			startLine = totalLines
		}

		endLine := totalLines
		if limit > 0 {
			endLine = startLine + limit
			if endLine > totalLines {
				endLine = totalLines
			}
		}

		// Build numbered output
		var b strings.Builder
		for i := startLine; i < endLine; i++ {
			fmt.Fprintf(&b, "%6d|%s\n", i+1, lines[i])
		}
		content = b.String()
	}

	return protocol.TextResult(content, false)
}

// intArg safely extracts an int argument from the args map.
func intArg(args map[string]interface{}, key string, def int) int {
	v, ok := args[key]
	if !ok {
		return def
	}
	switch n := v.(type) {
	case float64:
		return int(n)
	case int:
		return n
	case int64:
		return int(n)
	}
	return def
}
