// Package protocol defines the JSON-RPC 2.0 message types and error codes
// used for communication with tgo-device-control.
package protocol

import "encoding/json"

// --------------------------------------------------------------------
// JSON-RPC 2.0 message types
// --------------------------------------------------------------------

// Request represents a JSON-RPC 2.0 request or notification.
type Request struct {
	JSONRPC string           `json:"jsonrpc"`
	ID      *json.RawMessage `json:"id,omitempty"` // nil for notifications
	Method  string           `json:"method"`
	Params  json.RawMessage  `json:"params,omitempty"`
}

// Response represents a JSON-RPC 2.0 response.
type Response struct {
	JSONRPC string           `json:"jsonrpc"`
	ID      *json.RawMessage `json:"id,omitempty"`
	Result  json.RawMessage  `json:"result,omitempty"`
	Error   *RPCError        `json:"error,omitempty"`
}

// RPCError represents a JSON-RPC 2.0 error object.
type RPCError struct {
	Code    int              `json:"code"`
	Message string           `json:"message"`
	Data    *json.RawMessage `json:"data,omitempty"`
}

// NewRequest creates a JSON-RPC 2.0 request with a numeric ID.
func NewRequest(id int, method string, params interface{}) (*Request, error) {
	rawID, _ := json.Marshal(id)
	rm := json.RawMessage(rawID)

	var rawParams json.RawMessage
	if params != nil {
		b, err := json.Marshal(params)
		if err != nil {
			return nil, err
		}
		rawParams = b
	} else {
		rawParams = json.RawMessage(`{}`)
	}

	return &Request{
		JSONRPC: "2.0",
		ID:      &rm,
		Method:  method,
		Params:  rawParams,
	}, nil
}

// NewNotification creates a JSON-RPC 2.0 notification (no id).
func NewNotification(method string, params interface{}) (*Request, error) {
	var rawParams json.RawMessage
	if params != nil {
		b, err := json.Marshal(params)
		if err != nil {
			return nil, err
		}
		rawParams = b
	} else {
		rawParams = json.RawMessage(`{}`)
	}
	return &Request{
		JSONRPC: "2.0",
		Method:  method,
		Params:  rawParams,
	}, nil
}

// NewResponse creates a success response.
func NewResponse(id *json.RawMessage, result interface{}) (*Response, error) {
	b, err := json.Marshal(result)
	if err != nil {
		return nil, err
	}
	return &Response{
		JSONRPC: "2.0",
		ID:      id,
		Result:  b,
	}, nil
}

// NewErrorResponse creates an error response.
func NewErrorResponse(id *json.RawMessage, code int, message string) *Response {
	return &Response{
		JSONRPC: "2.0",
		ID:      id,
		Error: &RPCError{
			Code:    code,
			Message: message,
		},
	}
}

// --------------------------------------------------------------------
// JSON-RPC 2.0 error codes
// --------------------------------------------------------------------

const (
	ErrParseError     = -32700
	ErrInvalidRequest = -32600
	ErrMethodNotFound = -32601
	ErrInvalidParams  = -32602
	ErrInternalError  = -32603

	// Custom error codes (matching tgo-device-control)
	ErrAuthFailed         = -32001
	ErrToolNotFound       = -32002
	ErrToolExecFailed     = -32003
	ErrConnectionClosed   = -32004
)

// IsResponse returns true if the raw JSON contains "result" or "error" keys
// (i.e., it is a response rather than a request).
func IsResponse(raw json.RawMessage) bool {
	var probe struct {
		Result *json.RawMessage `json:"result"`
		Error  *json.RawMessage `json:"error"`
	}
	if err := json.Unmarshal(raw, &probe); err != nil {
		return false
	}
	return probe.Result != nil || probe.Error != nil
}
