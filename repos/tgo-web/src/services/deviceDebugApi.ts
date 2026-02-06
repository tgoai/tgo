/**
 * Device Debug API Service
 * API functions for device debug chat functionality
 */

import apiClient from './api';
import type {
  AgentEvent,
  DeviceDebugChatRequest,
  ConnectedDevice,
  DeviceToolsResponse,
} from '@/types/deviceDebug';

const DEVICE_CONTROL_BASE_URL = '/v1/device-control';

/**
 * Callbacks for device debug chat stream
 */
export interface DeviceDebugStreamCallbacks {
  onEvent: (event: AgentEvent) => void;
  onClose?: () => void;
  onError?: (error: unknown) => void;
}

/**
 * Start a device debug chat session with streaming response
 */
export async function startDeviceDebugChat(
  request: DeviceDebugChatRequest,
  callbacks: DeviceDebugStreamCallbacks,
  signal?: AbortSignal
): Promise<void> {
  return apiClient.stream(
    `${DEVICE_CONTROL_BASE_URL}/chat`,
    request,
    {
      onMessage: (_event: string, data: AgentEvent) => {
        callbacks.onEvent(data);
      },
      onClose: callbacks.onClose,
      onError: callbacks.onError,
      signal,
    }
  );
}

/**
 * List connected devices available for agent control
 */
export async function listConnectedDevices(): Promise<{
  devices: ConnectedDevice[];
  count: number;
}> {
  return apiClient.get(`${DEVICE_CONTROL_BASE_URL}/connected-devices`);
}

/**
 * Get available tools from a connected device
 */
export async function getDeviceTools(deviceId: string): Promise<DeviceToolsResponse> {
  return apiClient.get(`${DEVICE_CONTROL_BASE_URL}/devices/${deviceId}/tools`);
}

export default {
  startDeviceDebugChat,
  listConnectedDevices,
  getDeviceTools,
};
