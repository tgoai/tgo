/**
 * Plugin API Service
 */

import { apiClient } from './api';
import type {
  PluginInfo,
  InstalledPluginInfo,
  PluginPanelItem,
  ChatToolbarButton,
  PluginRenderResponse,
  PluginActionResponse,
  PluginRenderRequest,
  PluginEventRequest,
} from '@/types/plugin';

class PluginApiService {
  /**
   * Get all registered plugins
   */
  async listPlugins(): Promise<{ plugins: PluginInfo[]; total: number }> {
    return apiClient.get<{ plugins: PluginInfo[]; total: number }>('/v1/plugins');
  }

  /**
   * Get all installed plugins from database
   */
  async listInstalledPlugins(): Promise<{ plugins: InstalledPluginInfo[]; total: number }> {
    return apiClient.get<{ plugins: InstalledPluginInfo[]; total: number }>('/v1/plugins/installed');
  }

  /**
   * Install a new plugin via YAML
   */
  async installPlugin(yamlConfig: any): Promise<InstalledPluginInfo> {
    return apiClient.post<InstalledPluginInfo>('/v1/plugins/install', yamlConfig);
  }

  /**
   * Uninstall a plugin
   */
  async uninstallPlugin(pluginId: string): Promise<any> {
    return apiClient.delete<any>(`/v1/plugins/${pluginId}`);
  }

  /**
   * Start a plugin
   */
  async startPlugin(pluginId: string): Promise<any> {
    return apiClient.post<any>(`/v1/plugins/${pluginId}/start`);
  }

  /**
   * Stop a plugin
   */
  async stopPlugin(pluginId: string): Promise<any> {
    return apiClient.post<any>(`/v1/plugins/${pluginId}/stop`);
  }

  /**
   * Restart a plugin
   */
  async restartPlugin(pluginId: string): Promise<any> {
    return apiClient.post<any>(`/v1/plugins/${pluginId}/restart`);
  }

  /**
   * Get plugin logs
   */
  async getPluginLogs(pluginId: string): Promise<{ logs: string[] }> {
    return apiClient.get<{ logs: string[] }>(`/v1/plugins/${pluginId}/logs`);
  }

  /**
   * Get a specific plugin by ID
   */
  async getPlugin(pluginId: string): Promise<PluginInfo> {
    return apiClient.get<PluginInfo>(`/v1/plugins/${pluginId}`);
  }

  /**
   * Trigger a plugin to render its UI
   */
  async renderPlugin(pluginId: string, request: PluginRenderRequest): Promise<PluginRenderResponse> {
    return apiClient.post<PluginRenderResponse>(`/v1/plugins/${pluginId}/render`, request);
  }

  /**
   * Send an event to a plugin
   */
  async sendPluginEvent(pluginId: string, request: PluginEventRequest): Promise<PluginActionResponse> {
    return apiClient.post<PluginActionResponse>(`/v1/plugins/${pluginId}/event`, request);
  }

  /**
   * Render all visitor panel plugins for a specific visitor
   */
  async renderVisitorPanels(request: {
    visitor_id: string;
    session_id?: string;
    visitor?: any;
    language?: string;
    context?: Record<string, any>;
  }): Promise<{ panels: PluginPanelItem[] }> {
    return apiClient.post<{ panels: PluginPanelItem[] }>('/v1/plugins/visitor-panel/render', request);
  }

  /**
   * Get all chat toolbar buttons
   */
  async getChatToolbarButtons(): Promise<{ buttons: ChatToolbarButton[] }> {
    return apiClient.get<{ buttons: ChatToolbarButton[] }>('/v1/plugins/chat-toolbar/buttons');
  }

  /**
   * Render a chat toolbar plugin's content
   */
  async renderChatToolbarPlugin(pluginId: string, request: PluginRenderRequest): Promise<PluginRenderResponse> {
    return apiClient.post<PluginRenderResponse>(`/v1/plugins/chat-toolbar/${pluginId}/render`, request);
  }

  /**
   * Send an event to a chat toolbar plugin
   */
  async sendChatToolbarEvent(pluginId: string, request: PluginEventRequest): Promise<PluginActionResponse> {
    return apiClient.post<PluginActionResponse>(`/v1/plugins/chat-toolbar/${pluginId}/event`, request);
  }

  /**
   * Generate a dev token for plugin debugging
   */
  async generateDevToken(projectId: string, expiresHours: number = 24): Promise<{ token: string; expires_at: string }> {
    return apiClient.post<{ token: string; expires_at: string }>('/v1/plugins/dev-token', {
      project_id: projectId,
      expires_hours: expiresHours,
    });
  }

  /**
   * Fetch plugin info from a URL
   */
  async fetchPluginInfo(url: string): Promise<any> {
    return apiClient.post<any>('/v1/plugins/fetch-info', { url });
  }
}

export const pluginApiService = new PluginApiService();
export default pluginApiService;

