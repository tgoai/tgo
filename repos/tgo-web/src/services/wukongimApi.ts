/**
 * WuKongIM API Service
 * Handles WuKongIM conversation synchronization and messaging API endpoints
 */

import { BaseApiService } from './base/BaseApiService';

import { CHANNEL_TYPE, DEFAULT_CHANNEL_TYPE, MESSAGE_SENDER_TYPE, PlatformType, STAFF_UID_SUFFIX } from '@/constants';

import { useAuthStore } from '@/stores';
import { toAbsoluteApiUrl } from '@/utils/url';
import type {
  WuKongIMConversationSyncRequest,
  WuKongIMConversationSyncResponse,
  WuKongIMMessagePayload,
  WuKongIMMessageSyncRequest,
  WuKongIMMessageSyncResponse,
  WuKongIMEnhancedMessage,
  WuKongIMMessage,
  MessageSenderType,
  Message,
  MessagePayload,
  PayloadRichTextImage,
  PayloadSystem,
} from '../types';
import { MessagePayloadType, isSystemMessageType } from '../types';


/**
 * WuKongIM API Service Class
 */
export class WuKongIMApiService extends BaseApiService {
  protected readonly apiVersion = 'v1';
  protected readonly endpoints = {
    ROUTE: `/${this.apiVersion}/wukongim/route`,
    CONVERSATIONS_SYNC: `/${this.apiVersion}/conversations/all`,
    CONVERSATIONS_DELETE: `/${this.apiVersion}/conversations`,
    CONVERSATIONS_SET_UNREAD: `/${this.apiVersion}/conversations/unread`,
    MESSAGES_SYNC: `/${this.apiVersion}/conversations/messages`,
  } as const;

  /**
   * Set conversation unread count
   */
  static async setConversationUnread(
    channelId: string,
    channelType: number,
    unreadCount: number = 0
  ): Promise<{ success?: boolean } | void> {
    const service = new WuKongIMApiService();
    try {
      return await service.put<{ success?: boolean }>(
        service.endpoints.CONVERSATIONS_SET_UNREAD,
        {
          channel_id: channelId,
          channel_type: channelType,
          unread: unreadCount
        }
      );
    } catch (error) {
      console.error('Failed to set WuKongIM conversation unread:', error);
      throw new Error(service['handleApiError'](error));
    }
  }

  /**
   * Resolve WebSocket server URL for a given UID via dynamic route endpoint with caching and safe fallback
   */
  private static routeCache = new Map<string, { url: string; ts: number }>();
  private static readonly ROUTE_TTL_MS = 5 * 60 * 1000; // 5 minutes

  private static getCachedWsUrl(uid: string): string | null {
    const entry = this.routeCache.get(uid);
    if (!entry) return null;
    if (Date.now() - entry.ts > this.ROUTE_TTL_MS) {
      this.routeCache.delete(uid);
      return null;
    }
    return entry.url;
  }

  private static setCachedWsUrl(uid: string, url: string) {
    this.routeCache.set(uid, { url, ts: Date.now() });
  }

  /** Raw route call returning ws_addr/tcp_addr */
  static async getRoute(uid: string): Promise<{ tcp_addr: string; ws_addr: string;wss_addr:string }> {
    const service = new WuKongIMApiService();
    // Build endpoint with query since BaseQueryParams doesn't include uid
    const endpoint = `${service.endpoints.ROUTE}?uid=${encodeURIComponent(uid)}`;
    return service.get<{ tcp_addr: string; ws_addr: string;wss_addr:string }>(endpoint as any);
  }

  /** Build full ws URL from addr value and current scheme */
  private static buildWebSocketUrl(addr: string): string {
    if (!addr) return '';
    if (addr.includes('://')) return addr;
    const isHttps = (typeof window !== 'undefined') && window.location.protocol === 'https:';
    const scheme = isHttps ? 'wss://' : 'ws://';
    return `${scheme}${addr}`;
  }

