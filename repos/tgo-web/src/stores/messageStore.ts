import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import type { Message, WuKongIMMessage, ChannelInfo } from '@/types';
import { WuKongIMApiService, WuKongIMUtils } from '@/services/wukongimApi';
import { getChannelKey } from '@/utils/channelUtils';
import { MESSAGE_SENDER_TYPE, STORAGE_KEYS } from '@/constants';

// Track channels currently loading history to prevent duplicate requests
const loadingHistoryChannels = new Set<string>();

/**
 * Stream End Reason constants - matches backend definitions
 * Used to indicate why a stream was completed
 */
export const StreamEndReason = {
  /** Stream completed successfully (default) */
  SUCCESS: 0,
  /** Stream ended due to inactivity timeout */
  TIMEOUT: 1,
  /** Stream ended due to an error */
  ERROR: 2,
  /** Stream was manually cancelled */
  CANCELLED: 3,
  /** Stream was forcefully ended (e.g., channel closure) */
  FORCE: 4,
} as const;

export type StreamEndReasonType = (typeof StreamEndReason)[keyof typeof StreamEndReason];

/**
 * Message Store State Interface
 * Manages real-time messages, historical messages, and streaming
 */
interface MessageState {
  // 实时消息
  messages: Message[];
  isLoading: boolean;
  isSending: boolean;

  // 历史消息
  historicalMessages: Record<string, WuKongIMMessage[]>; // channelKey -> messages
  isLoadingHistory: boolean;
  historyError: string | null;
  hasMoreHistory: Record<string, boolean>; // channelKey -> hasMore（更旧方向）
  nextHistorySeq: Record<string, number>; // channelKey -> nextSeq（更旧方向）
  hasMoreNewerHistory: Record<string, boolean>; // channelKey -> hasMore（更新方向）
  nextNewerSeq: Record<string, number>; // channelKey -> nextSeq（更新方向）

  // 流式消息
  isStreamingInProgress: boolean;
  streamingClientMsgNo: string | null;

  // 目标消息定位（从搜索跳转）
  targetMessageLocation: { channelId: string; channelType: number; messageSeq: number } | null;

  // Actions - 实时消息
  addMessage: (message: Message) => void;
  updateMessageByClientMsgNo: (clientMsgNo: string, patch: Partial<Message>) => void;
  loadMessages: (chatId: string) => Promise<void>;
  setMessages: (messages: Message[]) => void;
  setLoading: (loading: boolean) => void;
  setSending: (sending: boolean) => void;

  // Actions - 历史消息
  loadHistoricalMessages: (channelId: string, channelType: number) => Promise<void>;
  loadMoreHistory: (channelId: string, channelType: number) => Promise<void>;
  loadNewerHistory: (channelId: string, channelType: number) => Promise<void>;
  loadMessageContext: (channelId: string, channelType: number, targetSeq: number, totalLimit?: number) => Promise<void>;
  clearHistoricalMessages: (channelId: string, channelType: number) => void;
  setLoadingHistory: (loading: boolean) => void;
  setHistoryError: (error: string | null) => void;
  getChannelMessages: (channelId: string, channelType: number) => WuKongIMMessage[];

  // Actions - 流式消息
  appendStreamMessageContent: (clientMsgNo: string, content: string) => void;
  markStreamMessageEnd: (clientMsgNo: string, error?: string) => void;
  cancelStreamingMessage: () => Promise<void>;
  setStreamingState: (inProgress: boolean, clientMsgNo: string | null) => void;

  // Actions - 目标消息
  setTargetMessageLocation: (loc: { channelId: string; channelType: number; messageSeq: number } | null) => void;

  // Actions - Channel 信息应用（仅消息部分）
  applyChannelInfoToMessages: (channelId: string, channelType: number, info: ChannelInfo) => void;

  // Actions - 更新会话预览（供流式消息使用）
  // 注意：这个方法需要调用 conversationStore，在跨 store 通信中实现
  onConversationPreviewUpdate?: (channelId: string, channelType: number, content: string) => void;

  // Actions - 清理
  clearMessageStore: () => void;
}

