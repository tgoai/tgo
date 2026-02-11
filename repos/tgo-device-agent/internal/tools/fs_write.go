package tools

import (
	"context"
	"fmt"
	"os"
	"path/filepath"

	"github.com/tgoai/tgo-device-agent/internal/config"
	"github.com/tgoai/tgo-device-agent/internal/protocol"
	"github.com/tgoai/tgo-device-agent/internal/sandbox"
)

// FSWrite implements the fs_write tool – writes content to a file.
type FSWrite struct {
	sb  *sandbox.Sandbox
	cfg *config.Config
}

// NewFSWrite creates a new FSWrite tool.
func NewFSWrite(sb *sandbox.Sandbox, cfg *config.Config) *FSWrite {
	return &FSWrite{sb: sb, cfg: cfg}
}

func (t *FSWrite) Name() string { return "fs_write" }

func (t *FSWrite) Definition() protocol.ToolDefinition {
	return protocol.ToolDefinition{
		Name:        "fs_write",
		Description: "Write content to a file. Creates the file and parent directories if they do not exist. Supports overwrite and append modes.",
		InputSchema: map[string]interface{}{
			"type": "object",
			"properties": map[string]interface{}{
				"path": map[string]interface{}{
					"type":        "string",
					"description": "Absolute or relative path to the file to write",
				},
				"content": map[string]interface{}{
					"type":        "string",
					"description": "Content to write to the file",
				},
				"mode": map[string]interface{}{
					"type":        "string",
					"description": "Write mode: 'overwrite' (default) or 'append'",
					"enum":        []string{"overwrite", "append"},
					"default":     "overwrite",
				},
				"create_dirs": map[string]interface{}{
					"type":        "boolean",
					"description": "Create parent directories if they do not exist. Default: true",
					"default":     true,
				},
			},
			"required": []string{"path", "content"},
		},
	}
}

func (t *FSWrite) Execute(_ context.Context, args map[string]interface{}) *protocol.ToolCallResult {
	path, _ := args["path"].(string)
	content, _ := args["content"].(string)

	if path == "" {
		return protocol.TextResult("Error: 'path' argument is required", true)
	}

	// Check content size
	if int64(len(content)) > t.cfg.MaxWriteBytes {
		return protocol.TextResult(
			fmt.Sprintf("Error: content too large (%d bytes, max %d bytes)", len(content), t.cfg.MaxWriteBytes),
			true,
		)
	}

	// Sandbox validation
	resolved, err := t.sb.ResolvePath(path)
	if err != nil {
		return protocol.TextResult(fmt.Sprintf("Error: %v", err), true)
	}

	if err := t.sb.ValidateWrite(resolved); err != nil {
		return protocol.TextResult(fmt.Sprintf("Error: %v", err), true)
	}

	// Create parent dirs
	createDirs := boolArg(args, "create_dirs", true)
	if createDirs {
		dir := filepath.Dir(resolved)
		if err := os.MkdirAll(dir, 0o755); err != nil {
			return protocol.TextResult(fmt.Sprintf("Error creating directories: %v", err), true)
		}
	}

	// Determine file mode
	mode, _ := args["mode"].(string)
	if mode == "" {
		mode = "overwrite"
	}

	var flag int
	switch mode {
	case "append":
		flag = os.O_WRONLY | os.O_CREATE | os.O_APPEND
	default:
		flag = os.O_WRONLY | os.O_CREATE | os.O_TRUNC
	}

	f, err := os.OpenFile(resolved, flag, 0o644)
	if err != nil {
		return protocol.TextResult(fmt.Sprintf("Error opening file: %v", err), true)
	}
	defer f.Close()

	n, err := f.WriteString(content)
	if err != nil {
		return protocol.TextResult(fmt.Sprintf("Error writing file: %v", err), true)
	}

	return protocol.TextResult(
		fmt.Sprintf("Successfully wrote %d bytes to %s", n, path),
		false,
	)
}

// boolArg safely extracts a bool argument from the args map.
func boolArg(args map[string]interface{}, key string, def bool) bool {
	v, ok := args[key]
	if !ok {
		return def
	}
	b, ok := v.(bool)
	if !ok {
		return def
	}
	return b
}
