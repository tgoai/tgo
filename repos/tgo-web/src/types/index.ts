// Core types for the application

export interface Platform {
  id: string;
  name: string;
  display_name?: string; // display name for UI (preferred over name)
  icon: string;
  iconColor: string;
  status: PlatformStatus;
  statusText: string;
  statusColor: string;
  type: string; // Use API-returned type directly
  is_supported?: boolean; // whether this platform type is currently supported
  description: string;
  config: PlatformConfig;
  // Top-level callback URL from API (not nested in config)
  callback_url?: string;
  // Top-level logo URL from API (read-only on backend, updated via POST /platforms/{id}/logo)
  logo_url?: string | null;
  // Chat completion URL for custom platforms (only returned for type='custom')
  chat_url?: string | null;
}

export type PlatformStatus = 'connected' | 'pending' | 'unconfigured' | 'disabled' | 'error';

export enum PlatformType {
  WEBSITE = "website",
  WECHAT = "wechat",
  WHATSAPP = "whatsapp",
  TELEGRAM = "telegram",
  EMAIL = "email",
  SMS = "sms",
  FACEBOOK = "facebook",
  INSTAGRAM = "instagram",
  TWITTER = "twitter",
  LINKEDIN = "linkedin",
  DISCORD = "discord",
  SLACK = "slack",
  TEAMS = "teams",
  WEBCHAT = "webchat",
  PHONE = "phone",
  DOUYIN = "douyin",
  TIKTOK = "tiktok",
  CUSTOM = "custom",
  WECOM = "wecom"
}

export interface PlatformConfig {
  [key: string]: any;
  webhookUrl?: string;
  secretKey?: string;
  outgoingUrl?: string;
  outgoingToken?: string;
  enabled?: boolean;
  domain?: string;
  embedCode?: string;
  appId?: string;
  appSecret?: string;
  token?: string;
  smtpHost?: string;
  smtpPort?: number;
  username?: string;
  lastError?: string;
}

/**
 * Custom platform configuration
 */
export interface CustomConfig {
  apiKey?: string;
  callbackUrl?: string; // Third-party callback URL to receive messages from customer service
}

export interface PlatformStatusConfig {
  label: string;
  bgColor: string;
  textColor: string;
}

export interface PlatformTypeConfig {
  label: string;
  color: string;
}

export interface Agent {
  id: string;
  name: string;
  description: string;
  avatar: string;
  status: AgentStatus;
  type?: AgentType;
  role?: string;
  llmModel?: string;
  endpoint?: string;
  capabilities: string[];
  lastActive: string;
  conversationCount: number;
  successRate: number;
  responseTime: string;
  tags: string[];
  mcpTools: string[]; // MCP工具ID列表 (for backward compatibility)
  mcpToolConfigs?: Record<string, Record<string, any>>; // 工具配置
  knowledgeBases: string[]; // 知识库ID列表 (for backward compatibility)
  collections?: AICollectionResponse[]; // Full collection objects from API
  tools?: AgentToolResponse[]; // Full tool objects from API
}

export type AgentStatus = 'active' | 'inactive' | 'training' | 'error';
export type AgentType = 'coordinator' | 'expert';

// 智能体创建表单数据类型
export interface CreateAgentFormData {
  name: string;
  profession: string; // 职业/角色字段
  description: string;
  llmModel: string;
  mcpTools: string[];
  mcpToolConfigs: Record<string, Record<string, any>>; // 工具配置
  knowledgeBases: string[];
}

// 表单验证错误类型
export interface FormValidationErrors {
  name?: string;
  profession?: string;
  description?: string;
  llmModel?: string;
  type?: string;
}

// API-specific Agent types based on OpenAPI specification
// AI Collection Response Type (based on API spec)
export interface AICollectionResponse {
  id: string;
  display_name: string;
  description?: string | null;
  collection_metadata?: Record<string, any> | null;
  created_at: string;
  updated_at: string;
  deleted_at?: string | null;
}

// Agent Tool Response Type (based on API spec)
export interface AgentToolResponse {
  id: string;
  tool_name: string; // Format: 'provider:tool_name' (e.g., 'arcade:web_search')
  enabled: boolean;
  permissions?: string[] | null;
  config?: Record<string, any> | null;
  agent_id: string;
  created_at: string;
  updated_at: string;
  deleted_at?: string | null;
}

