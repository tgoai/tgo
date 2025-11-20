import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import ConfirmDialog from '@/components/ui/ConfirmDialog';
import type { Platform, PlatformConfig } from '@/types';
import { usePlatformStore } from '@/stores/platformStore';
import { useToast } from '@/hooks/useToast';
import { showApiError, showSuccess } from '@/utils/toastHelpers';
import platformsApiService from '@/services/platformsApi';
import { keysToSnake } from '@/utils/case';
import ImageCropModal from '@/components/ui/ImageCropModal';


interface WebsitePlatformConfigProps {
  platform: Platform;
}

// Keys we will persist in platform.config for website widget
type WebsiteWidgetConfig = {
  widgetTitle: string;
  themeColor: string;
  logoUrl: string;
  welcomeMessage: string;
  position: 'bottom-right' | 'bottom-left' | 'top-right' | 'top-left';
};

// Note: Default values will be translated at runtime using t() function
const getDefaultWebsiteConfig = (t: any): WebsiteWidgetConfig => ({
  widgetTitle: t('platforms.website.defaults.widgetTitle', '欢迎光临'),
  themeColor: '#1E40AF', // blue-800
  logoUrl: '',
  welcomeMessage: t('platforms.website.defaults.welcomeMessage', '您好！有什么可以帮您？'),
  position: 'bottom-right',
});

// Widget preview URL and origin (configurable via Vite env)
const WIDGET_PREVIEW_URL: string = (import.meta as any).env?.VITE_WIDGET_PREVIEW_URL ?? 'http://127.0.0.1:5500/tgo-widget-app/dist/index.html';
const WIDGET_PREVIEW_ORIGIN: string = (() => {
  try { return new URL(WIDGET_PREVIEW_URL, window.location.origin).origin; } catch { return '*'; }
})();

// Widget SDK script base and demo page (configurable via Vite env)
const WIDGET_SCRIPT_BASE: string = (import.meta as any).env?.VITE_WIDGET_SCRIPT_BASE || `${WIDGET_PREVIEW_ORIGIN}/tgo-widget-sdk.js`;
const WIDGET_DEMO_URL: string = (import.meta as any).env?.VITE_WIDGET_DEMO_URL || `${WIDGET_PREVIEW_ORIGIN}/demo.html`;



