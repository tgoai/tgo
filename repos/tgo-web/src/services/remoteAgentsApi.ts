/**
 * Remote Agents API Service
 * API functions for managing remote agents from AgentOS
 */

import apiClient from './api';

const REMOTE_AGENTS_BASE_URL = '/v1/remote-agents';

/**
 * Remote Agent information
 */
export interface RemoteAgentInfo {
  agent_id: string;
  name: string;
  type: 'computer_use' | 'custom';
  base_url: string;
  description?: string;
  status: 'available' | 'unavailable';
  supports_device_control?: boolean;
  available_tools?: string[];
}

/**
 * Remote Agent configuration from AgentOS
 */
export interface RemoteAgentConfig {
  agent_id: string;
  name: string;
  description?: string;
  instructions?: string;
  tools?: string[];
  model?: string;
}

/**
 * Request to register a custom remote agent
 */
export interface RemoteAgentRegisterRequest {
  base_url: string;
  agent_id: string;
  display_name?: string;
  description?: string;
}

/**
 * Response from list remote agents
 */
export interface RemoteAgentsListResponse {
  items: RemoteAgentInfo[];
  total: number;
}

/**
 * Test remote agent response
 */
export interface RemoteAgentTestResponse {
  success: boolean;
  response?: unknown;
  error?: string;
  details?: string;
}

/**
 * List available remote agents
 */
export async function listRemoteAgents(): Promise<RemoteAgentsListResponse> {
  return apiClient.get<RemoteAgentsListResponse>(REMOTE_AGENTS_BASE_URL);
}

/**
 * Get information about a specific remote agent
 */
export async function getRemoteAgent(agentId: string): Promise<RemoteAgentInfo> {
  return apiClient.get<RemoteAgentInfo>(`${REMOTE_AGENTS_BASE_URL}/${agentId}`);
}

/**
 * Get configuration of a remote agent from its AgentOS
 */
export async function getRemoteAgentConfig(agentId: string): Promise<RemoteAgentConfig> {
  return apiClient.get<RemoteAgentConfig>(`${REMOTE_AGENTS_BASE_URL}/${agentId}/config`);
}

/**
 * Register a custom remote agent
 */
export async function registerRemoteAgent(
  request: RemoteAgentRegisterRequest
): Promise<RemoteAgentInfo> {
  return apiClient.post<RemoteAgentInfo>(REMOTE_AGENTS_BASE_URL, request);
}

/**
 * Unregister a custom remote agent
 */
export async function unregisterRemoteAgent(agentId: string): Promise<void> {
  await apiClient.delete(`${REMOTE_AGENTS_BASE_URL}/${agentId}`);
}

/**
 * Test a remote agent by sending a message
 */
export async function testRemoteAgent(
  agentId: string,
  message: string
): Promise<RemoteAgentTestResponse> {
  return apiClient.post<RemoteAgentTestResponse>(
    `${REMOTE_AGENTS_BASE_URL}/${agentId}/test`,
    { message }
  );
}

export default {
  listRemoteAgents,
  getRemoteAgent,
  getRemoteAgentConfig,
  registerRemoteAgent,
  unregisterRemoteAgent,
  testRemoteAgent,
};