  /** Public resolver with caching and env fallback */
  static async resolveWebSocketUrl(uid: string): Promise<string> {
    // Check cache first
    const cached = this.getCachedWsUrl(uid);
    if (cached) return cached;

    try {
      const route = await this.getRoute(uid);
      let addr = route.wss_addr;
      if (!addr || addr === "") {
        addr = route.ws_addr;
      }
      

      const wsUrl = this.buildWebSocketUrl(addr);
      if (wsUrl) {
        this.setCachedWsUrl(uid, wsUrl);
        return wsUrl;
      }
      throw new Error('Invalid ws_addr from route');
    } catch (err) {
      console.error('Failed to fetch WuKongIM route, using env fallback if available:', err);
      throw new Error('无法获取WuKongIM路由地址，请稍后重试');
    }
  }


  /**
   * Synchronize recent conversations from WuKongIM
   * @param request - Sync request parameters
   * @returns Promise with conversation sync response
   */
  static async syncConversations(
    request: WuKongIMConversationSyncRequest
  ): Promise<WuKongIMConversationSyncResponse> {
    const service = new WuKongIMApiService();
    try {
      return await service.post<WuKongIMConversationSyncResponse>(
        service.endpoints.CONVERSATIONS_SYNC,
        request
      );
    } catch (error) {
      console.error('Failed to sync WuKongIM conversations:', error);
      throw new Error(service['handleApiError'](error));
    }
  }

  /**
   * Sync conversations with default parameters for initial load
   * @param msgCount - Maximum message count per conversation (default: 20)
   * @returns Promise with conversation sync response
   */
  static async syncConversationsInitial(
    msgCount: number = 20
  ): Promise<WuKongIMConversationSyncResponse> {
    const request: WuKongIMConversationSyncRequest = {
      version: 0, // 0 indicates no local data
      msg_count: msgCount,
    };
    return this.syncConversations(request);
  }

  /**
   * Sync conversations incrementally with version tracking
   * @param version - Current client version
   * @param lastMsgSeqs - Last message sequences string
   * @param msgCount - Maximum message count per conversation (default: 20)
   * @returns Promise with conversation sync response
   */
  static async syncConversationsIncremental(
    version: number,
    lastMsgSeqs?: string,
    msgCount: number = 20
  ): Promise<WuKongIMConversationSyncResponse> {
    const request: WuKongIMConversationSyncRequest = {
      version,
      last_msg_seqs: lastMsgSeqs || null,
      msg_count: msgCount,
    };
    return this.syncConversations(request);
  }

  /**
   * Synchronize historical messages for a specific channel
   * Note: This endpoint is not yet available in the API, but provides the structure for future implementation
   * @param request - Message sync request parameters
   * @returns Promise with message sync response
   */
  static async syncChannelMessages(
    request: WuKongIMMessageSyncRequest
  ): Promise<WuKongIMMessageSyncResponse> {
    const service = new WuKongIMApiService();
    try {
      // For now, this will simulate the API call structure
      // When the actual endpoint becomes available, this will work seamlessly
      return await service.post<WuKongIMMessageSyncResponse>(
        service.endpoints.MESSAGES_SYNC,
        request
      );
    } catch (error) {
      console.error('Failed to sync WuKongIM channel messages:', error);

      throw new Error(service['handleApiError'](error));
    }
  }

  /**
   * Get historical messages for a channel with pagination
   * @param channelId - Channel ID
   * @param channelType - Channel type
   * @param limit - Maximum number of messages (default: 50)
   * @param startSeq - Starting sequence number (optional)
   * @returns Promise with message sync response
   */
  static async getChannelHistory(
    channelId: string,
    channelType: number,
    limit: number = 50,
    startSeq?: number
  ): Promise<WuKongIMMessageSyncResponse> {
    const user = useAuthStore.getState().user;
    const login_uid = user?.id ? `${user.id}-staff` : '';

    const request: WuKongIMMessageSyncRequest = {
      login_uid,
      channel_id: channelId,
      channel_type: channelType,
      start_message_seq: typeof startSeq === 'number' ? startSeq : 0,
      end_message_seq: 0,
      limit,
      pull_mode: 1 // upward/newer; 0/0 special case returns latest
    };
    return this.syncChannelMessages(request);
  }

