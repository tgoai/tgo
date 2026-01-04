/**
 * Plugin State Management Store
 */

import { create } from 'zustand';
import i18next from 'i18next';
import { pluginApiService } from '@/services/pluginApi';
import type {
  PluginInfo,
  PluginPanelItem,
  ChatToolbarButton,
  PluginRenderResponse,
  PluginActionResponse,
} from '@/types/plugin';

interface PluginState {
  // Data
  plugins: PluginInfo[];
  visitorPanels: Record<string, PluginPanelItem[]>; // visitorId -> panels
  toolbarButtons: ChatToolbarButton[];
  
  // UI State
  isLoadingPlugins: boolean;
  isLoadingVisitorPanels: boolean;
  isLoadingToolbarButtons: boolean;
  activeModal: {
    pluginId: string;
    title: string;
    ui: PluginRenderResponse;
    context: any;
  } | null;

  // Actions
  fetchPlugins: () => Promise<void>;
  fetchVisitorPanels: (visitorId: string, context?: any) => Promise<void>;
  fetchToolbarButtons: () => Promise<void>;
  
  // Modal & Event Actions
  openPluginModal: (pluginId: string, title: string, context: any) => Promise<void>;
  closePluginModal: () => void;
  sendPluginEvent: (pluginId: string, eventType: string, actionId: string, context: any, formData?: any) => Promise<void>;
  
  // Action Handling
  handlePluginAction: (action: PluginActionResponse, context: any) => void;
}

export const usePluginStore = create<PluginState>((set, get) => ({
  plugins: [],
  visitorPanels: {},
  toolbarButtons: [],
  isLoadingPlugins: false,
  isLoadingVisitorPanels: false,
  isLoadingToolbarButtons: false,
  activeModal: null,

  fetchPlugins: async () => {
    set({ isLoadingPlugins: true });
    try {
      const { plugins } = await pluginApiService.listPlugins();
      set({ plugins });
    } catch (error) {
      console.error('Failed to fetch plugins:', error);
    } finally {
      set({ isLoadingPlugins: false });
    }
  },

  fetchVisitorPanels: async (visitorId, context) => {
    // Basic optimization: don't fetch if already loading
    if (get().isLoadingVisitorPanels) return;
    
    set({ isLoadingVisitorPanels: true });
    try {
      const { panels } = await pluginApiService.renderVisitorPanels({
        visitor_id: visitorId,
        context,
        language: i18next.language,
      });
      set((state) => ({
        visitorPanels: {
          ...state.visitorPanels,
          [visitorId]: panels,
        },
      }));
    } catch (error) {
      console.error(`Failed to fetch visitor panels for ${visitorId}:`, error);
    } finally {
      set({ isLoadingVisitorPanels: false });
    }
  },

  fetchToolbarButtons: async () => {
    set({ isLoadingToolbarButtons: true });
    try {
      const { buttons } = await pluginApiService.getChatToolbarButtons();
      set({ toolbarButtons: buttons });
    } catch (error) {
      console.error('Failed to fetch toolbar buttons:', error);
    } finally {
      set({ isLoadingToolbarButtons: false });
    }
  },

  openPluginModal: async (pluginId, title, context) => {
    try {
      const ui = await pluginApiService.renderChatToolbarPlugin(pluginId, {
        ...context,
        language: i18next.language,
      });
      set({
        activeModal: {
          pluginId,
          title,
          ui,
          context,
        },
      });
    } catch (error) {
      console.error(`Failed to open plugin modal for ${pluginId}:`, error);
    }
  },

  closePluginModal: () => {
    set({ activeModal: null });
  },

  sendPluginEvent: async (pluginId, eventType, actionId, context, formData) => {
    try {
      const action = await pluginApiService.sendPluginEvent(pluginId, {
        event_type: eventType,
        action_id: actionId,
        extension_type: context.extension_type,
        visitor_id: context.visitor_id,
        session_id: context.session_id,
        language: i18next.language,
        form_data: formData,
        payload: context,
      });
      get().handlePluginAction(action, context);
    } catch (error) {
      console.error(`Failed to send plugin event to ${pluginId}:`, error);
    }
  },

  handlePluginAction: (action, context) => {
    const { action: type, data } = action;
    console.log(`Handling plugin action: ${type}`, data);

    switch (type) {
      case 'open_url':
        if (data.url) {
          window.open(data.url, data.target || '_blank');
        }
        break;
      
      case 'insert_text':
        if (data.text) {
          window.dispatchEvent(new CustomEvent('tgo:insert_text', { detail: { text: data.text, replace: data.replace } }));
        }
        break;

      case 'send_message':
        if (data.content) {
          window.dispatchEvent(new CustomEvent('tgo:send_message', { detail: { content: data.content, content_type: data.content_type } }));
        }
        break;

      case 'show_toast':
        if (data.message) {
          window.dispatchEvent(new CustomEvent('tgo:show_toast', { detail: { message: data.message, type: data.type || 'success' } }));
        }
        break;

      case 'copy_text':
        if (data.text) {
          navigator.clipboard.writeText(data.text);
        }
        break;

      case 'refresh':
        if (get().activeModal?.pluginId) {
          get().openPluginModal(get().activeModal!.pluginId, get().activeModal!.title, context);
        }
        if (context.visitor_id) {
          get().fetchVisitorPanels(context.visitor_id, context);
        }
        break;

      case 'close_modal':
        get().closePluginModal();
        break;

      case 'show_modal':
        if (data.template && data.data) {
          set({
            activeModal: {
              pluginId: 'action_modal',
              title: data.title || 'Plugin',
              ui: { template: data.template, data: data.data },
              context,
            },
          });
        }
        break;

      case 'noop':
      default:
        break;
    }
  },
}));

