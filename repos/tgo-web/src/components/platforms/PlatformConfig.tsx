import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Webhook, Copy, Eye, EyeOff, RefreshCw, Settings, Pencil } from 'lucide-react';
import type { Platform, PlatformConfig as PlatformConfigType } from '@/types';

interface BasicSettingsProps {
  platform: Platform;
  onUpdate?: (platform: Platform) => void;
}

/**
 * Basic settings section component
 */
const BasicSettings: React.FC<BasicSettingsProps> = ({ platform, onUpdate }) => {
  const { t } = useTranslation();
  const [name, setName] = useState<string>(platform?.name || '');
  const [description, setDescription] = useState<string>(platform?.description || '');

  const handleNameChange = (e: React.ChangeEvent<HTMLInputElement>): void => {
    const newName = e.target.value;
    setName(newName);
    onUpdate?.({ ...platform, name: newName });
  };

  const handleDescriptionChange = (e: React.ChangeEvent<HTMLTextAreaElement>): void => {
    const newDescription = e.target.value;
    setDescription(newDescription);
    onUpdate?.({ ...platform, description: newDescription });
  };

  return (
    <div className="bg-white/80 backdrop-blur-md p-5 rounded-lg shadow-sm border border-gray-200/60 w-full">
      <h3 className="text-md font-semibold text-gray-700 mb-4">
        {t('platforms.config.basic.title', '基础设置')}
      </h3>
      <div className="space-y-4">
        <div>
          <label htmlFor="platform-name" className="block text-sm font-medium text-gray-600 mb-1">
            {t('platforms.config.basic.platformName', '平台名称')}
          </label>
          <input
            type="text"
            id="platform-name"
            value={name}
            onChange={handleNameChange}
            className="w-full text-sm p-1.5 border border-gray-300/80 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500 bg-white/90"
          />
        </div>
        <div>
          <label htmlFor="platform-desc" className="block text-sm font-medium text-gray-600 mb-1">
            {t('platforms.config.basic.platformDesc', '平台描述 (可选)')}
          </label>
          <textarea
            id="platform-desc"
            rows={2}
            value={description}
            onChange={handleDescriptionChange}
            placeholder={t('platforms.config.basic.descPlaceholder', '描述此平台的用途')}
            className="w-full text-sm p-1.5 border border-gray-300/80 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500 bg-white/90 resize-none"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-600 mb-1">
            {t('platforms.config.basic.platformIcon', '平台图标')}
          </label>
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 p-1.5 rounded border border-gray-300/80 bg-gray-100/50 text-gray-500 flex items-center justify-center">
              <Webhook className="w-4 h-4" />
            </div>
            <button className="text-xs text-blue-600 hover:underline">
              {t('platforms.config.basic.selectUploadIcon', '选择/上传图标')}
            </button>
          </div>
          <p className="text-xs text-gray-500 mt-1">
            {t('platforms.config.basic.iconHint', '选择一个图标在平台列表中展示。')}
          </p>
        </div>
      </div>
    </div>
  );
};

interface WebhookIncomingProps {
  config: PlatformConfigType;
  onUpdate?: (config: PlatformConfigType) => void;
}

/**
 * Webhook incoming section component
 */
