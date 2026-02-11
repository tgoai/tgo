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

// FSEdit implements the fs_edit tool – performs exact string replacements in files.
type FSEdit struct {
	sb  *sandbox.Sandbox
	cfg *config.Config
}

// NewFSEdit creates a new FSEdit tool.
func NewFSEdit(sb *sandbox.Sandbox, cfg *config.Config) *FSEdit {
	return &FSEdit{sb: sb, cfg: cfg}
}

func (t *FSEdit) Name() string { return "fs_edit" }

func (t *FSEdit) Definition() protocol.ToolDefinition {
	return protocol.ToolDefinition{
		Name:        "fs_edit",
		Description: "Perform exact string replacement in a file. Finds 'old_string' and replaces it with 'new_string'. By default replaces only the first occurrence; set 'replace_all' to true to replace all occurrences. The edit will fail if old_string is not found or is ambiguous (multiple matches when replace_all is false).",
		InputSchema: map[string]interface{}{
			"type": "object",
			"properties": map[string]interface{}{
				"path": map[string]interface{}{
					"type":        "string",
					"description": "Path to the file to edit",
				},
				"old_string": map[string]interface{}{
					"type":        "string",
					"description": "The exact text to find and replace",
				},
				"new_string": map[string]interface{}{
					"type":        "string",
					"description": "The replacement text",
				},
				"replace_all": map[string]interface{}{
					"type":        "boolean",
					"description": "If true, replace all occurrences. Default: false",
					"default":     false,
				},
			},
			"required": []string{"path", "old_string", "new_string"},
		},
	}
}

func (t *FSEdit) Execute(_ context.Context, args map[string]interface{}) *protocol.ToolCallResult {
	path, _ := args["path"].(string)
	oldStr, _ := args["old_string"].(string)
	newStr, _ := args["new_string"].(string)
	replaceAll := boolArg(args, "replace_all", false)

	if path == "" {
		return protocol.TextResult("Error: 'path' argument is required", true)
	}
	if oldStr == "" {
		return protocol.TextResult("Error: 'old_string' argument is required and cannot be empty", true)
	}

	// Sandbox validation
	resolved, err := t.sb.ResolvePath(path)
	if err != nil {
		return protocol.TextResult(fmt.Sprintf("Error: %v", err), true)
	}

	if err := t.sb.ValidateWrite(resolved); err != nil {
		return protocol.TextResult(fmt.Sprintf("Error: %v", err), true)
	}

	// Read existing content
	data, err := os.ReadFile(resolved)
	if err != nil {
		if os.IsNotExist(err) {
			return protocol.TextResult(fmt.Sprintf("Error: file not found: %s", path), true)
		}
		return protocol.TextResult(fmt.Sprintf("Error reading file: %v", err), true)
	}

	content := string(data)

	// Count occurrences
	count := strings.Count(content, oldStr)
	if count == 0 {
		return protocol.TextResult(
			fmt.Sprintf("Error: old_string not found in %s. Make sure the string matches exactly, including whitespace and indentation.", path),
			true,
		)
	}

	if !replaceAll && count > 1 {
		return protocol.TextResult(
			fmt.Sprintf("Error: old_string found %d times in %s. Provide more context to make it unique, or set replace_all=true.", count, path),
			true,
		)
	}

	// Perform replacement
	var newContent string
	if replaceAll {
		newContent = strings.ReplaceAll(content, oldStr, newStr)
	} else {
		newContent = strings.Replace(content, oldStr, newStr, 1)
	}

	// Check size limit
	if int64(len(newContent)) > t.cfg.MaxWriteBytes {
		return protocol.TextResult(
			fmt.Sprintf("Error: resulting file too large (%d bytes, max %d bytes)", len(newContent), t.cfg.MaxWriteBytes),
			true,
		)
	}

	// Write back
	if err := os.WriteFile(resolved, []byte(newContent), 0o644); err != nil {
		return protocol.TextResult(fmt.Sprintf("Error writing file: %v", err), true)
	}

	replacements := 1
	if replaceAll {
		replacements = count
	}

	return protocol.TextResult(
		fmt.Sprintf("Successfully applied %d replacement(s) in %s", replacements, path),
		false,
	)
}
