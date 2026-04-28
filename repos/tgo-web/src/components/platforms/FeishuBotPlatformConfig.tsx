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
  platform: Platform; // expected: platform.type === 'feishu_bot'
}

const FeishuBotPlatformConfig: React.FC<Props> = ({ platform }) => {
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
    appId: (platform.config as any)?.app_id ?? '',
    appSecret: (platform.config as any)?.app_secret ?? '',
    encryptKey: (platform.config as any)?.encrypt_key ?? '',
    verificationToken: (platform.config as any)?.verification_token ?? '',
    // Convert relative callback URL to absolute
    callbackUrl: toAbsoluteUrl((platform as any)?.callback_url ?? ''),
  }));

  useEffect(() => {
    setFormValues({
      appId: (platform.config as any)?.app_id ?? '',
      appSecret: (platform.config as any)?.app_secret ?? '',
      encryptKey: (platform.config as any)?.encrypt_key ?? '',
      verificationToken: (platform.config as any)?.verification_token ?? '',
      // Convert relative callback URL to absolute
      callbackUrl: toAbsoluteUrl((platform as any)?.callback_url ?? ''),
    });
  }, [platform]);

  const handleChange = (patch: Partial<typeof formValues>) => {
    setFormValues(v => ({ ...v, ...patch }));
    const { callbackUrl, ...rest } = { ...formValues, ...patch };
    // Write changes to store; callbackUrl is derived from backend (callback_url)
    const toSave: Partial<PlatformConfig> = {
      ...(rest.appId !== undefined ? { appId: rest.appId } : {}),
      ...(rest.appSecret !== undefined ? { appSecret: rest.appSecret } : {}),
      ...(rest.encryptKey !== undefined ? { encryptKey: rest.encryptKey } : {}),
      ...(rest.verificationToken !== undefined ? { verificationToken: rest.verificationToken } : {}),
    };
    updatePlatformConfig(platform.id, toSave);
  };

  const handleSave = async () => {
    try {
      const updates: Partial<Platform> = {};

      if (hasConfigChanges) {
        // Transform camelCase form values to snake_case API payload for Feishu Bot
        updates.config = {
          app_id: (formValues.appId || '').trim(),
          app_secret: (formValues.appSecret || '').trim(),
          encrypt_key: (formValues.encryptKey || '').trim(),
          verification_token: (formValues.verificationToken || '').trim(),
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
      showSuccess(showToast, t('platforms.feishuBot.messages.saveSuccess', '保存成功'), t('platforms.feishuBot.messages.saveSuccessMessage', '飞书机器人配置已更新'));
    } catch (e) {
      showApiError(showToast, e);
    }
  };

  const displayName = platform.display_name || platform.name;

  return (
    <main className="flex flex-col flex-1 min-h-0 bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-900 dark:to-gray-800">
      <header className="px-6 py-4 border-b border-gray-200/80 dark:border-gray-700/80 flex justify-between items-center bg-white/60 dark:bg-gray-800/60 backdrop-blur-lg sticky top-0 z-10">
        <div>
          <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-200">{t('platforms.feishuBot.header.title', { name: displayName, defaultValue: '{{name}} 配置' })}</h2>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{t('platforms.feishuBot.header.subtitle', '配置飞书机器人对接所需的凭据与回调。')}</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            disabled={isUpdating || isDeleting}
            onClick={() => setConfirmOpen(true)}
            className={`px-3 py-1.5 text-sm rounded-md ${isDeleting ? 'bg-red-400 text-white' : 'bg-red-600 dark:bg-red-500 text-white hover:bg-red-700 dark:hover:bg-red-600'}`}
          >
            {isDeleting ? t('platforms.feishuBot.buttons.deleting', '删除中…') : t('platforms.feishuBot.buttons.delete', '删除')}
          </button>
          <button
            disabled={isUpdating || isDeleting || isToggling}
            onClick={async () => {
              if (isToggling) return;
              setIsToggling(true);
              try {
                if (isEnabled) {
                  await disablePlatform(platform.id);
                  showSuccess(showToast, t('platforms.feishuBot.messages.disabled', '平台已禁用'));
                } else {
                  await enablePlatform(platform.id);
                  showSuccess(showToast, t('platforms.feishuBot.messages.enabled', '平台已启用'));
                }
              } catch (e) {
                showApiError(showToast, e);
              } finally {
                setIsToggling(false);
              }
            }}
            className={`px-3 py-1.5 text-sm rounded-md text-white ${isEnabled ? 'bg-gray-600 dark:bg-gray-500 hover:bg-gray-700 dark:hover:bg-gray-600' : 'bg-green-600 dark:bg-green-500 hover:bg-green-700 dark:hover:bg-green-600'} ${isToggling ? 'opacity-70 cursor-not-allowed' : ''}`}
          >
            {isToggling ? (isEnabled ? t('platforms.feishuBot.buttons.disabling', '禁用中…') : t('platforms.feishuBot.buttons.enabling', '启用中…')) : (isEnabled ? t('platforms.feishuBot.buttons.disable', '禁用') : t('platforms.feishuBot.buttons.enable', '启用'))}
          </button>

          <button
            disabled={!canSave || isUpdating}
            onClick={handleSave}
            className={`px-3 py-1.5 text-sm rounded-md ${canSave ? 'bg-blue-600 dark:bg-blue-500 text-white hover:bg-blue-700 dark:hover:bg-blue-600' : 'bg-gray-200 dark:bg-gray-700 text-gray-500 dark:text-gray-400 cursor-not-allowed'}`}
          >
            {isUpdating ? t('platforms.feishuBot.buttons.saving', '保存中…') : t('platforms.feishuBot.buttons.save', '保存')}
          </button>
        </div>
      </header>

      <div className="flex flex-1 min-h-0 flex-col lg:flex-row gap-4 p-6">
        {/* Left: form */}
        <section className="lg:w-2/5 w-full bg-white/80 dark:bg-gray-800/80 backdrop-blur-md p-5 rounded-lg shadow-sm border border-gray-200/60 dark:border-gray-700/60 space-y-4 overflow-y-auto min-h-0 auto-hide-scrollbar">
          {/* 平台名称 */}
          <div>
            <label className="block text-sm font-medium text-gray-600 dark:text-gray-300 mb-1">{t('platforms.feishuBot.form.name', '平台名称')}</label>
            <input
              type="text"
              value={platformName}
              onChange={(e) => setPlatformName(e.target.value)}
              placeholder={t('platforms.feishuBot.form.namePlaceholder', '请输入平台名称')}
              className="w-full text-sm p-1.5 border border-gray-300/80 dark:border-gray-600/80 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 dark:focus:ring-blue-400 focus:border-blue-500 dark:focus:border-blue-400 bg-white/90 dark:bg-gray-700/50 dark:text-gray-200"
            />
          </div>

          {/* 回调URL（只读，需填入飞书） */}
          <div>
            <label className="block text-sm font-medium text-gray-600 dark:text-gray-300 mb-1">{t('platforms.feishuBot.form.callbackUrl', '请求地址 URL')}</label>
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={formValues.callbackUrl}
                readOnly
                placeholder={t('platforms.feishuBot.form.callbackUrlPlaceholder', '平台创建后会生成请求地址')}
                className="flex-1 text-sm p-1.5 border border-gray-300/80 dark:border-gray-600/80 rounded-md bg-gray-100/70 dark:bg-gray-700/50 dark:text-gray-200 focus:outline-none font-mono"
              />
              <button
                type="button"
                disabled={!formValues.callbackUrl}
                onClick={async () => {
                  try {
                    if (!formValues.callbackUrl) return;
                    await navigator.clipboard.writeText(formValues.callbackUrl);
                    showSuccess(showToast, t('platforms.feishuBot.messages.urlCopied', '请求地址已复制'));
                  } catch (e) {
                    showApiError(showToast, e);
                  }
                }}
                className={`px-2 py-1 text-xs rounded-md ${formValues.callbackUrl ? 'bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-200' : 'bg-gray-100 dark:bg-gray-700 text-gray-400 dark:text-gray-500 cursor-not-allowed'}`}
              >
                {t('platforms.feishuBot.buttons.copy', '复制')}
              </button>
            </div>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">{t('platforms.feishuBot.form.callbackUrlHint', '将此 URL 填入飞书机器人的「请求地址」配置中。')}</p>
          </div>

          {/* App ID */}
          <div>
            <label className="block text-sm font-medium text-gray-600 dark:text-gray-300 mb-1">{t('platforms.feishuBot.form.appId', 'App ID')}</label>
            <input
              type="text"
              value={formValues.appId}
              onChange={(e) => handleChange({ appId: e.target.value })}
              placeholder={t('platforms.feishuBot.form.appIdPlaceholder', '飞书应用的 App ID')}
              className="w-full text-sm p-1.5 border border-gray-300/80 dark:border-gray-600/80 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 dark:focus:ring-blue-400 focus:border-blue-500 dark:focus:border-blue-400 bg-white/90 dark:bg-gray-700/50 dark:text-gray-200"
            />
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">{t('platforms.feishuBot.form.appIdHint', '可在飞书开放平台应用详情的「凭证与基础信息」中获取。')}</p>
          </div>

          {/* App Secret */}
          <div>
            <label className="block text-sm font-medium text-gray-600 dark:text-gray-300 mb-1">{t('platforms.feishuBot.form.appSecret', 'App Secret')}</label>
            <input
              type="password"
              value={formValues.appSecret}
              onChange={(e) => handleChange({ appSecret: e.target.value })}
              placeholder={t('platforms.feishuBot.form.appSecretPlaceholder', '飞书应用的 App Secret')}
              className="w-full text-sm p-1.5 border border-gray-300/80 dark:border-gray-600/80 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 dark:focus:ring-blue-400 focus:border-blue-500 dark:focus:border-blue-400 bg-white/90 dark:bg-gray-700/50 dark:text-gray-200"
            />
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">{t('platforms.feishuBot.form.appSecretHint', '可在飞书开放平台应用详情的「凭证与基础信息」中获取，请妥善保管。')}</p>
          </div>

          {/* Encrypt Key（加密密钥） */}
          <div>
            <label className="block text-sm font-medium text-gray-600 dark:text-gray-300 mb-1">{t('platforms.feishuBot.form.encryptKey', 'Encrypt Key（加密密钥）')}</label>
            <input
              type="text"
              value={formValues.encryptKey}
              onChange={(e) => handleChange({ encryptKey: e.target.value })}
              placeholder={t('platforms.feishuBot.form.encryptKeyPlaceholder', '飞书开放平台提供的加密密钥')}
              className="w-full text-sm p-1.5 border border-gray-300/80 dark:border-gray-600/80 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 dark:focus:ring-blue-400 focus:border-blue-500 dark:focus:border-blue-400 bg-white/90 dark:bg-gray-700/50 dark:text-gray-200"
            />
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">{t('platforms.feishuBot.form.encryptKeyHint', '用于解密飞书推送的事件消息，可在飞书开放平台获取。')}</p>
          </div>

          {/* Verification Token（验证令牌） */}
          <div>
            <label className="block text-sm font-medium text-gray-600 dark:text-gray-300 mb-1">{t('platforms.feishuBot.form.verificationToken', 'Verification Token（验证令牌）')}</label>
            <input
              type="text"
              value={formValues.verificationToken}
              onChange={(e) => handleChange({ verificationToken: e.target.value })}
              placeholder={t('platforms.feishuBot.form.verificationTokenPlaceholder', '飞书开放平台提供的验证令牌')}
              className="w-full text-sm p-1.5 border border-gray-300/80 dark:border-gray-600/80 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 dark:focus:ring-blue-400 focus:border-blue-500 dark:focus:border-blue-400 bg-white/90 dark:bg-gray-700/50 dark:text-gray-200"
            />
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">{t('platforms.feishuBot.form.verificationTokenHint', '用于验证事件订阅请求的来源，可在飞书开放平台获取。')}</p>
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
          <h3 className="text-lg font-semibold text-gray-800 dark:text-gray-100">{t('platforms.feishuBot.guide.title', '飞书机器人配置指南')}</h3>

          <div className="bg-blue-50 dark:bg-blue-900/30 border border-blue-200 dark:border-blue-700 text-blue-800 dark:text-blue-200 text-sm rounded-md p-3">
            <p className="font-medium">{t('platforms.feishuBot.guide.overview', '快速概览')}</p>
            <p className="mt-1">{t('platforms.feishuBot.guide.overviewText', '完成以下三步：①在飞书开放平台创建应用/机器人 → ②配置请求地址并获取 Encrypt Key 和 Verification Token → ③将信息回填到本平台并保存。')}</p>
          </div>

          <details className="rounded-md border border-gray-200 dark:border-gray-600 p-3 bg-white/70 dark:bg-gray-700/50" open>
            <summary className="cursor-pointer font-semibold text-gray-800 dark:text-gray-100">{t('platforms.feishuBot.guide.step1Title', '1️⃣ 创建飞书应用/机器人')}</summary>
            <div className="text-sm text-gray-700 dark:text-gray-300 mt-2 space-y-2">
              <ol className="list-decimal pl-5 space-y-1">
                <li dangerouslySetInnerHTML={{ __html: t('platforms.feishuBot.guide.step1Item1', '访问 <a class="text-blue-600 hover:underline" href="https://open.feishu.cn/app" target="_blank" rel="noreferrer">飞书开放平台</a>，登录并进入开发者后台。') }} />
                <li>{t('platforms.feishuBot.guide.step1Item2', '点击「创建企业自建应用」，填写应用名称和描述。')}</li>
                <li>{t('platforms.feishuBot.guide.step1Item3', '进入应用详情，在左侧菜单找到「机器人」，开启机器人能力。')}</li>
              </ol>
            </div>
          </details>

          <details className="rounded-md border border-gray-200 dark:border-gray-600 p-3 bg-white/70 dark:bg-gray-700/50">
            <summary className="cursor-pointer font-semibold text-gray-800 dark:text-gray-100">{t('platforms.feishuBot.guide.step2Title', '2️⃣ 配置事件订阅')}</summary>
            <div className="text-sm text-gray-700 dark:text-gray-300 mt-2 space-y-2">
              <ol className="list-decimal pl-5 space-y-1">
                <li>{t('platforms.feishuBot.guide.step2Item1', '在应用详情页，进入「事件订阅」配置。')}</li>
                <li>{t('platforms.feishuBot.guide.step2Item2', '复制左侧「请求地址 URL」，粘贴到飞书的「请求地址」输入框中。')}</li>
                <li>{t('platforms.feishuBot.guide.step2Item3', '在页面上找到「Encrypt Key」和「Verification Token」，复制并分别填入左侧对应的输入框。')}</li>
                <li>{t('platforms.feishuBot.guide.step2Item4', '添加需要订阅的事件，如「接收消息」(im.message.receive_v1)。')}</li>
              </ol>
              <div className="bg-yellow-50 dark:bg-yellow-900/30 border border-yellow-200 dark:border-yellow-700 rounded p-2 text-xs text-yellow-800 dark:text-yellow-200">
                <p className="font-semibold">{t('platforms.feishuBot.guide.step2SecurityTitle', '安全提示')}</p>
                <p>{t('platforms.feishuBot.guide.step2SecurityText', '请妥善保管 Encrypt Key 和 Verification Token，它们用于验证消息来源和解密消息内容。')}</p>
              </div>
            </div>
          </details>

          <details className="rounded-md border border-gray-200 dark:border-gray-600 p-3 bg-white/70 dark:bg-gray-700/50">
            <summary className="cursor-pointer font-semibold text-gray-800 dark:text-gray-100">{t('platforms.feishuBot.guide.step3Title', '3️⃣ 发布应用')}</summary>
            <div className="text-sm text-gray-700 dark:text-gray-300 mt-2 space-y-2">
              <ol className="list-decimal pl-5 space-y-1">
                <li>{t('platforms.feishuBot.guide.step3Item1', '在本平台点击「保存」按钮保存配置。')}</li>
                <li>{t('platforms.feishuBot.guide.step3Item2', '回到飞书开放平台，点击「版本管理与发布」→「创建版本」。')}</li>
                <li>{t('platforms.feishuBot.guide.step3Item3', '提交版本审核，等待管理员审批后即可使用。')}</li>
              </ol>
              <a className="text-blue-600 dark:text-blue-400 hover:underline" href="https://open.feishu.cn/document/home/develop-a-bot-in-5-minutes/create-an-app" target="_blank" rel="noreferrer">{t('platforms.feishuBot.guide.docsLink', '飞书机器人开发文档')}</a>
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
        title={t('platforms.feishuBot.dialog.deleteTitle', '确认删除')}
        message={t('platforms.feishuBot.dialog.deleteMessage', '确定要删除此飞书机器人平台吗？此操作不可撤销。')}
        confirmText={t('platforms.feishuBot.dialog.confirmDelete', '删除')}
        cancelText={t('platforms.feishuBot.dialog.cancel', '取消')}
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
            showSuccess(showToast, t('platforms.feishuBot.messages.deleteSuccess', '删除成功'), t('platforms.feishuBot.messages.deleteSuccessMessage', '飞书机器人平台已删除'));
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

export default FeishuBotPlatformConfig;

