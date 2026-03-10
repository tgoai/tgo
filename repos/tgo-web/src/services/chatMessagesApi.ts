import { BaseApiService } from './base/BaseApiService';

// Request type based on OpenAPI docs#/components/schemas/StaffSendPlatformMessageRequest
export interface StaffSendPlatformMessageRequest {
  channel_id: string;
  channel_type: number; // WuKongIM channel type, customer service chat uses 251
  payload: Record<string, any>; // Platform Service message payload
  client_msg_no?: string | null; // Optional idempotency key
}

// Response type is not specified in OpenAPI schema (empty). Use unknown for now.
export type StaffSendPlatformMessageResponse = unknown;

// Request type for staff-to-team/agent chat based on OpenAPI docs
// Either team_id or agent_id must be provided (exactly one)
export interface StaffTeamChatRequest {
  team_id?: string | null; // AI Team ID to chat with (UUID format)
  agent_id?: string | null; // AI Agent ID to chat with (UUID format)
  message: string; // Message content to send
  system_message?: string | null; // Optional system message/prompt
  expected_output?: string | null; // Optional expected output format
  timeout_seconds?: number | null; // Timeout in seconds (1-600, default 120)
}

// Response type for staff-to-team/agent chat
export interface StaffTeamChatResponse {
  success: boolean; // Whether the chat completed successfully
  message: string; // Status message
  client_msg_no: string; // Message correlation ID for tracking
}

class ChatMessagesApiService extends BaseApiService {
  protected readonly apiVersion = 'v1';
  protected readonly endpoints = {
    sendPlatformMessage: '/v1/chat/messages/send',
    teamChat: '/v1/chat/team',
    clearMemory: '/v1/chat/memory',
  } as const;

  /**
   * Forward a staff-authenticated outbound message to the Platform Service.
   * This must be called before sending via WebSocket for non-website platforms.
   */
  async staffSendPlatformMessage(
    data: StaffSendPlatformMessageRequest
  ): Promise<StaffSendPlatformMessageResponse> {
    return this.post<StaffSendPlatformMessageResponse>(this.endpoints.sendPlatformMessage, data);
  }

  /**
   * Staff chat with AI team or agent.
   * This endpoint allows authenticated staff members to chat with AI teams or agents.
   * Either team_id or agent_id must be provided (exactly one).
   * The AI response is delivered via WuKongIM to the client.
   */
  async staffTeamChat(
    data: StaffTeamChatRequest
  ): Promise<StaffTeamChatResponse> {
    return this.post<StaffTeamChatResponse>(this.endpoints.teamChat, data);
  }

  /**
   * Clear AI conversational memory for a specific channel.
   */
  async clearChatMemory(params: {
    channel_id: string;
    channel_type: number;
  }): Promise<{ success: boolean; message: string }> {
    const query = new URLSearchParams({
      channel_id: params.channel_id,
      channel_type: params.channel_type.toString(),
    }).toString();
    return this.delete<{ success: boolean; message: string }>(`${this.endpoints.clearMemory}?${query}`);
  }
}

export const chatMessagesApiService = new ChatMessagesApiService();
export default chatMessagesApiService;
