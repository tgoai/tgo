/**
 * Remote Agent Types
 * Type definitions for remote agents from AgentOS
 */

/**
 * Remote Agent type
 */
export type RemoteAgentType = 'computer_use' | 'custom';

/**
 * Remote Agent status
 */
export type RemoteAgentStatus = 'available' | 'unavailable';

/**
 * Remote Agent information
 */
export interface RemoteAgentInfo {
  agent_id: string;
  name: string;
  type: RemoteAgentType;
  base_url: string;
  description?: string;
  status: RemoteAgentStatus;
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
 * Configuration for using a remote agent in a team
 */
export interface RemoteAgentTeamConfig {
  agent_id: string;
  base_url: string;
  display_name?: string;
  description?: string;
  // Computer Use specific config
  device_id?: string;
  max_rounds?: number;
  grounding_model?: 'openai' | 'uitars';
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
