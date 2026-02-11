package tools

import (
	"bytes"
	"context"
	"fmt"
	"os/exec"
	"strings"
	"time"

	"github.com/tgoai/tgo-device-agent/internal/config"
	"github.com/tgoai/tgo-device-agent/internal/protocol"
	"github.com/tgoai/tgo-device-agent/internal/sandbox"
)

// ShellExec implements the shell_exec tool – runs shell commands.
type ShellExec struct {
	sb  *sandbox.Sandbox
	cfg *config.Config
}

// NewShellExec creates a new ShellExec tool.
func NewShellExec(sb *sandbox.Sandbox, cfg *config.Config) *ShellExec {
	return &ShellExec{sb: sb, cfg: cfg}
}

func (t *ShellExec) Name() string { return "shell_exec" }

func (t *ShellExec) Definition() protocol.ToolDefinition {
	return protocol.ToolDefinition{
		Name:        "shell_exec",
		Description: "Execute a shell command on the device. Returns stdout, stderr, and exit code. Commands run with a configurable timeout (default 60s). Output is truncated if it exceeds the maximum size.",
		InputSchema: map[string]interface{}{
			"type": "object",
			"properties": map[string]interface{}{
				"command": map[string]interface{}{
					"type":        "string",
					"description": "The shell command to execute",
				},
				"cwd": map[string]interface{}{
					"type":        "string",
					"description": "Working directory for the command. Optional – defaults to the agent's work root.",
				},
				"timeout_sec": map[string]interface{}{
					"type":        "integer",
					"description": "Timeout in seconds. Optional – defaults to 60.",
				},
				"env": map[string]interface{}{
					"type":        "object",
					"description": "Additional environment variables as key-value pairs. Optional.",
				},
			},
			"required": []string{"command"},
		},
	}
}

func (t *ShellExec) Execute(ctx context.Context, args map[string]interface{}) *protocol.ToolCallResult {
	command, _ := args["command"].(string)
	if command == "" {
		return protocol.TextResult("Error: 'command' argument is required", true)
	}

	// Security: check blocked commands
	if err := t.sb.ValidateCommand(command); err != nil {
		return protocol.TextResult(fmt.Sprintf("Error: %v", err), true)
	}

	// Timeout
	timeout := t.cfg.ShellTimeout
	if ts := intArg(args, "timeout_sec", 0); ts > 0 {
		timeout = time.Duration(ts) * time.Second
		// Cap at 5 minutes
		if timeout > 5*time.Minute {
			timeout = 5 * time.Minute
		}
	}
	cmdCtx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()

	// Find shell
	shell := findShell(t.cfg.AllowedShells)

	cmd := exec.CommandContext(cmdCtx, shell, "-c", command)

	// Working directory
	cwd, _ := args["cwd"].(string)
	if cwd != "" {
		resolved, err := t.sb.ResolvePath(cwd)
		if err != nil {
			return protocol.TextResult(fmt.Sprintf("Error: invalid cwd: %v", err), true)
		}
		cmd.Dir = resolved
	} else {
		cmd.Dir = t.sb.WorkRoot()
	}

	// Environment
	cmd.Env = cmd.Environ()
	if envMap, ok := args["env"].(map[string]interface{}); ok {
		for k, v := range envMap {
			cmd.Env = append(cmd.Env, fmt.Sprintf("%s=%v", k, v))
		}
	}

	// Capture output
	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	err := cmd.Run()

	// Determine exit code
	exitCode := 0
	timedOut := false
	if err != nil {
		if cmdCtx.Err() == context.DeadlineExceeded {
			timedOut = true
			exitCode = -1
		} else if exitErr, ok := err.(*exec.ExitError); ok {
			exitCode = exitErr.ExitCode()
		} else {
			return protocol.TextResult(fmt.Sprintf("Error executing command: %v", err), true)
		}
	}

	// Truncate output if needed
	stdoutStr := truncate(stdout.String(), t.cfg.MaxOutputBytes)
	stderrStr := truncate(stderr.String(), t.cfg.MaxOutputBytes)

	// Build result
	var result strings.Builder
	if timedOut {
		result.WriteString(fmt.Sprintf("[TIMEOUT after %v]\n", timeout))
	}
	if stdoutStr != "" {
		result.WriteString(stdoutStr)
	}
	if stderrStr != "" {
		if result.Len() > 0 {
			result.WriteString("\n--- stderr ---\n")
		}
		result.WriteString(stderrStr)
	}
	if result.Len() == 0 {
		result.WriteString("(no output)")
	}
	result.WriteString(fmt.Sprintf("\n\n[exit_code: %d]", exitCode))
	if timedOut {
		result.WriteString(" [timed_out: true]")
	}

	return protocol.TextResult(result.String(), exitCode != 0)
}

// findShell returns the first available shell from the allowed list.
func findShell(allowed []string) string {
	for _, sh := range allowed {
		if _, err := exec.LookPath(sh); err == nil {
			return sh
		}
	}
	// Fallback
	return "/bin/sh"
}

// truncate limits a string to maxBytes and appends a truncation notice.
func truncate(s string, maxBytes int64) string {
	if int64(len(s)) <= maxBytes {
		return s
	}
	return s[:maxBytes] + "\n... [output truncated]"
}
