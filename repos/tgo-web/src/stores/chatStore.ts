/**
 * ChatStore - Aggregation layer for chat-related stores
 *
 * This store acts as a facade/aggregation layer that:
 * 1. Maintains backward compatibility with existing code
 * 2. Coordinates cross-store communication
 * 3. Provides unified access to conversation, message, and sync functionality
 *
 * The actual state is managed by:
 * - conversationStore: Chat list, active chat, search
 * - messageStore: Real-time messages, historical messages, streaming
 * - syncStore: WuKongIM synchronization
 */

import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';
import type { Chat, Message, ChatStatus, WuKongIMConversation, WuKongIMMessage, ChannelInfo } from '@/types';
import { MessagePayloadType, isChannelRefreshSystemMessage } from '@/types';

import { useConversationStore } from './conversationStore';
import { useMessageStore } from './messageStore';
import { useSyncStore } from './syncStore';
import { useChannelStore } from './channelStore';
import { useOnboardingStore } from './onboardingStore';

import { WuKongIMUtils } from '@/services/wukongimApi';
import { getChannelKey, isSameChannel } from '@/utils/channelUtils';
import { CHANNEL_TYPE, DEFAULT_CHANNEL_TYPE, MESSAGE_SENDER_TYPE, CHAT_STATUS as CHAT_STATUS_CONST, CHAT_PRIORITY as CHAT_PRIORITY_CONST, STORAGE_KEYS } from '@/constants';

// Re-export StreamEndReason for backward compatibility
export { StreamEndReason } from './messageStore';
export type { StreamEndReasonType } from './messageStore';

/**
 * ChatStore State Interface (Aggregated)
 * Provides backward-compatible interface while delegating to split stores
 */
interface ChatState {
  // ============================================================================
  // Conversation Store Proxy (会话列表)
  // ============================================================================
  chats: Chat[];
  activeChat: Chat | null;
  searchQuery: string;

  setChats: (chats: Chat[]) => void;
  setActiveChat: (chat: Chat | null) => void;
  setSearchQuery: (query: string) => void;
  createChat: (_visitorName: string, platform: string) => void;
  createChatByChannel: (channelId: string, channelType: number, options?: { platform?: string; name?: string; avatar?: string }) => Chat;
  deleteChat: (chatId: string) => void;
  updateChatStatus: (chatId: string, status: string) => void;
  getFilteredChats: () => Chat[];
  getChatById: (chatId: string) => Chat | undefined;
  updateConversationLastMessage: (channelId: string, channelType: number, message: Message) => void;
  moveConversationToTop: (channelId: string, channelType: number) => void;
  incrementUnreadCount: (channelId: string, channelType: number) => void;
  clearConversationUnread: (channelId: string, channelType: number) => Promise<void>;

  // ============================================================================
  // Message Store Proxy (消息管理)
  // ============================================================================
  messages: Message[];
  isLoading: boolean;
  isSending: boolean;
  historicalMessages: Record<string, WuKongIMMessage[]>;
  isLoadingHistory: boolean;
  historyError: string | null;
  hasMoreHistory: Record<string, boolean>;
  nextHistorySeq: Record<string, number>;
  hasMoreNewerHistory: Record<string, boolean>;
  nextNewerSeq: Record<string, number>;
  isStreamingInProgress: boolean;
  streamingClientMsgNo: string | null;
  targetMessageLocation: { channelId: string; channelType: number; messageSeq: number } | null;

  addMessage: (message: Message) => void;
  updateMessageByClientMsgNo: (clientMsgNo: string, patch: Partial<Message>) => void;
  loadMessages: (chatId: string) => Promise<void>;
  setLoading: (loading: boolean) => void;
  setSending: (sending: boolean) => void;
  loadHistoricalMessages: (channelId: string, channelType: number) => Promise<void>;
  loadMoreHistory: (channelId: string, channelType: number) => Promise<void>;
  loadNewerHistory: (channelId: string, channelType: number) => Promise<void>;
  loadMessageContext: (channelId: string, channelType: number, targetSeq: number, totalLimit?: number) => Promise<void>;
  clearHistoricalMessages: (channelId: string, channelType: number) => void;
  setLoadingHistory: (loading: boolean) => void;
  setHistoryError: (error: string | null) => void;
  getChannelMessages: (channelId: string, channelType: number) => WuKongIMMessage[];
  appendStreamMessageContent: (clientMsgNo: string, content: string) => void;
  markStreamMessageEnd: (clientMsgNo: string, error?: string) => void;
  cancelStreamingMessage: () => Promise<void>;
  setTargetMessageLocation: (loc: { channelId: string; channelType: number; messageSeq: number } | null) => void;

