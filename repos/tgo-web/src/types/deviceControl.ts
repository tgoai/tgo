/**
 * Device Control Types
 * Types for device control functionality
 */

export type DeviceType = 'desktop' | 'mobile';
export type DeviceStatus = 'online' | 'offline';

/**
 * Device information
 */
export interface Device {
  id: string;
  project_id: string;
  device_type: DeviceType;
  device_name: string;
  os: string;
  os_version?: string;
  screen_resolution?: string;
  status: DeviceStatus;
  last_seen_at?: string;
  created_at: string;
}

/**
 * Device list response
 */
export interface DeviceListResponse {
  devices: Device[];
  total: number;
}

/**
 * Bind code response
 */
export interface BindCodeResponse {
  bind_code: string;
  expires_at: string;
}

/**
 * Device update request
 */
export interface DeviceUpdateRequest {
  device_name?: string;
}

/**
 * Device list query parameters
 * Note: project_id is not needed as it's obtained from JWT token
 */
export interface DeviceListParams {
  device_type?: DeviceType;
  status?: DeviceStatus;
  skip?: number;
  limit?: number;
}

/**
 * Device control tool definition (for AI agent integration)
 */
export interface DeviceControlTool {
  id: string;
  name: string;
  description: string;
  device_id?: string;
  enabled: boolean;
}

/**
 * Device session information
 */
export interface DeviceSession {
  id: string;
  device_id: string;
  agent_id?: string;
  started_at: string;
  ended_at?: string;
  screenshots_count: number;
  actions_count: number;
}
