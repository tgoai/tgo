import React, { useEffect, useRef } from 'react';
import { useParams, Navigate } from 'react-router-dom';
import { usePlatformStore } from '@/stores/platformStore';
import { platformSelectors } from '@/stores';
import PlatformConfig from '@/components/platforms/PlatformConfig';
import WebsitePlatformConfig from '@/components/platforms/WebsitePlatformConfig';
import WeComPlatformConfig from '@/components/platforms/WeComPlatformConfig';
import WeComBotPlatformConfig from '@/components/platforms/WeComBotPlatformConfig';
import FeishuBotPlatformConfig from '@/components/platforms/FeishuBotPlatformConfig';
import DingTalkBotPlatformConfig from '@/components/platforms/DingTalkBotPlatformConfig';
import EmailPlatformConfig from '@/components/platforms/EmailPlatformConfig';
import DouyinPlatformConfig from '@/components/platforms/DouyinPlatformConfig';
import CustomPlatformConfig from '@/components/platforms/CustomPlatformConfig';
import TelegramPlatformConfig from '@/components/platforms/TelegramPlatformConfig';
import SlackPlatformConfig from '@/components/platforms/SlackPlatformConfig';
import WeChatPersonalPlatformConfig from '@/components/platforms/WeChatPersonalPlatformConfig';

/**
 * Platform Configuration page component
 * Displays configuration for a specific platform based on URL parameter
 */
const PlatformConfigPage: React.FC = () => {
  const { platformId } = useParams<{ platformId: string }>();
  const platforms = usePlatformStore(platformSelectors.platforms);
  const isLoading = usePlatformStore(platformSelectors.isLoading);
  const isLoadingDetail = usePlatformStore(state => state.isLoadingDetail);
  const detailLoadError = usePlatformStore(state => state.detailLoadError);
  const fetchPlatformById = usePlatformStore(state => state.fetchPlatformById);

  // Track the last loaded platform ID to avoid redundant fetches
  const lastLoadedIdRef = useRef<string | null>(null);

  const platform = platforms.find((p: any) => p.id === platformId);

  // Fetch platform detail when platformId changes
  useEffect(() => {
    if (platformId && platformId !== lastLoadedIdRef.current) {
      lastLoadedIdRef.current = platformId;
      fetchPlatformById(platformId).catch((error) => {
        console.error('Failed to load platform detail:', error);
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [platformId]); // Only depend on platformId, not fetchPlatformById (it's a stable store function)

  // Show loading state while fetching platform detail
  if (isLoadingDetail) {
    return (
      <div className="flex-grow flex items-center justify-center bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-900 dark:to-gray-800">
        <div className="text-center text-gray-500 dark:text-gray-400">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 dark:border-blue-400 mx-auto mb-4"></div>
          <p className="text-sm">加载平台配置中...</p>
        </div>
      </div>
    );
  }

  // Show error state if detail loading failed
  if (detailLoadError && !platform) {
    return (
      <div className="flex-grow flex items-center justify-center bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-900 dark:to-gray-800">
        <div className="text-center text-red-600 dark:text-red-400">
          <div className="text-red-300 dark:text-red-500 mb-4">
            <svg className="mx-auto h-12 w-12" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <p className="text-sm font-medium mb-2">加载平台配置失败</p>
          <p className="text-xs text-red-500 dark:text-red-400 mb-4">{detailLoadError}</p>
          <button
            onClick={() => platformId && fetchPlatformById(platformId)}
            className="px-4 py-2 bg-blue-600 dark:bg-blue-500 text-white text-sm rounded-md hover:bg-blue-700 dark:hover:bg-blue-600 transition-colors"
          >
            重试
          </button>
        </div>
      </div>
    );
  }

  // Show loading state while fetching platform list
  if (isLoading && !platform) {
    return (
      <div className="p-6">
        <div className="text-center text-gray-500">Loading...</div>
      </div>
    );
  }

  if (!isLoading && !platform && platforms.length > 0) {
    return <Navigate to={`/platforms/${platforms[0]!.id}`} replace />;
  }

  if (!isLoading && platforms.length === 0) {
    return <Navigate to="/platforms" replace />;
  }

  if (!platform) {
    return null;
  }

  if (platform.type === 'website') {
    return <WebsitePlatformConfig platform={platform} />;
  }
  // 企业微信（WeCom）
  if ((platform.type as any) === 'wecom') {
    return <WeComPlatformConfig platform={platform} />;
  }
  // 企业微信机器人（WeCom Bot）
  if ((platform.type as any) === 'wecom_bot') {
    return <WeComBotPlatformConfig platform={platform} />;
  }
  // 飞书机器人（Feishu Bot）
  if ((platform.type as any) === 'feishu_bot') {
    return <FeishuBotPlatformConfig platform={platform} />;
  }
  // 钉钉机器人（DingTalk Bot）
  if ((platform.type as any) === 'dingtalk_bot') {
    return <DingTalkBotPlatformConfig platform={platform} />;
  }
  // 邮件（Email）
  if (platform.type === 'email') {
    return <EmailPlatformConfig platform={platform} />;
  }
  // 抖音/抖音国际（TikTok China market）
  if (platform.type === 'douyin' || platform.type === 'tiktok') {
    return <DouyinPlatformConfig platform={platform} />;
  }
  // 自定义平台（Custom）
  if (platform.type === 'custom') {
    return <CustomPlatformConfig platform={platform} />;
  }
  // Telegram
  if ((platform.type as any) === 'telegram') {
    return <TelegramPlatformConfig platform={platform} />;
  }
  // Slack
  if ((platform.type as any) === 'slack') {
    return <SlackPlatformConfig platform={platform} />;
  }
  // 个人微信（WeChat Personal）- Vision Agent
  if ((platform.type as any) === 'wechat_personal') {
    return <WeChatPersonalPlatformConfig platform={platform} />;
  }

  // Fallback to generic/placeholder config for other types
  return <PlatformConfig platform={platform} />;
};

export default PlatformConfigPage;