// Some agent detail APIs may return full tool details instead of AgentToolResponse
export interface AgentToolDetailed {
  id: string;
  name: string;
  title?: string;
  description?: string | null;
  version?: string | null;
  category?: string | null;
  tags?: string[];
  status: ToolStatus; // Reuse ToolStatus from tools API
  tool_source_type?: ToolSourceType;
  input_schema?: Record<string, any>;
  output_schema?: Record<string, any> | null;
  meta_data?: Record<string, any> | null;
  created_at?: string;
  updated_at?: string;
  mcp_server_id?: string | null;
  mcp_server?: {
    id?: string;
    name?: string;
    description?: string;
    endpoint?: string;
    short_no?: string | null;
    status?: string;
  } | null;
  // Backward compatibility fields
  enabled?: boolean;
  tool_name?: string;
  config?: Record<string, any> | null;
}

export type AgentToolUnion = AgentToolResponse | AgentToolDetailed;

// Agent Response Type (basic agent info)
export interface AgentResponse {
  id: string;
  name: string;
  instruction: string | null;
  model: string;
  is_default: boolean;
  config: Record<string, any> | null;
  team_id: string | null;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
}

// Agent With Details Response Type (includes tools and collections)
export interface AgentWithDetailsResponse {
  id: string;
  name: string;
  instruction?: string | null;
  model: string;
  ai_provider_id?: string | null;
  is_default: boolean;
  config?: Record<string, any> | null;
  team_id?: string | null;
  created_at: string;
  updated_at: string;
  deleted_at?: string | null;
  tools: AgentToolResponse[];
  collections: AICollectionResponse[];
}

// Agent Tool Create Request Type (based on API spec)
export interface AgentToolCreateRequest {
  tool_id: string; // Tool ID (UUID) to bind to the agent
  enabled?: boolean; // Default: true
  permissions?: string[] | null;
  config?: Record<string, any> | null;
}

// Agent Create Request Type (based on API spec)
export interface AgentCreateRequest {
  name: string;
  instruction?: string | null;
  model: string; // pure model name (e.g., 'gpt-4o'), no provider prefix
  is_default?: boolean;
  config?: Record<string, any> | null;
  team_id?: string | null;
  ai_provider_id?: string | null; // AI provider UUID (credentials)
  tools?: AgentToolCreateRequest[] | null;
  collections?: string[] | null; // Collection IDs (UUID strings)
}

// Agent Update Request Type (based on API spec - all fields optional)
export interface AgentUpdateRequest {
  name?: string | null;
  instruction?: string | null;
  model?: string | null; // pure model name (no provider prefix)
  is_default?: boolean | null;
  config?: Record<string, any> | null;
  team_id?: string | null;
  ai_provider_id?: string | null; // AI provider UUID (credentials)
  tools?: AgentToolCreateRequest[] | null;
  collections?: string[] | null; // Collection IDs (UUID strings)
}

// Agent List Response Type (now returns detailed agents with tools and collections)
export interface AgentListResponse {
  data: AgentWithDetailsResponse[];
  pagination: PaginationMetadata;
}

// Pagination Metadata Type
export interface PaginationMetadata {
  total: number;
  limit: number;
  offset: number;
  has_next: boolean;
  has_prev: boolean;
}

// Agent Query Parameters
export interface AgentQueryParams {
  team_id?: string | null;
  model?: string | null;
  is_default?: boolean | null;
  limit?: number;
  offset?: number;
}

export interface MCPTool {
  id: string;
  name: string;
  title?: string; // Display title for the tool (may be different from name)
  description: string;
  category: MCPCategory;
  status: MCPToolStatus;
  version: string;
  endpoint?: string;
  author: string;
  lastUpdated: string;
  usageCount: number;
  rating: number;
  tags: string[];
  capabilities?: string[];
  config?: Record<string, any>;
  successRate?: number;
  avgResponseTime?: string;
  input_schema?: Record<string, any>; // Add input_schema for detail display
  short_no?: string; // Add short_no field from API response
}

export type MCPCategory = 'all' | 'productivity' | 'communication' | 'data' | 'ai' | 'integration';

export type MCPToolStatus = 'active' | 'inactive' | 'updating' | 'error';

// API Response types for AI Models (based on OpenAPI spec)
export interface ModelInfo {
  id: string;
  display_name: string;
  provider: string;
  model_type: ModelType;
  status: ModelStatus;
  capabilities: ModelCapabilities;
  pricing_tier: PricingTier;
  description?: string | null;
  version?: string | null;
  release_date?: string | null;
  deprecation_date?: string | null;
  documentation_url?: string | null;
}

export interface ModelListResponse {
  data: ModelInfo[];
  pagination: PaginationMetadata;
}

