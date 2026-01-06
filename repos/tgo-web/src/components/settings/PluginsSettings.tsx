import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { 
  Puzzle, RefreshCcw, Info, 
  XCircle, Plus, Trash2, Play, Square, RotateCw, Terminal, 
  Github, Download, Key, Copy, Check, ExternalLink, Cpu, Box
} from 'lucide-react';
import { usePluginStore } from '@/stores/pluginStore';
import { useAuthStore } from '@/stores/authStore';
import { formatRelativeTime } from '@/utils/dateUtils';
import type { InstalledPluginInfo } from '@/types/plugin';

const PluginsSettings: React.FC = () => {
  const { t } = useTranslation();
  const { user } = useAuthStore();
  const { 
    installedPlugins, 
    isLoadingInstalled,
    fetchInstalledPlugins,
    uninstallPlugin,
    startPlugin,
    stopPlugin,
    restartPlugin,
    installPlugin,
    fetchPluginInfo,
    getPluginLogs,
    generateDevToken
  } = usePluginStore();

  const [showInstallModal, setShowInstallModal] = useState(false);
  const [installStep, setInstallStep] = useState<1 | 2>(1);
  const [pluginUrl, setPluginUrl] = useState('');
  const [fetchedPluginInfo, setFetchedPluginInfo] = useState<any>(null);
  const [isFetchingInfo, setIsFetchingInfo] = useState(false);
  const [installError, setInstallError] = useState<string | null>(null);
  
  const [showTokenModal, setShowTokenModal] = useState(false);
  const [yamlConfig, setYamlConfig] = useState('');
  const [isInstalling, setIsInstalling] = useState(false);
  const [showManualMode, setShowManualMode] = useState(false);
  const [showLogsPluginId, setShowLogsPluginId] = useState<string | null>(null);
  const [showDetailPlugin, setShowDetailPlugin] = useState<InstalledPluginInfo | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [devToken, setDevToken] = useState<string | null>(null);
  const [isGeneratingToken, setIsGeneratingToken] = useState(false);
  const [copied, setCopied] = useState(false);
  const [processingPlugins, setProcessingPlugins] = useState<Record<string, string | null>>({});

  useEffect(() => {
    fetchInstalledPlugins();
  }, [fetchInstalledPlugins]);

  const handlePluginAction = async (pluginId: string, action: 'start' | 'stop' | 'restart' | 'uninstall') => {
    if (action === 'uninstall') {
      if (!confirm(t('settings.plugins.actions.uninstallConfirm', '确定要卸载此插件吗？此操作不可恢复。'))) {
        return;
      }
    }
    
    setProcessingPlugins(prev => ({ ...prev, [pluginId]: action }));
    try {
      switch (action) {
        case 'start': await startPlugin(pluginId); break;
        case 'stop': await stopPlugin(pluginId); break;
        case 'restart': await restartPlugin(pluginId); break;
        case 'uninstall': await uninstallPlugin(pluginId); break;
      }
    } catch (error) {
      console.error(`Action ${action} failed for plugin ${pluginId}:`, error);
    } finally {
      setProcessingPlugins(prev => ({ ...prev, [pluginId]: null }));
    }
  };

  const handleFetchInfo = async () => {
    if (!pluginUrl.trim()) return;
    setIsFetchingInfo(true);
    setInstallError(null);
    try {
      const info = await fetchPluginInfo(pluginUrl);
      setFetchedPluginInfo(info);
      setInstallStep(2);
    } catch (error: any) {
      // Handle structured API error
      const message = error.getUserMessage?.() || 
                      error.response?.data?.error?.message || 
                      error.response?.data?.detail || 
                      error.message || 
                      t('settings.plugins.fetch.error', '无法获取插件信息，请检查 URL 是否正确。');
      setInstallError(message);
    } finally {
      setIsFetchingInfo(false);
    }
  };

  const handleInstall = async () => {
    setIsInstalling(true);
    setInstallError(null);
    try {
      if (showManualMode) {
        if (!yamlConfig.trim()) return;
        await installPlugin(yamlConfig);
        setYamlConfig('');
        setShowManualMode(false);
      } else {
        if (!fetchedPluginInfo) return;
        await installPlugin(fetchedPluginInfo);
        setPluginUrl('');
        setFetchedPluginInfo(null);
        setInstallStep(1);
      }
      setShowInstallModal(false);
    } catch (error: any) {
      // Handle structured API error
      const message = error.getUserMessage?.() || 
                      error.response?.data?.error?.message || 
                      error.response?.data?.detail || 
                      error.message || 
                      t('settings.plugins.install.error', '安装失败');
      setInstallError(message);
    } finally {
      setIsInstalling(false);
    }
  };

  const handleGenerateToken = async () => {
    if (!user?.project_id) return;
    setIsGeneratingToken(true);
    try {
      const { token } = await generateDevToken(user.project_id);
      setDevToken(token);
      setShowTokenModal(true);
    } catch (error) {
      alert(t('settings.plugins.token.error', '生成令牌失败'));
    } finally {
      setIsGeneratingToken(false);
    }
  };

  const handleCopyToken = () => {
    if (devToken) {
      navigator.clipboard.writeText(devToken);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleShowLogs = async (pluginId: string) => {
    setShowLogsPluginId(pluginId);
    const pluginLogs = await getPluginLogs(pluginId);
    setLogs(pluginLogs);
  };

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Puzzle className="w-6 h-6 text-blue-600" />
          <div>
            <h1 className="text-2xl font-semibold text-gray-800 dark:text-gray-100">
              {t('settings.plugins.title', '插件管理')}
            </h1>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
              {t('settings.plugins.subtitle', '查看并管理已连接或已安装的插件')}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleGenerateToken}
            disabled={isGeneratingToken}
            className="flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-blue-700 bg-blue-50 border border-blue-200 rounded-md hover:bg-blue-100 dark:bg-blue-900/20 dark:text-blue-300 dark:border-blue-800/50 transition-colors"
          >
            {isGeneratingToken ? <RefreshCcw className="w-4 h-4 animate-spin" /> : <Key className="w-4 h-4" />}
            {t('settings.plugins.token.generate', '调试令牌')}
          </button>
          <button
            onClick={() => setShowInstallModal(true)}
            className="flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 transition-colors"
          >
            <Plus className="w-4 h-4" />
            {t('settings.plugins.install.button', '安装插件')}
          </button>
          <button
            onClick={() => {
              fetchInstalledPlugins();
            }}
            disabled={isLoadingInstalled}
            className="flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50 dark:bg-gray-800 dark:text-gray-200 dark:border-gray-600 dark:hover:bg-gray-700 transition-colors"
          >
            <RefreshCcw className={`w-4 h-4 ${isLoadingInstalled ? 'animate-spin' : ''}`} />
            {t('common.refresh', '刷新')}
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
        {isLoadingInstalled && installedPlugins.length === 0 ? (
          <div className="p-12 flex flex-col items-center justify-center text-gray-500">
            <RefreshCcw className="w-8 h-8 animate-spin mb-4" />
            <p>{t('common.loading', '加载中...')}</p>
          </div>
        ) : installedPlugins.length === 0 ? (
          <div className="p-12 flex flex-col items-center justify-center text-gray-500 text-center">
            <Plus className="w-12 h-12 mb-4 opacity-20" />
            <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-1">
              {t('settings.plugins.installed.empty.title', '暂无插件')}
            </h3>
            <p className="max-w-xs text-sm">
              {t('settings.plugins.installed.empty.description', '您可以从 GitHub 源码编译安装、通过二进制文件安装，或使用调试令牌连接本地插件。')}
            </p>
            <button
              onClick={() => setShowInstallModal(true)}
              className="mt-4 text-blue-600 hover:underline text-sm font-medium"
            >
              {t('settings.plugins.install.now', '立即安装')}
            </button>
          </div>
        ) : (
          <div className="divide-y divide-gray-200 dark:divide-gray-700">
            {installedPlugins.map((plugin) => (
              <div key={plugin.plugin_id} className="p-6 hover:bg-gray-50 dark:hover:bg-gray-900/50 transition-colors">
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-4">
                    <div className={`w-12 h-12 rounded-lg flex items-center justify-center ${
                      plugin.is_dev_mode ? 'bg-amber-50 text-amber-600 dark:bg-amber-900/20' :
                      plugin.install_type === 'github' ? 'bg-purple-50 text-purple-600 dark:bg-purple-900/20' : 
                      'bg-green-50 text-green-600 dark:bg-green-900/20'
                    }`}>
                      {plugin.is_dev_mode ? <Terminal className="w-6 h-6" /> :
                       plugin.install_type === 'github' ? <Github className="w-6 h-6" /> : 
                       <Download className="w-6 h-6" />}
                    </div>
                    <div>
                      <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-2">
                        {plugin.name}
                        <span className="px-2 py-0.5 text-xs font-normal bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 rounded">
                          v{plugin.version}
                        </span>
                        {plugin.is_dev_mode && (
                          <span className="px-2 py-0.5 text-[10px] font-bold bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400 rounded uppercase tracking-wider">
                            {t('settings.plugins.debug.badge', '调试')}
                          </span>
                        )}
                      </h3>
                      <div className="flex items-center gap-3 mt-0.5">
                        <p className="text-xs text-mono font-mono text-gray-500 dark:text-gray-400">
                          {plugin.plugin_id}
                        </p>
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                          plugin.status === 'running' ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400' :
                          plugin.status === 'error' ? 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400' :
                          plugin.status === 'installing' ? 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400' :
                          'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300'
                        }`}>
                          {plugin.status === 'running' && plugin.is_dev_mode ? t('settings.plugins.status.connected', '已连接') : plugin.status}
                        </span>
                      </div>
                    </div>
                  </div>
                  
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => setShowDetailPlugin(plugin)}
                      className="p-2 text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded-md"
                      title={t('settings.plugins.actions.detail', '查看详情')}
                    >
                      <ExternalLink className="w-4 h-4" />
                    </button>

                    {!plugin.is_dev_mode && (
                      <>
                        <button
                          onClick={() => handleShowLogs(plugin.plugin_id)}
                          className="p-2 text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-md"
                          title={t('settings.plugins.actions.logs', '查看日志')}
                        >
                          <Terminal className="w-4 h-4" />
                        </button>
                        
                        {plugin.status === 'running' ? (
                          <button
                            onClick={() => handlePluginAction(plugin.plugin_id, 'stop')}
                            disabled={!!processingPlugins[plugin.plugin_id]}
                            className="p-2 text-orange-600 hover:bg-orange-50 dark:hover:bg-orange-900/20 rounded-md disabled:opacity-50"
                            title={t('settings.plugins.actions.stop', '停止')}
                          >
                            {processingPlugins[plugin.plugin_id] === 'stop' ? (
                              <RefreshCcw className="w-4 h-4 animate-spin" />
                            ) : (
                              <Square className="w-4 h-4 fill-current" />
                            )}
                          </button>
                        ) : (
                          <button
                            onClick={() => handlePluginAction(plugin.plugin_id, 'start')}
                            disabled={plugin.status === 'installing' || !!processingPlugins[plugin.plugin_id]}
                            className="p-2 text-green-600 hover:bg-green-50 dark:hover:bg-green-900/20 rounded-md disabled:opacity-50"
                            title={t('settings.plugins.actions.start', '启动')}
                          >
                            {processingPlugins[plugin.plugin_id] === 'start' ? (
                              <RefreshCcw className="w-4 h-4 animate-spin" />
                            ) : (
                              <Play className="w-4 h-4 fill-current" />
                            )}
                          </button>
                        )}
                        
                        <button
                          onClick={() => handlePluginAction(plugin.plugin_id, 'restart')}
                          disabled={plugin.status === 'installing' || !!processingPlugins[plugin.plugin_id]}
                          className="p-2 text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded-md disabled:opacity-50"
                          title={t('settings.plugins.actions.restart', '重启')}
                        >
                          <RotateCw className={`w-4 h-4 ${processingPlugins[plugin.plugin_id] === 'restart' ? 'animate-spin' : ''}`} />
                        </button>
                        
                        <button
                          onClick={() => handlePluginAction(plugin.plugin_id, 'uninstall')}
                          disabled={!!processingPlugins[plugin.plugin_id]}
                          className="p-2 text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-md disabled:opacity-50"
                          title={t('settings.plugins.actions.uninstall', '卸载')}
                        >
                          {processingPlugins[plugin.plugin_id] === 'uninstall' ? (
                            <RefreshCcw className="w-4 h-4 animate-spin" />
                          ) : (
                            <Trash2 className="w-4 h-4" />
                          )}
                        </button>
                      </>
                    )}
                    {plugin.is_dev_mode && (
                      <span className="text-xs text-gray-400 px-2 italic">
                        {t('settings.plugins.debug.autoManaged', '调试模式 - 自动管理')}
                      </span>
                    )}
                  </div>
                </div>

                {plugin.last_error && plugin.status === 'error' && (
                  <div className="mt-3 ml-16 p-2 bg-red-50 dark:bg-red-900/10 border border-red-100 dark:border-red-900/20 rounded text-xs text-red-700 dark:text-red-400 font-mono overflow-auto max-h-24">
                    {plugin.last_error}
                  </div>
                )}

                <div className="mt-4 ml-16 flex items-center gap-6 text-xs text-gray-500">
                  <div className="flex items-center gap-1">
                    <span>{plugin.is_dev_mode ? t('settings.plugins.connectedAt', '连接于') : t('settings.plugins.installedAt', '安装于')}:</span>
                    <span className="text-gray-700 dark:text-gray-300 font-medium">
                      {formatRelativeTime(plugin.installed_at)}
                    </span>
                  </div>
                  {plugin.pid && (
                    <div className="flex items-center gap-1">
                      <span>PID:</span>
                      <span className="text-gray-700 dark:text-gray-300 font-medium">{plugin.pid}</span>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Install Plugin Modal */}
      {showInstallModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-xl w-full max-w-2xl overflow-hidden animate-in fade-in zoom-in duration-200">
            <div className="p-6 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
              <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-2">
                <Plus className="w-5 h-5 text-blue-600" />
                {t('settings.plugins.install.modal.title', '安装新插件')}
              </h2>
              <button 
                onClick={() => {
                  setShowInstallModal(false);
                  setInstallStep(1);
                  setFetchedPluginInfo(null);
                  setShowManualMode(false);
                  setInstallError(null);
                }}
                className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
              >
                <XCircle className="w-6 h-6" />
              </button>
            </div>
            
            <div className="p-6 space-y-4">
              {installError && (
                <div className="p-3 bg-red-50 dark:bg-red-900/20 border border-red-100 dark:border-red-800 rounded-lg flex items-start gap-3 animate-in fade-in slide-in-from-top-2 duration-200">
                  <XCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
                  <div className="text-sm text-red-700 dark:text-red-400">
                    <p className="font-bold mb-0.5">{t('common.error', '错误')}</p>
                    <p>{installError}</p>
                  </div>
                </div>
              )}

              {showManualMode ? (
                /* Manual YAML Mode */
                <div className="space-y-4">
                  <div className="flex items-start gap-3 p-3 bg-amber-50 dark:bg-amber-900/10 border border-amber-100 dark:border-amber-900/20 rounded-lg text-sm text-amber-800 dark:text-amber-300">
                    <Info className="w-5 h-5 flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="font-medium mb-1">{t('settings.plugins.install.manual.title', '手动安装模式')}</p>
                      <p>{t('settings.plugins.install.manual.description', '粘贴插件描述 YAML 文件进行安装。仅建议高级用户或开发调试时使用。')}</p>
                    </div>
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      {t('settings.plugins.install.modal.yamlLabel', '插件配置 (YAML)')}
                    </label>
                    <textarea
                      value={yamlConfig}
                      onChange={(e) => setYamlConfig(e.target.value)}
                      placeholder="id: com.example.plugin..."
                      className="w-full h-64 p-4 font-mono text-sm bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all resize-none"
                    />
                  </div>
                  <button 
                    onClick={() => {
                      setShowManualMode(false);
                      setInstallError(null);
                    }}
                    className="text-sm text-blue-600 hover:underline"
                  >
                    {t('settings.plugins.install.backToUrl', '返回 URL 安装模式')}
                  </button>
                </div>
              ) : installStep === 1 ? (
                /* Step 1: URL Input */
                <div className="space-y-6">
                  <div className="flex items-start gap-3 p-3 bg-blue-50 dark:bg-blue-900/10 border border-blue-100 dark:border-blue-900/20 rounded-lg text-sm text-blue-800 dark:text-blue-300">
                    <Info className="w-5 h-5 flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="font-medium mb-1">{t('settings.plugins.install.url.title', '通过 URL 安装')}</p>
                      <p>{t('settings.plugins.install.url.description', '输入插件的远程地址，系统将自动获取配置并准备安装。')}</p>
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      {t('settings.plugins.install.url.label', '插件地址')}
                    </label>
                    <div className="flex gap-2">
                      <input
                        type="text"
                        value={pluginUrl}
                        onChange={(e) => {
                          setPluginUrl(e.target.value);
                          if (installError) setInstallError(null);
                        }}
                        onKeyDown={(e) => e.key === 'Enter' && handleFetchInfo()}
                        placeholder="https://github.com/user/repo"
                        className="flex-1 px-4 py-2 bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all"
                      />
                      <button
                        onClick={handleFetchInfo}
                        disabled={isFetchingInfo || !pluginUrl.trim()}
                        className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors flex items-center gap-2"
                      >
                        {isFetchingInfo ? <RefreshCcw className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
                        {t('settings.plugins.install.fetch', '获取信息')}
                      </button>
                    </div>
                    <div className="mt-4 grid grid-cols-3 gap-3">
                      <div className="p-3 border border-gray-100 dark:border-gray-700 rounded-lg bg-gray-50/50 dark:bg-gray-900/30">
                        <div className="flex items-center gap-2 mb-1 text-gray-900 dark:text-gray-100">
                          <Github className="w-3.5 h-3.5" />
                          <span className="text-xs font-bold">GitHub</span>
                        </div>
                        <p className="text-[10px] text-gray-500">支持仓库地址及分支路径</p>
                      </div>
                      <div className="p-3 border border-gray-100 dark:border-gray-700 rounded-lg bg-gray-50/50 dark:bg-gray-900/30">
                        <div className="flex items-center gap-2 mb-1 text-gray-900 dark:text-gray-100">
                          <Puzzle className="w-3.5 h-3.5 text-red-500" />
                          <span className="text-xs font-bold">Gitee</span>
                        </div>
                        <p className="text-[10px] text-gray-500">国内加速，支持码云仓库</p>
                      </div>
                      <div className="p-3 border border-gray-100 dark:border-gray-700 rounded-lg bg-gray-50/50 dark:bg-gray-900/30">
                        <div className="flex items-center gap-2 mb-1 text-gray-900 dark:text-gray-100">
                          <ExternalLink className="w-3.5 h-3.5 text-blue-500" />
                          <span className="text-xs font-bold">Custom</span>
                        </div>
                        <p className="text-[10px] text-gray-500">支持直接 YAML 或目录地址</p>
                      </div>
                    </div>
                  </div>
                  <div className="pt-2">
                    <button 
                      onClick={() => {
                        setShowManualMode(true);
                        setInstallError(null);
                      }}
                      className="text-xs text-gray-400 hover:text-blue-500 transition-colors"
                    >
                      {t('settings.plugins.install.useManual', '使用手动 YAML 粘贴模式')}
                    </button>
                  </div>
                </div>
              ) : (
                /* Step 2: Preview & Confirm */
                <div className="space-y-6 animate-in slide-in-from-right-4 duration-300">
                  <div className="p-4 bg-green-50 dark:bg-green-900/10 border border-green-100 dark:border-green-900/20 rounded-lg flex items-center gap-3 text-green-800 dark:text-green-300 text-sm">
                    <Check className="w-5 h-5" />
                    {t('settings.plugins.install.preview.success', '已成功解析插件配置信息')}
                  </div>

                  <div className="bg-gray-50 dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-700 p-6 space-y-6">
                    <div className="flex items-center gap-4">
                      <div className="w-16 h-16 bg-blue-100 dark:bg-blue-900/40 text-blue-600 dark:text-blue-400 rounded-2xl flex items-center justify-center">
                        <Puzzle className="w-8 h-8" />
                      </div>
                      <div>
                        <h3 className="text-xl font-bold text-gray-900 dark:text-gray-100">{fetchedPluginInfo.name}</h3>
                        <div className="flex items-center gap-2 mt-1">
                          <span className="text-sm font-mono text-gray-500">{fetchedPluginInfo.id}</span>
                          <span className="px-1.5 py-0.5 bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-400 text-[10px] rounded font-bold">v{fetchedPluginInfo.version}</span>
                        </div>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4 text-sm">
                      <div>
                        <p className="text-gray-400 text-xs uppercase font-bold tracking-wider mb-1">{t('settings.plugins.author', '作者')}</p>
                        <p className="text-gray-700 dark:text-gray-300">{fetchedPluginInfo.author || '-'}</p>
                      </div>
                      <div>
                        <p className="text-gray-400 text-xs uppercase font-bold tracking-wider mb-1">{t('settings.plugins.install.source', '来源')}</p>
                        <p className="text-gray-700 dark:text-gray-300 truncate" title={fetchedPluginInfo.source_url}>
                          {new URL(fetchedPluginInfo.source_url).hostname}
                        </p>
                      </div>
                    </div>

                    {fetchedPluginInfo.description && (
                      <div>
                        <p className="text-gray-400 text-xs uppercase font-bold tracking-wider mb-1">{t('settings.plugins.details.description', '描述')}</p>
                        <p className="text-gray-600 dark:text-gray-400 line-clamp-2">{fetchedPluginInfo.description}</p>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
            
            <div className="p-6 bg-gray-50 dark:bg-gray-900/50 border-t border-gray-200 dark:border-gray-700 flex justify-end gap-3">
              {showManualMode ? (
                /* Manual Mode Footer */
                <>
                  <button
                    onClick={() => setShowManualMode(false)}
                    className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-md transition-colors"
                  >
                    {t('common.cancel', '取消')}
                  </button>
                  <button
                    onClick={handleInstall}
                    disabled={isInstalling || !yamlConfig.trim()}
                    className="flex items-center gap-2 px-6 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-md disabled:opacity-50 transition-colors"
                  >
                    {isInstalling ? <RefreshCcw className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
                    {isInstalling ? t('common.installing', '安装中...') : t('common.install', '安装')}
                  </button>
                </>
              ) : installStep === 1 ? (
                /* Step 1 Footer */
                <button
                  onClick={() => {
                    setShowInstallModal(false);
                    setInstallError(null);
                  }}
                  className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-md transition-colors"
                >
                  {t('common.close', '关闭')}
                </button>
              ) : (
                /* Step 2 Footer */
                <>
                  <button
                    onClick={() => {
                      setInstallStep(1);
                      setInstallError(null);
                    }}
                    disabled={isInstalling}
                    className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-md transition-colors"
                  >
                    {t('settings.plugins.install.back', '上一步')}
                  </button>
                  <button
                    onClick={handleInstall}
                    disabled={isInstalling}
                    className="flex items-center gap-2 px-6 py-2 text-sm font-medium text-white bg-green-600 hover:bg-green-700 rounded-md disabled:opacity-50 transition-colors shadow-sm"
                  >
                    {isInstalling ? <RefreshCcw className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
                    {isInstalling ? t('common.installing', '正在安装...') : t('settings.plugins.install.confirm', '确认并安装')}
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Dev Token Modal */}
      {showTokenModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-xl w-full max-w-xl overflow-hidden animate-in fade-in zoom-in duration-200">
            <div className="p-6 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
              <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-2">
                <Key className="w-5 h-5 text-blue-600" />
                {t('settings.plugins.token.modal.title', '项目调试令牌')}
              </h2>
              <button 
                onClick={() => setShowTokenModal(false)}
                className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
              >
                <XCircle className="w-6 h-6" />
              </button>
            </div>
            
            <div className="p-6 space-y-6">
              <div className="p-4 bg-amber-50 dark:bg-amber-900/10 border border-amber-100 dark:border-amber-900/20 rounded-lg text-sm text-amber-800 dark:text-amber-300 flex items-start gap-3">
                <Info className="w-5 h-5 flex-shrink-0 mt-0.5" />
                <p>{t('settings.plugins.token.modal.warning', '令牌有效期为 24 小时。本地调试插件使用此令牌连接后，将自动关联到当前项目。')}</p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  {t('settings.plugins.token.modal.tokenLabel', '您的调试令牌')}
                </label>
                <div className="flex gap-2">
                  <div className="flex-1 p-3 bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg font-mono text-xs break-all text-gray-600 dark:text-gray-400">
                    {devToken}
                  </div>
                  <button
                    onClick={handleCopyToken}
                    className="flex-shrink-0 p-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
                    title={t('common.copy', '复制')}
                  >
                    {copied ? <Check className="w-5 h-5" /> : <Copy className="w-5 h-5" />}
                  </button>
                </div>
              </div>

              <div className="space-y-3">
                <h4 className="text-sm font-semibold text-gray-900 dark:text-gray-100">{t('settings.plugins.token.modal.usage', '使用方法')}</h4>
                
                <div className="space-y-2">
                  <p className="text-xs text-gray-500 font-medium">Go SDK:</p>
                  <pre className="p-3 bg-gray-900 text-gray-300 rounded-lg text-[10px] overflow-auto">
{`tgo.Run(&MyPlugin{}, 
    tgo.WithTCPAddr("localhost:8005"), 
    tgo.WithDevToken("${devToken?.substring(0, 8)}..."))`}
                  </pre>
                </div>

                <div className="space-y-2">
                  <p className="text-xs text-gray-500 font-medium">Python SDK:</p>
                  <pre className="p-3 bg-gray-900 text-gray-300 rounded-lg text-[10px] overflow-auto">
{`plugin = MyPlugin(
    tcp_addr="localhost:8005", 
    dev_token="${devToken?.substring(0, 8)}...")
plugin.run()`}
                  </pre>
                </div>
              </div>
            </div>
            
            <div className="p-6 bg-gray-50 dark:bg-gray-900/50 border-t border-gray-200 dark:border-gray-700 flex justify-end">
              <button
                onClick={() => setShowTokenModal(false)}
                className="px-6 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-md transition-colors"
              >
                {t('common.close', '关闭')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Logs Modal */}
      {showLogsPluginId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
          <div className="bg-gray-900 rounded-xl shadow-2xl w-full max-w-4xl max-h-[80vh] flex flex-col overflow-hidden border border-gray-700">
            <div className="p-4 border-b border-gray-800 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Terminal className="w-5 h-5 text-green-500" />
                <h2 className="text-lg font-semibold text-gray-100">
                  {t('settings.plugins.logs.title', '插件日志')}: {showLogsPluginId}
                </h2>
              </div>
              <div className="flex items-center gap-2">
                <button 
                  onClick={() => handleShowLogs(showLogsPluginId)}
                  className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-800 rounded transition-colors"
                >
                  <RotateCw className="w-4 h-4" />
                </button>
                <button 
                  onClick={() => setShowLogsPluginId(null)}
                  className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-800 rounded transition-colors"
                >
                  <XCircle className="w-5 h-5" />
                </button>
              </div>
            </div>
            
            <div className="flex-1 p-4 font-mono text-xs text-gray-300 overflow-auto bg-black/50">
              {logs.length > 0 ? (
                <div className="space-y-1">
                  {logs.map((log, i) => (
                    <div key={i} className="whitespace-pre-wrap break-all border-l-2 border-transparent hover:border-gray-700 hover:bg-gray-800/30 px-2 py-0.5 transition-colors">
                      {log}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="h-full flex items-center justify-center text-gray-600 italic">
                  {t('settings.plugins.logs.empty', '暂无日志输出')}
                </div>
              )}
            </div>
            
            <div className="p-3 bg-gray-800/50 border-t border-gray-800 flex justify-between text-[10px] text-gray-500 uppercase font-bold tracking-wider">
              <span>{logs.length} LINES</span>
              <span>AUTO-RELOAD EVERY 5S</span>
            </div>
          </div>
        </div>
      )}

      {/* Detail Modal */}
      {showDetailPlugin && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-xl w-full max-w-3xl max-h-[90vh] flex flex-col overflow-hidden animate-in fade-in zoom-in duration-200">
            <div className="p-6 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                  showDetailPlugin.is_dev_mode ? 'bg-amber-50 text-amber-600' : 'bg-blue-50 text-blue-600'
                }`}>
                  {showDetailPlugin.is_dev_mode ? <Terminal className="w-5 h-5" /> : <Puzzle className="w-5 h-5" />}
                </div>
                <div>
                  <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-2">
                    {showDetailPlugin.name}
                    <span className="px-2 py-0.5 text-xs font-normal bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 rounded">
                      v{showDetailPlugin.version}
                    </span>
                  </h2>
                  <p className="text-xs text-mono font-mono text-gray-500 dark:text-gray-400">
                    {showDetailPlugin.plugin_id}
                  </p>
                </div>
              </div>
              <button 
                onClick={() => setShowDetailPlugin(null)}
                className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
              >
                <XCircle className="w-6 h-6" />
              </button>
            </div>
            
            <div className="flex-1 overflow-auto p-6 space-y-8">
              {/* Basic Info Section */}
              <section className="space-y-4">
                <h3 className="text-sm font-bold text-gray-400 uppercase tracking-wider flex items-center gap-2">
                  <Info className="w-4 h-4" />
                  {t('settings.plugins.detail.basicInfo', '基本信息')}
                </h3>
                <div className="grid grid-cols-2 gap-6 bg-gray-50 dark:bg-gray-900/50 p-4 rounded-lg border border-gray-100 dark:border-gray-700">
                  <div className="space-y-1">
                    <p className="text-xs text-gray-500">{t('settings.plugins.author', '作者')}</p>
                    <p className="text-sm font-medium text-gray-900 dark:text-gray-100">{showDetailPlugin.author || '-'}</p>
                  </div>
                  <div className="space-y-1">
                    <p className="text-xs text-gray-500">{t('settings.plugins.status.label', '当前状态')}</p>
                    <div className="flex items-center gap-2">
                      <span className={`w-2 h-2 rounded-full ${showDetailPlugin.status === 'running' ? 'bg-green-500' : 'bg-gray-400'}`} />
                      <p className="text-sm font-medium text-gray-900 dark:text-gray-100 capitalize">{showDetailPlugin.status}</p>
                    </div>
                  </div>
                  <div className="space-y-1">
                    <p className="text-xs text-gray-500">{t('settings.plugins.installType', '安装方式')}</p>
                    <p className="text-sm font-medium text-gray-900 dark:text-gray-100 capitalize">{showDetailPlugin.install_type}</p>
                  </div>
                  <div className="space-y-1">
                    <p className="text-xs text-gray-500">{t('settings.plugins.installedAt', '安装时间')}</p>
                    <p className="text-sm font-medium text-gray-900 dark:text-gray-100">{formatRelativeTime(showDetailPlugin.installed_at)}</p>
                  </div>
                </div>
                {showDetailPlugin.description && (
                  <div className="p-4 bg-blue-50/50 dark:bg-blue-900/10 rounded-lg text-sm text-gray-700 dark:text-gray-300 italic">
                    {showDetailPlugin.description}
                  </div>
                )}
              </section>

              {/* Capabilities Section */}
              <section className="space-y-4">
                <h3 className="text-sm font-bold text-gray-400 uppercase tracking-wider flex items-center gap-2">
                  <Cpu className="w-4 h-4" />
                  {t('settings.plugins.capabilities', '功能能力')}
                </h3>
                {showDetailPlugin.capabilities && showDetailPlugin.capabilities.length > 0 ? (
                  <div className="space-y-3">
                    {showDetailPlugin.capabilities.map((cap, idx) => (
                      <div key={idx} className="p-4 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-sm">
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center gap-2">
                            <span className="p-1.5 bg-gray-100 dark:bg-gray-700 rounded text-gray-600 dark:text-gray-300">
                              <Box className="w-4 h-4" />
                            </span>
                            <span className="font-semibold text-gray-900 dark:text-gray-100">{cap.title}</span>
                            <span className="text-[10px] px-1.5 py-0.5 bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 rounded-full font-bold uppercase">
                              {cap.type}
                            </span>
                          </div>
                          <div className="text-xs text-gray-400">Priority: {cap.priority}</div>
                        </div>
                        
                        {cap.type === 'mcp_tools' && cap.tools && (
                          <div className="mt-4 pl-4 border-l-2 border-gray-100 dark:border-gray-700 space-y-4">
                            <p className="text-xs font-bold text-gray-400 uppercase tracking-wider">MCP Tools ({cap.tools.length})</p>
                            {cap.tools.map((tool, tidx) => (
                              <div key={tidx} className="space-y-2">
                                <div className="flex items-center gap-2">
                                  <span className="text-sm font-mono font-bold text-gray-700 dark:text-gray-200">{tool.name}</span>
                                  <span className="text-xs text-gray-500">— {tool.title}</span>
                                </div>
                                {tool.description && <p className="text-xs text-gray-500 dark:text-gray-400 italic">{tool.description}</p>}
                                {tool.parameters && tool.parameters.length > 0 && (
                                  <div className="overflow-hidden border border-gray-100 dark:border-gray-700 rounded">
                                    <table className="w-full text-xs text-left">
                                      <thead className="bg-gray-50 dark:bg-gray-900/50 text-gray-500">
                                        <tr>
                                          <th className="px-3 py-2 font-medium">Parameter</th>
                                          <th className="px-3 py-2 font-medium">Type</th>
                                          <th className="px-3 py-2 font-medium">Required</th>
                                          <th className="px-3 py-2 font-medium">Description</th>
                                        </tr>
                                      </thead>
                                      <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                                        {tool.parameters.map((param, pidx) => (
                                          <tr key={pidx}>
                                            <td className="px-3 py-2 font-mono text-blue-600 dark:text-blue-400">{param.name}</td>
                                            <td className="px-3 py-2">{param.type}</td>
                                            <td className="px-3 py-2">{param.required ? 'Yes' : 'No'}</td>
                                            <td className="px-3 py-2 text-gray-500">{param.description || '-'}</td>
                                          </tr>
                                        ))}
                                      </tbody>
                                    </table>
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="p-8 text-center bg-gray-50 dark:bg-gray-900/30 border border-dashed border-gray-200 dark:border-gray-700 rounded-lg text-gray-400 text-sm">
                    {t('settings.plugins.detail.noCapabilities', '该插件未声明任何特殊功能')}
                  </div>
                )}
              </section>
            </div>
            
            <div className="p-6 bg-gray-50 dark:bg-gray-900/50 border-t border-gray-200 dark:border-gray-700 flex justify-end">
              <button
                onClick={() => setShowDetailPlugin(null)}
                className="px-6 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-md transition-colors border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800"
              >
                {t('common.close', '关闭')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Development Notice */}
      <div className="bg-blue-50 dark:bg-blue-900/10 border border-blue-100 dark:border-blue-900/20 rounded-lg p-4">
        <div className="flex items-start gap-3">
          <Info className="w-5 h-5 text-blue-600 mt-0.5" />
          <div className="text-sm text-blue-800 dark:text-blue-300">
            <p className="font-semibold mb-1">{t('settings.plugins.debug.title', '调试提示')}</p>
            <p>{t('settings.plugins.debug.description', '在开发模式下，插件可以通过 8005 端口（TCP）连接到 TGO AI 服务。')}</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PluginsSettings;
