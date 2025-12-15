import React, { useCallback, useMemo, useState, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import type { Chat } from '@/types';
import { useChatStore, chatSelectors } from '@/stores';
import { useSyncStore } from '@/stores/syncStore';
import { useChannelStore } from '@/stores/channelStore';
import { conversationsApi } from '@/services/conversationsApi';
import { wukongimWebSocketService } from '@/services/wukongimWebSocket';
import { getChannelKey } from '@/utils/channelUtils';
import { ChatListHeader } from '@/components/chat/ChatListHeader';
import { ChatListEmpty } from '@/components/chat/ChatListEmpty';
import { ChatListItem } from '@/components/chat/ChatListItem';
import { UnassignedChatListItem } from '@/components/chat/UnassignedChatListItem';
import { ChatListTabs, ChatTabType } from '@/components/chat/ChatListTabs';
import OnboardingSidebarPanel from '@/components/onboarding/OnboardingSidebarPanel';

// ============================================================================
// Main Component
// ============================================================================

/**
 * Props for the ChatList component
 */
interface ChatListProps {
  /** Currently active chat */
  activeChat?: Chat;
  /** Callback when a chat is selected */
  onChatSelect: (chat: Chat) => void;
  /** Active tab (controlled by parent if provided) */
  activeTab?: ChatTabType;
  /** Callback when tab changes */
  onTabChange?: (tab: ChatTabType) => void;
  /** Trigger to refresh lists (increment to trigger refresh) */
  refreshTrigger?: number;
  /** Channel info of the deleted chat (to remove from local state) */
  deletedChatChannel?: { channelId: string; channelType: number } | null;
}

/**
 * Custom hook for managing chat list filtering with search
 */
const useSearchFiltering = (chats: Chat[], searchQuery: string) => {
  return useMemo(() => {
    if (!searchQuery.trim()) return chats;
    
    const lowerQuery = searchQuery.toLowerCase();
    return chats.filter((chat: Chat) => {
      const baseId = chat.channelId || chat.id;
      const name = (chat.channelInfo?.name || `访客${String(baseId).slice(-4)}`).toLowerCase();
      return name.includes(lowerQuery) || chat.lastMessage.toLowerCase().includes(lowerQuery);
    });
  }, [chats, searchQuery]);
};

/**
 * Sort chats by timestamp (desc)
 */
const sortChatsByTimestamp = (chats: Chat[]): Chat[] => {
  return [...chats].sort((a, b) => {
    const aSec = a.lastTimestampSec ?? (a.timestamp ? Math.floor(new Date(a.timestamp).getTime() / 1000) : 0);
    const bSec = b.lastTimestampSec ?? (b.timestamp ? Math.floor(new Date(b.timestamp).getTime() / 1000) : 0);
    return bSec - aSec;
  });
};

/**
 * Chat list sidebar component
 * Displays a list of conversations with search and sync functionality
 *
 * Features:
 * - Tab filtering (Mine, Unassigned, All) - each tab has its own data source
 * - "我的": /conversations/my + 新消息创建的会话
 * - "未分配": /conversations/waiting
 * - "全部": /conversations/all
 * - Search filtering by visitor name or last message
 * - Real-time sync with WuKongIM
 * - Empty state when no conversations exist
 * - Optimized rendering with memoized sub-components
 */
const ChatListComponent: React.FC<ChatListProps> = ({ 
  activeChat, 
  onChatSelect,
  activeTab: controlledActiveTab,
  onTabChange: controlledOnTabChange,
  refreshTrigger,
  deletedChatChannel,
}) => {
  const { t } = useTranslation();
  
  // Store subscriptions - chats 用于存储新消息创建的会话
  const realtimeChats = useChatStore(chatSelectors.chats) ?? [];
  const searchQuery = useChatStore(chatSelectors.searchQuery) ?? '';
  const setSearchQuery = useChatStore(state => state.setSearchQuery);
  
  // Get convertWuKongIMToChat from syncStore
  const convertWuKongIMToChat = useSyncStore(state => state.convertWuKongIMToChat);
  
  // Get seedChannel from channelStore to cache channel info from API responses
  const seedChannel = useChannelStore(state => state.seedChannel);

  // Local state for tabs (used when not controlled by parent)
  const [internalActiveTab, setInternalActiveTab] = useState<ChatTabType>('mine');
  
  // Use controlled tab if provided, otherwise use internal state
  const activeTab = controlledActiveTab ?? internalActiveTab;
  const setActiveTab = controlledOnTabChange ?? setInternalActiveTab;
  
  // 每个 tab 独立的会话列表
  const [myChats, setMyChats] = useState<Chat[]>([]);
  const [unassignedChats, setUnassignedChats] = useState<Chat[]>([]);
  const [allChats, setAllChats] = useState<Chat[]>([]);
  
  // Loading state for each tab
  const [isLoadingMine, setIsLoadingMine] = useState(false);
  const [isLoadingUnassigned, setIsLoadingUnassigned] = useState(false);
  const [isLoadingAll, setIsLoadingAll] = useState(false);
  
  // Loading more state for pagination
  const [isLoadingMoreUnassigned, setIsLoadingMoreUnassigned] = useState(false);
  const [isLoadingMoreAll, setIsLoadingMoreAll] = useState(false);
  
  // Has more data for pagination
  const [hasMoreUnassigned, setHasMoreUnassigned] = useState(false);
  const [hasMoreAll, setHasMoreAll] = useState(false);
  
  // Track which tabs have been loaded (to prevent duplicate requests on mount)
  const loadedTabsRef = useRef<Set<ChatTabType>>(new Set());
  
  // Scroll container ref for infinite scroll
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  
  // 未分配数量（从 API 获取，监听 queue.updated 事件更新）
  const [unassignedCount, setUnassignedCount] = useState<number>(0);
  
  // 获取未分配数量的函数
  const fetchUnassignedCount = useCallback(async () => {
    try {
      const response = await conversationsApi.getWaitingQueueCount();
      // API 可能返回 { count: number } 或 { waiting: number }
      const count = response.waiting ?? 0;
      setUnassignedCount(count);
      console.log('📋 ChatList: Fetched unassigned count:', count, response);
    } catch (error) {
      console.error('📋 ChatList: Failed to fetch unassigned count:', error);
    }
  }, []);
  
  // 初始化时获取一次，并监听 queue.updated 事件
  useEffect(() => {
    // 立即获取一次
    fetchUnassignedCount();
    
    // 监听 queue.updated 事件
    const unsubscribe = wukongimWebSocketService.onQueueUpdated(() => {
      console.log('📋 ChatList: queue.updated event received, refreshing count');
      fetchUnassignedCount();
    });
    
    // 清理订阅
    return () => unsubscribe();
  }, [fetchUnassignedCount]);
  
  // 获取"我的"会话
  const fetchMyConversations = useCallback(async (force = false) => {
    if (!force && loadedTabsRef.current.has('mine')) return;
    loadedTabsRef.current.add('mine');
    
    setIsLoadingMine(true);
    try {
      const response = await conversationsApi.getMyConversations(1);
      if (response?.conversations) {
        const chats = response.conversations.map(conv => convertWuKongIMToChat(conv));
        setMyChats(sortChatsByTimestamp(chats));
        console.log(`📋 ChatList: Loaded "mine" tab, ${chats.length} conversations`);
        
        // 缓存频道信息，避免后续单独请求
        if (response.channels && response.channels.length > 0) {
          response.channels.forEach(channel => {
            if (channel.channel_id && channel.channel_type != null) {
              seedChannel(channel.channel_id, channel.channel_type, channel);
            }
          });
          console.log(`📋 ChatList: Cached ${response.channels.length} channels from "mine" tab`);
        }
      }
    } catch (error) {
      console.error('📋 ChatList: Failed to load "mine" conversations:', error);
    } finally {
      setIsLoadingMine(false);
    }
  }, [convertWuKongIMToChat, seedChannel]);
  
  // 每页会话数量
  const PAGE_SIZE = 20;
  
  // 获取"未分配"会话（首次加载）
  const fetchUnassignedConversations = useCallback(async () => {
    setIsLoadingUnassigned(true);
    try {
      const response = await conversationsApi.getWaitingConversations(20, PAGE_SIZE, 0);
      if (response?.conversations) {
        const chats = response.conversations.map(conv => convertWuKongIMToChat(conv));
        setUnassignedChats(sortChatsByTimestamp(chats));
        setHasMoreUnassigned(response.pagination?.has_next ?? false);
        console.log(`📋 ChatList: Loaded "unassigned" tab, ${chats.length} conversations, hasMore: ${response.pagination?.has_next}`);
        
        // 缓存频道信息，避免后续单独请求
        if (response.channels && response.channels.length > 0) {
          response.channels.forEach(channel => {
            if (channel.channel_id && channel.channel_type != null) {
              seedChannel(channel.channel_id, channel.channel_type, channel);
            }
          });
          console.log(`📋 ChatList: Cached ${response.channels.length} channels from "unassigned" tab`);
        }
      }
    } catch (error) {
      console.error('📋 ChatList: Failed to load "unassigned" conversations:', error);
    } finally {
      setIsLoadingUnassigned(false);
    }
  }, [convertWuKongIMToChat, seedChannel]);
  
  // 加载更多"未分配"会话
  const loadMoreUnassignedConversations = useCallback(async () => {
    if (isLoadingMoreUnassigned || !hasMoreUnassigned) return;
    
    setIsLoadingMoreUnassigned(true);
    try {
      const offset = unassignedChats.length;
      const response = await conversationsApi.getWaitingConversations(20, PAGE_SIZE, offset);
      if (response?.conversations) {
        const newChats = response.conversations.map(conv => convertWuKongIMToChat(conv));
        setUnassignedChats(prev => [...prev, ...newChats]);
        setHasMoreUnassigned(response.pagination?.has_next ?? false);
        console.log(`📋 ChatList: Loaded more "unassigned", +${newChats.length} conversations, hasMore: ${response.pagination?.has_next}`);
        
        // 缓存频道信息
        if (response.channels && response.channels.length > 0) {
          response.channels.forEach(channel => {
            if (channel.channel_id && channel.channel_type != null) {
              seedChannel(channel.channel_id, channel.channel_type, channel);
            }
          });
        }
      }
    } catch (error) {
      console.error('📋 ChatList: Failed to load more "unassigned" conversations:', error);
    } finally {
      setIsLoadingMoreUnassigned(false);
    }
  }, [isLoadingMoreUnassigned, hasMoreUnassigned, unassignedChats.length, convertWuKongIMToChat, seedChannel]);
  
  // 获取"全部"会话（每次切换到此 tab 都调用）
  const fetchAllConversations = useCallback(async () => {
    setIsLoadingAll(true);
    try {
      const response = await conversationsApi.getAllConversations(20, PAGE_SIZE, 0);
      if (response?.conversations) {
        const chats = response.conversations.map(conv => convertWuKongIMToChat(conv));
        setAllChats(sortChatsByTimestamp(chats));
        setHasMoreAll(response.pagination?.has_next ?? false);
        console.log(`📋 ChatList: Loaded "all" tab, ${chats.length} conversations, hasMore: ${response.pagination?.has_next}`);
        
        // 缓存频道信息，避免后续单独请求
        if (response.channels && response.channels.length > 0) {
          response.channels.forEach(channel => {
            if (channel.channel_id && channel.channel_type != null) {
              seedChannel(channel.channel_id, channel.channel_type, channel);
            }
          });
          console.log(`📋 ChatList: Cached ${response.channels.length} channels from "all" tab`);
        }
      }
    } catch (error) {
      console.error('📋 ChatList: Failed to load "all" conversations:', error);
    } finally {
      setIsLoadingAll(false);
    }
  }, [convertWuKongIMToChat, seedChannel]);
  
  // 加载更多"全部"会话
  const loadMoreAllConversations = useCallback(async () => {
    if (isLoadingMoreAll || !hasMoreAll) return;
    
    setIsLoadingMoreAll(true);
    try {
      const offset = allChats.length;
      const response = await conversationsApi.getAllConversations(20, PAGE_SIZE, offset);
      if (response?.conversations) {
        const newChats = response.conversations.map(conv => convertWuKongIMToChat(conv));
        setAllChats(prev => [...prev, ...newChats]);
        setHasMoreAll(response.pagination?.has_next ?? false);
        console.log(`📋 ChatList: Loaded more "all", +${newChats.length} conversations, hasMore: ${response.pagination?.has_next}`);
        
        // 缓存频道信息
        if (response.channels && response.channels.length > 0) {
          response.channels.forEach(channel => {
            if (channel.channel_id && channel.channel_type != null) {
              seedChannel(channel.channel_id, channel.channel_type, channel);
            }
          });
        }
      }
    } catch (error) {
      console.error('📋 ChatList: Failed to load more "all" conversations:', error);
    } finally {
      setIsLoadingMoreAll(false);
    }
  }, [isLoadingMoreAll, hasMoreAll, allChats.length, convertWuKongIMToChat, seedChannel]);
  
  // 根据当前 tab 获取对应数据（组件挂载时和 tab 切换时）
  useEffect(() => {
    if (activeTab === 'mine') {
      fetchMyConversations();
    } else if (activeTab === 'unassigned') {
      fetchUnassignedConversations();
    } else if (activeTab === 'all') {
      fetchAllConversations();
    }
  }, [activeTab, fetchMyConversations, fetchUnassignedConversations, fetchAllConversations]);
  
  // 当 refreshTrigger 变化时，强制刷新"我的"和"未分配"列表及数量
  const prevRefreshTriggerRef = useRef(refreshTrigger);
  useEffect(() => {
    // 只在 refreshTrigger 变化时触发（而不是初次挂载）
    if (refreshTrigger !== undefined && refreshTrigger !== prevRefreshTriggerRef.current) {
      prevRefreshTriggerRef.current = refreshTrigger;
      console.log('📋 ChatList: refreshTrigger changed, refreshing lists');
      // 强制刷新"我的"会话
      loadedTabsRef.current.delete('mine');
      fetchMyConversations(true);
      // 刷新未分配列表和数量
      fetchUnassignedConversations();
      fetchUnassignedCount();
    }
  }, [refreshTrigger, fetchMyConversations, fetchUnassignedConversations, fetchUnassignedCount]);
  
  // 追踪上一次处理的 deletedChatChannel，避免重复处理
  const lastDeletedChannelRef = useRef<string | null>(null);
  
  // 当 deletedChatChannel 变化时，从本地状态中移除该会话并选中下一个
  useEffect(() => {
    if (deletedChatChannel?.channelId && deletedChatChannel?.channelType != null) {
      const { channelId, channelType } = deletedChatChannel;
      const key = getChannelKey(channelId, channelType);
      
      // 避免重复处理同一个删除
      if (lastDeletedChannelRef.current === key) {
        return;
      }
      lastDeletedChannelRef.current = key;
      
      console.log('📋 ChatList: Removing deleted chat from local state:', key);
      
      // 从本地状态中移除（使用函数式更新，不依赖外部状态）
      setMyChats(prev => {
        const remaining = prev.filter(c => !(c.channelId === channelId && c.channelType === channelType));
        
        // 如果被删除的是当前选中的会话，选中下一个
        if (activeChat?.channelId === channelId && activeChat?.channelType === channelType && remaining.length > 0 && activeTab === 'mine') {
          const deletedIndex = prev.findIndex(c => c.channelId === channelId && c.channelType === channelType);
          const nextIndex = Math.min(deletedIndex, remaining.length - 1);
          const nextChat = remaining[Math.max(0, nextIndex)];
          console.log('📋 ChatList: Selecting next chat:', nextChat.channelId);
          // 使用 setTimeout 避免在 setState 回调中调用
          setTimeout(() => onChatSelect(nextChat), 0);
        }
        
        return remaining;
      });
      setAllChats(prev => prev.filter(c => !(c.channelId === channelId && c.channelType === channelType)));
    }
  }, [deletedChatChannel, activeChat, activeTab, onChatSelect]);
  
  // 合并"我的"会话：API 返回的 + 新消息创建的会话
  // 优先使用 realtimeChats 中的更新数据（包含最新的 lastMessage 和 unreadCount）
  // 但只在 realtimeChats 的数据比 API 的更新时才使用
  const mergedMyChats = useMemo(() => {
    // 建立 realtimeChats 的 key -> chat 映射，用于快速查找
    const realtimeChatMap = new Map<string, Chat>();
    realtimeChats.forEach(c => {
      const key = getChannelKey(c.channelId, c.channelType);
      realtimeChatMap.set(key, c);
    });
    
    // 合并 API 会话，如果 realtimeChats 中有更新且更新时间更晚则使用更新后的数据
    const mergedFromApi = myChats.map(apiChat => {
      const key = getChannelKey(apiChat.channelId, apiChat.channelType);
      const realtimeChat = realtimeChatMap.get(key);
      if (realtimeChat) {
        const apiTimestamp = apiChat.lastTimestampSec ?? 0;
        const realtimeTimestamp = realtimeChat.lastTimestampSec ?? 0;
        
        // 只在 realtimeChat 的时间戳更新且有 lastMessage 时才使用它
        if (realtimeTimestamp > apiTimestamp && realtimeChat.lastMessage) {
          return {
            ...apiChat,
            lastMessage: realtimeChat.lastMessage,
            timestamp: realtimeChat.timestamp,
            lastTimestampSec: realtimeChat.lastTimestampSec,
            unreadCount: realtimeChat.unreadCount,
            priority: realtimeChat.priority,
          };
        }
      }
      return apiChat;
    });
    
    // 获取 API 返回的会话 keys
    const apiChatKeys = new Set(myChats.map(c => getChannelKey(c.channelId, c.channelType)));
    
    // 过滤出不在 API 结果中的实时会话（新消息创建的，且有实际内容）
    const newRealtimeChats = realtimeChats.filter(
      c => !apiChatKeys.has(getChannelKey(c.channelId, c.channelType)) && c.lastMessage
    );
    
    // 合并并排序
    return sortChatsByTimestamp([...mergedFromApi, ...newRealtimeChats]);
  }, [myChats, realtimeChats]);

  // 合并"全部"会话：API 返回的 + 实时更新
  // 优先使用 realtimeChats 中的更新数据（包含最新的 lastMessage 和 unreadCount）
  // 但只在 realtimeChats 的数据比 API 的更新时才使用
  const mergedAllChats = useMemo(() => {
    // 建立 realtimeChats 的 key -> chat 映射，用于快速查找
    const realtimeChatMap = new Map<string, Chat>();
    realtimeChats.forEach(c => {
      const key = getChannelKey(c.channelId, c.channelType);
      realtimeChatMap.set(key, c);
    });
    
    // "全部"tab 不需要过滤已删除的会话，因为它显示所有服务过的会话（包括已关闭的）
    // 直接使用 allChats（从 API 获取的数据）
    
    // 合并 API 会话，如果 realtimeChats 中有更新且更新时间更晚则使用更新后的数据
    const mergedFromApi = allChats.map(apiChat => {
      const key = getChannelKey(apiChat.channelId, apiChat.channelType);
      const realtimeChat = realtimeChatMap.get(key);
      if (realtimeChat) {
        const apiTimestamp = apiChat.lastTimestampSec ?? 0;
        const realtimeTimestamp = realtimeChat.lastTimestampSec ?? 0;
        
        // 只在 realtimeChat 的时间戳更新且有 lastMessage 时才使用它
        if (realtimeTimestamp > apiTimestamp && realtimeChat.lastMessage) {
          return {
            ...apiChat,
            lastMessage: realtimeChat.lastMessage,
            timestamp: realtimeChat.timestamp,
            lastTimestampSec: realtimeChat.lastTimestampSec,
            unreadCount: realtimeChat.unreadCount,
            priority: realtimeChat.priority,
          };
        }
      }
      return apiChat;
    });
    
    // 获取 API 返回的会话 keys
    const apiChatKeys = new Set(allChats.map(c => getChannelKey(c.channelId, c.channelType)));
    
    // 过滤出不在 API 结果中的实时会话（新消息创建的，且有实际内容）
    // "全部"tab 不过滤已删除的会话
    const newRealtimeChats = realtimeChats.filter(
      c => !apiChatKeys.has(getChannelKey(c.channelId, c.channelType)) && c.lastMessage
    );
    
    // 合并并排序
    return sortChatsByTimestamp([...mergedFromApi, ...newRealtimeChats]);
  }, [allChats, realtimeChats]);

  // Get the appropriate chat list based on active tab
  const getChatsForTab = useCallback((): Chat[] => {
    switch (activeTab) {
      case 'mine':
        return mergedMyChats;
      case 'unassigned':
        return unassignedChats;
      case 'all':
        return mergedAllChats;
      default:
        return mergedMyChats;
    }
  }, [activeTab, mergedMyChats, unassignedChats, mergedAllChats]);

  // Calculate counts for tabs
  // "我的" tab 显示会话数量，"未分配" tab 显示等待数量
  const counts = useMemo(() => {
    return {
      mine: mergedMyChats.length,
      unassigned: unassignedCount,
    };
  }, [mergedMyChats.length, unassignedCount]);

  // Get chats for current tab
  const tabChats = getChatsForTab();
  
  // Apply search filtering
  const filteredChats = useSearchFiltering(tabChats, searchQuery);

  // Memoized callbacks to prevent unnecessary re-renders
  const handleSearchChange = useCallback((value: string) => {
    setSearchQuery(value);
  }, [setSearchQuery]);

  const handleTabChange = useCallback((tab: ChatTabType) => {
    setActiveTab(tab);
  }, [setActiveTab]);

  // Handle chat click - clear unread count locally and call parent handler
  const handleChatClick = useCallback((chat: Chat) => {
    // Don't clear unread for unassigned tab
    if (activeTab !== 'unassigned' && (chat.unreadCount || 0) > 0) {
      const updateChatUnread = (chats: Chat[]) => 
        chats.map(c => 
          c.channelId === chat.channelId && c.channelType === chat.channelType
            ? { ...c, unreadCount: 0 }
            : c
        );
      
      // Update local state for the appropriate tab
      setMyChats(updateChatUnread);
      setAllChats(updateChatUnread);
    }
    
    // Call parent handler
    onChatSelect(chat);
  }, [activeTab, onChatSelect]);

  // Loading state based on active tab
  const isLoading = useMemo(() => {
    switch (activeTab) {
      case 'mine':
        return isLoadingMine;
      case 'unassigned':
        return isLoadingUnassigned;
      case 'all':
        return isLoadingAll;
      default:
        return false;
    }
  }, [activeTab, isLoadingMine, isLoadingUnassigned, isLoadingAll]);
  
  // 是否正在加载更多
  const isLoadingMore = useMemo(() => {
    switch (activeTab) {
      case 'unassigned':
        return isLoadingMoreUnassigned;
      case 'all':
        return isLoadingMoreAll;
      default:
        return false;
    }
  }, [activeTab, isLoadingMoreUnassigned, isLoadingMoreAll]);
  
  // 是否还有更多数据
  const hasMore = useMemo(() => {
    switch (activeTab) {
      case 'unassigned':
        return hasMoreUnassigned;
      case 'all':
        return hasMoreAll;
      default:
        return false;
    }
  }, [activeTab, hasMoreUnassigned, hasMoreAll]);
  
  // 滚动事件处理 - 上拉加载更多
  const handleScroll = useCallback((e: React.UIEvent<HTMLDivElement>) => {
    const target = e.currentTarget;
    const scrollTop = target.scrollTop;
    const scrollHeight = target.scrollHeight;
    const clientHeight = target.clientHeight;
    
    // 当滚动到距离底部 100px 时触发加载更多
    const threshold = 100;
    const isNearBottom = scrollHeight - scrollTop - clientHeight < threshold;
    
    if (isNearBottom && !isLoadingMore && hasMore) {
      if (activeTab === 'unassigned') {
        loadMoreUnassignedConversations();
      } else if (activeTab === 'all') {
        loadMoreAllConversations();
      }
    }
  }, [activeTab, isLoadingMore, hasMore, loadMoreUnassignedConversations, loadMoreAllConversations]);

  return (
    <div className="w-72 bg-white/90 dark:bg-gray-800/90 backdrop-blur-lg border-r border-gray-200/60 dark:border-gray-700/60 flex flex-col">
      {/* Header with search */}
      <ChatListHeader
        searchQuery={searchQuery}
        onSearchChange={handleSearchChange}
      />

      {/* Tabs */}
      <ChatListTabs 
        activeTab={activeTab} 
        onTabChange={handleTabChange} 
        counts={counts}
      />

      {/* Chat list */}
      <div 
        ref={scrollContainerRef}
        className="flex-grow overflow-y-auto p-2 space-y-1" 
        style={{ height: 0 }}
        onScroll={handleScroll}
      >
        {filteredChats.length === 0 ? (
          <ChatListEmpty isSyncing={isLoading} />
        ) : (
          <>
            {filteredChats.map((chat: Chat) => (
              activeTab === 'unassigned' ? (
                <UnassignedChatListItem
                  key={chat.id}
                  chat={chat}
                  isActive={activeChat?.id === chat.id}
                  onClick={onChatSelect}
                />
              ) : (
                <ChatListItem
                  key={chat.id}
                  chat={chat}
                  isActive={activeChat?.id === chat.id}
                  onClick={handleChatClick}
                />
              )
            ))}
            {/* 加载更多提示 */}
            {isLoadingMore && (
              <div className="flex items-center justify-center py-3">
                <div className="w-4 h-4 border-2 border-gray-300 dark:border-gray-600 border-t-blue-500 rounded-full animate-spin" />
                <span className="ml-2 text-xs text-gray-500 dark:text-gray-400">{t('common.loadingMore')}</span>
              </div>
            )}
            {/* 没有更多数据提示 */}
            {!hasMore && filteredChats.length > 0 && (activeTab === 'unassigned' || activeTab === 'all') && (
              <div className="flex items-center justify-center py-3">
                <span className="text-xs text-gray-400 dark:text-gray-500">{t('common.noMore')}</span>
              </div>
            )}
          </>
        )}
      </div>

      {/* Onboarding Panel */}
      <OnboardingSidebarPanel />
    </div>
  );
};

// Wrap with React.memo to prevent unnecessary re-renders
const ChatList = React.memo(ChatListComponent);
ChatList.displayName = 'ChatList';

export default ChatList;
