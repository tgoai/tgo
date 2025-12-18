import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';
import { MessagePayloadType, type Chat, type ChatStatus, type Message, type ChannelInfo } from '@/types';
import { WuKongIMApiService, WuKongIMUtils } from '@/services/wukongimApi';
import { diffMinutesFromNow } from '@/utils/dateUtils';
import { getChannelKey } from '@/utils/channelUtils';
import {
  DEFAULT_CHANNEL_TYPE,
  CHAT_STATUS as CHAT_STATUS_CONST,
  CHAT_PRIORITY as CHAT_PRIORITY_CONST,
  VISITOR_STATUS,
  STORAGE_KEYS,
} from '@/constants';

// Debounce map for unread clearing API calls (per conversation)
const pendingUnreadTimers: Record<string, ReturnType<typeof setTimeout>> = {};

/**
 * Conversation Store State Interface
 * Manages conversation list, active chat, and search
 */
interface ConversationState {
  // 会话列表 (单一数据源)
  chats: Chat[];
  activeChat: Chat | null;
  searchQuery: string;

  // Actions - 基础操作
  setChats: (chats: Chat[]) => void;
  setActiveChat: (chat: Chat | null) => void;
  setSearchQuery: (query: string) => void;

  // Actions - CRUD 操作
  createChat: (_visitorName: string, platform: string) => void;
  createChatByChannel: (channelId: string, channelType: number, options?: { platform?: string; name?: string; avatar?: string }) => Chat;
  deleteChat: (chatId: string) => void;
  updateChatStatus: (chatId: string, status: string) => void;

  // Actions - 搜索和筛选
  getFilteredChats: () => Chat[];
  getChatById: (chatId: string) => Chat | undefined;
  getChatByChannel: (channelId: string, channelType: number) => Chat | undefined;

  // Actions - 会话更新
  updateConversationLastMessage: (channelId: string, channelType: number, message: Message) => void;
  updateConversationPreview: (channelId: string, channelType: number, content: string) => void;
  moveConversationToTop: (channelId: string, channelType: number) => void;
  incrementUnreadCount: (channelId: string, channelType: number) => void;
  clearConversationUnread: (channelId: string, channelType: number) => Promise<void>;

  // Actions - Channel 信息应用（仅会话部分）
  applyChannelInfoToConversations: (channelId: string, channelType: number, info: ChannelInfo) => void;

  // Actions - 清理
  clearConversationStore: () => void;
}

