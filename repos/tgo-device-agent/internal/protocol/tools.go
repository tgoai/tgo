package protocol

// ToolDefinition describes a tool in MCP-compatible format.
type ToolDefinition struct {
	Name        string                 `json:"name"`
	Description string                 `json:"description"`
	InputSchema map[string]interface{} `json:"inputSchema"`
}

// ToolsListResult is the result payload for "tools/list".
type ToolsListResult struct {
	Tools []ToolDefinition `json:"tools"`
}

// ToolCallParams is the params payload for "tools/call".
type ToolCallParams struct {
	Name      string                 `json:"name"`
	Arguments map[string]interface{} `json:"arguments"`
}

// ContentItem is one piece of content in a tool call result.
type ContentItem struct {
	Type     string `json:"type"`               // "text" or "image"
	Text     string `json:"text,omitempty"`
	Data     string `json:"data,omitempty"`      // base64 for images
	MimeType string `json:"mimeType,omitempty"`
}

// ToolCallResult is the result payload for "tools/call".
type ToolCallResult struct {
	Content []ContentItem `json:"content"`
	IsError bool          `json:"isError"`
}

// TextResult is a convenience constructor for a single-text tool result.
func TextResult(text string, isError bool) *ToolCallResult {
	return &ToolCallResult{
		Content: []ContentItem{{Type: "text", Text: text}},
		IsError: isError,
	}
}