const WebsitePlatformConfig: React.FC<WebsitePlatformConfigProps> = ({ platform }) => {
  const { t } = useTranslation();
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const updatePlatformConfig = usePlatformStore(s => s.updatePlatformConfig);
  const resetPlatformConfig = usePlatformStore(s => s.resetPlatformConfig);
  const updatePlatform = usePlatformStore(s => s.updatePlatform);
  const fetchPlatformById = usePlatformStore(s => s.fetchPlatformById);
  const regenerateApiKey = usePlatformStore(s => s.regenerateApiKey);
  const hasConfigChanges = usePlatformStore(s => s.hasConfigChanges(platform.id));
  const isUpdating = usePlatformStore(s => s.isUpdating);
  const deletePlatform = usePlatformStore(s => s.deletePlatform);
  const enablePlatform = usePlatformStore(s => s.enablePlatform);
  const disablePlatform = usePlatformStore(s => s.disablePlatform);
  const platforms = usePlatformStore(s => s.platforms);
  const { showToast } = useToast();
  const navigate = useNavigate();
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isToggling, setIsToggling] = useState(false);
  const isEnabled = platform.status === 'connected';

  const defaultWebsiteConfig = useMemo(() => getDefaultWebsiteConfig(t), [t]);

  const initialFormValues: WebsiteWidgetConfig = useMemo(() => {
    const cfg = (platform.config || {}) as PlatformConfig as any;
    return {
      // Read both camelCase (legacy) and snake_case (backend) keys, defaulting as needed
      widgetTitle: (cfg.widgetTitle ?? cfg.widget_title) ?? defaultWebsiteConfig.widgetTitle,
      themeColor: (cfg.themeColor ?? cfg.theme_color) ?? defaultWebsiteConfig.themeColor,
      // Logo now comes from top-level platform.logo_url
      logoUrl: platform.logo_url ?? defaultWebsiteConfig.logoUrl,
      welcomeMessage: (cfg.welcomeMessage ?? cfg.welcome_message) ?? defaultWebsiteConfig.welcomeMessage,
      position: cfg.position ?? defaultWebsiteConfig.position,
    } as WebsiteWidgetConfig;
  }, [platform.config, platform.logo_url]);

  const [formValues, setFormValues] = useState<WebsiteWidgetConfig>(initialFormValues);
  const [uploadingLogo, setUploadingLogo] = useState(false);
  const apiKey: string = useMemo(() => ((platform.config as any)?.apiKey ?? ''), [platform.config]);
  // 裁剪弹窗状态
  const [cropOpen, setCropOpen] = useState(false);
  const [cropSrc, setCropSrc] = useState<string>('');
  const [pendingFile, setPendingFile] = useState<File | null>(null);

  const [showApiKey, setShowApiKey] = useState(false);
  const [embedOpen, setEmbedOpen] = useState(true);
  // Sync logo preview from top-level platform.logo_url changes
  const [previewLoaded, setPreviewLoaded] = useState(false);

  useEffect(() => {
    const url = (platform as any).logo_url || '';
    setFormValues(v => (v.logoUrl !== url ? { ...v, logoUrl: url } : v));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [platform.logo_url]);


  // Live preview: postMessage to widget iframe whenever form changes (after iframe is loaded)
  useEffect(() => {
    if (!previewLoaded) return;
    const targetOrigin = WIDGET_PREVIEW_ORIGIN;
    const win = iframeRef.current?.contentWindow;
    if (!win) return;
    win.postMessage({
      type: 'CONFIG_UPDATE',
      payload: {
        title: formValues.widgetTitle,
        themeColor: formValues.themeColor,
        logoUrl: formValues.logoUrl,
        welcomeMessage: formValues.welcomeMessage,
        position: formValues.position,
      }
    }, targetOrigin);
  }, [formValues, previewLoaded]);
  // Platform name editing
  const [platformName, setPlatformName] = useState<string>(platform.name);
  useEffect(() => { setPlatformName(platform.name); }, [platform.name]);
  const hasNameChanged = useMemo(() => platformName.trim() !== platform.name, [platformName, platform.name]);
  const canSave = hasConfigChanges || hasNameChanged;


  // Ensure platform details (incl. apiKey) are fresh
  useEffect(() => {
    if (!apiKey) {
      fetchPlatformById(platform.id).catch(() => { });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [platform.id]);

  const handleChange = (patch: Partial<WebsiteWidgetConfig>) => {
    setFormValues(v => ({ ...v, ...patch }));
    // Accumulate changes into store for Save
    updatePlatformConfig(platform.id, patch as Partial<PlatformConfig>);
  };

  const handleSave = async () => {
    try {
      if (hasConfigChanges) {
        // Build full config object from current form state (camelCase)
        const fullCamelConfig = {
          widgetTitle: (formValues.widgetTitle || '').trim(),
          themeColor: (formValues.themeColor || '').trim(),
          welcomeMessage: (formValues.welcomeMessage || '').trim(),
          position: formValues.position,
        };

        // Transform keys to snake_case for backend API
        const snakeConfig = keysToSnake(fullCamelConfig);

        await updatePlatform(platform.id, { config: snakeConfig });
        // Clear pending local camelCase changes since we sent transformed full payload
        resetPlatformConfig(platform.id);
      }
      if (hasNameChanged) {
        await updatePlatform(platform.id, { name: platformName.trim() });
      }
      showSuccess(showToast, t('platforms.website.messages.saveSuccess', '保存成功'), t('platforms.website.messages.saveSuccessMessage', '平台信息已更新'));
    } catch (e) {
      showApiError(showToast, e);
    }
  };

  const displayName = platform.display_name || platform.name;

  return (
    <main className="flex flex-col flex-1 min-h-0 bg-gradient-to-br from-gray-50 to-gray-100">
      <header className="px-6 py-4 border-b border-gray-200/80 flex justify-between items-center bg-white/60 backdrop-blur-lg sticky top-0 z-10">
        <div>
          <h2 className="text-lg font-semibold text-gray-800">{t('platforms.website.header.title', {"name":displayName})}</h2>
          <p className="text-xs text-gray-500 mt-1">{t('platforms.website.header.subtitle', '调整左侧配置，右侧预览会实时更新')}</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            disabled={isUpdating || isDeleting}
            onClick={() => setConfirmOpen(true)}
            className={`px-3 py-1.5 text-sm rounded-md ${isDeleting ? 'bg-red-400 text-white' : 'bg-red-600 text-white hover:bg-red-700'}`}
          >
            {isDeleting ? t('platforms.website.buttons.deleting', '删除中…') : t('platforms.website.buttons.delete', '删除')}
          </button>
          <button
            disabled={isUpdating || isDeleting || isToggling}
            onClick={async () => {
              if (isToggling) return;
              setIsToggling(true);
              try {
                if (isEnabled) {
                  await disablePlatform(platform.id);
                  showSuccess(showToast, t('platforms.website.messages.disabled', '平台已禁用'));
                } else {
                  await enablePlatform(platform.id);
                  showSuccess(showToast, t('platforms.website.messages.enabled', '平台已启用'));
                }
              } catch (e) {
                showApiError(showToast, e);
              } finally {
                setIsToggling(false);
              }
            }}
            className={`px-3 py-1.5 text-sm rounded-md text-white ${isEnabled ? 'bg-gray-600 hover:bg-gray-700' : 'bg-green-600 hover:bg-green-700'} ${isToggling ? 'opacity-70 cursor-not-allowed' : ''}`}
          >
            {isToggling ? (isEnabled ? t('platforms.website.buttons.disabling', '禁用中…') : t('platforms.website.buttons.enabling', '启用中…')) : (isEnabled ? t('platforms.website.buttons.disable', '禁用') : t('platforms.website.buttons.enable', '启用'))}
          </button>
          <button
            disabled={!canSave || isUpdating}
            onClick={handleSave}
            className={`px-3 py-1.5 text-sm rounded-md ${canSave ? 'bg-blue-600 text-white hover:bg-blue-700' : 'bg-gray-200 text-gray-500 cursor-not-allowed'}`}
          >
            {isUpdating ? t('platforms.website.buttons.saving', '保存中…') : t('platforms.website.buttons.save', '保存')}
          </button>
        </div>
      </header>

      <div className="flex flex-1 min-h-0 flex-col lg:flex-row gap-4 p-6">
        {/* Left: form */}
        <section className="lg:w-2/5 w-full bg-white/80 backdrop-blur-md p-5 rounded-lg shadow-sm border border-gray-200/60 space-y-4 overflow-y-auto min-h-0 auto-hide-scrollbar">
          {/* 平台名称（置于表单最上方） */}
          <div>
            <label className="block text-sm font-medium text-gray-600 mb-1">{t('platforms.website.form.name', '名称')}</label>
            <input
              type="text"
              value={platformName}
              onChange={(e) => setPlatformName(e.target.value)}
              className="w-full text-sm p-1.5 border border-gray-300/80 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500 bg-white/90"
              placeholder={t('platforms.website.form.namePlaceholder', '请输入平台名称')}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-600 mb-1">{t('platforms.website.form.widgetTitle', '访客窗口标题')}</label>
            <input
              type="text"
              value={formValues.widgetTitle}
              onChange={e => handleChange({ widgetTitle: e.target.value })}
              className="w-full text-sm p-1.5 border border-gray-300/80 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500 bg-white/90"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-600 mb-1">{t('platforms.website.form.themeColor', '主题颜色')}</label>
            <input
              type="color"
              value={formValues.themeColor}
              onChange={e => handleChange({ themeColor: e.target.value })}
              className="h-9 w-16 p-1 border border-gray-300/80 rounded-md bg-white/90"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-600 mb-1">{t('platforms.website.form.logo', 'Logo')}</label>
            <div className="flex items-start gap-4">
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="relative group w-24 h-24 md:w-28 md:h-28 border border-dashed border-gray-300 rounded-md bg-gray-50 flex items-center justify-center overflow-hidden hover:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-500/30 transition"
                aria-label={t('platforms.website.form.uploadLogo', '上传 Logo')}
              >
                {formValues.logoUrl ? (
                  <img src={formValues.logoUrl} alt="Logo" className="w-full h-full object-contain transition-opacity group-hover:opacity-80" />
                ) : (
                  <div className="flex flex-col items-center justify-center text-gray-400 text-xs">
                    <svg className="w-6 h-6 mb-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4-4 4 4 4-4 4 4M4 8h16" />
                    </svg>
                    {t('platforms.website.form.clickUpload', '点击上传')}
                  </div>
                )}
                <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 text-white text-xs flex items-center justify-center transition">{t('platforms.website.form.clickUpload', '点击上传')}</div>
              </button>
              <div className="flex-1 flex flex-col gap-2">
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  disabled={uploadingLogo}
                  onChange={async (e) => {
                    const file = e.currentTarget.files?.[0];
                    if (!file) return;
                    const MAX_SIZE = 2 * 1024 * 1024; // 2MB
                    if (file.size > MAX_SIZE) {
                      showApiError(showToast, new Error(t('platforms.website.errors.fileTooLarge', '图片大小不能超过 2MB')));
                      if (fileInputRef.current) fileInputRef.current.value = '';
                      return;
                    }
                    if (!file.type.startsWith('image/')) {
                      showApiError(showToast, new Error(t('platforms.website.errors.invalidFileType', '仅支持图片文件')));
                      if (fileInputRef.current) fileInputRef.current.value = '';
                      return;
                    }
                    try {
                      const objectUrl = URL.createObjectURL(file);
                      setCropSrc(objectUrl);
                      setPendingFile(file);
                      setCropOpen(true);
                    } catch (err) {
                      showApiError(showToast, err || new Error(t('platforms.website.errors.cropperFailed', '无法打开裁剪器')));
                      if (fileInputRef.current) fileInputRef.current.value = '';
                    }
                  }}
                  className="hidden"
                />
                {uploadingLogo && (
                  <p className="text-xs text-gray-400">{t('platforms.website.form.uploading', '上传中…')}</p>
                )}
                {formValues.logoUrl && (
                  <div className="flex gap-2">
                    <button
                      type="button"
                      className="px-2 py-1 text-xs rounded-md bg-gray-100 hover:bg-gray-200 text-gray-700"
                      onClick={async () => {
                        try {
                          setUploadingLogo(true);
                          await platformsApiService.updatePlatform(platform.id, { logo_url: null } as any);
                          await fetchPlatformById(platform.id);
                          setFormValues(v => ({ ...v, logoUrl: '' }));
                          showSuccess(showToast, t('platforms.website.messages.logoRemoved', '已移除'), t('platforms.website.messages.logoRemovedMessage', 'Logo 已清除'));
                        } catch (err) {
                          showApiError(showToast, err || new Error(t('platforms.website.errors.removeLogoFailed', '暂不支持移除 Logo，请上传新的图片覆盖')));
                        } finally {
                          setUploadingLogo(false);
                        }
                      }}
                    >
                      {t('platforms.website.buttons.remove', '移除')}
                    </button>
                  </div>
                )}
                <p className="text-xs text-gray-600">{t('platforms.website.form.logoHint', '建议尺寸：72x72 像素。支持 PNG/JPG/SVG，最大 2MB。')}</p>
              </div>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-600 mb-1">{t('platforms.website.form.welcomeMessage', '欢迎语')}</label>
            <textarea
              rows={3}
              value={formValues.welcomeMessage}
              onChange={e => handleChange({ welcomeMessage: e.target.value })}
              className="w-full text-sm p-1.5 border border-gray-300/80 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500 bg-white/90 resize-none"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-600 mb-1">{t('platforms.website.form.position', '位置')}</label>
            <select
              value={formValues.position}
              onChange={e => handleChange({ position: e.target.value as WebsiteWidgetConfig['position'] })}
              className="w-full text-sm p-1.5 border border-gray-300/80 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500 bg-white/90"
            >
              <option value="bottom-right">{t('platforms.website.form.positionBottomRight', '右下角')}</option>
              <option value="bottom-left">{t('platforms.website.form.positionBottomLeft', '左下角')}</option>
              <option value="top-right">{t('platforms.website.form.positionTopRight', '右上角')}</option>
              <option value="top-left">{t('platforms.website.form.positionTopLeft', '左上角')}</option>
            </select>
          </div>

          {/* API Key（移动到主表单，位置字段之后） */}
          <div>
            <label className="block text-sm font-medium text-gray-600 mb-1">{t('platforms.website.form.apiKey', 'API Key')}</label>
            <div className="flex flex-wrap items-center gap-2">
              <input
                type={showApiKey ? 'text' : 'password'}
                readOnly
                value={apiKey || ''}
                placeholder={apiKey ? '' : t('platforms.website.form.noApiKey', '暂无 API Key')}
                className="flex-1 min-w-[160px] text-sm p-1.5 border border-gray-300/80 rounded-md bg-gray-50"
              />
              <button
                type="button"
                className="px-2 py-1 text-xs rounded-md bg-gray-100 hover:bg-gray-200 text-gray-700"
                onClick={() => setShowApiKey(v => !v)}
              >
                {showApiKey ? t('platforms.website.buttons.hide', '隐藏') : t('platforms.website.buttons.show', '显示')}
              </button>
              <button
                type="button"
                className="px-2 py-1 text-xs rounded-md bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
                onClick={async () => {
                  if (!apiKey) return;
                  try { await navigator.clipboard.writeText(apiKey); showSuccess(showToast, t('platforms.website.messages.copied', '已复制'), t('platforms.website.messages.apiKeyCopied', 'API Key 已复制到剪贴板')); }
                  catch (e) { showApiError(showToast, e); }
                }}
                disabled={!apiKey}
              >
                {t('platforms.website.buttons.copy', '复制')}
              </button>
              <button
                type="button"
                className="px-2 py-1 text-xs rounded-md bg-amber-500 text-white hover:bg-amber-600 disabled:opacity-50"
                onClick={async () => {
                  try {
                    if (!confirm(t('platforms.website.confirm.regenerateApiKey', '确定要重新生成 API Key 吗？现有嵌入脚本将需要更新。'))) return;
                    await regenerateApiKey(platform.id);
                    showSuccess(showToast, t('platforms.website.messages.updated', '已更新'), t('platforms.website.messages.apiKeyRegenerated', 'API Key 已重新生成'));
                  } catch (e) {
                    showApiError(showToast, e);
                  }
                }}
              >
                {t('platforms.website.buttons.regenerate', '重新生成')}
              </button>
            </div>
            <p className="text-xs text-gray-500 mt-1">{t('platforms.website.form.apiKeyHint', '用于网站集成脚本的鉴权标识，请妥善保管。')}</p>
          </div>



        </section>

        {/* Right: preview */}
        <section className="lg:w-3/5 w-full bg-white/80 backdrop-blur-md p-0 rounded-lg shadow-sm border border-gray-200/60 flex min-h-0">
          <iframe
            ref={iframeRef}
            src={WIDGET_PREVIEW_URL}
            onLoad={() => setPreviewLoaded(true)}
            title="Widget Preview"
            sandbox="allow-scripts allow-same-origin"
            className="w-full h-full rounded-lg"
          />
        </section>
      </div>
      {/* Embed code section (bottom, collapsible) */}
      <section className="px-6 pb-6">
        <div className="bg-white/80 backdrop-blur-md rounded-lg shadow-sm border border-gray-200/60 overflow-hidden">
          <button
            type="button"
            className="w-full px-5 py-3 flex items-center justify-between hover:bg-gray-50/50 transition-colors"
            onClick={() => setEmbedOpen(v => !v)}
          >
            <h3 className="text-md font-semibold text-gray-700">{t('platforms.website.embed.title', '网站集成代码')}</h3>
            <svg className={`w-5 h-5 text-gray-500 transition-transform ${embedOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>
          {embedOpen && (
            <div className="px-5 pb-5 pt-2 space-y-4">
              {/* 嵌入代码 */}
              <p className="text-xs text-gray-500" dangerouslySetInnerHTML={{ __html: t('platforms.website.embed.instruction', '将以下代码复制并粘贴到您网站的 <code>&lt;head&gt;</code> 或 <code>&lt;body&gt;</code> 中：') }} />
              {(() => {
                const snippet = `<script src="${WIDGET_SCRIPT_BASE}?api_key=${apiKey}" async></script>`;
                const demoUrl = `${WIDGET_DEMO_URL}${apiKey ? `?api_key=${encodeURIComponent(apiKey)}` : ''}`;
                return (
                  <div className="relative">
                    <pre className="text-xs bg-gray-50 border border-gray-200 rounded-md p-3 overflow-x-auto whitespace-pre-wrap">{snippet}</pre>
                    <div className="absolute top-2 right-2 flex gap-2">
                      <a
                        href={demoUrl}
                        target="_blank"
                        rel="noreferrer"
                        onClick={(e) => { if (!apiKey) { e.preventDefault(); } }}
                        className={`px-2 py-1 text-xs rounded ${apiKey ? 'bg-green-600 text-white hover:bg-green-700' : 'bg-gray-200 text-gray-500 cursor-not-allowed'}`}
                      >
                        {t('platforms.website.buttons.testIntegration', '测试集成')}
                      </a>
                      <button
                        type="button"
                        className="px-2 py-1 text-xs rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
                        onClick={async () => {
                          try { await navigator.clipboard.writeText(snippet); showSuccess(showToast, t('platforms.website.messages.copied', '已复制'), t('platforms.website.messages.embedCodeCopied', '嵌入代码已复制到剪贴板')); } catch (e) { showApiError(showToast, e); }
                        }}
                        disabled={!apiKey}
                      >
                        {t('platforms.website.buttons.copy', '复制')}
                      </button>
                    </div>
                  </div>
                );

              })()}
            </div>
          )}
        </div>
      </section>
      <style>{`
        .auto-hide-scrollbar { scrollbar-width: thin; scrollbar-color: rgba(0,0,0,0.3) transparent; }
        .auto-hide-scrollbar::-webkit-scrollbar { width: 8px; height: 8px; }
        .auto-hide-scrollbar::-webkit-scrollbar-thumb { background-color: transparent; border-radius: 4px; }
        .auto-hide-scrollbar:hover::-webkit-scrollbar-thumb { background-color: rgba(0,0,0,0.35); }
      `}</style>


      <ImageCropModal
        isOpen={cropOpen}
        imageSrc={cropSrc}
        onCancel={() => {
          setCropOpen(false);
          if (fileInputRef.current) fileInputRef.current.value = '';
          if (cropSrc) URL.revokeObjectURL(cropSrc);
          setCropSrc('');
          setPendingFile(null);
        }}
        onConfirm={async (blob: Blob, dataUrl: string) => {
          try {
            setUploadingLogo(true);
            // 本地预览裁剪后的结果
            setFormValues(v => ({ ...v, logoUrl: dataUrl }));
            // 从 Blob 构建 File
            const mime = pendingFile?.type || 'image/png';
            const ext = mime === 'image/jpeg' ? 'jpg' : (mime.split('/')[1] || 'png');
            const croppedFile = new File([blob], `logo-cropped.${ext}`, { type: mime });
            // 通过专用接口上传
            const resp = await platformsApiService.uploadPlatformLogo(platform.id, croppedFile);
            setFormValues(v => ({ ...v, logoUrl: (resp as any).logo_url || dataUrl }));
            await fetchPlatformById(platform.id);
            showSuccess(showToast, t('platforms.website.messages.uploadSuccess', '上传成功'), t('platforms.website.messages.logoUpdated', 'Logo 已更新'));
          } catch (err) {
            showApiError(showToast, err || new Error(t('platforms.website.errors.uploadFailed', '上传失败，请重试')));
          } finally {
            setUploadingLogo(false);
            setCropOpen(false);
            if (fileInputRef.current) fileInputRef.current.value = '';
            if (cropSrc) URL.revokeObjectURL(cropSrc);
            setCropSrc('');
            setPendingFile(null);
          }
        }}
      />

      <ConfirmDialog
        isOpen={confirmOpen}
        title={t('platforms.website.confirm.deleteTitle', '删除平台')}
        message={t('platforms.website.confirm.deleteMessage', '确定要删除此平台吗？')}
        confirmText={t('platforms.website.confirm.confirmText', '删除')}
        cancelText={t('platforms.website.confirm.cancelText', '取消')}
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
            showSuccess(showToast, t('platforms.website.messages.deleteSuccess', '平台已删除'), t('platforms.website.messages.deleteSuccessMessage', '平台已删除'));
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

export default WebsitePlatformConfig;