export interface ModelCapabilities {
  supports_function_calling: boolean;
  supports_vision: boolean;
  supports_streaming: boolean;
  context_length: number;
}

export type ModelType = 'chat' | 'completion' | 'embedding' | 'image' | 'audio';
export type ModelStatus = 'active' | 'deprecated' | 'maintenance' | 'beta';
export type PricingTier = 'free' | 'basic' | 'premium' | 'enterprise';

export interface ModelQueryParams {
  provider?: string | null;
  type?: ModelType | null;
  status?: ModelStatus | null;
  limit?: number;
  offset?: number;
}

// API Response types for MCP Tools (based on OpenAPI spec)
export interface ToolSummary {
  id: string;
  name: string;
  title?: string; // Display title for the tool (may be different from name)
  description: string | null;
  version: string;
  category: string | null;
  tags: string[];
  status: ToolStatus;
  tool_source_type: ToolSourceType;
  execution_count: number | null;
  created_at: string;
  mcp_server_id: string | null;
  input_schema: Record<string, any>;
  output_schema: Record<string, any> | null;
  short_no: string | null;
  is_installed?: boolean; // Installation status from backend
}

export interface ToolListResponse {
  timestamp: string;
  request_id: string | null;
  meta: ProjectToolsMeta;
  data: ToolSummary[];
}

// Detailed tool response interface (based on OpenAPI spec)
// NOTE: This is the OLD ToolResponse for MCP tools marketplace
// For the new /v1/ai/tools API, see AiToolResponse below
export interface ToolResponse {
  id: string;
  name: string;
  title?: string; // Display title for the tool (may be different from name)
  description: string | null;
  version: string;
  category: string | null;
  tags: string[];
  status: ToolStatus;
  input_schema: Record<string, any>;
  output_schema: Record<string, any> | null;
  meta_data: Record<string, any> | null;
  tool_source_type: ToolSourceType;
  mcp_server_id: string | null;
  project_id: string | null;
  execution_count: number | null;
  last_executed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface PaginationMetadata {
  total: number;
  limit: number;
  offset: number;
  has_next: boolean;
  has_prev: boolean;
}

// New meta pagination object for project tools API
// @deprecated - Old API, will be removed after migration to /v1/ai/tools
export interface ProjectToolsMeta {
  page: number;
  limit: number;
  total: number;
  total_pages: number;
  has_next: boolean;
  has_prev: boolean;
}

export type ToolStatus = 'ACTIVE' | 'INACTIVE' | 'DEPRECATED';
export type ToolSourceType = 'MARKETPLACE' | 'CUSTOM' | 'MCP_SERVER';

// Tool type enumeration for /v1/ai/tools API
export type ToolType = 'MCP' | 'FUNCTION';

// Project Tools API Response types (based on updated OpenAPI spec)
// @deprecated - Old API, will be removed after migration to /v1/ai/tools
export interface ProjectToolResponse {
  id: string;
  project_id: string;
  tool_id: string;
  is_enabled: boolean;
  installed_at: string;
  created_at: string;
  updated_at: string;
  // Flattened tool information (no nested tool object)
  tool_name: string;
  tool_version: string;
  tool_source_type: string;
  tool_status: string;
  tool_description: string | null;
  tool_category: string | null;
  // New fields from updated API
  mcp_server_id: string | null;
  input_schema: Record<string, any>;
  output_schema: Record<string, any> | null;
  short_no: string | null;
}

// @deprecated - Old API, will be removed after migration to /v1/ai/tools
export interface ProjectToolListResponse {
  timestamp: string;
  request_id: string | null;
  meta: ProjectToolsMeta;
  data: ProjectToolResponse[];
}

// ============================================================================
// NEW /v1/ai/tools API Types (based on docs/api.json)
// ============================================================================

/**
 * Tool response from /v1/ai/tools API
 * This is the NEW API response format
 */
export interface AiToolResponse {
  created_at: string; // date-time
  updated_at: string; // date-time
  deleted_at: string | null; // date-time, soft delete timestamp
  id: string; // uuid
  project_id: string; // uuid
  name: string;
  description: string | null;
  tool_type: ToolType; // "MCP" | "FUNCTION"
  transport_type: string | null;
  endpoint: string | null;
  config: Record<string, any> | null;
}

/**
 * Tool create request for /v1/ai/tools API
 */
export interface AiToolCreateRequest {
  project_id: string; // uuid - required
  name: string; // required
  description?: string | null;
  tool_type: ToolType; // "MCP" | "FUNCTION" - required
  transport_type?: string | null;
  endpoint?: string | null;
  config?: Record<string, any> | null;
}

/**
 * Tool update request for PATCH /v1/ai/tools/{tool_id} API
 * All fields are optional (PATCH semantics)
 */
export interface AiToolUpdateRequest {
  name?: string | null;
  description?: string | null;
  tool_type?: ToolType | null; // "MCP" | "FUNCTION"
  transport_type?: string | null;
  endpoint?: string | null;
  config?: Record<string, any> | null;
}

// Tool Store Types
export interface ToolStoreItem {
  id: string;
  name: string;
  title?: string; // Display title for the tool (may be different from name)
  description: string;
  author: string;
  authorHandle: string;
  category: string;
  tags: string[];
  downloads: number;
  rating: number;
  ratingCount: number;
  version: string;
  lastUpdated: string;
  featured: boolean;
  verified: boolean;
  icon: string;
  screenshots: string[];
  longDescription: string;
  requirements: string[];
  changelog: string;
  mcpMethods?: MCPToolMethod[];
  isInstalled?: boolean; // Whether the tool is already installed in the project
  input_schema?: Record<string, any>; // Schema from API response
  short_no?: string; // Short number/identifier from API response
}

export interface ToolStoreCategory {
  id: string;
  label: string;
  icon: string;
}

// MCP Tool Method Types
export interface MCPToolMethod {
  id: string;
  name: string;
  description: string;
  parameters: MCPToolParameter[];
  returnType: string;
  example?: string;
}

export interface MCPToolParameter {
  name: string;
  type: string;
  required: boolean;
  description: string;
  example?: string;
}

export interface ChatTag {
  name: string;
  color?: string | null;
}

// Visitor tag object from API (subset preserved through ChannelVisitorExtra)
export interface VisitorTag {
  name: string;
  category: string;
  weight: number;
  color: string;
  description: string | null;
  id: string;
}

export interface Chat {
  id: string;
  platform: string; // 渠道平台（wechat/tiktok/website等）
  lastMessage: string;
  timestamp: string; // ISO string for display formatting
  // Numeric timestamp in seconds for sorting (from WuKongIM API)
  lastTimestampSec?: number;
  status: ChatStatus;
  unreadCount: number;

