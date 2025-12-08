/**
 * Setup API Service
 * Handles system installation and initialization
 */

import { BaseApiService } from './base/BaseApiService';

// Request/Response Types based on OpenAPI specification

/**
 * Request schema for creating the first admin account
 */
export interface CreateAdminRequest {
  username: string;
  password: string;
  nickname?: string | null;
  project_name?: string;
}

/**
 * Response schema for admin creation
 */
export interface CreateAdminResponse {
  id: string;
  username: string;
  nickname: string | null;
  project_id: string;
  project_name: string;
  created_at: string;
}

/**
 * Request schema for configuring LLM provider
 */
export interface ConfigureLLMRequest {
  provider: string;
  name: string;
  api_key: string;
  api_base_url?: string | null;
  available_models?: string[];
  default_model?: string | null;
  is_active?: boolean;
  config?: Record<string, any> | null;
}

/**
 * Response schema for LLM configuration
 */
export interface ConfigureLLMResponse {
  id: string;
  provider: string;
  name: string;
  default_model: string | null;
  is_active: boolean;
  project_id: string;
  created_at: string;
}

/**
 * Individual check result for setup verification
 */
export interface SetupCheckResult {
  passed: boolean;
  message: string;
}

/**
 * Response schema for setup verification
 */
export interface VerifySetupResponse {
  is_valid: boolean;
  checks: Record<string, SetupCheckResult>;
  errors?: string[];
  warnings?: string[];
}

/**
 * Response schema for setup status check
 */
export interface SetupStatusResponse {
  is_installed: boolean;
  has_admin: boolean;
  has_user_staff: boolean;
  has_llm_config: boolean;
  setup_completed_at: string | null;
}

/**
 * Response schema for skipping LLM configuration
 */
export interface SkipLLMResponse {
  message: string;
  skipped: boolean;
}

/**
 * Request schema for creating a single staff member in batch
 */
export interface SetupStaffItem {
  username: string;
  password: string;
  name?: string | null;
}

/**
 * Request schema for batch creating staff members
 */
export interface CreateStaffBatchRequest {
  staff_list: SetupStaffItem[];
}

/**
 * Response schema for batch staff creation
 */
export interface CreateStaffBatchResponse {
  created_count: number;
  staff_ids: string[];
}

/**
 * Setup API Service Class
 */
class SetupApiService extends BaseApiService {
  protected readonly endpoints = {
    status: '/v1/setup/status',
    admin: '/v1/setup/admin',
    staff: '/v1/setup/staff',
    llmConfig: '/v1/setup/llm-config',
    skipLLM: '/v1/setup/skip-llm',
    verify: '/v1/setup/verify',
  } as const;

  protected readonly apiVersion = 'v1';

  /**
   * Check if system is already installed
   * GET /v1/setup/status
   */
  async getStatus(): Promise<SetupStatusResponse> {
    return this.get<SetupStatusResponse>(this.endpoints.status);
  }

  /**
   * Create admin account
   * POST /v1/setup/admin
   */
  async createAdmin(data: CreateAdminRequest): Promise<CreateAdminResponse> {
    return this.post<CreateAdminResponse>(this.endpoints.admin, data);
  }

  /**
   * Batch create staff members
   * POST /v1/setup/staff
   */
  async createStaffBatch(data: CreateStaffBatchRequest): Promise<CreateStaffBatchResponse> {
    return this.post<CreateStaffBatchResponse>(this.endpoints.staff, data);
  }

  /**
   * Configure LLM provider
   * POST /v1/setup/llm-config
   */
  async configureLLM(data: ConfigureLLMRequest): Promise<ConfigureLLMResponse> {
    return this.post<ConfigureLLMResponse>(this.endpoints.llmConfig, data);
  }

  /**
   * Skip LLM configuration
   * POST /v1/setup/skip-llm
   */
  async skipLLM(): Promise<SkipLLMResponse> {
    return this.post<SkipLLMResponse>(this.endpoints.skipLLM, {});
  }

  /**
   * Verify installation
   * GET /v1/setup/verify
   */
  async verify(): Promise<VerifySetupResponse> {
    return this.get<VerifySetupResponse>(this.endpoints.verify);
  }
}

export const setupApiService = new SetupApiService();

