import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import type { Chat, ChatStatus, WuKongIMConversation, WuKongIMConversationSyncResponse } from '@/types';
import { WuKongIMApiService, WuKongIMUtils } from '@/services/wukongimApi';
import { getChannelKey } from '@/utils/channelUtils';
import { useChannelStore } from './channelStore';
import { useConversationStore } from './conversationStore';
import {
  DEFAULT_CHANNEL_TYPE,
  CHAT_STATUS as CHAT_STATUS_CONST,
  CHAT_PRIORITY as CHAT_PRIORITY_CONST,
  STORAGE_KEYS,
} from '@/constants';

/**
 * Sync Store State Interface
 * Manages conversation synchronization with WuKongIM
 */
interface SyncState {
  // 同步状态
  isSyncing: boolean;
  lastSyncTime: string | null;
  syncVersion: number;
  syncError: string | null;
  hasSyncedOnce: boolean;

  // Actions - 同步控制
  setSyncing: (syncing: boolean) => void;
  setSyncError: (error: string | null) => void;

  // Actions - 同步方法
  syncConversations: () => Promise<void>;
  syncConversationsIfNeeded: () => Promise<void>;
  forceSyncConversations: () => Promise<void>;

  // Actions - 转换工具
  convertWuKongIMToChat: (conversation: WuKongIMConversation) => Chat;

  // Actions - 清理
  clearSyncStore: () => void;
}

