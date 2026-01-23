/**
 * Centralized constants for common values used across the app
 * Use these instead of hardcoded literals to improve maintainability.
 */

// ----------------------------------------------------------------------------
// Channel types (WuKongIM)
// ----------------------------------------------------------------------------

/**
 * Channel type constants from WuKongIM
 * 1 = person, 2 = group, 3 = customer service
 */
export const CHANNEL_TYPE = {
  PERSON: 1,
  GROUP: 2,
  CUSTOMER_SERVICE: 3,
} as const;

/** Default channel type to use when backend value is missing */
export const DEFAULT_CHANNEL_TYPE = CHANNEL_TYPE.PERSON;

// ----------------------------------------------------------------------------
// Message sender types (ownership/display)
// ----------------------------------------------------------------------------

/**
 * Sender type of a message in UI context
 */
export const MESSAGE_SENDER_TYPE = {
  VISITOR: 'visitor',
  STAFF: 'staff',
  SYSTEM: 'system',
} as const;

// ----------------------------------------------------------------------------
// Chat related enums
// ----------------------------------------------------------------------------

/** Chat status values */
export const CHAT_STATUS = {
  ACTIVE: 'active',
  WAITING: 'waiting',
  CLOSED: 'closed',
  TRANSFERRED: 'transferred',
} as const;

/** Chat priority values */
export const CHAT_PRIORITY = {
  LOW: 'low',
  NORMAL: 'normal',
  HIGH: 'high',
  URGENT: 'urgent',
} as const;

/** Visitor presence status values */
export const VISITOR_STATUS = {
  ONLINE: 'online',
  AWAY: 'away',
  OFFLINE: 'offline',
} as const;

// ----------------------------------------------------------------------------
// WuKongIM UID conventions
// ----------------------------------------------------------------------------

/** Suffix appended to staff agent UIDs */
export const STAFF_UID_SUFFIX = '-staff' as const;

// ----------------------------------------------------------------------------
// Auth / User
// ----------------------------------------------------------------------------

/** User role values */
export const USER_ROLE = {
  USER: 'user',
  AGENT: 'agent',
} as const;

// ----------------------------------------------------------------------------
// Storage keys
// ----------------------------------------------------------------------------

/** Keys used for localStorage/zustand persist */
export const STORAGE_KEYS = {
  AUTH: 'auth-storage',
  CHAT: 'chat-store',
  UI: 'ui-store',
  PROVIDERS: 'providers-store',
  AUTH_TOKEN: 'tgo-auth-token',
  // Split chat stores
  CONVERSATION: 'conversation-store',
  MESSAGE: 'message-store',
  SYNC: 'sync-store',
  TOOLSTORE_AUTH: 'toolstore-auth-storage',
  TOOLSTORE_TOKEN: 'toolstore-auth-token',
  TOOLSTORE_REFRESH_TOKEN: 'toolstore-refresh-token',
} as const;

/** Tool Store URLs (Deprecated: Use storeApi.getStoreConfig() instead) */
export const TOOL_STORE_URLS = {
  WEB: (window as any).ENV?.VITE_TOOLSTORE_WEB_URL || 'http://localhost:3002',
  API: (window as any).ENV?.VITE_TOOLSTORE_API_URL || 'http://localhost:8095',
} as const;

// ----------------------------------------------------------------------------
// Platform types
// ----------------------------------------------------------------------------
// Note: Use PlatformType enum from '@/types' for specific platforms.
// This section is here to document the convention and avoid hardcoding
// arbitrary strings. Prefer importing PlatformType where possible.
export { PlatformType } from '@/types';

// ----------------------------------------------------------------------------
// WebSocket Event Types
// ----------------------------------------------------------------------------

/**
 * WebSocket event type constants for real-time updates
 */
export const WS_EVENT_TYPE = {
  /** Visitor profile updated (name, tags, etc.) */
  VISITOR_PROFILE_UPDATED: 'visitor.profile.updated',
  /** Visitor presence changed (online/offline) */
  VISITOR_PRESENCE: 'visitor.presence',
  /** Waiting queue updated (new visitor, assigned, etc.) */
  QUEUE_UPDATED: 'queue.updated',
  /** AI streaming text message end */
  TEXT_MESSAGE_END: '___TextMessageEnd',
} as const;

export type WsEventType = typeof WS_EVENT_TYPE[keyof typeof WS_EVENT_TYPE];

