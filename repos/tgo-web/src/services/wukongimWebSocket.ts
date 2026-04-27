import { WKIM, WKIMChannelType, WKIMEvent, ReasonCode } from 'easyjssdk';
import { Message, MessagePayloadType, WuKongIMMessage } from '../types';
import { WuKongIMUtils } from './wukongimApi';
import { CHANNEL_TYPE, WS_EVENT_TYPE } from '@/constants';


export interface WuKongIMWebSocketConfig {
  serverUrl: string;
  uid: string;
  token: string;
}

export interface ConnectionStatus {
  isConnected: boolean;
  isConnecting: boolean;
  error?: string;
}

/**
 * WebSocket 发送消息的返回结果
 */
export interface WsSendResult {
  messageId: string;
  messageSeq: number;
  reasonCode: ReasonCode;
}

/**
 * ReasonCode 错误码对应的 i18n key 和默认消息
 */
export const REASON_CODE_I18N: Record<ReasonCode, { key: string; defaultMessage: string }> = {
  [ReasonCode.Unknown]: { key: 'ws.error.unknown', defaultMessage: '未知错误' },
  [ReasonCode.Success]: { key: 'ws.error.success', defaultMessage: '成功' },
  [ReasonCode.AuthFail]: { key: 'ws.error.authFail', defaultMessage: '认证失败' },
  [ReasonCode.SubscriberNotExist]: { key: 'ws.error.subscriberNotExist', defaultMessage: '订阅者不存在' },
  [ReasonCode.InBlacklist]: { key: 'ws.error.inBlacklist', defaultMessage: '用户在黑名单中' },
  [ReasonCode.ChannelNotExist]: { key: 'ws.error.channelNotExist', defaultMessage: '频道不存在' },
  [ReasonCode.UserNotOnNode]: { key: 'ws.error.userNotOnNode', defaultMessage: '用户不在节点上' },
  [ReasonCode.SenderOffline]: { key: 'ws.error.senderOffline', defaultMessage: '发送者离线' },
  [ReasonCode.MsgKeyError]: { key: 'ws.error.msgKeyError', defaultMessage: '消息密钥错误' },
  [ReasonCode.PayloadDecodeError]: { key: 'ws.error.payloadDecodeError', defaultMessage: '消息解码失败' },
  [ReasonCode.ForwardSendPacketError]: { key: 'ws.error.forwardSendPacketError', defaultMessage: '转发消息失败' },
  [ReasonCode.NotAllowSend]: { key: 'ws.error.notAllowSend', defaultMessage: '不允许发送消息' },
  [ReasonCode.ConnectKick]: { key: 'ws.error.connectKick', defaultMessage: '连接被踢出' },
  [ReasonCode.NotInWhitelist]: { key: 'ws.error.notInWhitelist', defaultMessage: '不在白名单中' },
  [ReasonCode.QueryTokenError]: { key: 'ws.error.queryTokenError', defaultMessage: '查询 Token 失败' },
  [ReasonCode.SystemError]: { key: 'ws.error.systemError', defaultMessage: '系统错误' },
  [ReasonCode.ChannelIDError]: { key: 'ws.error.channelIDError', defaultMessage: '频道 ID 错误' },
  [ReasonCode.NodeMatchError]: { key: 'ws.error.nodeMatchError', defaultMessage: '节点匹配错误' },
  [ReasonCode.NodeNotMatch]: { key: 'ws.error.nodeNotMatch', defaultMessage: '节点不匹配' },
  [ReasonCode.Ban]: { key: 'ws.error.ban', defaultMessage: '频道被禁' },
  [ReasonCode.NotSupportHeader]: { key: 'ws.error.notSupportHeader', defaultMessage: '不支持的消息头' },
  [ReasonCode.ClientKeyIsEmpty]: { key: 'ws.error.clientKeyIsEmpty', defaultMessage: '客户端密钥为空' },
  [ReasonCode.RateLimit]: { key: 'ws.error.rateLimit', defaultMessage: '发送频率限制' },
  [ReasonCode.NotSupportChannelType]: { key: 'ws.error.notSupportChannelType', defaultMessage: '不支持的频道类型' },
  [ReasonCode.Disband]: { key: 'ws.error.disband', defaultMessage: '频道已解散' },
  [ReasonCode.SendBan]: { key: 'ws.error.sendBan', defaultMessage: '发送被禁止' },
};

/**
 * 获取 ReasonCode 对应的错误消息（用于非 React 环境，返回默认消息）
 */
export function getReasonCodeMessage(reasonCode: ReasonCode): string {
  const info = REASON_CODE_I18N[reasonCode];
  return info?.defaultMessage || `发送消息失败 (错误码: ${reasonCode})`;
}

/**
 * 自定义错误类，包含 reasonCode 信息，供上层翻译使用
 */
export class WsSendError extends Error {
  public readonly reasonCode: ReasonCode;
  public readonly i18nKey: string;
  public readonly defaultMessage: string;

  constructor(reasonCode: ReasonCode) {
    const info = REASON_CODE_I18N[reasonCode] || { 
      key: 'ws.error.unknown', 
      defaultMessage: `发送消息失败 (错误码: ${reasonCode})` 
    };
    super(info.defaultMessage);
    this.name = 'WsSendError';
    this.reasonCode = reasonCode;
    this.i18nKey = info.key;
    this.defaultMessage = info.defaultMessage;
  }
}