export const useSyncStore = create<SyncState>()(
  devtools(
    (set, get) => ({
      // Initial state
      isSyncing: false,
      lastSyncTime: null,
      syncVersion: 0,
      syncError: null,
      hasSyncedOnce: false,

      // Sync control
      setSyncing: (syncing) => set({ isSyncing: syncing }, false, 'setSyncing'),

      setSyncError: (error) => set({ syncError: error }, false, 'setSyncError'),

      // Convert WuKongIM conversation to internal Chat format
      convertWuKongIMToChat: (conversation: WuKongIMConversation): Chat => {
        // Use the latest message by highest message_seq to ensure we pick the true last message
        const latestWkMsg =
          Array.isArray(conversation.recents) && conversation.recents.length > 0
            ? conversation.recents.reduce(
                (acc, m) => (!acc || m.message_seq > acc.message_seq ? m : acc),
                conversation.recents[0]
              )
            : null;

        // Debug: Log the latest message to see if stream_data is present
        if (latestWkMsg) {
          console.log('📋 convertWuKongIMToChat - Latest message:', {
            message_seq: latestWkMsg.message_seq,
            has_stream_data: !!latestWkMsg.stream_data,
            stream_data_preview: latestWkMsg.stream_data ? latestWkMsg.stream_data.substring(0, 50) : 'N/A',
            payload_type: typeof latestWkMsg.payload,
            payload_preview:
              typeof latestWkMsg.payload === 'object'
                ? (latestWkMsg.payload as any).content?.substring(0, 50)
                : latestWkMsg.payload?.substring(0, 50),
          });
        }

        const lastMessage = latestWkMsg ? WuKongIMUtils.extractMessageContent(latestWkMsg) : '暂无消息';
        const payloadType = latestWkMsg ? (typeof latestWkMsg.payload === 'object' ? (latestWkMsg.payload as any)?.type : undefined) : undefined;

        const channelId = conversation.channel_id;
        const channelType = conversation.channel_type ?? DEFAULT_CHANNEL_TYPE;

        // Derive basic presentation fields without fetching/seeding ChannelInfo here
        const platform = WuKongIMUtils.getPlatformFromChannelType(channelType);

        return {
          id: getChannelKey(channelId, channelType),
          platform,
          lastMessage,
          payloadType,
          timestamp: new Date(conversation.timestamp * 1000).toISOString(),
          lastTimestampSec: conversation.timestamp,
          status: CHAT_STATUS_CONST.ACTIVE as ChatStatus,
          unreadCount: conversation.unread,
          channelId: conversation.channel_id,
          channelType: conversation.channel_type ?? DEFAULT_CHANNEL_TYPE,
          lastMsgSeq: conversation.last_msg_seq,
          tags: [],
          priority: conversation.unread > 0 ? CHAT_PRIORITY_CONST.HIGH : CHAT_PRIORITY_CONST.NORMAL,
          lastSeenMinutes: undefined,
          metadata: {},
        };
      },

      // Sync conversations from WuKongIM
      syncConversations: async () => {
        const { setSyncing, setSyncError, syncVersion, convertWuKongIMToChat } = get();

        setSyncing(true);
        setSyncError(null);

        try {
          let response: WuKongIMConversationSyncResponse;

          response = await WuKongIMApiService.syncConversationsInitial();

          // Debug: Log sync response to see if stream_data is present
          console.log('📋 syncConversations - API response:', {
            conversationCount: response.conversations.length,
            conversations: response.conversations.map((conv) => ({
              channel_id: conv.channel_id,
              recentsCount: conv.recents.length,
              recents: conv.recents.map((msg) => ({
                message_seq: msg.message_seq,
                has_stream_data: !!msg.stream_data,
                stream_data_preview: msg.stream_data ? msg.stream_data.substring(0, 50) : 'N/A',
                payload_type: typeof msg.payload,
              })),
            })),
          });

          // 转换 WuKongIM 对话为内部格式
          const convertedChats = response.conversations.map((conv) => convertWuKongIMToChat(conv));

          // Merge existing visitor/channel info to prevent losing data on navigation
          const conversationStore = useConversationStore.getState();
          const existingChats = conversationStore.chats;
          const existingMap = new Map(existingChats.map((c) => [getChannelKey(c.channelId, c.channelType), c]));
          const channelStore = useChannelStore.getState();
          
          // 新会话的 key 集合
          const newChatKeys = new Set(convertedChats.map((c) => getChannelKey(c.channelId, c.channelType)));
          
          // 合并新会话（保留现有信息）
          const mergedChats = convertedChats.map((chat) => {
            const key = getChannelKey(chat.channelId, chat.channelType);
            const prev = existingMap.get(key);
            const cached = channelStore.getChannel(chat.channelId, chat.channelType);
            return {
              ...chat,
              channelInfo: prev?.channelInfo ?? cached ?? chat.channelInfo,
              visitorStatus: prev?.visitorStatus ?? chat.visitorStatus,
              // Preserve lastSeenMinutes if it was a meaningful value (>0); avoid carrying over 0 which renders as "刚刚"
              lastSeenMinutes:
                prev?.lastSeenMinutes != null && prev.lastSeenMinutes !== 0 ? prev.lastSeenMinutes : chat.lastSeenMinutes,
              tags: prev?.tags ?? chat.tags,
            } as Chat;
          });
          
          // 保留现有但不在新结果中的会话（可能来自其他 API 如 /conversations/my）
          const preservedChats = existingChats.filter((c) => !newChatKeys.has(getChannelKey(c.channelId, c.channelType)));
          
          // 合并所有会话
          const allChats = [...mergedChats, ...preservedChats];

          // Sort conversations by lastTimestampSec (desc)
          const sortedChats = allChats.sort((a, b) => {
            const aSec = a.lastTimestampSec ?? (a.timestamp ? Math.floor(new Date(a.timestamp).getTime() / 1000) : 0);
            const bSec = b.lastTimestampSec ?? (b.timestamp ? Math.floor(new Date(b.timestamp).getTime() / 1000) : 0);
            return bSec - aSec;
          });

          // 更新 conversationStore 的 chats
          conversationStore.setChats(sortedChats);

          // 更新本地状态
          const maxVersion = Math.max(...response.conversations.map((c) => c.version), syncVersion);
          set(
            {
              syncVersion: maxVersion,
              lastSyncTime: new Date().toISOString(),
              isSyncing: false,
              syncError: null,
              hasSyncedOnce: true,
            },
            false,
            'syncConversationsSuccess'
          );
        } catch (error) {
          console.error('同步对话失败:', error);
          const errorMessage = error instanceof Error ? error.message : '同步失败';
          setSyncError(errorMessage);
          setSyncing(false);
        }
      },

      // 仅在未同步过时同步会话列表
      syncConversationsIfNeeded: async () => {
        const { hasSyncedOnce, isSyncing, syncConversations } = get();
        if (hasSyncedOnce || isSyncing) {
          console.log('📋 syncConversationsIfNeeded: Skipping sync (already synced or syncing)', { hasSyncedOnce, isSyncing });
          return;
        }
        console.log('📋 syncConversationsIfNeeded: First time sync');
        await syncConversations();
      },

      // 强制同步会话列表（用于 WebSocket 重连后）
      forceSyncConversations: async () => {
        console.log('📋 forceSyncConversations: Force syncing conversations after reconnect');
        await get().syncConversations();
      },

      // Clear store
      clearSyncStore: () => {
        set(
          {
            isSyncing: false,
            lastSyncTime: null,
            syncVersion: 0,
            syncError: null,
            hasSyncedOnce: false,
          },
          false,
          'clearSyncStore'
        );
      },
    }),
    { name: STORAGE_KEYS.SYNC || 'SyncStore' }
  )
);

// Selectors for optimized subscriptions
export const syncSelectors = {
  isSyncing: (state: SyncState) => state.isSyncing,
  lastSyncTime: (state: SyncState) => state.lastSyncTime,
  syncVersion: (state: SyncState) => state.syncVersion,
  syncError: (state: SyncState) => state.syncError,
  hasSyncedOnce: (state: SyncState) => state.hasSyncedOnce,
};
