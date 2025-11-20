import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { FiCopy, FiEye, FiEyeOff, FiRefreshCw } from 'react-icons/fi';
import ConfirmDialog from '@/components/ui/ConfirmDialog';
import type { Platform } from '@/types';
import { usePlatformStore } from '@/stores/platformStore';
import { useToast } from '@/hooks/useToast';
import { showApiError, showSuccess } from '@/utils/toastHelpers';

interface Props {
  platform: Platform;
}

const CustomPlatformConfig: React.FC<Props> = ({ platform }) => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { showToast } = useToast();

  const deletePlatform = usePlatformStore(s => s.deletePlatform);
  const enablePlatform = usePlatformStore(s => s.enablePlatform);
  const disablePlatform = usePlatformStore(s => s.disablePlatform);
  const regenerateApiKey = usePlatformStore(s => s.regenerateApiKey);
  const updatePlatform = usePlatformStore(s => s.updatePlatform);
  const platforms = usePlatformStore(s => s.platforms);
  const isUpdating = usePlatformStore(s => s.isUpdating);

  // Name editing
  const [platformName, setPlatformName] = useState<string>(platform.name);
  useEffect(() => { setPlatformName(platform.name); }, [platform.name]);
  const hasNameChanged = useMemo(() => platformName.trim() !== platform.name, [platformName, platform.name]);

  // Callback URL state - initialize from platform.config.callback_url
  const [callbackUrl, setCallbackUrl] = useState<string>('');
  useEffect(() => {
    setCallbackUrl((platform.config as any)?.callback_url ?? '');
  }, [platform.config]);
  const hasCallbackChanged = useMemo(() => {
    const originalCallback = (platform.config as any)?.callback_url ?? '';
    return callbackUrl.trim() !== originalCallback;
  }, [callbackUrl, platform.config]);

  const canSave = hasNameChanged || hasCallbackChanged;

  const [showApiKey, setShowApiKey] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isToggling, setIsToggling] = useState(false);
  const [isRegenerating, setIsRegenerating] = useState(false);

  const isEnabled = platform.status === 'connected';
  const apiKey: string = useMemo(() => ((platform.config as any)?.apiKey ?? ''), [platform.config]);
  const chatUrl: string = useMemo(() => platform.chat_url ?? '', [platform.chat_url]);

  const copyToClipboard = async (text: string, label: string) => {
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      showSuccess(showToast, t('platforms.custom.copied', '{{label}} 已复制到剪贴板', { label }));
    } catch (error) {
      showApiError(showToast, error);
    }
  };

  const handleSave = async () => {
    try {
      // Validate callback URL format if it has changed
      if (hasCallbackChanged && callbackUrl && callbackUrl.trim()) {
        try {
          new URL(callbackUrl);
        } catch {
          showToast('error', t('platforms.custom.invalidUrl', '无效的 URL 格式'), t('platforms.custom.invalidUrlHint', '请输入有效的 HTTP/HTTPS 地址'));
          return;
        }
      }

      // Build update payload
      const updatePayload: any = {};

      if (hasNameChanged) {
        updatePayload.name = platformName.trim();
      }

      if (hasCallbackChanged) {
        updatePayload.config = {
          callback_url: callbackUrl.trim() || undefined
        };
      }

      await updatePlatform(platform.id, updatePayload);
      showSuccess(showToast, t('platforms.custom.saveSuccess', '保存成功'));
    } catch (error) {
      showApiError(showToast, error);
    }
  };

  const handleToggleStatus = async () => {
    setIsToggling(true);
    try {
      if (isEnabled) {
        await disablePlatform(platform.id);
        showSuccess(showToast, t('platforms.custom.disabled', '平台已禁用'));
      } else {
        await enablePlatform(platform.id);
        showSuccess(showToast, t('platforms.custom.enabled', '平台已启用'));
      }
    } catch (error) {
      showApiError(showToast, error);
    } finally {
      setIsToggling(false);
    }
  };

  const handleRegenerateApiKey = async () => {
    if (!confirm(t('platforms.custom.confirmRegenerate', '确定要重新生成 API 密钥吗？旧密钥将立即失效。'))) {
      return;
    }

    setIsRegenerating(true);
    try {
      await regenerateApiKey(platform.id);
      showSuccess(showToast, t('platforms.custom.regenerated', 'API 密钥已重新生成'));
    } catch (error) {
      showApiError(showToast, error);
    } finally {
      setIsRegenerating(false);
    }
  };

  const handleDelete = async () => {
    setIsDeleting(true);
    try {
      const idx = platforms.findIndex(p => p.id === platform.id);
      const nextId = idx !== -1
        ? (idx < platforms.length - 1 ? platforms[idx + 1]?.id : (idx > 0 ? platforms[idx - 1]?.id : null))
        : null;
      await deletePlatform(platform.id);
      showSuccess(showToast, t('platforms.custom.deleted', '平台已删除'));
      setConfirmOpen(false);
      if (nextId) navigate(`/platforms/${nextId}`);
      else navigate('/platforms');
    } catch (error) {
      showApiError(showToast, error);
    } finally {
      setIsDeleting(false);
    }
  };

  const displayName = platform.display_name || platform.name;

  return (
    <main className="flex flex-col flex-1 min-h-0 bg-gradient-to-br from-gray-50 to-gray-100">
      {/* Header */}
      <header className="px-6 py-4 border-b border-gray-200/80 flex justify-between items-center bg-white/60 backdrop-blur-lg sticky top-0 z-10">
        <div>
          <h2 className="text-lg font-semibold text-gray-800">{displayName} - {t('platforms.custom.title', '自定义平台配置')}</h2>
          <p className="text-xs text-gray-500 mt-0.5">{t('platforms.custom.subtitle', '配置第三方程序集成所需的 API 信息与回调地址。')}</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            disabled={isUpdating || isDeleting}
            onClick={() => setConfirmOpen(true)}
            className={`px-3 py-1.5 text-sm rounded-md ${isDeleting ? 'bg-red-400 text-white' : 'bg-red-600 text-white hover:bg-red-700'}`}
          >
            {isDeleting ? t('common.deleting', '删除中…') : t('common.delete', '删除')}
          </button>
          <button
            disabled={isUpdating || isDeleting || isToggling}
            onClick={handleToggleStatus}
            className={`px-3 py-1.5 text-sm rounded-md text-white ${isEnabled ? 'bg-gray-600 hover:bg-gray-700' : 'bg-green-600 hover:bg-green-700'} ${isToggling ? 'opacity-70 cursor-not-allowed' : ''}`}
          >
            {isToggling ? (isEnabled ? t('common.disabling', '禁用中…') : t('common.enabling', '启用中…')) : (isEnabled ? t('common.disable', '禁用') : t('common.enable', '启用'))}
          </button>
          <button
            disabled={!canSave || isUpdating}
            onClick={handleSave}
            className={`px-3 py-1.5 text-sm rounded-md ${canSave ? 'bg-blue-600 text-white hover:bg-blue-700' : 'bg-gray-200 text-gray-500 cursor-not-allowed'}`}
          >
            {isUpdating ? t('common.saving', '保存中…') : t('common.save', '保存')}
          </button>
        </div>
      </header>

      <div className="flex flex-1 min-h-0 flex-col lg:flex-row gap-4 p-6">
        {/* Left: Configuration Form */}
        <section className="lg:w-2/5 w-full bg-white/80 backdrop-blur-md p-5 rounded-lg shadow-sm border border-gray-200/60 space-y-4 overflow-y-auto min-h-0 auto-hide-scrollbar">
          <h3 className="text-base font-semibold text-gray-800 mb-3">{t('platforms.custom.configSection', '配置信息')}</h3>

          {/* Platform Name */}
          <div>
            <label className="block text-sm font-medium text-gray-600 mb-1">{t('platforms.custom.platformName', '平台名称')}</label>
            <input
              type="text"
              value={platformName}
              onChange={(e) => setPlatformName(e.target.value)}
              placeholder={t('platforms.custom.platformNamePlaceholder', '请输入平台名称')}
              className="w-full text-sm p-1.5 border border-gray-300/80 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500 bg-white/90"
            />
          </div>

          <div className="border-t border-gray-200 my-4"></div>

          <h3 className="text-base font-semibold text-gray-800 mb-3">{t('platforms.custom.integration.title', 'API 集成信息')}</h3>

          {/* Chat URL */}
          <div>
            <label className="block text-sm font-medium text-gray-600 mb-1">{t('platforms.custom.chatUrl', '对话接口地址')}</label>
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={chatUrl || t('platforms.custom.notAvailable', '暂无')}
                readOnly
                className="flex-1 text-sm p-1.5 border border-gray-300/80 rounded-md bg-gray-100/70 focus:outline-none font-mono"
              />
              <button
                type="button"
                disabled={!chatUrl}
                onClick={() => copyToClipboard(chatUrl, t('platforms.custom.chatUrl', '对话接口地址'))}
                className={`px-2 py-1 text-xs rounded-md ${chatUrl ? 'bg-gray-100 hover:bg-gray-200 text-gray-700' : 'bg-gray-100 text-gray-400 cursor-not-allowed'}`}
              >
                {t('common.copy', '复制')}
              </button>
            </div>
            <p className="text-xs text-gray-500 mt-1">{t('platforms.custom.chatUrlHint', '第三方程序调用此地址发送对话消息。')}</p>
          </div>

          {/* API Key */}
          <div>
            <label className="block text-sm font-medium text-gray-600 mb-1">{t('platforms.custom.apiKey', 'API 密钥')}</label>
            <div className="flex items-center gap-2">
              <input
                type={showApiKey ? 'text' : 'password'}
                value={apiKey || t('platforms.custom.notAvailable', '暂无')}
                readOnly
                className="flex-1 text-sm p-1.5 border border-gray-300/80 rounded-md bg-gray-100/70 focus:outline-none font-mono"
              />
              <button
                type="button"
                onClick={() => setShowApiKey(!showApiKey)}
                className="px-2 py-1 text-xs rounded-md bg-gray-100 hover:bg-gray-200 text-gray-700"
              >
                {showApiKey ? <FiEyeOff className="w-4 h-4" /> : <FiEye className="w-4 h-4" />}
              </button>
              <button
                type="button"
                disabled={!apiKey}
                onClick={() => copyToClipboard(apiKey, t('platforms.custom.apiKey', 'API 密钥'))}
                className={`px-2 py-1 text-xs rounded-md ${apiKey ? 'bg-gray-100 hover:bg-gray-200 text-gray-700' : 'bg-gray-100 text-gray-400 cursor-not-allowed'}`}
              >
                <FiCopy className="w-4 h-4" />
              </button>
              <button
                type="button"
                onClick={handleRegenerateApiKey}
                disabled={isRegenerating}
                className="px-2 py-1 text-xs rounded-md bg-orange-100 hover:bg-orange-200 text-orange-700 disabled:opacity-50"
              >
                <FiRefreshCw className={`w-4 h-4 ${isRegenerating ? 'animate-spin' : ''}`} />
              </button>
            </div>
            <p className="text-xs text-gray-500 mt-1">{t('platforms.custom.apiKeyHint', '在请求头中使用 X-Platform-API-Key 进行认证。')}</p>
          </div>

          {/* Callback URL */}
          <div>
            <label className="block text-sm font-medium text-gray-600 mb-1">{t('platforms.custom.callbackUrl', '回调地址')}</label>
            <p className="text-xs text-gray-500 mb-2">{t('platforms.custom.callbackUrlHint', '当客服回复消息时，系统会将消息推送到此地址')}</p>
            <div className="flex items-center gap-2">
              <input
                type="url"
                value={callbackUrl}
                onChange={(e) => setCallbackUrl(e.target.value)}
                placeholder={t('platforms.custom.callbackUrlPlaceholder', 'https://your-domain.com/webhook/callback')}
                className="flex-1 text-sm p-1.5 border border-gray-300/80 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500 bg-white/90 font-mono"
              />
              <button
                type="button"
                disabled={!callbackUrl}
                onClick={() => copyToClipboard(callbackUrl, t('platforms.custom.callbackUrl', '回调地址'))}
                className={`px-2 py-1 text-xs rounded-md ${callbackUrl ? 'bg-gray-100 hover:bg-gray-200 text-gray-700' : 'bg-gray-100 text-gray-400 cursor-not-allowed'}`}
              >
                {t('common.copy', '复制')}
              </button>
            </div>
          </div>
        </section>

        {/* Right: Integration Guide */}
        <section className="lg:w-3/5 w-full bg-white/80 backdrop-blur-md p-5 rounded-lg shadow-sm border border-gray-200/60 min-h-0 overflow-y-auto auto-hide-scrollbar space-y-4">
          <h3 className="text-lg font-semibold text-gray-800">{t('platforms.custom.integration.guide', '集成指南')}</h3>

          {/* 1. Chat API - Send Messages to TGO */}
          <details className="rounded-md border border-gray-200 p-3 bg-white/70" open>
            <summary className="cursor-pointer font-semibold text-gray-800">{t('platforms.custom.integration.chatApi', '对话接口说明（发送消息到 TGO）')}</summary>
            <div className="text-sm text-gray-700 mt-3 space-y-3">
              {/* API Endpoint */}
              <div>
                <p className="font-medium text-gray-800 mb-1">{t('platforms.custom.integration.endpoint', '接口地址')}</p>
                <code className="block bg-gray-50 px-3 py-2 rounded border border-gray-200 font-mono text-xs">
                  {chatUrl || '{chat_url}'}
                </code>
              </div>

              {/* Authentication */}
              <div>
                <p className="font-medium text-gray-800 mb-1">{t('platforms.custom.integration.authentication', '认证方式')}</p>
                <p className="text-xs text-gray-600 mb-1">{t('platforms.custom.integration.authDesc', '在请求头中添加平台 API 密钥：')}</p>
                <code className="block bg-gray-50 px-3 py-2 rounded border border-gray-200 font-mono text-xs">
                  X-Platform-API-Key: {apiKey || '{your_api_key}'}
                </code>
              </div>

              {/* Required Parameters */}
              <div>
                <p className="font-medium text-gray-800 mb-1">{t('platforms.custom.integration.requiredParams', '必需参数')}</p>
                <ul className="list-disc list-inside text-xs text-gray-600 space-y-1">
                  <li><code className="bg-gray-100 px-1 py-0.5 rounded font-mono">messages</code>: {t('platforms.custom.integration.messagesDesc', '对话消息数组，格式与 OpenAI ChatGPT API 兼容')}</li>
                  <li><code className="bg-gray-100 px-1 py-0.5 rounded font-mono">user</code>: {t('platforms.custom.integration.userDesc', '第三方平台的用户唯一标识（必需）')}</li>
                </ul>
              </div>

              {/* Simple Example */}
              <div>
                <p className="font-medium text-gray-800 mb-1">{t('platforms.custom.integration.simpleExample', '简单示例')}</p>
                <code className="block bg-gray-50 px-3 py-2 rounded border border-gray-200 font-mono text-xs whitespace-pre">
{`POST ${chatUrl || '{chat_url}'}
X-Platform-API-Key: ${apiKey || '{your_api_key}'}
Content-Type: application/json

{
  "messages": [{"role": "user", "content": "你好"}],
  "user": "third_party_user_123",
  "stream": false
}`}
                </code>
              </div>

              {/* Response Handling */}
              <div>
                <p className="font-medium text-gray-800 mb-1">{t('platforms.custom.integration.responseHandling', '响应处理')}</p>
                <p className="text-xs text-gray-600">{t('platforms.custom.integration.responseHandlingDesc', '调用对话接口后，TGO 系统会返回 AI 助手的回复内容。第三方平台需要将返回的回复内容发送给对应的第三方用户。响应格式与 OpenAI ChatGPT API 兼容，支持流式和非流式响应。')}</p>
              </div>
            </div>
          </details>

          {/* 2. Callback API - Receive Customer Service Replies */}
          <details className="rounded-md border border-gray-200 p-3 bg-white/70">
            <summary className="cursor-pointer font-semibold text-gray-800">{t('platforms.custom.integration.callbackApi', '回调接口说明（接收客服回复）')}</summary>
            <div className="text-sm text-gray-700 mt-3 space-y-3">
              {/* Configuration */}
              <div>
                <p className="font-medium text-gray-800 mb-1">{t('platforms.custom.integration.callbackConfig', '配置回调地址')}</p>
                <p className="text-xs text-gray-600">{t('platforms.custom.integration.callbackConfigDesc', '在左侧"回调地址"字段中配置您的回调 URL，当客服回复消息时，系统会向该地址发送 POST 请求。')}</p>
              </div>

              {/* Request Format */}
              <div>
                <p className="font-medium text-gray-800 mb-1">{t('platforms.custom.integration.requestFormat', '请求格式')}</p>
                <code className="block bg-gray-50 px-3 py-2 rounded border border-gray-200 font-mono text-xs whitespace-pre">
{`POST ${callbackUrl || '{your_callback_url}'}
Content-Type: application/json

{
  "message_id": "msg_123",
  "user": "third_party_user_123",
  "content": "客服回复的消息内容",
  "timestamp": "2024-01-01T12:00:00Z"
}`}
                </code>
              </div>

              {/* Field Descriptions */}
              <div>
                <p className="font-medium text-gray-800 mb-1">{t('platforms.custom.integration.fieldDescriptions', '字段说明')}</p>
                <ul className="list-disc list-inside text-xs text-gray-600 space-y-1">
                  <li><code className="bg-gray-100 px-1 py-0.5 rounded font-mono">message_id</code>: {t('platforms.custom.integration.messageIdDesc', '消息唯一标识')}</li>
                  <li><code className="bg-gray-100 px-1 py-0.5 rounded font-mono">user</code>: {t('platforms.custom.integration.callbackUserDesc', '第三方用户标识（与对话接口中的 user 字段对应）')}</li>
                  <li><code className="bg-gray-100 px-1 py-0.5 rounded font-mono">content</code>: {t('platforms.custom.integration.contentDesc', '客服回复的消息内容')}</li>
                  <li><code className="bg-gray-100 px-1 py-0.5 rounded font-mono">timestamp</code>: {t('platforms.custom.integration.timestampDesc', '消息时间戳（ISO 8601 格式）')}</li>
                </ul>
              </div>

              {/* Response Requirement */}
              <div>
                <p className="font-medium text-gray-800 mb-1">{t('platforms.custom.integration.responseRequirement', '响应要求')}</p>
                <p className="text-xs text-gray-600">{t('platforms.custom.integration.responseRequirementDesc', '请确保回调地址可公网访问，并返回 HTTP 200 状态码表示接收成功。')}</p>
              </div>
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

      {/* Delete Confirmation Dialog */}
      <ConfirmDialog
        isOpen={confirmOpen}
        title={t('platforms.custom.deleteTitle', '删除平台')}
        message={t('platforms.custom.deleteMessage', '确定要删除平台"{{name}}"吗？此操作无法撤销。', { name: platform.name })}
        confirmText={t('common.delete', '删除')}
        cancelText={t('common.cancel', '取消')}
        confirmVariant="danger"
        isLoading={isDeleting}
        onCancel={() => setConfirmOpen(false)}
        onConfirm={handleDelete}
      />
    </main>
  );
};

export default CustomPlatformConfig;




