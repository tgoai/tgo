/**
 * Plugin system type definitions
 */

export type PluginCapabilityType = 'visitor_panel' | 'chat_toolbar' | 'sidebar_iframe' | 'channel_integration' | 'mcp_tools';

export interface MCPToolParameter {
  name: string;
  type: string;
  description?: string;
  required: boolean;
  enum_values?: string[];
}

export interface MCPToolDefinition {
  name: string;
  title: string;
  description?: string;
  parameters?: MCPToolParameter[];
}

export interface PluginCapability {
  type: PluginCapabilityType;
  title: string;
  icon?: string;
  priority?: number;
  tooltip?: string;
  shortcut?: string;
  url?: string;
  width?: number;
  tools?: MCPToolDefinition[];
}

export interface PluginInfo {
  id: string;
  name: string;
  version: string;
  description?: string;
  author?: string;
  capabilities: PluginCapability[];
  connected_at: string;
  status: 'connected' | 'disconnected';
}

export interface PluginRenderResponse {
  template: string;
  data: any;
}

export interface PluginActionResponse {
  action: string;
  data: any;
}

export interface PluginPanelItem {
  plugin_id: string;
  title: string;
  icon?: string;
  priority: number;
  ui: PluginRenderResponse;
}

export interface ChatToolbarButton {
  plugin_id: string;
  title: string;
  icon?: string;
  tooltip?: string;
  shortcut?: string;
}

export interface PluginRenderRequest {
  visitor_id?: string;
  session_id?: string;
  visitor?: any;
  agent_id?: string;
  action_id?: string;
  language?: string;
  context?: Record<string, any>;
}

export interface PluginEventRequest {
  event_type: string;
  action_id: string;
  extension_type?: string;
  visitor_id?: string;
  session_id?: string;
  selected_id?: string;
  language?: string;
  form_data?: Record<string, any>;
  payload?: Record<string, any>;
}

export interface InstalledPluginInfo {
  id: string | null;
  plugin_id: string;
  name: string;
  version: string;
  description?: string;
  author?: string;
  status: 'pending' | 'installing' | 'running' | 'stopped' | 'error';
  install_type: 'github' | 'binary' | 'dev';
  installed_at: string;
  updated_at: string;
  pid?: number;
  last_error?: string;
  is_dev_mode?: boolean;
  capabilities?: PluginCapability[];
}

