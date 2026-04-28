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
  platform: Platform; // expected: platform.type === 'dingtalk_bot'
}

const DingTalkBotPlatformConfig: React.FC<Props> = ({ platform }) => {
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
  const [aiAgentIds, setAiAgentIds] = useState<string[]>(platform.agent_id ? [platform.agent_id] : []);
  const [aiMode, setAiMode] = useState<PlatformAIMode>(platform.ai_mode ?? 'auto');
  const [fallbackTimeout, setFallbackTimeout] = useState<number | null>(platform.fallback_to_ai_timeout ?? null);

  useEffect(() => {
    setAiAgentIds(platform.agent_id ? [platform.agent_id] : []);
    setAiMode(platform.ai_mode ?? 'auto');
    setFallbackTimeout(platform.fallback_to_ai_timeout ?? null);
  }, [platform.agent_id, platform.ai_mode, platform.fallback_to_ai_timeout]);

  const hasAISettingsChanged = useMemo(() => {
    const origAgentIds = platform.agent_id ? [platform.agent_id] : [];
    const origMode = platform.ai_mode ?? 'auto';
    const origTimeout = platform.fallback_to_ai_timeout ?? null;
    const agentIdsChanged = JSON.stringify(aiAgentIds.sort()) !== JSON.stringify([...origAgentIds].sort());
    const modeChanged = aiMode !== origMode;
    const timeoutChanged = fallbackTimeout !== origTimeout;
    return agentIdsChanged || modeChanged || timeoutChanged;
  }, [aiAgentIds, aiMode, fallbackTimeout, platform.agent_id, platform.ai_mode, platform.fallback_to_ai_timeout]);

  const canSave = hasConfigChanges || hasNameChanged || hasAISettingsChanged;

  // Local form state sourced from platform.config
  const [formValues, setFormValues] = useState(() => ({
    appKey: (platform.config as any)?.app_key ?? '',
    appSecret: (platform.config as any)?.app_secret ?? '',
    robotCode: (platform.config as any)?.robot_code ?? '',
    aesKey: (platform.config as any)?.aes_key ?? '',
    token: (platform.config as any)?.token ?? '',
    // Convert relative callback URL to absolute
    callbackUrl: toAbsoluteUrl((platform as any)?.callback_url ?? ''),
  }));

  useEffect(() => {
    setFormValues({
      appKey: (platform.config as any)?.app_key ?? '',
      appSecret: (platform.config as any)?.app_secret ?? '',
      robotCode: (platform.config as any)?.robot_code ?? '',
      aesKey: (platform.config as any)?.aes_key ?? '',
      token: (platform.config as any)?.token ?? '',
      // Convert relative callback URL to absolute
      callbackUrl: toAbsoluteUrl((platform as any)?.callback_url ?? ''),
    });
  }, [platform]);

  const handleChange = (patch: Partial<typeof formValues>) => {
    setFormValues(v => ({ ...v, ...patch }));
    const { callbackUrl, ...rest } = { ...formValues, ...patch };
    // Write changes to store; callbackUrl is derived from backend (callback_url)
    const toSave: Partial<PlatformConfig> = {
      ...(rest.appKey !== undefined ? { appKey: rest.appKey } : {}),
      ...(rest.appSecret !== undefined ? { appSecret: rest.appSecret } : {}),
      ...(rest.robotCode !== undefined ? { robotCode: rest.robotCode } : {}),
      ...(rest.aesKey !== undefined ? { aesKey: rest.aesKey } : {}),
      ...(rest.token !== undefined ? { token: rest.token } : {}),
    };
    updatePlatformConfig(platform.id, toSave);
  };

  const handleSave = async () => {
    try {
      const updates: Partial<Platform> = {};

      if (hasConfigChanges) {
        // Transform camelCase form values to snake_case API payload for DingTalk Bot
        updates.config = {
          app_key: (formValues.appKey || '').trim(),
          app_secret: (formValues.appSecret || '').trim(),
          robot_code: (formValues.robotCode || '').trim(),
          aes_key: (formValues.aesKey || '').trim(),
          token: (formValues.token || '').trim(),
        } as any;
      }
      if (hasNameChanged) {
        updates.name = platformName.trim();
      }
      if (hasAISettingsChanged) {
        updates.agent_id = aiAgentIds[0] ?? null;
        updates.ai_mode = aiMode;
        updates.fallback_to_ai_timeout = aiMode === 'assist' ? fallbackTimeout : null;
      }

      if (Object.keys(updates).length > 0) {
        await updatePlatform(platform.id, updates);
        if (hasConfigChanges) {
          resetPlatformConfig(platform.id);
        }
      }
      showSuccess(showToast, t('platforms.dingtalkBot.messages.saveSuccess', '保存成功'), t('platforms.dingtalkBot.messages.saveSuccessMessage', '钉钉机器人配置已更新'));
    } catch (e) {
      showApiError(showToast, e);
    }
  };

  const displayName = platform.display_name || platform.name;

  return (
    <main className="flex flex-col flex-1 min-h-0 bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-900 dark:to-gray-800">
      <header className="px-6 py-4 border-b border-gray-200/80 dark:border-gray-700/80 flex justify-between items-center bg-white/60 dark:bg-gray-800/60 backdrop-blur-lg sticky top-0 z-10">
        <div>
          <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-200">{t('platforms.dingtalkBot.header.title', { name: displayName, defaultValue: '{{name}} 配置' })}</h2>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{t('platforms.dingtalkBot.header.subtitle', '配置钉钉机器人对接所需的凭据与回调。')}</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            disabled={isUpdating || isDeleting}
            onClick={() => setConfirmOpen(true)}
            className={`px-3 py-1.5 text-sm rounded-md ${isDeleting ? 'bg-red-400 text-white' : 'bg-red-600 dark:bg-red-500 text-white hover:bg-red-700 dark:hover:bg-red-600'}`}
          >
            {isDeleting ? t('platforms.dingtalkBot.buttons.deleting', '删除中…') : t('platforms.dingtalkBot.buttons.delete', '删除')}
          </button>
          <button
            disabled={isUpdating || isDeleting || isToggling}
            onClick={async () => {
              if (isToggling) return;
              setIsToggling(true);
              try {
                if (isEnabled) {
                  await disablePlatform(platform.id);
                  showSuccess(showToast, t('platforms.dingtalkBot.messages.disabled', '平台已禁用'));
                } else {
                  await enablePlatform(platform.id);
                  showSuccess(showToast, t('platforms.dingtalkBot.messages.enabled', '平台已启用'));
                }
              } catch (e) {
                showApiError(showToast, e);
              } finally {
                setIsToggling(false);
              }
            }}
            className={`px-3 py-1.5 text-sm rounded-md text-white ${isEnabled ? 'bg-gray-600 dark:bg-gray-500 hover:bg-gray-700 dark:hover:bg-gray-600' : 'bg-green-600 dark:bg-green-500 hover:bg-green-700 dark:hover:bg-green-600'} ${isToggling ? 'opacity-70 cursor-not-allowed' : ''}`}
          >
            {isToggling ? (isEnabled ? t('platforms.dingtalkBot.buttons.disabling', '禁用中…') : t('platforms.dingtalkBot.buttons.enabling', '启用中…')) : (isEnabled ? t('platforms.dingtalkBot.buttons.disable', '禁用') : t('platforms.dingtalkBot.buttons.enable', '启用'))}
          </button>

          <button
            disabled={!canSave || isUpdating}
            onClick={handleSave}
            className={`px-3 py-1.5 text-sm rounded-md ${canSave ? 'bg-blue-600 dark:bg-blue-500 text-white hover:bg-blue-700 dark:hover:bg-blue-600' : 'bg-gray-200 dark:bg-gray-700 text-gray-500 dark:text-gray-400 cursor-not-allowed'}`}
          >
            {isUpdating ? t('platforms.dingtalkBot.buttons.saving', '保存中…') : t('platforms.dingtalkBot.buttons.save', '保存')}
          </button>
        </div>
      </header>

      <div className="flex flex-1 min-h-0 flex-col lg:flex-row gap-4 p-6">
        {/* Left: form */}
        <section className="lg:w-2/5 w-full bg-white/80 dark:bg-gray-800/80 backdrop-blur-md p-5 rounded-lg shadow-sm border border-gray-200/60 dark:border-gray-700/60 space-y-4 overflow-y-auto min-h-0 auto-hide-scrollbar">
          {/* 平台名称 */}
          <div>
            <label className="block text-sm font-medium text-gray-600 dark:text-gray-300 mb-1">{t('platforms.dingtalkBot.form.name', '平台名称')}</label>
            <input
              type="text"
              value={platformName}
              onChange={(e) => setPlatformName(e.target.value)}
              placeholder={t('platforms.dingtalkBot.form.namePlaceholder', '请输入平台名称')}
              className="w-full text-sm p-1.5 border border-gray-300/80 dark:border-gray-600/80 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 dark:focus:ring-blue-400 focus:border-blue-500 dark:focus:border-blue-400 bg-white/90 dark:bg-gray-700/50 dark:text-gray-200"
            />
          </div>

          {/* 回调URL（只读，需填入钉钉） */}
          <div>
            <label className="block text-sm font-medium text-gray-600 dark:text-gray-300 mb-1">{t('platforms.dingtalkBot.form.callbackUrl', '消息接收地址')}</label>
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={formValues.callbackUrl}
                readOnly
                placeholder={t('platforms.dingtalkBot.form.callbackUrlPlaceholder', '平台创建后会生成消息接收地址')}
                className="flex-1 text-sm p-1.5 border border-gray-300/80 dark:border-gray-600/80 rounded-md bg-gray-100/70 dark:bg-gray-700/50 dark:text-gray-200 focus:outline-none font-mono"
              />
              <button
                type="button"
                disabled={!formValues.callbackUrl}
                onClick={async () => {
                  try {
                    if (!formValues.callbackUrl) return;
                    await navigator.clipboard.writeText(formValues.callbackUrl);
                    showSuccess(showToast, t('platforms.dingtalkBot.messages.urlCopied', '消息接收地址已复制'));
                  } catch (e) {
                    showApiError(showToast, e);
                  }
                }}
                className={`px-2 py-1 text-xs rounded-md ${formValues.callbackUrl ? 'bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-200' : 'bg-gray-100 dark:bg-gray-700 text-gray-400 dark:text-gray-500 cursor-not-allowed'}`}
              >
                {t('platforms.dingtalkBot.buttons.copy', '复制')}
              </button>
            </div>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">{t('platforms.dingtalkBot.form.callbackUrlHint', '将此 URL 填入钉钉机器人的「消息接收地址」配置中。')}</p>
          </div>

          {/* App Key */}
          <div>
            <label className="block text-sm font-medium text-gray-600 dark:text-gray-300 mb-1">{t('platforms.dingtalkBot.form.appKey', 'App Key')}</label>
            <input
              type="text"
              value={formValues.appKey}
              onChange={(e) => handleChange({ appKey: e.target.value })}
              placeholder={t('platforms.dingtalkBot.form.appKeyPlaceholder', '钉钉应用的 AppKey')}
              className="w-full text-sm p-1.5 border border-gray-300/80 dark:border-gray-600/80 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 dark:focus:ring-blue-400 focus:border-blue-500 dark:focus:border-blue-400 bg-white/90 dark:bg-gray-700/50 dark:text-gray-200"
            />
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">{t('platforms.dingtalkBot.form.appKeyHint', '可在钉钉开放平台应用详情的「凭证与基础信息」中获取。')}</p>
          </div>

          {/* App Secret */}
          <div>
            <label className="block text-sm font-medium text-gray-600 dark:text-gray-300 mb-1">{t('platforms.dingtalkBot.form.appSecret', 'App Secret')}</label>
            <input
              type="password"
              value={formValues.appSecret}
              onChange={(e) => handleChange({ appSecret: e.target.value })}
              placeholder={t('platforms.dingtalkBot.form.appSecretPlaceholder', '钉钉应用的 AppSecret')}
              className="w-full text-sm p-1.5 border border-gray-300/80 dark:border-gray-600/80 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 dark:focus:ring-blue-400 focus:border-blue-500 dark:focus:border-blue-400 bg-white/90 dark:bg-gray-700/50 dark:text-gray-200"
            />
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">{t('platforms.dingtalkBot.form.appSecretHint', '可在钉钉开放平台应用详情的「凭证与基础信息」中获取，请妥善保管。')}</p>
          </div>

          {/* Robot Code */}
          <div>
            <label className="block text-sm font-medium text-gray-600 dark:text-gray-300 mb-1">{t('platforms.dingtalkBot.form.robotCode', 'Robot Code（机器人编码）')}</label>
            <input
              type="text"
              value={formValues.robotCode}
              onChange={(e) => handleChange({ robotCode: e.target.value })}
              placeholder={t('platforms.dingtalkBot.form.robotCodePlaceholder', '钉钉机器人的唯一编码')}
              className="w-full text-sm p-1.5 border border-gray-300/80 dark:border-gray-600/80 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 dark:focus:ring-blue-400 focus:border-blue-500 dark:focus:border-blue-400 bg-white/90 dark:bg-gray-700/50 dark:text-gray-200"
            />
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">{t('platforms.dingtalkBot.form.robotCodeHint', '可在钉钉开放平台机器人配置页面获取。')}</p>
          </div>

          {/* AES Key（加密密钥） */}
          <div>
            <label className="block text-sm font-medium text-gray-600 dark:text-gray-300 mb-1">{t('platforms.dingtalkBot.form.aesKey', 'AES Key（加密密钥）')}</label>
            <input
              type="text"
              value={formValues.aesKey}
              onChange={(e) => handleChange({ aesKey: e.target.value })}
              placeholder={t('platforms.dingtalkBot.form.aesKeyPlaceholder', '用于消息加解密的密钥')}
              className="w-full text-sm p-1.5 border border-gray-300/80 dark:border-gray-600/80 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 dark:focus:ring-blue-400 focus:border-blue-500 dark:focus:border-blue-400 bg-white/90 dark:bg-gray-700/50 dark:text-gray-200"
            />
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">{t('platforms.dingtalkBot.form.aesKeyHint', '用于解密钉钉推送的事件消息，可在钉钉开放平台获取。')}</p>
          </div>

          {/* Token（签名校验令牌） */}
          <div>
            <label className="block text-sm font-medium text-gray-600 dark:text-gray-300 mb-1">{t('platforms.dingtalkBot.form.token', 'Token（签名校验令牌）')}</label>
            <input
              type="text"
              value={formValues.token}
              onChange={(e) => handleChange({ token: e.target.value })}
              placeholder={t('platforms.dingtalkBot.form.tokenPlaceholder', '用于消息签名校验的令牌')}
              className="w-full text-sm p-1.5 border border-gray-300/80 dark:border-gray-600/80 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 dark:focus:ring-blue-400 focus:border-blue-500 dark:focus:border-blue-400 bg-white/90 dark:bg-gray-700/50 dark:text-gray-200"
            />
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">{t('platforms.dingtalkBot.form.tokenHint', '用于验证事件订阅请求的来源，可在钉钉开放平台获取。')}</p>
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
          <h3 className="text-lg font-semibold text-gray-800 dark:text-gray-100">{t('platforms.dingtalkBot.guide.title', '钉钉机器人配置指南')}</h3>

          <div className="bg-blue-50 dark:bg-blue-900/30 border border-blue-200 dark:border-blue-700 text-blue-800 dark:text-blue-200 text-sm rounded-md p-3">
            <p className="font-medium">{t('platforms.dingtalkBot.guide.overview', '快速概览')}</p>
            <p className="mt-1">{t('platforms.dingtalkBot.guide.overviewText', '完成以下三步：①在钉钉开放平台创建应用/机器人 → ②配置消息接收地址并获取凭证信息 → ③将信息回填到本平台并保存。')}</p>
          </div>

          <details className="rounded-md border border-gray-200 dark:border-gray-600 p-3 bg-white/70 dark:bg-gray-700/50" open>
            <summary className="cursor-pointer font-semibold text-gray-800 dark:text-gray-100">{t('platforms.dingtalkBot.guide.step1Title', '1️⃣ 创建钉钉应用/机器人')}</summary>
            <div className="text-sm text-gray-700 dark:text-gray-300 mt-2 space-y-2">
              <ol className="list-decimal pl-5 space-y-1">
                <li dangerouslySetInnerHTML={{ __html: t('platforms.dingtalkBot.guide.step1Item1', '访问 <a class="text-blue-600 hover:underline" href="https://open.dingtalk.com/developer" target="_blank" rel="noreferrer">钉钉开放平台</a>，登录并进入开发者后台。') }} />
                <li>{t('platforms.dingtalkBot.guide.step1Item2', '点击「应用开发」→「企业内部开发」→「创建应用」。')}</li>
                <li>{t('platforms.dingtalkBot.guide.step1Item3', '填写应用名称、描述等信息，点击确认创建。')}</li>
                <li>{t('platforms.dingtalkBot.guide.step1Item4', '在应用详情页，找到「机器人」功能，点击「创建机器人」。')}</li>
              </ol>
            </div>
          </details>

          <details className="rounded-md border border-gray-200 dark:border-gray-600 p-3 bg-white/70 dark:bg-gray-700/50">
            <summary className="cursor-pointer font-semibold text-gray-800 dark:text-gray-100">{t('platforms.dingtalkBot.guide.step2Title', '2️⃣ 配置消息接收与安全设置')}</summary>
            <div className="text-sm text-gray-700 dark:text-gray-300 mt-2 space-y-2">
              <ol className="list-decimal pl-5 space-y-1">
                <li>{t('platforms.dingtalkBot.guide.step2Item1', '在机器人配置页面，找到「消息接收模式」，选择「HTTP模式」。')}</li>
                <li>{t('platforms.dingtalkBot.guide.step2Item2', '复制左侧「消息接收地址」，粘贴到钉钉的「消息接收地址」输入框中。')}</li>
                <li>{t('platforms.dingtalkBot.guide.step2Item3', '在「凭证与基础信息」页面，复制「AppKey」和「AppSecret」，填入左侧对应输入框。')}</li>
                <li>{t('platforms.dingtalkBot.guide.step2Item4', '在机器人配置页面，复制「RobotCode」，填入左侧「Robot Code」输入框。')}</li>
                <li>{t('platforms.dingtalkBot.guide.step2Item5', '在「开发配置」→「事件订阅」中，复制「AES Key」和「Token」，填入左侧对应输入框。')}</li>
              </ol>
              <div className="bg-yellow-50 dark:bg-yellow-900/30 border border-yellow-200 dark:border-yellow-700 rounded p-2 text-xs text-yellow-800 dark:text-yellow-200">
                <p className="font-semibold">{t('platforms.dingtalkBot.guide.step2SecurityTitle', '安全提示')}</p>
                <p>{t('platforms.dingtalkBot.guide.step2SecurityText', '请妥善保管 AppSecret、AES Key 和 Token，它们用于验证消息来源和加解密消息内容。')}</p>
              </div>
            </div>
          </details>

          <details className="rounded-md border border-gray-200 dark:border-gray-600 p-3 bg-white/70 dark:bg-gray-700/50">
            <summary className="cursor-pointer font-semibold text-gray-800 dark:text-gray-100">{t('platforms.dingtalkBot.guide.step3Title', '3️⃣ 发布应用')}</summary>
            <div className="text-sm text-gray-700 dark:text-gray-300 mt-2 space-y-2">
              <ol className="list-decimal pl-5 space-y-1">
                <li>{t('platforms.dingtalkBot.guide.step3Item1', '在本平台点击「保存」按钮保存配置。')}</li>
                <li>{t('platforms.dingtalkBot.guide.step3Item2', '回到钉钉开放平台，点击「版本管理与发布」→「创建版本」。')}</li>
                <li>{t('platforms.dingtalkBot.guide.step3Item3', '提交版本审核，等待管理员审批后即可使用。')}</li>
              </ol>
              <a className="text-blue-600 dark:text-blue-400 hover:underline" href="https://open.dingtalk.com/document/orgapp/robot-overview" target="_blank" rel="noreferrer">{t('platforms.dingtalkBot.guide.docsLink', '钉钉机器人开发文档')}</a>
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
        title={t('platforms.dingtalkBot.dialog.deleteTitle', '确认删除')}
        message={t('platforms.dingtalkBot.dialog.deleteMessage', '确定要删除此钉钉机器人平台吗？此操作不可撤销。')}
        confirmText={t('platforms.dingtalkBot.dialog.confirmDelete', '删除')}
        cancelText={t('platforms.dingtalkBot.dialog.cancel', '取消')}
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
            showSuccess(showToast, t('platforms.dingtalkBot.messages.deleteSuccess', '删除成功'), t('platforms.dingtalkBot.messages.deleteSuccessMessage', '钉钉机器人平台已删除'));
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

export default DingTalkBotPlatformConfig;

