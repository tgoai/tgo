/**
 * Plugin API Service
 */

import { apiClient } from './api';
import type {
  PluginInfo,
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
}

export const pluginApiService = new PluginApiService();
export default pluginApiService;

