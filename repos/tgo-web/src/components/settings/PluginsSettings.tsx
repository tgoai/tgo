import React, { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Puzzle, RefreshCcw, ExternalLink, Cpu, Info, CheckCircle2, XCircle } from 'lucide-react';
import { usePluginStore } from '@/stores/pluginStore';

const PluginsSettings: React.FC = () => {
  const { t } = useTranslation();
  const { plugins, isLoadingPlugins, fetchPlugins } = usePluginStore();

  useEffect(() => {
    fetchPlugins();
  }, [fetchPlugins]);

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
              {t('settings.plugins.subtitle', '查看并管理已连接到 TGO 的插件')}
            </p>
          </div>
        </div>
        <button
          onClick={() => fetchPlugins()}
          disabled={isLoadingPlugins}
          className="flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50 dark:bg-gray-800 dark:text-gray-200 dark:border-gray-600 dark:hover:bg-gray-700 transition-colors"
        >
          <RefreshCcw className={`w-4 h-4 ${isLoadingPlugins ? 'animate-spin' : ''}`} />
          {t('common.refresh', '刷新')}
        </button>
      </div>

      {/* Plugins List */}
      <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
        {isLoadingPlugins && plugins.length === 0 ? (
          <div className="p-12 flex flex-col items-center justify-center text-gray-500">
            <RefreshCcw className="w-8 h-8 animate-spin mb-4" />
            <p>{t('common.loading', '加载中...')}</p>
          </div>
        ) : plugins.length === 0 ? (
          <div className="p-12 flex flex-col items-center justify-center text-gray-500 text-center">
            <Puzzle className="w-12 h-12 mb-4 opacity-20" />
            <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-1">
              {t('settings.plugins.empty.title', '暂无已连接的插件')}
            </h3>
            <p className="max-w-xs text-sm">
              {t('settings.plugins.empty.description', '插件可以通过 Unix Socket 或 TCP 连接到 TGO API 服务。')}
            </p>
            <a 
              href="https://tgo.example.com/docs/plugin" 
              target="_blank" 
              rel="noreferrer"
              className="mt-4 text-blue-600 hover:underline text-sm flex items-center gap-1"
            >
              {t('settings.plugins.viewDocs', '查看插件开发指南')}
              <ExternalLink className="w-3 h-3" />
            </a>
          </div>
        ) : (
          <div className="divide-y divide-gray-200 dark:divide-gray-700">
            {plugins.map((plugin) => (
              <div key={plugin.id} className="p-6 hover:bg-gray-50 dark:hover:bg-gray-900/50 transition-colors">
                <div className="flex items-start justify-between mb-4">
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 rounded-lg bg-blue-50 dark:bg-blue-900/20 flex items-center justify-center text-blue-600">
                      <Cpu className="w-6 h-6" />
                    </div>
                    <div>
                      <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-2">
                        {plugin.name}
                        <span className="px-2 py-0.5 text-xs font-normal bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 rounded">
                          v{plugin.version}
                        </span>
                      </h3>
                      <p className="text-sm text-mono font-mono text-gray-500 dark:text-gray-400">
                        {plugin.id}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {plugin.status === 'connected' ? (
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400">
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        {t('settings.plugins.status.connected', '已连接')}
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400">
                        <XCircle className="w-3.5 h-3.5" />
                        {t('settings.plugins.status.disconnected', '已断开')}
                      </span>
                    )}
                  </div>
                </div>

                {plugin.description && (
                  <p className="text-sm text-gray-600 dark:text-gray-300 mb-4 ml-16">
                    {plugin.description}
                  </p>
                )}

                <div className="ml-16 space-y-4">
                  {/* Capabilities */}
                  <div>
                    <h4 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-2 flex items-center gap-1">
                      <Info className="w-3 h-3" />
                      {t('settings.plugins.capabilities', '功能声明')}
                    </h4>
                    <div className="flex flex-wrap gap-2">
                      {plugin.capabilities.map((cap, idx) => (
                        <div 
                          key={idx}
                          className="px-3 py-1 bg-white dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-md shadow-sm"
                        >
                          <div className="flex items-center gap-2">
                            {cap.icon && <span className="text-gray-400">#{cap.icon}</span>}
                            <span className="text-sm font-medium text-gray-700 dark:text-gray-200">{cap.title}</span>
                            <span className="text-[10px] px-1 bg-gray-100 dark:bg-gray-600 text-gray-500 dark:text-gray-400 rounded">
                              {cap.type}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Metadata */}
                  <div className="flex items-center gap-6 text-xs text-gray-500">
                    {plugin.author && (
                      <div className="flex items-center gap-1">
                        <span>{t('settings.plugins.author', '作者')}:</span>
                        <span className="text-gray-700 dark:text-gray-300 font-medium">{plugin.author}</span>
                      </div>
                    )}
                    <div className="flex items-center gap-1">
                      <span>{t('settings.plugins.connectedAt', '连接时间')}:</span>
                      <span className="text-gray-700 dark:text-gray-300 font-medium">
                        {new Date(plugin.connected_at).toLocaleString()}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Debug Info */}
      <div className="bg-blue-50 dark:bg-blue-900/10 border border-blue-100 dark:border-blue-900/20 rounded-lg p-4">
        <div className="flex items-start gap-3">
          <Info className="w-5 h-5 text-blue-600 mt-0.5" />
          <div className="text-sm text-blue-800 dark:text-blue-300">
            <p className="font-semibold mb-1">{t('settings.plugins.debug.title', '调试提示')}</p>
            <p>{t('settings.plugins.debug.description', '在开发模式下，您可以通过 8005 端口（TCP）或 /var/run/tgo/tgo.sock（Unix Socket）连接本地开发的插件。')}</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PluginsSettings;

