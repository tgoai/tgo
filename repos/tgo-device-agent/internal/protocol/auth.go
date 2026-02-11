package protocol

// DeviceInfo describes the connecting device, sent during auth.
type DeviceInfo struct {
	Name             string `json:"name"`
	Version          string `json:"version"`
	OS               string `json:"os"`
	OSVersion        string `json:"osVersion,omitempty"`
	ScreenResolution string `json:"screenResolution,omitempty"`
}

// AuthParams is the params payload for the "auth" method.
type AuthParams struct {
	BindCode    string      `json:"bindCode,omitempty"`
	DeviceToken string      `json:"deviceToken,omitempty"`
	DeviceInfo  DeviceInfo  `json:"deviceInfo"`
}

// AuthResult is the successful result of the "auth" method.
type AuthResult struct {
	Status      string `json:"status"`
	DeviceID    string `json:"deviceId"`
	DeviceToken string `json:"deviceToken,omitempty"` // only on first registration
	ProjectID   string `json:"projectId"`
	Message     string `json:"message"`
}
