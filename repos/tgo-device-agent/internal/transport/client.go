// Package transport implements the TCP JSON-RPC client that connects to
// tgo-device-control, handles authentication, heartbeat, reconnection,
// and dispatches incoming tool calls to the tool registry.
package transport

import (
	"bufio"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"net"
	"os"
	"runtime"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"github.com/tgoai/tgo-device-agent/internal/config"
	"github.com/tgoai/tgo-device-agent/internal/protocol"
	"github.com/tgoai/tgo-device-agent/internal/tools"
)

// Client manages the TCP connection to tgo-device-control.
type Client struct {
	cfg      *config.Config
	registry *tools.Registry

	conn     net.Conn
	connMu   sync.Mutex
	reader   *bufio.Scanner
	writer   *bufio.Writer
	writeMu  sync.Mutex

	deviceID  string
	projectID string

	requestID atomic.Int64
	pending   sync.Map // id -> chan *protocol.Response
}

// NewClient creates a new transport client.
func NewClient(cfg *config.Config, registry *tools.Registry) *Client {
	return &Client{
		cfg:      cfg,
		registry: registry,
	}
}

// Run connects to the server and enters the main loop.
// It automatically reconnects on disconnection until ctx is cancelled.
func (c *Client) Run(ctx context.Context) error {
	delay := c.cfg.ReconnectInitialDelay
	attempts := 0

	for {
		select {
		case <-ctx.Done():
			c.close()
			return nil
		default:
		}

		err := c.connectAndServe(ctx)
		if err == nil || errors.Is(err, context.Canceled) {
			return nil
		}

		attempts++
		if c.cfg.MaxReconnectAttempts > 0 && attempts >= c.cfg.MaxReconnectAttempts {
			return fmt.Errorf("max reconnect attempts (%d) reached: %w", c.cfg.MaxReconnectAttempts, err)
		}

		slog.Warn("connection lost, reconnecting",
			"error", err,
			"delay", delay,
			"attempt", attempts,
		)

		select {
		case <-ctx.Done():
			return nil
		case <-time.After(delay):
		}

		// Exponential backoff
		delay = delay * 2
		if delay > c.cfg.ReconnectMaxDelay {
			delay = c.cfg.ReconnectMaxDelay
		}
	}
}

// connectAndServe performs a single connect-auth-serve cycle.
func (c *Client) connectAndServe(ctx context.Context) error {
	addr := fmt.Sprintf("%s:%d", c.cfg.ServerHost, c.cfg.ServerPort)
	slog.Info("connecting to server", "addr", addr)

	dialer := net.Dialer{Timeout: 10 * time.Second}
	conn, err := dialer.DialContext(ctx, "tcp", addr)
	if err != nil {
		return fmt.Errorf("dial: %w", err)
	}

	scanner := bufio.NewScanner(conn)
	// Allow up to 16 MB messages (for large tool results)
	scanner.Buffer(make([]byte, 0, 64*1024), 16*1024*1024)

	c.connMu.Lock()
	c.conn = conn
	c.reader = scanner
	c.writer = bufio.NewWriter(conn)
	c.connMu.Unlock()

	slog.Info("connected to server", "addr", addr)

	// Authenticate
	if err := c.authenticate(ctx); err != nil {
		c.close()
		return fmt.Errorf("auth: %w", err)
	}

	slog.Info("authenticated",
		"device_id", c.deviceID,
		"project_id", c.projectID,
	)

	// Start heartbeat
	heartbeatCtx, heartbeatCancel := context.WithCancel(ctx)
	defer heartbeatCancel()
	go c.heartbeatLoop(heartbeatCtx)

	// Main read loop
	return c.readLoop(ctx)
}

