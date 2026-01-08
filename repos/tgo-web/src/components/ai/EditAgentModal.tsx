import React, { useState, useEffect, useMemo } from 'react';
import { X, Save, RotateCcw, Bot, Wrench, FolderOpen, XCircle, User, Briefcase, GitBranch, Sparkles, Layout, ChevronRight, Settings, ChevronDown, ChevronUp } from 'lucide-react';
import { useTranslation } from 'react-i18next';
// import { getIconComponent, getIconColor } from '@/components/knowledge/IconPicker';
import { useAIStore } from '@/stores';
import { useKnowledgeStore } from '@/stores';

import { useToast } from '@/hooks/useToast';
// import { transformToolSummaryList } from '@/utils/toolsTransform';
import { transformAiToolResponseList } from '@/utils/projectToolsTransform';
import { TransformUtils } from '@/utils/base/BaseTransform';
import Toggle from '@/components/ui/Toggle';

import SectionHeader from '@/components/ui/SectionHeader';
import { AIAgentsApiService, AIAgentsTransformUtils } from '@/services/aiAgentsApi';
import ToolSelectionModal from './ToolSelectionModal';
import KnowledgeBaseSelectionModal from './KnowledgeBaseSelectionModal';
import { WorkflowSelectionModal } from '@/components/workflow';
import type { Agent, AiTool, AgentToolResponse, KnowledgeBaseItem, AgentToolDetailed, AgentToolUnion, ToolSummary } from '@/types';
import type { WorkflowSummary } from '@/types/workflow';
import AgentToolsSection from '@/components/ui/AgentToolsSection';
import AgentKnowledgeBasesSection from '@/components/ui/AgentKnowledgeBasesSection';
import AgentWorkflowsSection from '@/components/ui/AgentWorkflowsSection';
import { useWorkflowStore } from '@/stores/workflowStore';
import { useAgentForm } from '@/hooks/useAgentForm';
import { useProjectToolsStore } from '@/stores/projectToolsStore';
import { useProvidersStore } from '@/stores/providersStore';
import AIProvidersApiService from '@/services/aiProvidersApi';

interface EditAgentModalProps {
  agentId: string | null;
  isOpen: boolean;
  onClose: () => void;
}

/**
 * AI员工编辑模态框组件
 */
