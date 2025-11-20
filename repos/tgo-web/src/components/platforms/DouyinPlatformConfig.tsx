import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import ConfirmDialog from '@/components/ui/ConfirmDialog';
import type { Platform, PlatformConfig } from '@/types';
import { usePlatformStore } from '@/stores/platformStore';
import { useToast } from '@/hooks/useToast';
import { showApiError, showSuccess } from '@/utils/toastHelpers';

interface Props {
  platform: Platform; // expected: platform.type === 'douyin' or 'tiktok'
}

type DouyinConfig = {
  appId: string;
  appSecret: string;
  clientKey: string;
  clientSecret: string;
  callbackUrl: string; // read-only (from backend)
  authScope: string; // comma-separated scopes, e.g., "user_info,video.list"
};

const defaultDouyinConfig: DouyinConfig = {
  appId: '',
  appSecret: '',
  clientKey: '',
  clientSecret: '',
  callbackUrl: '',
  authScope: '',
};

const DouyinPlatformConfig: React.FC<Props> = ({ platform }) => {
  const { t } = useTranslation();
  const { showToast } = useToast();
  const updatePlatformConfig = usePlatformStore(s => s.updatePlatformConfig);
  const savePlatformConfig = usePlatformStore(s => s.savePlatformConfig);
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
  const canSave = hasConfigChanges || hasNameChanged;

  // Local form state sourced from platform.config
  const initialFormValues: DouyinConfig = useMemo(() => {
    const cfg = (platform.config || {}) as PlatformConfig as any;
    // callbackUrl: prefer explicit callbackUrl if provided; else fall back to webhookUrl as in WeCom
    const cb = (cfg.callbackUrl ?? cfg.webhookUrl ?? defaultDouyinConfig.callbackUrl) as string;
    // authScope: accept string or array from backend
    let scope: string = defaultDouyinConfig.authScope;
    const rawScope = cfg.authScope;
    if (Array.isArray(rawScope)) scope = rawScope.join(',');
    else if (typeof rawScope === 'string') scope = rawScope;

    return {
      appId: cfg.appId ?? defaultDouyinConfig.appId,
      appSecret: cfg.appSecret ?? defaultDouyinConfig.appSecret,
      clientKey: cfg.clientKey ?? defaultDouyinConfig.clientKey,
      clientSecret: cfg.clientSecret ?? defaultDouyinConfig.clientSecret,
      callbackUrl: cb,
      authScope: scope,
    } as DouyinConfig;
  }, [platform.config]);

  const [formValues, setFormValues] = useState<DouyinConfig>(initialFormValues);
  useEffect(() => { setFormValues(initialFormValues); }, [initialFormValues]);

  const handleChange = (patch: Partial<DouyinConfig>) => {
    setFormValues(v => ({ ...v, ...patch }));
    const { callbackUrl, ...rest } = { ...formValues, ...patch };
    const toSave: Partial<PlatformConfig> = {
      ...(rest.appId !== undefined ? { appId: rest.appId } : {}),
      ...(rest.appSecret !== undefined ? { appSecret: rest.appSecret } : {}),
      ...(rest.clientKey !== undefined ? { clientKey: rest.clientKey } : {}),
      ...(rest.clientSecret !== undefined ? { clientSecret: rest.clientSecret } : {}),
      ...(rest.authScope !== undefined ? { authScope: rest.authScope } : {}),
    };
    updatePlatformConfig(platform.id, toSave);
  };

  const [showAppSecret, setShowAppSecret] = useState(false);
  const [showClientSecret, setShowClientSecret] = useState(false);

  const handleSave = async () => {
    try {
      if (hasConfigChanges) {
        await savePlatformConfig(platform.id);
      }
      if (hasNameChanged) {
        await updatePlatform(platform.id, { name: platformName.trim() });
      }
      showSuccess(showToast, t('platforms.douyin.messages.saveSuccess', '保存成功'), t('platforms.douyin.messages.saveSuccessMessage', '抖音平台配置已保存'));
    } catch (e) {
      showApiError(showToast, e);
    }
  };

  const displayName = platform.display_name || platform.name;

  return (
    <main className="flex flex-col flex-1 min-h-0 bg-gradient-to-br from-gray-50 to-gray-100">
      <header className="px-6 py-4 border-b border-gray-200/80 flex justify-between items-center bg-white/60 backdrop-blur-lg sticky top-0 z-10">
        <div>
          <h2 className="text-lg font-semibold text-gray-800">
            {t('platforms.douyin.title', '{{name}} - 抖音平台配置', { name: displayName })}
          </h2>
          <p className="text-xs text-gray-500 mt-0.5">
            {t('platforms.douyin.subtitle', '配置抖音开放平台凭据与回调信息。')}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            disabled={isUpdating || isDeleting}
            onClick={() => setConfirmOpen(true)}
            className={`px-3 py-1.5 text-sm rounded-md ${isDeleting ? 'bg-red-400 text-white' : 'bg-red-600 text-white hover:bg-red-700'}`}
          >
            {isDeleting ? t('platforms.douyin.buttons.deleting', '删除中…') : t('platforms.douyin.buttons.delete', '删除')}
          </button>
          <button
            disabled={isUpdating || isDeleting || isToggling}
            onClick={async () => {
              if (isToggling) return;
              setIsToggling(true);
              try {
                if (isEnabled) {
                  await disablePlatform(platform.id);
                  showSuccess(showToast, t('platforms.douyin.messages.platformDisabled', '平台已禁用'));
                } else {
                  await enablePlatform(platform.id);
                  showSuccess(showToast, t('platforms.douyin.messages.platformEnabled', '平台已启用'));
                }
              } catch (e) {
                showApiError(showToast, e);
              } finally {
                setIsToggling(false);
              }
            }}
            className={`px-3 py-1.5 text-sm rounded-md text-white ${isEnabled ? 'bg-gray-600 hover:bg-gray-700' : 'bg-green-600 hover:bg-green-700'} ${isToggling ? 'opacity-70 cursor-not-allowed' : ''}`}
          >
            {isToggling
              ? (isEnabled ? t('platforms.douyin.buttons.disabling', '禁用中…') : t('platforms.douyin.buttons.enabling', '启用中…'))
              : (isEnabled ? t('platforms.douyin.buttons.disable', '禁用') : t('platforms.douyin.buttons.enable', '启用'))}
          </button>
          <button
            disabled={!canSave || isUpdating}
            onClick={handleSave}
            className={`px-3 py-1.5 text-sm rounded-md ${canSave ? 'bg-blue-600 text-white hover:bg-blue-700' : 'bg-gray-200 text-gray-500 cursor-not-allowed'}`}
          >
            {isUpdating ? t('platforms.douyin.buttons.saving', '保存中…') : t('platforms.douyin.buttons.save', '保存')}
          </button>
        </div>
      </header>

      <div className="flex flex-1 min-h-0 flex-col lg:flex-row gap-4 p-6">
        {/* Left: form */}
        <section className="lg:w-2/5 w-full bg-white/80 backdrop-blur-md p-5 rounded-lg shadow-sm border border-gray-200/60 space-y-4 overflow-y-auto min-h-0 auto-hide-scrollbar">
          {/* 平台名称 */}
          <div>
            <label className="block text-sm font-medium text-gray-600 mb-1">
              {t('platforms.douyin.form.platformName', '平台名称')}
            </label>
            <input
              type="text"
              value={platformName}
              onChange={(e) => setPlatformName(e.target.value)}
              placeholder={t('platforms.douyin.form.platformNamePlaceholder', '请输入平台名称')}
              className="w-full text-sm p-1.5 border border-gray-300/80 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500 bg-white/90"
            />
          </div>

          {/* App ID */}
          <div>
            <label className="block text-sm font-medium text-gray-600 mb-1">
              {t('platforms.douyin.form.appId', '应用ID (App ID)')}
            </label>
            <input
              type="text"
              value={formValues.appId}
              onChange={(e) => handleChange({ appId: e.target.value })}
              placeholder={t('platforms.douyin.form.appIdPlaceholder', '例如：your_app_id')}
              className="w-full text-sm p-1.5 border border-gray-300/80 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500 bg-white/90"
            />
          </div>

          {/* App Secret */}
          <div>
            <label className="block text-sm font-medium text-gray-600 mb-1">
              {t('platforms.douyin.form.appSecret', '应用密钥 (App Secret)')}
            </label>
            <div className="flex items-center gap-2">
              <input
                type={showAppSecret ? 'text' : 'password'}
                value={formValues.appSecret}
                onChange={(e) => handleChange({ appSecret: e.target.value })}
                placeholder={showAppSecret ? t('platforms.douyin.form.appSecretPlaceholder', '请输入 App Secret') : '********'}
                className="flex-1 text-sm p-1.5 border border-gray-300/80 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500 bg-white/90"
              />
              <button
                type="button"
                onClick={() => setShowAppSecret(v => !v)}
                className="px-2 py-1 text-xs rounded-md bg-gray-100 hover:bg-gray-200 text-gray-700"
              >
                {showAppSecret ? t('platforms.douyin.buttons.hide', '隐藏') : t('platforms.douyin.buttons.show', '显示')}
              </button>
            </div>
          </div>

          {/* Client Key */}
          <div>
            <label className="block text-sm font-medium text-gray-600 mb-1">
              {t('platforms.douyin.form.clientKey', 'Client Key')}
            </label>
            <input
              type="text"
              value={formValues.clientKey}
              onChange={(e) => handleChange({ clientKey: e.target.value })}
              placeholder={t('platforms.douyin.form.clientKeyPlaceholder', '例如：your_client_key')}
              className="w-full text-sm p-1.5 border border-gray-300/80 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500 bg-white/90"
            />
          </div>

          {/* Client Secret */}
          <div>
            <label className="block text-sm font-medium text-gray-600 mb-1">
              {t('platforms.douyin.form.clientSecret', 'Client Secret')}
            </label>
            <div className="flex items-center gap-2">
              <input
                type={showClientSecret ? 'text' : 'password'}
                value={formValues.clientSecret}
                onChange={(e) => handleChange({ clientSecret: e.target.value })}
                placeholder={showClientSecret ? t('platforms.douyin.form.clientSecretPlaceholder', '请输入 Client Secret') : '********'}
                className="flex-1 text-sm p-1.5 border border-gray-300/80 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500 bg-white/90"
              />
              <button
                type="button"
                onClick={() => setShowClientSecret(v => !v)}
                className="px-2 py-1 text-xs rounded-md bg-gray-100 hover:bg-gray-200 text-gray-700"
              >
                {showClientSecret ? t('platforms.douyin.buttons.hide', '隐藏') : t('platforms.douyin.buttons.show', '显示')}
              </button>
            </div>
          </div>

          {/* 回调 URL（只读） */}
          <div>
            <label className="block text-sm font-medium text-gray-600 mb-1">
              {t('platforms.douyin.form.callbackUrl', '回调 URL')}
            </label>
            <input
              type="text"
              value={formValues.callbackUrl}
              readOnly
              placeholder={t('platforms.douyin.form.callbackUrlPlaceholder', '平台创建后会生成回调URL')}
              className="w-full text-sm p-1.5 border border-gray-300/80 rounded-md bg-gray-100/70 focus:outline-none font-mono"
            />
            <p className="text-xs text-gray-500 mt-1">
              {t('platforms.douyin.form.callbackUrlHint', '将此 URL 配置到抖音开放平台「回调地址」设置中。')}
            </p>
          </div>

          {/* 授权范围 */}
          <div>
            <label className="block text-sm font-medium text-gray-600 mb-1">
              {t('platforms.douyin.form.authScope', '授权范围 (Authorization Scope)')}
            </label>
            <input
              type="text"
              value={formValues.authScope}
              onChange={(e) => handleChange({ authScope: e.target.value })}
              placeholder={t('platforms.douyin.form.authScopePlaceholder', '例如：user_info,video.list')}
              className="w-full text-sm p-1.5 border border-gray-300/80 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500 bg-white/90"
            />
            <p className="text-xs text-gray-500 mt-1">
              {t('platforms.douyin.form.authScopeHint', '多个权限用英文逗号分隔，例如：user_info,video.list。')}
            </p>
          </div>
        </section>

        {/* Right: comprehensive guide */}
        <section className="lg:w-3/5 w-full bg-white/80 backdrop-blur-md p-5 rounded-lg shadow-sm border border-gray-200/60 min-h-0 overflow-y-auto auto-hide-scrollbar space-y-4">
          <h3 className="text-lg font-semibold text-gray-800">
            {t('platforms.douyin.guide.title', '抖音开放平台配置指南')}
          </h3>

          <div className="bg-blue-50 border border-blue-200 text-blue-800 text-sm rounded-md p-3">
            <p className="font-medium">{t('platforms.douyin.guide.overview', '快速概览')}</p>
            <p className="mt-1">
              {t('platforms.douyin.guide.overviewText', '完成以下四步：① 注册开放平台账号 → ② 创建应用并获取凭据 → ③ 配置回调地址 → ④ 保存并测试。')}
            </p>
          </div>

          <details className="rounded-md border border-gray-200 p-3 bg-white/70">
            <summary className="cursor-pointer font-semibold text-gray-800">
              {t('platforms.douyin.guide.step1Title', '1️⃣ 注册抖音开放平台账号')}
            </summary>
            <div className="text-sm text-gray-700 mt-2 space-y-2">
              <ol className="list-decimal pl-5 space-y-1">
                <li dangerouslySetInnerHTML={{ __html: t('platforms.douyin.guide.step1Item1', '访问 <a class="text-blue-600 hover:underline" href="https://developer.open-douyin.com/" target="_blank" rel="noreferrer">抖音开放平台</a> 并完成账号注册与主体认证（如需）。') }} />
                <li>{t('platforms.douyin.guide.step1Item2', '登录控制台，完善开发者信息。')}</li>
              </ol>
            </div>
          </details>

          <details className="rounded-md border border-gray-200 p-3 bg-white/70">
            <summary className="cursor-pointer font-semibold text-gray-800">
              {t('platforms.douyin.guide.step2Title', '2️⃣ 创建应用并获取凭据')}
            </summary>
            <div className="text-sm text-gray-700 mt-2 space-y-2">
              <ol className="list-decimal pl-5 space-y-1">
                <li>{t('platforms.douyin.guide.step2Item1', '在控制台创建新应用，记下 App ID 与 App Secret。')}</li>
                <li>{t('platforms.douyin.guide.step2Item2', '在应用设置中获取 Client Key 与 Client Secret。')}</li>
                <li>{t('platforms.douyin.guide.step2Item3', '根据业务选择并开通所需的授权范围（Scope）。')}</li>
              </ol>
              <div className="bg-gray-50 border border-gray-200 rounded p-2 text-xs">
                <pre className="font-mono overflow-x-auto">{`APP_ID=your_app_id
APP_SECRET=your_app_secret
CLIENT_KEY=your_client_key
CLIENT_SECRET=your_client_secret
AUTH_SCOPE=user_info,video.list`}</pre>
              </div>
            </div>
          </details>

          <details className="rounded-md border border-gray-200 p-3 bg-white/70">
            <summary className="cursor-pointer font-semibold text-gray-800">
              {t('platforms.douyin.guide.step3Title', '3️⃣ 配置回调地址')}
            </summary>
            <div className="text-sm text-gray-700 mt-2 space-y-2">
              <ol className="list-decimal pl-5 space-y-1">
                <li>{t('platforms.douyin.guide.step3Item1', '在开放平台「回调设置」中配置回调 URL：使用上方只读回调 URL。')}</li>
                <li>{t('platforms.douyin.guide.step3Item2', '确保服务端可公网访问，并正确处理校验请求。')}</li>
              </ol>
              <div className="bg-gray-50 border border-gray-200 rounded p-2 text-xs">
                <pre className="font-mono overflow-x-auto">{`CALLBACK_URL=https://your-domain.com/api/douyin/callback/{platformId}`}</pre>
              </div>
            </div>
          </details>

          <details className="rounded-md border border-gray-200 p-3 bg-white/70">
            <summary className="cursor-pointer font-semibold text-gray-800">
              {t('platforms.douyin.guide.step4Title', '4️⃣ 常见问题与排查')}
            </summary>
            <div className="text-sm text-gray-700 mt-2 space-y-2">
              <ul className="list-disc pl-5 space-y-1">
                <li>{t('platforms.douyin.guide.step4Item1', '回调校验失败：检查回调 URL 是否可访问、TLS 证书是否有效。')}</li>
                <li>{t('platforms.douyin.guide.step4Item2', '权限不足：确认所需 Scope 已在开放平台开通并授权。')}</li>
                <li>{t('platforms.douyin.guide.step4Item3', '凭据错误：核对 App ID/Secret 与 Client Key/Secret 是否输入正确。')}</li>
              </ul>
              <a className="text-blue-600 hover:underline" href="https://developer.open-douyin.com/" target="_blank" rel="noreferrer">抖音开放平台文档</a>
            </div>
          </details>

          <div className="bg-green-50 border border-green-200 text-green-800 text-sm rounded-md p-3">
            <p className="font-semibold">{t('platforms.douyin.guide.bestPracticesTitle', '最佳实践')}</p>
            <ul className="list-disc pl-5 mt-1 space-y-1">
              <li>{t('platforms.douyin.guide.bestPracticesItem1', '将密钥存放于安全的密钥管理服务（如 KMS/Vault），避免出现在代码库。')}</li>
              <li>{t('platforms.douyin.guide.bestPracticesItem2', '不同环境（开发/测试/生产）使用不同的回调与凭据，按需最小授权。')}</li>
              <li>{t('platforms.douyin.guide.bestPracticesItem3', '定期轮换密钥并最小化权限范围（Scope）。')}</li>
            </ul>
          </div>
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
        title={t('platforms.douyin.confirm.deleteTitle', '删除平台')}
        message={t('platforms.douyin.confirm.deleteMessage', '确定要删除此平台吗？')}
        confirmText={t('platforms.douyin.confirm.confirmText', '删除')}
        cancelText={t('platforms.douyin.confirm.cancelText', '取消')}
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
            showSuccess(showToast, t('platforms.douyin.messages.deleteSuccess', '平台已删除'), t('platforms.douyin.messages.deleteSuccessMessage', '平台已删除'));
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

export default DouyinPlatformConfig;

