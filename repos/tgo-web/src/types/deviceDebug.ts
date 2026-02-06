/**
 * Device Debug Types
 * Types for device debug chat functionality
 */

import type { Device } from './deviceControl';

/**
 * Agent event types from device control service
 */
export type AgentEventType =
  | 'started'
  | 'completed'
  | 'error'
  | 'tools_loaded'
  | 'tool_call'
  | 'tool_result'
  | 'thinking'
  | 'iteration_start'
  | 'iteration_end';

/**
 * Tool call information
 */
export interface ToolCallInfo {
  name: string;
  arguments: Record<string, unknown>;
}

/**
 * Tool result information
 */
export interface ToolResultInfo {
  name: string;
  success: boolean;
  content?: string;
  has_image: boolean;
  image_data?: string;
  error?: string;
}

/**
 * Agent event from SSE stream
 */
export interface AgentEvent {
  event_type: AgentEventType;
  run_id: string;
  timestamp: string;
  content?: string;
  tool_call?: ToolCallInfo;
  tool_result?: ToolResultInfo;
  iteration?: number;
  max_iterations?: number;
  final_result?: string;
  success: boolean;
  error?: string;
  error_code?: string;
  metadata?: {
    tool_names?: string[];
    [key: string]: unknown;
  };
}

/**
 * Debug message types in the chat
 */
export type DebugMessageType =
  | 'user'
  | 'thinking'
  | 'tool_call'
  | 'tool_result'
  | 'ai_response'
  | 'error'
  | 'system';

/**
 * Debug message in the chat
 */
export interface DebugMessage {
  id: string;
  type: DebugMessageType;
  content: string;
  timestamp: string;
  
  // For tool messages
  toolName?: string;
  toolArgs?: Record<string, unknown>;
  toolSuccess?: boolean;
  
  // For screenshot messages
  hasScreenshot?: boolean;
  screenshotData?: string;
  
  // For thinking messages
  iteration?: number;
  maxIterations?: number;
  
  // For error messages
  errorCode?: string;
}

/**
 * Execution step in the timeline
 */
export interface ExecutionStep {
  id: string;
  timestamp: string;
  type: 'tool_call' | 'tool_result' | 'thinking' | 'completed' | 'error';
  toolName?: string;
  toolArgs?: Record<string, unknown>;
  success?: boolean;
  duration?: number;
  hasScreenshot?: boolean;
  screenshotData?: string;
  content?: string;
  iteration?: number;
}

/**
 * Screenshot captured during debugging
 */
export interface Screenshot {
  id: string;
  timestamp: string;
  data: string;
  toolName?: string;
  iteration?: number;
}

/**
 * Debug session statistics
 */
export interface DebugStats {
  toolCalls: number;
  screenshotsCount: number;
  totalDuration: number;
  iterations: number;
  errors: number;
}

/**
 * Quick command for device debugging
 */
export interface QuickCommand {
  id: string;
  label: string;
  icon: string;
  command: string;
}

/**
 * Device debug chat request
 */
export interface DeviceDebugChatRequest {
  device_id: string;
  message: string;
  model?: string;
  max_iterations?: number;
  system_prompt?: string;
}

/**
 * Connected device for agent control
 */
export interface ConnectedDevice {
  device_id: string;
  name: string;
  version: string;
  capabilities: string[];
  connected_at: string;
  tools_count: number;
}

/**
 * Device tools response
 */
export interface DeviceToolsResponse {
  device_id: string;
  tools: DeviceTool[];
  count: number;
}

/**
 * Device tool definition
 */
export interface DeviceTool {
  name: string;
  description: string;
  inputSchema?: Record<string, unknown>;
}

/**
 * Device debug state
 */
export interface DeviceDebugState {
  // Session state
  sessionId: string | null;
  device: Device | null;
  isConnected: boolean;
  
  // Messages
  messages: DebugMessage[];
  
  // Execution state
  isExecuting: boolean;
  currentIteration: number;
  maxIterations: number;
  runId: string | null;
  
  // Screenshots
  screenshots: Screenshot[];
  latestScreenshot: Screenshot | null;
  
  // Timeline
  executionSteps: ExecutionStep[];
  
  // Stats
  stats: DebugStats;
  
  // Error
  error: string | null;
}
