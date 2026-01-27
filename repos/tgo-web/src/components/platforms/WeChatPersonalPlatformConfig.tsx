import React, { useEffect, useMemo, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ChevronDown } from 'lucide-react';
import ConfirmDialog from '@/components/ui/ConfirmDialog';
import Select from '@/components/ui/Select';
import PlatformAISettings from '@/components/platforms/PlatformAISettings';
import VisionAgentConsole from '@/components/platforms/VisionAgentConsole';
import type { Platform, PlatformConfig, PlatformAIMode } from '@/types';
import { usePlatformStore } from '@/stores/platformStore';
import { useProvidersStore } from '@/stores/providersStore';
import { useToast } from '@/hooks/useToast';
import { showApiError, showSuccess } from '@/utils/toastHelpers';
import AIProvidersApiService from '@/services/aiProvidersApi';

interface Props {
    platform: Platform;
}

/**
 * WeChat Personal platform configuration component.
 * 
 * This platform uses tgo-vision-agent for UI automation via:
 * - AgentBay (cloud phone/desktop)
 * - VLM (visual language model) for screen analysis
 */
const WeChatPersonalPlatformConfig: React.FC<Props> = ({ platform }) => {
    const { t } = useTranslation();
    const { showToast } = useToast();
    const updatePlatformConfig = usePlatformStore(s => s.updatePlatformConfig);
    const resetPlatformConfig = usePlatformStore(s => s.resetPlatformConfig);
    const updatePlatform = usePlatformStore(s => s.updatePlatform);
    const deletePlatform = usePlatformStore(s => s.deletePlatform);
    const enablePlatform = usePlatformStore(s => s.enablePlatform);
    const disablePlatform = usePlatformStore(s => s.disablePlatform);
    const platforms = usePlatformStore(s => s.platforms);
    const providers = useProvidersStore(s => s.providers);
    const loadProviders = useProvidersStore(s => s.loadProviders);
    const hasConfigChanges = usePlatformStore(s => s.hasConfigChanges(platform.id));
    const isUpdating = usePlatformStore(s => s.isUpdating);
    const navigate = useNavigate();

    useEffect(() => {
        loadProviders();
    }, [loadProviders]);

    const [confirmOpen, setConfirmOpen] = useState(false);
    const [isDeleting, setIsDeleting] = useState(false);
    const [isToggling, setIsToggling] = useState(false);
    const isEnabled = platform.status === 'connected';

    // Vision model options state
    const [visionOptions, setVisionOptions] = useState<Array<{ value: string; label: string }>>([]);
    const [visionLoading, setVisionLoading] = useState(false);
    
    // Reasoning model options state
    const [reasoningOptions, setReasoningOptions] = useState<Array<{ value: string; label: string }>>([]);
    const [reasoningLoading, setReasoningLoading] = useState(false);

    const fetchModelOptions = useCallback(async () => {
        setVisionLoading(true);
        setReasoningLoading(true);
        try {
            const svc = new AIProvidersApiService();
            const res = await svc.listProjectModels({ model_type: 'chat', is_active: true });
            const allModels = res.data || [];
            
            // Vision models: require vision capability
            const visionOpts = allModels
                .filter((m: any) => m.capabilities?.vision)
                .map((m: any) => ({
                    value: `${m.provider_id}:${m.model_id}`,
                    label: `${m.model_name} · ${m.provider_name}`,
                }));
            setVisionOptions(visionOpts);
            
            // Reasoning models: all chat models can be used for reasoning
            const reasoningOpts = allModels.map((m: any) => ({
                value: `${m.provider_id}:${m.model_id}`,
                label: `${m.model_name} · ${m.provider_name}`,
            }));
            setReasoningOptions(reasoningOpts);
        } catch (e) {
            console.error('Failed to fetch model options', e);
        } finally {
            setVisionLoading(false);
            setReasoningLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchModelOptions();
    }, [fetchModelOptions, providers]);

    // Name editing
    const [platformName, setPlatformName] = useState<string>(platform.name);
    useEffect(() => { setPlatformName(platform.name); }, [platform.name]);
    const hasNameChanged = useMemo(() => platformName.trim() !== platform.name, [platformName, platform.name]);

    // AI Settings state
    const [aiAgentIds, setAiAgentIds] = useState<string[]>(platform.agent_ids ?? []);
    const [aiMode, setAiMode] = useState<PlatformAIMode>(platform.ai_mode ?? 'auto');
    const [fallbackTimeout, setFallbackTimeout] = useState<number | null>(platform.fallback_to_ai_timeout ?? null);

    useEffect(() => {
        setAiAgentIds(platform.agent_ids ?? []);
        setAiMode(platform.ai_mode ?? 'auto');
        setFallbackTimeout(platform.fallback_to_ai_timeout ?? null);
    }, [platform.agent_ids, platform.ai_mode, platform.fallback_to_ai_timeout]);

    const hasAISettingsChanged = useMemo(() => {
        const origAgentIds = platform.agent_ids ?? [];
        const origMode = platform.ai_mode ?? 'auto';
        const origTimeout = platform.fallback_to_ai_timeout ?? null;
        const agentIdsChanged = JSON.stringify(aiAgentIds.sort()) !== JSON.stringify([...origAgentIds].sort());
        const modeChanged = aiMode !== origMode;
        const timeoutChanged = fallbackTimeout !== origTimeout;
        return agentIdsChanged || modeChanged || timeoutChanged;
    }, [aiAgentIds, aiMode, fallbackTimeout, platform.agent_ids, platform.ai_mode, platform.fallback_to_ai_timeout]);

    const canSave = hasConfigChanges || hasNameChanged || hasAISettingsChanged;

    const [formValues, setFormValues] = useState(() => {
        const config = platform.config as any;
        return {
            agentbayApiKey: config?.agentbay_api_key ?? '',
            environmentType: config?.environment_type ?? 'mobile',
            imageId: config?.image_id ?? '',
            visionFullId: config?.vision_provider_id && config?.vision_model_id 
                ? `${config.vision_provider_id}:${config.vision_model_id}` 
                : '',
            reasoningFullId: config?.reasoning_provider_id && config?.reasoning_model_id
                ? `${config.reasoning_provider_id}:${config.reasoning_model_id}`
                : '',
            pollIntervalSeconds: config?.poll_interval_seconds ?? 10,
        };
    });

    useEffect(() => {
        const config = platform.config as any;
        setFormValues({
            agentbayApiKey: config?.agentbay_api_key ?? '',
            environmentType: config?.environment_type ?? 'mobile',
            imageId: config?.image_id ?? '',
            visionFullId: config?.vision_provider_id && config?.vision_model_id 
                ? `${config.vision_provider_id}:${config.vision_model_id}` 
                : '',
            reasoningFullId: config?.reasoning_provider_id && config?.reasoning_model_id
                ? `${config.reasoning_provider_id}:${config.reasoning_model_id}`
                : '',
            pollIntervalSeconds: config?.poll_interval_seconds ?? 10,
        });
    }, [platform]);

    const handleChange = (patch: Partial<typeof formValues>) => {
        setFormValues(v => ({ ...v, ...patch }));
        const toSave: Partial<PlatformConfig> = {};
        if (patch.agentbayApiKey !== undefined) toSave.agentbayApiKey = patch.agentbayApiKey;
        if (patch.environmentType !== undefined) toSave.environmentType = patch.environmentType;
        if (patch.imageId !== undefined) toSave.imageId = patch.imageId;
        
        if (patch.visionFullId !== undefined) {
            if (patch.visionFullId === '') {
                toSave.visionProviderId = '';
                toSave.visionModelId = '';
            } else {
                const [pId, ...mParts] = patch.visionFullId.split(':');
                toSave.visionProviderId = pId;
                toSave.visionModelId = mParts.join(':');
            }
        }
        
        if (patch.reasoningFullId !== undefined) {
            if (patch.reasoningFullId === '') {
                toSave.reasoningProviderId = '';
                toSave.reasoningModelId = '';
            } else {
                const [pId, ...mParts] = patch.reasoningFullId.split(':');
                toSave.reasoningProviderId = pId;
                toSave.reasoningModelId = mParts.join(':');
            }
        }
        
        if (patch.pollIntervalSeconds !== undefined) toSave.pollIntervalSeconds = patch.pollIntervalSeconds;
        updatePlatformConfig(platform.id, toSave);
    };

    const handleSave = async () => {
        try {
            // Validate required fields
            if (!formValues.agentbayApiKey?.trim()) {
                showToast(
                    'error',
                    t('platforms.wechatPersonal.messages.validationError', '验证失败'),
                    t('platforms.wechatPersonal.messages.agentbayKeyRequired', 'AgentBay API Key 为必填项')
                );
                return;
            }
            if (!formValues.imageId?.trim()) {
                showToast(
                    'error',
                    t('platforms.wechatPersonal.messages.validationError', '验证失败'),
                    t('platforms.wechatPersonal.messages.imageIdRequired', '镜像 ID 为必填项，请在 AgentBay 控制台创建镜像后获取')
                );
                return;
            }
            if (!formValues.visionFullId?.trim()) {
                showToast(
                    'error',
                    t('platforms.wechatPersonal.messages.validationError', '验证失败'),
                    t('platforms.wechatPersonal.messages.visionModelRequired', '视觉模型为必填项')
                );
                return;
            }
            if (!formValues.reasoningFullId?.trim()) {
                showToast(
                    'error',
                    t('platforms.wechatPersonal.messages.validationError', '验证失败'),
                    t('platforms.wechatPersonal.messages.reasoningModelRequired', '推理模型为必填项')
                );
                return;
            }

            const updates: Partial<Platform> = {};
            if (hasConfigChanges) {
                const [visionProviderId, ...visionModelParts] = (formValues.visionFullId || '').split(':');
                const visionModelId = visionModelParts.join(':');
                const [reasoningProviderId, ...reasoningModelParts] = (formValues.reasoningFullId || '').split(':');
                const reasoningModelId = reasoningModelParts.join(':');

                updates.config = {
                    agentbay_api_key: (formValues.agentbayApiKey || '').trim(),
                    environment_type: formValues.environmentType,
                    image_id: (formValues.imageId || '').trim(),
                    vision_provider_id: visionProviderId,
                    vision_model_id: visionModelId,
                    reasoning_provider_id: reasoningProviderId,
                    reasoning_model_id: reasoningModelId,
                    poll_interval_seconds: formValues.pollIntervalSeconds,
                } as any;
            }
            if (hasNameChanged) {
                updates.name = platformName.trim();
            }
            if (hasAISettingsChanged) {
                updates.agent_ids = aiAgentIds.length > 0 ? aiAgentIds : null;
                updates.ai_mode = aiMode;
                updates.fallback_to_ai_timeout = aiMode === 'assist' ? fallbackTimeout : null;
            }
            if (Object.keys(updates).length > 0) {
                await updatePlatform(platform.id, updates);
                if (hasConfigChanges) {
                    resetPlatformConfig(platform.id);
                }
            }
            showSuccess(showToast, t('platforms.wechatPersonal.messages.saveSuccess', '保存成功'), t('platforms.wechatPersonal.messages.saveSuccessMessage', '个人微信配置已更新'));
        } catch (e) {
            showApiError(showToast, e);
        }
    };

    const displayName = platform.display_name || platform.name;

    return (
        <main className="flex flex-col flex-1 min-h-0 bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-900 dark:to-gray-800">
            <header className="px-6 py-4 border-b border-gray-200/80 dark:border-gray-700/80 flex justify-between items-center bg-white/60 dark:bg-gray-800/60 backdrop-blur-lg sticky top-0 z-10">
                <div>
                    <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-200">{t('platforms.wechatPersonal.header.title', { name: displayName, defaultValue: '{{name}} 配置' })}</h2>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{t('platforms.wechatPersonal.header.subtitle', '通过 VLM + AgentBay 实现个人微信消息自动化收发。')}</p>
                </div>
                <div className="flex items-center gap-3">
                    <button
                        disabled={isUpdating || isDeleting}
                        onClick={() => setConfirmOpen(true)}
                        className={`px-3 py-1.5 text-sm rounded-md ${isDeleting ? 'bg-red-400 text-white' : 'bg-red-600 dark:bg-red-500 text-white hover:bg-red-700 dark:hover:bg-red-600'}`}
                    >
                        {isDeleting ? t('platforms.wechatPersonal.buttons.deleting', '删除中…') : t('platforms.wechatPersonal.buttons.delete', '删除')}
                    </button>
                    <button
                        disabled={isUpdating || isDeleting || isToggling}
                        onClick={async () => {
                            if (isToggling) return;
                            setIsToggling(true);
                            try {
                                if (isEnabled) {
                                    await disablePlatform(platform.id);
                                    showSuccess(showToast, t('platforms.wechatPersonal.messages.disabled', '平台已禁用'));
                                } else {
                                    await enablePlatform(platform.id);
                                    showSuccess(showToast, t('platforms.wechatPersonal.messages.enabled', '平台已启用'));
                                }
                            } catch (e) {
                                showApiError(showToast, e);
                            } finally {
                                setIsToggling(false);
                            }
                        }}
                        className={`px-3 py-1.5 text-sm rounded-md text-white ${isEnabled ? 'bg-gray-600 dark:bg-gray-500 hover:bg-gray-700 dark:hover:bg-gray-600' : 'bg-green-600 dark:bg-green-500 hover:bg-green-700 dark:hover:bg-green-600'} ${isToggling ? 'opacity-70 cursor-not-allowed' : ''}`}
                    >
                        {isToggling ? (isEnabled ? t('platforms.wechatPersonal.buttons.disabling', '禁用中…') : t('platforms.wechatPersonal.buttons.enabling', '启用中…')) : (isEnabled ? t('platforms.wechatPersonal.buttons.disable', '禁用') : t('platforms.wechatPersonal.buttons.enable', '启用'))}
                    </button>

                    <button
                        disabled={!canSave || isUpdating}
                        onClick={handleSave}
                        className={`px-3 py-1.5 text-sm rounded-md ${canSave ? 'bg-blue-600 dark:bg-blue-500 text-white hover:bg-blue-700 dark:hover:bg-blue-600' : 'bg-gray-200 dark:bg-gray-700 text-gray-500 dark:text-gray-400 cursor-not-allowed'}`}
                    >
                        {isUpdating ? t('platforms.wechatPersonal.buttons.saving', '保存中…') : t('platforms.wechatPersonal.buttons.save', '保存')}
                    </button>
                </div>
            </header>

            <div className="flex flex-1 min-h-0 flex-col lg:flex-row gap-4 p-6">
                {/* Left: form */}
                <section className="lg:w-2/5 w-full bg-white/80 dark:bg-gray-800/80 backdrop-blur-md p-5 rounded-lg shadow-sm border border-gray-200/60 dark:border-gray-700/60 space-y-4 overflow-y-auto min-h-0 auto-hide-scrollbar">
                    {/* 平台名称 */}
                    <div>
                        <label className="block text-sm font-medium text-gray-600 dark:text-gray-300 mb-1">{t('platforms.wechatPersonal.form.name', '平台名称')}</label>
                        <input
                            type="text"
                            value={platformName}
                            onChange={(e) => setPlatformName(e.target.value)}
                            placeholder={t('platforms.wechatPersonal.form.namePlaceholder', '请输入平台名称')}
                            className="w-full text-sm p-1.5 border border-gray-300/80 dark:border-gray-600/80 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 dark:focus:ring-blue-400 focus:border-blue-500 dark:focus:border-blue-400 bg-white/90 dark:bg-gray-700/50 dark:text-gray-200"
                        />
                    </div>

                    {/* AgentBay Configuration */}
                    <div className="border-t border-gray-200 dark:border-gray-700 pt-4">
                        <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-200 mb-3">{t('platforms.wechatPersonal.form.agentbaySection', 'AgentBay 配置')}</h4>
                        
                        {/* AgentBay API Key */}
                        <div className="mb-3">
                            <label className="block text-sm font-medium text-gray-600 dark:text-gray-300 mb-1">{t('platforms.wechatPersonal.form.agentbayApiKey', 'AgentBay API Key')}</label>
                            <input
                                type="password"
                                value={formValues.agentbayApiKey}
                                onChange={(e) => handleChange({ agentbayApiKey: e.target.value })}
                                placeholder={t('platforms.wechatPersonal.form.agentbayApiKeyPlaceholder', '输入您的 AgentBay API Key')}
                                className="w-full text-sm p-1.5 border border-gray-300/80 dark:border-gray-600/80 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 dark:focus:ring-blue-400 focus:border-blue-500 dark:focus:border-blue-400 bg-white/90 dark:bg-gray-700/50 dark:text-gray-200"
                            />
                            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">{t('platforms.wechatPersonal.form.agentbayApiKeyHint', '从阿里云无影 AgentBay 控制台获取。')}</p>
                        </div>

                        {/* Environment Type */}
                        <div className="mb-3">
                            <label className="block text-sm font-medium text-gray-600 dark:text-gray-300 mb-1">{t('platforms.wechatPersonal.form.environmentType', '运行环境')}</label>
                            <select
                                value={formValues.environmentType}
                                onChange={(e) => handleChange({ environmentType: e.target.value })}
                                className="w-full text-sm p-1.5 border border-gray-300/80 dark:border-gray-600/80 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 dark:focus:ring-blue-400 focus:border-blue-500 dark:focus:border-blue-400 bg-white/90 dark:bg-gray-700/50 dark:text-gray-200"
                            >
                                <option value="mobile">{t('platforms.wechatPersonal.form.envMobile', '云手机 (MobileUse)')}</option>
                                <option value="desktop">{t('platforms.wechatPersonal.form.envDesktop', '云桌面 (ComputerUse)')}</option>
                            </select>
                            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">{t('platforms.wechatPersonal.form.environmentTypeHint', '推荐使用云手机以获得最佳稳定性。')}</p>
                        </div>

                        {/* Image ID */}
                        <div className="mb-3">
                            <label className="block text-sm font-medium text-gray-600 dark:text-gray-300 mb-1">
                                {t('platforms.wechatPersonal.form.imageId', '镜像 ID')}
                                <span className="text-red-500 ml-0.5">*</span>
                            </label>
                            <input
                                type="text"
                                value={formValues.imageId}
                                onChange={(e) => handleChange({ imageId: e.target.value })}
                                placeholder={t('platforms.wechatPersonal.form.imageIdPlaceholder', '请输入 AgentBay 镜像 ID')}
                                className="w-full text-sm p-1.5 border border-gray-300/80 dark:border-gray-600/80 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 dark:focus:ring-blue-400 focus:border-blue-500 dark:focus:border-blue-400 bg-white/90 dark:bg-gray-700/50 dark:text-gray-200"
                            />
                            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                                {t('platforms.wechatPersonal.form.imageIdHint', '请在 AgentBay 控制台创建镜像后获取，')}
                                <a 
                                    href="https://help.aliyun.com/document_detail/2618946.html" 
                                    target="_blank" 
                                    rel="noopener noreferrer"
                                    className="text-blue-500 hover:text-blue-600 dark:text-blue-400"
                                >
                                    {t('platforms.wechatPersonal.form.viewDocs', '查看文档')}
                                </a>
                            </p>
                        </div>
                    </div>

                    {/* Model Configuration */}
                    <div className="border-t border-gray-200 dark:border-gray-700 pt-4">
                        <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-200 mb-3">{t('platforms.wechatPersonal.form.modelSection', 'AI 模型配置')}</h4>
                        
                        {/* Vision Model selection */}
                        <div className="mb-3">
                            <label className="block text-sm font-medium text-gray-600 dark:text-gray-300 mb-1">
                                {t('platforms.wechatPersonal.form.visionModel', '视觉模型')}
                                <span className="text-red-500 ml-0.5">*</span>
                            </label>
                            <Select
                                value={formValues.visionFullId}
                                onChange={(val) => handleChange({ visionFullId: val })}
                                options={visionOptions}
                                isLoading={visionLoading}
                                placeholder={t('platforms.wechatPersonal.form.selectVisionModel', '请选择视觉模型')}
                                emptyMessage={t('platforms.wechatPersonal.form.noVisionModels', '暂无可用视觉模型')}
                            />
                            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">{t('platforms.wechatPersonal.form.visionModelHint', '用于屏幕分析和元素定位，推荐 Qwen-VL-Max 或 GPT-4o。')}</p>
                        </div>
                        
                        {/* Reasoning Model selection */}
                        <div className="mb-3">
                            <label className="block text-sm font-medium text-gray-600 dark:text-gray-300 mb-1">
                                {t('platforms.wechatPersonal.form.reasoningModel', '推理模型')}
                                <span className="text-red-500 ml-0.5">*</span>
                            </label>
                            <Select
                                value={formValues.reasoningFullId}
                                onChange={(val) => handleChange({ reasoningFullId: val })}
                                options={reasoningOptions}
                                isLoading={reasoningLoading}
                                placeholder={t('platforms.wechatPersonal.form.selectReasoningModel', '请选择推理模型')}
                                emptyMessage={t('platforms.wechatPersonal.form.noReasoningModels', '暂无可用推理模型')}
                            />
                            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">{t('platforms.wechatPersonal.form.reasoningModelHint', '用于任务规划和动作决策，推荐 Qwen-Plus 或 GPT-4o。')}</p>
                        </div>
                    </div>

                    {/* Polling Configuration */}
                    <div className="border-t border-gray-200 dark:border-gray-700 pt-4">
                        <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-200 mb-3">{t('platforms.wechatPersonal.form.pollingSection', '轮询配置')}</h4>
                        
                        <div>
                            <label className="block text-sm font-medium text-gray-600 dark:text-gray-300 mb-1">{t('platforms.wechatPersonal.form.pollInterval', '消息轮询间隔 (秒)')}</label>
                            <input
                                type="number"
                                min={5}
                                max={60}
                                value={formValues.pollIntervalSeconds}
                                onChange={(e) => handleChange({ pollIntervalSeconds: parseInt(e.target.value) || 10 })}
                                className="w-full text-sm p-1.5 border border-gray-300/80 dark:border-gray-600/80 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 dark:focus:ring-blue-400 focus:border-blue-500 dark:focus:border-blue-400 bg-white/90 dark:bg-gray-700/50 dark:text-gray-200"
                            />
                            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">{t('platforms.wechatPersonal.form.pollIntervalHint', '建议设置为 5-15 秒，较短间隔会增加 API 调用成本。')}</p>
                        </div>
                    </div>

                    {/* AI Settings */}
                    <PlatformAISettings
                        platform={platform}
                        agentIds={aiAgentIds}
                        aiMode={aiMode}
                        fallbackTimeout={fallbackTimeout}
                        onAgentIdsChange={setAiAgentIds}
                        onAIModeChange={setAiMode}
                        onFallbackTimeoutChange={setFallbackTimeout}
                    />
                </section>

                {/* Right: Vision Console + Guide */}
                <section className="lg:w-3/5 w-full flex flex-col gap-4 min-h-0">
                    {/* Vision Agent Console */}
                    <div className="flex-1 bg-white/80 dark:bg-gray-800/80 backdrop-blur-md p-5 rounded-lg shadow-sm border border-gray-200/60 dark:border-gray-700/60 min-h-[400px] overflow-hidden">
                        <h3 className="text-lg font-semibold text-gray-800 dark:text-gray-100 mb-3">{t('platforms.wechatPersonal.console.title', '可视化控制台')}</h3>
                        <VisionAgentConsole
                            platformId={platform.id}
                            isEnabled={isEnabled}
                        />
                    </div>

                    {/* Collapsible Guide */}
                    <details className="bg-white/80 dark:bg-gray-800/80 backdrop-blur-md rounded-lg shadow-sm border border-gray-200/60 dark:border-gray-700/60">
                        <summary className="cursor-pointer p-4 flex items-center justify-between hover:bg-gray-50/50 dark:hover:bg-gray-700/50 rounded-lg transition-colors">
                            <h3 className="text-base font-semibold text-gray-800 dark:text-gray-100">{t('platforms.wechatPersonal.guide.title', '个人微信接入指南')}</h3>
                            <ChevronDown className="w-5 h-5 text-gray-500 transition-transform details-open:rotate-180" />
                        </summary>
                        <div className="px-4 pb-4 space-y-3">
                            <div className="bg-amber-50 dark:bg-amber-900/30 border border-amber-200 dark:border-amber-700 text-amber-800 dark:text-amber-200 text-sm rounded-md p-3">
                                <p className="font-medium">{t('platforms.wechatPersonal.guide.warning', '重要提示')}</p>
                                <p className="mt-1">{t('platforms.wechatPersonal.guide.warningText', '个人微信接入使用 UI 自动化技术，可能违反微信服务条款。请谨慎使用，仅用于合法的客服场景。')}</p>
                            </div>

                            <div className="bg-blue-50 dark:bg-blue-900/30 border border-blue-200 dark:border-blue-700 text-blue-800 dark:text-blue-200 text-sm rounded-md p-3">
                                <p className="font-medium">{t('platforms.wechatPersonal.guide.overview', '工作原理')}</p>
                                <p className="mt-1">{t('platforms.wechatPersonal.guide.overviewText', '本平台通过 AgentBay 云手机运行微信，使用视觉语言模型 (VLM) 分析界面截图，自动识别新消息并发送回复。')}</p>
                            </div>

                            <details className="rounded-md border border-gray-200 dark:border-gray-600 p-3 bg-white/70 dark:bg-gray-700/50">
                                <summary className="cursor-pointer font-semibold text-gray-800 dark:text-gray-100 text-sm">{t('platforms.wechatPersonal.guide.step1Title', '1. 获取 AgentBay API Key')}</summary>
                                <div className="text-sm text-gray-700 dark:text-gray-300 mt-2 space-y-2">
                                    <ol className="list-decimal pl-5 space-y-1">
                                        <li dangerouslySetInnerHTML={{ __html: t('platforms.wechatPersonal.guide.step1Item1', '访问 <a class="text-blue-600 hover:underline" href="https://www.aliyun.com/product/wuying/agentbay" target="_blank" rel="noreferrer">阿里云无影 AgentBay</a> 控制台。') }} />
                                        <li>{t('platforms.wechatPersonal.guide.step1Item2', '创建或选择一个 AgentBay 项目。')}</li>
                                        <li>{t('platforms.wechatPersonal.guide.step1Item3', '在项目设置中获取 API Key 并填入左侧配置。')}</li>
                                    </ol>
                                </div>
                            </details>

                            <details className="rounded-md border border-gray-200 dark:border-gray-600 p-3 bg-white/70 dark:bg-gray-700/50">
                                <summary className="cursor-pointer font-semibold text-gray-800 dark:text-gray-100 text-sm">{t('platforms.wechatPersonal.guide.step2Title', '2. 配置视觉模型')}</summary>
                                <div className="text-sm text-gray-700 dark:text-gray-300 mt-2 space-y-2">
                                    <ol className="list-decimal pl-5 space-y-1">
                                        <li>{t('platforms.wechatPersonal.guide.step2Item1', '在「设置 - AI Providers」中配置支持视觉的模型提供商。')}</li>
                                        <li>{t('platforms.wechatPersonal.guide.step2Item2', '推荐使用 GPT-4o、Claude 3.5 Sonnet 或 Qwen-VL-Max。')}</li>
                                        <li>{t('platforms.wechatPersonal.guide.step2Item3', '在左侧「视觉模型」下拉菜单中选择已配置的模型。')}</li>
                                    </ol>
                                </div>
                            </details>

                            <details className="rounded-md border border-gray-200 dark:border-gray-600 p-3 bg-white/70 dark:bg-gray-700/50">
                                <summary className="cursor-pointer font-semibold text-gray-800 dark:text-gray-100 text-sm">{t('platforms.wechatPersonal.guide.step3Title', '3. 启动并登录微信')}</summary>
                                <div className="text-sm text-gray-700 dark:text-gray-300 mt-2 space-y-2">
                                    <ol className="list-decimal pl-5 space-y-1">
                                        <li>{t('platforms.wechatPersonal.guide.step3Item1', '保存配置后，点击「启用」按钮。')}</li>
                                        <li>{t('platforms.wechatPersonal.guide.step3Item2', '系统将创建 AgentBay 会话并启动微信。')}</li>
                                        <li>{t('platforms.wechatPersonal.guide.step3Item3', '在控制台区域扫描二维码完成微信登录。')}</li>
                                    </ol>
                                </div>
                            </details>

                            <details className="rounded-md border border-gray-200 dark:border-gray-600 p-3 bg-white/70 dark:bg-gray-700/50">
                                <summary className="cursor-pointer font-semibold text-gray-800 dark:text-gray-100 text-sm">{t('platforms.wechatPersonal.guide.step4Title', '4. 配置 AI Agent')}</summary>
                                <div className="text-sm text-gray-700 dark:text-gray-300 mt-2 space-y-2">
                                    <ol className="list-decimal pl-5 space-y-1">
                                        <li>{t('platforms.wechatPersonal.guide.step4Item1', '在左侧「AI 设置」区域选择要使用的 AI Agent。')}</li>
                                        <li>{t('platforms.wechatPersonal.guide.step4Item2', '设置 AI 模式（自动/辅助/关闭）。')}</li>
                                        <li>{t('platforms.wechatPersonal.guide.step4Item3', '保存后，AI 将自动响应收到的微信消息。')}</li>
                                    </ol>
                                </div>
                            </details>
                        </div>
                    </details>
                </section>
            </div>

            <style>{`
                .auto-hide-scrollbar { scrollbar-width: thin; scrollbar-color: rgba(0,0,0,0.3) transparent; }
                .auto-hide-scrollbar::-webkit-scrollbar { width: 8px; height: 8px; }
                .auto-hide-scrollbar::-webkit-scrollbar-thumb { background-color: transparent; border-radius: 4px; }
                .auto-hide-scrollbar:hover::-webkit-scrollbar-thumb { background-color: rgba(0,0,0,0.35); }
            `}</style>
            <ConfirmDialog
                isOpen={confirmOpen}
                title={t('platforms.wechatPersonal.dialog.deleteTitle', '确认删除')}
                message={t('platforms.wechatPersonal.dialog.deleteMessage', '确定要删除此个人微信平台吗？此操作不可撤销。')}
                confirmText={t('platforms.wechatPersonal.dialog.confirmDelete', '删除')}
                cancelText={t('platforms.wechatPersonal.dialog.cancel', '取消')}
                confirmVariant="danger"
                isLoading={isDeleting}
                onCancel={() => setConfirmOpen(false)}
                onConfirm={async () => {
                    if (isDeleting) return;
                    setIsDeleting(true);
                    try {
                        const idx = platforms.findIndex(p => p.id === platform.id);
                        const nextId = idx !== -1
                            ? (idx < platforms.length - 1 ? platforms[idx + 1]?.id : (idx > 0 ? platforms[idx - 1]?.id : null))
                            : null;
                        await deletePlatform(platform.id);
                        showSuccess(showToast, t('platforms.wechatPersonal.messages.deleteSuccess', '删除成功'), t('platforms.wechatPersonal.messages.deleteSuccessMessage', '个人微信平台已删除'));
                        setConfirmOpen(false);
                        if (nextId) navigate(`/platforms/${nextId}`);
                        else navigate('/platforms');
                    } catch (e) {
                        showApiError(showToast, e);
                    } finally {
                        setIsDeleting(false);
                    }
                }}
            />
        </main>
    );
};

export default WeChatPersonalPlatformConfig;
