import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import ConfirmDialog from '@/components/ui/ConfirmDialog';
import type { Platform, PlatformConfig } from '@/types';
import { usePlatformStore } from '@/stores/platformStore';
import { useToast } from '@/hooks/useToast';
import { showApiError, showSuccess } from '@/utils/toastHelpers';

interface Props {
  platform: Platform; // expected: platform.type === 'wecom'
}

const WeComPlatformConfig: React.FC<Props> = ({ platform }) => {
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
  const canSave = hasConfigChanges || hasNameChanged;

  // Local form state sourced from platform.config
  const [formValues, setFormValues] = useState(() => ({
    corpId: (platform.config as any)?.corp_id ?? '',
    agentId: (platform.config as any)?.agent_id ?? '',
    appSecret: (platform.config as any)?.app_secret ?? '',
    token: (platform.config as any)?.token ?? '',
    encodingAESKey: (platform.config as any)?.encoding_aes_key ?? '',
    callbackUrl: (platform as any)?.callback_url ?? '',
  }));

  useEffect(() => {
    setFormValues({
      corpId: (platform.config as any)?.corp_id ?? '',
      agentId: (platform.config as any)?.agent_id ?? '',
      appSecret: (platform.config as any)?.app_secret ?? '',
      token: (platform.config as any)?.token ?? '',
      encodingAESKey: (platform.config as any)?.encoding_aes_key ?? '',
      callbackUrl: (platform as any)?.callback_url ?? '',
    });
  }, [platform]);

  const handleChange = (patch: Partial<typeof formValues>) => {
    setFormValues(v => ({ ...v, ...patch }));
    const { callbackUrl, ...rest } = { ...formValues, ...patch };
    // Write changes to store; callbackUrl is derived from backend (callback_url)
    const toSave: Partial<PlatformConfig> = {
      ...(rest.corpId !== undefined ? { corpId: rest.corpId } : {}),
      ...(rest.agentId !== undefined ? { agentId: rest.agentId } : {}),
      ...(rest.appSecret !== undefined ? { appSecret: rest.appSecret } : {}),
      ...(rest.token !== undefined ? { token: rest.token } : {}),
      ...(rest.encodingAESKey !== undefined ? { encodingAESKey: rest.encodingAESKey } : {}),
    };
    updatePlatformConfig(platform.id, toSave);
  };

  const [showSecret, setShowSecret] = useState(false);

  const handleSave = async () => {
    try {
      if (hasConfigChanges) {
        // Transform camelCase form values to snake_case API payload for WeCom
        const snakeConfig: Record<string, any> = {
          corp_id: (formValues.corpId || '').trim(),
          agent_id: (formValues.agentId || '').trim(),
          app_secret: (formValues.appSecret || '').trim(),
          token: (formValues.token || '').trim(),
        };
        const aes = (formValues.encodingAESKey || '').trim();
        if (aes) {
          snakeConfig.encoding_aes_key = aes;
        } else {
          // optional: backend accepts undefined or null
          snakeConfig.encoding_aes_key = null;
        }

        await updatePlatform(platform.id, { config: snakeConfig });
        // Clear pending local camelCase changes since we sent transformed payload
        resetPlatformConfig(platform.id);
      }
      if (hasNameChanged) {
        await updatePlatform(platform.id, { name: platformName.trim() });
      }
      showSuccess(showToast, t('platforms.wecom.messages.saveSuccess', '保存成功'), t('platforms.wecom.messages.saveSuccessMessage', '企业微信平台配置已更新'));
    } catch (e) {
      showApiError(showToast, e);
    }
  };

  const displayName = platform.display_name || platform.name;

  return (
    <main className="flex flex-col flex-1 min-h-0 bg-gradient-to-br from-gray-50 to-gray-100">
      <header className="px-6 py-4 border-b border-gray-200/80 flex justify-between items-center bg-white/60 backdrop-blur-lg sticky top-0 z-10">
        <div>
          <h2 className="text-lg font-semibold text-gray-800">{t('platforms.wecom.header.title', {"name":displayName})}</h2>
          <p className="text-xs text-gray-500 mt-0.5">{t('platforms.wecom.header.subtitle', '配置企业微信（WeCom）对接所需的凭据与回调。')}</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            disabled={isUpdating || isDeleting}
            onClick={() => setConfirmOpen(true)}
            className={`px-3 py-1.5 text-sm rounded-md ${isDeleting ? 'bg-red-400 text-white' : 'bg-red-600 text-white hover:bg-red-700'}`}
          >
            {isDeleting ? t('platforms.wecom.buttons.deleting', '删除中…') : t('platforms.wecom.buttons.delete', '删除')}
          </button>
          <button
            disabled={isUpdating || isDeleting || isToggling}
            onClick={async () => {
              if (isToggling) return;
              setIsToggling(true);
              try {
                if (isEnabled) {
                  await disablePlatform(platform.id);
                  showSuccess(showToast, t('platforms.wecom.messages.disabled', '平台已禁用'));
                } else {
                  await enablePlatform(platform.id);
                  showSuccess(showToast, t('platforms.wecom.messages.enabled', '平台已启用'));
                }
              } catch (e) {
                showApiError(showToast, e);
              } finally {
                setIsToggling(false);
              }
            }}
            className={`px-3 py-1.5 text-sm rounded-md text-white ${isEnabled ? 'bg-gray-600 hover:bg-gray-700' : 'bg-green-600 hover:bg-green-700'} ${isToggling ? 'opacity-70 cursor-not-allowed' : ''}`}
          >
            {isToggling ? (isEnabled ? t('platforms.wecom.buttons.disabling', '禁用中…') : t('platforms.wecom.buttons.enabling', '启用中…')) : (isEnabled ? t('platforms.wecom.buttons.disable', '禁用') : t('platforms.wecom.buttons.enable', '启用'))}
          </button>

          <button
            disabled={!canSave || isUpdating}
            onClick={handleSave}
            className={`px-3 py-1.5 text-sm rounded-md ${canSave ? 'bg-blue-600 text-white hover:bg-blue-700' : 'bg-gray-200 text-gray-500 cursor-not-allowed'}`}
          >
            {isUpdating ? t('platforms.wecom.buttons.saving', '保存中…') : t('platforms.wecom.buttons.save', '保存')}
          </button>
        </div>
      </header>

      <div className="flex flex-1 min-h-0 flex-col lg:flex-row gap-4 p-6">
        {/* Left: form */}
        <section className="lg:w-2/5 w-full bg-white/80 backdrop-blur-md p-5 rounded-lg shadow-sm border border-gray-200/60 space-y-4 overflow-y-auto min-h-0 auto-hide-scrollbar">
          {/* 平台名称 */}
          <div>
            <label className="block text-sm font-medium text-gray-600 mb-1">{t('platforms.wecom.form.name', '平台名称')}</label>
            <input
              type="text"
              value={platformName}
              onChange={(e) => setPlatformName(e.target.value)}
              placeholder={t('platforms.wecom.form.namePlaceholder', '请输入平台名称')}
              className="w-full text-sm p-1.5 border border-gray-300/80 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500 bg-white/90"
            />
          </div>

          {/* 企业ID（CorpID） */}
          <div>
            <label className="block text-sm font-medium text-gray-600 mb-1">{t('platforms.wecom.form.corpId', '企业ID（CorpID）')}</label>
            <input
              type="text"
              value={formValues.corpId}
              onChange={(e) => handleChange({ corpId: e.target.value })}
              placeholder={t('platforms.wecom.form.corpIdPlaceholder', '例如：ww1234567890abcdef')}
              className="w-full text-sm p-1.5 border border-gray-300/80 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500 bg-white/90"
            />
            <p className="text-xs text-gray-500 mt-1">{t('platforms.wecom.form.corpIdHint', '可在「我的企业」-「企业信息」中查看。')}</p>
          </div>

          {/* 应用AgentId */}
          <div>
            <label className="block text-sm font-medium text-gray-600 mb-1">{t('platforms.wecom.form.agentId', '应用 AgentId')}</label>
            <input
              type="text"
              value={formValues.agentId}
              onChange={(e) => handleChange({ agentId: e.target.value })}
              placeholder={t('platforms.wecom.form.agentIdPlaceholder', '例如：1000002')}
              className="w-full text-sm p-1.5 border border-gray-300/80 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500 bg-white/90"
            />
            <p className="text-xs text-gray-500 mt-1">{t('platforms.wecom.form.agentIdHint', '在企业微信管理后台的应用详情页获取。')}</p>
          </div>

          {/* 应用Secret（App Secret） */}
          <div>
            <label className="block text-sm font-medium text-gray-600 mb-1">{t('platforms.wecom.form.appSecret', '应用 Secret')}</label>
            <div className="flex items-center gap-2">
              <input
                type={showSecret ? 'text' : 'password'}
                value={formValues.appSecret}
                onChange={(e) => handleChange({ appSecret: e.target.value })}
                placeholder={showSecret ? t('platforms.wecom.form.appSecretPlaceholder', '请输入应用Secret') : '********'}
                className="flex-1 text-sm p-1.5 border border-gray-300/80 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500 bg-white/90"
              />
              <button
                type="button"
                onClick={() => setShowSecret(v => !v)}
                className="px-2 py-1 text-xs rounded-md bg-gray-100 hover:bg-gray-200 text-gray-700"
              >
                {showSecret ? t('platforms.wecom.buttons.hide', '隐藏') : t('platforms.wecom.buttons.show', '显示')}
              </button>
            </div>
            <p className="text-xs text-gray-500 mt-1">{t('platforms.wecom.form.appSecretHint', '用于调用企业微信接口的凭证，请妥善保管。')}</p>
          </div>

          {/* Token */}
          <div>
            <label className="block text-sm font-medium text-gray-600 mb-1">{t('platforms.wecom.form.token', 'Token')}</label>
            <input
              type="text"
              value={formValues.token}
              onChange={(e) => handleChange({ token: e.target.value })}
              placeholder={t('platforms.wecom.form.tokenPlaceholder', '用于回调验证的 Token')}
              className="w-full text-sm p-1.5 border border-gray-300/80 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500 bg-white/90"
            />
            <p className="text-xs text-gray-500 mt-1">{t('platforms.wecom.form.tokenHint', '与企业微信回调配置中的 Token 保持一致。')}</p>
          </div>

          {/* EncodingAESKey */}
          <div>
            <label className="block text-sm font-medium text-gray-600 mb-1">{t('platforms.wecom.form.encodingAESKey', 'EncodingAESKey')}</label>
            <input
              type="text"
              value={formValues.encodingAESKey}
              onChange={(e) => handleChange({ encodingAESKey: e.target.value })}
              placeholder={t('platforms.wecom.form.encodingAESKeyPlaceholder', '43 位字符的消息加密密钥')}
              className="w-full text-sm p-1.5 border border-gray-300/80 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500 bg-white/90"
            />
            <p className="text-xs text-gray-500 mt-1">{t('platforms.wecom.form.encodingAESKeyHint', '在消息加解密方式为兼容/安全模式时使用。')}</p>
          </div>

          {/* 回调URL（只读） */}
          <div>
            <label className="block text-sm font-medium text-gray-600 mb-1">{t('platforms.wecom.form.callbackUrl', '回调 URL')}</label>
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={formValues.callbackUrl}
                readOnly
                placeholder={t('platforms.wecom.form.callbackUrlPlaceholder', '平台创建后会生成回调URL')}
                className="flex-1 text-sm p-1.5 border border-gray-300/80 rounded-md bg-gray-100/70 focus:outline-none font-mono"
              />
              <button
                type="button"
                disabled={!formValues.callbackUrl}
                onClick={async () => {
                  try {
                    if (!formValues.callbackUrl) return;
                    await navigator.clipboard.writeText(formValues.callbackUrl);
                    showSuccess(showToast, t('platforms.wecom.messages.urlCopied', '回调URL已复制'));
                  } catch (e) {
                    showApiError(showToast, e);
                  }
                }}
                className={`px-2 py-1 text-xs rounded-md ${formValues.callbackUrl ? 'bg-gray-100 hover:bg-gray-200 text-gray-700' : 'bg-gray-100 text-gray-400 cursor-not-allowed'}`}
              >
                {t('platforms.wecom.buttons.copy', '复制')}
              </button>
            </div>
            <p className="text-xs text-gray-500 mt-1">{t('platforms.wecom.form.callbackUrlHint', '将此 URL 配置到企业微信「服务器配置」中的回调地址。')}</p>
          </div>
        </section>

        {/* Right: comprehensive guide */}
        <section className="lg:w-3/5 w-full bg-white/80 backdrop-blur-md p-5 rounded-lg shadow-sm border border-gray-200/60 min-h-0 overflow-y-auto auto-hide-scrollbar space-y-4">
          <h3 className="text-lg font-semibold text-gray-800">{t('platforms.wecom.guide.title', '企业微信（WeCom）配置指南')}</h3>

          <div className="bg-blue-50 border border-blue-200 text-blue-800 text-sm rounded-md p-3">
            <p className="font-medium">{t('platforms.wecom.guide.overview', '快速概览')}</p>
            <p className="mt-1">{t('platforms.wecom.guide.overviewText', '完成以下四步：①查找企业ID → ②获取应用 AgentId/Secret → ③配置服务器回调（URL/Token/EncodingAESKey）→ ④保存测试。')}</p>
          </div>

          <details className="rounded-md border border-gray-200 p-3 bg-white/70">
            <summary className="cursor-pointer font-semibold text-gray-800">{t('platforms.wecom.guide.step1Title', '1️⃣ 查找企业ID（CorpID）')}</summary>
            <div className="text-sm text-gray-700 mt-2 space-y-2">
              <ol className="list-decimal pl-5 space-y-1">
                <li dangerouslySetInnerHTML={{ __html: t('platforms.wecom.guide.step1Item1', '登录 <a class="text-blue-600 hover:underline" href="https://work.weixin.qq.com/wework_admin/frame" target="_blank" rel="noreferrer">企业微信管理后台</a>。') }} />
                <li>{t('platforms.wecom.guide.step1Item2', '进入「我的企业」 → 「企业信息」页面。')}</li>
                <li>{t('platforms.wecom.guide.step1Item3', '复制「企业ID（CorpID）」并粘贴到左侧表单「企业ID」。')}</li>
              </ol>
              <div className="bg-gray-50 border border-gray-200 rounded p-2 text-xs">
                <pre className="font-mono overflow-x-auto">{t('platforms.wecom.guide.step1Example', '示例：ww1234567890abcdef')}</pre>
              </div>
            </div>
          </details>

          <details className="rounded-md border border-gray-200 p-3 bg-white/70">
            <summary className="cursor-pointer font-semibold text-gray-800">{t('platforms.wecom.guide.step2Title', '2️⃣ 获取应用 AgentId 与 App Secret')}</summary>
            <div className="text-sm text-gray-700 mt-2 space-y-2">
              <ol className="list-decimal pl-5 space-y-1">
                <li>{t('platforms.wecom.guide.step2Item1', '在后台左侧选择「应用管理」，打开你的自建应用。')}</li>
                <li>{t('platforms.wecom.guide.step2Item2', '在应用详情页可看到「AgentId」。')}</li>
                <li>{t('platforms.wecom.guide.step2Item3', '点击「Secret」显示或重置，复制后填入左侧表单「应用 Secret」。')}</li>
              </ol>
              <div className="bg-yellow-50 border border-yellow-200 rounded p-2 text-xs text-yellow-800">
                <p className="font-semibold">{t('platforms.wecom.guide.step2SecurityTitle', '安全提示')}</p>
                <p>{t('platforms.wecom.guide.step2SecurityText', '请妥善保管 Secret，不要泄露；生产环境建议使用最小权限与定期轮换。')}</p>
              </div>
            </div>
          </details>

          <details className="rounded-md border border-gray-200 p-3 bg-white/70">
            <summary className="cursor-pointer font-semibold text-gray-800">{t('platforms.wecom.guide.step3Title', '3️⃣ 配置服务器回调（URL / Token / EncodingAESKey）')}</summary>
            <div className="text-sm text-gray-700 mt-2 space-y-3">
              <ol className="list-decimal pl-5 space-y-1">
                <li>{t('platforms.wecom.guide.step3Item1', '在「应用管理」→ 你的应用 → 「接收消息」中，点击「设置」进入「服务器配置」。')}</li>
                <li>{t('platforms.wecom.guide.step3Item2', '回调 URL：复制左侧表单中的回调 URL（只读）粘贴至后台；')}</li>
                <li>{t('platforms.wecom.guide.step3Item3', 'Token：自定义任意字符串，并确保与左侧表单一致；')}</li>
                <li>{t('platforms.wecom.guide.step3Item4', 'EncodingAESKey：点击生成 43 位密钥，并复制到左侧表单；')}</li>
                <li>{t('platforms.wecom.guide.step3Item5', '消息加解密方式：建议选择「兼容模式」或「安全模式」。')}</li>
              </ol>
              <div>
                <h4 className="text-sm font-semibold text-gray-800">{t('platforms.wecom.guide.step3ExampleTitle', '示例占位（仅供参考）')}</h4>
                <div className="bg-gray-50 border border-gray-200 rounded p-2 text-xs">
                  <pre className="font-mono overflow-x-auto">{`URL:    https://your-domain.com/api/wecom/callback/{platformId}
Token:  your_token_string
AESKey: your_43_chars_encoding_aes_key`}</pre>
                </div>
              </div>
              <div className="bg-blue-50 border border-blue-200 rounded p-2 text-xs text-blue-800">
                <p>{t('platforms.wecom.guide.step3Note', '保存后，企业微信会进行 URL 校验，请确保服务端已正确返回校验响应。')}</p>
              </div>
            </div>
          </details>

          <details className="rounded-md border border-gray-200 p-3 bg-white/70">
            <summary className="cursor-pointer font-semibold text-gray-800">{t('platforms.wecom.guide.step4Title', '4️⃣ 常见问题与排查')}</summary>
            <div className="text-sm text-gray-700 mt-2 space-y-2">
              <ul className="list-disc pl-5 space-y-1">
                <li>{t('platforms.wecom.guide.step4Item1', 'URL 校验失败：检查你的回调服务是否可公网访问，TLS 证书是否有效。')}</li>
                <li>{t('platforms.wecom.guide.step4Item2', '消息解密失败：确认 EncodingAESKey 正确且未包含多余空格。')}</li>
                <li>{t('platforms.wecom.guide.step4Item3', '403/权限问题：确认应用已启用并授予所需权限；必要时重新生成 Secret。')}</li>
              </ul>
              <a className="text-blue-600 hover:underline" href="https://developer.work.weixin.qq.com/document/path/90968" target="_blank" rel="noreferrer">{t('platforms.wecom.guide.docsLink', '企业微信消息回调开发文档')}</a>
            </div>
          </details>

          <div className="bg-green-50 border border-green-200 text-green-800 text-sm rounded-md p-3">
            <p className="font-semibold">{t('platforms.wecom.guide.bestPracticesTitle', '最佳实践')}</p>
            <ul className="list-disc pl-5 mt-1 space-y-1">
              <li>{t('platforms.wecom.guide.bestPracticesItem1', '将 Secret 存放于密钥管理服务（如 Vault、KMS），避免明文出现在代码库。')}</li>
              <li>{t('platforms.wecom.guide.bestPracticesItem2', '为不同环境（开发/测试/生产）使用不同的 Token/AESKey。')}</li>
              <li>{t('platforms.wecom.guide.bestPracticesItem3', '定期轮换 Secret，并在失效前完成服务端配置更新。')}</li>
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
        title=""
        message="?"
        confirmText=""
        cancelText=""
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
            showSuccess(showToast, '', '');
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

export default WeComPlatformConfig;