export type MessageHandler = (message: Message) => void;
export type ConnectionStatusHandler = (status: ConnectionStatus) => void;
export type ErrorHandler = (error: any) => void;
export type StreamMessageHandler = (clientMsgNo: string, content: string) => void;
export type StreamEndHandler = (clientMsgNo: string, error?: string) => void;
export type StreamFinishHandler = (clientMsgNo: string) => void;
export type JSONRenderMessageHandler = (clientMsgNo: string, payload: { patches: Record<string, unknown>[] }) => void;
export type VisitorPresenceEvent = { visitorId?: string; channelId: string; channelType: number; isOnline: boolean; timestamp?: string | null; eventType: string; raw?: any };
export type VisitorPresenceHandler = (presence: VisitorPresenceEvent) => void;

export type VisitorProfileUpdatedEvent = { visitorId?: string; channelId: string; channelType: number; raw?: any };
export type VisitorProfileUpdatedHandler = (evt: VisitorProfileUpdatedEvent) => void;

export type QueueUpdatedEvent = { raw?: any };
export type QueueUpdatedHandler = (evt: QueueUpdatedEvent) => void;

type CommandMessage = {
  cmd: string;
  param?: Record<string, unknown>;
  channelId: string;
  channelType: number;
};

const VISITOR_ONLINE_EVENT_TYPE = 'visitor.online';
const VISITOR_OFFLINE_EVENT_TYPE = 'visitor.offline';

/**
 * WuKongIM WebSocket Service Manager
 * Handles real-time messaging through WuKongIM EasySDK-JS
 */
export class WuKongIMWebSocketService {
  private im?: WKIM = undefined;
  private connectionStatus: ConnectionStatus = {
    isConnected: false,
    isConnecting: false,
  };

  // Event handlers
  private messageHandlers: MessageHandler[] = [];
  private connectionStatusHandlers: ConnectionStatusHandler[] = [];
  private errorHandlers: ErrorHandler[] = [];
  private visitorProfileUpdatedHandlers: VisitorProfileUpdatedHandler[] = [];
  private queueUpdatedHandlers: QueueUpdatedHandler[] = [];

  private streamMessageHandlers: StreamMessageHandler[] = [];
  private streamEndHandlers: StreamEndHandler[] = [];
  private streamFinishHandlers: StreamFinishHandler[] = [];
  private jsonRenderMessageHandlers: JSONRenderMessageHandler[] = [];
  private visitorPresenceHandlers: VisitorPresenceHandler[] = [];

  // Reconnection timer (for cleanup)
  private reconnectTimer: number | null = null;

  // Prevent multiple simultaneous connection attempts
  private connectionPromise: Promise<void> | null = null;
  private isInitialized = false;

  // Track manual disconnection to prevent unnecessary reconnections
  private manualDisconnect = false;

  private tryExtractCommandMessage(message: unknown): CommandMessage | null {
    if (!message || typeof message !== 'object') return null;

    const raw = message as Record<string, unknown>;
    const rawPayload = raw.payload;
    const payloadRecord =
      rawPayload && typeof rawPayload === 'object'
        ? (rawPayload as Record<string, unknown>)
        : typeof rawPayload === 'string'
          ? (WuKongIMUtils.tryParsePayloadString(rawPayload) as Record<string, unknown> | null)
          : null;
    if (!payloadRecord) return null;

    if (payloadRecord.type !== MessagePayloadType.COMMAND) return null;
    if (typeof payloadRecord.cmd !== 'string' || !payloadRecord.cmd) return null;

    const channelId =
      typeof raw.channelId === 'string'
        ? raw.channelId
        : typeof raw.channel_id === 'string'
          ? raw.channel_id
          : '';
    const channelTypeValue =
      typeof raw.channelType === 'number'
        ? raw.channelType
        : typeof raw.channel_type === 'number'
          ? raw.channel_type
          : NaN;

    if (!channelId || !Number.isFinite(channelTypeValue)) {
      return null;
    }

    const param =
      payloadRecord.param && typeof payloadRecord.param === 'object'
        ? (payloadRecord.param as Record<string, unknown>)
        : undefined;

    return {
      cmd: payloadRecord.cmd,
      param,
      channelId,
      channelType: channelTypeValue,
    };
  }

  private handleCommandMessage(message: unknown): boolean {
    const command = this.tryExtractCommandMessage(message);
    if (!command) return false;

    const eventType = command.cmd;
    const rawData = command.param;

    if (
      eventType === VISITOR_ONLINE_EVENT_TYPE
      || eventType === VISITOR_OFFLINE_EVENT_TYPE
    ) {
      const presenceChannelId =
        typeof rawData?.channel_id === 'string'
          ? rawData.channel_id
          : typeof rawData?.channelId === 'string'
            ? rawData.channelId
            : command.channelId;
      const presenceChannelType =
        typeof rawData?.channel_type === 'number'
          ? rawData.channel_type
          : typeof rawData?.channelType === 'number'
            ? rawData.channelType
            : command.channelType;
      const visitorId =
        typeof rawData?.visitor_id === 'string'
          ? rawData.visitor_id
          : typeof rawData?.visitorId === 'string'
            ? rawData.visitorId
            : undefined;
      const timestamp =
        typeof rawData?.timestamp === 'string'
          ? rawData.timestamp
          : null;
      const isOnline =
        eventType === VISITOR_ONLINE_EVENT_TYPE
          ? true
          : eventType === VISITOR_OFFLINE_EVENT_TYPE
            ? false
            : Boolean(rawData?.is_online);

      this.notifyVisitorPresenceHandlers({
        visitorId,
        channelId: presenceChannelId,
        channelType: presenceChannelType,
        isOnline,
        timestamp,
        eventType,
        raw: rawData,
      });
      return true;
    }

    if (eventType === WS_EVENT_TYPE.QUEUE_UPDATED) {
      this.notifyQueueUpdatedHandlers({ raw: rawData });
      return true;
    }

    if (eventType !== WS_EVENT_TYPE.VISITOR_PROFILE_UPDATED) {
      console.warn('🔌 Unsupported WuKongIM command message ignored:', {
        cmd: eventType,
        channelId: command.channelId,
        channelType: command.channelType,
      });
      return true;
    }

    const visitorId =
      typeof rawData?.visitor_id === 'string'
        ? rawData.visitor_id
        : typeof rawData?.visitorId === 'string'
          ? rawData.visitorId
          : undefined;

    this.notifyVisitorProfileUpdatedHandlers({
      visitorId,
      channelId: command.channelId,
      channelType: command.channelType,
      raw: rawData,
    });
    return true;
  }


