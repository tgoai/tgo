import React, { useState, useCallback } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { CirclePlus, Inbox, RefreshCw } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { usePlatformStore, platformSelectors } from '@/stores';
import type { Platform } from '@/types';
import { PlatformType } from '@/types';
import PlatformTypeSelector from './PlatformTypeSelector';
import { useToast } from '@/hooks/useToast';
import { showApiError, showSuccess } from '@/utils/toastHelpers';
import { getPlatformColor, getPlatformIconComponent, getPlatformLabel, toPlatformType } from '@/utils/platformUtils';

interface PlatformListItemProps {
  platform: Platform;
}

/**
 * Platform list item component
 */

const PlatformListItem: React.FC<PlatformListItemProps> = ({ platform }) => {
  const { t } = useTranslation();

  const getStatusConfig = (status: string) => {
    switch (status) {
      case 'connected':
        return { color: 'bg-green-500', text: t('platforms.list.status.connected', '已连接'), textColor: 'text-gray-500' };
      case 'error':
        return { color: 'bg-red-500', text: t('platforms.list.status.error', '连接失败'), textColor: 'text-red-600' };
      case 'pending':
        return { color: 'bg-yellow-400', text: t('platforms.list.status.pending', '待配置'), textColor: 'text-gray-500' };
      default:
        return { color: 'bg-gray-400', text: t('platforms.list.status.notConfigured', '未配置'), textColor: 'text-gray-500' };
    }
  };

  const statusConfig = getStatusConfig(platform.status);
  const isSupported = platform.is_supported !== false; // default to true if not specified
  const displayName = platform.display_name || platform.name;

  const renderIcon = () => {
    const type = toPlatformType(platform.type as any);
    const IconComp = getPlatformIconComponent(type);
    const label = getPlatformLabel(type);
    return (
      <span title={label}>
        <IconComp size={20} className={`w-6 h-6 mr-3 flex-shrink-0 ${getPlatformColor(type)} ${!isSupported ? 'opacity-50' : ''}`} />
      </span>
    );
  };

  // If platform type is not supported, render as disabled (non-clickable)
  if (!isSupported) {
    return (
      <div
        className="flex items-center p-3 rounded-lg opacity-60 cursor-not-allowed bg-gray-50"
      >
        <div className="text-gray-500">
          {renderIcon()}
        </div>
        <div className="flex-grow overflow-hidden">
          <p className="text-sm font-medium truncate text-gray-500">
            {displayName}
          </p>
          <div className="flex items-center mt-1">
            <span className={`w-2 h-2 ${statusConfig.color} rounded-full mr-1.5 flex-shrink-0 opacity-50`}></span>
            <span className="text-xs text-gray-400">
              {t('platforms.list.status.unsupported', '平台类型暂不支持')}
            </span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <NavLink
      to={`/platforms/${platform.id}`}
      className={({ isActive }) => `
        flex items-center p-3 rounded-lg transition-colors duration-150
        ${isActive
          ? 'bg-blue-50 hover:bg-blue-100/70 border border-blue-200/80'
          : 'hover:bg-gray-100/70'
        }
      `}
    >
      {({ isActive }) => (
        <>
          <div className="text-gray-700">
            {renderIcon()}
          </div>
          <div className="flex-grow overflow-hidden">
            <p className={`text-sm font-medium truncate ${
              isActive ? 'text-blue-800' : 'text-gray-800'
            }`}>
              {displayName}
            </p>
            <div className="flex items-center mt-1">
              <span className={`w-2 h-2 ${statusConfig.color} rounded-full mr-1.5 flex-shrink-0`}></span>
              <span className={`text-xs ${statusConfig.textColor}`}>
                {statusConfig.text}
              </span>
            </div>
          </div>
        </>
      )}
    </NavLink>
  );
};

/**
 * Platform list sidebar component
 */
const PlatformList: React.FC = () => {
  const { t } = useTranslation();
  const platforms = usePlatformStore(platformSelectors.platforms);
  const isLoading = usePlatformStore(platformSelectors.isLoading);
  const loadError = usePlatformStore(state => state.loadError);
  const createPlatform = usePlatformStore(state => state.createPlatform);
  const initializeStore = usePlatformStore(state => state.initializeStore);
  const navigate = useNavigate();
  const { showToast } = useToast();
  const [showTypeSelector, setShowTypeSelector] = useState(false);
  const [isRetrying, setIsRetrying] = useState(false);

  const handleAddPlatform = (): void => {
    setShowTypeSelector(true);
  };

  const handleRetry = useCallback(async () => {
    setIsRetrying(true);
    try {
      await initializeStore();
    } catch (error) {
      // Error is already handled in the store
      console.error('Retry failed:', error);
    } finally {
      setIsRetrying(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Empty deps - initializeStore is a stable store function

  const handleTypeSelect = useCallback(async ({ type, name }: { type: string; name: string }) => {
    try {
      const selectedType: PlatformType = type as PlatformType;
      const created = await createPlatform({
        name: name || t('platforms.list.defaultName', '新平台'),
        type: selectedType,
      });
      setShowTypeSelector(false); // close only on success
      showSuccess(
        showToast,
        t('platforms.list.toast.createSuccessTitle', '创建成功'),
        t('platforms.list.toast.createSuccessMessage', {
          defaultValue: `平台 “${created.name}” 已创建`,
          name: created.name,
        })
      );
      navigate(`/platforms/${created.id}`);
    } catch (e) {
      // Keep modal open on failure; show error toast
      showApiError(showToast, e);
    }
  }, [createPlatform, navigate, showToast, t]);

  return (
    <>
      <aside className="w-72 bg-white/90 backdrop-blur-lg border-r border-gray-200/60 flex flex-col shrink-0">
      {/* Header */}
      <div className="p-4 border-b border-gray-200/60 sticky top-0 bg-white/90 backdrop-blur-lg z-10 flex justify-between items-center">
        <h3 className="text-md font-semibold text-gray-800">
          {t('platforms.list.title', '接入平台')}
        </h3>
        <button
          className="p-1.5 text-blue-600 hover:bg-blue-100/70 rounded-md transition-colors duration-200"
          title={t('platforms.list.addPlatform', '添加平台')}
          onClick={handleAddPlatform}
        >
          <CirclePlus className="w-5 h-5" />
        </button>
      </div>

      {/* Platform List */}
      <nav className="flex-grow overflow-y-auto p-3 space-y-1">
        {isLoading && (
          <div className="text-center text-gray-500 py-8 animate-pulse">
            <Inbox className="mx-auto mb-4 w-12 h-12 text-gray-300" />
            <p className="text-sm">{t('platforms.list.loading', '正在加载平台列表…')}</p>
          </div>
        )}

        {!isLoading && loadError && (
          <div className="text-center text-red-600 py-8 px-4">
            <Inbox className="mx-auto mb-4 w-12 h-12 text-red-300" />
            <p className="text-sm font-medium">{t('platforms.list.loadFailedTitle', '加载失败')}</p>
            <p className="text-xs mt-1 text-red-500">{loadError}</p>
            <button
              onClick={handleRetry}
              disabled={isRetrying}
              className="mt-4 px-4 py-2 bg-blue-600 text-white text-sm rounded-md hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors duration-200 flex items-center gap-2 mx-auto"
            >
              <RefreshCw className={`w-4 h-4 ${isRetrying ? 'animate-spin' : ''}`} />
              {isRetrying ? t('platforms.list.retrying', '重试中...') : t('platforms.list.retry', '重试')}
            </button>
          </div>
        )}

        {!isLoading && !loadError && platforms.map((platform: Platform) => (
          <PlatformListItem
            key={platform.id}
            platform={platform}
          />
        ))}

        {!isLoading && !loadError && platforms.length === 0 && (
          <div className="text-center text-gray-500 py-8">
            <Inbox className="mx-auto mb-4 w-12 h-12 text-gray-300" />
            <p className="text-sm">{t('platforms.list.emptyTitle', '暂无平台')}</p>
            <p className="text-xs mt-1">{t('platforms.list.emptyDescription', '点击上方按钮添加平台')}</p>
          </div>
        )}
      </nav>
    </aside>
    <PlatformTypeSelector
      open={showTypeSelector}
      onClose={() => setShowTypeSelector(false)}
      onSelect={handleTypeSelect}
    />
    </>
  );
};

export default PlatformList;

