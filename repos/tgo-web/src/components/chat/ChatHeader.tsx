import React, { useState, useCallback, useEffect, useRef } from 'react';
import type { Chat, PlatformType, ChannelVisitorExtra, VisitorServiceStatus } from '@/types';
import { useTranslation } from 'react-i18next';
import { Bot, LogOut, Loader2, ArrowRightLeft, ChevronDown, User } from 'lucide-react';
import { TbBrain } from 'react-icons/tb';

import { getPlatformIconComponent, getPlatformLabel, toPlatformType, getPlatformColor } from '@/utils/platformUtils';
import { visitorApiService } from '@/services/visitorApi';
import { staffApi, type StaffListResponse } from '@/services/staffApi';
import type { StaffResponse } from '@/services/api';
import { useToast } from '@/hooks/useToast';
import { useChannelStore } from '@/stores/channelStore';
import { useChannelDisplay } from '@/hooks/useChannelDisplay';
import { useAuthStore } from '@/stores/authStore';
import { useChatStore } from '@/stores/chatStore';

/**
 * Props for the ChatHeader component
 */
export interface ChatHeaderProps {
  /** The active chat to display in the header */
  activeChat: Chat;
  /** Callback when chat is ended successfully (with channel info) */
  onEndChatSuccess?: (channelId: string, channelType: number) => void;
}

/**
 * Chat header component displaying visitor name and platform icon
 * Memoized to prevent unnecessary re-renders
 */