  /**
   * Initialize the WebSocket connection
   */
  async init(config: WuKongIMWebSocketConfig): Promise<void> {
    // Prevent multiple simultaneous connection attempts
    if (this.connectionPromise) {
      console.log('🔌 Connection attempt already in progress, waiting...');
      return this.connectionPromise;
    }

    // If already connected with same config, skip
    if (this.isInitialized && this.connectionStatus.isConnected) {
      console.log('🔌 Already connected, skipping initialization');
      return;
    }

    this.connectionPromise = this.performConnection(config);

    try {
      await this.connectionPromise;
    } finally {
      this.connectionPromise = null;
    }
  }

  /**
   * Perform actual connection logic
   */
  private async performConnection(config: WuKongIMWebSocketConfig): Promise<void> {
    try {
      console.log('🔌 Starting WebSocket connection...', { uid: config.uid, serverUrl: config.serverUrl });

      // Clean up any existing connection first
      if (this.im) {
        console.log('🔌 Cleaning up existing connection...');
        this.cleanupConnection();
      }

      this.updateConnectionStatus({ isConnecting: true, isConnected: false });
      this.manualDisconnect = false;

      // Initialize WKIM instance with connection timeout
      this.im = WKIM.init(config.serverUrl, {
        uid: config.uid,
        token: config.token
      },{});

      // Setup event listeners
      this.setupEventListeners();

      // Attempt connection with timeout
      const connectionTimeout = new Promise((_, reject) => {
        setTimeout(() => reject(new Error('Connection timeout')), 10000);
      });

      await Promise.race([
        this.im.connect(),
        connectionTimeout
      ]);

      this.isInitialized = true;
      console.log('🔌 WebSocket connection established successfully');

    } catch (error) {
      console.error('🔌 WebSocket initialization failed:', error);
      this.cleanupConnection();
      this.updateConnectionStatus({
        isConnected: false,
        isConnecting: false,
        error: error instanceof Error ? error.message : 'Connection failed',
      });
      this.notifyErrorHandlers(error);
      throw error;
    }
  }

  /**
   * Disconnect from WebSocket
   */
  disconnect(): void {
    console.log('🔌 Manual disconnect requested');
    this.manualDisconnect = true;
    this.cleanupConnection();
  }

  /**
   * Clean up connection resources
   */
  private cleanupConnection(): void {
    console.log('🔌 Cleaning up connection:', {
      hasIM: !!this.im,
      isConnected: this.connectionStatus.isConnected,
      isInitialized: this.isInitialized
    });

    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    if (this.im) {
      try {
        // Clear event listeners first to prevent any callbacks during disconnect
        this.clearEventListeners();

        // Try to disconnect gracefully, but catch any WebSocket close code errors
        this.im.disconnect();
      } catch (error) {
        // Ignore WebSocket close code errors from the SDK
        if (error instanceof Error && error.message.includes('close code')) {
          console.warn('🔌 WebSocket close code error ignored:', error.message);
        } else {
          console.error('🔌 Error during WebSocket disconnect:', error);
        }
      }
      this.im = undefined;
    }

    this.isInitialized = false;
    // Always update connection status when cleaning up
    this.updateConnectionStatus({ isConnected: false, isConnecting: false });

    console.log('🔌 Connection cleanup completed');
  }

  /**
   * Safe disconnect that avoids SDK close code issues
   */
  safeDisconnect(): void {
    console.log('🔌 Safe disconnect requested:', {
      hasIM: !!this.im,
      isConnected: this.connectionStatus.isConnected,
      isInitialized: this.isInitialized
    });

    this.manualDisconnect = true;

    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    // Clear connection promise to prevent pending connections
    this.connectionPromise = null;

    // Just clear the instance without calling disconnect to avoid close code errors
    if (this.im) {
      // Clear event listeners to prevent any remaining callbacks
      this.clearEventListeners();
      this.im = undefined;
    }

    this.isInitialized = false;
    this.updateConnectionStatus({ isConnected: false, isConnecting: false });

    console.log('🔌 Safe disconnect completed');
  }

