import { BaseApiService } from './base/BaseApiService';
import type { PlatformType, PaginationMetadata } from '@/types';
import { apiClient } from './api';


export interface PlatformTypeDefinitionResponse {
  id: string; // uuid
  type: string; // e.g., wechat, website, email, phone, custom, tiktok, etc.
  name: string; // human-readable
  display_name?: string; // display name for UI (preferred over name)
  is_supported?: boolean; // whether this platform type is currently supported
  icon?: string | null; // optional SVG markup or identifier
  created_at: string;
  updated_at: string;
}

// OpenAPI: PlatformCreate
export interface PlatformCreateRequest {
  name: string;
  type: PlatformType;
  config?: Record<string, any> | null;
  is_active?: boolean; // default true
}

// OpenAPI: PlatformResponse
export interface PlatformResponse {
  id: string; // uuid
  project_id: string; // uuid
  name: string;
  display_name?: string; // display name for UI (preferred over name)
  type: PlatformType;
  is_supported?: boolean; // whether this platform type is currently supported
  // Some APIs also return api_key at the top level (e.g., website widget)
  api_key?: string | null; // optional API key (top-level)
  config?: Record<string, any> | null;
  is_active: boolean;
  // Read-only fields from API
  callback_url?: string; // public callback URL for this platform
  logo_url?: string | null; // public URL to retrieve the platform logo
  deleted_at?: string | null;
  created_at: string;
  updated_at: string;
}
// OpenAPI: PlatformUpdate (partial)
export interface PlatformUpdateRequest {
  name?: string | null;
  type?: PlatformType | null; // usually immutable; keep for completeness
  config?: Record<string, any> | null;
  is_active?: boolean | null;
}


/**
 * Platforms API Service
 */
class PlatformsApiService extends BaseApiService {
  protected readonly apiVersion = 'v1';

  protected readonly endpoints = {
    TYPES: `/${this.apiVersion}/platforms/types`,
    LIST: `/${this.apiVersion}/platforms`,
    CREATE: `/${this.apiVersion}/platforms`,
    PLATFORM_BY_ID: (id: string) => `/${this.apiVersion}/platforms/${id}`,
    UPDATE: (id: string) => `/${this.apiVersion}/platforms/${id}`,
    REGENERATE_API_KEY: (id: string) => `/${this.apiVersion}/platforms/${id}/regenerate_api_key`,
    DELETE: (id: string) => `/${this.apiVersion}/platforms/${id}`,
    ENABLE: (id: string) => `/${this.apiVersion}/platforms/${id}/enable`,
    DISABLE: (id: string) => `/${this.apiVersion}/platforms/${id}/disable`,
    UPLOAD_LOGO: (id: string) => `/${this.apiVersion}/platforms/${id}/logo`,
  } as const;

  private static typesCache: { data: PlatformTypeDefinitionResponse[]; ts: number } | null = null;
  private static readonly CACHE_TTL_MS = 5 * 60 * 1000; // 5 minutes

  /**
   * List available platform types (with simple in-memory caching)
   */
  async listPlatformTypes(forceRefresh = false): Promise<PlatformTypeDefinitionResponse[]> {
    const now = Date.now();
    if (!forceRefresh && PlatformsApiService.typesCache) {
      const { ts, data } = PlatformsApiService.typesCache;
      if (now - ts < PlatformsApiService.CACHE_TTL_MS) return data;
    }

    const result = await this.get<PlatformTypeDefinitionResponse[]>(this.endpoints.TYPES);
    PlatformsApiService.typesCache = { data: result, ts: Date.now() };
    return result;
  }

  /**
   * Create a platform via API
   */
  async createPlatform(payload: PlatformCreateRequest): Promise<PlatformResponse> {
    return this.post<PlatformResponse>(this.endpoints.CREATE, payload);
  }


  /**
   * List platforms with optional filters and pagination
   */
  async listPlatforms(params?: PlatformListQueryParams): Promise<PlatformListResponse> {
    const qs = new URLSearchParams();
    if (params?.type !== undefined && params?.type !== null) qs.append('type', String(params.type));
    if (params?.limit !== undefined) qs.append('limit', String(params.limit));
    if (params?.offset !== undefined) qs.append('offset', String(params.offset));
    if (params?.is_active !== undefined && params?.is_active !== null) {
      qs.append('is_active', String(params.is_active));
    }

    const endpoint = qs.toString() ? `${this.endpoints.LIST}?${qs.toString()}` : this.endpoints.LIST;
    return this.get<PlatformListResponse>(endpoint);
  }

  /**
   * Update a platform (partial update)
   */
  async updatePlatform(id: string, payload: PlatformUpdateRequest): Promise<PlatformResponse> {
    const endpoint = this.endpoints.UPDATE(id);
    return this.patch<PlatformResponse>(endpoint, payload);
  }
  /**
   * Upload or replace platform logo (multipart/form-data: field 'file')
   */
  async uploadPlatformLogo(id: string, file: File): Promise<PlatformResponse> {
    const endpoint = this.endpoints.UPLOAD_LOGO(id);
    const form = new FormData();
    form.append('file', file);
    // Use apiClient directly for multipart upload
    return apiClient.postFormData<PlatformResponse>(endpoint, form);
  }


  /**
   * Get a platform by ID
   */
  async getPlatformById(id: string): Promise<PlatformResponse> {
    const endpoint = this.endpoints.PLATFORM_BY_ID(id);
    return this.get<PlatformResponse>(endpoint);
  }

  /**
   * Regenerate API key for a platform
   * Note: backend returns only { id, api_key }
   */
  async regenerateApiKey(id: string): Promise<{ id: string; api_key: string }> {
    const endpoint = this.endpoints.REGENERATE_API_KEY(id);
    return this.post<{ id: string; api_key: string }>(endpoint, {});
  }

  /**
   * Delete a platform by ID
   */
  async deletePlatform(id: string): Promise<void> {
    const endpoint = this.endpoints.DELETE(id);
    await this.delete<void>(endpoint);
  }

  async enablePlatform(id: string): Promise<void> {
    const endpoint = this.endpoints.ENABLE(id);
    await this.post<void>(endpoint, {});
  }

  async disablePlatform(id: string): Promise<void> {
    const endpoint = this.endpoints.DISABLE(id);
    await this.post<void>(endpoint, {});
  }
}


export const platformsApiService = new PlatformsApiService();
export default platformsApiService;


export interface PlatformListResponse {
  data: PlatformResponse[];
  pagination: PaginationMetadata;
}

export interface PlatformListQueryParams {
  type?: PlatformType | null;
  is_active?: boolean | null;
  limit?: number;
  offset?: number;
}

