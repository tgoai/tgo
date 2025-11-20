// 导出所有store
export { useChatStore } from './chatStore';
export { useAIStore } from './aiStore';
export { useKnowledgeStore } from './knowledgeStore';
export { usePlatformStore } from './platformStore';
export { useUIStore } from './uiStore';
export { useAuthStore } from './authStore';
export { useSetupStore } from './setupStore';

// 常用选择器 - 避免在选择器中调用计算方法
export const chatSelectors = {
  activeChat: (state: any) => state.activeChat,
  messages: (state: any) => state.messages,
  chats: (state: any) => state.chats,
  searchQuery: (state: any) => state.searchQuery,
  isLoading: (state: any) => state.isLoading || state.isSending
};

export const aiSelectors = {
  agents: (state: any) => state.agents,
  mcpTools: (state: any) => state.mcpTools,
  selectedAgent: (state: any) => state.selectedAgent,
  selectedTool: (state: any) => state.selectedTool,
  agentCurrentPage: (state: any) => state.agentCurrentPage,
  agentPageSize: (state: any) => state.agentPageSize
};

export const knowledgeSelectors = {
  knowledgeBases: (state: any) => state.knowledgeBases,
  searchQuery: (state: any) => state.searchQuery,
  isLoading: (state: any) =>
    state.isLoading || state.isCreating || state.isUpdating || state.isDeleting
};

export const platformSelectors = {
  platforms: (state: any) => state.platforms,
  selectedPlatform: (state: any) => state.selectedPlatform,
  searchQuery: (state: any) => state.searchQuery,
  statusFilter: (state: any) => state.statusFilter,
  isLoading: (state: any) =>
    state.isLoading || state.isConnecting || state.isUpdating || state.isDeleting,
  isLoadingDetail: (state: any) => state.isLoadingDetail,
  detailLoadError: (state: any) => state.detailLoadError
};

export const uiSelectors = {
  theme: (state: any) => state.theme,
  sidebarState: (state: any) => state.sidebarState,
  notifications: (state: any) => state.notifications,
  isMobile: (state: any) => state.isMobile,
  isTablet: (state: any) => state.isTablet,
  preferences: (state: any) => state.preferences
};