  /**
   * Send a message through WebSocket
   * @param channelId Target channel ID
   * @param channelType Target channel type
   * @param payload Message payload
   * @param clientMsgNo Client message number for deduplication (required to match local message)
   * @returns Promise with send result containing messageId, messageSeq, and reasonCode
   * @throws Error if reasonCode is not Success or if connection fails
   */
  async sendMessage(
    channelId: string,
    channelType: number,
    payload: any,
    clientMsgNo: string
  ): Promise<WsSendResult> {
    console.log('🔌 WebSocket sendMessage called:', {
      hasIM: !!this.im,
      isConnected: this.connectionStatus.isConnected,
      isInitialized: this.isInitialized,
      channelId,
      channelType,
      clientMsgNo
    });

    // ENHANCED STATE CONSISTENCY CHECK
    // Check for state inconsistency: connection shows as connected but no IM instance
    if (this.connectionStatus.isConnected && !this.im) {
      console.error('🔌 CRITICAL STATE INCONSISTENCY: isConnected=true but im=null, fixing...');
      this.updateConnectionStatus({ isConnected: false, isConnecting: false });
      this.isInitialized = false;
      throw new Error('WebSocket state inconsistency detected - connection status reset');
    }

    // Check IM instance first
    if (!this.im) {
      // Update connection status to reflect reality
      this.updateConnectionStatus({ isConnected: false, isConnecting: false });
      throw new Error('WebSocket not initialized');
    }

    // Check connection status
    if (!this.connectionStatus.isConnected) {
      throw new Error('WebSocket not connected');
    }

    // Additional check: verify the IM instance is actually connected
    try {
      // Test if the connection is actually alive by checking IM state
      if (this.im.isConnected && typeof this.im.isConnected === 'function') {
        if (!this.im.isConnected) {
          console.log('🔌 IM instance reports not connected, updating status');
          this.updateConnectionStatus({ isConnected: false, isConnecting: false });
          this.im = undefined; // Clear broken instance
          this.isInitialized = false;
          throw new Error('WebSocket connection lost');
        }
      }
    } catch (stateCheckError) {
      // If we can't check state, log but continue with send attempt
      console.warn('🔌 WebSocket state check failed:', stateCheckError);
    }

    try {
      // Convert channel type to WuKongIM format
      const wkimChannelType = this.convertChannelType(channelType);

      console.log('🔌 Sending WebSocket message:', {
        channelId,
        channelType,
        wkimChannelType,
        clientMsgNo,
        payloadType: typeof payload,
        payload,
      });

      // Send message with clientMsgNo in options to ensure server uses the same ID
      const result = await this.im!.send(channelId, wkimChannelType, payload, { clientMsgNo });
      
      // Check reasonCode - Success = 1, other values indicate errors
      if (result.reasonCode !== ReasonCode.Success) {
        console.error('🔌 WebSocket send failed with reasonCode:', {
          reasonCode: result.reasonCode,
          messageId: result.messageId,
          messageSeq: result.messageSeq
        });
        throw new WsSendError(result.reasonCode as ReasonCode);
      }

      console.log('🔌 WebSocket message sent successfully:', {
        messageId: result.messageId,
        messageSeq: result.messageSeq,
        reasonCode: result.reasonCode
      });
      
      return result as WsSendResult;
    } catch (error) {
      console.error('🔌 WebSocket send failed:', error);

      // Update connection status if this was a connection error
      if (error instanceof Error) {
        const errorMsg = error.message.toLowerCase();
        if (errorMsg.includes('connect') || errorMsg.includes('websocket') || errorMsg.includes('closed')) {
          console.log('🔌 Send error indicates connection issue, updating status');
          this.updateConnectionStatus({ isConnected: false, isConnecting: false });
        }
      }

      this.notifyErrorHandlers(error);
      throw error;
    }
  }

  /**
   * Get current connection status
   */
  getConnectionStatus(): ConnectionStatus {
    return { ...this.connectionStatus };
  }

  /**
   * Get comprehensive service state for debugging
   */
  getServiceState(): any {
    return {
      hasIM: !!this.im,
      isConnected: this.connectionStatus.isConnected,
      isConnecting: this.connectionStatus.isConnecting,
      isInitialized: this.isInitialized,
      manualDisconnect: this.manualDisconnect,
      hasReconnectTimer: !!this.reconnectTimer,
      hasConnectionPromise: !!this.connectionPromise,
      error: this.connectionStatus.error
    };
  }

  /**
   * Force a clean reconnection - useful when state inconsistency is detected
   */
  async forceReconnect(config: WuKongIMWebSocketConfig): Promise<void> {
    console.log('🔌 Force reconnect requested:', this.getServiceState());

    // Clean up current connection completely
    this.cleanupConnection();

    // Wait a bit to ensure cleanup is complete
    await new Promise(resolve => setTimeout(resolve, 100));

    // Initialize fresh connection
    return this.init(config);
  }

  /**
   * Add message handler
   */
  onMessage(handler: MessageHandler): () => void {
    this.messageHandlers.push(handler);
    return () => {
      const index = this.messageHandlers.indexOf(handler);
      if (index > -1) {
        this.messageHandlers.splice(index, 1);
      }
    };
  }

  /**
   * Add connection status handler
   */
  onConnectionStatus(handler: ConnectionStatusHandler): () => void {
    this.connectionStatusHandlers.push(handler);
    return () => {
      const index = this.connectionStatusHandlers.indexOf(handler);
      if (index > -1) {
        this.connectionStatusHandlers.splice(index, 1);
      }
    };
  }

  /**
   * Add error handler
   */
  onError(handler: ErrorHandler): () => void {
    this.errorHandlers.push(handler);
    return () => {
      const index = this.errorHandlers.indexOf(handler);
      if (index > -1) {
        this.errorHandlers.splice(index, 1);
      }
    };
  }

  // Track event handlers for proper cleanup
  private eventHandlers: {
    connect?: (result: any) => void;
    disconnect?: (reason: any) => void;
    message?: (message: any) => void;
    error?: (error: any) => void;
    customEvent?: (event: any) => void;
  } = {};