const EditAgentModal: React.FC<EditAgentModalProps> = ({
  agentId,
  isOpen,
  onClose
}) => {
  const { updateAgent, refreshAgents } = useAIStore();
  const { knowledgeBases, fetchKnowledgeBases } = useKnowledgeStore();
  const { aiTools, loadTools } = useProjectToolsStore();
  const { showToast } = useToast();
  const { t } = useTranslation();

  // Providers + model options consistent with Settings → Model Providers
  const { providers, loadProviders } = useProvidersStore();
  const enabledProviderKeys = useMemo(() => {
    const enabled = (providers || []).filter((p) => p.enabled);
    return new Set(enabled.map((p) => AIProvidersApiService.kindToProviderKey(p.kind)));
  }, [providers]);

  const [llmOptions, setLlmOptions] = useState<Array<{ value: string; label: string }>>([]);
  const [llmLoading, setLlmLoading] = useState(false);
  const [llmError, setLlmError] = useState<string | null>(null);


  useEffect(() => {
    if (!isOpen) return;
    if ((providers || []).length === 0) {
      loadProviders().catch(() => {});
    }
  }, [isOpen, providers?.length, loadProviders]);

  useEffect(() => {
    if (!isOpen) return;
    let cancelled = false;
    const fetchChatOptions = async () => {
      if (enabledProviderKeys.size === 0) return;
      setLlmLoading(true);
      setLlmError(null);
      try {
        const svc = new AIProvidersApiService();
        const res = await svc.listProviders({ is_active: true, model_type: 'chat', limit: 100, offset: 0 });
        const options = (res.data || [])
          .filter((p: any) => enabledProviderKeys.has(p.provider) && Array.isArray(p.available_models) && p.available_models.length > 0)
          .flatMap((p: any) => (p.available_models || []).map((m: string) => {
            const ui = `${p.id}:${m}`;
            return { value: ui, label: `${m} · ${p.name || p.provider}` };
          }));
        if (!cancelled) {
          setLlmOptions(options);
        }
      } catch (e: any) {
        if (!cancelled) setLlmError(e?.message || t('agents.create.models.error', '加载模型失败'));
      } finally {
        if (!cancelled) setLlmLoading(false);
      }
    };
    fetchChatOptions();
    return () => { cancelled = true; };
  }, [isOpen, enabledProviderKeys, t]);

  // Agent data state
  const [agent, setAgent] = useState<Agent | null>(null);
  const [isLoadingAgent, setIsLoadingAgent] = useState(false);
  const [agentError, setAgentError] = useState<string | null>(null);

  // 表单状态（通过通用 hook 管理）
  const {
    formData,
    setFormData,
    handleInputChange,
    removeTool,
    removeKnowledgeBase,
    removeWorkflow,
    reset,
  } = useAgentForm();

  // Workflow store
  const { workflows, loadWorkflows } = useWorkflowStore();

  const [isUpdating, setIsUpdating] = useState(false);
  const [isAdvancedOpen, setIsAdvancedOpen] = useState(false);
  const [showToolSelectionModal, setShowToolSelectionModal] = useState(false);
  const [showKnowledgeBaseSelectionModal, setShowKnowledgeBaseSelectionModal] = useState(false);
  const [showWorkflowSelectionModal, setShowWorkflowSelectionModal] = useState(false);

  // Fetch agent data from API
  const fetchAgent = async (id: string): Promise<void> => {
    setIsLoadingAgent(true);
    setAgentError(null);

    try {
      const apiResponse = await AIAgentsApiService.getAgent(id);
      const agentData = AIAgentsTransformUtils.transformApiAgentToAgent(apiResponse);
      setAgent(agentData);
    } catch (error) {
      console.error('Failed to fetch agent:', error);
      const errorMessage = error instanceof Error ? error.message : t('agents.edit.loadAgentError', '无法加载AI员工详情');
      setAgentError(errorMessage);
      showToast('error', t('common.loadFailed', '加载失败'), t('agents.edit.loadAgentError', '无法加载AI员工详情，请稍后重试'));
    } finally {
      setIsLoadingAgent(false);
    }
  };

  // Fetch agent when modal opens or agentId changes
  useEffect(() => {
    if (isOpen && agentId) {
      fetchAgent(agentId);
    } else if (!isOpen) {
      // Reset state when modal closes
      setAgent(null);
      setAgentError(null);
    }
  }, [isOpen, agentId]);

  // 不再在编辑弹窗内主动拉取工具列表，直接使用 agent.tools 进行展示

  // Ensure knowledge bases are loaded when modal opens (for display of selected items)
  useEffect(() => {
    if (isOpen && knowledgeBases.length === 0) {
      try {
        fetchKnowledgeBases();
      } catch (e) {
        console.warn('Failed to load knowledge bases for EditAgentModal:', e);
      }
    }
  }, [isOpen]);

  // Ensure workflows are loaded when modal opens
  useEffect(() => {
    if (isOpen && workflows.length === 0) {
      loadWorkflows().catch((e) => {
        console.warn('Failed to load workflows for EditAgentModal:', e);
      });
    }
  }, [isOpen, workflows.length, loadWorkflows]);

  // 初始化表单数据（直接基于 agent.tools，无需依赖工具商店列表）
  useEffect(() => {
    if (agent && !isLoadingAgent) {
      // 直接使用 Agent 返回的工具详情
      const toolIds: string[] = agent.tools || [];

      // Handle knowledge bases - use collections if available, fallback to knowledgeBases
      const kbIds = agent.collections?.map(collection => collection.id) || agent.knowledgeBases || [];

      // Handle workflows - extract IDs if objects are returned
      const workflowIds = (agent.workflows || []).map((w: any) => typeof w === 'string' ? w : w.id);

      reset({
        name: agent.name,
        profession: agent.role || t('agents.copy.defaultProfession', '专家'),
        description: agent.description,
        llmModel: agent.llmModel || 'gemini-1.5-pro',
        tools: toolIds,
        toolConfigs: agent.toolConfigs || {},
        knowledgeBases: kbIds,
        workflows: workflowIds,
        // 高级配置
        markdown: agent.config?.markdown ?? true,
        add_datetime_to_context: agent.config?.add_datetime_to_context ?? true,
        tool_call_limit: agent.config?.tool_call_limit ?? 10,
        num_history_runs: agent.config?.num_history_runs ?? 5,
      });
    }
  }, [agent, knowledgeBases, isLoadingAgent]);



  // Ensure AI tools are available for mapping when saving
  useEffect(() => {
    if (aiTools.length === 0) {
      // Load AI tools list (only active Tool tools)
      loadTools(false).catch(() => {});
    }
  }, [aiTools.length, loadTools]);



  // 将 AgentToolResponse 转为用于展示的 AiTool 结构（最小化依赖）
  const agentToolToAiTool = (t: AgentToolUnion): AiTool => {
    // Branch 1: legacy AgentToolResponse shape with tool_name
    if ((t as AgentToolResponse) && typeof (t as AgentToolResponse).tool_name === 'string') {
      const tt = t as AgentToolResponse;
      const namePart = tt.tool_name.includes(':') ? tt.tool_name.split(':').slice(1).join(':') : (tt.tool_name || 'tool');
      const provider = tt.tool_name.includes(':') ? tt.tool_name.split(':')[0] : 'tool';
      return {
        id: tt.id,
        name: namePart,
        title: namePart,
        description: '',
        category: 'integration',
        status: tt.enabled ? 'active' : 'inactive',
        version: 'v1.0.0',
        author: provider,
        lastUpdated: new Date(tt.updated_at || Date.now()).toISOString().split('T')[0],
        usageCount: 0,
        rating: 0,
        tags: [],
        config: tt.config || undefined,
        short_no: provider,
      } as AiTool;
    }

    // Branch 2: detailed tool object from new API
    const tool = (t as AgentToolDetailed) || {};
    const statusMapped = TransformUtils.transformToolStatus((tool.status || 'ACTIVE') as any);
    const categoryMapped = TransformUtils.transformCategory(tool.category || 'integration');
    const shortNo = tool.tool_server?.short_no;
    const author = shortNo || tool.tool_server?.name || tool.tool_source_type || 'tool';

    return {
      id: tool.id,
      name: tool.title || tool.name || 'tool',
      title: tool.title || tool.name,
      description: tool.description || '',
      category: categoryMapped,
      status: statusMapped,
      version: tool.version || 'v1.0.0',
      author,
      lastUpdated: (tool.updated_at || tool.created_at || new Date().toISOString()).split('T')[0],
      usageCount: 0,
      rating: 0,
      tags: Array.isArray(tool.tags) ? tool.tags : [],
      config: tool.meta_data || undefined,
      input_schema: tool.input_schema,
      short_no: shortNo,
    } as AiTool;
  };

  // 已添加的Tool工具列表 - 结合 agent.tools 和 AI tools 数据
  const addedAiTools = useMemo(() => {
    const byId = new Map<string, AgentToolUnion>();
    ((agent?.agentTools as AgentToolUnion[]) || []).forEach((t) => byId.set(t.id, t));

    const toolsFromAgent = formData.tools
      .map(id => byId.get(id))
      .filter(Boolean) as AgentToolUnion[];

    // 对于不在 agent.tools 中的工具ID，从 AI tools 获取完整信息
    const missingIds = formData.tools.filter(id => !byId.has(id));
    const toolsFromStore = transformAiToolResponseList(aiTools)
      .filter((tool: AiTool) => missingIds.includes(tool.id));

    // 对于既不在 agent.tools 也不在工具商店中的工具ID，创建占位符
    const foundStoreIds = toolsFromStore.map(t => t.id);
    const stillMissingIds = missingIds.filter(id => !foundStoreIds.includes(id));
    const placeholderTools: AiTool[] = stillMissingIds.map(id => ({
      id,
      name: id,
      description: t('agents.edit.tools.pendingNewTool', '待保存的新工具'),
      category: 'integration',
      status: 'active',
      version: 'v1.0.0',
      author: 'tool',
      lastUpdated: new Date().toISOString().split('T')[0],
      usageCount: 0,
      rating: 0,
      tags: [],
    } as AiTool));

    return [
      ...toolsFromAgent.map(agentToolToAiTool),
      ...toolsFromStore,
      ...placeholderTools,
    ];
  }, [agent?.agentTools, formData.tools, aiTools]);

  // 知识库启用状态：后端暂不支持单独启用/禁用，选中即关联

  // 已添加的知识库列表 - 显示所有已添加的知识库（包括启用和禁用的）
  const addedKnowledgeBases = useMemo(() => {
    return (knowledgeBases as KnowledgeBaseItem[]).filter((kb: KnowledgeBaseItem) => formData.knowledgeBases.includes(kb.id));
  }, [knowledgeBases, formData.knowledgeBases]);

  // 已添加的工作流列表
  const addedWorkflows = useMemo<WorkflowSummary[]>(() => {
    return workflows.filter((wf) => formData.workflows.includes(wf.id));
  }, [workflows, formData.workflows]);

  // 输入处理由 hook 提供

  // 处理工具移除
  const handleToolRemove = (toolId: string) => { removeTool(toolId); };

  // 处理知识库移除
  const handleKnowledgeBaseRemove = (kbId: string) => { removeKnowledgeBase(kbId); };

  // 处理工作流移除
  const handleWorkflowRemove = (workflowId: string) => { removeWorkflow(workflowId); };

  // 知识库图标颜色由通用组件处理



  const resolvedLlmModel = useMemo(() => {
    const raw = formData.llmModel;
    if (!raw) return '';
    if (raw.includes(':')) return raw;
    const match = llmOptions.find(option => option.value.split(':').slice(1).join(':') === raw);
    return match ? match.value : '';
  }, [formData.llmModel, llmOptions]);


  const handleSubmit = async (e: React.FormEvent): Promise<void> => {
    e.preventDefault();
    if (!agent || !agentId) return;

    setIsUpdating(true);
    try {
      // 合并可用工具来源：AI tools + 当前已添加/选择的工具（包含 short_no）
      const extraSummaries: ToolSummary[] = addedAiTools.map((t) => ({
        id: t.id,
        name: t.name,
        title: t.title || t.name,
        description: t.description || null,
        version: t.version || '1.0.0',
        category: typeof t.category === 'string' ? t.category : (t.category as any) || null,
        tags: t.tags || [],
        status: 'ACTIVE',
        tool_source_type: 'Tool_SERVER',
        execution_count: null,
        created_at: new Date().toISOString(),
        tool_server_id: null,
        input_schema: t.input_schema || {},
        output_schema: null,
        short_no: t.short_no || null,
        is_installed: undefined,
      }));

      // Convert AI tools to ToolSummary format for compatibility
      const aiToolSummaries: ToolSummary[] = aiTools.map((aiTool) => ({
        id: aiTool.id,
        name: aiTool.name,
        title: aiTool.name,
        description: aiTool.description || null,
        version: '1.0.0',
        category: null,
        tags: [],
        status: 'ACTIVE',
        tool_source_type: 'Tool_SERVER',
        execution_count: null,
        created_at: aiTool.created_at,
        tool_server_id: null,
        input_schema: {},
        output_schema: null,
        short_no: null,
        is_installed: undefined,
      }));

      const byId = new Map<string, ToolSummary>();
      aiToolSummaries.forEach(ts => byId.set(ts.id, ts));
      extraSummaries.forEach(ts => byId.set(ts.id, ts));
      const mergedAvailable = Array.from(byId.values());

      // Preflight: ensure every selected tool has name
      const missing = formData.tools.filter(id => {
        const s = byId.get(id);
        return !s || !s.name;
      });
      if (missing.length > 0) {
        // Try to resolve readable names from addedAiTools
        const nameMap = new Map(addedAiTools.map(t => [t.id, t.title || t.name || t.id] as const));
        const missingNames = missing.map(id => nameMap.get(id) || id).join(t('common.separator', '、'));
        showToast('error', t('agents.edit.tools.missingTitle', '工具信息缺失'), t('agents.edit.tools.missingDesc', '以下工具缺少名称：{{names}}，请重新选择后重试', { names: missingNames }));
        setIsUpdating(false);
        return;
      }

      // Validate selected model and keep UI value (providerId:modelName)
      const uiModel = formData.llmModel;
      let normalized = uiModel;
      if (!uiModel || !uiModel.includes(':')) {
        // Try to resolve by matching model name to current options
        const match = llmOptions.find(o => o.value.split(':').slice(1).join(':') === uiModel);
        if (match) {
          normalized = match.value;
        } else {
          showToast('error', t('agents.create.models.selectPlaceholder', '请选择模型'), t('agents.edit.modelProviderRequired', '请重新选择一个有效的模型（需要包含提供商）'));
          setIsUpdating(false);
          return;
        }
      }

      await updateAgent(agentId, {
        name: formData.name,
        description: formData.description,
        llmModel: normalized,
        role: formData.profession,
        tools: formData.tools,
        toolConfigs: formData.toolConfigs,
        knowledgeBases: formData.knowledgeBases,
        workflows: formData.workflows,
      }, mergedAvailable);
      // 强制刷新列表，确保卡片立即展示最新 tools/collections
      await refreshAgents();
      showToast('success', t('agents.messages.updateSuccess', '更新成功'), t('agents.messages.updateSuccessDesc', 'AI员工 "{{name}}" 已成功更新', { name: formData.name }));
      onClose();
    } catch (error) {
      console.error('Failed to update agent:', error);
      const errorMessage = error instanceof Error ? error.message : t('agents.edit.updateFailedUnknown', '更新AI员工时发生未知错误');
      showToast('error', t('agents.messages.updateFailed', '更新失败'), errorMessage);
    } finally {
      setIsUpdating(false);
    }
  };

  const handleReset = (): void => {
    if (agent && !isLoadingAgent) {
      // Directly reset based on current agent.tools
      const toolIds: string[] = (agent.tools || []).map((t: any) => t.id);

      // Handle knowledge bases - use collections if available, fallback to knowledgeBases
      const kbIds = agent.collections?.map(collection => collection.id) || agent.knowledgeBases || [];

      // Handle workflows - extract IDs if objects are returned
      const workflowIds = (agent.workflows || []).map((w: any) => typeof w === 'string' ? w : w.id);

      reset({
        name: agent.name,
        profession: agent.role || t('agents.copy.defaultProfession', '专家'),
        description: agent.description,
        llmModel: agent.llmModel || 'gemini-1.5-pro',
        tools: toolIds,
        toolConfigs: agent.toolConfigs || {},
        knowledgeBases: kbIds,
        workflows: workflowIds,
        // 高级配置
        markdown: agent.config?.markdown ?? true,
        add_datetime_to_context: agent.config?.add_datetime_to_context ?? true,
        tool_call_limit: agent.config?.tool_call_limit ?? 10,
        num_history_runs: agent.config?.num_history_runs ?? 5,
      });
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-hidden flex items-center justify-center p-4 sm:p-6">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-gray-900/60 dark:bg-black/80 backdrop-blur-sm transition-opacity animate-in fade-in duration-300"
        onClick={onClose}
      />

      {/* Modal Container */}
      <div className="relative bg-white dark:bg-gray-900 rounded-[2rem] shadow-2xl w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col animate-in zoom-in-95 duration-300">
        {/* Header */}
        <div className="flex items-center justify-between px-8 py-6 border-b border-gray-100 dark:border-gray-800 bg-gradient-to-r from-blue-600 to-indigo-700 text-white">
          <div className="flex items-center gap-4">
            <div className="p-3 bg-white/10 backdrop-blur-md rounded-2xl">
              <Bot className="w-7 h-7 text-white" />
            </div>
            <div>
              <h2 className="text-xl font-bold">{t('agents.modal.edit.title', '编辑AI员工')}</h2>
              <p className="text-blue-100 text-xs mt-0.5 opacity-80">{t('agents.modal.edit.subtitle', '优化AI员工的行为和配置')}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-white/70 hover:text-white hover:bg-white/10 rounded-xl transition-all"
            disabled={isUpdating || isLoadingAgent}
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        {/* Loading State */}
        {isLoadingAgent && (
          <div className="flex-1 flex flex-col items-center justify-center py-24 bg-gray-50 dark:bg-gray-950">
            <div className="relative">
              <div className="w-16 h-16 border-4 border-blue-100 dark:border-blue-900/30 rounded-full" />
              <div className="absolute inset-0 w-16 h-16 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
            </div>
            <p className="mt-4 text-gray-500 font-medium">{t('agents.edit.loading', '正在获取AI员工配置...')}</p>
          </div>
        )}

        {/* Error State */}
        {agentError && !isLoadingAgent && (
          <div className="flex-1 flex flex-col items-center justify-center py-16 px-8 bg-gray-50 dark:bg-gray-950">
            <div className="p-4 bg-red-50 dark:bg-red-900/20 rounded-full mb-4">
              <XCircle className="w-12 h-12 text-red-500" />
            </div>
            <h3 className="text-lg font-bold text-gray-900 dark:text-gray-100 mb-2">{t('common.loadFailed', '配置加载失败')}</h3>
            <p className="text-gray-500 text-center max-w-md mb-6">{agentError}</p>
            <button
              onClick={() => agentId && fetchAgent(agentId)}
              className="px-8 py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-xl transition-all active:scale-95 shadow-lg shadow-blue-200 dark:shadow-none"
            >
              {t('common.retry', '重新加载')}
            </button>
          </div>
        )}

        {/* Form Content - Only show when agent is loaded */}
        {agent && !isLoadingAgent && !agentError && (
          <form onSubmit={handleSubmit} className="flex-1 flex flex-col min-h-0">
            <div className="flex-1 overflow-y-auto custom-scrollbar bg-gray-50 dark:bg-gray-950">
              <div className="p-8 space-y-8">
                {/* 基本信息 Section */}
                <div className="space-y-4">
                  <div className="flex items-center gap-2 px-1">
                    <User className="w-5 h-5 text-blue-600" />
                    <h3 className="font-bold text-gray-900 dark:text-gray-100 uppercase tracking-tight text-sm">
                      {t('agents.detail.basicInfo', '基本信息')}
                    </h3>
                  </div>
                  <div className="bg-white dark:bg-gray-900 p-6 rounded-3xl border border-gray-100 dark:border-gray-800 shadow-sm space-y-6">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      {/* AI员工名称 */}
                      <div className="space-y-2">
                        <label className="text-xs font-bold text-gray-500 dark:text-gray-400 ml-1 uppercase">
                          {t('agents.form.name', 'AI员工名称')} <span className="text-red-500">*</span>
                        </label>
                        <input
                          type="text"
                          value={formData.name}
                          onChange={(e) => handleInputChange('name', e.target.value)}
                          className="w-full px-4 py-3 bg-gray-50 dark:bg-gray-800/50 border border-gray-100 dark:border-gray-700 rounded-2xl focus:ring-4 focus:ring-blue-500/10 focus:border-blue-500 transition-all outline-none"
                          placeholder={t('agents.create.placeholders.name', '请输入AI员工名称')}
                          required
                          disabled={isUpdating}
                        />
                      </div>

                      {/* 职业/角色 */}
                      <div className="space-y-2">
                        <label className="text-xs font-bold text-gray-500 dark:text-gray-400 ml-1 uppercase">
                          {t('agents.form.profession', '职业/角色')} <span className="text-red-500">*</span>
                        </label>
                        <input
                          type="text"
                          value={formData.profession}
                          onChange={(e) => handleInputChange('profession', e.target.value)}
                          className="w-full px-4 py-3 bg-gray-50 dark:bg-gray-800/50 border border-gray-100 dark:border-gray-700 rounded-2xl focus:ring-4 focus:ring-blue-500/10 focus:border-blue-500 transition-all outline-none"
                          placeholder={t('agents.create.placeholders.profession', '例如：客服专员、技术支持')}
                          required
                          disabled={isUpdating}
                        />
                      </div>
                    </div>
                  </div>
                </div>

                {/* 模型配置 Section */}
                <div className="space-y-4">
                  <div className="flex items-center gap-2 px-1">
                    <Layout className="w-5 h-5 text-purple-600" />
                    <h3 className="font-bold text-gray-900 dark:text-gray-100 uppercase tracking-tight text-sm">
                      {t('agents.create.sections.modelConfig', '模型配置')}
                    </h3>
                  </div>
                  <div className="bg-white dark:bg-gray-900 p-6 rounded-3xl border border-gray-100 dark:border-gray-800 shadow-sm space-y-4">
                    <div className="space-y-2">
                      <label className="text-xs font-bold text-gray-500 dark:text-gray-400 ml-1 uppercase">
                        {t('agents.form.llmModel', 'LLM模型')} <span className="text-red-500">*</span>
                      </label>
                      <div className="relative">
                        <select
                          value={resolvedLlmModel}
                          onChange={(e) => handleInputChange('llmModel', e.target.value)}
                          className="w-full appearance-none px-4 py-3 bg-gray-50 dark:bg-gray-800/50 border border-gray-100 dark:border-gray-700 rounded-2xl focus:ring-4 focus:ring-purple-500/10 focus:border-purple-500 transition-all outline-none"
                          disabled={isUpdating || llmLoading}
                        >
                          {llmLoading ? (
                            <option value="">{t('agents.create.models.loading', '正在加载模型...')}</option>
                          ) : llmError ? (
                            <option value="">{t('agents.create.models.error', '加载模型失败')}</option>
                          ) : llmOptions.length === 0 ? (
                            <option value="">{t('agents.create.models.empty', '暂无可用模型')}</option>
                          ) : (
                            <>
                              {!resolvedLlmModel && (
                                <option value="">{t('agents.create.models.selectPlaceholder', '请选择模型')}</option>
                              )}
                              {/* Fallback option in case current value is a providerKey:model not present in options */}
                              {formData.llmModel && !llmOptions.some(o => o.value === formData.llmModel) && formData.llmModel.includes(':') && (
                                <option value={formData.llmModel}>
                                  {formData.llmModel.split(':').slice(1).join(':')} · {formData.llmModel.split(':')[0]}
                                </option>
                              )}
                              {llmOptions.map(option => (
                                <option key={option.value} value={option.value}>
                                  {option.label}
                                </option>
                              ))}
                            </>
                          )}
                        </select>
                        <div className="absolute right-4 top-1/2 -translate-y-1/2 pointer-events-none text-gray-400">
                          <ChevronRight className="w-4 h-4 rotate-90" />
                        </div>
                      </div>
                      {llmError && (
                        <p className="text-[11px] text-red-500 flex items-center gap-1 mt-1 ml-1">
                          <XCircle className="w-3 h-3" /> {t('agents.create.models.loadFailedInline', '模型加载失败: {{error}}', { error: llmError })}
                        </p>
                      )}
                    </div>
                  </div>
                </div>

                {/* 能力描述 Section */}
                <div className="space-y-4">
                  <div className="flex items-center gap-2 px-1">
                    <Sparkles className="w-5 h-5 text-green-600" />
                    <h3 className="font-bold text-gray-900 dark:text-gray-100 uppercase tracking-tight text-sm">
                      {t('agents.create.sections.description', '能力描述')}
                    </h3>
                  </div>
                  <div className="bg-white dark:bg-gray-900 p-6 rounded-3xl border border-gray-100 dark:border-gray-800 shadow-sm">
                    <div className="space-y-2">
                      <label className="text-xs font-bold text-gray-500 dark:text-gray-400 ml-1 uppercase">
                        {t('agents.form.detailedDescription', '详细提示词/指令')} <span className="text-red-500">*</span>
                      </label>
                      <textarea
                        value={formData.description}
                        onChange={(e) => handleInputChange('description', e.target.value)}
                        rows={6}
                        className="w-full px-4 py-4 bg-gray-50 dark:bg-gray-800/50 border border-gray-100 dark:border-gray-700 rounded-2xl focus:ring-4 focus:ring-green-500/10 focus:border-green-500 transition-all outline-none resize-none"
                        placeholder={t('agents.create.placeholders.description', '请详细描述AI员工的功能、职责和特点...')}
                        required
                      disabled={isUpdating}
                    />
                  </div>
                </div>
              </div>

              {/* Advanced Configuration Section */}
              <div className="space-y-4">
                <button
                  type="button"
                  onClick={() => setIsAdvancedOpen(!isAdvancedOpen)}
                  className="flex items-center justify-between w-full px-6 py-4 bg-white dark:bg-gray-900 rounded-3xl border border-gray-100 dark:border-gray-800 hover:border-blue-500/50 transition-all group shadow-sm"
                >
                  <div className="flex items-center gap-3">
                    <Settings className={`w-5 h-5 ${isAdvancedOpen ? 'text-blue-600' : 'text-gray-400'} transition-colors`} />
                    <h3 className="font-bold text-gray-900 dark:text-gray-100 uppercase tracking-tight text-sm">
                      {t('agents.config.advanced', '高级配置')}
                    </h3>
                  </div>
                  {isAdvancedOpen ? (
                    <ChevronUp className="w-5 h-5 text-gray-400" />
                  ) : (
                    <ChevronDown className="w-5 h-5 text-gray-400" />
                  )}
                </button>

                {isAdvancedOpen && (
                  <div className="p-6 bg-white dark:bg-gray-900 rounded-3xl border border-gray-100 dark:border-gray-800 shadow-sm space-y-6 animate-in slide-in-from-top-2 duration-200">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      {/* Markdown */}
                      <div className="flex items-center justify-between p-4 bg-gray-50 dark:bg-gray-800/50 rounded-2xl border border-gray-50 dark:border-gray-700">
                        <div>
                          <p className="text-sm font-bold text-gray-700 dark:text-gray-200">{t('config.markdown', 'Markdown 格式')}</p>
                          <p className="text-xs text-gray-500">{t('config.markdownDesc', '使用 Markdown 格式化输出内容')}</p>
                        </div>
                        <Toggle
                          checked={!!formData.markdown}
                          onChange={(checked) => handleInputChange('markdown', checked)}
                        />
                      </div>

                      {/* Add Datetime */}
                      <div className="flex items-center justify-between p-4 bg-gray-50 dark:bg-gray-800/50 rounded-2xl border border-gray-50 dark:border-gray-700">
                        <div>
                          <p className="text-sm font-bold text-gray-700 dark:text-gray-200">{t('config.addDatetime', '添加日期时间')}</p>
                          <p className="text-xs text-gray-500">{t('config.addDatetimeDesc', '在上下文中包含当前日期时间')}</p>
                        </div>
                        <Toggle
                          checked={!!formData.add_datetime_to_context}
                          onChange={(checked) => handleInputChange('add_datetime_to_context', checked)}
                        />
                      </div>

                      {/* History Runs */}
                      <div className="space-y-2">
                        <label className="text-xs font-bold text-gray-500 dark:text-gray-400 ml-1 uppercase">
                          {t('config.numHistoryRuns', '历史会话轮数')}
                        </label>
                        <input
                          type="number"
                          min={0}
                          max={20}
                          value={formData.num_history_runs}
                          onChange={(e) => handleInputChange('num_history_runs', parseInt(e.target.value) || 0)}
                          className="w-full px-4 py-3 rounded-2xl border border-gray-100 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all outline-none"
                        />
                      </div>

                      {/* Tool Call Limit */}
                      <div className="space-y-2">
                        <label className="text-xs font-bold text-gray-500 dark:text-gray-400 ml-1 uppercase">
                          {t('config.toolCallLimit', '工具调用限制')}
                        </label>
                        <input
                          type="number"
                          min={1}
                          max={50}
                          value={formData.tool_call_limit}
                          onChange={(e) => handleInputChange('tool_call_limit', parseInt(e.target.value) || 0)}
                          className="w-full px-4 py-3 rounded-2xl border border-gray-100 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all outline-none"
                        />
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* 资源关联 Section */}
                <div className="space-y-4">
                  <div className="flex items-center gap-2 px-1">
                    <Briefcase className="w-5 h-5 text-orange-600" />
                    <h3 className="font-bold text-gray-900 dark:text-gray-100 uppercase tracking-tight text-sm">
                      {t('agents.create.sections.resources', '资源关联')}
                    </h3>
                  </div>
                  <div className="grid grid-cols-1 gap-6">
                    {/* Tool工具 */}
                    <div className="bg-white dark:bg-gray-900 p-6 rounded-3xl border border-gray-100 dark:border-gray-800 shadow-sm">
                      <SectionHeader icon={<Wrench className="w-4 h-4 text-orange-600" />} title={t('agents.create.sections.tools', 'Tool工具')} />
                      <AgentToolsSection
                        tools={addedAiTools}
                        toolConfigs={formData.toolConfigs}
                        onAdd={() => setShowToolSelectionModal(true)}
                        onRemove={handleToolRemove}
                        disabled={isUpdating}
                      />
                    </div>

                    {/* 知识库 */}
                    <div className="bg-white dark:bg-gray-900 p-6 rounded-3xl border border-gray-100 dark:border-gray-800 shadow-sm">
                      <SectionHeader icon={<FolderOpen className="w-4 h-4 text-teal-600" />} title={t('agents.form.knowledge_bases', '知识库')} />
                      <AgentKnowledgeBasesSection
                        items={addedKnowledgeBases}
                        onAdd={() => setShowKnowledgeBaseSelectionModal(true)}
                        onRemove={handleKnowledgeBaseRemove}
                        disabled={isUpdating}
                      />
                    </div>

                    {/* 工作流 */}
                    <div className="bg-white dark:bg-gray-900 p-6 rounded-3xl border border-gray-100 dark:border-gray-800 shadow-sm">
                      <SectionHeader icon={<GitBranch className="w-4 h-4 text-purple-600" />} title={t('workflow.title', '工作流')} />
                      <AgentWorkflowsSection
                        workflows={addedWorkflows}
                        onAdd={() => setShowWorkflowSelectionModal(true)}
                        onRemove={handleWorkflowRemove}
                        disabled={isUpdating}
                      />
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Footer */}
            <div className="px-8 py-6 border-t border-gray-100 dark:border-gray-800 bg-white/50 dark:bg-gray-900/50 backdrop-blur-md flex items-center justify-end gap-3 rounded-b-[2rem]">
              <button
                type="button"
                onClick={onClose}
                className="flex items-center px-6 py-2.5 text-sm font-bold text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-xl transition-all"
                disabled={isUpdating}
              >
                {t('common.cancel', '取消')}
              </button>
              <button
                type="button"
                onClick={handleReset}
                className="flex items-center gap-2 px-6 py-2.5 text-sm font-bold text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-xl transition-all"
                disabled={isUpdating}
              >
                <RotateCcw className="w-4 h-4" />
                {t('common.reset', '重置')}
              </button>
              <button
                type="submit"
                disabled={isUpdating}
                className="flex items-center gap-2 px-8 py-2.5 bg-blue-600 hover:bg-blue-700 text-white text-sm font-bold rounded-xl shadow-lg shadow-blue-200 dark:shadow-none transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isUpdating ? (
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                ) : (
                <Save className="w-4 h-4" />
              )}
              {t('agents.edit.saveButton', '保存修改')}
            </button>
            </div>
          </form>
        )}
      </div>

      {/* Modals - Always available regardless of loading state */}
      <ToolSelectionModal
        isOpen={showToolSelectionModal}
        onClose={() => setShowToolSelectionModal(false)}
        selectedTools={formData.tools}
        toolConfigs={formData.toolConfigs}
        onConfirm={(selectedToolIds, toolConfigs) => {
          setFormData({
            tools: selectedToolIds,
            toolConfigs: toolConfigs,
          });
        }}
      />

      <KnowledgeBaseSelectionModal
        isOpen={showKnowledgeBaseSelectionModal}
        onClose={() => setShowKnowledgeBaseSelectionModal(false)}
        selectedKnowledgeBases={formData.knowledgeBases}
        onConfirm={(selectedKnowledgeBaseIds) => {
          setFormData({ knowledgeBases: selectedKnowledgeBaseIds });
        }}
      />

      <WorkflowSelectionModal
        isOpen={showWorkflowSelectionModal}
        onClose={() => setShowWorkflowSelectionModal(false)}
        selectedWorkflows={formData.workflows}
        onConfirm={(selectedWorkflowIds) => {
          setFormData({ workflows: selectedWorkflowIds });
        }}
      />
    </div>
  );
};

export default EditAgentModal;