export const useConversationStore = create<ConversationState>()(
  devtools(
    persist(
      (set, get) => ({
        // Initial state
        chats: [],
        activeChat: null,
        searchQuery: '',

        // Basic setters
        setChats: (chats) => set({ chats }, false, 'setChats'),

        setActiveChat: (chat) => {
          set({ activeChat: chat }, false, 'setActiveChat');
        },

        setSearchQuery: (query) => set({ searchQuery: query }, false, 'setSearchQuery'),

        // CRUD operations
        createChat: (_visitorName, platform) => {
          const id = Date.now().toString();
          const newChat: Chat = {
            id,
            platform,
            lastMessage: '新对话已创建',
            timestamp: new Date().toISOString(),
            lastTimestampSec: Math.floor(Date.now() / 1000),
            status: CHAT_STATUS_CONST.ACTIVE,
            unreadCount: 0,
            channelId: id,
            channelType: DEFAULT_CHANNEL_TYPE,
            lastMsgSeq: 1,
            tags: [],
            priority: CHAT_PRIORITY_CONST.NORMAL,
          };

          set(
            (state) => ({ chats: [newChat, ...state.chats] }),
            false,
            'createChat'
          );
        },

        createChatByChannel: (channelId: string, channelType: number, options?: { platform?: string; name?: string; avatar?: string }) => {
          const key = getChannelKey(channelId, channelType);
          const platform = options?.platform || WuKongIMUtils.getPlatformFromChannelType(channelType);
          const nowSec = Math.floor(Date.now() / 1000);

          const newChat: Chat = {
            id: key,
            platform,
            lastMessage: '',
            timestamp: new Date().toISOString(),
            lastTimestampSec: nowSec,
            status: CHAT_STATUS_CONST.ACTIVE as ChatStatus,
            unreadCount: 0,
            channelId,
            channelType,
            lastMsgSeq: 0,
            tags: [],
            priority: CHAT_PRIORITY_CONST.NORMAL,
            metadata: {},
          };

          set(
            (state) => {
              // Check if chat already exists
              const exists = state.chats.some((c) => c.channelId === channelId && c.channelType === channelType);
              if (exists) {
                return {} as any;
              }
              return { chats: [newChat, ...state.chats] } as any;
            },
            false,
            'createChatByChannel'
          );

          return newChat;
        },

        deleteChat: (chatId) =>
          set(
            (state) => ({
              chats: state.chats.filter((chat) => chat.id !== chatId),
              activeChat: state.activeChat?.id === chatId ? null : state.activeChat,
            }),
            false,
            'deleteChat'
          ),

        updateChatStatus: (chatId, status) =>
          set(
            (state) => ({
              chats: state.chats.map((chat) =>
                chat.id === chatId ? { ...chat, status: status as ChatStatus } : chat
              ),
            }),
            false,
            'updateChatStatus'
          ),

        // Search and filter
        getFilteredChats: () => {
          const { chats, searchQuery } = get();
          if (!searchQuery.trim()) return chats;

          const lower = searchQuery.toLowerCase();
          return chats.filter((chat: Chat) => {
            const baseId = chat.channelId || chat.id;
            const fallbackName = `访客${String(baseId).slice(-4)}`;
            const name = (chat.channelInfo?.name || fallbackName).toLowerCase();
            return name.includes(lower) || chat.lastMessage.toLowerCase().includes(lower);
          });
        },

        getChatById: (chatId) => {
          const { chats } = get();
          return chats.find((chat) => chat.id === chatId);
        },

        getChatByChannel: (channelId, channelType) => {
          const { chats } = get();
          return chats.find((c) => c.channelId === channelId && c.channelType === channelType);
        },

        // Conversation updates
        updateConversationLastMessage: (channelId: string, channelType: number, message: Message) => {
          set(
            (state) => ({
              chats: state.chats.map((chat) => {
                if (chat.channelId === channelId && chat.channelType === channelType) {
                  const isoTs =
                    message.timestamp && !isNaN(new Date(message.timestamp).getTime())
                      ? new Date(message.timestamp).toISOString()
                      : new Date().toISOString();
                  const sec = Math.floor(new Date(isoTs).getTime() / 1000);

        // For STREAM messages, use a placeholder if content is empty
        let content = message.content;
        if (message.payloadType === MessagePayloadType.STREAM && !content) {
          content = 'AI 正在输入...';
        }

                  return {
                    ...chat,
                    lastMessage: content,
                    payloadType: message.payloadType,
                    timestamp: isoTs,
                    lastTimestampSec: sec,
                  };
                }
                return chat;
              }),
            }),
            false,
            'updateConversationLastMessage'
          );
        },

        // Update conversation preview content without re-sorting or changing timestamps
        // Used primarily for streaming messages
        updateConversationPreview: (channelId: string, channelType: number, content: string) => {
          set(
            (state) => ({
              chats: state.chats.map((chat) => {
                if (chat.channelId === channelId && chat.channelType === channelType) {
                  // Only update if content changed
                  if (chat.lastMessage === content) return chat;
                  return {
                    ...chat,
                    lastMessage: content,
                  };
                }
                return chat;
              }),
            }),
            false,
            'updateConversationPreview'
          );
        },

        moveConversationToTop: (channelId: string, channelType: number) => {
          set(
            (state) => {
              // Mark parameters as used to satisfy TS noUnusedParameters
              if (!channelId || channelType == null) {
                // no-op
              }
              // Re-sort all conversations by numeric timestamp (desc)
              const sorted = [...state.chats].sort((a, b) => {
                const aSec = a.lastTimestampSec ?? (a.timestamp ? Math.floor(new Date(a.timestamp).getTime() / 1000) : 0);
                const bSec = b.lastTimestampSec ?? (b.timestamp ? Math.floor(new Date(b.timestamp).getTime() / 1000) : 0);
                return bSec - aSec;
              });
              return { chats: sorted };
            },
            false,
            'moveConversationToTop'
          );
        },

        incrementUnreadCount: (channelId: string, channelType: number) => {
          set(
            (state) => ({
              chats: state.chats.map((chat) => {
                if (chat.channelId === channelId && chat.channelType === channelType) {
                  return {
                    ...chat,
                    unreadCount: (chat.unreadCount || 0) + 1,
                    priority: CHAT_PRIORITY_CONST.HIGH, // Mark as high priority when unread
                  };
                }
                return chat;
              }),
            }),
            false,
            'incrementUnreadCount'
          );
        },

        clearConversationUnread: async (channelId: string, channelType: number) => {
          if (!channelId || channelType == null) {
            console.log('🔔 clearConversationUnread: Invalid params', { channelId, channelType });
            return;
          }
          
          console.log('🔔 clearConversationUnread: Called', { channelId, channelType });

          // Skip API call if page is not visible (user not looking at the page)
          const isPageVisible = typeof document !== 'undefined' && !document.hidden;
          console.log('🔔 clearConversationUnread: Page visible:', isPageVisible);

          // Optimistic local update for better UX (update if exists in store)
          set(
            (s) => ({
              chats: s.chats.map((c) => {
                if (c.channelId === channelId && c.channelType === channelType) {
                  return {
                    ...c,
                    unreadCount: 0,
                    // Restore priority back to normal when unread is cleared
                    priority: c.priority === CHAT_PRIORITY_CONST.HIGH ? CHAT_PRIORITY_CONST.NORMAL : c.priority,
                  };
                }
                return c;
              }),
            }),
            false,
            'clearConversationUnread:local'
          );

          // Only notify backend if page is visible
          if (!isPageVisible) {
            console.log('🔔 clearConversationUnread: Skipped API call - page not visible');
            return;
          }

          // Notify backend (debounced per conversation)
          try {
            const key = getChannelKey(channelId, channelType);
            if (pendingUnreadTimers[key]) {
              clearTimeout(pendingUnreadTimers[key]);
            }
            console.log('🔔 clearConversationUnread: Scheduling API call with 300ms debounce');
            pendingUnreadTimers[key] = setTimeout(async () => {
              try {
                console.log('🔔 clearConversationUnread: Calling API setConversationUnread');
                await WuKongIMApiService.setConversationUnread(channelId, channelType, 0);
                console.log('🔔 clearConversationUnread: API call success');
              } catch (err) {
                console.warn('清零未读数失败:', { channelId, channelType, error: err });
              } finally {
                delete pendingUnreadTimers[key];
              }
            }, 300);
          } catch (err) {
            // Guard against unexpected scheduling errors
            console.warn('清零未读数调度失败:', { channelId, channelType, error: err });
          }
        },

        // Apply channel info to conversations only
        applyChannelInfoToConversations: (channelId: string, channelType: number, info: ChannelInfo) => {
          if (!channelId || channelType == null) return;

          set((state) => {
            // Update chats only if the target chat actually changes
            let chatsChanged = false;
            const extra: any = info.extra;
            const extraTags: any[] = Array.isArray(extra?.tags) ? (extra.tags as any[]) : [];
            const newTags = extraTags.map((t: any) => ({ name: t?.name ?? '', color: t?.color ?? null }));
            const derivedStatus = extra?.is_online ? VISITOR_STATUS.ONLINE : VISITOR_STATUS.OFFLINE;
            const lastOfflineIso: string | undefined = extra?.last_offline_time;
            let computedLastSeen: number | undefined = undefined;
            if (!extra?.is_online && lastOfflineIso) {
              const mins = diffMinutesFromNow(lastOfflineIso);
              if (mins != null) {
                if (mins === 0) {
                  computedLastSeen = 0;
                } else if (mins > 0 && mins <= 60) {
                  computedLastSeen = mins;
                } else {
                  computedLastSeen = undefined;
                }
              }
            }

            const updatedChats = state.chats.map((chat) => {
              if (!(chat.channelId === channelId && chat.channelType === channelType)) return chat;
              const nextChat = {
                ...chat,
                visitorStatus: (derivedStatus ?? chat.visitorStatus) as any,
                tags: newTags,
                channelInfo: info,
                lastSeenMinutes: computedLastSeen,
              } as typeof chat;
              const prevTags = chat.tags || [];
              const tagsChanged =
                prevTags.length !== newTags.length ||
                prevTags.some((t, i) => t.name !== newTags[i]?.name || t.color !== newTags[i]?.color);
              const infoNameChanged = (chat.channelInfo?.name || '') !== info.name;
              const infoAvatarChanged = (chat.channelInfo?.avatar || '') !== (info.avatar || '');
              const lastSeenChanged = (chat.lastSeenMinutes ?? 0) !== (nextChat.lastSeenMinutes ?? 0);
              if (
                infoNameChanged ||
                infoAvatarChanged ||
                nextChat.visitorStatus !== chat.visitorStatus ||
                tagsChanged ||
                lastSeenChanged
              ) {
                chatsChanged = true;
                return nextChat;
              }
              return chat;
            });

            // Also update activeChat if it refers to the same channel
            let activeChanged = false;
            let updatedActive = state.activeChat;
            if (state.activeChat && state.activeChat.channelId === channelId && state.activeChat.channelType === channelType) {
              const nextActive = {
                ...state.activeChat,
                visitorStatus: (derivedStatus ?? state.activeChat.visitorStatus) as any,
                tags: newTags,
                channelInfo: info,
                lastSeenMinutes: computedLastSeen,
              } as typeof state.activeChat;
              const prevTagsA = state.activeChat.tags || [];
              const tagsChangedA =
                prevTagsA.length !== newTags.length ||
                prevTagsA.some((t, i) => t.name !== newTags[i]?.name || t.color !== newTags[i]?.color);
              const infoNameChangedA = (state.activeChat.channelInfo?.name || '') !== info.name;
              const infoAvatarChangedA = (state.activeChat.channelInfo?.avatar || '') !== (info.avatar || '');
              const lastSeenChangedA = (state.activeChat.lastSeenMinutes ?? 0) !== (nextActive.lastSeenMinutes ?? 0);
              const statusChangedA = nextActive.visitorStatus !== state.activeChat.visitorStatus;
              if (infoNameChangedA || infoAvatarChangedA || tagsChangedA || lastSeenChangedA || statusChangedA) {
                activeChanged = true;
                updatedActive = nextActive;
              }
            }

            // If nothing actually changed, return the original state slice to avoid re-renders
            const partial: Partial<typeof state> = {};
            if (chatsChanged) partial.chats = updatedChats;
            if (activeChanged) partial.activeChat = updatedActive!;
            return Object.keys(partial).length > 0 ? partial : {};
          }, false, 'applyChannelInfoToConversations');
        },

        // Clear store
        clearConversationStore: () => {
          // Clear any pending unread debounce timers
          try {
            Object.values(pendingUnreadTimers).forEach((t) => clearTimeout(t));
            Object.keys(pendingUnreadTimers).forEach((k) => delete (pendingUnreadTimers as any)[k]);
          } catch {}
          set(
            {
              chats: [],
              activeChat: null,
              searchQuery: '',
            },
            false,
            'clearConversationStore'
          );
        },
      }),
      {
        name: STORAGE_KEYS.CONVERSATION || 'tgo-conversation',
        partialize: (state) => ({
          // 只持久化搜索查询
          searchQuery: state.searchQuery,
        }),
      }
    ),
    { name: 'ConversationStore' }
  )
);

// Selectors for optimized subscriptions
export const conversationSelectors = {
  chats: (state: ConversationState) => state.chats,
  activeChat: (state: ConversationState) => state.activeChat,
  searchQuery: (state: ConversationState) => state.searchQuery,
};