  /**
   * Clear WebSocket event listeners to prevent duplicate handlers
   */
  private clearEventListeners(): void {
    if (!this.im) return;

    try {
      // Remove specific event listeners using stored references
      if (this.eventHandlers.connect) {
        this.im.off(WKIMEvent.Connect, this.eventHandlers.connect);
      }
      if (this.eventHandlers.disconnect) {
        this.im.off(WKIMEvent.Disconnect, this.eventHandlers.disconnect);
      }
      if (this.eventHandlers.message) {
        this.im.off(WKIMEvent.Message, this.eventHandlers.message);
      }
      if (this.eventHandlers.error) {
        this.im.off(WKIMEvent.Error, this.eventHandlers.error);
      }
      if (this.eventHandlers.customEvent) {
        this.im.off(WKIMEvent.CustomEvent, this.eventHandlers.customEvent);
      }

      // Clear handler references
      this.eventHandlers = {};
      console.log('🔌 Cleared all WebSocket event listeners (including CustomEvent)');
    } catch (error) {
      // Some versions of the SDK might not support off() method properly
      console.warn('🔌 Could not clear event listeners:', error);
      // Reset handler references anyway
      this.eventHandlers = {};
    }
  }

  /**
   * Setup WebSocket event listeners
   */
  private setupEventListeners(): void {
    if (!this.im) return;

    // CRITICAL: Clear existing listeners first to prevent duplicate message handling
    this.clearEventListeners();

    console.log('🔌 Setting up fresh WebSocket event listeners');

    // Connection established
    this.eventHandlers.connect = (result: any) => {
      console.log('🔌 WuKongIM WebSocket connected:', result);
      this.updateConnectionStatus({ isConnected: true, isConnecting: false, error: undefined });
      console.log('🔌 Service state:', this.getServiceState());
    };
    this.im.on(WKIMEvent.Connect, this.eventHandlers.connect);

    // Connection lost
    this.eventHandlers.disconnect = (reason: any) => {
      console.log('🔌 WuKongIM WebSocket disconnected:', reason, {
        manualDisconnect: this.manualDisconnect,
        hasIM: !!this.im,
        wasConnected: this.connectionStatus.isConnected
      });

      // CRITICAL: Clear the IM instance when disconnected to maintain state consistency
      // This prevents the state where isConnected=true but this.im is in broken state
      if (!this.manualDisconnect) {
        console.log('🔌 Clearing IM instance due to disconnect');
        this.im = undefined;
        this.isInitialized = false;
      }

      // Only update status if not manually disconnected
      if (!this.manualDisconnect) {
        this.updateConnectionStatus({ isConnected: false, isConnecting: false });

        // Only attempt to reconnect for certain disconnect reasons
        // Avoid reconnecting on normal closures (code 1000) or client-initiated closures
        if (this.shouldAttemptReconnect(reason)) {
          console.log('🔌 Will attempt to reconnect in 1s (Attempt 1)');
          this.scheduleReconnect();
        }
      } else {
        console.log('🔌 Manual disconnect, not attempting reconnection');
        this.updateConnectionStatus({ isConnected: false, isConnecting: false });
      }
    };
    this.im.on(WKIMEvent.Disconnect, this.eventHandlers.disconnect);

    // Message received - Single handler only
    this.eventHandlers.message = (message: any) => {
      console.log('🔌 WuKongIM message received (single handler):', {
        messageId: message?.messageId || message?.id,
        content: typeof message?.content === 'string' ? `${message.content.substring(0, 50)}...` : message?.content,
        channelId: message?.channelId,
      });
      try {
        if (this.handleCommandMessage(message)) {
          return;
        }

        // Convert WuKongIM message to internal format
        const convertedMessage = this.convertWuKongIMMessage(message);
        this.notifyMessageHandlers(convertedMessage);
      } catch (error) {
        console.error('Failed to convert received message:', error);
        this.notifyErrorHandlers(error);
      }
    };
    this.im.on(WKIMEvent.Message, this.eventHandlers.message);

    // Error occurred
    this.eventHandlers.error = (error: any) => {
      console.error('🔌 WuKongIM WebSocket error:', error);

      // Don't immediately update status on error if we're manually disconnecting
      if (!this.manualDisconnect) {
        this.updateConnectionStatus({
          isConnected: false,
          isConnecting: false,
          error: error.message || 'WebSocket error',
        });
      }

      this.notifyErrorHandlers(error);
    };
    this.im.on(WKIMEvent.Error, this.eventHandlers.error);

    // Custom event - AI stream message handling and visitor presence
    // Supports both legacy event format (event.type/event.data) and new Stream API v2 format (event_type/payload)
    this.eventHandlers.customEvent = (event: any) => {
      console.log('🔌 WuKongIM CustomEvent received:', {
        id: event?.id,
        type: event?.type,
        timestamp: event?.timestamp,
        dataPreview: typeof event?.data === 'string' ? `${event.data.substring(0, 50)}...` : event?.data,
      });

      try {
        // --- New Stream API v2 event format ---
        // Check if this is a new-format event by looking for event_type in the event data
        const eventData = (() => {
          if (event?.dataJson && typeof event.dataJson === 'object') return event.dataJson;
          if (typeof event?.data === 'string') {
            try { return JSON.parse(event.data); } catch { return null; }
          }
          if (event?.data && typeof event.data === 'object') return event.data;
          return null;
        })();

        // event_type may be inside the data payload or at the top-level event.type
        const newEventType = eventData?.event_type || event?.type;
        const clientMsgNo = eventData?.client_msg_no || event?.id;

        if (newEventType === WS_EVENT_TYPE.STREAM_DELTA) {
          const payload = eventData.payload;
          const delta = payload?.delta;
          if (delta) {
            // All deltas (text, mixed content with spec fences) go through
            // the unified stream handler. MixedStreamParser on the consumer
            // side will split text vs JSONL patches automatically.
            this.notifyStreamMessageHandlers(clientMsgNo, delta);
          }
          return;
        }

        if (newEventType === WS_EVENT_TYPE.STREAM_CLOSE) {
          const errorMessage = eventData.payload?.end_reason > 0 ? '流异常结束' : undefined;
          this.notifyStreamEndHandlers(clientMsgNo, errorMessage);
          return;
        }

        if (newEventType === WS_EVENT_TYPE.STREAM_ERROR) {
          this.notifyStreamEndHandlers(clientMsgNo, eventData.payload?.error || '未知错误');
          return;
        }

        if (newEventType === WS_EVENT_TYPE.STREAM_CANCEL) {
          this.notifyStreamEndHandlers(clientMsgNo);
          return;
        }

        if (newEventType === WS_EVENT_TYPE.STREAM_FINISH) {
          this.notifyStreamFinishHandlers(clientMsgNo);
          return;
        }

        // --- Legacy event format (backward compatibility) ---
        if (event.type === '___TextMessageContent') {
          // AI streaming content (legacy)
          this.notifyStreamMessageHandlers(event.id, event.data);
        } else if (event.type === 'visitor.online' || event.type === 'visitor.offline') {
          // Visitor presence updates
          let payload: any = null;
          try {
            payload = typeof event.data === 'string' ? JSON.parse(event.data) : event.data;
          } catch (e) {
            console.warn('🔌 Failed to parse presence event data:', e);
          }
          const visitorId: string | undefined = payload?.visitor_id || payload?.visitorId || payload?.id;
          const channelId: string | undefined = payload?.channel_id || payload?.channelId || visitorId;
          const channelType: number = typeof payload?.channel_type === 'number' ? payload.channel_type : CHANNEL_TYPE.PERSON;
          const isOnline: boolean = event.type === 'visitor.online' ? true : event.type === 'visitor.offline' ? false : Boolean(payload?.is_online);
          const ts: string | undefined = typeof payload?.timestamp === 'string' ? payload.timestamp : undefined;

          if (!channelId) {
            console.warn('🔌 Presence event missing channel_id (and visitor_id), ignoring');
          } else {
            this.notifyVisitorPresenceHandlers({ visitorId, channelId, channelType, isOnline, timestamp: ts, eventType: event.type, raw: payload });
          }
        } else if (event.type === WS_EVENT_TYPE.VISITOR_PROFILE_UPDATED) {
          // Visitor profile updated -> refresh specific channel info
          let payload: any = null;
          try {
            payload = typeof event.data === 'string' ? JSON.parse(event.data) : event.data;
          } catch (e) {
            console.warn('🔌 Failed to parse visitor.profile.updated data:', e);
          }
          const visitorId: string | undefined = payload?.visitor_id || payload?.visitorId || payload?.id;
          const channelId: string | undefined = payload?.channel_id || payload?.channelId;
          const channelType: number | undefined = typeof payload?.channel_type === 'number' ? payload.channel_type : undefined;

          if (!channelId || typeof channelType !== 'number' || !Number.isFinite(channelType)) {
            console.warn('🔌 visitor.profile.updated missing channel_id or channel_type, ignoring');
          } else {
            this.notifyVisitorProfileUpdatedHandlers({ visitorId, channelId, channelType, raw: payload });
          }
        } else if (event.type === WS_EVENT_TYPE.QUEUE_UPDATED) {
          // Queue updated -> notify handlers to refresh unassigned count
          let payload: any = null;
          try {
            payload = typeof event.data === 'string' ? JSON.parse(event.data) : event.data;
          } catch (e) {
            console.warn('🔌 Failed to parse queue.updated data:', e);
          }
          console.log('🔌 Queue updated event received:', payload);
          this.notifyQueueUpdatedHandlers({ raw: payload });
        } else if (event.type === '___JSONRenderMessage') {
          // json-render patch message from the AI agent (legacy)
          try {
            const jsonRenderPayload = typeof event.data === 'string' ? JSON.parse(event.data) : event.data;
            this.notifyJSONRenderMessageHandlers(event.id, jsonRenderPayload);
          } catch (e) {
            console.warn('🔌 Failed to parse json-render message data:', e);
          }
        } else if (event.type === WS_EVENT_TYPE.TEXT_MESSAGE_END) {
          // AI streaming content ended (legacy)
          const errorMessage = event.data && typeof event.data === 'string' && event.data.trim() !== ''
            ? event.data.trim()
            : undefined;
          console.log('🔌 Stream message ended:', { clientMsgNo: event.id, error: errorMessage });
          this.notifyStreamEndHandlers(event.id, errorMessage);
        } else {
          console.log('🔌 CustomEvent type not handled:', event.type);
        }
      } catch (error) {
        console.error('🔌 Failed to handle CustomEvent:', error);
        this.notifyErrorHandlers(error);
      }
    };
    this.im.on(WKIMEvent.CustomEvent, this.eventHandlers.customEvent);

    console.log('🔌 WebSocket event listeners setup completed (including CustomEvent)');
  }

