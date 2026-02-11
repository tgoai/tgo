// Package config provides application configuration via environment variables,
// config file, and CLI flags.
package config

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"time"
)

// Config holds all runtime settings for the device agent.
type Config struct {
	// Server connection
	ServerHost string `json:"server_host"`
	ServerPort int    `json:"server_port"`

	// Authentication
	BindCode    string `json:"bind_code,omitempty"`
	DeviceToken string `json:"device_token,omitempty"`
	TokenFile   string `json:"token_file"`

	// Device info
	DeviceName string `json:"device_name"`

	// Reconnection
	ReconnectInitialDelay time.Duration `json:"-"`
	ReconnectMaxDelay     time.Duration `json:"-"`
	MaxReconnectAttempts  int           `json:"max_reconnect_attempts"` // 0 = unlimited

	// Heartbeat
	HeartbeatInterval time.Duration `json:"-"`

	// Sandbox – file operations
	WorkRoot      string   `json:"work_root"`
	AllowedPaths  []string `json:"allowed_paths,omitempty"`
	DeniedPaths   []string `json:"denied_paths,omitempty"`
	MaxReadBytes  int64    `json:"max_read_bytes"`
	MaxWriteBytes int64    `json:"max_write_bytes"`

	// Sandbox – shell execution
	ShellTimeout     time.Duration `json:"-"`
	MaxOutputBytes   int64         `json:"max_output_bytes"`
	BlockedCommands  []string      `json:"blocked_commands,omitempty"`
	AllowedShells    []string      `json:"allowed_shells,omitempty"`

	// Logging
	LogLevel string `json:"log_level"`
}

// DefaultConfig returns a Config with sensible defaults.
func DefaultConfig() *Config {
	home, _ := os.UserHomeDir()
	tokenFile := filepath.Join(home, ".tgo-device-agent", "device_token")

	return &Config{
		ServerHost:            "localhost",
		ServerPort:            9876,
		TokenFile:             tokenFile,
		DeviceName:            hostname(),
		ReconnectInitialDelay: 1 * time.Second,
		ReconnectMaxDelay:     30 * time.Second,
		MaxReconnectAttempts:  0,
		HeartbeatInterval:     25 * time.Second,
		WorkRoot:              ".",
		MaxReadBytes:          10 * 1024 * 1024, // 10 MB
		MaxWriteBytes:         10 * 1024 * 1024,
		ShellTimeout:          60 * time.Second,
		MaxOutputBytes:        1 * 1024 * 1024, // 1 MB
		BlockedCommands: []string{
			"rm -rf /", "mkfs", "dd if=/dev/zero",
			":(){:|:&};:", "fork bomb",
		},
		AllowedShells: []string{"/bin/sh", "/bin/bash", "/bin/zsh"},
		LogLevel:      "info",
	}
}

// LoadTokenFromFile reads a saved device token from disk.
func (c *Config) LoadTokenFromFile() {
	data, err := os.ReadFile(c.TokenFile)
	if err != nil {
		return
	}
	c.DeviceToken = string(data)
}

// SaveTokenToFile persists the device token to disk for reconnection.
func (c *Config) SaveTokenToFile(token string) error {
	dir := filepath.Dir(c.TokenFile)
	if err := os.MkdirAll(dir, 0o700); err != nil {
		return fmt.Errorf("create token dir: %w", err)
	}
	return os.WriteFile(c.TokenFile, []byte(token), 0o600)
}

// LoadFromFile reads JSON config from the given path and merges into c.
func (c *Config) LoadFromFile(path string) error {
	data, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	return json.Unmarshal(data, c)
}

func hostname() string {
	h, err := os.Hostname()
	if err != nil {
		return "unknown"
	}
	return h
}
