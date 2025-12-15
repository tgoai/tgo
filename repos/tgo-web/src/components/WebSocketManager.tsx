import React, { useEffect } from 'react';
import { useAuthStore } from '../stores/authStore';
import { useChatStore } from '../stores/chatStore';
import { useChannelStore } from '../stores/channelStore';
import {
  wukongimWebSocketService,
  ConnectionStatus,
  WuKongIMWebSocketConfig,
  type VisitorPresenceEvent,
  type VisitorProfileUpdatedEvent,
} from '../services/wukongimWebSocket';
import { WuKongIMApiService } from '../services/wukongimApi';
import { Message } from '../types';
import { isWebSocketAutoConnectDisabled } from '@/utils/config';

/**
 * Centralized WebSocket manager component
 * This component should be rendered ONCE at the app level to manage
 * the single WebSocket connection and prevent multiple connection attempts.
 */
export const WebSocketManager: React.FC = () => {
  // Use stable selectors to prevent unnecessary re-renders
  const token = useAuthStore(state => state.token);
  const user = useAuthStore(state => state.user);
  const handleRealtimeMessage = useChatStore(state => state.handleRealtimeMessage);
  const appendStreamMessageContent = useChatStore(state => state.appendStreamMessageContent);
  const markStreamMessageEnd = useChatStore(state => state.markStreamMessageEnd);
  const activeChat = useChatStore(state => state.activeChat);

  /**
   * Handle incoming real-time messages
   */
  const handleMessage = React.useCallback((message: Message) => {
    const channelId = message.channelId;
    const isActiveConversation = activeChat?.channelId === channelId;

    console.log('🔌 WebSocket Manager: Received real-time message', {
      messageId: message.id,
      content: message.content.substring(0, 50) + '...',
      sender: message.fromInfo?.name,
      type: message.type,
      channelId: channelId,
      timestamp: message.timestamp,
      isActiveConversation: isActiveConversation,
      activeChannelId: activeChat?.channelId
    });

    if (!channelId) {
      console.warn('🔌 WebSocket Manager: Message missing channel_id, cannot process');
      return;
    }

    try {
      console.log('🔌 WebSocket Manager: Delegating to chat store handleRealtimeMessage');
      handleRealtimeMessage(message);
      console.log('🔌 WebSocket Manager: Real-time message processing completed successfully');
    } catch (error) {
      console.error('🔌 WebSocket Manager: Error in handleRealtimeMessage:', error);
    }
  }, [
    activeChat?.channelId,
    handleRealtimeMessage
  ]);

  // Track if this is a reconnection (not the initial connection)
  const wasConnectedRef = React.useRef(false);
  const forceSyncConversations = useChatStore(state => state.forceSyncConversations);

  /**
   * Handle connection status changes
   */
  const handleConnectionStatus = React.useCallback((status: ConnectionStatus) => {
    console.log('🔌 WebSocket Manager: Connection status changed:', status);
    
    // If we're now connected and we were previously connected (i.e., this is a reconnection)
    if (status.isConnected) {
      if (wasConnectedRef.current) {
        // This is a reconnection, sync conversations
        console.log('🔌 WebSocket Manager: Reconnected, syncing conversations');
        forceSyncConversations().catch(err => {
          console.error('🔌 WebSocket Manager: Failed to sync after reconnection:', err);
        });
      }
      wasConnectedRef.current = true;
    } else if (!status.isConnecting) {
      // Connection lost (not just connecting)
      // Keep wasConnectedRef.current as true to detect next reconnection
    }
  }, [forceSyncConversations]);

  /**
   * Handle WebSocket errors
   */
  const handleError = React.useCallback((error: any) => {
    console.error('🔌 WebSocket Manager: WebSocket error:', error);
  }, []);

  /**
   * Handle AI stream messages (incremental updates)
   */
  const handleStreamMessage = React.useCallback((clientMsgNo: string, content: string) => {

    try {
      // Append content to the message
      appendStreamMessageContent(clientMsgNo, content);
      console.log('🤖 WebSocket Manager: Stream message content appended successfully');
    } catch (error) {
      console.error('🤖 WebSocket Manager: Error appending stream message content:', error);
    }
  }, [appendStreamMessageContent]);

  /**
   * Handle AI stream end events
   * @param clientMsgNo - The client message number
   * @param error - Optional error message from the stream end event
   */
  const handleStreamEnd = React.useCallback((clientMsgNo: string, error?: string) => {
    try {
      markStreamMessageEnd(clientMsgNo, error);
      if (error) {
        console.log('🤖 WebSocket Manager: Stream message ended with error:', error);
      } else {
        console.log('🤖 WebSocket Manager: Stream message marked as ended');
      }
    } catch (err) {
      console.error('🤖 WebSocket Manager: Error marking stream message end:', err);
    }
  }, [markStreamMessageEnd]);

  /**
   * Handle visitor presence events (visitor.online / visitor.offline)
   */
  const handlePresenceEvent = React.useCallback((presence: VisitorPresenceEvent) => {
    try {
      const { channelId, channelType, isOnline, timestamp } = presence;
      if (!channelId || !Number.isFinite(channelType)) return;

      const channelStore = useChannelStore.getState();
      // Update cached channel info presence fields (no fetch)
      channelStore.updateVisitorOnlineStatus(channelId, channelType, isOnline, timestamp ?? undefined);

      // Apply to chat list if the channel exists in cache
      const updatedInfo = channelStore.getChannel(channelId, channelType);
      if (updatedInfo) {
        useChatStore.getState().applyChannelInfo(channelId, channelType, updatedInfo);
      }
    } catch (error) {
      console.error('🔌 WebSocket Manager: Error handling presence event:', error);
    }
  }, []);

  /**
   * Handle visitor.profile.updated events
   */
  const handleVisitorProfileUpdated = React.useCallback(async (evt: VisitorProfileUpdatedEvent) => {
    try {
      const { channelId, channelType } = evt;
      if (!channelId || !Number.isFinite(channelType)) return;

      const channelStore = useChannelStore.getState();
      // Force refresh from API
      await channelStore.refreshChannel({ channel_id: channelId, channel_type: channelType });

      // Apply to chat list if the channel exists in cache
      const updatedInfo = channelStore.getChannel(channelId, channelType);
      if (updatedInfo) {
        useChatStore.getState().applyChannelInfo(channelId, channelType, updatedInfo);
      }
    } catch (error) {
      console.error('🔌 WebSocket Manager: Error handling visitor.profile.updated:', error);
    }
  }, []);



  /**
   * Connect to WebSocket
   */
  const connect = React.useCallback(async () => {
    if (!token) {
      console.log('🔌 WebSocket Manager: No token available, skipping connection');
      return;
    }

    if (!user?.id) {
      console.log('🔌 WebSocket Manager: No user ID available, skipping connection');
      return;
    }

    // Generate dynamic UID using user ID with "-staff" suffix
    const uid = `${user.id}-staff`;

    console.log('🔌 WebSocket Manager: Connecting with dynamic UID', {
      userId: user.id,
      uid: uid,
      hasToken: !!token
    });

    // Resolve server URL dynamically via backend route (with env fallback)
    const serverUrl = await WuKongIMApiService.resolveWebSocketUrl(uid);
    const config: WuKongIMWebSocketConfig = {
      serverUrl,
      uid: uid,
      token: token,
    };

    try {
      await wukongimWebSocketService.init(config);
    } catch (error) {
      console.error('🔌 WebSocket Manager: Failed to connect:', error);
    }
  }, [token, user?.id]);

  /**
   * Setup event listeners on mount
   */
  useEffect(() => {
    console.log('🔌 WebSocket Manager: Setting up event listeners (including stream + presence)');

    const unsubscribeMessage = wukongimWebSocketService.onMessage(handleMessage);
    const unsubscribeStatus = wukongimWebSocketService.onConnectionStatus(handleConnectionStatus);
    const unsubscribeError = wukongimWebSocketService.onError(handleError);
    const unsubscribeStreamMessage = wukongimWebSocketService.onStreamMessage(handleStreamMessage);
    const unsubscribeStreamEnd = wukongimWebSocketService.onStreamEnd(handleStreamEnd);
    const unsubscribePresence = wukongimWebSocketService.onVisitorPresence(handlePresenceEvent);
    const unsubscribeProfileUpdated = wukongimWebSocketService.onVisitorProfileUpdated(handleVisitorProfileUpdated);


    return () => {
      console.log('🔌 WebSocket Manager: Cleaning up event listeners (including stream + presence)');
      unsubscribeMessage();
      unsubscribeStatus();
      unsubscribeError();
      unsubscribeStreamMessage();
      unsubscribeStreamEnd();
      unsubscribePresence();
      unsubscribeProfileUpdated();
    };
  }, [handleMessage, handleConnectionStatus, handleError, handleStreamMessage, handleStreamEnd, handlePresenceEvent, handleVisitorProfileUpdated]);

  /**
   * Auto-connect when token and user are available
   */
  useEffect(() => {
    // Check if auto-connect is disabled via runtime/build-time configuration
    if (isWebSocketAutoConnectDisabled()) {
      console.log('🔌 WebSocket Manager: Auto-connect is disabled via environment variable');
      return;
    }

    if (token && user?.id) {
      console.log('🔌 WebSocket Manager: Token and user available, attempting auto-connect');
      connect().catch(error => {
        console.error('🔌 WebSocket Manager: Auto-connect failed:', error);
      });
    } else {
      console.log('🔌 WebSocket Manager: Token or user not available 1111', {
        hasToken: !!token,
        hasUser: !!user?.id
      });
    }
  }, [token, user?.id, connect]);

  /**
   * Cleanup on unmount
   */
  useEffect(() => {
    return () => {
      console.log('🔌 WebSocket Manager: Component unmounting, disconnecting WebSocket');
      wukongimWebSocketService.safeDisconnect();
    };
  }, []);

  // This component doesn't render anything
  return null;
};