const ChatHeader: React.FC<ChatHeaderProps> = React.memo(({ activeChat, onEndChatSuccess }) => {
  const { t } = useTranslation();
  const { showSuccess, showError } = useToast();
  const [isClosing, setIsClosing] = useState(false);
  const [isTransferring, setIsTransferring] = useState(false);
  const [showTransferMenu, setShowTransferMenu] = useState(false);
  const [staffList, setStaffList] = useState<StaffResponse[]>([]);
  const [isLoadingStaff, setIsLoadingStaff] = useState(false);
  const transferMenuRef = useRef<HTMLDivElement>(null);
  const updateChannelExtra = useChannelStore(state => state.updateChannelExtra);
  const deleteChat = useChatStore(state => state.deleteChat);
  const currentUser = useAuthStore(state => state.user);
  
  // 判断是否是 agent 会话（channelId 以 -agent 结尾）或 team 会话（channelId 以 -team 结尾）
  const isAgentChat = activeChat.channelId?.endsWith('-agent') ?? false;
  const isTeamChat = activeChat.channelId?.endsWith('-team') ?? false;
  const isAIChat = isAgentChat || isTeamChat;
  
  // 使用 useChannelDisplay hook 获取频道展示信息
  const { name: channelName, extra } = useChannelDisplay({
    channelId: activeChat.channelId,
    channelType: activeChat.channelType,
    skipFetch: isAIChat, // AI 会话不需要获取频道信息
  });
  
  // 获取访客信息
  const visitorExtra = extra as ChannelVisitorExtra | undefined;
  const visitorId = visitorExtra?.id;
  const serviceStatus = visitorExtra?.service_status as VisitorServiceStatus | undefined;
  const assignedStaffId = visitorExtra?.assigned_staff_id;
  
  // 检查访客是否分配给当前坐席
  const isMyVisitor = !assignedStaffId || assignedStaffId === currentUser?.id;
  
  // 只有访客会话且状态为 active 且是我的访客时才显示结束聊天按钮
  const showEndChatButton = !isAIChat && visitorId && serviceStatus === 'active' && isMyVisitor;
  
  // 获取显示名称
  const displayName = isAgentChat 
    ? t('chat.header.agentFallback', '智能体')
    : isTeamChat
      ? t('chat.header.teamFallback', '智能体团队')
      : channelName;

  // 结束聊天处理
  const handleEndChat = useCallback(async () => {
    if (!visitorId || isClosing) return;
    
    setIsClosing(true);
    try {
      await visitorApiService.closeSession(visitorId);
      showSuccess(t('chat.header.endChatSuccess', '会话已结束'));
      
      // 保存 channel 信息用于通知父组件
      const channelId = activeChat.channelId;
      const channelType = activeChat.channelType;
      
      // 更新本地状态
      if (channelId && channelType !== undefined) {
        updateChannelExtra(channelId, channelType, {
          service_status: 'closed' as VisitorServiceStatus,
        });
        // 从最近会话列表移除当前会话
        deleteChat(activeChat.id);
        
        // 通知父组件结束聊天成功（传递 channel 信息），让父组件处理移除和选中下一个会话
        onEndChatSuccess?.(channelId, channelType);
      }
    } catch (error: any) {
      console.error('Failed to close session:', error);
      showError(error?.message || t('chat.header.endChatError', '结束会话失败'));
    } finally {
      setIsClosing(false);
    }
  }, [visitorId, isClosing, showSuccess, showError, t, activeChat.channelId, activeChat.channelType, activeChat.id, updateChannelExtra, deleteChat, onEndChatSuccess]);

  // 加载坐席列表
  const loadStaffList = useCallback(async () => {
    if (isLoadingStaff) return;
    setIsLoadingStaff(true);
    try {
      const response: StaffListResponse = await staffApi.listStaff({ limit: 50 });
      // 过滤掉当前用户和未激活的坐席
      const filteredStaff = response.data.filter(
        staff => staff.id !== currentUser?.id && staff.is_active !== false
      );
      setStaffList(filteredStaff);
    } catch (error) {
      console.error('Failed to load staff list:', error);
      showError(t('chat.header.loadStaffError', '获取坐席列表失败'));
    } finally {
      setIsLoadingStaff(false);
    }
  }, [isLoadingStaff, currentUser?.id, showError, t]);

  // 打开转接菜单
  const handleTransferClick = useCallback(() => {
    if (!showTransferMenu) {
      loadStaffList();
    }
    setShowTransferMenu(!showTransferMenu);
  }, [showTransferMenu, loadStaffList]);

  // 执行转接
  const handleTransferToStaff = useCallback(async (targetStaffId: string, staffName: string) => {
    if (!visitorId || isTransferring) return;
    
    setIsTransferring(true);
    setShowTransferMenu(false);
    try {
      await visitorApiService.transferSession(visitorId, targetStaffId);
      showSuccess(t('chat.header.transferSuccess', '已转接给 {{name}}', { name: staffName }));
      
      // 保存 channel 信息用于通知父组件
      const channelId = activeChat.channelId;
      const channelType = activeChat.channelType;
      
      // 更新本地状态
      if (channelId && channelType !== undefined) {
        updateChannelExtra(channelId, channelType, {
          service_status: 'closed' as VisitorServiceStatus,
        });
        // 从最近会话列表移除当前会话
        deleteChat(activeChat.id);
        
        // 通知父组件转接成功（传递 channel 信息），让父组件处理移除和选中下一个会话
        onEndChatSuccess?.(channelId, channelType);
      }
    } catch (error: any) {
      console.error('Failed to transfer session:', error);
      showError(error?.message || t('chat.header.transferError', '转接失败'));
    } finally {
      setIsTransferring(false);
    }
  }, [visitorId, isTransferring, showSuccess, showError, t, activeChat.channelId, activeChat.channelType, activeChat.id, updateChannelExtra, deleteChat, onEndChatSuccess]);

  // 点击外部关闭菜单
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (transferMenuRef.current && !transferMenuRef.current.contains(event.target as Node)) {
        setShowTransferMenu(false);
      }
    };
    if (showTransferMenu) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [showTransferMenu]);
  
  return (
    <header className="px-6 py-3 border-b border-gray-200/80 dark:border-gray-700/80 flex justify-between items-center bg-white/60 dark:bg-gray-800/60 backdrop-blur-lg sticky top-0 z-10">
      <div>
        <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-200 flex items-center">
          <span>{displayName}</span>
          {isAgentChat ? (
            <span title={t('chat.header.agentTooltip', '智能体会话')}>
              <Bot className="w-4 h-4 inline-block ml-1.5 -mt-0.5 text-purple-500 dark:text-purple-400" />
            </span>
          ) : isTeamChat ? (
            <span title={t('chat.header.teamTooltip', '团队会话')}>
              <TbBrain className="w-4 h-4 inline-block ml-1.5 -mt-0.5 text-green-500 dark:text-green-400" />
            </span>
          ) : (
            (() => {
              const fromExtra: PlatformType | undefined = visitorExtra?.platform_type;
              const type = fromExtra ?? toPlatformType(activeChat.platform);
              const IconComp = getPlatformIconComponent(type);
              const label = getPlatformLabel(type);
              return (
                <span title={label}>
                  <IconComp size={16} className={`w-3.5 h-3.5 inline-block ml-1 -mt-0.5 ${getPlatformColor(type)}`} />
                </span>
              );
            })()
          )}
        </h2>
      </div>
      {/* 操作按钮 - 只对访客会话显示 */}
      {showEndChatButton && (
        <div className="flex items-center gap-1">
          {/* 转接按钮 */}
          <div className="relative" ref={transferMenuRef}>
            <button
              onClick={handleTransferClick}
              disabled={isTransferring}
              className="flex items-center gap-1 px-2 py-1 text-xs text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded transition-colors duration-200 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
              title={t('chat.header.transferTooltip', '转接给其他客服')}
            >
              {isTransferring ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <ArrowRightLeft className="w-3.5 h-3.5" />
              )}
              <span>{t('chat.header.transfer', '转接')}</span>
              <ChevronDown className="w-3 h-3" />
            </button>
            {/* 坐席选择下拉菜单 */}
            {showTransferMenu && (
              <div className="absolute right-0 top-full mt-1 w-48 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg z-20 py-1 max-h-60 overflow-y-auto">
                {isLoadingStaff ? (
                  <div className="flex items-center justify-center py-3">
                    <Loader2 className="w-4 h-4 animate-spin text-gray-400" />
                  </div>
                ) : staffList.length === 0 ? (
                  <div className="px-3 py-2 text-xs text-gray-500 dark:text-gray-400">
                    {t('chat.header.noAvailableStaff', '暂无可用坐席')}
                  </div>
                ) : (
                  staffList.map(staff => (
                    <button
                      key={staff.id}
                      onClick={() => handleTransferToStaff(staff.id, staff.nickname || staff.username)}
                      className="w-full flex items-center gap-2 px-3 py-2 text-xs text-left text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                    >
                      {staff.avatar_url ? (
                        <img src={staff.avatar_url} alt="" className="w-5 h-5 rounded-full object-cover" />
                      ) : (
                        <User className="w-5 h-5 text-gray-400" />
                      )}
                      <span className="truncate">{staff.nickname || staff.username}</span>
                    </button>
                  ))
                )}
              </div>
            )}
          </div>
          {/* 结束聊天按钮 */}
          <button
            onClick={handleEndChat}
            disabled={isClosing}
            className="flex items-center gap-1 px-2 py-1 text-xs text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded transition-colors duration-200 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
            title={t('chat.header.endChatTooltip', '结束当前会话')}
          >
            {isClosing ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <LogOut className="w-3.5 h-3.5" />
            )}
            <span>{t('chat.header.endChat', '结束聊天')}</span>
          </button>
        </div>
      )}
    </header>
  );
});

ChatHeader.displayName = 'ChatHeader';

export default ChatHeader;
