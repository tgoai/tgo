import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Info, Server, Code, GitBranch, Clock, AlertCircle, Github, Globe, ExternalLink } from 'lucide-react';
import { systemApiService, type SystemInfoResponse } from '@/services/systemApi';

const AboutSettings: React.FC = () => {
  const { t } = useTranslation();
  const [systemInfo, setSystemInfo] = useState<SystemInfoResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchSystemInfo = async () => {
      try {
        setLoading(true);
        setError(null);
        const info = await systemApiService.getSystemInfo();
        setSystemInfo(info);
      } catch (err) {
        console.error('Failed to fetch system info:', err);
        setError(t('about.loadError', '加载系统信息失败'));
      } finally {
        setLoading(false);
      }
    };

    fetchSystemInfo();
  }, [t]);

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center gap-2">
        <Info className="w-5 h-5 text-gray-600" />
        <h2 className="text-lg font-medium text-gray-800">{t('common.about', '关于')}</h2>
      </div>

      {/* Loading State */}
      {loading && (
        <div className="bg-white rounded-lg border border-gray-200 p-8 flex items-center justify-center">
          <div className="flex items-center gap-3 text-gray-500">
            <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-blue-600"></div>
            <span className="text-sm">{t('about.loading', '加载中...')}</span>
          </div>
        </div>
      )}

      {/* Error State */}
      {error && !loading && (
        <div className="bg-red-50 rounded-lg border border-red-200 p-4 flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <p className="text-sm text-red-800">{error}</p>
          </div>
        </div>
      )}

      {/* System Information */}
      {!loading && !error && systemInfo && (
        <div className="space-y-4">
          {/* Main System Info Card */}
          <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
            <div className="px-4 py-3 bg-gray-50 border-b border-gray-200">
              <div className="flex items-center gap-2">
                <Server className="w-4 h-4 text-gray-600" />
                <h3 className="text-sm font-medium text-gray-800">{t('about.systemInfo', '系统信息')}</h3>
              </div>
            </div>
            <div className="p-4 space-y-3">
              <div className="flex items-center justify-between py-2">
                <span className="text-sm text-gray-600">{t('about.version', '版本')}</span>
                <span className="text-sm font-mono font-medium text-gray-900">{systemInfo.version || 'N/A'}</span>
              </div>
              <div className="flex items-center justify-between py-2 border-t border-gray-100">
                <span className="text-sm text-gray-600">{t('about.environment', '环境')}</span>
                <span className="text-sm font-mono text-gray-900">
                  <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                    systemInfo.environment === 'production'
                      ? 'bg-green-100 text-green-800'
                      : systemInfo.environment === 'development'
                      ? 'bg-yellow-100 text-yellow-800'
                      : 'bg-gray-100 text-gray-800'
                  }`}>
                    {systemInfo.environment || 'unknown'}
                  </span>
                </span>
              </div>
            </div>
          </div>

          {/* Technical Details Card */}
          <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
            <div className="px-4 py-3 bg-gray-50 border-b border-gray-200">
              <div className="flex items-center gap-2">
                <Code className="w-4 h-4 text-gray-600" />
                <h3 className="text-sm font-medium text-gray-800">{t('about.technicalDetails', '技术详情')}</h3>
              </div>
            </div>
            <div className="p-4 space-y-3">
              <div className="flex items-center justify-between py-2">
                <span className="text-sm text-gray-600">{t('about.apiVersion', 'API 版本')}</span>
                <span className="text-sm font-mono text-gray-900">{systemInfo.api_version || 'N/A'}</span>
              </div>
              <div className="flex items-center justify-between py-2 border-t border-gray-100">
                <span className="text-sm text-gray-600">{t('about.pythonVersion', 'Python 版本')}</span>
                <span className="text-sm font-mono text-gray-900">{systemInfo.python_version || 'N/A'}</span>
              </div>
              <div className="flex items-start justify-between py-2 border-t border-gray-100">
                <span className="text-sm text-gray-600 flex items-center gap-1.5">
                  <Clock className="w-3.5 h-3.5" />
                  {t('about.buildTime', '构建时间')}
                </span>
                <span className="text-sm font-mono text-gray-900 text-right">{systemInfo.build_time || 'N/A'}</span>
              </div>
              <div className="flex items-start justify-between py-2 border-t border-gray-100">
                <span className="text-sm text-gray-600 flex items-center gap-1.5">
                  <GitBranch className="w-3.5 h-3.5" />
                  {t('about.gitCommit', 'Git 提交')}
                </span>
                <span className="text-xs font-mono text-gray-900 bg-gray-50 px-2 py-1 rounded border border-gray-200">
                  {systemInfo.git_commit ? systemInfo.git_commit.substring(0, 8) : 'N/A'}
                </span>
              </div>
            </div>
          </div>

          {/* Links Card */}
          <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
            <div className="px-4 py-3 bg-gray-50 border-b border-gray-200">
              <div className="flex items-center gap-2">
                <ExternalLink className="w-4 h-4 text-gray-600" />
                <h3 className="text-sm font-medium text-gray-800">{t('about.links', '相关链接')}</h3>
              </div>
            </div>
            <div className="p-4 space-y-3">
              <a
                href="https://github.com/tgoai/tgo"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center justify-between py-2 px-3 rounded-md hover:bg-gray-50 transition-colors group"
              >
                <span className="flex items-center gap-2 text-sm text-gray-700">
                  <Github className="w-4 h-4 text-gray-600" />
                  {t('about.github', 'GitHub 开源地址')}
                </span>
                <ExternalLink className="w-3.5 h-3.5 text-gray-400 group-hover:text-blue-600 transition-colors" />
              </a>
              <a
                href="https://tgo.ai"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center justify-between py-2 px-3 rounded-md hover:bg-gray-50 transition-colors group border-t border-gray-100"
              >
                <span className="flex items-center gap-2 text-sm text-gray-700">
                  <Globe className="w-4 h-4 text-gray-600" />
                  {t('about.website', '官网地址')}
                </span>
                <ExternalLink className="w-3.5 h-3.5 text-gray-400 group-hover:text-blue-600 transition-colors" />
              </a>
            </div>
          </div>

          {/* Copyright */}
          <div className="text-center text-xs text-gray-500 pt-2">
            © {new Date().getFullYear()} TGO Web. {t('about.copyright', 'All rights reserved.')}
          </div>
        </div>
      )}
    </div>
  );
};

export default AboutSettings;