export const useMessageStore = create<MessageState>()(
  devtools(
    (set, get) => ({
      // Initial state
      messages: [],
      isLoading: false,
      isSending: false,
      historicalMessages: {},
      isLoadingHistory: false,
      historyError: null,
      hasMoreHistory: {},
      nextHistorySeq: {},
      hasMoreNewerHistory: {},
      nextNewerSeq: {},
      isStreamingInProgress: false,
      streamingClientMsgNo: null,
      targetMessageLocation: null,

      // Real-time message actions
      addMessage: (message) =>
        set((state) => ({ messages: [...state.messages, message] }), false, 'addMessage'),

      updateMessageByClientMsgNo: (clientMsgNo, patch) =>
        set(
          (state) => {
            const idx = state.messages.findIndex((m) => m.clientMsgNo === clientMsgNo || m.id === clientMsgNo);
            if (idx === -1) {
              return {} as any;
            }
            const prev = state.messages[idx];
            const merged: Message = {
              ...prev,
              ...patch,
              metadata: {
                ...(prev.metadata || {}),
                ...(patch.metadata || {}),
              },
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

      setMessages: (messages) => set({ messages }, false, 'setMessages'),

      setLoading: (loading) => set({ isLoading: loading }, false, 'setLoading'),

      setSending: (sending) => set({ isSending: sending }, false, 'setSending'),

      // Historical message actions
      loadHistoricalMessages: async (channelId: string, channelType: number) => {
        const key = getChannelKey(channelId, channelType);

        // 防止重复请求：如果该频道正在加载中，直接返回
        if (loadingHistoryChannels.has(key)) {
          console.log('loadHistoricalMessages: Already loading for', key, ', skipping');
          return;
        }

        loadingHistoryChannels.add(key);
        set({ isLoadingHistory: true, historyError: null });

        try {
          const response = await WuKongIMApiService.getChannelHistory(channelId, channelType, 50);
          console.log('loadHistoricalMessages: Response received for', channelId, response);

          // Sort and store messages for the channel
          const sortedAsc = WuKongIMUtils.sortMessages(response.messages, 'asc');
          set((state) => ({
            historicalMessages: {
              ...state.historicalMessages,
              [key]: sortedAsc,
            },
            hasMoreHistory: {
              ...state.hasMoreHistory,
              [key]: response.more,
            },
            nextHistorySeq: {
              ...state.nextHistorySeq,
              [key]: response.next_start_seq || 0,
            },
            isLoadingHistory: false,
          }));

          // 加载完成，清除跟踪
          loadingHistoryChannels.delete(key);
        } catch (error) {
          console.error('Failed to load historical messages:', error);
          loadingHistoryChannels.delete(key);
          set({
            historyError: error instanceof Error ? error.message : '加载历史消息失败',
            isLoadingHistory: false,
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
          const earliestSeq =
            currentMessages.length > 0
              ? Math.min(...currentMessages.map((m) => m.message_seq))
              : state.nextHistorySeq[key] || 0;

          const response = await WuKongIMApiService.loadMoreMessages(channelId, channelType, earliestSeq, 50);
          set((state) => ({
            historicalMessages: {
              ...state.historicalMessages,
              [key]: WuKongIMUtils.mergeMessages(state.historicalMessages[key] || [], response.messages, 'asc'),
            },
            hasMoreHistory: {
              ...state.hasMoreHistory,
              [key]: response.more,
            },
            nextHistorySeq: {
              ...state.nextHistorySeq,
              [key]: response.next_start_seq || 0,
            },
            isLoadingHistory: false,
          }));
        } catch (error) {
          console.error('Failed to load more historical messages:', error);
          set({
            historyError: error instanceof Error ? error.message : '加载更多消息失败',
            isLoadingHistory: false,
          });
        }
      },

      loadNewerHistory: async (channelId: string, channelType: number) => {
        if (!channelId || channelType == null) return;
        const state = get();
        const key = getChannelKey(channelId, channelType);
        const current = state.historicalMessages[key] || [];
        const currentMaxSeq = current.length > 0 ? current[current.length - 1].message_seq : 0;

        // 无更多较新历史且已到最新
        if (state.hasMoreNewerHistory?.[key] === false) {
          return;
        }

        try {
          const resp = await WuKongIMApiService.syncChannelMessages({
            channel_id: channelId,
            channel_type: channelType,
            start_message_seq: currentMaxSeq,
            end_message_seq: 0,
            pull_mode: 1, // 向上/较新
            limit: 50,
          } as any);

          const merged = WuKongIMUtils.mergeMessages(current, resp?.messages || [], 'asc');

          set(
            (s) => ({
              historicalMessages: {
                ...s.historicalMessages,
                [key]: merged,
              },
              hasMoreNewerHistory: {
                ...s.hasMoreNewerHistory,
                [key]: Boolean(resp?.more),
              },
              nextNewerSeq: {
                ...s.nextNewerSeq,
                [key]: resp?.next_start_seq || 0,
              },
            }),
            false,
            'loadNewerHistorySuccess'
          );
        } catch (error) {
          console.error('Failed to load newer messages:', error);
          set({ historyError: error instanceof Error ? error.message : '加载更新消息失败' }, false, 'loadNewerHistoryError');
        }
      },

      loadMessageContext: async (channelId: string, channelType: number, targetSeq: number, totalLimit: number = 20) => {
        if (!channelId || channelType == null || !targetSeq) return;
        const key = getChannelKey(channelId, channelType);
        const half = Math.max(1, Math.floor(totalLimit / 2));
        set({ isLoadingHistory: true, historyError: null }, false, 'loadMessageContextStart');
        try {
          const reqBase = { channel_id: channelId, channel_type: channelType, start_message_seq: targetSeq, end_message_seq: 0 } as any;
          const [downResp, upResp] = await Promise.all([
            WuKongIMApiService.syncChannelMessages({ ...reqBase, pull_mode: 0, limit: half }), // 向下/更旧，包含目标
            WuKongIMApiService.syncChannelMessages({ ...reqBase, pull_mode: 1, limit: half }), // 向上/更新，包含目标
          ]);
          const mergedArr = [...(downResp?.messages || []), ...(upResp?.messages || [])];
          // 去重，避免目标消息（start_message_seq）在双向结果中重复
          const deduped = WuKongIMUtils.deduplicateMessages(mergedArr);
          const sorted = WuKongIMUtils.sortMessages(deduped, 'asc');
          set((state) => ({
            historicalMessages: {
              ...state.historicalMessages,
              [key]: sorted, // 直接替换，确保连续上下文
            },
            // "更旧方向"翻页信息（用于顶部继续加载更早）
            hasMoreHistory: {
              ...state.hasMoreHistory,
              [key]: Boolean(downResp?.more),
            },
            nextHistorySeq: {
              ...state.nextHistorySeq,
              [key]: downResp?.next_start_seq || 0,
            },
            // "更新方向"翻页信息（用于底部继续加载较新）
            hasMoreNewerHistory: {
              ...state.hasMoreNewerHistory,
              [key]: Boolean(upResp?.more),
            },
            nextNewerSeq: {
              ...state.nextNewerSeq,
              [key]: upResp?.next_start_seq || 0,
            },
            isLoadingHistory: false,
          }));
        } catch (error) {
          console.error('Failed to load message context by seq:', error);
          set(
            { historyError: error instanceof Error ? error.message : '加载消息上下文失败', isLoadingHistory: false },
            false,
            'loadMessageContextError'
          );
        }
      },

      clearHistoricalMessages: (channelId: string, channelType: number) => {
        const key = getChannelKey(channelId, channelType);
        set(
          (state) => ({
            historicalMessages: {
              ...state.historicalMessages,
              [key]: [],
            },
            hasMoreHistory: {
              ...state.hasMoreHistory,
              [key]: true,
            },
            nextHistorySeq: {
              ...state.nextHistorySeq,
              [key]: 0,
            },
            hasMoreNewerHistory: {
              ...state.hasMoreNewerHistory,
              [key]: false,
            },
            nextNewerSeq: {
              ...state.nextNewerSeq,
              [key]: 0,
            },
          }),
          false,
          'clearHistoricalMessages'
        );
      },

      setLoadingHistory: (loading: boolean) => set({ isLoadingHistory: loading }),

      setHistoryError: (error: string | null) => set({ historyError: error }),

      getChannelMessages: (channelId: string, channelType: number): WuKongIMMessage[] => {
        const state = get();
        const key = getChannelKey(channelId, channelType);
        return state.historicalMessages[key] || [];
      },

      // Streaming message actions
      appendStreamMessageContent: (clientMsgNo: string, content: string) => {
        const state = get();

        // Find the message by clientMsgNo in real-time messages first
        const messageIndex = state.messages.findIndex((msg) => msg.clientMsgNo === clientMsgNo);

        // If not found in real-time messages, check historical messages
        if (messageIndex === -1) {
          // Search in historicalMessages (WuKongIMMessage format)
          let foundInHistory = false;
          let historyChannelKey: string | null = null;
          let historyMessageIndex = -1;

          for (const [channelKey, messages] of Object.entries(state.historicalMessages)) {
            const idx = messages.findIndex((msg) => msg.client_msg_no === clientMsgNo);
            if (idx !== -1) {
              foundInHistory = true;
              historyChannelKey = channelKey;
              historyMessageIndex = idx;
              break;
            }
          }

          if (foundInHistory && historyChannelKey !== null && historyMessageIndex !== -1) {
            // Update historical message
            const historyMessage = state.historicalMessages[historyChannelKey][historyMessageIndex];
            const oldStreamData = historyMessage.stream_data || '';
            const newStreamData = oldStreamData + content;

            console.log('🤖 Message Store: Updating historical message stream_data', {
              clientMsgNo,
              channelKey: historyChannelKey,
              oldLength: oldStreamData.length,
              appendedLength: content.length,
              newLength: newStreamData.length,
            });

            set(
              (s) => {
                const updatedHistoricalMessages = { ...s.historicalMessages };
                const channelMessages = [...(updatedHistoricalMessages[historyChannelKey!] || [])];
                if (channelMessages[historyMessageIndex]) {
                  channelMessages[historyMessageIndex] = {
                    ...channelMessages[historyMessageIndex],
                    stream_data: newStreamData,
                  };
                  updatedHistoricalMessages[historyChannelKey!] = channelMessages;
                }

                return { historicalMessages: updatedHistoricalMessages };
              },
              false,
              'appendStreamMessageContent:historical'
            );

            // Notify conversation store to update preview (if callback is set)
            const onUpdate = get().onConversationPreviewUpdate;
            if (onUpdate && newStreamData.length > 0) {
              // Parse channelKey to get channelId and channelType
              const parts = historyChannelKey.split(':');
              if (parts.length === 2) {
                onUpdate(parts[0], parseInt(parts[1], 10), newStreamData);
              }
            }
            return;
          }

          // Message not found in either location
          console.warn('🤖 Message Store: Message not found for stream update', {
            clientMsgNo,
            realtimeMessagesCount: state.messages.length,
            historicalChannels: Object.keys(state.historicalMessages).length,
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

        console.log('🤖 Message Store: Updating message content', {
          messageId: message.id,
          clientMsgNo,
          isFirstChunk,
          oldContentLength: oldContent.length,
          appendedLength: content.length,
          newContentLength: newContent.length,
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
                    last_stream_update: Date.now(),
                  },
                };
              }
              return msg;
            });

            return { messages: updatedMessages };
          },
          false,
          'appendStreamMessageContent'
        );

        // Notify conversation store to update preview (if callback is set)
        const onUpdate = get().onConversationPreviewUpdate;
        if (onUpdate && message.channelId && newContent.length > 0) {
          onUpdate(message.channelId, message.channelType ?? 1, newContent);
        }

        console.log('🤖 Message Store: Stream message content appended successfully', {
          messageId: message.id,
          finalContentLength: newContent.length,
        });
      },

      markStreamMessageEnd: (clientMsgNo: string, error?: string) => {
        const state = get();

        // Find the message by clientMsgNo in real-time messages first
        const messageIndex = state.messages.findIndex((msg) => msg.clientMsgNo === clientMsgNo);

        // If found in real-time messages, mark as stream ended
        if (messageIndex !== -1) {
          console.log('🤖 Message Store: Marking stream message as ended (realtime)', { clientMsgNo, error });
          set(
            (s) => {
              const updatedMessages = s.messages.map((msg, idx) => {
                if (idx === messageIndex) {
                  const hasContent = Boolean(msg.content?.trim());
                  return {
                    ...msg,
                    metadata: {
                      ...(msg.metadata ?? {}),
                      is_streaming: false,
                      has_stream_data: hasContent,
                      stream_end: 1,
                      stream_end_reason: error ? 1 : 0, // 1 = error, 0 = success
                      error: error || undefined, // Store error message if present
                    },
                  };
                }
                return msg;
              });
              return {
                messages: updatedMessages,
                isStreamingInProgress: false,
                streamingClientMsgNo: null,
              };
            },
            false,
            'markStreamMessageEnd:realtime'
          );
          return;
        }

        // If not found in real-time messages, check historical messages
        for (const [channelKey, messages] of Object.entries(state.historicalMessages)) {
          const idx = messages.findIndex((msg) => msg.client_msg_no === clientMsgNo);
          if (idx !== -1) {
            console.log('🤖 Message Store: Marking stream message as ended (historical)', { clientMsgNo, channelKey, error });
            set(
              (s) => {
                const updatedHistoricalMessages = { ...s.historicalMessages };
                const channelMessages = [...(updatedHistoricalMessages[channelKey] || [])];
                if (channelMessages[idx]) {
                  channelMessages[idx] = {
                    ...channelMessages[idx],
                    end: 1, // Mark as ended
                    end_reason: error ? 1 : 0, // 1 = error, 0 = success
                    error: error || undefined, // Store error message at WuKongIMMessage level
                  };
                  updatedHistoricalMessages[channelKey] = channelMessages;
                }
                return {
                  historicalMessages: updatedHistoricalMessages,
                  isStreamingInProgress: false,
                  streamingClientMsgNo: null,
                };
              },
              false,
              'markStreamMessageEnd:historical'
            );
            return;
          }
        }

        // If message not found, still clear streaming state (safety measure)
        console.warn('🤖 Message Store: Message not found for stream end', { clientMsgNo });
        set(
          {
            isStreamingInProgress: false,
            streamingClientMsgNo: null,
          },
          false,
          'markStreamMessageEnd:notFound'
        );
      },

      cancelStreamingMessage: async () => {
        const state = get();
        const { streamingClientMsgNo, isStreamingInProgress } = state;

        if (!isStreamingInProgress || !streamingClientMsgNo) {
          console.warn('🤖 Message Store: No streaming message to cancel');
          return;
        }

        try {
          const { aiRunsApiService } = await import('@/services/aiRunsApi');
          await aiRunsApiService.cancelByClientNo({
            client_msg_no: streamingClientMsgNo,
            reason: 'User cancelled',
          });
          console.log('🤖 Message Store: Stream message cancelled successfully', { clientMsgNo: streamingClientMsgNo });

          // Clear streaming state
          set(
            {
              isStreamingInProgress: false,
              streamingClientMsgNo: null,
            },
            false,
            'cancelStreamingMessage:success'
          );
        } catch (error) {
          console.error('🤖 Message Store: Failed to cancel stream message:', error);
          throw error;
        }
      },

      setStreamingState: (inProgress, clientMsgNo) =>
        set(
          {
            isStreamingInProgress: inProgress,
            streamingClientMsgNo: clientMsgNo,
          },
          false,
          'setStreamingState'
        ),

      // Target message location
      setTargetMessageLocation: (loc) => set({ targetMessageLocation: loc }, false, 'setTargetMessageLocation'),

      // Apply channel info to messages only
      applyChannelInfoToMessages: (channelId: string, channelType: number, info: ChannelInfo) => {
        if (!channelId || channelType == null) return;

        set((state) => {
          // Update messages only when we actually modify at least one message
          let messagesChanged = false;
          let updatedMessages = state.messages;
          if (state.messages.length > 0) {
            updatedMessages = state.messages.map((msg) => {
              if (msg.channelId === channelId && msg.channelType === channelType && msg.type === MESSAGE_SENDER_TYPE.VISITOR) {
                const curName = msg.fromInfo?.name;
                const curAvatar = msg.fromInfo?.avatar || msg.avatar;
                const nextMsg = {
                  ...msg,
                  fromInfo: {
                    name: info.name,
                    avatar: info.avatar || curAvatar || '',
                    channel_id: channelId,
                    channel_type: channelType,
                    extra: info.extra ?? undefined,
                  },
                } as typeof msg;
                if (curName !== info.name || curAvatar !== (info.avatar || curAvatar || '')) {
                  messagesChanged = true;
                  return nextMsg;
                }
              }
              return msg;
            });
          }

          // If nothing actually changed, return the original state slice to avoid re-renders
          return messagesChanged ? { messages: updatedMessages } : {};
        }, false, 'applyChannelInfoToMessages');
      },

      // Clear store
      clearMessageStore: () => {
        loadingHistoryChannels.clear();
        set(
          {
            messages: [],
            isLoading: false,
            isSending: false,
            historicalMessages: {},
            isLoadingHistory: false,
            historyError: null,
            hasMoreHistory: {},
            nextHistorySeq: {},
            hasMoreNewerHistory: {},
            nextNewerSeq: {},
            isStreamingInProgress: false,
            streamingClientMsgNo: null,
            targetMessageLocation: null,
          },
          false,
          'clearMessageStore'
        );
      },
    }),
    { name: STORAGE_KEYS.MESSAGE || 'MessageStore' }
  )
);

// Selectors for optimized subscriptions
export const messageSelectors = {
  messages: (state: MessageState) => state.messages,
  isLoading: (state: MessageState) => state.isLoading || state.isSending,
  isLoadingHistory: (state: MessageState) => state.isLoadingHistory,
  historyError: (state: MessageState) => state.historyError,
  isStreamingInProgress: (state: MessageState) => state.isStreamingInProgress,
  streamingClientMsgNo: (state: MessageState) => state.streamingClientMsgNo,
  targetMessageLocation: (state: MessageState) => state.targetMessageLocation,
};