  // Flattened WuKongIM metadata
  channelId: string;
  channelType: number;
  lastMsgSeq: number;

  // Lazily loaded channel info (name/avatar etc.)
  channelInfo?: ChannelInfo;

  // Additional presentation and business fields
  tags: ChatTag[];
  priority: ChatPriority;
  visitorStatus?: VisitorStatus; // 访客在线状态
  lastSeenMinutes?: number; // 最后在线时间（分钟前）

  // Keep metadata but remove nested wukongim object
  metadata?: {
    [key: string]: any;
  };
}

export type ChatStatus = 'active' | 'waiting' | 'closed' | 'transferred';

export type ChatPriority = 'low' | 'normal' | 'high' | 'urgent';

export interface MessageAction {
  label: string;
  type: 'primary' | 'secondary' | 'danger';
  action?: string;
}

export interface MessageAIInfo {
  title: string;
  status: string;
  details?: Record<string, any>;
  actions?: MessageAction[];
}

export enum MessagePayloadType {
  TEXT = 1,
  IMAGE = 2,
  FILE = 3,
  RICH_TEXT = 12,
  STREAM = 100,  // 流消息类型（AI 流式输出开始）
  // 系统消息类型范围：1000-2000
  SYSTEM_MIN = 1000,
  SYSTEM_STAFF_ASSIGNED = 1000,  // 已分配到客服
  SYSTEM_SESSION_CLOSED = 1001,  // 会话关闭
  SYSTEM_MAX = 2000,
}

/**
 * 检查是否是需要刷新频道信息的系统消息类型
 * 1000 - 已分配到客服
 * 1001 - 会话关闭
 */
export function isChannelRefreshSystemMessage(type: number): boolean {
  return type === MessagePayloadType.SYSTEM_STAFF_ASSIGNED || type === MessagePayloadType.SYSTEM_SESSION_CLOSED;
}

/**
 * 检查消息类型是否为系统消息
 * 系统消息的 payload.type 范围在 1000-2000 之间
 */
export function isSystemMessageType(type: number): boolean {
  return type >= MessagePayloadType.SYSTEM_MIN && type <= MessagePayloadType.SYSTEM_MAX;
}

/**
 * 系统消息中的额外信息项
 */
export interface SystemMessageExtraItem {
  uid?: string;
  name?: string;
  [key: string]: any;
}

/**
 * 系统消息 Payload
 */
export interface PayloadSystem {
  type: number; // 1000-2000
  content: string; // 模板字符串，如 "您已接入人工客服，客服{0} 将为您服务"
  extra?: SystemMessageExtraItem[];
}

// Strongly-typed message payloads
export interface PayloadText {
  type: MessagePayloadType.TEXT;
  content: string;
}

export interface PayloadImage {
  type: MessagePayloadType.IMAGE;
  content?: string;
  url: string;
  width?: number;
  height?: number;
}

export interface PayloadFile {
  type: MessagePayloadType.FILE;
  url: string;
  name: string;
  size?: number;
}

export interface PayloadRichTextImage {
  url: string;
  width?: number;
  height?: number;
}

export interface PayloadRichText {
  type: MessagePayloadType.RICH_TEXT;
  content: string;
  images: PayloadRichTextImage[];
  file?: {
    url: string;
    name: string;
    size?: number;
  };
}

export type MessagePayload = PayloadText | PayloadImage | PayloadFile | PayloadRichText | PayloadSystem;


export interface Message {
  id: string;
  chatId?: string;
  // Unified sender info (preferred)
  fromInfo?: ChannelInfo;
  // Ownership/display type (no longer tied to sender identity like 'visitor'/'staff')
  type: MessageSenderType;
  content: string;
  timestamp: string;
  status?: MessageStatus;
  platform?: string;
  // Backward-compat (deprecated): prefer fromInfo.avatar — will be removed later
  avatar?: string;
  aiInfo?: MessageAIInfo;
  isRead?: boolean;
  attachments?: MessageAttachment[];