const WebhookIncoming: React.FC<WebhookIncomingProps> = ({ config, onUpdate }) => {
  const { t } = useTranslation();
  const [showSecret, setShowSecret] = useState<boolean>(false);
  
  const webhookUrl = config?.webhookUrl || 'https://api.example.com/webhook/ch_abc123xyz';
  const secretKey = config?.secretKey || 'sk_test_1234567890abcdef';

  const handleCopy = (text: string): void => {
    navigator.clipboard.writeText(text);
    // TODO: Show toast notification
    console.log('Copied to clipboard:', text);
  };

  const handleRegenerateSecret = (): void => {
    const newSecret = 'sk_test_' + Math.random().toString(36).substring(2, 15);
    onUpdate?.({ ...config, secretKey: newSecret });
    console.log('Secret regenerated');
  };

  return (
    <div className="bg-white/80 backdrop-blur-md p-5 rounded-lg shadow-sm border border-gray-200/60 w-full">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-md font-semibold text-gray-700">
          {t('platforms.config.webhookIncoming.title', 'Webhook 接入 (接收消息)')}
        </h3>
        <button className="text-xs text-blue-600 hover:underline">
          {t('platforms.config.webhookIncoming.viewDocs', '查看接入文档')}
        </button>
      </div>
      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-600 mb-1">Webhook URL</label>
          <div className="flex items-center space-x-2">
            <input
              type="text"
              readOnly
              value={webhookUrl}
              className="flex-grow text-sm p-1.5 border border-gray-300/80 rounded-md bg-gray-100/70 focus:outline-none font-mono"
            />
            <button
              className="p-1.5 text-gray-500 hover:bg-gray-200/70 rounded-md"
              title={t('platforms.config.webhookIncoming.copyUrl', '复制URL')}
              onClick={() => handleCopy(webhookUrl)}
            >
              <Copy className="w-4 h-4" />
            </button>
          </div>
          <p className="text-xs text-gray-500 mt-1">
            {t('platforms.config.webhookIncoming.urlHint', '将此 URL 配置到您的系统中，用于接收来自您系统的消息。')}
          </p>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-600 mb-1">Secret Key</label>
          <div className="flex items-center space-x-2">
            <input
              type={showSecret ? 'text' : 'password'}
              readOnly
              value={showSecret ? secretKey : '**********'}
              className="flex-grow text-sm p-1.5 border border-gray-300/80 rounded-md bg-gray-100/70 focus:outline-none font-mono"
            />
            <button
              className="p-1.5 text-gray-500 hover:bg-gray-200/70 rounded-md"
              title={t('platforms.config.webhookIncoming.toggleSecret', '显示/隐藏密钥')}
              onClick={() => setShowSecret(!showSecret)}
            >
              {showSecret ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
            <button
              className="p-1.5 text-gray-500 hover:bg-gray-200/70 rounded-md"
              title={t('platforms.config.webhookIncoming.copySecret', '复制密钥')}
              onClick={() => handleCopy(secretKey)}
            >
              <Copy className="w-4 h-4" />
            </button>
            <button
              className="p-1.5 text-red-500 hover:bg-red-100/70 rounded-md"
              title={t('platforms.config.webhookIncoming.regenerateSecret', '重新生成密钥')}
              onClick={handleRegenerateSecret}
            >
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>
          <p className="text-xs text-gray-500 mt-1">
            {t('platforms.config.webhookIncoming.secretHint', '用于验证传入请求的签名，确保安全性。')}
          </p>
        </div>
      </div>
    </div>
  );
};

interface WebhookOutgoingProps {
  config: PlatformConfigType;
  onUpdate?: (config: PlatformConfigType) => void;
}

/**
 * Webhook outgoing section component
 */
const WebhookOutgoing: React.FC<WebhookOutgoingProps> = ({ config, onUpdate }) => {
  const { t } = useTranslation();
  const [outgoingUrl, setOutgoingUrl] = useState<string>(config?.outgoingUrl || '');
  const [outgoingToken, setOutgoingToken] = useState<string>(config?.outgoingToken || '');

  const handleUrlChange = (e: React.ChangeEvent<HTMLInputElement>): void => {
    const newUrl = e.target.value;
    setOutgoingUrl(newUrl);
    onUpdate?.({ ...config, outgoingUrl: newUrl });
  };

  const handleTokenChange = (e: React.ChangeEvent<HTMLInputElement>): void => {
    const newToken = e.target.value;
    setOutgoingToken(newToken);
    onUpdate?.({ ...config, outgoingToken: newToken });
  };

  return (
    <div className="bg-white/80 backdrop-blur-md p-5 rounded-lg shadow-sm border border-gray-200/60 w-full">
      <h3 className="text-md font-semibold text-gray-700 mb-4">
        {t('platforms.config.webhookOutgoing.title', 'Webhook 推送 (发送消息)')}
      </h3>
      <div className="space-y-4">
        <div>
          <label htmlFor="outgoing-url" className="block text-sm font-medium text-gray-600 mb-1">
            {t('platforms.config.webhookOutgoing.yourUrl', '您的接收 URL')}
          </label>
          <input
            type="url"
            id="outgoing-url"
            value={outgoingUrl}
            onChange={handleUrlChange}
            placeholder="https://your.system.com/receive_message"
            className="w-full text-sm p-1.5 border border-gray-300/80 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500 bg-white/90"
          />
          <p className="text-xs text-gray-500 mt-1">
            {t('platforms.config.webhookOutgoing.urlHint', '当客服回复时，我们会将消息 POST 到此 URL。')}
          </p>
        </div>
        <div>
          <label htmlFor="outgoing-token" className="block text-sm font-medium text-gray-600 mb-1">
            {t('platforms.config.webhookOutgoing.authToken', '认证 Token (可选)')}
          </label>
          <input
            type="text"
            id="outgoing-token"
            value={outgoingToken}
            onChange={handleTokenChange}
            placeholder={t('platforms.config.webhookOutgoing.tokenPlaceholder', '例如：Bearer your_secret_token')}
            className="w-full text-sm p-1.5 border border-gray-300/80 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500 bg-white/90"
          />
          <p className="text-xs text-gray-500 mt-1">
            {t('platforms.config.webhookOutgoing.tokenHint', '如果您的接收 URL 需要认证，请在此处填写（例如 Authorization Header 的值）。')}
          </p>
        </div>
      </div>
    </div>
  );
};

/**
 * API access section component (placeholder)
 */
const ApiAccess: React.FC = () => {
  const { t } = useTranslation();
  return (
    <div className="bg-white/80 backdrop-blur-md p-5 rounded-lg shadow-sm border border-gray-200/60 opacity-60 w-full">
      <h3 className="text-md font-semibold text-gray-700 mb-4">
        {t('platforms.config.apiAccess.title', 'API 接入 (可选)')}
      </h3>
      <div className="text-sm text-gray-500">
        <p>{t('platforms.config.apiAccess.placeholder', '[API Key/Secret 管理和文档链接占位符]')}</p>
        <p className="mt-2">
          {t('platforms.config.apiAccess.description', '或者，您也可以通过调用我们的开放 API 来发送和接收消息。请参考开发者文档了解详情。')}
        </p>
      </div>
    </div>
  );
};

interface PlatformConfigProps {
  platform?: Platform;
  onUpdate?: (platform: Platform) => void;
  onToggle?: (platform: Platform) => void;
}

/**
 * Platform configuration main component
 */
const PlatformConfig: React.FC<PlatformConfigProps> = ({ platform, onUpdate, onToggle }) => {
  const { t } = useTranslation();

  if (!platform) {
    return (
      <main className="flex-grow flex items-center justify-center bg-gradient-to-br from-gray-50 to-gray-100">
        <div className="text-center text-gray-500">
          <Settings className="mx-auto mb-4 w-12 h-12 text-gray-300" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">
            {t('platforms.config.placeholder.title', '选择平台')}
          </h3>
          <p>{t('platforms.config.placeholder.description', '请从左侧列表中选择一个平台进行配置')}</p>
        </div>
      </main>
    );
  }

  const isEnabled = platform.status === 'connected';

  const displayName = platform.display_name || platform.name;

  return (
    <main className="flex-grow flex flex-col bg-gradient-to-br from-gray-50 to-gray-100">
      {/* Header */}
      <header className="px-6 py-4 border-b border-gray-200/80 flex justify-between items-center bg-white/60 backdrop-blur-lg sticky top-0 z-10">
        <div className="flex items-center space-x-3">
          <Webhook className="w-6 h-6 text-purple-600" />
          <h2 className="text-lg font-semibold text-gray-800">
            {t('platforms.config.header.title', '{{name}} 配置', { name: displayName })}
          </h2>
        </div>
        <div className="flex items-center space-x-3">
          <button className="text-sm text-gray-600 hover:text-blue-600 flex items-center">
            <Pencil className="w-4 h-4 mr-1" />
            {t('common.edit', '编辑')}
          </button>
          {/* Toggle Switch */}
          <button
            role="switch"
            aria-checked={isEnabled}
            className={`relative inline-flex items-center h-6 rounded-full w-11 transition-colors ${
              isEnabled ? 'bg-blue-500' : 'bg-gray-300'
            }`}
            onClick={() => onToggle?.(platform)}
          >
            <span className="sr-only">{t('platforms.config.header.enablePlatform', '启用平台')}</span>
            <span className={`inline-block w-4 h-4 transform bg-white rounded-full transition-transform ${
              isEnabled ? 'translate-x-6' : 'translate-x-1'
            }`}></span>
          </button>
        </div>
      </header>

      {/* Content Area */}
      <div className="flex-grow overflow-y-auto p-6 space-y-6" style={{ height: 0 }}>
        <BasicSettings platform={platform} onUpdate={onUpdate} />

        {platform.type === 'custom' && (
          <>
            <WebhookIncoming config={platform.config} onUpdate={(config) => onUpdate?.({ ...platform, config })} />
            <WebhookOutgoing config={platform.config} onUpdate={(config) => onUpdate?.({ ...platform, config })} />
            <ApiAccess />
          </>
        )}

        {platform.type !== 'custom' && (
          <div className="bg-white/80 backdrop-blur-md p-5 rounded-lg shadow-sm border border-gray-200/60 w-full">
            <h3 className="text-md font-semibold text-gray-700 mb-4">
              {t('platforms.config.generic.title', '平台配置')}
            </h3>
            <div className="text-sm text-gray-500">
              <p>{t('platforms.config.generic.comingSoon', '此平台的具体配置选项将在后续版本中提供。')}</p>
              <p className="mt-2">
                {t('platforms.config.generic.currentStatus', '当前状态：{{status}}', { status: platform.statusText })}
              </p>
            </div>
          </div>
        )}
      </div>
    </main>
  );
};

export default PlatformConfig;