  /**
   * Load more historical messages (pagination)
   * @param channelId - Channel ID
   * @param channelType - Channel type
   * @param beforeSeq - Load messages before this sequence number
   * @param limit - Maximum number of messages (default: 50)
   * @returns Promise with message sync response
   */
  static async loadMoreMessages(
    channelId: string,
    channelType: number,
    beforeSeq: number,
    limit: number = 50
  ): Promise<WuKongIMMessageSyncResponse> {
    const user = useAuthStore.getState().user;
    const login_uid = user?.id ? `${user.id}-staff` : '';

    const request: WuKongIMMessageSyncRequest = {
      login_uid,
      channel_id: channelId,
      channel_type: channelType,
      start_message_seq: beforeSeq, // inclusive
      end_message_seq: 0,
      limit,
      pull_mode: 0 // downward/older for infinite scroll
    };
    return this.syncChannelMessages(request);
  }

}

/**
 * Utility functions for WuKongIM data processing
 */
export class WuKongIMUtils {
  /**
   * Get channel type name from channel type number
   */
  static getChannelTypeName(channelType: number): string {
    switch (channelType) {
      case CHANNEL_TYPE.PERSON:
        return 'personal';
      case CHANNEL_TYPE.GROUP:
        return 'group';
      case CHANNEL_TYPE.CUSTOMER_SERVICE:
        return 'customer_service';
      default:
        return 'unknown';
    }
  }

  /**
   * Get platform name from channel type
   */
  static getPlatformFromChannelType(channelType: number): string {
    switch (channelType) {
      case CHANNEL_TYPE.PERSON:
        return PlatformType.WECHAT; // Personal chat - assume WeChat
      case CHANNEL_TYPE.GROUP:
        return 'group'; // Group chat (no dedicated PlatformType)
      case CHANNEL_TYPE.CUSTOMER_SERVICE:
        return PlatformType.WEBSITE; // Customer service - assume website
      default:
        return 'unknown';
    }
  }

  /**
   * Format timestamp from seconds to readable string
   */
  static formatTimestamp(timestamp: number): string {
    const date = new Date(timestamp * 1000); // Convert seconds to milliseconds
    return date.toLocaleTimeString('zh-CN', {
      hour: '2-digit',
      minute: '2-digit'
    });
  }

  /**
   * Extract message content from WuKongIM message (supports stream_data, payload object, and legacy string format)
   * @param wkMessage - WuKongIM message object
   * @returns Extracted message content string
   */
  static extractMessageContent(wkMessage: WuKongIMMessage | { payload: WuKongIMMessagePayload | string; stream_data?: string | null }): string {
    // Priority 1: Use stream_data if available and not empty
    if ('stream_data' in wkMessage && wkMessage.stream_data && wkMessage.stream_data.trim() !== '') {
      return wkMessage.stream_data;
    }

    // Priority 2: Extract from payload
    const payload = wkMessage.payload as any;

    // Handle new object format
    if (typeof payload === 'object' && payload !== null) {
      // Special-case image messages (type: 2) with no textual content
      if (payload.type === 2) {
        return payload.content || '[图片]';
      }
      // 处理系统消息 (type: 1000-2000) 的模板替换
      if (typeof payload.type === 'number' && isSystemMessageType(payload.type)) {
        return WuKongIMUtils.formatSystemMessageContent(payload.content, payload.extra);
      }
      return payload.content || '';
    }

    // Handle legacy string format (backward compatibility)
    if (typeof payload === 'string') {
      try {
        // Try to parse as JSON (old format where payload was JSON string)
        const parsed = JSON.parse(payload);
        // Check if it's the new object format embedded in string
        if (parsed && typeof parsed === 'object' && parsed.content !== undefined) {
          // 处理系统消息 (type: 1000-2000) 的模板替换
          if (typeof parsed.type === 'number' && isSystemMessageType(parsed.type)) {
            return WuKongIMUtils.formatSystemMessageContent(parsed.content, parsed.extra);
          }
          return parsed.content || (parsed.type === 2 ? '[图片]' : '');
        }
        // Fallback to old parsing logic
        return parsed.content || parsed.text || (parsed.type === 2 ? '[图片]' : payload);
      } catch {
        // If JSON parsing fails, return the string as-is
        return payload;
      }
    }

    // Fallback for any other type
    return String(payload || '');
  }