  // New: Strongly-typed message payload
  payload?: MessagePayload;

  // Flattened WuKongIM metadata (camelCase)
  messageId?: string; // was wukongim.message_id (now string)
  clientMsgNo?: string; // was client_msg_no
  messageSeq?: number; // was message_seq
  fromUid?: string; // was from_uid
  channelId?: string; // was channel_id
  channelType?: number; // was channel_type
  payloadType?: MessagePayloadType; // was payload_type

  // Metadata (no nested wukongim)
  metadata?: {
    sender_avatar?: string;
    is_read?: boolean;
    has_stream_data?: boolean; // Flag to indicate if content comes from stream_data field
    is_streaming?: boolean; // Flag to indicate the message is still receiving stream data
    stream_started?: boolean; // Indicates whether the first stream chunk has been applied
    last_stream_update?: number; // Timestamp for the latest stream content update
    error?: string; // Error message from stream end event or API response
    [key: string]: any;
  };
}

export type MessageSenderType = 'visitor' | 'staff' | 'system';

export type MessageType = 'text' | 'image' | 'file' | 'system' | 'quick_reply';

export type MessageStatus = 'sent' | 'delivered' | 'read' | 'failed';

export interface MessageAttachment {
  id: string;
  name: string;
  type: string;
  size: number;
  url: string;
}

export interface Visitor {
  id: string;
  name: string;
  email?: string;
  avatar: string;
  location?: string;
  device?: string;
  browser?: string;
  platform?: string;
  firstVisit: string;
  lastSeen?: string;
  lastVisit?: string;
  visitCount?: number;
  pageViews?: number;
  sessionDuration?: string;
  status?: VisitorStatus;
  tags: string[];
  notes?: string;
  phone?: string;
}

export type VisitorStatus = 'online' | 'away' | 'offline';

// Visitor recent activity types from channel info API
export type VisitorActivityType = 'session_start' | 'session_end' | 'page_view' | string;

export interface VisitorActivityContext {
  page_url?: string;
  referrer?: string;
  metadata?: Record<string, any> | null;
  [key: string]: any;
}

export interface VisitorActivity {
  id: string;
  activity_type: VisitorActivityType | string;
  title: string;
  description?: string | null;
  occurred_at: string; // ISO timestamp
  duration_seconds?: number | null;
  context?: VisitorActivityContext | null;
}



// Visitor system information from channel info API
export interface SystemInfo {
  platform: string;
  source_detail: string;
  browser: string;
  operating_system: string;
  first_seen_at: string; // ISO timestamp
}

/**
 * Unified channel information model
 */
export interface ChannelStaffExtra {
  staff_id: string;
  username: string;
  role: string; // e.g., 'user' | 'agent'
}

export interface ChannelAIInsights {
  satisfaction_score: number | null; // 0-5；0 表示未知；越大越好
  emotion_score: number | null; // 0-5；0 表示未知；越大越好
  intent: string | null;
  insight_summary: string | null;
}

// Visitor service status enum
export type VisitorServiceStatus = 'new' | 'queued' | 'assigned_pending' | 'active' | 'closed';

export interface ChannelVisitorExtra {
  id: string;
  platform_id: string;
  platform_type: PlatformType;
  platform_open_id: string;
  name?: string;
  nickname?: string;
  display_nickname?: string; // Display nickname for header
  avatar_url?: string;
  phone_number?: string;
  email?: string;
  company?: string;
  job_title?: string;
  source?: string;
  note?: string;
  custom_attributes?: Record<string, any>;
  created_at?: string;
  updated_at?: string;
  deleted_at?: string | null;
  first_visit_time?: string;
  last_visit_time?: string;
  last_offline_time?: string;
  is_online?: boolean;
  ai_disabled?: boolean; // True means AI is disabled for this visitor
  assigned_staff_id?: string; // ID of the staff member assigned to this visitor
  ai_insights?: ChannelAIInsights | null; // AI insights from backend
  tags?: VisitorTag[];
  recent_activities?: VisitorActivity[];
  system_info?: SystemInfo;
  service_status?: VisitorServiceStatus; // Visitor service status: new, queued, assigned_pending, active, closed
  language?: string; // Visitor's browser language (e.g., 'zh-CN', 'en-US')
  timezone?: string; // Visitor's timezone (e.g., 'Asia/Shanghai', 'America/New_York')
  ip_address?: string; // Visitor's IP address
}

export type ChannelExtra = ChannelVisitorExtra | ChannelStaffExtra | null;

export interface ChannelInfo {
  name: string;
  avatar: string;
  channel_id: string;
  channel_type: number; // 1 personal, 251 customer service
  extra?: ChannelExtra; // metadata from channel info API
}


export interface KnowledgeBaseTag {
  name: string;
  color: string;
}

// Knowledge Base Type - file (default), website, or qa
export type KnowledgeBaseType = 'file' | 'website' | 'qa';

// Crawl job status
export type CrawlJobStatus = 'pending' | 'crawling' | 'processing' | 'completed' | 'failed' | 'cancelled';

// Crawl options for website type
export interface CrawlOptions {
  render_js?: boolean;
  wait_time?: number;
  follow_external_links?: boolean;
  respect_robots_txt?: boolean;
  user_agent?: string;
}

// Crawl progress information
export interface CrawlProgress {
  pages_discovered: number;
  pages_crawled: number;
  pages_processed: number;
  pages_failed: number;
  progress_percent: number;
}

// Website crawl configuration
export interface WebsiteCrawlConfig {
  start_url: string;
  max_pages?: number; // default: 100, max: 10000
  max_depth?: number; // default: 3, max: 10
  include_patterns?: string[];
  exclude_patterns?: string[];
  options?: CrawlOptions;
}

// Website crawl job response
export interface WebsiteCrawlJob {
  id: string;
  collection_id: string;
  start_url: string;
  max_pages: number;
  max_depth: number;
  include_patterns?: string[] | null;
  exclude_patterns?: string[] | null;
  status: CrawlJobStatus;
  progress: CrawlProgress;
  crawl_options?: Record<string, any> | null;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
}

// Website crawl create response
export interface WebsiteCrawlCreateResponse {
  job_id: string;
  status: string;
  start_url: string;
  collection_id: string;
  created_at: string;
  message: string;
}

export interface KnowledgeBaseItem {
  id: string;
  title: string;
  name?: string; // For backward compatibility
  content: string;
  description?: string; // For backward compatibility
  category: string;
  tags: string[] | KnowledgeBaseTag[];
  author: string;
  createdAt: string;
  updatedAt: string;
  lastUpdated?: string; // For backward compatibility
  views: number;
  fileCount?: number; // file count
  status: KnowledgeBaseStatus;
  icon?: string; // For backward compatibility
  iconColor?: string; // For backward compatibility
  // New fields for type support
  type?: KnowledgeBaseType; // 'file' or 'website'
  crawlConfig?: WebsiteCrawlConfig; // Website crawl configuration
  crawlJob?: WebsiteCrawlJob; // Latest crawl job info
}

export type KnowledgeBaseStatus = 'published' | 'draft' | 'archived';

// Knowledge Base for detail view (compatible with KnowledgeBaseItem and API)
export interface KnowledgeBase {
  id: string;
  name: string;
  title?: string; // For compatibility with KnowledgeBaseItem
  description?: string;
  content?: string; // For compatibility with KnowledgeBaseItem
  category?: string;
  status: 'active' | 'inactive' | 'processing';
  createdAt: string;
  updatedAt: string;
  author?: string;
  tags?: string[] | KnowledgeBaseTag[];
  icon?: string; // Lucide icon name for visual identification
  // API-specific fields
  display_name?: string;
  collection_metadata?: Record<string, any>;
  created_at?: string;
  updated_at?: string;
  deleted_at?: string | null;
  // New fields for type support
  type?: KnowledgeBaseType;
  crawlConfig?: WebsiteCrawlConfig;
  crawlJob?: WebsiteCrawlJob;
}

// Knowledge Base File/Document (compatible with API FileResponse)
export interface KnowledgeFile {
  id: string;
  name: string;
  size: string; // Formatted size like "2.5 MB"
  sizeBytes: number; // Raw bytes for sorting
  type: string; // File type like 'pdf', 'doc', 'txt'
  uploadDate: string;
  status: string; // Display status like "已处理", "处理中", "错误"
  statusType: 'success' | 'processing' | 'error';
  knowledgeBaseId: string;
  url?: string;
  // API-specific fields
  collection_id?: string | null;
  original_filename?: string;
  file_size?: number;
  content_type?: string;
  document_count?: number;
  total_tokens?: number;
  language?: string | null;
  description?: string | null;
  tags?: string[] | null;
  uploaded_by?: string | null;
  created_at?: string;
  updated_at?: string;
}

// Navigation and UI types
export interface NavigationItem {
  id: string;
  title: string;
  icon: string;
  path: string;
  badge?: number;
  children?: NavigationItem[];
}

export interface ButtonVariant {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger' | 'icon';
  size?: 'sm' | 'md' | 'lg';
}

// Event handler types
export type PlatformSelectHandler = (platform: Platform) => void;
export type PlatformUpdateHandler = (platform: Platform) => void;
export type PlatformToggleHandler = (platform: Platform) => void;
export type AgentActionHandler = (actionType: string, agent: Agent) => void;
export type ChatSelectHandler = (chat: Chat) => void;
export type MessageSendHandler = (content: string) => void;

// Component prop types
export interface BaseComponentProps {
  className?: string;
  children?: React.ReactNode;
}

export interface IconProps extends BaseComponentProps {
  name: string;
  size?: number;
}

export interface ButtonProps extends BaseComponentProps, ButtonVariant {
  onClick?: () => void;
  disabled?: boolean;
  icon?: string;
  type?: 'button' | 'submit' | 'reset';
  title?: string;
}

export interface ToggleProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
  'aria-label'?: string;
}