  // ============================================================================
  // Sync Store Proxy (同步管理)
  // ============================================================================
  isSyncing: boolean;
  lastSyncTime: string | null;
  syncVersion: number;
  syncError: string | null;
  hasSyncedOnce: boolean;

  syncConversations: () => Promise<void>;
  syncConversationsIfNeeded: () => Promise<void>;
  forceSyncConversations: () => Promise<void>;
  setSyncing: (syncing: boolean) => void;
  setSyncError: (error: string | null) => void;
  convertWuKongIMToChat: (conversation: WuKongIMConversation) => Chat;

  // ============================================================================
  // Cross-Store Coordination (跨 store 协调)
  // ============================================================================
  initializeStore: () => Promise<void>;
  handleRealtimeMessage: (message: Message) => void;
  applyChannelInfo: (channelId: string, channelType: number, info: ChannelInfo) => void;
  syncChannelInfoAcrossUI: (channelId: string, channelType: number) => Promise<ChannelInfo | null>;
  clearStore: () => void;
}

/**
 * Helper to get current state from split stores with safe defaults
 */
const getAggregatedState = () => {
  const convState = useConversationStore.getState();
  const msgState = useMessageStore.getState();
  const syncState = useSyncStore.getState();

  return {
    // Conversation (with safe defaults)
    chats: convState?.chats ?? [],
    activeChat: convState?.activeChat ?? null,
    searchQuery: convState?.searchQuery ?? '',
    // Message (with safe defaults)
    messages: msgState?.messages ?? [],
    isLoading: msgState?.isLoading ?? false,
    isSending: msgState?.isSending ?? false,
    historicalMessages: msgState?.historicalMessages ?? {},
    isLoadingHistory: msgState?.isLoadingHistory ?? false,
    historyError: msgState?.historyError ?? null,
    hasMoreHistory: msgState?.hasMoreHistory ?? {},
    nextHistorySeq: msgState?.nextHistorySeq ?? {},
    hasMoreNewerHistory: msgState?.hasMoreNewerHistory ?? {},
    nextNewerSeq: msgState?.nextNewerSeq ?? {},
    isStreamingInProgress: msgState?.isStreamingInProgress ?? false,
    streamingClientMsgNo: msgState?.streamingClientMsgNo ?? null,
    targetMessageLocation: msgState?.targetMessageLocation ?? null,
    // Sync (with safe defaults)
    isSyncing: syncState?.isSyncing ?? false,
    lastSyncTime: syncState?.lastSyncTime ?? null,
    syncVersion: syncState?.syncVersion ?? 0,
    syncError: syncState?.syncError ?? null,
    hasSyncedOnce: syncState?.hasSyncedOnce ?? false,
  };
};