  /**
   * 格式化系统消息内容，将模板中的 {0}, {1} 等占位符替换为 extra 中对应的名称
   * @param template - 模板字符串，如 "您已接入人工客服，客服{0} 将为您服务"
   * @param extra - 额外信息数组，如 [{ uid: "xxx", name: "Administrator" }]
   * @returns 格式化后的字符串
   */
  static formatSystemMessageContent(template: string, extra?: Array<{ uid?: string; name?: string; [key: string]: any }>): string {
    if (!template) return '';
    if (!extra || extra.length === 0) return template;

    return template.replace(/\{(\d+)\}/g, (match, index) => {
      const idx = parseInt(index, 10);
      const item = extra[idx];
      return item?.name || match;
    });
  }

  /**
   * Convert WuKongIM message to internal Message format
   * @param wkMessage - WuKongIM message object
   * @returns Internal Message object
   */
  static convertToMessage(wkMessage: WuKongIMMessage): Message {
    const content = WuKongIMUtils.extractMessageContent(wkMessage);
    const payloadTypeNum = WuKongIMUtils.extractMessageType(wkMessage.payload);
    const payloadType = payloadTypeNum as MessagePayloadType;

    // Determine sender type based on from_uid and message context
    let senderType: 'visitor' | 'agent' | 'system' = 'visitor';
    if (wkMessage.from_uid === 'system') {
      senderType = 'system';
    } else if (wkMessage.from_uid && wkMessage.from_uid.endsWith(STAFF_UID_SUFFIX)) {
      senderType = 'agent';
    }

    const idStr = (wkMessage as any).message_id_str
      || (typeof (wkMessage as any).message_id === 'string' ? (wkMessage as any).message_id : ((wkMessage as any).message_id != null ? String((wkMessage as any).message_id) : undefined))
      || ((wkMessage as any).messageId != null ? String((wkMessage as any).messageId) : undefined)
      || String(Date.now());
    const channelType = wkMessage.channel_type || (wkMessage as any).channelType || DEFAULT_CHANNEL_TYPE;

    // Derive image metadata if this is an image message (type 2) or rich text with images (type 12)
    const rawPayload: WuKongIMMessagePayload | string = wkMessage.payload as any;
    let payloadObj: any = undefined;
    if (typeof rawPayload === 'object' && rawPayload !== null) {
      payloadObj = rawPayload;
    } else if (typeof rawPayload === 'string') {
      try { payloadObj = JSON.parse(rawPayload); } catch {}
    }

    let imageMeta: Record<string, any> = {};
    let fileMeta: Record<string, any> = {};
    let richImagesMeta: PayloadRichTextImage[] | undefined;
    let typedPayload: MessagePayload | undefined;

    if (payloadType === MessagePayloadType.IMAGE) {
      const url0 = payloadObj?.url || payloadObj?.file_url || payloadObj?.imageUrl || payloadObj?.image_url;
      const url = url0 ? toAbsoluteApiUrl(url0) : undefined;
      const width = payloadObj?.width || payloadObj?.image_width;
      const height = payloadObj?.height || payloadObj?.image_height;
      typedPayload = { type: MessagePayloadType.IMAGE, content: payloadObj?.content || content || '[图片]', url: url || '', width, height };
      imageMeta = { image_url: url || url0, image_width: width, image_height: height };
    } else if (payloadType === MessagePayloadType.RICH_TEXT) {
      const imgs: PayloadRichTextImage[] = Array.isArray(payloadObj?.images)
        ? payloadObj.images.map((img: any) => {
            const u0 = img?.url || img?.file_url || img?.image_url;
            const u = u0 ? toAbsoluteApiUrl(u0) : undefined;
            return { url: (u || u0) as string, width: img?.width || img?.image_width, height: img?.height || img?.image_height };
          })
        : [];

      // Handle file attachment in rich text
      let fileAttachment: { url: string; name: string; size?: number } | undefined;
      if (payloadObj?.file && typeof payloadObj.file === 'object') {
        const fileUrl0 = payloadObj.file.url || payloadObj.file.file_url;
        const fileUrl = fileUrl0 ? toAbsoluteApiUrl(fileUrl0) : undefined;
        fileAttachment = {
          url: (fileUrl || fileUrl0 || '') as string,
          name: payloadObj.file.name || payloadObj.file.file_name || '未命名文件',
          size: payloadObj.file.size || payloadObj.file.file_size,
        };
        fileMeta = { file_url: fileAttachment.url, file_name: fileAttachment.name, file_size: fileAttachment.size };
      }

      typedPayload = {
        type: MessagePayloadType.RICH_TEXT,
        content: payloadObj?.content ?? content ?? '',
        images: imgs,
        file: fileAttachment
      };
      richImagesMeta = imgs;
    } else if (payloadType === MessagePayloadType.FILE) {
      const url0 = payloadObj?.url || payloadObj?.file_url || payloadObj?.fileUrl;
      const url = url0 ? toAbsoluteApiUrl(url0) : undefined;
      const name = payloadObj?.name || payloadObj?.file_name || payloadObj?.filename || '';
      const size = payloadObj?.size || payloadObj?.file_size;
      typedPayload = { type: MessagePayloadType.FILE, url: (url || url0 || '') as string, name, size } as any;
      fileMeta = { file_url: url || url0, file_name: name, file_size: size };
    } else if (payloadType === MessagePayloadType.TEXT) {
      typedPayload = { type: MessagePayloadType.TEXT, content };
    }

    // 处理系统消息 (payload.type 在 1000-2000 范围内)
    if (isSystemMessageType(payloadTypeNum)) {
      // 系统消息直接使用原始 payload 对象
      typedPayload = {
        type: payloadTypeNum,
        content: payloadObj?.content || content || '',
        extra: payloadObj?.extra || [],
      } as PayloadSystem;
    }

    // Determine if this is a streaming message that's still in progress
    // A message is streaming if:
    // 1. It has stream_data (indicating it's a stream message)
    // 2. end field is not 1 (end=1 means streaming finished)
    const hasStreamData = !!(wkMessage.stream_data && wkMessage.stream_data.trim() !== '');
    const isStreamingInProgress = hasStreamData && wkMessage.end !== 1;

    // Extract end and end_reason for error state detection
    const streamEnd = wkMessage.end;
    const streamEndReason = wkMessage.end_reason;
    
    // Extract error message from WuKongIMMessage.error field first, then fallback to payload.error
    // This supports both real-time stream end events and offline API responses
    const errorMessage = (wkMessage.error && typeof wkMessage.error === 'string' && wkMessage.error.trim() !== '')
      ? wkMessage.error.trim()
      : (payloadObj?.error && typeof payloadObj.error === 'string' && payloadObj.error.trim() !== '')
        ? payloadObj.error.trim()
        : undefined;

    const convertedMessage: Message = {
      id: idStr,
      content,
      timestamp: new Date(wkMessage.timestamp * 1000).toISOString(),
      type: senderType === 'agent' ? MESSAGE_SENDER_TYPE.STAFF : (senderType === 'system' ? MESSAGE_SENDER_TYPE.SYSTEM : MESSAGE_SENDER_TYPE.VISITOR),
      status: 'delivered',
      isRead: false,
      platform: WuKongIMUtils.getPlatformFromChannelType(channelType),
      messageId: idStr,
      clientMsgNo: wkMessage.client_msg_no || (wkMessage as any).clientMsgNo,
      messageSeq: wkMessage.message_seq || (wkMessage as any).messageSeq,
      fromUid: wkMessage.from_uid || (wkMessage as any).fromUid,
      channelId: wkMessage.channel_id || (wkMessage as any).channelId,
      channelType: channelType,
      payloadType: payloadType,
      payload: typedPayload,
      metadata: {
        sender_avatar: (wkMessage as any).sender_avatar,
        is_read: false,
        has_stream_data: hasStreamData,
        is_streaming: isStreamingInProgress, // Flag for UI to show loading cursor
        stream_end: streamEnd, // Stream end flag (0=not ended, 1=ended)
        stream_end_reason: streamEndReason, // Stream end reason code (>0 indicates error)
        error: errorMessage, // Error message from stream end event or API response
        ...imageMeta,
        ...fileMeta,
        ...(richImagesMeta ? { images: richImagesMeta } : {}),
      }
    };

    return convertedMessage;
  }

