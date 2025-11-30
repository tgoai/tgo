import React, { useState, useEffect, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { LuX, LuUsers, LuSave } from 'react-icons/lu';
import { Loader2 } from 'lucide-react';
import { aiTeamsApiService, TeamWithDetailsResponse, TeamUpdateRequest } from '@/services/aiTeamsApi';
import { useToast } from '@/hooks/useToast';
import { useProvidersStore } from '@/stores/providersStore';
import AIProvidersApiService from '@/services/aiProvidersApi';

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

  // Form state
  const [formData, setFormData] = useState({
    name: '',
    model: '',
    instruction: '',
    expected_output: '',
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
      setFormData({
        name: team.name || '',
        model: matchingOption?.value || team.model || '', // Use composite value if found
        instruction: team.instruction || '',
        expected_output: team.expected_output || '',
      });
      setSelectedProviderId(matchingOption?.providerId || null);
      setIsDirty(false);
    }
  }, [team, llmOptions]);

  const handleInputChange = (field: keyof typeof formData, value: string) => {
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
    <div className="fixed inset-0 z-50 overflow-y-auto">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50 dark:bg-black/70 transition-opacity"
        onClick={handleClose}
      />

      {/* Modal */}
      <div className="relative min-h-screen flex items-center justify-center p-4">
        <div className="relative bg-white dark:bg-gray-800 rounded-xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
            <div className="flex items-center space-x-3">
              <div className="p-2 bg-purple-100 dark:bg-purple-900/30 rounded-lg">
                <LuUsers className="w-5 h-5 text-purple-600 dark:text-purple-400" />
              </div>
              <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                {t('team.modal.title', '团队信息')}
              </h2>
            </div>
            <button
              onClick={handleClose}
              className="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
            >
              <LuX className="w-5 h-5" />
            </button>
          </div>

          {/* Content */}
          <div className="px-6 py-4 overflow-y-auto max-h-[calc(90vh-140px)]">
            {team ? (
              <div className="space-y-6">
                {/* Team Name */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    {t('team.modal.name', '团队名称')}
                  </label>
                  <input
                    type="text"
                    value={formData.name}
                    onChange={(e) => handleInputChange('name', e.target.value)}
                    className="w-full px-4 py-2.5 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-blue-500 dark:focus:ring-blue-400 focus:border-transparent transition-colors"
                    placeholder={t('team.modal.namePlaceholder', '输入团队名称')}
                  />
                </div>

                {/* Model - Dropdown Select */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    {t('team.modal.model', 'LLM 模型')}
                  </label>
                  <select
                    value={formData.model}
                    onChange={(e) => handleInputChange('model', e.target.value)}
                    className="w-full px-4 py-2.5 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-blue-500 dark:focus:ring-blue-400 focus:border-transparent transition-colors"
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
                  <p className="mt-1.5 text-xs text-gray-500 dark:text-gray-400">
                    {t('team.modal.modelHint', '选择团队使用的默认 LLM 模型')}
                  </p>
                </div>

                {/* Instruction */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    {t('team.modal.instruction', '团队指令')}
                  </label>
                  <textarea
                    value={formData.instruction}
                    onChange={(e) => handleInputChange('instruction', e.target.value)}
                    rows={4}
                    className="w-full px-4 py-2.5 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-blue-500 dark:focus:ring-blue-400 focus:border-transparent transition-colors resize-none"
                    placeholder={t('team.modal.instructionPlaceholder', '输入团队的系统提示词或指令...')}
                  />
                  <p className="mt-1.5 text-xs text-gray-500 dark:text-gray-400">
                    {t('team.modal.instructionHint', '此指令将应用于团队中的所有智能体')}
                  </p>
                </div>
              </div>
            ) : (
              <div className="text-center py-12 text-gray-500 dark:text-gray-400">
                {t('team.modal.noTeam', '未找到默认团队')}
              </div>
            )}
          </div>

          {/* Footer */}
          {team && (
            <div className="flex items-center justify-end px-6 py-4 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
              <button
                onClick={handleClose}
                className="px-4 py-2 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors mr-3"
              >
                {t('team.modal.cancel', '取消')}
              </button>
              <button
                onClick={handleSave}
                disabled={!isDirty || isSaving}
                className="flex items-center px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:bg-gray-300 dark:disabled:bg-gray-600 disabled:cursor-not-allowed transition-colors"
              >
                {isSaving ? (
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                ) : (
                  <LuSave className="w-4 h-4 mr-2" />
                )}
                {t('team.modal.save', '保存')}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default TeamInfoModal;