// API response types
export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
  message?: string;
}

// Configuration types
export interface AppConfig {
  apiUrl: string;
  wsUrl: string;
  version: string;
  environment: 'development' | 'staging' | 'production';
}

// Error types
export interface AppError {
  code: string;
  message: string;
  details?: any;
}

// WuKongIM API Types
export interface WuKongIMMessageHeader {
  no_persist: number; // Whether to persist message (0=persist, 1=no persist)
  red_dot: number; // Whether to show red dot (0=no, 1=yes)
  sync_once: number; // Whether write diffusion (0=no, 1=yes)
}

export interface WuKongIMMessagePayload {
  content: string; // Message content
  type: number; // Message type
}

export interface WuKongIMMessage {
  header: WuKongIMMessageHeader;
  setting: number; // Message settings (uint8)
  // Use string to avoid JS int64 precision loss; prefer message_id_str from API if available
  message_id_str?: string; // String representation provided by backend (preferred)
  client_msg_no: string; // Client message number (UUID)
  message_seq: number; // Message sequence number
  from_uid: string; // Sender user ID
  channel_id: string; // Channel ID
  channel_type: number; // Channel type
  timestamp: number; // Message timestamp
  payload: WuKongIMMessagePayload | string; // Message payload (new object format or legacy string format)
  end?: number | null; // Stream end flag (0=not ended, 1=ended)
  end_reason?: number | null; // Stream end reason code
  stream_data?: string | null; // Decoded stream data (base64 decoded) - prioritized over payload content
  error?: string | null; // Error message from stream end event or API response
}

