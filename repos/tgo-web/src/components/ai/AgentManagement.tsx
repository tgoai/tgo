import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import AgentCard from './AgentCard';
import CreateAgentModal from './CreateAgentModal';
import EditAgentModal from './EditAgentModal';
import AgentStoreModal from './AgentStoreModal';
import ToolToastProvider from './ToolToastProvider';
// import AiToolDetailModal from '@/components/ui/AiToolDetailModal';
import ConfirmDialog from '@/components/ui/ConfirmDialog';
import { AgentsGridSkeleton, AgentsErrorState, AgentsEmptyState } from '@/components/ui/AgentsSkeleton';
import { useAIStore } from '@/stores';
import { useToast } from '@/hooks/useToast';
import { LuPlus, LuChevronLeft, LuChevronRight, LuSearch, LuRefreshCw, LuStore } from 'react-icons/lu';
import { Bot } from 'lucide-react';
import type { Agent, AgentToolResponse, AgentWithDetailsResponse } from '@/types';
import { AIAgentsApiService } from '@/services/aiAgentsApi';

/**
 * Agent management page component
 */
// Stable selectors to prevent unnecessary re-renders
const selectAgents = (state: any) => state.agents;
const selectCurrentPage = (state: any) => state.agentCurrentPage;
const selectPageSize = (state: any) => state.agentPageSize;
const selectIsLoadingAgents = (state: any) => state.isLoadingAgents;
const selectAgentsError = (state: any) => state.agentsError;
const selectSetCurrentPage = (state: any) => state.setAgentCurrentPage;
const selectCreateAgent = (state: any) => state.createAgent;
const selectUpdateAgent = (state: any) => state.updateAgent;
const selectDeleteAgent = (state: any) => state.deleteAgent;
const selectSetShowCreateAgentModal = (state: any) => state.setShowCreateAgentModal;
const selectLoadAgents = (state: any) => state.loadAgents;