  /**
   * Convert channel type to WuKongIM format
   */
  private convertChannelType(channelType: number): any {
    // Map internal channel types to WuKongIM channel types
    switch (channelType) {
      case CHANNEL_TYPE.PERSON: // Person
        return WKIMChannelType.Person;
      case CHANNEL_TYPE.GROUP: // Group
        return WKIMChannelType.Group;
      default:
        return channelType;
    }
  }

  /**
   * Convert WuKongIM message to internal Message format
   */
  private convertWuKongIMMessage(wkimMessage: WuKongIMMessage): Message {
    return WuKongIMUtils.convertToMessage(wkimMessage);
  }

  /**
   * Determine if we should attempt to reconnect based on disconnect reason
   */
  private shouldAttemptReconnect(reason: any): boolean {
    // Don't reconnect if manually disconnected
    if (this.manualDisconnect) {
      return false;
    }

    // Get the close code from the reason
    const code = reason?.code || reason;

    // Don't reconnect for normal closures (1000) or client-initiated closures (1001)
    if (code === 1000 || code === 1001) {
      console.log('🔌 Normal closure, not reconnecting', { code });
      return false;
    }

    // Don't reconnect for authentication errors (typically 1002-1015)
    if (code >= 1002 && code <= 1015) {
      console.log('🔌 Authentication/protocol error, not reconnecting', { code });
      return false;
    }

    // Reconnect for abnormal closures (1006) and other unexpected disconnections
    console.log('🔌 Unexpected disconnection, will reconnect', { code, reason });
    return true;
  }

