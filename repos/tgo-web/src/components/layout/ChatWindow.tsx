import React, { useCallback, useEffect, useState } from 'react';
import ChatHeader from '../chat/ChatHeader';
import MessagesList from '../chat/MessagesList';
import MessageInput from '../chat/MessageInput';
import EmptyState from '../chat/EmptyState';
import DevModeToolbar from '../chat/DevModeToolbar';
import { useHistoricalMessages } from '@/hooks/useHistoricalMessages';
import { useWuKongIMWebSocket } from '@/hooks/useWuKongIMWebSocket';
import { useChatStore } from '@/stores/chatStore';
import { useAuthStore } from '@/stores/authStore';
import { useChannelStore } from '@/stores/channelStore';
import { useAppSettingsStore } from '@/stores/appSettingsStore';
import type { Chat, Message, ChannelVisitorExtra } from '@/types';
import { PlatformType, MessagePayloadType } from '@/types';
import { chatMessagesApiService } from '@/services/chatMessagesApi';
import { useToast } from '@/hooks/useToast';
import { showApiError } from '@/utils/toastHelpers';
import { useTranslation } from 'react-i18next';
import { WsSendError } from '@/services/wukongimWebSocket';

/**
 * Props for the ChatWindow component
 */
export interface ChatWindowProps {
  /** The currently active chat */
  activeChat?: Chat;
  /** Callback when a message is sent */
  onSendMessage?: (message: string) => void;
  /** Callback when a visitor is accepted from the waiting queue */
  onAcceptVisitor?: () => void;
  /** Callback when a chat is ended successfully (with channel info) */
  onEndChatSuccess?: (channelId: string, channelType: number) => void;
}

/**
 * Main chat window component - refactored for better maintainability
 *
 * Features:
 * - WuKongIM historical message integration with infinite scroll
 * - Fallback to mock messages for non-WuKongIM chats
 * - Optimized rendering with memoized sub-components
 * - Stable selectors to prevent infinite loops
 * - Comprehensive error handling and loading states
 *
 * @param activeChat - The currently active chat
 * @param onSendMessage - Callback when a message is sent
 */