const AgentManagement: React.FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const agents = useAIStore(selectAgents);
  const currentPage = useAIStore(selectCurrentPage);
  const pageSize = useAIStore(selectPageSize);
  const isLoadingAgents = useAIStore(selectIsLoadingAgents);
  const agentsError = useAIStore(selectAgentsError);
  const setCurrentPage = useAIStore(selectSetCurrentPage);
  const createAgent = useAIStore(selectCreateAgent);
  const updateAgent = useAIStore(selectUpdateAgent);
  const deleteAgent = useAIStore(selectDeleteAgent);
  const setShowCreateAgentModal = useAIStore(selectSetShowCreateAgentModal);
  const loadAgents = useAIStore(selectLoadAgents);

  const { showSuccess, showError } = useToast();

  // 模态框状态
  // const [selectedTool, setSelectedTool] = useState<AgentToolResponse | null>(null);
  // const [showToolDetail, setShowToolDetail] = useState(false);
  const [showEditAgent, setShowEditAgent] = useState(false);
  const [showAgentStore, setShowAgentStore] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Default agent state
  const [defaultAgent, setDefaultAgent] = useState<AgentWithDetailsResponse | null>(null);
  const [isLoadingDefaultAgent, setIsLoadingDefaultAgent] = useState(false);

  // Track if agents have been loaded to prevent multiple API calls
  const hasLoadedAgents = useRef(false);
  const hasLoadedDefaultAgent = useRef(false);

  // Load default agent info
  const loadDefaultAgent = useCallback(async () => {
    if (hasLoadedDefaultAgent.current) return;
    setIsLoadingDefaultAgent(true);
    try {
      hasLoadedDefaultAgent.current = true;
      const response = await AIAgentsApiService.getDefaultAgents({ limit: 1, offset: 0 });
      setDefaultAgent(response.data[0] ?? null);
    } catch (error) {
      hasLoadedDefaultAgent.current = false;
      console.error('Failed to load default agent:', error);
    } finally {
      setIsLoadingDefaultAgent(false);
    }
  }, []);

  // Load agents and default agent on component mount
  useEffect(() => {
    if (hasLoadedAgents.current) {
      return;
    }

    const loadInitialAgents = async () => {
      try {
        hasLoadedAgents.current = true;
        await loadAgents();
      } catch (error) {
        hasLoadedAgents.current = false;
        console.error('Failed to load agents on mount:', error);
        showError(
          t('agents.messages.loadFailed', '加载失败'),
          t('agents.messages.loadFailedDesc', '无法加载AI员工列表，请稍后重试')
        );
      }
    };

    void loadInitialAgents();
    void loadDefaultAgent();
  }, [loadAgents, loadDefaultAgent, showError, t]);

  const handleRefresh = async (silent = false) => {
    setIsRefreshing(true);
    try {
      await loadAgents();
      if (!silent) {
        showSuccess(t('agents.messages.refreshSuccess', '刷新成功'), t('agents.messages.refreshSuccessDesc', 'AI员工列表已更新'));
      }
    } catch {
      if (!silent) {
        showError(t('agents.messages.refreshFailed', '刷新失败'), t('agents.messages.refreshFailedDesc', '无法刷新AI员工列表'));
      }
    } finally {
      setIsRefreshing(false);
    }
  };

  // 在组件中计算分页和筛选
  const { paginatedAgents, totalPages } = React.useMemo(() => {
    const filtered = agents.filter((a: Agent) => 
      a.name.toLowerCase().includes(searchQuery.toLowerCase()) || 
      a.description?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      a.role?.toLowerCase().includes(searchQuery.toLowerCase())
    );
    const total = Math.ceil(filtered.length / pageSize);
    const startIndex = (currentPage - 1) * pageSize;
    const paginated = filtered.slice(startIndex, startIndex + pageSize);
    return { paginatedAgents: paginated, totalPages: total };
  }, [agents, currentPage, pageSize, searchQuery]);

  const handleCreateAgent = (): void => {
    setShowCreateAgentModal(true);
  };

  const handleChatWithDefaultAgent = (): void => {
    if (!defaultAgent) {
      showError(
        t('agents.messages.noDefaultAgent', '默认AI员工未加载'),
        t('agents.messages.noDefaultAgentDesc', '请稍后重试')
      );
      return;
    }
    const channelId = `${defaultAgent.id}-agent`;
    navigate(`/chat/1/${channelId}`, {
      state: {
        agentName: defaultAgent.name || t('agents.defaultAgent.defaultName', '默认AI员工'),
        platform: 'agent'
      }
    });
  };

  // Handle retry on error
  const handleRetry = useCallback(async (): Promise<void> => {
    try {
      await loadAgents();
    } catch (error) {
      console.error('Failed to retry loading agents:', error);
      showError(
        t('agents.messages.retryFailed', '重试失败'),
        t('agents.messages.retryFailedDesc', '无法加载AI员工列表，请稍后重试')
      );
    }
  }, [loadAgents, showError, t]);

  const handleAgentAction = (actionType: string, agent: Agent): void => {
    setSelectedAgent(agent);

    switch (actionType) {
      case 'view':
      case 'edit':
        setShowEditAgent(true);
        break;
      case 'delete':
        setShowDeleteConfirm(true);
        break;
      case 'deleted':
        // Agent was successfully deleted by the card component
        // No additional action needed as the store will update automatically
        console.log('Agent deleted:', agent.name);
        break;
      case 'copy':
        handleCopyAgent(agent);
        break;
      case 'refresh':
        handleRefreshAgent(agent);
        break;
      default:
        console.log('Unknown action:', actionType);
    }
  };

  const handleCopyAgent = async (agent: Agent): Promise<void> => {
    try {
      await createAgent({
        name: `${agent.name}${t('agents.copy.suffix', ' (副本)')}`,
        profession: agent.role || t('agents.copy.defaultProfession', '专家'),
        description: agent.description,
        llmModel: agent.llmModel || 'gemini-1.5-pro',
        tools: agent.tools,
        toolConfigs: {},
        knowledgeBases: agent.knowledgeBases
      });
      showSuccess(
        t('agents.messages.copySuccess', '复制成功'),
        t('agents.messages.copySuccessDesc', `AI员工 "${agent.name}" 已成功复制`, { name: agent.name })
      );
    } catch {
      showError(
        t('agents.messages.copyFailed', '复制失败'),
        t('agents.messages.copyFailedDesc', '复制AI员工时发生错误')
      );
    }
  };

  const handleRefreshAgent = async (agent: Agent): Promise<void> => {
    try {
      await updateAgent(agent.id, {
        status: agent.status === 'active' ? 'inactive' : 'active'
      });
      showSuccess(
        t('agents.messages.statusUpdateSuccess', '刷新成功'),
        t('agents.messages.statusUpdateSuccessDesc', `AI员工 "${agent.name}" 状态已更新`, { name: agent.name })
      );
    } catch (error) {
      console.error('Failed to refresh agent:', error);
      showError(
        t('agents.messages.statusUpdateFailed', '刷新失败'),
        t('agents.messages.statusUpdateFailedDesc', '更新AI员工状态时发生错误')
      );
    }
  };

  const handleDeleteAgent = async (): Promise<void> => {
    if (!selectedAgent) return;

    setIsDeleting(true);
    try {
      await deleteAgent(selectedAgent.id);
      showSuccess(
        t('agents.messages.deleteSuccess', '删除成功'),
        t('agents.messages.deleteSuccessDesc', `AI员工 "${selectedAgent.name}" 已删除`, { name: selectedAgent.name })
      );
      setShowDeleteConfirm(false);
      setSelectedAgent(null);
    } catch {
      showError(
        t('agents.messages.deleteFailed', '删除失败'),
        t('agents.messages.deleteFailedDesc', '删除AI员工时发生错误')
      );
    } finally {
      setIsDeleting(false);
    }
  };

  const handleToolClick = (tool: AgentToolResponse): void => {
    // TODO: Create AgentToolDetailModal for AgentToolResponse objects
    console.log('Tool clicked:', tool);
    // setSelectedTool(tool);
    // setShowToolDetail(true);
  };



  const handlePageChange = (page: number): void => {
    setCurrentPage(page);
  };

  return (
    <main className="flex-grow flex flex-col bg-[#f8fafc] dark:bg-gray-950 overflow-hidden">
      {/* Header */}
      <header className="px-8 py-5 bg-white/80 dark:bg-gray-900/80 backdrop-blur-xl border-b border-gray-200/50 dark:border-gray-800/50 flex flex-col md:flex-row md:items-center justify-between gap-4 sticky top-0 z-30">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100 flex items-center gap-2">
            <Bot className="w-7 h-7 text-blue-600" />
            {t('agents.title', 'AI员工管理')}
          </h2>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            {t('agents.subtitle', '管理和部署您的智能化数字员工')}
          </p>
        </div>
        
        <div className="flex items-center gap-3">
          <div className="relative group hidden sm:block">
            <LuSearch className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 group-focus-within:text-blue-500 transition-colors" />
            <input 
              type="text"
              placeholder={t('common.search', '搜索...')}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-10 pr-4 py-2 w-64 bg-gray-100/50 dark:bg-gray-800/50 border-transparent focus:bg-white dark:focus:bg-gray-800 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 rounded-xl text-sm transition-all outline-none"
            />
          </div>
          
          <div className="h-8 w-px bg-gray-200 dark:border-gray-800 mx-1 hidden sm:block"></div>
          
          <div className="flex items-center gap-2">
            <button
              className="p-2 text-gray-500 hover:text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded-xl transition-all"
              onClick={() => handleRefresh()}
              disabled={isRefreshing}
              title={t('common.refresh', '刷新')}
            >
              <LuRefreshCw className={`w-5 h-5 ${isRefreshing ? 'animate-spin' : ''}`} />
            </button>
            <button
              className="flex items-center gap-2 px-4 py-2 bg-indigo-50 hover:bg-indigo-100 text-indigo-600 text-sm font-bold rounded-xl transition-all active:scale-95 border border-indigo-100 dark:bg-indigo-900/20 dark:border-indigo-800/50 dark:text-indigo-400"
              onClick={() => setShowAgentStore(true)}
            >
              <LuStore className="w-4 h-4" />
              <span className="hidden sm:inline">{t('agents.actions.store', '招聘员工')}</span>
            </button>
            <button
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-bold rounded-xl shadow-lg shadow-blue-200 dark:shadow-none transition-all active:scale-95"
              onClick={handleCreateAgent}
            >
              <LuPlus className="w-4 h-4" />
              <span className="hidden sm:inline">{t('agents.actions.create', '创建AI员工')}</span>
            </button>
          </div>
        </div>
      </header>

      {/* Content Area */}
      <div className="flex-1 overflow-y-auto custom-scrollbar">
        <div className="max-w-[1600px] mx-auto p-8 space-y-8">
          
          {/* Quick Actions / Default Agent */}
          <div className="bg-gradient-to-r from-blue-600 to-indigo-700 rounded-3xl p-6 text-white shadow-xl shadow-blue-200 dark:shadow-none flex flex-col md:flex-row items-center justify-between gap-6 relative overflow-hidden">
            <div className="absolute inset-0 bg-[url('https://www.transparenttextures.com/patterns/cubes.png')] opacity-10"></div>
            <div className="relative z-10">
              <h3 className="text-xl font-bold flex items-center gap-2">
                <Bot className="w-6 h-6" />
                {defaultAgent?.name || t('agents.defaultAgent.defaultName', '默认AI员工')}
              </h3>
              <p className="text-blue-100 text-sm mt-1 opacity-90 max-w-xl">
                {defaultAgent?.instruction || t('agents.defaultAgent.description', '项目默认AI员工会在未显式指定目标时承接 AI 对话。')}
              </p>
            </div>
            <div className="flex items-center gap-3 relative z-10">
              <button
                onClick={handleChatWithDefaultAgent}
                disabled={!defaultAgent || isLoadingDefaultAgent}
                className="px-5 py-2.5 bg-white text-blue-600 hover:bg-blue-50 text-sm font-bold rounded-xl transition-all shadow-lg disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {t('agents.actions.defaultAgentChat', '与默认AI员工对话')}
              </button>
            </div>
          </div>

          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-bold text-gray-900 dark:text-gray-100">{t('agents.listTitle', 'AI员工列表')}</h3>
            </div>

            {agentsError ? (
              <AgentsErrorState error={agentsError} onRetry={handleRetry} />
            ) : isLoadingAgents ? (
              <AgentsGridSkeleton count={9} />
            ) : paginatedAgents.length === 0 ? (
              <AgentsEmptyState
                title={searchQuery ? t('agents.empty.noResults', '未找到相关AI员工') : t('agents.empty.title', '暂无AI员工')}
                description={searchQuery ? t('agents.empty.noResultsDesc', '请尝试更换搜索关键词') : t('agents.empty.description', '点击「创建AI员工」按钮开始创建您的第一个AI员工')}
                actionButton={!searchQuery && (
                  <button
                    onClick={handleCreateAgent}
                    className="inline-flex items-center px-6 py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-xl shadow-lg shadow-blue-200 dark:shadow-none transition-all"
                  >
                    <LuPlus className="w-4 h-4 mr-2" />
                    {t('agents.actions.create', '创建AI员工')}
                  </button>
                )}
              />
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
                {paginatedAgents.map((agent: Agent) => (
                  <AgentCard
                    key={agent.id}
                    agent={agent}
                    onAction={handleAgentAction}
                    onToolClick={handleToolClick}
                  />
                ))}
              </div>
            )}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex justify-center pt-4 pb-12">
              <nav className="flex items-center gap-1 p-1.5 bg-white dark:bg-gray-900 border border-gray-200/50 dark:border-gray-800 rounded-2xl shadow-sm">
                <button
                  className="p-2 rounded-xl text-gray-500 hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
                  onClick={() => handlePageChange(Math.max(1, currentPage - 1))}
                  disabled={currentPage === 1}
                >
                  <LuChevronLeft className="w-5 h-5" />
                </button>

                <div className="flex items-center gap-1 px-2">
                  {Array.from({ length: totalPages }, (_, i) => i + 1).map((page) => (
                    <button
                      key={page}
                      onClick={() => handlePageChange(page)}
                      className={`min-w-[36px] h-9 flex items-center justify-center rounded-xl text-sm font-bold transition-all ${
                        page === currentPage
                          ? 'bg-blue-600 text-white shadow-md shadow-blue-200 dark:shadow-none scale-105'
                          : 'text-gray-500 hover:bg-gray-50 dark:hover:bg-gray-800 hover:text-gray-900'
                      }`}
                    >
                      {page}
                    </button>
                  ))}
                </div>

                <button
                  className="p-2 rounded-xl text-gray-500 hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
                  onClick={() => handlePageChange(Math.min(totalPages, currentPage + 1))}
                  disabled={currentPage === totalPages}
                >
                  <LuChevronRight className="w-5 h-5" />
                </button>
              </nav>
            </div>
          )}
        </div>
      </div>

      {/* Modals */}
      <CreateAgentModal />
      <EditAgentModal agentId={selectedAgent?.id || null} isOpen={showEditAgent} onClose={() => setShowEditAgent(false)} />
      
      <ToolToastProvider>
        <AgentStoreModal 
          isOpen={showAgentStore} 
          onClose={() => setShowAgentStore(false)}
          onInstalled={() => handleRefresh(true)}
        />
      </ToolToastProvider>

      <ConfirmDialog
        isOpen={showDeleteConfirm}
        title={t('agents.modal.delete.title', '删除AI员工')}
        message={t('agents.modal.delete.message', `确定要删除AI员工 "${selectedAgent?.name}" 吗？此操作不可撤销。`, { name: selectedAgent?.name })}
        confirmText={t('agents.modal.delete.confirm', '删除')}
        cancelText={t('agents.modal.delete.cancel', '取消')}
        confirmVariant="danger"
        onConfirm={handleDeleteAgent}
        onCancel={() => setShowDeleteConfirm(false)}
        isLoading={isDeleting}
      />
    </main>
  );
};

export default AgentManagement;
