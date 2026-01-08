import React, { useState, useEffect, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { LuX, LuUsers, LuSave, LuMessageSquare, LuCpu, LuInfo, LuChevronRight, LuChevronDown, LuChevronUp, LuSettings } from 'react-icons/lu';
import { Loader2, Sparkles } from 'lucide-react';
import { aiTeamsApiService, TeamWithDetailsResponse, TeamUpdateRequest } from '@/services/aiTeamsApi';
import { useToast } from '@/hooks/useToast';
import { useProvidersStore } from '@/stores/providersStore';
import AIProvidersApiService from '@/services/aiProvidersApi';
import Toggle from '@/components/ui/Toggle';

interface TeamInfoModalProps {
  isOpen: boolean;
  onClose: () => void;
  team: TeamWithDetailsResponse | null;
  onTeamUpdated?: () => void;
}

const TeamInfoModal: React.FC<TeamInfoModalProps> = ({ isOpen, onClose, team, onTeamUpdated }) => {
  const { t } = useTranslation();
  const { showSuccess, showError } = useToast();

  const [isSaving, setIsSaving] = useState(false);
  const [isAdvancedOpen, setIsAdvancedOpen] = useState(false);

  // Form state
  const [formData, setFormData] = useState({
    name: '',
    model: '',
    instruction: '',
    expected_output: '',
    // Advanced config
    respond_directly: false,
    num_history_runs: 5,
    markdown: true,
    add_datetime_to_context: true,
    tool_call_limit: 10,
  });

  // Track if form has been modified
  const [isDirty, setIsDirty] = useState(false);

  // Model selection (from providers)
  const { providers, loadProviders } = useProvidersStore();
  const enabledProviderKeys = useMemo(() => {
    const enabled = (providers || []).filter((p) => p.enabled);
    return new Set(enabled.map((p) => AIProvidersApiService.kindToProviderKey(p.kind)));
  }, [providers]);

  // value format: "providerId:modelName"
  const [llmOptions, setLlmOptions] = useState<Array<{ value: string; label: string; providerId: string; modelName: string }>>([]);
  const [llmLoading, setLlmLoading] = useState(false);
  const [llmError, setLlmError] = useState<string | null>(null);
  // Track selected provider ID separately
  const [selectedProviderId, setSelectedProviderId] = useState<string | null>(null);

  // Load providers when modal opens
  useEffect(() => {
    if (!isOpen) return;
    if ((providers || []).length === 0) {
      loadProviders();
    }
  }, [isOpen, providers?.length, loadProviders]);

  // Fetch chat models from providers
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
            // Store providerId:modelName as value for later extraction
            const compositeValue = `${p.id}:${m}`;
            return { 
              value: compositeValue, 
              label: `${m} · ${p.name || p.provider}`,
              providerId: p.id,
              modelName: m
            };
          }));
        if (!cancelled) {
          setLlmOptions(options);
        }
      } catch (e: any) {
        if (!cancelled) setLlmError(e?.message || t('team.modal.models.error', '加载模型失败'));
      } finally {
        if (!cancelled) setLlmLoading(false);
      }
    };
    fetchChatOptions();
    return () => { cancelled = true; };
  }, [isOpen, enabledProviderKeys, t]);

  // Update form data when team changes
  useEffect(() => {
    if (team) {
      // Find the matching option for the current model to get the composite value
      const matchingOption = llmOptions.find(opt => opt.modelName === team.model);
      const config = team.config || {};
      
      setFormData({
        name: team.name || '',
        model: matchingOption?.value || team.model || '', // Use composite value if found
        instruction: team.instruction || '',
        expected_output: team.expected_output || '',
        // Advanced config
        respond_directly: config.respond_directly ?? false,
        num_history_runs: config.num_history_runs ?? 5,
        markdown: config.markdown ?? true,
        add_datetime_to_context: config.add_datetime_to_context ?? true,
        tool_call_limit: config.tool_call_limit ?? 10,
      });
      setSelectedProviderId(matchingOption?.providerId || null);
      setIsDirty(false);
    }
  }, [team, llmOptions]);

  const handleInputChange = (field: keyof typeof formData, value: any) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    setIsDirty(true);
    
    // When model changes, update selectedProviderId
    if (field === 'model') {
      const selectedOption = llmOptions.find(opt => opt.value === value);
      setSelectedProviderId(selectedOption?.providerId || null);
    }
  };

  const handleSave = async () => {
    if (!team || !isDirty) return;

    setIsSaving(true);
    try {
      const updateData: TeamUpdateRequest = {};

      // Only include changed fields
      if (formData.name !== team.name) {
        updateData.name = formData.name || null;
      }
      
      // Extract model name from composite value (providerId:modelName)
      const selectedOption = llmOptions.find(opt => opt.value === formData.model);
      const modelName = selectedOption?.modelName || formData.model;
      
      if (modelName !== team.model) {
        updateData.model = modelName || null;
        // Include ai_provider_id when model changes
        if (selectedProviderId) {
          updateData.ai_provider_id = selectedProviderId;
        }
      }
      if (formData.instruction !== (team.instruction || '')) {
        updateData.instruction = formData.instruction || null;
      }
      if (formData.expected_output !== (team.expected_output || '')) {
        updateData.expected_output = formData.expected_output || null;
      }

      // Always include config if dirty (or we can diff it too)
      updateData.config = {
        respond_directly: formData.respond_directly,
        num_history_runs: formData.num_history_runs,
        markdown: formData.markdown,
        add_datetime_to_context: formData.add_datetime_to_context,
        tool_call_limit: formData.tool_call_limit,
      };

      await aiTeamsApiService.updateTeam(team.id, updateData);
      showSuccess(
        t('team.modal.saveSuccess', '保存成功'),
        t('team.modal.saveSuccessDesc', '团队信息已更新')
      );
      setIsDirty(false);
      // Notify parent to refresh team data
      onTeamUpdated?.();
    } catch (err: any) {
      console.error('Failed to save team data:', err);
      showError(
        t('team.modal.saveFailed', '保存失败'),
        err.message || t('team.modal.saveFailedDesc', '更新团队信息时发生错误')
      );
    } finally {
      setIsSaving(false);
    }
  };

  const handleClose = () => {
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-hidden flex items-center justify-center p-4 sm:p-6">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-gray-900/60 dark:bg-black/80 backdrop-blur-sm transition-opacity animate-in fade-in duration-300"
        onClick={handleClose}
      />

      {/* Modal */}
      <div className="relative bg-white dark:bg-gray-900 rounded-3xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col animate-in zoom-in-95 duration-300">
        {/* Header */}
        <div className="flex items-center justify-between px-8 py-6 border-b border-gray-100 dark:border-gray-800">
          <div className="flex items-center gap-4">
            <div className="p-3 bg-blue-50 dark:bg-blue-900/30 rounded-2xl text-blue-600 dark:text-blue-400">
              <LuUsers className="w-6 h-6" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100">
                {t('team.modal.title', '团队信息')}
              </h2>
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
                {t('team.modal.subtitle', '配置您的 AI 协作团队，整合工具、工作流及知识库以增强集体能力')}
              </p>
            </div>
          </div>
          <button
            onClick={handleClose}
            className="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 rounded-xl transition-all"
          >
            <LuX className="w-6 h-6" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto custom-scrollbar px-8 py-8 space-y-8">
          {team ? (
            <>
              {/* Team Name */}
              <div className="space-y-3">
                <label className="flex items-center gap-2 text-sm font-bold text-gray-700 dark:text-gray-300">
                  <LuInfo className="w-4 h-4 text-blue-500" />
                  {t('team.modal.name', '团队名称')}
                </label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => handleInputChange('name', e.target.value)}
                  className="w-full px-4 py-3 rounded-2xl border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all outline-none"
                  placeholder={t('team.modal.namePlaceholder', '输入团队名称')}
                />
              </div>

              {/* Model */}
              <div className="space-y-3">
                <label className="flex items-center gap-2 text-sm font-bold text-gray-700 dark:text-gray-300">
                  <LuCpu className="w-4 h-4 text-purple-500" />
                  {t('team.modal.model', '默认 LLM 模型')}
                </label>
                <div className="relative">
                  <select
                    value={formData.model}
                    onChange={(e) => handleInputChange('model', e.target.value)}
                    className="w-full appearance-none px-4 py-3 rounded-2xl border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all outline-none"
                  >
                    {llmLoading ? (
                      <option value="">{t('team.modal.models.loading', '正在加载模型...')}</option>
                    ) : llmError ? (
                      <option value="">{t('team.modal.models.error', '加载模型失败')}</option>
                    ) : llmOptions.length === 0 ? (
                      <option value="">{t('team.modal.models.empty', '暂无可用模型')}</option>
                    ) : (
                      <>
                        {!formData.model && (
                          <option value="">{t('team.modal.models.selectPlaceholder', '请选择模型')}</option>
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
                    <LuChevronRight className="w-4 h-4 rotate-90" />
                  </div>
                </div>
                <p className="text-[11px] text-gray-500 flex items-center gap-1.5 px-1">
                  <Sparkles className="w-3 h-3 text-yellow-500" />
                  {t('team.modal.modelHint', '选择团队使用的默认 LLM 模型，子员工未配置时将使用此模型')}
                </p>
              </div>

              {/* Instruction */}
              <div className="space-y-3">
                <label className="flex items-center gap-2 text-sm font-bold text-gray-700 dark:text-gray-300">
                  <LuMessageSquare className="w-4 h-4 text-green-500" />
                  {t('team.modal.instruction', '团队协作指令')}
                </label>
                <div className="relative group">
                  <textarea
                    value={formData.instruction}
                    onChange={(e) => handleInputChange('instruction', e.target.value)}
                    rows={6}
                    className="w-full px-4 py-4 rounded-2xl border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all outline-none resize-none"
                    placeholder={t('team.modal.instructionPlaceholder', '描述团队的协作目标、规则和通用的系统指令...')}
                  />
                </div>
                <div className="p-4 bg-blue-50 dark:bg-blue-900/20 rounded-2xl border border-blue-100/50 dark:border-blue-800/50">
                  <p className="text-xs text-blue-600 dark:text-blue-400 leading-relaxed">
                    {t('team.modal.instructionHint', '💡 此指令作为团队全局背景，将整合工具调用、工作流执行及知识库能力，应用于所有成员以实现高效协作。')}
                  </p>
                </div>
              </div>

              {/* Advanced Configuration */}
              <div className="space-y-4">
                <button
                  type="button"
                  onClick={() => setIsAdvancedOpen(!isAdvancedOpen)}
                  className="flex items-center justify-between w-full px-6 py-4 bg-gray-50 dark:bg-gray-800/50 rounded-2xl border border-gray-100 dark:border-gray-700 hover:border-blue-500/50 transition-all group"
                >
                  <div className="flex items-center gap-3">
                    <LuSettings className={`w-5 h-5 ${isAdvancedOpen ? 'text-blue-500' : 'text-gray-400'} transition-colors`} />
                    <span className="font-bold text-gray-700 dark:text-gray-300">
                      {t('team.config.advanced', '高级配置')}
                    </span>
                  </div>
                  {isAdvancedOpen ? (
                    <LuChevronUp className="w-5 h-5 text-gray-400" />
                  ) : (
                    <LuChevronDown className="w-5 h-5 text-gray-400" />
                  )}
                </button>

                {isAdvancedOpen && (
                  <div className="px-2 py-2 space-y-6 animate-in slide-in-from-top-2 duration-200">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      {/* Respond Directly */}
                      <div className="flex items-center justify-between p-4 bg-white dark:bg-gray-900 rounded-2xl border border-gray-100 dark:border-gray-800">
                        <div>
                          <p className="text-sm font-bold text-gray-700 dark:text-gray-200">{t('config.respondDirectly', '直接响应')}</p>
                          <p className="text-xs text-gray-500">{t('config.respondDirectlyDesc', '跳过成员回答汇总，直接返回回答')}</p>
                        </div>
                        <Toggle
                          checked={formData.respond_directly}
                          onChange={(checked) => handleInputChange('respond_directly', checked)}
                        />
                      </div>

                      {/* Markdown */}
                      <div className="flex items-center justify-between p-4 bg-white dark:bg-gray-900 rounded-2xl border border-gray-100 dark:border-gray-800">
                        <div>
                          <p className="text-sm font-bold text-gray-700 dark:text-gray-200">{t('config.markdown', 'Markdown 格式')}</p>
                          <p className="text-xs text-gray-500">{t('config.markdownDesc', '使用 Markdown 格式化输出内容')}</p>
                        </div>
                        <Toggle
                          checked={formData.markdown}
                          onChange={(checked) => handleInputChange('markdown', checked)}
                        />
                      </div>

                      {/* Add Datetime */}
                      <div className="flex items-center justify-between p-4 bg-white dark:bg-gray-900 rounded-2xl border border-gray-100 dark:border-gray-800">
                        <div>
                          <p className="text-sm font-bold text-gray-700 dark:text-gray-200">{t('config.addDatetime', '添加日期时间')}</p>
                          <p className="text-xs text-gray-500">{t('config.addDatetimeDesc', '在上下文中包含当前日期时间')}</p>
                        </div>
                        <Toggle
                          checked={formData.add_datetime_to_context}
                          onChange={(checked) => handleInputChange('add_datetime_to_context', checked)}
                        />
                      </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
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
                          className="w-full px-4 py-3 rounded-2xl border border-gray-100 dark:border-gray-700 bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all outline-none"
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
                          className="w-full px-4 py-3 rounded-2xl border border-gray-100 dark:border-gray-700 bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all outline-none"
                        />
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </>
          ) : (
            <div className="flex flex-col items-center justify-center py-20 text-center">
              <div className="w-16 h-16 bg-gray-50 dark:bg-gray-800 rounded-full flex items-center justify-center mb-4">
                <LuUsers className="w-8 h-8 text-gray-300" />
              </div>
              <p className="text-gray-500 dark:text-gray-400 font-medium">
                {t('team.modal.noTeam', '未找到默认团队')}
              </p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-8 py-6 border-t border-gray-100 dark:border-gray-800 bg-gray-50/50 dark:bg-gray-800/30 flex items-center justify-end gap-3">
          <button
            onClick={handleClose}
            className="px-6 py-2.5 text-sm font-bold text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 hover:bg-white dark:hover:bg-gray-800 rounded-xl transition-all border border-transparent hover:border-gray-200 dark:hover:border-gray-700"
          >
            {t('common.cancel', '取消')}
          </button>
          <button
            onClick={handleSave}
            disabled={!isDirty || isSaving}
            className="flex items-center gap-2 px-8 py-2.5 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-200 dark:disabled:bg-gray-800 text-white text-sm font-bold rounded-xl shadow-lg shadow-blue-200 dark:shadow-none transition-all active:scale-95 disabled:cursor-not-allowed disabled:text-gray-400"
          >
            {isSaving ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <LuSave className="w-4 h-4" />
            )}
            {t('common.save', '保存')}
          </button>
        </div>
      </div>
    </div>
  );
};

export default TeamInfoModal;