// authenticate sends the auth request and reads the response directly using
// the shared scanner. This is done before the main readLoop starts.
func (c *Client) authenticate(ctx context.Context) error {
	params := protocol.AuthParams{
		DeviceInfo: protocol.DeviceInfo{
			Name:      c.cfg.DeviceName,
			Version:   "1.0.0",
			OS:        runtime.GOOS,
			OSVersion: osVersion(),
		},
	}

	if c.cfg.DeviceToken != "" {
		params.DeviceToken = c.cfg.DeviceToken
		slog.Debug("authenticating with device token")
	} else if c.cfg.BindCode != "" {
		params.BindCode = c.cfg.BindCode
		slog.Debug("authenticating with bind code", "bind_code", c.cfg.BindCode)
	} else {
		return errors.New("no bind code or device token available")
	}

	id := int(c.requestID.Add(1))
	req, err := protocol.NewRequest(id, "auth", params)
	if err != nil {
		return err
	}

	// Send auth request
	if err := c.writeMessage(req); err != nil {
		return fmt.Errorf("send auth: %w", err)
	}

	slog.Debug("auth request sent, waiting for response")

	// Read the auth response directly using the shared scanner.
	// We use a goroutine + select so we can respect context cancellation and timeout.
	type readResult struct {
		raw []byte
		err error
	}
	ch := make(chan readResult, 1)

	go func() {
		if !c.reader.Scan() {
			if err := c.reader.Err(); err != nil {
				ch <- readResult{err: fmt.Errorf("read auth response: %w", err)}
			} else {
				ch <- readResult{err: errors.New("connection closed before auth response")}
			}
			return
		}
		// Copy bytes since scanner reuses the buffer
		raw := make([]byte, len(c.reader.Bytes()))
		copy(raw, c.reader.Bytes())
		ch <- readResult{raw: raw}
	}()

	// Wait with timeout
	select {
	case <-ctx.Done():
		return ctx.Err()
	case <-time.After(30 * time.Second):
		return errors.New("auth response timed out")
	case r := <-ch:
		if r.err != nil {
			return r.err
		}
		slog.Debug("auth response received", "size", len(r.raw))
		var resp protocol.Response
		if err := json.Unmarshal(r.raw, &resp); err != nil {
			return fmt.Errorf("parse auth response: %w", err)
		}
		return c.processAuthResult(&resp)
	}
}

// processAuthResult handles the parsed auth response.
func (c *Client) processAuthResult(resp *protocol.Response) error {
	if resp.Error != nil {
		return fmt.Errorf("auth rejected: [%d] %s", resp.Error.Code, resp.Error.Message)
	}

	var result protocol.AuthResult
	if err := json.Unmarshal(resp.Result, &result); err != nil {
		return fmt.Errorf("parse auth result: %w", err)
	}

	c.deviceID = result.DeviceID
	c.projectID = result.ProjectID

	// Save token on first registration
	if result.DeviceToken != "" {
		c.cfg.DeviceToken = result.DeviceToken
		if err := c.cfg.SaveTokenToFile(result.DeviceToken); err != nil {
			slog.Warn("failed to save device token", "error", err)
		} else {
			slog.Info("device token saved for reconnection")
		}
		// Clear bind code so reconnects use token
		c.cfg.BindCode = ""
	}

	return nil
}

// sendRequest sends a JSON-RPC request and waits for the matching response.
func (c *Client) sendRequest(ctx context.Context, method string, params interface{}) (*protocol.Response, error) {
	id := int(c.requestID.Add(1))

	req, err := protocol.NewRequest(id, method, params)
	if err != nil {
		return nil, err
	}

	ch := make(chan *protocol.Response, 1)
	c.pending.Store(id, ch)
	defer c.pending.Delete(id)

	if err := c.writeMessage(req); err != nil {
		return nil, err
	}

	select {
	case <-ctx.Done():
		return nil, ctx.Err()
	case resp := <-ch:
		return resp, nil
	case <-time.After(30 * time.Second):
		return nil, fmt.Errorf("request %d (%s) timed out", id, method)
	}
}

// readLoop reads newline-delimited JSON messages using the shared scanner.
func (c *Client) readLoop(ctx context.Context) error {
	for {
		select {
		case <-ctx.Done():
			return nil
		default:
		}

		if !c.reader.Scan() {
			if err := c.reader.Err(); err != nil {
				return fmt.Errorf("read: %w", err)
			}
			return errors.New("connection closed by server")
		}

		// Copy bytes since scanner reuses the buffer
		raw := make([]byte, len(c.reader.Bytes()))
		copy(raw, c.reader.Bytes())

		if len(raw) == 0 {
			continue
		}

		slog.Debug("received message", "size", len(raw))

		// Determine if response or request
		if protocol.IsResponse(raw) {
			c.handleResponse(raw)
		} else {
			go c.handleRequest(ctx, raw)
		}
	}
}

// handleResponse resolves a pending request future.
func (c *Client) handleResponse(raw []byte) {
	var resp protocol.Response
	if err := json.Unmarshal(raw, &resp); err != nil {
		slog.Warn("failed to parse response", "error", err)
		return
	}

	if resp.ID == nil {
		return
	}

	// Extract numeric ID
	var id int
	if err := json.Unmarshal(*resp.ID, &id); err != nil {
		slog.Warn("failed to parse response id", "error", err)
		return
	}

	if ch, ok := c.pending.Load(id); ok {
		ch.(chan *protocol.Response) <- &resp
	}
}

