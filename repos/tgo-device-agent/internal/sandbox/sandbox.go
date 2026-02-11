// Package sandbox provides security enforcement for file and command operations.
// It implements path whitelisting, command blacklisting, and output size limits.
package sandbox

import (
	"fmt"
	"log/slog"
	"os"
	"path/filepath"
	"strings"

	"github.com/tgoai/tgo-device-agent/internal/config"
)

// Sandbox enforces path and command safety policies.
type Sandbox struct {
	workRoot       string
	allowedPaths   []string
	deniedPaths    []string
	blockedCmds    []string
}

// New creates a Sandbox from the given config.
func New(cfg *config.Config) *Sandbox {
	// Resolve work root to absolute path
	workRoot, err := filepath.Abs(cfg.WorkRoot)
	if err != nil {
		workRoot = cfg.WorkRoot
	}

	// Resolve allowed paths to absolute
	allowed := make([]string, 0, len(cfg.AllowedPaths)+1)
	allowed = append(allowed, workRoot) // work root is always allowed
	for _, p := range cfg.AllowedPaths {
		abs, err := filepath.Abs(p)
		if err == nil {
			allowed = append(allowed, abs)
		}
	}

	// Resolve denied paths
	denied := make([]string, len(cfg.DeniedPaths))
	for i, p := range cfg.DeniedPaths {
		abs, err := filepath.Abs(p)
		if err == nil {
			denied[i] = abs
		} else {
			denied[i] = p
		}
	}

	sb := &Sandbox{
		workRoot:     workRoot,
		allowedPaths: allowed,
		deniedPaths:  denied,
		blockedCmds:  cfg.BlockedCommands,
	}

	slog.Info("sandbox initialized",
		"work_root", workRoot,
		"allowed_paths", len(allowed),
		"blocked_commands", len(cfg.BlockedCommands),
	)

	return sb
}

// WorkRoot returns the resolved work root directory.
func (s *Sandbox) WorkRoot() string {
	return s.workRoot
}

// ResolvePath resolves a potentially relative path and validates it
// is within the allowed paths.
func (s *Sandbox) ResolvePath(path string) (string, error) {
	if path == "" {
		return "", fmt.Errorf("empty path")
	}

	var resolved string
	if filepath.IsAbs(path) {
		resolved = filepath.Clean(path)
	} else {
		resolved = filepath.Join(s.workRoot, path)
		resolved = filepath.Clean(resolved)
	}

	// Resolve symlinks to prevent escape
	// Use EvalSymlinks only if the path exists (for reading)
	// For new files (writing), validate the parent directory
	realPath := resolved
	if _, err := os.Stat(resolved); err == nil {
		real, err := filepath.EvalSymlinks(resolved)
		if err == nil {
			realPath = real
		}
	} else {
		// File doesn't exist - validate parent directory
		parentDir := filepath.Dir(resolved)
		if _, err := os.Stat(parentDir); err == nil {
			real, err := filepath.EvalSymlinks(parentDir)
			if err == nil {
				realPath = filepath.Join(real, filepath.Base(resolved))
			}
		}
	}

	// Check path is within allowed paths
	if !s.isAllowed(realPath) {
		return "", fmt.Errorf("path '%s' is outside allowed directories", path)
	}

	// Check path is not in denied paths
	if s.isDenied(realPath) {
		return "", fmt.Errorf("path '%s' is in a denied directory", path)
	}

	return resolved, nil
}

// ValidateWrite performs additional validation for write operations.
func (s *Sandbox) ValidateWrite(resolvedPath string) error {
	// Prevent writing to critical system paths
	criticalPaths := []string{
		"/etc", "/usr", "/bin", "/sbin", "/var", "/System",
		"/Library", "/boot", "/proc", "/sys",
	}

	for _, cp := range criticalPaths {
		if strings.HasPrefix(resolvedPath, cp+"/") || resolvedPath == cp {
			return fmt.Errorf("write to system path '%s' is not allowed", resolvedPath)
		}
	}

	return nil
}

// ValidateCommand checks if a shell command is allowed.
func (s *Sandbox) ValidateCommand(command string) error {
	lower := strings.ToLower(strings.TrimSpace(command))

	for _, blocked := range s.blockedCmds {
		if strings.Contains(lower, strings.ToLower(blocked)) {
			return fmt.Errorf("command contains blocked pattern '%s'", blocked)
		}
	}

	// Block known dangerous patterns
	dangerousPatterns := []string{
		"> /dev/sda",
		"> /dev/hda",
		"chmod -R 777 /",
		"chown -R",
		"curl | sh",
		"curl | bash",
		"wget | sh",
		"wget | bash",
	}

	for _, pattern := range dangerousPatterns {
		if strings.Contains(lower, strings.ToLower(pattern)) {
			return fmt.Errorf("command matches dangerous pattern '%s'", pattern)
		}
	}

	return nil
}

// isAllowed returns true if the path is within any allowed directory.
func (s *Sandbox) isAllowed(path string) bool {
	for _, allowed := range s.allowedPaths {
		if path == allowed || strings.HasPrefix(path, allowed+string(filepath.Separator)) {
			return true
		}
	}
	return false
}

// isDenied returns true if the path is within any denied directory.
func (s *Sandbox) isDenied(path string) bool {
	for _, denied := range s.deniedPaths {
		if path == denied || strings.HasPrefix(path, denied+string(filepath.Separator)) {
			return true
		}
	}
	return false
}
