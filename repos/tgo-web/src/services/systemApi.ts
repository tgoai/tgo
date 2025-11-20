/**
 * System API Service
 * Handles system information and status endpoints
 */

import { BaseApiService } from './base/BaseApiService';

/**
 * System Information Response
 * GET /v1/system/info
 */
export interface SystemInfoResponse {
  version: string | null;
  environment: string | null;
  api_version: string | null;
  python_version: string | null;
  build_time: string | null;
  git_commit: string | null;
}

/**
 * System API Service Class
 */
class SystemApiService extends BaseApiService {
  protected readonly endpoints = {
    info: '/v1/system/info',
  } as const;

  protected readonly apiVersion = 'v1';

  /**
   * Get system information
   * GET /v1/system/info
   */
  async getSystemInfo(): Promise<SystemInfoResponse> {
    return this.get<SystemInfoResponse>(this.endpoints.info);
  }
}

export const systemApiService = new SystemApiService();