export interface WuKongIMConversation {
  channel_id: string; // Channel ID
  channel_type: number; // Channel type (1=personal, 2=group, 3=customer_service)
  unread: number; // Unread message count
  timestamp: number; // Timestamp (10-digit seconds)
  last_msg_seq: number; // Last message sequence number
  last_client_msg_no: string; // Last client message number
  version: number; // Data version number
  recents: WuKongIMMessage[]; // Recent messages
}

export interface WuKongIMConversationSyncRequest {
  version: number; // Client's max conversation version (0 if no local data)
  last_msg_seqs?: string | null; // Last message sequences string (format: channelID:channelType:last_msg_seq|...)
  msg_count?: number; // Max message count per conversation (default: 20)
}

export interface WuKongIMConversationSyncResponse {
  conversations: WuKongIMConversation[]; // List of conversations
  channels?: ChannelInfo[]; // Optional channel info for each conversation (returned by /conversations/my, /waiting, /all)
}

// Pagination metadata for paginated responses
export interface PaginationMetadata {
  total: number; // Total number of items
  limit: number; // Number of items per page
  offset: number; // Number of items skipped
  has_next: boolean; // Whether there are more items
  has_prev: boolean; // Whether there are previous items
}

// Paginated conversation response (for /conversations/waiting and /conversations/all)
export interface WuKongIMConversationPaginatedResponse extends WuKongIMConversationSyncResponse {
  pagination: PaginationMetadata;
}

