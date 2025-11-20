import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';
import type {
  Chat,
  Message,
  ChatStatus,
  WuKongIMConversation,
  WuKongIMConversationSyncResponse,
  WuKongIMMessage,
  MessageSenderType
} from '@/types';
import { WuKongIMApiService, WuKongIMUtils } from '@/services/wukongimApi';

import { diffMinutesFromNow } from '@/utils/dateUtils';

import { useChannelStore } from './channelStore';
import type { ChannelInfo } from '@/types';
import { getChannelKey, isSameChannel } from '@/utils/channelUtils';
import { CHANNEL_TYPE, DEFAULT_CHANNEL_TYPE, MESSAGE_SENDER_TYPE, CHAT_STATUS as CHAT_STATUS_CONST, CHAT_PRIORITY as CHAT_PRIORITY_CONST, VISITOR_STATUS, STORAGE_KEYS, STAFF_UID_SUFFIX } from '@/constants';
import { useOnboardingStore } from './onboardingStore';



// Debounce map for unread clearing API calls (per conversation)
const pendingUnreadTimers: Record<string, ReturnType<typeof setTimeout>> = {};

interface ChatState {
  // 聊天列表相关
  chats: Chat[];
  activeChat: Chat | null;
  searchQuery: string;

  // 消息相关
  messages: Message[];
  isLoading: boolean;
  isSending: boolean;

  // WuKongIM 同步相关
  isSyncing: boolean;
  lastSyncTime: string | null;
  syncVersion: number;
  syncError: string | null;

  // 历史消息相关
  historicalMessages: Record<string, WuKongIMMessage[]>; // channelKey -> messages
  isLoadingHistory: boolean;
  historyError: string | null;
  hasMoreHistory: Record<string, boolean>; // channelKey -> hasMore（更旧方向）
  nextHistorySeq: Record<string, number>; // channelKey -> nextSeq（更旧方向）
  // 新方向（较新消息）分页
  hasMoreNewerHistory: Record<string, boolean>; // channelKey -> hasMore（更新方向）
  nextNewerSeq: Record<string, number>; // channelKey -> nextSeq（更新方向）

  // 目标消息定位（从搜索跳转）
  targetMessageLocation: { channelId: string; channelType: number; messageSeq: number } | null;

  // Actions
  setChats: (chats: Chat[]) => void;
  setActiveChat: (chat: Chat | null) => void;
  setSearchQuery: (query: string) => void;
  addMessage: (message: Message) => void;
  updateMessageByClientMsgNo: (clientMsgNo: string, patch: Partial<Message>) => void;
  loadMessages: (chatId: string) => Promise<void>;
  setLoading: (loading: boolean) => void;
  setSending: (sending: boolean) => void;

  // Initialization
  initializeStore: () => Promise<void>;

  // Real-time message handling
  handleRealtimeMessage: (message: Message) => void;
  updateConversationLastMessage: (channelId: string, channelType: number, message: Message) => void;
  moveConversationToTop: (channelId: string, channelType: number) => void;
  incrementUnreadCount: (channelId: string, channelType: number) => void;
  clearConversationUnread: (channelId: string, channelType: number) => Promise<void>;

  // AI stream message handling
  appendStreamMessageContent: (clientMsgNo: string, content: string) => void;

  // 聊天操作
  createChat: (_visitorName: string, platform: string) => void;
  deleteChat: (chatId: string) => void;
  updateChatStatus: (chatId: string, status: string) => void;

  // 搜索和筛选
  getFilteredChats: () => Chat[];
  getChatById: (chatId: string) => Chat | undefined;

  // WuKongIM 同步相关
  syncConversations: () => Promise<void>;
  setSyncing: (syncing: boolean) => void;
  setSyncError: (error: string | null) => void;
  convertWuKongIMToChat: (conversation: WuKongIMConversation) => Chat;

  // 历史消息相关
  loadHistoricalMessages: (channelId: string, channelType: number) => Promise<void>;
  loadMoreHistory: (channelId: string, channelType: number) => Promise<void>;
  loadNewerHistory: (channelId: string, channelType: number) => Promise<void>;
  loadMessageContext: (channelId: string, channelType: number, targetSeq: number, totalLimit?: number) => Promise<void>;
  clearHistoricalMessages: (channelId: string, channelType: number) => void;
  setLoadingHistory: (loading: boolean) => void;
  setHistoryError: (error: string | null) => void;
  getChannelMessages: (channelId: string, channelType: number) => WuKongIMMessage[];

  // 目标消息相关 actions
  setTargetMessageLocation: (loc: { channelId: string; channelType: number; messageSeq: number } | null) => void;