  /**
   * Schedule a reconnection attempt with exponential backoff
   */
  private scheduleReconnect(): void {
    if (this.reconnectTimer || this.manualDisconnect) {
      return;
    }

    // Simple 1-second delay for now (could be enhanced with exponential backoff)
    this.reconnectTimer = window.setTimeout(() => {
      this.reconnectTimer = null;

      if (!this.manualDisconnect && !this.connectionStatus.isConnected) {
        console.log('🔌 Attempting automatic reconnection...');
        // Note: We don't have the original config here, so reconnection
        // should be handled by the hook's auto-connect logic
        this.updateConnectionStatus({ isConnecting: false, isConnected: false });
      }
    }, 1000);
  }

  /**
   * Update connection status and notify handlers
   */
  private updateConnectionStatus(status: Partial<ConnectionStatus>): void {
    this.connectionStatus = { ...this.connectionStatus, ...status };
    this.notifyConnectionStatusHandlers(this.connectionStatus);
  }

  /**
   * Notify all message handlers
   */
  private notifyMessageHandlers(message: Message): void {
    this.messageHandlers.forEach(handler => {
      try {
        handler(message);
      } catch (error) {
        console.error('Message handler error:', error);
      }
    });
  }

  /**
   * Notify all connection status handlers
   */
  private notifyConnectionStatusHandlers(status: ConnectionStatus): void {
    this.connectionStatusHandlers.forEach(handler => {
      try {
        handler(status);
      } catch (error) {
        console.error('Connection status handler error:', error);
      }
    });
  }

  /**
   * Notify all error handlers
   */
  private notifyErrorHandlers(error: any): void {
    this.errorHandlers.forEach(handler => {
      try {
        handler(error);
      } catch (error) {
        console.error('Error handler error:', error);
      }
    });
  }