// Historical Messages Sync Types (aligned with WuKongIM /channel/messagesync)
export interface WuKongIMMessageSyncRequest {
  login_uid: string; // Current logged-in user UID
  channel_id: string; // Channel ID to sync messages for
  channel_type: number; // Channel type (1=personal, 2=group, 3=customer_service)
  start_message_seq?: number; // Start message sequence (inclusive). 0 with end=0 loads latest
  end_message_seq?: number; // End message sequence (exclusive). 0 means unbounded
  limit?: number; // Maximum number of messages to return (default: 50)
  pull_mode?: 0 | 1; // 0=downward (older), 1=upward (newer)
}

export interface WuKongIMMessageSyncResponse {
  messages: WuKongIMMessage[]; // List of historical messages
  more: boolean; // Whether there are more messages available
  next_start_seq?: number; // Next sequence number for pagination (earliest seq to continue)
  total_count?: number; // Total message count in channel (optional)
}

// Enhanced message with additional metadata for UI
export interface WuKongIMEnhancedMessage extends WuKongIMMessage {
  sender_name?: string; // Sender display name
  sender_avatar?: string; // Sender avatar URL
  is_read?: boolean; // Whether message has been read
  reply_to?: string; // Message ID this is replying to (optional)
}

// Authentication types
export interface LoginFormData {
  email: string;
  password: string;
  rememberMe: boolean;
}

export interface RegisterFormData {
  email: string;
  password: string;
  passwordConfirmation: string;
}

export interface AuthValidationErrors {
  email?: string;
  password?: string;
  passwordConfirmation?: string;
  general?: string;
}

// Utility types
export type Optional<T, K extends keyof T> = Omit<T, K> & Partial<Pick<T, K>>;
export type RequiredFields<T, K extends keyof T> = T & Required<Pick<T, K>>;
export type DeepPartial<T> = {
  [P in keyof T]?: T[P] extends object ? DeepPartial<T[P]> : T[P];
};


// Search API types (GET /v1/search)
export type SearchScope = 'all' | 'visitors' | 'messages';

export interface SearchPagination {
  page: number;
  page_size: number;
  total: number;
  has_next: boolean;
  has_prev: boolean;
}

export interface MessageSearchResult {
  message_id: number | null;
  client_msg_no: string | null;
  message_seq: number | null;
  from_uid: string | null;
  channel_id: string | null;
  channel_type: number | null;
  timestamp: number | null;
  payload: Record<string, any>;
  stream_data: string | null;
  topic: string | null;
  preview_text: string | null;
  message_id_str: string; // String representation of message_id (required)
}

export interface VisitorBasicResponse {
  id: string; // UUID
  name: string | null;
  nickname: string | null;
  avatar_url: string | null;
  platform_open_id: string; // Required
  platform_id: string; // UUID, Required
  platform_type: PlatformType | null;
  ai_disabled: boolean | null;
  is_online: boolean; // Required
  created_at: string; // date-time, Required
  updated_at: string; // date-time, Required
}

export interface UnifiedSearchResponse {
  query: string;
  scope: SearchScope;
  visitors: VisitorBasicResponse[];
  messages: MessageSearchResult[];
  visitor_count: number;
  message_count: number;
  visitor_pagination: SearchPagination | null;
  message_pagination: SearchPagination | null;
}

// UI Widget types
export * from './ui-widget';