  /**
   * Extract message type from payload (supports both new object format and legacy string format)
   * @param payload - Message payload (object with content/type or legacy string)
   * @returns Message type number (defaults to 1 for text messages)
   */
  static extractMessageType(payload: WuKongIMMessagePayload | string): number {
    // Handle new object format
    if (typeof payload === 'object' && payload !== null) {
      return payload.type || 1; // Default to type 1 (text) if not specified
    }

    // Handle legacy string format
    if (typeof payload === 'string') {
      try {
        const parsed = JSON.parse(payload);
        if (parsed && typeof parsed === 'object' && parsed.type !== undefined) {
          return parsed.type;
        }
      } catch {
        // JSON parsing failed, assume text message
      }
    }

    // Default to type 1 (text message)
    return 1;
  }



  /**
   * Enhance WuKongIM message with additional UI metadata
   * @param message - Raw WuKongIM message
   * @returns Enhanced message with UI metadata
   */
  static enhanceMessage(message: WuKongIMMessage): WuKongIMEnhancedMessage {
    return {
      ...message,
      sender_name: this.getSenderName(message.from_uid),
      sender_avatar: this.getSenderAvatar(message.from_uid),
      is_read: true, // Default to read for historical messages
    };
  }

  static getSendType(wkMessage: WuKongIMMessage): MessageSenderType {
    const user = useAuthStore.getState().user;
    const currentUid = user?.id ? `${user.id}-staff` : null;

    if (currentUid && wkMessage.from_uid === currentUid) {
      return MESSAGE_SENDER_TYPE.STAFF;
    }

    return MESSAGE_SENDER_TYPE.VISITOR;
  }