  // Channel helpers
  applyChannelInfo: (channelId: string, channelType: number, info: ChannelInfo) => void;
  // Unified sync: refresh channel then propagate to chats and messages
  syncChannelInfoAcrossUI: (channelId: string, channelType: number) => Promise<ChannelInfo | null>;

  // 清理存储（用于退出登录）
  clearStore: () => void;
}

export const useChatStore = create<ChatState>()(
  devtools(
    persist(
      (set, get) => ({
        // Initialize with empty arrays - will load mock data in development
        chats: [],
        activeChat: null,
        searchQuery: '',
        messages: [],
        isLoading: false,
        isSending: false,

        // WuKongIM 同步状态
        isSyncing: false,
        lastSyncTime: null,
        syncVersion: 0,
        syncError: null,

        // 历史消息状态
        historicalMessages: {},
        isLoadingHistory: false,
        historyError: null,

        // 目标消息定位（从搜索跳转）
        targetMessageLocation: null,

        hasMoreHistory: {},
        nextHistorySeq: {},
        hasMoreNewerHistory: {},
        nextNewerSeq: {},

        // Actions

        setTargetMessageLocation: (loc) => set({ targetMessageLocation: loc }, false, 'setTargetMessageLocation'),

        setChats: (chats) => set({ chats }, false, 'setChats'),

        setActiveChat: (chat) => {
          set({ activeChat: chat }, false, 'setActiveChat');
          if (chat) {
            get().loadMessages(chat.id);
          }
        },

        setSearchQuery: (query) => set({ searchQuery: query }, false, 'setSearchQuery'),

        addMessage: (message) => set(
          (state) => ({ messages: [...state.messages, message] }),
          false,
          'addMessage'
        ),

        updateMessageByClientMsgNo: (clientMsgNo, patch) => set(
          (state) => {
            const idx = state.messages.findIndex(m => m.clientMsgNo === clientMsgNo || m.id === clientMsgNo);
            if (idx === -1) {
              return {} as any;
            }
            const prev = state.messages[idx];
            const merged: Message = {
              ...prev,
              ...patch,
              metadata: {
                ...(prev.metadata || {}),
                ...(patch.metadata || {})
              }
            };
            const updated = [...state.messages];
            updated[idx] = merged;
            return { messages: updated } as any;
          },
          false,
          'updateMessageByClientMsgNo'
        ),
        loadMessages: async (_chatId) => {
          // Load no messages by default; real-time and historical APIs populate as events occur
          set({ isLoading: true }, false, 'loadMessages');
          try {
            set({ messages: [], isLoading: false }, false, 'loadMessagesComplete');
          } catch (error) {
            console.error('Failed to load messages:', error);
            set({ messages: [], isLoading: false }, false, 'loadMessagesError');
          }
        },

        setLoading: (loading) => set({ isLoading: loading }, false, 'setLoading'),
        setSending: (sending) => set({ isSending: sending }, false, 'setSending'),

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
            priority: CHAT_PRIORITY_CONST.NORMAL
          };

          set(
            (state) => ({ chats: [newChat, ...state.chats] }),
            false,
            'createChat'
          );
        },

        deleteChat: (chatId) => set(
          (state) => ({
            chats: state.chats.filter(chat => chat.id !== chatId),
            activeChat: state.activeChat?.id === chatId ? null : state.activeChat
          }),
          false,
          'deleteChat'
        ),

        updateChatStatus: (chatId, status) => set(
          (state) => ({
            chats: state.chats.map(chat =>
              chat.id === chatId ? { ...chat, status: status as ChatStatus } : chat
            )
          }),
          false,
          'updateChatStatus'
        ),

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
          return chats.find(chat => chat.id === chatId);
        },

        // WuKongIM 同步相关方法
        setSyncing: (syncing) => set({ isSyncing: syncing }, false, 'setSyncing'),

        setSyncError: (error) => set({ syncError: error }, false, 'setSyncError'),

        convertWuKongIMToChat: (conversation: WuKongIMConversation): Chat => {
          // Use the latest message by highest message_seq to ensure we pick the true last message
          const latestWkMsg = Array.isArray(conversation.recents) && conversation.recents.length > 0
            ? conversation.recents.reduce((acc, m) => (!acc || m.message_seq > acc.message_seq ? m : acc), conversation.recents[0])
            : null;

          // Debug: Log the latest message to see if stream_data is present
          if (latestWkMsg) {
            console.log('📋 convertWuKongIMToChat - Latest message:', {
              message_seq: latestWkMsg.message_seq,
              has_stream_data: !!latestWkMsg.stream_data,
              stream_data_preview: latestWkMsg.stream_data ? latestWkMsg.stream_data.substring(0, 50) : 'N/A',
              payload_type: typeof latestWkMsg.payload,
              payload_preview: typeof latestWkMsg.payload === 'object' ? (latestWkMsg.payload as any).content?.substring(0, 50) : latestWkMsg.payload?.substring(0, 50)
            });
          }

          const lastMessage = latestWkMsg
            ? WuKongIMUtils.extractMessageContent(latestWkMsg)
            : '暂无消息';

          const channelId = conversation.channel_id;
          const channelType = conversation.channel_type ?? DEFAULT_CHANNEL_TYPE;

          // Derive basic presentation fields without fetching/seeding ChannelInfo here
          const platform = WuKongIMUtils.getPlatformFromChannelType(channelType);

          return {
            id: getChannelKey(channelId, channelType),
            platform,
            lastMessage,
            timestamp: new Date(conversation.timestamp * 1000).toISOString(),
            lastTimestampSec: conversation.timestamp,
            status: CHAT_STATUS_CONST.ACTIVE as ChatStatus,
            unreadCount: conversation.unread,
            channelId: conversation.channel_id,
            channelType: conversation.channel_type ?? DEFAULT_CHANNEL_TYPE,
            lastMsgSeq: conversation.last_msg_seq,
            tags: [],
            priority: (conversation.unread > 0 ? CHAT_PRIORITY_CONST.HIGH : CHAT_PRIORITY_CONST.NORMAL),
            lastSeenMinutes: undefined,
            metadata: {}
          };
        },

        syncConversations: async () => {
          const { setSyncing, setSyncError, syncVersion } = get();

          setSyncing(true);
          setSyncError(null);

          try {
            let response: WuKongIMConversationSyncResponse;

            response = await WuKongIMApiService.syncConversationsInitial();

            // Debug: Log sync response to see if stream_data is present
            console.log('📋 syncConversations - API response:', {
              conversationCount: response.conversations.length,
              conversations: response.conversations.map(conv => ({
                channel_id: conv.channel_id,
                recentsCount: conv.recents.length,
                recents: conv.recents.map(msg => ({
                  message_seq: msg.message_seq,
                  has_stream_data: !!msg.stream_data,
                  stream_data_preview: msg.stream_data ? msg.stream_data.substring(0, 50) : 'N/A',
                  payload_type: typeof msg.payload
                }))
              }))
            });

            // 转换 WuKongIM 对话为内部格式
            const convertedChats = response.conversations.map(conv =>
              get().convertWuKongIMToChat(conv)
            );

            // Merge existing visitor/channel info to prevent losing data on navigation
            const existingChats = get().chats;
            const existingMap = new Map(existingChats.map(c => [getChannelKey(c.channelId, c.channelType), c]));
            const channelStore = useChannelStore.getState();
            const mergedChats = convertedChats.map(chat => {
              const key = getChannelKey(chat.channelId, chat.channelType);
              const prev = existingMap.get(key);
              const cached = channelStore.getChannel(chat.channelId, chat.channelType);
              return {
                ...chat,
                channelInfo: prev?.channelInfo ?? cached ?? chat.channelInfo,
                visitorStatus: prev?.visitorStatus ?? chat.visitorStatus,
                // Preserve lastSeenMinutes if it was a meaningful value (>0); avoid carrying over 0 which renders as "刚刚"
                lastSeenMinutes: (prev?.lastSeenMinutes != null && prev.lastSeenMinutes !== 0) ? prev.lastSeenMinutes : chat.lastSeenMinutes,
                tags: prev?.tags ?? chat.tags
              } as Chat;
            });

            // Sort conversations by lastTimestampSec (desc)
            const sortedChats = [...mergedChats].sort((a, b) => {
              const aSec = a.lastTimestampSec ?? (a.timestamp ? Math.floor(new Date(a.timestamp).getTime() / 1000) : 0);
              const bSec = b.lastTimestampSec ?? (b.timestamp ? Math.floor(new Date(b.timestamp).getTime() / 1000) : 0);
              return bSec - aSec;
            });

            // 更新状态
            const maxVersion = Math.max(...response.conversations.map(c => c.version), syncVersion);
            set({
              chats: sortedChats,
              syncVersion: maxVersion,
              lastSyncTime: new Date().toISOString(),
              isSyncing: false,
              syncError: null
            }, false, 'syncConversationsSuccess');

          } catch (error) {
            console.error('同步对话失败:', error);
            const errorMessage = error instanceof Error ? error.message : '同步失败';
            setSyncError(errorMessage);
            setSyncing(false);
          }
        },

        // 历史消息管理
        loadHistoricalMessages: async (channelId: string, channelType: number) => {
          set({ isLoadingHistory: true, historyError: null });

          try {
            const response = await WuKongIMApiService.getChannelHistory(channelId, channelType, 50);
            console.log('loadHistoricalMessages: Response received for', channelId, response);
            const key = getChannelKey(channelId, channelType);

            // Sort and store messages for the channel
            const sortedAsc = WuKongIMUtils.sortMessages(response.messages, 'asc');
            set(state => ({
              historicalMessages: {
                ...state.historicalMessages,
                [key]: sortedAsc
              },
              hasMoreHistory: {
                ...state.hasMoreHistory,
                [key]: response.more
              },
              nextHistorySeq: {
                ...state.nextHistorySeq,
                [key]: response.next_start_seq || 0
              },
              isLoadingHistory: false
            }));

            // Update the conversation preview using stream_data when available from messages sync
            // Pick the latest message from the response (highest seq)
            const latest = response.messages && response.messages.length > 0
              ? response.messages.reduce((acc, m) => (acc == null || m.message_seq > acc.message_seq ? m : acc), null as any)
              : null;

            if (latest) {
              const latestContent = WuKongIMUtils.extractMessageContent(latest);
              const latestSec = Number(latest.timestamp || 0);
              const latestIso = latestSec > 0 ? new Date(latestSec * 1000).toISOString() : new Date().toISOString();

              set(state => ({
                chats: state.chats.map(c => {
                  if (c.channelId === channelId && c.channelType === channelType) {
                    // Only update if this is newer or content actually differs to avoid flicker
                    const shouldUpdate = (c.lastTimestampSec ?? 0) <= latestSec || (latestContent && latestContent !== c.lastMessage);
                    if (shouldUpdate) {
                      return {
                        ...c,
                        lastMessage: latestContent || c.lastMessage,
                        timestamp: latestIso,
                        lastTimestampSec: latestSec || c.lastTimestampSec
                      };
                    }
                  }
                  return c;
                })
              }));
            }
          } catch (error) {
            console.error('Failed to load historical messages:', error);
            set({
              historyError: error instanceof Error ? error.message : '加载历史消息失败',
              isLoadingHistory: false
            });
          }
        },

        loadMoreHistory: async (channelId: string, channelType: number) => {
          console.log('loadMoreHistory: Loading more history for', channelId);
          const state = get();
          const key = getChannelKey(channelId, channelType);
          const currentMessages = state.historicalMessages[key] || [];
          const hasMore = state.hasMoreHistory[key];

          if (!hasMore || state.isLoadingHistory) {
            return;
          }

          set({ isLoadingHistory: true, historyError: null });

          try {
            // Get the earliest message sequence for pagination
            const earliestSeq = currentMessages.length > 0
              ? Math.min(...currentMessages.map(m => m.message_seq))
              : state.nextHistorySeq[key] || 0;

            const response = await WuKongIMApiService.loadMoreMessages(
              channelId,
              channelType,
              earliestSeq,
              50
            );
            set(state => ({
              historicalMessages: {
                ...state.historicalMessages,
                [key]: WuKongIMUtils.mergeMessages(
                  state.historicalMessages[key] || [],
                  response.messages,
                  'asc'
                )
              },
              hasMoreHistory: {
                ...state.hasMoreHistory,
                [key]: response.more
              },


              nextHistorySeq: {
                ...state.nextHistorySeq,
                [key]: response.next_start_seq || 0
              },
              isLoadingHistory: false
            }));
          } catch (error) {
            console.error('Failed to load more historical messages:', error);
            set({
              historyError: error instanceof Error ? error.message : '加载更多消息失败',
              isLoadingHistory: false
            });
          }
        },

        // 向下加载较新历史（底部无限滚动）
        loadNewerHistory: async (channelId: string, channelType: number) => {
          if (!channelId || channelType == null) return;
          const state = get();
          const key = getChannelKey(channelId, channelType);
          const current = state.historicalMessages[key] || [];
          const currentMaxSeq = current.length > 0 ? current[current.length - 1].message_seq : 0;
          const chat = state.chats.find(c => c.channelId === channelId && c.channelType === channelType);
          const convLatestSeq = chat?.lastMsgSeq ?? 0;

          // 无更多较新历史且已到最新
          if (state.hasMoreNewerHistory?.[key] === false && (convLatestSeq === 0 || currentMaxSeq >= convLatestSeq)) {
            return;
          }

          try {
            const resp = await WuKongIMApiService.syncChannelMessages({
              channel_id: channelId,
              channel_type: channelType,
              start_message_seq: currentMaxSeq,
              end_message_seq: 0,
              pull_mode: 1, // 向上/较新
              limit: 50
            } as any);

            const merged = WuKongIMUtils.mergeMessages(current, resp?.messages || [], 'asc');

            set((s) => ({
              historicalMessages: {
                ...s.historicalMessages,
                [key]: merged
              },
              hasMoreNewerHistory: {
                ...s.hasMoreNewerHistory,
                [key]: Boolean(resp?.more)
              },
              nextNewerSeq: {
                ...s.nextNewerSeq,
                [key]: resp?.next_start_seq || 0
              }
            }), false, 'loadNewerHistorySuccess');
          } catch (error) {
            console.error('Failed to load newer messages:', error);
            set({ historyError: error instanceof Error ? error.message : '加载更新消息失败' }, false, 'loadNewerHistoryError');
          }
        },



        // 加载包含目标消息（按 message_seq）的上下文消息段
        loadMessageContext: async (channelId: string, channelType: number, targetSeq: number, totalLimit: number = 20) => {
          if (!channelId || channelType == null || !targetSeq) return;
          const key = getChannelKey(channelId, channelType);
          const half = Math.max(1, Math.floor(totalLimit / 2));
          set({ isLoadingHistory: true, historyError: null }, false, 'loadMessageContextStart');
          try {
            const reqBase = { channel_id: channelId, channel_type: channelType, start_message_seq: targetSeq, end_message_seq: 0 } as any;
            const [downResp, upResp] = await Promise.all([
              WuKongIMApiService.syncChannelMessages({ ...reqBase, pull_mode: 0, limit: half }), // 向下/更旧，包含目标
              WuKongIMApiService.syncChannelMessages({ ...reqBase, pull_mode: 1, limit: half })  // 向上/更新，包含目标
            ]);
            const mergedArr = [
              ...(downResp?.messages || []),
              ...(upResp?.messages || [])
            ];
            // 去重，避免目标消息（start_message_seq）在双向结果中重复
            const deduped = WuKongIMUtils.deduplicateMessages(mergedArr);
            const sorted = WuKongIMUtils.sortMessages(deduped, 'asc');
            set(state => ({
              historicalMessages: {
                ...state.historicalMessages,
                [key]: sorted // 直接替换，确保连续上下文
              },
              // “更旧方向”翻页信息（用于顶部继续加载更早）
              hasMoreHistory: {
                ...state.hasMoreHistory,
                [key]: Boolean(downResp?.more)
              },
              nextHistorySeq: {
                ...state.nextHistorySeq,
                [key]: downResp?.next_start_seq || 0
              },
              // “更新方向”翻页信息（用于底部继续加载较新）
              hasMoreNewerHistory: {
                ...state.hasMoreNewerHistory,
                [key]: Boolean(upResp?.more)
              },
              nextNewerSeq: {
                ...state.nextNewerSeq,
                [key]: upResp?.next_start_seq || 0
              },
              isLoadingHistory: false
            }));
          } catch (error) {
            console.error('Failed to load message context by seq:', error);
            set({ historyError: error instanceof Error ? error.message : '加载消息上下文失败', isLoadingHistory: false }, false, 'loadMessageContextError');
          }
        },


        clearHistoricalMessages: (channelId: string, channelType: number) => {
          const key = getChannelKey(channelId, channelType);
          set(state => ({
            historicalMessages: {
              ...state.historicalMessages,
              [key]: []
            },
            hasMoreHistory: {
              ...state.hasMoreHistory,
              [key]: true
            },
            nextHistorySeq: {
              ...state.nextHistorySeq,
              [key]: 0
            },
            hasMoreNewerHistory: {
              ...state.hasMoreNewerHistory,
              [key]: false
            },
            nextNewerSeq: {
              ...state.nextNewerSeq,
              [key]: 0
            }
          }), false, 'clearHistoricalMessages');
        },

        setLoadingHistory: (loading: boolean) => set({ isLoadingHistory: loading }),

        setHistoryError: (error: string | null) => set({ historyError: error }),

        getChannelMessages: (channelId: string, channelType: number): WuKongIMMessage[] => {
          const state = get();
          const key = getChannelKey(channelId, channelType);
          return state.historicalMessages[key] || [];
        },
        getSendType: (wkMessage: WuKongIMMessage): MessageSenderType => {
          return wkMessage.from_uid?.endsWith(STAFF_UID_SUFFIX) ? MESSAGE_SENDER_TYPE.STAFF : MESSAGE_SENDER_TYPE.VISITOR;
        },



        applyChannelInfo: (channelId: string, channelType: number, info: ChannelInfo) => {
          if (!channelId || channelType == null) return;

          set(state => {
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
                  // Offline within the last minute -> show "刚刚在线"
                  computedLastSeen = 0;
                } else if (mins > 0 && mins <= 60) {
                  // Offline within 1-60 minutes -> show "X分钟前在线"


                  computedLastSeen = mins;
                } else {
                  // More than 60 minutes -> no recent last-seen badge
                  computedLastSeen = undefined;
                }
              }
            }

            const updatedChats = state.chats.map(chat => {
              if (!(chat.channelId === channelId && chat.channelType === channelType)) return chat;
              const nextChat = {
                ...chat,
                visitorStatus: (derivedStatus ?? chat.visitorStatus) as any,
                tags: newTags,
                channelInfo: info,
                lastSeenMinutes: computedLastSeen
              } as typeof chat;
              const prevTags = chat.tags || [];
              const tagsChanged = prevTags.length !== newTags.length || prevTags.some((t, i) => t.name !== newTags[i]?.name || t.color !== newTags[i]?.color);
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

            // Update messages only when we actually modify at least one message.
            // Also, avoid creating a new empty array when there are no messages.
            let messagesChanged = false;
            let updatedMessages = state.messages;
            if (state.messages.length > 0) {
              updatedMessages = state.messages.map(msg => {
                if ((msg.channelId === channelId && msg.channelType === channelType && msg.type === MESSAGE_SENDER_TYPE.VISITOR)) {
                  const curName = msg.fromInfo?.name;
                  const curAvatar = msg.fromInfo?.avatar || msg.avatar;
                  const nextMsg = {
                    ...msg,
                    fromInfo: {
                      name: info.name,
                      avatar: info.avatar || curAvatar || '',
                      channel_id: channelId,
                      channel_type: channelType,
                      extra: info.extra ?? undefined
                    }
                  } as typeof msg;
                  if (
                    (curName !== info.name) ||
                    (curAvatar !== (info.avatar || curAvatar || ''))
                  ) {
                    messagesChanged = true;
                    return nextMsg;
                  }
                }
                return msg;
              });
            }

            // Also update activeChat if it refers to the same channel
            let activeChanged = false;
            let updatedActive = state.activeChat;
            if (state.activeChat && state.activeChat.channelId === channelId && state.activeChat.channelType === channelType) {
              const nextActive = {
                ...state.activeChat,
                visitorStatus: (derivedStatus ?? state.activeChat.visitorStatus) as any,
                tags: newTags,
                channelInfo: info,
                lastSeenMinutes: computedLastSeen
              } as typeof state.activeChat;
              const prevTagsA = state.activeChat.tags || [];
              const tagsChangedA = prevTagsA.length !== newTags.length || prevTagsA.some((t, i) => t.name !== newTags[i]?.name || t.color !== newTags[i]?.color);
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
            if (messagesChanged) partial.messages = updatedMessages;
            if (activeChanged) partial.activeChat = updatedActive!;
            return Object.keys(partial).length > 0 ? partial : {};
          }, false, 'applyChannelInfo');
        },

        // Unified sync: refresh channel then propagate to chats and messages
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

        // Real-time message handling methods
        handleRealtimeMessage: (message: Message) => {
          console.log('📨 Chat Store: Handling real-time message', {
            messageId: message.messageId || message.id,
            content: message.content.substring(0, 50) + '...',
            sender: message.fromInfo?.name,
            type: message.type,
            channelId: message.channelId,
            channelType: message.channelType
          });

          const { activeChat, updateConversationLastMessage, moveConversationToTop, incrementUnreadCount } = get();
          const channelId = message.channelId || message.fromUid;
          const channelType = message.channelType ?? DEFAULT_CHANNEL_TYPE;
          const clientMsgNo = message.clientMsgNo;
          const channelStore = useChannelStore.getState();

          if (!channelId) {
            console.warn('📨 Chat Store: Message missing channel ID, cannot update conversation');
            return;
          }

          // 0. Auto-create conversation if not exists (visitor messages only)
          let createdNewConversation = false;
          if (message.type === MESSAGE_SENDER_TYPE.VISITOR) {
            const key = getChannelKey(channelId, channelType);
            const platform = WuKongIMUtils.getPlatformFromChannelType(channelType);
            const isoTs = message.timestamp && !isNaN(new Date(message.timestamp).getTime())
              ? new Date(message.timestamp).toISOString()
              : new Date().toISOString();
            const sec = Math.floor(new Date(isoTs).getTime() / 1000);

            set((state) => {
              const exists = state.chats.some(c => c.channelId === channelId && c.channelType === channelType);
              if (exists) return {} as any;
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
                metadata: {}
              };
              return { chats: [newChat, ...state.chats] } as any;
            }, false, 'handleRealtimeMessage:autoCreateConversation');

            // Mark onboarding task as completed when receiving a visitor message
            try {
              useOnboardingStore.getState().markTaskCompleted('messageReceived');
            } catch (error) {
              console.error('Failed to mark onboarding task completed:', error);
            }
          }

          // 1. Update conversation list (always)
          updateConversationLastMessage(channelId, channelType, message);
          moveConversationToTop(channelId, channelType);

          // 2. If message is for a different conversation than active, increment unread count
          if (!createdNewConversation && (!activeChat || !isSameChannel(activeChat.channelId, activeChat.channelType, channelId, channelType))) {
            incrementUnreadCount(channelId, channelType);
          }

          if (message.type === MESSAGE_SENDER_TYPE.VISITOR && channelId) {
            const cachedChannel = channelStore.getChannel(channelId, CHANNEL_TYPE.PERSON);
            const fallbackName = message.fromInfo?.name || cachedChannel?.name || `访客${String(channelId).slice(-4)}`;
            const fallbackAvatar = message.fromInfo?.avatar || message.avatar || cachedChannel?.avatar || '';

            channelStore.seedChannel(channelId, 1, {
              name: fallbackName,
              avatar: fallbackAvatar
            });

            channelStore.ensureChannel({ channel_id: channelId, channel_type: 1 }).then(info => {
              if (!info) return;
              get().applyChannelInfo(channelId, 1, info);
            }).catch(error => {
              console.warn('频道信息获取失败（实时消息）:', error);
            });
          }

          // 3. If message is for the currently active conversation, add to message list
          if (activeChat && isSameChannel(activeChat.channelId, activeChat.channelType, channelId, channelType)) {
            console.log('📨 Chat Store: Adding message to active conversation');
            set(
              (state) => {
                if (!clientMsgNo) {
                  return {
                    messages: [...state.messages, message]
                  };
                }

                const existingIndex = state.messages.findIndex(msg =>
                  msg.clientMsgNo === clientMsgNo
                );

                if (existingIndex === -1) {
                  return {
                    messages: [...state.messages, message]
                  };
                }

                const updatedMessages = [...state.messages];
                updatedMessages[existingIndex] = {
                  ...state.messages[existingIndex],
                  ...message,
                  metadata: {
                    ...state.messages[existingIndex]?.metadata,
                    ...message.metadata,
                    is_streaming: false,
                    last_stream_update: Date.now()
                  }
                };

                return { messages: updatedMessages };
              },
              false,
              'handleRealtimeMessage:updateExisting'
            );
          }
        },

        updateConversationLastMessage: (channelId: string, channelType: number, message: Message) => {
          set(
            (state) => ({
              chats: state.chats.map(chat => {
                if (chat.channelId === channelId && chat.channelType === channelType) {
                  const isoTs = message.timestamp && !isNaN(new Date(message.timestamp).getTime())
                    ? new Date(message.timestamp).toISOString()
                    : new Date().toISOString();
                  const sec = Math.floor(new Date(isoTs).getTime() / 1000);
                  return {
                    ...chat,
                    lastMessage: message.content,
                    timestamp: isoTs,
                    lastTimestampSec: sec
                  };
                }
                return chat;
              })
            }),
            false,
            'updateConversationLastMessage'
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
              chats: state.chats.map(chat => {
                if (chat.channelId === channelId && chat.channelType === channelType) {
                  return {
                    ...chat,
                    unreadCount: (chat.unreadCount || 0) + 1,
                    priority: CHAT_PRIORITY_CONST.HIGH // Mark as high priority when unread
                  };
                }
                return chat;
              })
            }),
            false,
            'incrementUnreadCount'
          );
        },


        clearConversationUnread: async (channelId: string, channelType: number) => {
          if (!channelId || channelType == null) return;
          const state = get();
          const target = state.chats.find(c => c.channelId === channelId && c.channelType === channelType);
          if (!target || (target.unreadCount || 0) <= 0) {
            // Avoid duplicate API calls when already cleared
            return;
          }

          // Optimistic local update for better UX
          set(
            (s) => ({
              chats: s.chats.map(c => {
                if (c.channelId === channelId && c.channelType === channelType) {
                  return {
                    ...c,
                    unreadCount: 0,
                    // Restore priority back to normal when unread is cleared
                    priority: c.priority === CHAT_PRIORITY_CONST.HIGH ? CHAT_PRIORITY_CONST.NORMAL : c.priority
                  };
                }
                return c;
              })
            }),
            false,
            'clearConversationUnread:local'
          );

          // Notify backend (debounced per conversation)
          try {
            const key = getChannelKey(channelId, channelType);
            if (pendingUnreadTimers[key]) {
              clearTimeout(pendingUnreadTimers[key]);
            }
            pendingUnreadTimers[key] = setTimeout(async () => {
              try {
                await WuKongIMApiService.setConversationUnread(channelId, channelType, 0);
              } catch (err) {
                console.warn('清零未读数失败（已本地乐观更新）:', { channelId, channelType, error: err });
              } finally {
                delete pendingUnreadTimers[key];
              }
            }, 300);
          } catch (err) {
            // Guard against unexpected scheduling errors
            console.warn('清零未读数调度失败（已本地乐观更新）:', { channelId, channelType, error: err });
          }
        },

        /**
         * Append content to a stream message (AI incremental updates)
         * @param clientMsgNo - The client_msg_no of the message to update
         * @param content - The content to append
         */
        appendStreamMessageContent: (clientMsgNo: string, content: string) => {
          const state = get();

          // Find the message by clientMsgNo (flattened)
          const messageIndex = state.messages.findIndex(msg =>
            msg.clientMsgNo === clientMsgNo
          );

          if (messageIndex === -1) {
            console.warn('🤖 Chat Store: Message not found for stream update', {
              clientMsgNo,
              availableMessages: state.messages.map(m => ({
                id: m.id,
                clientMsgNo: m.clientMsgNo,
                content_preview: m.content.substring(0, 30)
              }))
            });
            return;
          }

          const message = state.messages[messageIndex];
          const metadata = message.metadata ?? {};
          const hasStreamStarted = metadata.stream_started === true;
          const isFirstChunk = !hasStreamStarted;
          const oldContent = message.content;



          const baseContent = isFirstChunk ? '' : oldContent;
          const newContent = baseContent + content;

          console.log("newContent---->",newContent)

          console.log('🤖 Chat Store: Updating message content', {
            messageId: message.id,
            clientMsgNo,
            isFirstChunk,
            oldContentLength: oldContent.length,
            appendedLength: content.length,
            newContentLength: newContent.length,
            oldPreview: oldContent.substring(0, 50),
            newPreview: newContent.substring(0, 50)
          });

          // Update the message with appended content
          set(
            (state) => {
              const updatedMessages = state.messages.map((msg, idx) => {
                if (idx === messageIndex) {
                  return {
                    ...msg,
                    content: newContent,
                    metadata: {
                      ...(msg.metadata ?? {}),
                      has_stream_data: true, // Mark as stream data for Markdown rendering
                      is_streaming: true, // Flag to indicate message is still streaming
                      stream_started: true, // Ensure subsequent chunks append to streamed content
                      last_stream_update: Date.now()
                    }
                  };
                }
                return msg;
              });

              // Update conversation preview for the streaming message's chat
              const targetChannelId = message.channelId;
              const targetChannelType = message.channelType;
              const shouldUpdatePreview = newContent.length > 0;
              const updatedChats = state.chats.map(chat => {
                if (chat.channelId === targetChannelId && chat.channelType === (targetChannelType ?? chat.channelType)) {
                  return shouldUpdatePreview ? { ...chat, lastMessage: newContent } : chat;
                }
                return chat;
              });

              return { messages: updatedMessages, chats: updatedChats };
            },
            false,
            'appendStreamMessageContent'
          );

          console.log('🤖 Chat Store: Stream message content appended successfully', {
            messageId: message.id,
            finalContentLength: newContent.length
          });
        },

        // Initialize store with empty data; conversations will be loaded from real APIs
        initializeStore: async () => {
          set({ chats: [] }, false, 'initializeEmpty');
        },

        // Clear all store data (for logout)
        clearStore: () => {
          console.log('🗑️ Chat Store: Clearing all data for logout');
          try { useChannelStore.getState().clear(); } catch {}
          // Clear any pending unread debounce timers
          try {
            Object.values(pendingUnreadTimers).forEach((t) => clearTimeout(t));
            Object.keys(pendingUnreadTimers).forEach((k) => delete (pendingUnreadTimers as any)[k]);
          } catch {}
          set({
            chats: [],
            activeChat: null,
            searchQuery: '',
            messages: [],
            isLoading: false,
            isSending: false,
            isSyncing: false,
            lastSyncTime: null,
            syncVersion: 0,
            syncError: null,
            historicalMessages: {},
            isLoadingHistory: false,
            historyError: null,
            hasMoreHistory: {},
            nextHistorySeq: {},
            hasMoreNewerHistory: {},
            nextNewerSeq: {}
          }, false, 'clearStore');
        }
      }),
      {
        name: STORAGE_KEYS.CHAT,
        partialize: (state) => ({
          // 只持久化用户偏好，不持久化聊天数据
          searchQuery: state.searchQuery
        })
      }
    ),
    { name: STORAGE_KEYS.CHAT }
  )
);

