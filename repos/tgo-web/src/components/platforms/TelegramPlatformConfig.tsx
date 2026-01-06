import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import ConfirmDialog from '@/components/ui/ConfirmDialog';
import PlatformAISettings from '@/components/platforms/PlatformAISettings';
import type { Platform, PlatformConfig, PlatformAIMode } from '@/types';
import { usePlatformStore } from '@/stores/platformStore';
import { useToast } from '@/hooks/useToast';
import { showApiError, showSuccess } from '@/utils/toastHelpers';
import { toAbsoluteUrl } from '@/utils/config';

interface Props {
    platform: Platform; // expected: platform.type === 'telegram'
}

const TelegramPlatformConfig: React.FC<Props> = ({ platform }) => {
    const { t } = useTranslation();
    const { showToast } = useToast();
    const updatePlatformConfig = usePlatformStore(s => s.updatePlatformConfig);
    const resetPlatformConfig = usePlatformStore(s => s.resetPlatformConfig);
    const updatePlatform = usePlatformStore(s => s.updatePlatform);
    const deletePlatform = usePlatformStore(s => s.deletePlatform);
    const enablePlatform = usePlatformStore(s => s.enablePlatform);
    const disablePlatform = usePlatformStore(s => s.disablePlatform);
    const platforms = usePlatformStore(s => s.platforms);
    const hasConfigChanges = usePlatformStore(s => s.hasConfigChanges(platform.id));
    const isUpdating = usePlatformStore(s => s.isUpdating);
    const navigate = useNavigate();
    const [confirmOpen, setConfirmOpen] = useState(false);
    const [isDeleting, setIsDeleting] = useState(false);
    const [isToggling, setIsToggling] = useState(false);
    const isEnabled = platform.status === 'connected';

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

    // Local form state sourced from platform.config
    const [formValues, setFormValues] = useState(() => ({
        botToken: (platform.config as any)?.bot_token ?? '',
        webhookSecret: (platform.config as any)?.webhook_secret ?? '',
        // Convert relative callback URL to absolute
        callbackUrl: toAbsoluteUrl((platform as any)?.callback_url ?? ''),
    }));

    useEffect(() => {
        setFormValues({
            botToken: (platform.config as any)?.bot_token ?? '',
            webhookSecret: (platform.config as any)?.webhook_secret ?? '',
            callbackUrl: toAbsoluteUrl((platform as any)?.callback_url ?? ''),
        });
    }, [platform]);

    const handleChange = (patch: Partial<typeof formValues>) => {
        setFormValues(v => ({ ...v, ...patch }));
        const { callbackUrl, ...rest } = { ...formValues, ...patch };
        // Write changes to store; callbackUrl is derived from backend (callback_url)
        const toSave: Partial<PlatformConfig> = {
            ...(rest.botToken !== undefined ? { botToken: rest.botToken } : {}),
            ...(rest.webhookSecret !== undefined ? { webhookSecret: rest.webhookSecret } : {}),
        };
        updatePlatformConfig(platform.id, toSave);
    };

    const handleSave = async () => {
        try {
            const updates: Partial<Platform> = {};

            if (hasConfigChanges) {
                // Transform camelCase form values to snake_case API payload for Telegram
                updates.config = {
                    bot_token: (formValues.botToken || '').trim(),
                    webhook_secret: (formValues.webhookSecret || '').trim(),
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
            showSuccess(showToast, t('platforms.telegram.messages.saveSuccess', '保存成功'), t('platforms.telegram.messages.saveSuccessMessage', 'Telegram 配置已更新'));
        } catch (e) {
            showApiError(showToast, e);
        }
    };

    const displayName = platform.display_name || platform.name;

    return (
        <main className="flex flex-col flex-1 min-h-0 bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-900 dark:to-gray-800">
            <header className="px-6 py-4 border-b border-gray-200/80 dark:border-gray-700/80 flex justify-between items-center bg-white/60 dark:bg-gray-800/60 backdrop-blur-lg sticky top-0 z-10">
                <div>
                    <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-200">{t('platforms.telegram.header.title', { name: displayName, defaultValue: '{{name}} 配置' })}</h2>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{t('platforms.telegram.header.subtitle', '配置 Telegram Bot 所需的凭据与回调。')}</p>
                </div>
                <div className="flex items-center gap-3">
                    <button
                        disabled={isUpdating || isDeleting}
                        onClick={() => setConfirmOpen(true)}
                        className={`px-3 py-1.5 text-sm rounded-md ${isDeleting ? 'bg-red-400 text-white' : 'bg-red-600 dark:bg-red-500 text-white hover:bg-red-700 dark:hover:bg-red-600'}`}
                    >
                        {isDeleting ? t('platforms.telegram.buttons.deleting', '删除中…') : t('platforms.telegram.buttons.delete', '删除')}
                    </button>
                    <button
                        disabled={isUpdating || isDeleting || isToggling}
                        onClick={async () => {
                            if (isToggling) return;
                            setIsToggling(true);
                            try {
                                if (isEnabled) {
                                    await disablePlatform(platform.id);
                                    showSuccess(showToast, t('platforms.telegram.messages.disabled', '平台已禁用'));
                                } else {
                                    await enablePlatform(platform.id);
                                    showSuccess(showToast, t('platforms.telegram.messages.enabled', '平台已启用'));
                                }
                            } catch (e) {
                                showApiError(showToast, e);
                            } finally {
                                setIsToggling(false);
                            }
                        }}
                        className={`px-3 py-1.5 text-sm rounded-md text-white ${isEnabled ? 'bg-gray-600 dark:bg-gray-500 hover:bg-gray-700 dark:hover:bg-gray-600' : 'bg-green-600 dark:bg-green-500 hover:bg-green-700 dark:hover:bg-green-600'} ${isToggling ? 'opacity-70 cursor-not-allowed' : ''}`}
                    >
                        {isToggling ? (isEnabled ? t('platforms.telegram.buttons.disabling', '禁用中…') : t('platforms.telegram.buttons.enabling', '启用中…')) : (isEnabled ? t('platforms.telegram.buttons.disable', '禁用') : t('platforms.telegram.buttons.enable', '启用'))}
                    </button>

                    <button
                        disabled={!canSave || isUpdating}
                        onClick={handleSave}
                        className={`px-3 py-1.5 text-sm rounded-md ${canSave ? 'bg-blue-600 dark:bg-blue-500 text-white hover:bg-blue-700 dark:hover:bg-blue-600' : 'bg-gray-200 dark:bg-gray-700 text-gray-500 dark:text-gray-400 cursor-not-allowed'}`}
                    >
                        {isUpdating ? t('platforms.telegram.buttons.saving', '保存中…') : t('platforms.telegram.buttons.save', '保存')}
                    </button>
                </div>
            </header>

            <div className="flex flex-1 min-h-0 flex-col lg:flex-row gap-4 p-6">
                {/* Left: form */}
                <section className="lg:w-2/5 w-full bg-white/80 dark:bg-gray-800/80 backdrop-blur-md p-5 rounded-lg shadow-sm border border-gray-200/60 dark:border-gray-700/60 space-y-4 overflow-y-auto min-h-0 auto-hide-scrollbar">
                    {/* 平台名称 */}
                    <div>
                        <label className="block text-sm font-medium text-gray-600 dark:text-gray-300 mb-1">{t('platforms.telegram.form.name', '平台名称')}</label>
                        <input
                            type="text"
                            value={platformName}
                            onChange={(e) => setPlatformName(e.target.value)}
                            placeholder={t('platforms.telegram.form.namePlaceholder', '请输入平台名称')}
                            className="w-full text-sm p-1.5 border border-gray-300/80 dark:border-gray-600/80 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 dark:focus:ring-blue-400 focus:border-blue-500 dark:focus:border-blue-400 bg-white/90 dark:bg-gray-700/50 dark:text-gray-200"
                        />
                    </div>

                    {/* 回调URL（只读，需设置到 Telegram） */}
                    <div>
                        <label className="block text-sm font-medium text-gray-600 dark:text-gray-300 mb-1">{t('platforms.telegram.form.callbackUrl', 'Webhook URL')}</label>
                        <div className="flex items-center gap-2">
                            <input
                                type="text"
                                value={formValues.callbackUrl}
                                readOnly
                                placeholder={t('platforms.telegram.form.callbackUrlPlaceholder', '平台创建后会生成 Webhook URL')}
                                className="flex-1 text-sm p-1.5 border border-gray-300/80 dark:border-gray-600/80 rounded-md bg-gray-100/70 dark:bg-gray-700/50 dark:text-gray-200 focus:outline-none font-mono"
                            />
                            <button
                                type="button"
                                disabled={!formValues.callbackUrl}
                                onClick={async () => {
                                    try {
                                        if (!formValues.callbackUrl) return;
                                        await navigator.clipboard.writeText(formValues.callbackUrl);
                                        showSuccess(showToast, t('platforms.telegram.messages.urlCopied', 'Webhook URL 已复制'));
                                    } catch (e) {
                                        showApiError(showToast, e);
                                    }
                                }}
                                className={`px-2 py-1 text-xs rounded-md ${formValues.callbackUrl ? 'bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-200' : 'bg-gray-100 dark:bg-gray-700 text-gray-400 dark:text-gray-500 cursor-not-allowed'}`}
                            >
                                {t('platforms.telegram.buttons.copy', '复制')}
                            </button>
                        </div>
                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">{t('platforms.telegram.form.callbackUrlHint', '使用 setWebhook API 将此 URL 设置为 Bot 的 Webhook 地址。')}</p>
                    </div>

                    {/* Bot Token */}
                    <div>
                        <label className="block text-sm font-medium text-gray-600 dark:text-gray-300 mb-1">{t('platforms.telegram.form.botToken', 'Bot Token')}</label>
                        <input
                            type="password"
                            value={formValues.botToken}
                            onChange={(e) => handleChange({ botToken: e.target.value })}
                            placeholder={t('platforms.telegram.form.botTokenPlaceholder', '例如: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz')}
                            className="w-full text-sm p-1.5 border border-gray-300/80 dark:border-gray-600/80 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 dark:focus:ring-blue-400 focus:border-blue-500 dark:focus:border-blue-400 bg-white/90 dark:bg-gray-700/50 dark:text-gray-200"
                        />
                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">{t('platforms.telegram.form.botTokenHint', '通过 @BotFather 创建 Bot 后获取的 Token，请妥善保管。')}</p>
                    </div>

                    {/* Webhook Secret (可选) */}
                    <div>
                        <label className="block text-sm font-medium text-gray-600 dark:text-gray-300 mb-1">{t('platforms.telegram.form.webhookSecret', 'Webhook Secret（可选）')}</label>
                        <input
                            type="text"
                            value={formValues.webhookSecret}
                            onChange={(e) => handleChange({ webhookSecret: e.target.value })}
                            placeholder={t('platforms.telegram.form.webhookSecretPlaceholder', '用于验证 webhook 请求来源')}
                            className="w-full text-sm p-1.5 border border-gray-300/80 dark:border-gray-600/80 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 dark:focus:ring-blue-400 focus:border-blue-500 dark:focus:border-blue-400 bg-white/90 dark:bg-gray-700/50 dark:text-gray-200"
                        />
                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">{t('platforms.telegram.form.webhookSecretHint', '在 setWebhook 时通过 secret_token 参数设置相同的值，用于验证请求来源。')}</p>
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

                {/* Right: comprehensive guide */}
                <section className="lg:w-3/5 w-full bg-white/80 dark:bg-gray-800/80 backdrop-blur-md p-5 rounded-lg shadow-sm border border-gray-200/60 dark:border-gray-700/60 min-h-0 overflow-y-auto auto-hide-scrollbar space-y-4">
                    <h3 className="text-lg font-semibold text-gray-800 dark:text-gray-100">{t('platforms.telegram.guide.title', 'Telegram Bot 配置指南')}</h3>

                    <div className="bg-green-50 dark:bg-green-900/30 border border-green-200 dark:border-green-700 text-green-800 dark:text-green-200 text-sm rounded-md p-3">
                        <p className="font-medium">{t('platforms.telegram.guide.overview', '✨ 极简配置')}</p>
                        <p className="mt-1">{t('platforms.telegram.guide.overviewText', '只需：①创建 Bot 获取 Token → ②填入 Token → ③点击「启用」。系统会自动配置 Webhook！')}</p>
                    </div>

                    <details className="rounded-md border border-gray-200 dark:border-gray-600 p-3 bg-white/70 dark:bg-gray-700/50" open>
                        <summary className="cursor-pointer font-semibold text-gray-800 dark:text-gray-100">{t('platforms.telegram.guide.step1Title', '1️⃣ 创建 Telegram Bot')}</summary>
                        <div className="text-sm text-gray-700 dark:text-gray-300 mt-2 space-y-2">
                            <ol className="list-decimal pl-5 space-y-1">
                                <li dangerouslySetInnerHTML={{ __html: t('platforms.telegram.guide.step1Item1', '在 Telegram 中搜索 <a class="text-blue-600 hover:underline" href="https://t.me/BotFather" target="_blank" rel="noreferrer">@BotFather</a> 并打开对话。') }} />
                                <li>{t('platforms.telegram.guide.step1Item2', '发送 /newbot 命令开始创建机器人。')}</li>
                                <li>{t('platforms.telegram.guide.step1Item3', '按提示输入机器人名称（显示名）和用户名（以 _bot 结尾）。')}</li>
                                <li>{t('platforms.telegram.guide.step1Item4', 'BotFather 将返回 Bot Token，复制备用。')}</li>
                            </ol>
                        </div>
                    </details>

                    <details className="rounded-md border border-gray-200 dark:border-gray-600 p-3 bg-white/70 dark:bg-gray-700/50" open>
                        <summary className="cursor-pointer font-semibold text-gray-800 dark:text-gray-100">{t('platforms.telegram.guide.step2Title', '2️⃣ 配置并启用')}</summary>
                        <div className="text-sm text-gray-700 dark:text-gray-300 mt-2 space-y-2">
                            <ol className="list-decimal pl-5 space-y-1">
                                <li>{t('platforms.telegram.guide.step2Item1', '在左侧「Bot Token」输入框中粘贴 Token。')}</li>
                                <li>{t('platforms.telegram.guide.step2Item2', '（可选）填写「Webhook Secret」增强安全性。')}</li>
                                <li>{t('platforms.telegram.guide.step2Item3', '点击「保存」后，再点击右上角的「启用」按钮。')}</li>
                            </ol>
                            <div className="bg-blue-50 dark:bg-blue-900/30 border border-blue-200 dark:border-blue-700 rounded p-2 text-xs text-blue-800 dark:text-blue-200 mt-2">
                                <p className="font-semibold">💡 自动配置</p>
                                <p>{t('platforms.telegram.guide.step2AutoConfig', '点击「启用」后，系统会自动向 Telegram 注册 Webhook 地址，无需手动操作。')}</p>
                            </div>
                        </div>
                    </details>

                    <details className="rounded-md border border-gray-200 dark:border-gray-600 p-3 bg-white/70 dark:bg-gray-700/50">
                        <summary className="cursor-pointer font-semibold text-gray-800 dark:text-gray-100">{t('platforms.telegram.guide.step3Title', '3️⃣ 测试机器人')}</summary>
                        <div className="text-sm text-gray-700 dark:text-gray-300 mt-2 space-y-2">
                            <ol className="list-decimal pl-5 space-y-1">
                                <li>{t('platforms.telegram.guide.step3Item1', '在 Telegram 中搜索你的 Bot 用户名并开始对话。')}</li>
                                <li>{t('platforms.telegram.guide.step3Item2', '发送任意消息，AI 将自动回复。')}</li>
                                <li>{t('platforms.telegram.guide.step3Item3', '如需将 Bot 添加到群组，确保在 BotFather 中开启「Allow Groups」选项。')}</li>
                            </ol>
                            <a className="text-blue-600 dark:text-blue-400 hover:underline" href="https://core.telegram.org/bots/api" target="_blank" rel="noreferrer">{t('platforms.telegram.guide.docsLink', 'Telegram Bot API 文档')}</a>
                        </div>
                    </details>

                </section>
            </div>

            {/* Scoped scrollbar style */}
            <style>{`
        .auto-hide-scrollbar { scrollbar-width: thin; scrollbar-color: rgba(0,0,0,0.3) transparent; }
        .auto-hide-scrollbar::-webkit-scrollbar { width: 8px; height: 8px; }
        .auto-hide-scrollbar::-webkit-scrollbar-thumb { background-color: transparent; border-radius: 4px; }
        .auto-hide-scrollbar:hover::-webkit-scrollbar-thumb { background-color: rgba(0,0,0,0.35); }
      `}</style>
            <ConfirmDialog
                isOpen={confirmOpen}
                title={t('platforms.telegram.dialog.deleteTitle', '确认删除')}
                message={t('platforms.telegram.dialog.deleteMessage', '确定要删除此 Telegram Bot 平台吗？此操作不可撤销。')}
                confirmText={t('platforms.telegram.dialog.confirmDelete', '删除')}
                cancelText={t('platforms.telegram.dialog.cancel', '取消')}
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
                        showSuccess(showToast, t('platforms.telegram.messages.deleteSuccess', '删除成功'), t('platforms.telegram.messages.deleteSuccessMessage', 'Telegram Bot 平台已删除'));
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

export default TelegramPlatformConfig;