// handleRequest dispatches incoming server requests (tools/list, tools/call, ping).
func (c *Client) handleRequest(ctx context.Context, raw []byte) {
	var req protocol.Request
	if err := json.Unmarshal(raw, &req); err != nil {
		slog.Warn("failed to parse request", "error", err)
		return
	}

	slog.Debug("handling request", "method", req.Method)

	switch req.Method {
	case "ping":
		c.handlePing(req.ID)
	case "tools/list":
		c.handleToolsList(req.ID)
	case "tools/call":
		c.handleToolsCall(ctx, req.ID, req.Params)
	default:
		if req.ID != nil {
			resp := protocol.NewErrorResponse(req.ID, protocol.ErrMethodNotFound,
				fmt.Sprintf("Method not found: %s", req.Method))
			c.writeMessage(resp)
		}
	}
}

// handlePing responds to server ping.
func (c *Client) handlePing(id *json.RawMessage) {
	if id != nil {
		result := map[string]interface{}{
			"pong":      true,
			"timestamp": time.Now().Unix(),
		}
		resp, _ := protocol.NewResponse(id, result)
		c.writeMessage(resp)
	} else {
		// Notification ping -> respond with pong notification
		pong, _ := protocol.NewNotification("pong", nil)
		c.writeMessage(pong)
	}
}

// handleToolsList returns the tool definitions from the registry.
func (c *Client) handleToolsList(id *json.RawMessage) {
	defs := c.registry.ListTools()
	result := protocol.ToolsListResult{Tools: defs}
	resp, err := protocol.NewResponse(id, result)
	if err != nil {
		slog.Error("failed to build tools/list response", "error", err)
		return
	}
	c.writeMessage(resp)
}

// handleToolsCall dispatches a tool call to the registry and returns the result.
func (c *Client) handleToolsCall(ctx context.Context, id *json.RawMessage, paramsRaw json.RawMessage) {
	start := time.Now()

	var params protocol.ToolCallParams
	if err := json.Unmarshal(paramsRaw, &params); err != nil {
		resp := protocol.NewErrorResponse(id, protocol.ErrInvalidParams, "Invalid tools/call params")
		c.writeMessage(resp)
		return
	}

	slog.Info("tool call", "tool", params.Name, "args_keys", mapKeys(params.Arguments))

	result := c.registry.CallTool(ctx, params.Name, params.Arguments)

	elapsed := time.Since(start)
	slog.Info("tool call completed",
		"tool", params.Name,
		"is_error", result.IsError,
		"elapsed", elapsed,
	)

	resp, err := protocol.NewResponse(id, result)
	if err != nil {
		slog.Error("failed to build tools/call response", "error", err)
		return
	}
	c.writeMessage(resp)
}

// heartbeatLoop sends periodic heartbeat messages.
func (c *Client) heartbeatLoop(ctx context.Context) {
	ticker := time.NewTicker(c.cfg.HeartbeatInterval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			msg, _ := protocol.NewNotification("pong", nil)
			if err := c.writeMessage(msg); err != nil {
				slog.Warn("heartbeat send failed", "error", err)
				return
			}
			slog.Debug("heartbeat sent")
		}
	}
}

// writeMessage serializes and sends a JSON-RPC message (newline-delimited).
func (c *Client) writeMessage(msg interface{}) error {
	data, err := json.Marshal(msg)
	if err != nil {
		return err
	}

	c.writeMu.Lock()
	defer c.writeMu.Unlock()

	c.connMu.Lock()
	w := c.writer
	c.connMu.Unlock()

	if w == nil {
		return errors.New("no connection")
	}

	if _, err := w.Write(data); err != nil {
		return err
	}
	if err := w.WriteByte('\n'); err != nil {
		return err
	}
	return w.Flush()
}

// close cleanly shuts down the TCP connection.
func (c *Client) close() {
	c.connMu.Lock()
	defer c.connMu.Unlock()

	if c.conn != nil {
		c.conn.Close()
		c.conn = nil
		c.reader = nil
		c.writer = nil
	}
}

// mapKeys extracts the keys of a map for logging.
func mapKeys(m map[string]interface{}) []string {
	keys := make([]string, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	return keys
}

// osVersion returns a best-effort OS version string.
func osVersion() string {
	switch runtime.GOOS {
	case "darwin":
		// Try sw_vers
		if data, err := os.ReadFile("/System/Library/CoreServices/SystemVersion.plist"); err == nil {
			s := string(data)
			if idx := strings.Index(s, "ProductVersion"); idx >= 0 {
				sub := s[idx:]
				start := strings.Index(sub, "<string>")
				end := strings.Index(sub, "</string>")
				if start >= 0 && end > start {
					return sub[start+8 : end]
				}
			}
		}
	}
	return runtime.GOARCH
}
