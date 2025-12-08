/**
 * Staff API Service
 * Handles all staff-related API operations
 */

import apiClient, { StaffResponse, StaffCreateRequest } from './api';

// Staff role type
export type StaffRole = 'user' | 'admin' | 'agent';

// Staff status type
export type StaffStatus = 'online' | 'offline' | 'busy';

// Staff update request type
export interface StaffUpdateRequest {
  nickname?: string | null;
  avatar_url?: string | null;
  role?: StaffRole;
  status?: StaffStatus;
  agent_id?: string | null;
  password?: string;
  description?: string | null;
}

// Pagination metadata
export interface PaginationMetadata {
  total: number;
  limit: number;
  offset: number;
  has_next: boolean;
  has_prev: boolean;
}

// Staff list response
export interface StaffListResponse {
  data: StaffResponse[];
  pagination: PaginationMetadata;
}

// Query parameters for listing staff
export interface StaffQueryParams {
  role?: StaffRole;
  status?: StaffStatus;
  limit?: number;
  offset?: number;
}

// Visitor Assignment Rule Response
export interface VisitorAssignmentRuleResponse {
  id: string;
  project_id: string;
  ai_provider_id: string | null;
  model: string | null;
  prompt: string | null;
  effective_prompt: string;
  llm_assignment_enabled: boolean;
  timezone: string;
  service_weekdays: number[];
  service_start_time: string;
  service_end_time: string;
  max_concurrent_chats: number;
  auto_close_hours: number;
  created_at: string;
  updated_at: string;
}

// Visitor Assignment Rule Update Request
export interface VisitorAssignmentRuleUpdate {
  ai_provider_id?: string | null;
  model?: string | null;
  prompt?: string | null;
  llm_assignment_enabled?: boolean | null;
  timezone?: string | null;
  service_weekdays?: number[] | null;
  service_start_time?: string | null;
  service_end_time?: string | null;
  max_concurrent_chats?: number | null;
  auto_close_hours?: number | null;
}

/**
 * Staff API methods
 */
export const staffApi = {
  /**
   * List staff members with optional filtering
   */
  async listStaff(params?: StaffQueryParams): Promise<StaffListResponse> {
    const queryParams = new URLSearchParams();
    
    if (params?.role) {
      queryParams.append('role', params.role);
    }
    if (params?.status) {
      queryParams.append('status', params.status);
    }
    if (params?.limit !== undefined) {
      queryParams.append('limit', params.limit.toString());
    }
    if (params?.offset !== undefined) {
      queryParams.append('offset', params.offset.toString());
    }
    
    const queryString = queryParams.toString();
    const endpoint = `/v1/staff${queryString ? `?${queryString}` : ''}`;
    
    return apiClient.get<StaffListResponse>(endpoint);
  },

  /**
   * Get a single staff member by ID
   */
  async getStaff(staffId: string): Promise<StaffResponse> {
    return apiClient.get<StaffResponse>(`/v1/staff/${staffId}`);
  },

  /**
   * Create a new staff member
   */
  async createStaff(data: StaffCreateRequest): Promise<StaffResponse> {
    return apiClient.post<StaffResponse>('/v1/staff', data);
  },

  /**
   * Update a staff member
   */
  async updateStaff(staffId: string, data: StaffUpdateRequest): Promise<StaffResponse> {
    return apiClient.patch<StaffResponse>(`/v1/staff/${staffId}`, data);
  },

  /**
   * Delete a staff member (soft delete)
   */
  async deleteStaff(staffId: string): Promise<void> {
    return apiClient.delete<void>(`/v1/staff/${staffId}`);
  },

  /**
   * Get online status of staff members from WuKongIM
   */
  async getOnlineStatus(staffIds: string[]): Promise<Record<string, boolean>> {
    const response = await apiClient.post<{ online_statuses: Record<string, boolean> }>(
      '/v1/staff/wukongim/online-status',
      { staff_ids: staffIds }
    );
    return response.online_statuses;
  },

  /**
   * Get visitor assignment rule for current project
   */
  async getAssignmentRule(): Promise<VisitorAssignmentRuleResponse> {
    return apiClient.get<VisitorAssignmentRuleResponse>('/v1/visitor-assignment-rules');
  },

  /**
   * Update or create visitor assignment rule for current project
   */
  async updateAssignmentRule(data: VisitorAssignmentRuleUpdate): Promise<VisitorAssignmentRuleResponse> {
    return apiClient.put<VisitorAssignmentRuleResponse>('/v1/visitor-assignment-rules', data);
  },

  /**
   * Get default prompt for visitor assignment
   */
  async getDefaultAssignmentPrompt(): Promise<{ default_prompt: string }> {
    return apiClient.get<{ default_prompt: string }>('/v1/visitor-assignment-rules/default-prompt');
  },
};

export default staffApi;