  /**
   * Get sender display name from UID
   * @param uid - User ID
   * @returns Display name
   */
  static getSenderName(uid: string): string {
    // In a real implementation, this would look up user info
    // For now, generate a display name based on UID
    if (uid.includes('agent') || uid.includes('staff')) {
      return '客服';
    }
    return `用户${uid.slice(-4)}`;
  }

  /**
   * Get sender avatar URL from UID
   * @param uid - User ID
   * @returns Avatar URL
   */
  static getSenderAvatar(uid: string): string {
    // Generate consistent avatar based on UID
    const hash = uid.split('').reduce((a, b) => a + b.charCodeAt(0), 0);
    return `https://i.pravatar.cc/32?img=${Math.abs(hash) % 10 + 1}`;
  }

  /**
   * Sort messages by sequence number
   * @param messages - Array of messages
   * @param order - Sort order ('asc' or 'desc')
   * @returns Sorted messages
   */
  static sortMessages(messages: WuKongIMMessage[], order: 'asc' | 'desc' = 'asc'): WuKongIMMessage[] {
    return [...messages].sort((a, b) => {
      return order === 'asc'
        ? a.message_seq - b.message_seq
        : b.message_seq - a.message_seq;
    });
  }

  /**
   * Deduplicate messages by message_id
   * @param messages - Array of messages
   * @returns Deduplicated messages
   */
  static deduplicateMessages(messages: WuKongIMMessage[]): WuKongIMMessage[] {
    const seen = new Set<string>();
    return messages.filter(message => {
      const key = (message as any).message_id_str || (typeof (message as any).message_id === 'string' ? (message as any).message_id : String((message as any).message_id));
      if (seen.has(key)) {
        return false;
      }
      seen.add(key);
      return true;
    });
  }

  /**
   * Merge new messages with existing messages, maintaining order and deduplication
   * @param existingMessages - Current messages
   * @param newMessages - New messages to merge
   * @param order - Sort order
   * @returns Merged and sorted messages
   */
  static mergeMessages(
    existingMessages: WuKongIMMessage[],
    newMessages: WuKongIMMessage[],
    order: 'asc' | 'desc' = 'asc'
  ): WuKongIMMessage[] {
    const allMessages = [...existingMessages, ...newMessages];
    const deduplicated = this.deduplicateMessages(allMessages);
    return this.sortMessages(deduplicated, order);
  }

  /**
   * Generate last message sequences string for sync request
   */
  static generateLastMsgSeqs(conversations: any[]): string {
    return conversations
      .map(conv => `${conv.channel_id}:${conv.channel_type}:${conv.last_msg_seq}`)
      .join('|');
  }
}
