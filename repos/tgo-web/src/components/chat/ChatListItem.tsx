import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { Chat, ChannelVisitorExtra } from '@/types';
import { DEFAULT_CHANNEL_TYPE } from '@/constants';
import { useChannelDisplay } from '@/hooks/useChannelDisplay';
import { toPlatformType } from '@/utils/platformUtils';
import { formatWeChatConversationTime } from '@/utils/timeFormatting';
import { formatChatLastMessage } from '@/utils/messageFormatting';
import { diffMinutesFromNow } from '@/utils/dateUtils';
import { ChatAvatar } from './ChatAvatar';
import { ChatPlatformIcon } from './ChatPlatformIcon';
import { ChatTags } from './ChatTags';
import { Bot } from 'lucide-react';

export interface ChatListItemProps {
  chat: Chat;
  isActive: boolean;
  onClick: (chat: Chat) => void;
}

/**
 * Individual chat list item in the sidebar list. Memoized for performance.
 */
export const ChatListItem: React.FC<ChatListItemProps> = React.memo(({ chat, isActive, onClick }) => {
  const { t } = useTranslation();
  const channelId = chat.channelId;
  const channelType = chat.channelType ?? DEFAULT_CHANNEL_TYPE;

  
  // 判断是否是 agent 会话（channelId 以 -agent 结尾）
  const isAgentChat = channelId?.endsWith('-agent') ?? false;

  // Use unified hook for channel display info
  const { name, avatar, extra } = useChannelDisplay({
    channelId,
    channelType,
    // Skip fetch for special chat types
    skipFetch: false,
  });

  // Apply special display names for agent chats
  const displayName = name;
  const displayAvatar = avatar;

  // Get online status from extra (channel info)
  const visitorExtra = extra as ChannelVisitorExtra | undefined;
  const { visitorStatus, lastSeenMinutes } = useMemo((): { visitorStatus?: 'online' | 'offline' | 'away'; lastSeenMinutes?: number } => {
    // Priority: extra.is_online (from channel info API) > chat.visitorStatus (legacy)
    if (visitorExtra?.is_online !== undefined) {
      if (visitorExtra.is_online) {
        return { visitorStatus: 'online', lastSeenMinutes: undefined };
      }
      return { visitorStatus: 'offline', lastSeenMinutes: diffMinutesFromNow(visitorExtra.last_offline_time) ?? undefined };
    }
    // Fallback to chat.visitorStatus
    return { visitorStatus: chat.visitorStatus, lastSeenMinutes: chat.lastSeenMinutes };
  }, [visitorExtra?.is_online, visitorExtra?.last_offline_time, chat.visitorStatus, chat.lastSeenMinutes]);

  const handleClick = useCallback(() => { onClick(chat); }, [onClick, chat]);

  // Unread fade-out animation when transitioning from >0 to 0
  const prevUnreadRef = useRef<number>(chat.unreadCount);
  const [fadeOut, setFadeOut] = useState(false);
  useEffect(() => {
    let tid: ReturnType<typeof setTimeout> | null = null;
    const prev = prevUnreadRef.current;
    if (prev > 0 && chat.unreadCount === 0) {
      setFadeOut(true);
      tid = setTimeout(() => {
        setFadeOut(false);
        prevUnreadRef.current = 0;
      }, 220);
    } else {
      prevUnreadRef.current = chat.unreadCount;
    }
    return () => { if (tid) clearTimeout(tid); };
  }, [chat.unreadCount]);

  const unreadToDisplay = chat.unreadCount > 0 ? chat.unreadCount : prevUnreadRef.current;
  const tags = (extra as any)?.tags || [];
  return (
    <div
      className={`
        flex items-center p-3 rounded-lg cursor-pointer transition-colors duration-150
        ${isActive ? 'bg-blue-500 dark:bg-blue-600 text-white shadow-sm' : 'hover:bg-gray-100/70 dark:hover:bg-gray-700/70'}
      `}
      onClick={handleClick}
    >
      <ChatAvatar
        displayName={displayName}
        displayAvatar={displayAvatar}
        visitorStatus={visitorStatus}
        lastSeenMinutes={lastSeenMinutes}
        colorSeed={channelId}
      />

      <div className="flex-grow overflow-hidden">
        <div className="flex justify-between items-center">
          <h3 className={`text-sm font-semibold truncate flex items-center ${isActive ? 'text-white' : 'text-gray-800 dark:text-gray-200'}`}>
            <span className="truncate">{displayName}</span>
            {isAgentChat ? (
              <Bot className={`w-3.5 h-3.5 ml-1 flex-shrink-0 ${isActive ? 'text-blue-100' : 'text-purple-500 dark:text-purple-400'}`} />
            ) : (
              <ChatPlatformIcon platformType={(extra as any)?.platform_type ?? toPlatformType(chat.platform)} />
            )}
          </h3>
          <span className={`text-xs flex-shrink-0 ml-2 ${isActive ? 'text-blue-100' : 'text-gray-400 dark:text-gray-500'}`}>
            {formatWeChatConversationTime(chat.timestamp)}
          </span>
        </div>

        <div className="flex justify-between items-center mt-1">
          <p className={`text-xs truncate flex-1 ${isActive ? 'text-blue-100' : 'text-gray-500 dark:text-gray-400'}`}>
            {formatChatLastMessage(chat, t)}
          </p>
          {(chat.unreadCount > 0 || fadeOut) && (
            <div className={`min-w-[16px] h-4 bg-red-500 text-white text-[10px] font-medium rounded-full flex items-center justify-center px-1 flex-shrink-0 ml-2 transition-opacity duration-200 ${fadeOut && chat.unreadCount === 0 ? 'opacity-0' : 'opacity-100'}`}>
              {unreadToDisplay > 99 ? '99+' : unreadToDisplay}
            </div>
          )}
        </div>

        <ChatTags tags={tags} isActive={isActive} />
      </div>
    </div>
  );
});

ChatListItem.displayName = 'ChatListItem';