const ChatWindow: React.FC<ChatWindowProps> = React.memo(({ activeChat, onSendMessage, onAcceptVisitor, onEndChatSuccess }) => {
  const { t } = useTranslation();
  // Get channel info for WuKongIM integration (flattened on Chat)
  const channelId = activeChat?.channelId;
  const channelType = activeChat?.channelType;
  const isWuKongIMChat = Boolean(channelId && channelType);

  // State for message sending
  const [isSending, setIsSending] = useState(false);

  // Dev mode state
  const devMode = useAppSettingsStore(state => state.devMode);
  const canShowDevTools = import.meta.env.DEV;

  // Get current user info for message attribution
  const user = useAuthStore(state => state.user);

  // Chat store actions
  const addMessage = useChatStore(state => state.addMessage);
  const updateMessageByClientMsgNo = useChatStore(state => state.updateMessageByClientMsgNo);

  const updateConversationLastMessage = useChatStore(state => state.updateConversationLastMessage);
  const moveConversationToTop = useChatStore(state => state.moveConversationToTop);
  const loadNewerHistory = useChatStore(state => state.loadNewerHistory);

  // Use custom hook for historical messages management
  const {
    historicalMessages,
    hasMoreHistory,
    isLoadingHistory,
    isLoadingMore,
    historyError,
    loadMoreHistory,
    retryLoadHistory,
    convertWuKongIMToMessage
  } = useHistoricalMessages({ channelId, channelType });

  // Subscribe to real-time messages from chat store and filter by channel
  const allRealtimeMessages = useChatStore(state => state.messages);

  // Filter real-time messages to only show messages for the current conversation
  const realtimeMessages = React.useMemo(() => {
    if (!channelId || !isWuKongIMChat) {
      return [];
    }

    return allRealtimeMessages.filter(message =>
      message.channelId === channelId &&
      message.channelType === channelType
    );
  }, [allRealtimeMessages, channelId, channelType, isWuKongIMChat]);

  // Use WebSocket directly
  const { sendMessage: sendWsMessage, isConnected } = useWuKongIMWebSocket();

  // Resolve platform type from channel info
  const channelInfo = useChannelStore(state =>
    channelId && typeof channelType === 'number'
      ? state.getChannel(channelId, channelType)
      : undefined
  );
  const platformType = (channelInfo?.extra as ChannelVisitorExtra | undefined)?.platform_type;
  const { showToast } = useToast();



  // Memoized event handlers to prevent unnecessary re-renders
  const handleSuggestionClick = useCallback((suggestion: string): void => {
    onSendMessage?.(suggestion);
  }, [onSendMessage]);

  // Check if current chat is an agent chat or team chat
  const isAgentChat = channelId?.endsWith('-agent') ?? false;
  const isTeamChat = channelId?.endsWith('-team') ?? false;
  const isAIChat = isAgentChat || isTeamChat;

  // Enhanced message sending with platform-aware flow (REST first for non-website, then WebSocket)
  // For agent/team chats, use REST API instead of WebSocket
  const handleSendMessage = useCallback(async (message: string): Promise<void> => {
    if (!message.trim()) {
      console.warn('Cannot send empty message');
      return;
    }
    setIsSending(true);
    try {
      if (isWuKongIMChat && channelId && channelType) {
        const nowId = `local-${Date.now()}`;
        const payload = {
          type: MessagePayloadType.TEXT,
          content: message.trim(),
          timestamp: Date.now(),
        };

        // Agent/Team chat: use REST API (/v1/chat/team) instead of WebSocket
        // Don't add local message - rely on WebSocket to receive the message back
        // This prevents duplicate messages in the UI
        if (isAIChat) {
          try {
            let response;
            if (isAgentChat) {
              // Extract agent_id from channelId (format: {agent_id}-agent)
              const agentId = channelId.replace(/-agent$/, '');
              response = await chatMessagesApiService.staffTeamChat({
                agent_id: agentId,
                message: message.trim(),
              });
            } else {
              // Extract team_id from channelId (format: {team_id}-team)
              const teamId = channelId.replace(/-team$/, '');
              response = await chatMessagesApiService.staffTeamChat({
                team_id: teamId,
                message: message.trim(),
              });
            }
            console.log('🤖 AI Chat: Message sent successfully via REST API', {
              channelId,
              clientMsgNo: response.client_msg_no
            });
            onSendMessage?.(message);
          } catch (e: any) {
            const errorKey = isAgentChat ? 'chat.send.agentErrorLog' : 'chat.send.teamErrorLog';
            const errorDefault = isAgentChat ? 'AI员工消息发送失败' : '团队消息发送失败';
            console.error(t(errorKey, errorDefault), e);
            showApiError(showToast, e);
          }
          return;
        }

        // For regular visitor chats: add local message for immediate UI feedback
        const localMessage: Message = {
          id: nowId,
          type: 'staff',
          content: message.trim(),
          timestamp: new Date().toISOString(),
          messageId: nowId,
          clientMsgNo: nowId,
          messageSeq: 0,
          fromUid: user?.id ? `${user.id}-staff` : 'unknown-staff',
          channelId,
          channelType,
          payloadType: 1 as any,
          metadata: { isLocal: true },
        };
        // Immediate UI update for visitor chats
        addMessage(localMessage);
        updateConversationLastMessage(channelId, channelType, localMessage);
        moveConversationToTop(channelId, channelType);

        // If non-website platform, send via REST first
        if (platformType && platformType !== PlatformType.WEBSITE) {
          try {
            await chatMessagesApiService.staffSendPlatformMessage({
              channel_id: channelId,
              channel_type: channelType,
              payload,
              client_msg_no: nowId,
            });
          } catch (e: any) {
            console.error(t('chat.send.platformErrorLog', '\u5e73\u53f0\u6d88\u606f\u53d1\u9001\u5931\u8d25'), e);
            const apiMsg = e?.message || t('chat.send.platformError', '\u5e73\u53f0\u6d88\u606f\u53d1\u9001\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5');
            updateMessageByClientMsgNo(nowId, { metadata: { platform_send_error: true, error_text: apiMsg } as any });
            throw new Error(apiMsg);
          }
        }
        // Send via WebSocket (with dedicated error handling)
        try {
          if (!isConnected) throw new Error(t('chat.send.wsNotConnected', 'WebSocket \u672a\u8fde\u63a5\uff0c\u8bf7\u68c0\u67e5\u7f51\u7edc\u8fde\u63a5'));
          await sendWsMessage(channelId, channelType, payload, nowId);
          // Update message metadata to mark as successfully sent
          updateMessageByClientMsgNo(nowId, { metadata: { ws_sent: true, ws_send_error: false } as any });
          onSendMessage?.(message);
        } catch (e) {
          // 使用 i18n 翻译 WsSendError
          let errMsg: string;
          if (e instanceof WsSendError) {
            errMsg = t(e.i18nKey, e.defaultMessage);
          } else if (e instanceof Error) {
            errMsg = e.message;
          } else {
            errMsg = t('chat.send.wsFailed', 'WebSocket \u53d1\u9001\u5931\u8d25\uff0c\u8bf7\u68c0\u67e5\u7f51\u7edc\u8fde\u63a5');
          }
          updateMessageByClientMsgNo(nowId, { metadata: { ws_send_error: true, error_text: errMsg } as any });
          showApiError(showToast, e);
          return;
        }
      } else {
        // Non-WuKongIM flow
        onSendMessage?.(message);
      }
    } catch (error) {
      console.error(t('chat.send.failedLogPrefix', '\u53d1\u9001\u6d88\u606f\u5931\u8d25:'), error);
      showApiError(showToast, error);
    } finally {
      setIsSending(false);
    }
  }, [isWuKongIMChat, channelId, channelType, isConnected, isAIChat, isAgentChat, user, addMessage, updateConversationLastMessage, moveConversationToTop, platformType, onSendMessage, sendWsMessage, updateMessageByClientMsgNo, showToast, t]);

  // Handle empty state when no chat is selected
  if (!activeChat) {
    return <EmptyState type="no-chat" />;
  }

  // Target message jump & highlight from SearchPanel
  const targetLoc = useChatStore(state => state.targetMessageLocation);
  const loadMessageContext = useChatStore(state => state.loadMessageContext);
  const setTargetMessageLocation = useChatStore(state => state.setTargetMessageLocation);
  const clearHistoricalMessages = useChatStore(state => state.clearHistoricalMessages);
  const setLoadingHistory = useChatStore(state => state.setLoadingHistory);
  const [scrollToSeq, setScrollToSeq] = useState<number | null>(null);
  const [isLoadingNewer, setIsLoadingNewer] = useState(false);

  // Bottom pagination for newer historical messages
  const onLoadMoreNewer = useCallback(async (): Promise<void> => {
    if (!isWuKongIMChat || !channelId || typeof channelType !== 'number') return;
    if (isLoadingNewer) return;
    setIsLoadingNewer(true);
    try {
      await loadNewerHistory(channelId, channelType);
    } finally {
      setIsLoadingNewer(false);
    }
  }, [isWuKongIMChat, channelId, channelType, isLoadingNewer, loadNewerHistory]);

  useEffect(() => {
    if (!isWuKongIMChat || !channelId || typeof channelType !== 'number') return;
    if (!targetLoc) return;
    if (targetLoc.channelId !== channelId || targetLoc.channelType !== channelType) return;

    let cancelled = false;
    const locate = async () => {
      try {
        // 清空并重新加载目标消息上下文，避免断层
        setLoadingHistory(true);
        clearHistoricalMessages(channelId, channelType);
        await loadMessageContext(channelId, channelType, targetLoc.messageSeq, 20);
        if (!cancelled) {
          setScrollToSeq(targetLoc.messageSeq);
        }
      } catch (err) {
        showToast('warning', t('chat.search.locateFailedTitle','\u672a\u80fd\u5b9a\u4f4d\u6d88\u606f'), t('chat.search.locateFailedDesc','\u8be5\u6d88\u606f\u53ef\u80fd\u5df2\u88ab\u5220\u9664\u6216\u6682\u4e0d\u53ef\u7528'));
      } finally {
        // Clear target to avoid repeat
        setTargetMessageLocation(null);
      }
    };
    void locate();
    return () => { cancelled = true; };
  // We want to re-run when target changes or conversation changes
  }, [isWuKongIMChat, channelId, channelType, targetLoc, loadMessageContext, clearHistoricalMessages, setLoadingHistory, setTargetMessageLocation, showToast]);

  // Handle dev mode test message sending (simulates AI assistant response)
  const handleDevModeMessage = useCallback((content: string, isFromAssistant?: boolean) => {
    if (!channelId || typeof channelType !== 'number') {
      console.warn('Cannot send dev mode message without active channel');
      return;
    }

    const nowId = `dev-${Date.now()}`;
    const devMessage: Message = {
      id: nowId,
      // Use 'system' type for AI assistant messages in dev mode
      type: "staff",
      content: content,
      timestamp: new Date().toISOString(),
      messageId: nowId,
      clientMsgNo: nowId,
      messageSeq: Date.now(), // Use timestamp as sequence for ordering
      fromUid: isFromAssistant ? 'dev-assistant' : (user?.id ? `${user.id}-staff` : 'unknown-staff'),
      channelId,
      channelType,
      payloadType: 1 as any,
      // has_stream_data enables MarkdownContent rendering which supports UI Widget parsing
      metadata: { isDevMode: true, isAIResponse: isFromAssistant, has_stream_data: true },
    };

    // Add message to chat store
    addMessage(devMessage);
    updateConversationLastMessage(channelId, channelType, devMessage);
  }, [channelId, channelType, user, addMessage, updateConversationLastMessage]);

  return (
    <main className="flex-grow flex flex-col bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-900 dark:to-gray-800">
      {/* Chat Header */}
      <ChatHeader activeChat={activeChat} onEndChatSuccess={onEndChatSuccess} />

      {/* Messages Area */}
      <div className="flex-1 min-h-0 overflow-hidden">
        <MessagesList
          key={activeChat.id}
          isWuKongIMChat={isWuKongIMChat}
          historicalMessages={historicalMessages}
          realtimeMessages={realtimeMessages}
          isLoadingHistory={isLoadingHistory}
          isLoadingMore={isLoadingMore}
          historyError={historyError}
          hasMoreHistory={hasMoreHistory}
          hasMoreNewerHistory={Boolean((activeChat?.lastMsgSeq ?? 0) > (historicalMessages[historicalMessages.length - 1]?.message_seq ?? 0))}
          isLoadingMoreNewer={isLoadingNewer}
          convertWuKongIMToMessage={convertWuKongIMToMessage}
          onLoadMore={loadMoreHistory}
          onLoadMoreNewer={onLoadMoreNewer}
          onRetry={retryLoadHistory}
          onSuggestionClick={handleSuggestionClick}
          scrollToSeq={scrollToSeq}
          onScrolledToSeq={() => setScrollToSeq(null)}
          onSendMessage={handleSendMessage}
        />
      </div>

      {/* Message Input */}
      <MessageInput
        onSendMessage={handleSendMessage}
        isSending={isSending}
        onAcceptVisitor={onAcceptVisitor}
      />

      {/* Dev Mode Toolbar - only shown when dev mode is enabled */}
      {canShowDevTools && devMode && (
        <DevModeToolbar onSendMessage={handleDevModeMessage} />
      )}
    </main>
  );
});

// Set display name for debugging
ChatWindow.displayName = 'ChatWindow';

export default ChatWindow;