export const useChatStore = create<ChatState>()(
  devtools(
    persist(
      (set, get) => {
        // Get initial state from split stores
        const initialState = getAggregatedState();

        return {
          // ====================================================================
          // Initial State (from split stores)
          // ====================================================================
          ...initialState,

          // ====================================================================
          // Conversation Store Proxies
          // ====================================================================
          setChats: (chats) => {
            useConversationStore.getState().setChats(chats);
            set({ chats }, false, 'setChats');
          },
          setActiveChat: (chat) => {
            useConversationStore.getState().setActiveChat(chat);
            set({ activeChat: chat }, false, 'setActiveChat');
            if (chat) {
              useMessageStore.getState().loadMessages(chat.id);
            }
          },
          setSearchQuery: (query) => {
            useConversationStore.getState().setSearchQuery(query);
            set({ searchQuery: query }, false, 'setSearchQuery');
          },
          createChat: (visitorName, platform) => {
            useConversationStore.getState().createChat(visitorName, platform);
            set({ chats: useConversationStore.getState().chats }, false, 'createChat');
          },
          createChatByChannel: (channelId, channelType, options) => {
            const result = useConversationStore.getState().createChatByChannel(channelId, channelType, options);
            set({ chats: useConversationStore.getState().chats }, false, 'createChatByChannel');
            return result;
          },
          deleteChat: (chatId) => {
            useConversationStore.getState().deleteChat(chatId);
            const convState = useConversationStore.getState();
            set({ chats: convState.chats, activeChat: convState.activeChat }, false, 'deleteChat');
          },
          updateChatStatus: (chatId, status) => {
            useConversationStore.getState().updateChatStatus(chatId, status);
            set({ chats: useConversationStore.getState().chats }, false, 'updateChatStatus');
          },
          getFilteredChats: () => useConversationStore.getState().getFilteredChats(),
          getChatById: (chatId) => useConversationStore.getState().getChatById(chatId),
          updateConversationLastMessage: (channelId, channelType, message) => {
            useConversationStore.getState().updateConversationLastMessage(channelId, channelType, message);
            set({ chats: useConversationStore.getState().chats }, false, 'updateConversationLastMessage');
          },
          moveConversationToTop: (channelId, channelType) => {
            useConversationStore.getState().moveConversationToTop(channelId, channelType);
            set({ chats: useConversationStore.getState().chats }, false, 'moveConversationToTop');
          },
          incrementUnreadCount: (channelId, channelType) => {
            useConversationStore.getState().incrementUnreadCount(channelId, channelType);
            set({ chats: useConversationStore.getState().chats }, false, 'incrementUnreadCount');
          },
          clearConversationUnread: async (channelId, channelType) => {
            await useConversationStore.getState().clearConversationUnread(channelId, channelType);
            set({ chats: useConversationStore.getState().chats }, false, 'clearConversationUnread');
          },

          // ====================================================================
          // Message Store Proxies
          // ====================================================================
          addMessage: (message) => {
            useMessageStore.getState().addMessage(message);
            set({ messages: useMessageStore.getState().messages }, false, 'addMessage');
          },
          updateMessageByClientMsgNo: (clientMsgNo, patch) => {
            useMessageStore.getState().updateMessageByClientMsgNo(clientMsgNo, patch);
            set({ messages: useMessageStore.getState().messages }, false, 'updateMessageByClientMsgNo');
          },
          loadMessages: async (chatId) => {
            await useMessageStore.getState().loadMessages(chatId);
            set({ messages: useMessageStore.getState().messages, isLoading: useMessageStore.getState().isLoading }, false, 'loadMessages');
          },
          setLoading: (loading) => {
            useMessageStore.getState().setLoading(loading);
            set({ isLoading: loading }, false, 'setLoading');
          },
          setSending: (sending) => {
            useMessageStore.getState().setSending(sending);
            set({ isSending: sending }, false, 'setSending');
          },
          loadHistoricalMessages: async (channelId, channelType) => {
            await useMessageStore.getState().loadHistoricalMessages(channelId, channelType);
            const msgState = useMessageStore.getState();
            set({
              historicalMessages: msgState.historicalMessages,
              hasMoreHistory: msgState.hasMoreHistory,
              nextHistorySeq: msgState.nextHistorySeq,
              isLoadingHistory: msgState.isLoadingHistory,
            }, false, 'loadHistoricalMessages');
          },
          loadMoreHistory: async (channelId, channelType) => {
            await useMessageStore.getState().loadMoreHistory(channelId, channelType);
            const msgState = useMessageStore.getState();
            set({
              historicalMessages: msgState.historicalMessages,
              hasMoreHistory: msgState.hasMoreHistory,
              nextHistorySeq: msgState.nextHistorySeq,
              isLoadingHistory: msgState.isLoadingHistory,
            }, false, 'loadMoreHistory');
          },
          loadNewerHistory: async (channelId, channelType) => {
            await useMessageStore.getState().loadNewerHistory(channelId, channelType);
            const msgState = useMessageStore.getState();
            set({
              historicalMessages: msgState.historicalMessages,
              hasMoreNewerHistory: msgState.hasMoreNewerHistory,
              nextNewerSeq: msgState.nextNewerSeq,
            }, false, 'loadNewerHistory');
          },
          loadMessageContext: async (channelId, channelType, targetSeq, totalLimit) => {
            await useMessageStore.getState().loadMessageContext(channelId, channelType, targetSeq, totalLimit);
            const msgState = useMessageStore.getState();
            set({
              historicalMessages: msgState.historicalMessages,
              hasMoreHistory: msgState.hasMoreHistory,
              nextHistorySeq: msgState.nextHistorySeq,
              hasMoreNewerHistory: msgState.hasMoreNewerHistory,
              nextNewerSeq: msgState.nextNewerSeq,
              isLoadingHistory: msgState.isLoadingHistory,
            }, false, 'loadMessageContext');
          },
          clearHistoricalMessages: (channelId, channelType) => {
            useMessageStore.getState().clearHistoricalMessages(channelId, channelType);
            const msgState = useMessageStore.getState();
            set({
              historicalMessages: msgState.historicalMessages,
              hasMoreHistory: msgState.hasMoreHistory,
              nextHistorySeq: msgState.nextHistorySeq,
              hasMoreNewerHistory: msgState.hasMoreNewerHistory,
              nextNewerSeq: msgState.nextNewerSeq,
            }, false, 'clearHistoricalMessages');
          },
          setLoadingHistory: (loading) => {
            useMessageStore.getState().setLoadingHistory(loading);
            set({ isLoadingHistory: loading }, false, 'setLoadingHistory');
          },
          setHistoryError: (error) => {
            useMessageStore.getState().setHistoryError(error);
            set({ historyError: error }, false, 'setHistoryError');
          },
          getChannelMessages: (channelId, channelType) =>
            useMessageStore.getState().getChannelMessages(channelId, channelType),
          appendStreamMessageContent: (clientMsgNo, content) => {
            useMessageStore.getState().appendStreamMessageContent(clientMsgNo, content);
            const msgState = useMessageStore.getState();
            set({
              messages: msgState.messages,
              historicalMessages: msgState.historicalMessages,
            }, false, 'appendStreamMessageContent');
          },
          markStreamMessageEnd: (clientMsgNo, error) => {
            useMessageStore.getState().markStreamMessageEnd(clientMsgNo, error);
            const msgState = useMessageStore.getState();
            set({
              messages: msgState.messages,
              historicalMessages: msgState.historicalMessages,
              isStreamingInProgress: msgState.isStreamingInProgress,
              streamingClientMsgNo: msgState.streamingClientMsgNo,
            }, false, 'markStreamMessageEnd');
          },
          cancelStreamingMessage: async () => {
            await useMessageStore.getState().cancelStreamingMessage();
            const msgState = useMessageStore.getState();
            set({
              isStreamingInProgress: msgState.isStreamingInProgress,
              streamingClientMsgNo: msgState.streamingClientMsgNo,
            }, false, 'cancelStreamingMessage');
          },
          setTargetMessageLocation: (loc) => {
            useMessageStore.getState().setTargetMessageLocation(loc);
            set({ targetMessageLocation: loc }, false, 'setTargetMessageLocation');
          },

          // ====================================================================
          // Sync Store Proxies
          // ====================================================================
          syncConversations: async () => {
            await useSyncStore.getState().syncConversations();
            const syncState = useSyncStore.getState();
            const convState = useConversationStore.getState();
            set({
              chats: convState.chats,
              isSyncing: syncState.isSyncing,
              lastSyncTime: syncState.lastSyncTime,
              syncVersion: syncState.syncVersion,
              syncError: syncState.syncError,
              hasSyncedOnce: syncState.hasSyncedOnce,
            }, false, 'syncConversations');
          },
          syncConversationsIfNeeded: async () => {
            await useSyncStore.getState().syncConversationsIfNeeded();
            const syncState = useSyncStore.getState();
            const convState = useConversationStore.getState();
            set({
              chats: convState.chats,
              isSyncing: syncState.isSyncing,
              lastSyncTime: syncState.lastSyncTime,
              syncVersion: syncState.syncVersion,
              syncError: syncState.syncError,
              hasSyncedOnce: syncState.hasSyncedOnce,
            }, false, 'syncConversationsIfNeeded');
          },
          forceSyncConversations: async () => {
            await useSyncStore.getState().forceSyncConversations();
            const syncState = useSyncStore.getState();
            const convState = useConversationStore.getState();
            set({
              chats: convState.chats,
              isSyncing: syncState.isSyncing,
              lastSyncTime: syncState.lastSyncTime,
              syncVersion: syncState.syncVersion,
              syncError: syncState.syncError,
              hasSyncedOnce: syncState.hasSyncedOnce,
            }, false, 'forceSyncConversations');
          },
          setSyncing: (syncing) => {
            useSyncStore.getState().setSyncing(syncing);
            set({ isSyncing: syncing }, false, 'setSyncing');
          },
          setSyncError: (error) => {
            useSyncStore.getState().setSyncError(error);
            set({ syncError: error }, false, 'setSyncError');
          },
          convertWuKongIMToChat: (conversation) => useSyncStore.getState().convertWuKongIMToChat(conversation),

          // ====================================================================
          // Cross-Store Coordination
          // ====================================================================
          initializeStore: async () => {
            // Initialize empty - conversations will be loaded from real APIs
            useConversationStore.getState().setChats([]);
            set({ chats: [] }, false, 'initializeStore');
          },

          /**
           * Handle real-time message - coordinates between conversation and message stores
           */
          handleRealtimeMessage: (message: Message) => {
            console.log('📨 Chat Store: Handling real-time message', {
              messageId: message.messageId || message.id,
              content: message.content.substring(0, 50) + '...',
              sender: message.fromInfo?.name,
              type: message.type,
              channelId: message.channelId,
              channelType: message.channelType,
            });

            const convStore = useConversationStore.getState();
            const msgStore = useMessageStore.getState();
            const channelStore = useChannelStore.getState();

            const activeChat = convStore.activeChat;
            const channelId = message.channelId || message.fromUid;
            const channelType = message.channelType ?? DEFAULT_CHANNEL_TYPE;
            const clientMsgNo = message.clientMsgNo;

            if (!channelId) {
              console.warn('📨 Chat Store: Message missing channel ID, cannot update conversation');
              return;
            }

            // 0. Auto-create conversation if not exists (visitor messages only)
            let createdNewConversation = false;
            if (message.type === MESSAGE_SENDER_TYPE.VISITOR) {
              const key = getChannelKey(channelId, channelType);
              const platform = WuKongIMUtils.getPlatformFromChannelType(channelType);
              const isoTs =
                message.timestamp && !isNaN(new Date(message.timestamp).getTime())
                  ? new Date(message.timestamp).toISOString()
                  : new Date().toISOString();
              const sec = Math.floor(new Date(isoTs).getTime() / 1000);

              const exists = convStore.chats.some((c) => c.channelId === channelId && c.channelType === channelType);
              if (!exists) {
                createdNewConversation = true;
                const newChat: Chat = {
                  id: key,
                  platform,
                  lastMessage: message.content,
                  timestamp: isoTs,
                  lastTimestampSec: sec,
                  status: CHAT_STATUS_CONST.ACTIVE as ChatStatus,
                  unreadCount: 1,
                  channelId,
                  channelType,
                  lastMsgSeq: message.messageSeq ?? 1,
                  tags: [],
                  priority: CHAT_PRIORITY_CONST.HIGH,
                  metadata: {},
                };
                convStore.setChats([newChat, ...convStore.chats]);
              }

              // Mark onboarding task as completed when receiving a visitor message
              try {
                useOnboardingStore.getState().markTaskCompleted('messageReceived');
              } catch (error) {
                console.error('Failed to mark onboarding task completed:', error);
              }
            }

            // 1. Update conversation list (always)
            convStore.updateConversationLastMessage(channelId, channelType, message);
            convStore.moveConversationToTop(channelId, channelType);

            // 2. If message is for a different conversation than active, increment unread count
            if (!createdNewConversation && (!activeChat || !isSameChannel(activeChat.channelId, activeChat.channelType, channelId, channelType))) {
              convStore.incrementUnreadCount(channelId, channelType);
            }

            if (message.type === MESSAGE_SENDER_TYPE.VISITOR && channelId) {
              const cachedChannel = channelStore.getChannel(channelId, CHANNEL_TYPE.PERSON);
              const fallbackName = message.fromInfo?.name || cachedChannel?.name || `访客${String(channelId).slice(-4)}`;
              const fallbackAvatar = message.fromInfo?.avatar || message.avatar || cachedChannel?.avatar || '';

              channelStore.seedChannel(channelId, 1, {
                name: fallbackName,
                avatar: fallbackAvatar,
              });

              channelStore
                .ensureChannel({ channel_id: channelId, channel_type: 1 })
                .then((info) => {
                  if (!info) return;
                  get().applyChannelInfo(channelId, 1, info);
                })
                .catch((error) => {
                  console.warn('频道信息获取失败（实时消息）:', error);
                });
            }

            // Check if this is a stream start message (type=100)
            const isStreamStart =
              message.payloadType === MessagePayloadType.STREAM || (message.payload as any)?.type === MessagePayloadType.STREAM;

            if (isStreamStart && clientMsgNo) {
              console.log('📨 Chat Store: Stream message started (type=100)', { clientMsgNo });
              msgStore.setStreamingState(true, clientMsgNo);
            }

            // 检查是否是需要刷新频道信息的系统消息（1000-已分配到客服，1001-会话关闭）
            const payloadType = message.payloadType || (message.payload as any)?.type;
            if (payloadType && isChannelRefreshSystemMessage(payloadType)) {
              console.log('📨 Chat Store: System message requires channel refresh', { payloadType, channelId, channelType });
              // 强制刷新频道信息以获取最新的 service_status
              channelStore
                .refreshChannel({ channel_id: channelId, channel_type: channelType })
                .then((info) => {
                  if (info) {
                    console.log('📨 Chat Store: Channel info refreshed after system message', { channelId, serviceStatus: (info.extra as any)?.service_status });
                    get().applyChannelInfo(channelId, channelType, info);
                  }
                })
                .catch((error) => {
                  console.warn('📨 Chat Store: Failed to refresh channel info after system message:', error);
                });
            }

            // 3. If message is for the currently active conversation, add to message list
            if (activeChat && isSameChannel(activeChat.channelId, activeChat.channelType, channelId, channelType)) {
              console.log('📨 Chat Store: Adding message to active conversation');

              if (!clientMsgNo) {
                msgStore.addMessage(message);
              } else {
                const existingIndex = msgStore.messages.findIndex((msg) => msg.clientMsgNo === clientMsgNo);

                if (existingIndex === -1) {
                  msgStore.addMessage(message);
                } else {
                  msgStore.updateMessageByClientMsgNo(clientMsgNo, {
                    ...message,
                    metadata: {
                      ...message.metadata,
                      is_streaming: false,
                      last_stream_update: Date.now(),
                    },
                  });
                }
              }

              // Clear unread for active conversation when receiving messages (user is viewing it)
              // Only if page is visible and service_status is not 'queued'
              const isPageVisible = typeof document !== 'undefined' && !document.hidden;
              if (isPageVisible) {
                const extra = channelStore.getChannel(channelId, channelType)?.extra as { service_status?: string } | undefined;
                if (extra?.service_status !== 'queued') {
                  convStore.clearConversationUnread(channelId, channelType);
                }
              }
            }

            // Sync state to chatStore
            set({
              chats: useConversationStore.getState().chats,
              messages: useMessageStore.getState().messages,
              isStreamingInProgress: useMessageStore.getState().isStreamingInProgress,
              streamingClientMsgNo: useMessageStore.getState().streamingClientMsgNo,
            }, false, 'handleRealtimeMessage');
          },

          /**
           * Apply channel info to both conversations and messages
           */
          applyChannelInfo: (channelId: string, channelType: number, info: ChannelInfo) => {
            if (!channelId || channelType == null) return;

            // Update conversations
            useConversationStore.getState().applyChannelInfoToConversations(channelId, channelType, info);

            // Update messages
            useMessageStore.getState().applyChannelInfoToMessages(channelId, channelType, info);

            // Sync state
            set({
              chats: useConversationStore.getState().chats,
              activeChat: useConversationStore.getState().activeChat,
              messages: useMessageStore.getState().messages,
            }, false, 'applyChannelInfo');
          },

          /**
           * Unified sync: refresh channel then propagate to chats and messages
           */
          syncChannelInfoAcrossUI: async (channelId: string, channelType: number) => {
            if (!channelId || channelType == null) return null;
            const channelStore = useChannelStore.getState();
            try {
              const info = await channelStore.refreshChannel({ channel_id: channelId, channel_type: channelType });
              if (info) {
                get().applyChannelInfo(channelId, channelType, info);
              }
              return info ?? null;
            } catch (err) {
              console.warn('syncChannelInfoAcrossUI failed:', err);
              return null;
            }
          },

          /**
           * Clear all store data (for logout)
           */
          clearStore: () => {
            console.log('🗑️ Chat Store: Clearing all data for logout');
            useConversationStore.getState().clearConversationStore();
            useMessageStore.getState().clearMessageStore();
            useSyncStore.getState().clearSyncStore();
            useChannelStore.getState().clear();
            set(getAggregatedState(), false, 'clearStore');
          },
        };
      },
      {
        name: STORAGE_KEYS.CHAT,
        partialize: (state) => ({
          // 只持久化用户偏好，不持久化聊天数据
          searchQuery: state.searchQuery,
        }),
      }
    ),
    { name: STORAGE_KEYS.CHAT }
  )
);

// Re-export selectors for backward compatibility
// Note: These selectors use ChatState as parameter type for compatibility with useChatStore
export const chatSelectors = {
  activeChat: (state: ChatState) => state.activeChat ?? null,
  messages: (state: ChatState) => state.messages ?? [],
  chats: (state: ChatState) => state.chats ?? [],
  searchQuery: (state: ChatState) => state.searchQuery ?? '',
  isLoading: (state: ChatState) => state.isLoading || state.isSending || false,
  isSyncing: (state: ChatState) => state.isSyncing ?? false,
};