  /**
   * Notify all stream message handlers
   */
  private notifyStreamMessageHandlers(clientMsgNo: string, content: string): void {
    console.log('🔌 Notifying stream message handlers:', {
      clientMsgNo,
      handlerCount: this.streamMessageHandlers.length,
      contentLength: content?.length
    });

    this.streamMessageHandlers.forEach(handler => {
      try {
        handler(clientMsgNo, content);
      } catch (error) {
        console.error('Stream message handler error:', error);
      }
    });

    // Broadcast a DOM event so UI components can react (e.g., keep scroll position)
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('chat:stream-update', {
        detail: {
          clientMsgNo,
          contentLength: content?.length ?? 0
        }
      }));
    }
  }

  /**
   * Notify all stream end handlers
   * @param clientMsgNo - The client message number
   * @param error - Optional error message from the stream end event
   */
  private notifyStreamEndHandlers(clientMsgNo: string, error?: string): void {
    console.log('🔌 Notifying stream end handlers:', {
      clientMsgNo,
      error,
      handlerCount: this.streamEndHandlers.length
    });

    this.streamEndHandlers.forEach(handler => {
      try {
        handler(clientMsgNo, error);
      } catch (err) {
        console.error('Stream end handler error:', err);
      }
    });

    // Broadcast a DOM event so UI components can react
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('chat:stream-end', {
        detail: { clientMsgNo, error }
      }));
    }
  }

  private notifyStreamFinishHandlers(clientMsgNo: string): void {
    console.log('🔌 Notifying stream finish handlers:', {
      clientMsgNo,
      handlerCount: this.streamFinishHandlers.length
    });

    this.streamFinishHandlers.forEach(handler => {
      try {
        handler(clientMsgNo);
      } catch (err) {
        console.error('Stream finish handler error:', err);
      }
    });
  }

  /**
   * Notify all json-render message handlers.
   */
  private notifyJSONRenderMessageHandlers(clientMsgNo: string, payload: { patches: Record<string, unknown>[] }): void {
    this.jsonRenderMessageHandlers.forEach(handler => {
      try {
        handler(clientMsgNo, payload);
      } catch (err) {
        console.error('json-render message handler error:', err);
      }
    });
  }

  /**
   * Notify all visitor profile updated handlers
   */
  private notifyVisitorProfileUpdatedHandlers(event: VisitorProfileUpdatedEvent): void {
    console.log('🔌 Notifying visitor profile updated handlers:', {
      channelId: event.channelId,
      channelType: event.channelType,
      visitorId: event.visitorId,
      handlerCount: this.visitorProfileUpdatedHandlers.length
    });

    this.visitorProfileUpdatedHandlers.forEach(handler => {
      try {
        handler(event);
      } catch (error) {
        console.error('Visitor profile updated handler error:', error);
      }
    });
  }

  /**
   * Notify all visitor presence handlers
   */
  private notifyVisitorPresenceHandlers(event: VisitorPresenceEvent): void {
    console.log('\ud83d\udd0c Notifying visitor presence handlers:', {
      channelId: event.channelId,
      channelType: event.channelType,
      visitorId: event.visitorId,
      isOnline: event.isOnline,
      timestamp: event.timestamp,
      type: event.eventType,
      handlerCount: this.visitorPresenceHandlers.length
    });

    this.visitorPresenceHandlers.forEach(handler => {
      try {
        handler(event);
      } catch (error) {
        console.error('Visitor presence handler error:', error);
      }
    });
  }

  /**
   * Subscribe to visitor profile updated events
   */
  onVisitorProfileUpdated(handler: VisitorProfileUpdatedHandler): () => void {
    this.visitorProfileUpdatedHandlers.push(handler);
    console.log('🔌 Visitor profile updated handler registered, total:', this.visitorProfileUpdatedHandlers.length);
    return () => {
      const index = this.visitorProfileUpdatedHandlers.indexOf(handler);
      if (index > -1) {
        this.visitorProfileUpdatedHandlers.splice(index, 1);
        console.log('🔌 Visitor profile updated handler unregistered, remaining:', this.visitorProfileUpdatedHandlers.length);
      }
    };
  }

  /**
   * Notify queue updated handlers
   */
  private notifyQueueUpdatedHandlers(event: QueueUpdatedEvent): void {
    console.log('🔌 Notifying queue updated handlers:', {
      handlerCount: this.queueUpdatedHandlers.length
    });

    this.queueUpdatedHandlers.forEach(handler => {
      try {
        handler(event);
      } catch (error) {
        console.error('Queue updated handler error:', error);
      }
    });
  }

  /**
   * Subscribe to queue updated events
   */
  onQueueUpdated(handler: QueueUpdatedHandler): () => void {
    this.queueUpdatedHandlers.push(handler);
    console.log('🔌 Queue updated handler registered, total:', this.queueUpdatedHandlers.length);
    return () => {
      const index = this.queueUpdatedHandlers.indexOf(handler);
      if (index > -1) {
        this.queueUpdatedHandlers.splice(index, 1);
        console.log('🔌 Queue updated handler unregistered, remaining:', this.queueUpdatedHandlers.length);
      }
    };
  }

  /**
   * Subscribe to stream messages (AI incremental updates)
   */
  onStreamMessage(handler: StreamMessageHandler): () => void {
    this.streamMessageHandlers.push(handler);
    console.log('🔌 Stream message handler registered, total:', this.streamMessageHandlers.length);

    return () => {
      const index = this.streamMessageHandlers.indexOf(handler);
      if (index > -1) {
        this.streamMessageHandlers.splice(index, 1);
        console.log('🔌 Stream message handler unregistered, remaining:', this.streamMessageHandlers.length);
      }
    };
  }

  /**
   * Subscribe to stream end events (AI streaming finished)
   */
  onStreamEnd(handler: StreamEndHandler): () => void {
    this.streamEndHandlers.push(handler);
    console.log('🔌 Stream end handler registered, total:', this.streamEndHandlers.length);

    return () => {
      const index = this.streamEndHandlers.indexOf(handler);
      if (index > -1) {
        this.streamEndHandlers.splice(index, 1);
        console.log('🔌 Stream end handler unregistered, remaining:', this.streamEndHandlers.length);
      }
    };
  }

  /**
   * Subscribe to stream finish events (entire stream message completed)
   */
  onStreamFinish(handler: StreamFinishHandler): () => void {
    this.streamFinishHandlers.push(handler);
    console.log('🔌 Stream finish handler registered, total:', this.streamFinishHandlers.length);
    return () => {
      const index = this.streamFinishHandlers.indexOf(handler);
      if (index > -1) {
        this.streamFinishHandlers.splice(index, 1);
        console.log('🔌 Stream finish handler unregistered, remaining:', this.streamFinishHandlers.length);
      }
    };
  }

  /**
   * Subscribe to json-render patch message events.
   */
  onJSONRenderMessage(handler: JSONRenderMessageHandler): () => void {
    this.jsonRenderMessageHandlers.push(handler);
    return () => {
      const index = this.jsonRenderMessageHandlers.indexOf(handler);
      if (index > -1) this.jsonRenderMessageHandlers.splice(index, 1);
    };
  }

  /**
   * Subscribe to visitor presence events (visitor.online / visitor.offline)
   */
  onVisitorPresence(handler: VisitorPresenceHandler): () => void {
    this.visitorPresenceHandlers.push(handler);
    console.log('🔌 Visitor presence handler registered, total:', this.visitorPresenceHandlers.length);
    return () => {
      const index = this.visitorPresenceHandlers.indexOf(handler);
      if (index > -1) {
        this.visitorPresenceHandlers.splice(index, 1);
        console.log('🔌 Visitor presence handler unregistered, remaining:', this.visitorPresenceHandlers.length);
      }
    };
  }
}

// Singleton instance
export const wukongimWebSocketService = new WuKongIMWebSocketService();
