/**
 * AI Providers API Service
 * Implements REST API calls for AI Providers based on docs/api.json
 */

import BaseApiService from './base/BaseApiService';
import type { PaginationMetadata } from '@/types';

// Local type copies to avoid circular imports
export type ProviderKind = 'openai' | 'azure' | 'qwen' | 'moonshot' | 'deepseek' | 'baichuan' | 'ollama' | 'custom';
export interface ProviderParams {
  azure?: { deployment?: string; resource?: string; apiVersion?: string };
  [key: string]: any;
}

// Backend DTOs (from docs/api.json)
export interface AIProviderCreateDTO {
  provider: string;
  name: string;
  api_base_url?: string | null;
  available_models?: string[] | null;
  default_model?: string | null;
  config?: Record<string, any> | null;
  is_active?: boolean;
  api_key: string;
}

export interface AIProviderUpdateDTO {
  provider?: string | null;
  name?: string | null;
  api_key?: string | null; // only include when changing
  api_base_url?: string | null;
  available_models?: string[] | null;
  default_model?: string | null;
  config?: Record<string, any> | null;
  is_active?: boolean | null;
}

export interface AIProviderResponseDTO {
  id: string;
  project_id: string;
  provider: string;
  name: string;
  api_base_url?: string | null;
  available_models?: string[];
  default_model?: string | null;
  config?: Record<string, any> | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  deleted_at?: string | null;
  has_api_key: boolean;
  api_key_masked?: string | null;
  store_resource_id?: string | null;
  is_from_store?: boolean;
}

export interface AIProviderListResponseDTO {
  data: AIProviderResponseDTO[];
  pagination: PaginationMetadata;
}

// Models list (minimal fields used)
export interface AIModelResponseDTO {
  id: string; // model UUID (not used for Tag list)
  provider: string;
  model_id: string; // e.g., gpt-4o
  model_name: string; // display name
}
export interface AIModelListResponseDTO {
  data: AIModelResponseDTO[];
  pagination: PaginationMetadata;
}

// POST /v1/ai/models request body (based on docs/api.json ModelListRequest)
export interface ModelListRequestDTO {
  provider: string; // Required: provider type (openai, anthropic, dashscope, azure, etc.)
  api_key?: string | null; // Optional: API key for the provider
  api_base_url?: string | null; // Optional: Custom API base URL
  config?: Record<string, any> | null; // Optional: Additional configuration
}

// POST /v1/ai/models response body (based on docs/api.json ModelListResponse)
export interface ModelInfoDTO {
  id: string; // Model identifier (required)
  name?: string | null; // Model display name
  owned_by?: string | null; // Model owner/provider
  model_type?: string | null; // chat or embedding
  context_length?: number | null; // Maximum context length
  created?: number | null; // Creation timestamp
}

export interface ModelListResponseDTO {
  provider: string; // Provider type
  models?: ModelInfoDTO[]; // List of available models
  is_fallback?: boolean; // True if using fallback default models
}

export interface AIModelWithProviderDTO {
  id: string;
  model_id: string;
  model_name: string;
  model_type: string;
  provider_id: string;
  provider_name: string;
  provider_kind: string;
  description?: string | null;
  context_window?: number | null;
  is_active: boolean;
}

export interface AIModelWithProviderListResponseDTO {
  data: AIModelWithProviderDTO[];
  pagination: PaginationMetadata;
}

export class AIProvidersApiService extends BaseApiService {
  protected readonly apiVersion = 'v1';
  protected readonly endpoints = {
    PROVIDERS: `/${this.apiVersion}/ai/providers`,
    PROVIDER_BY_ID: (id: string) => `/${this.apiVersion}/ai/providers/${id}`,
    PROVIDER_ENABLE: (id: string) => `/${this.apiVersion}/ai/providers/${id}/enable`,
    PROVIDER_DISABLE: (id: string) => `/${this.apiVersion}/ai/providers/${id}/disable`,
    PROVIDER_TEST: (id: string) => `/${this.apiVersion}/ai/providers/${id}/test`,
    PROVIDER_REMOTE_MODELS: (id: string) => `/${this.apiVersion}/ai/providers/${id}/remote-models`,
    MODELS: `/${this.apiVersion}/ai/models`,
    PROJECT_MODELS: `/${this.apiVersion}/ai-models`,
  } as const;

  // List models for current project with provider info
  async listProjectModels(params?: { 
    model_type?: 'chat' | 'embedding' | null; 
    is_active?: boolean; 
    limit?: number; 
    offset?: number 
  }): Promise<AIModelWithProviderListResponseDTO> {
    return this.get<AIModelWithProviderListResponseDTO>(this.endpoints.PROJECT_MODELS, params as any);
  }

  // List providers
  async listProviders(params?: { limit?: number; offset?: number; search?: string; provider?: string | null; is_active?: boolean | null; model_type?: 'chat' | 'embedding' | null }): Promise<AIProviderListResponseDTO> {
    return this.get<AIProviderListResponseDTO>(this.endpoints.PROVIDERS, params as any);
  }

  // Create provider
  async createProvider(payload: AIProviderCreateDTO): Promise<AIProviderResponseDTO> {
    return this.post<AIProviderResponseDTO>(this.endpoints.PROVIDERS, payload);
  }

  // Update provider
  async updateProvider(id: string, payload: AIProviderUpdateDTO): Promise<AIProviderResponseDTO> {
    return this.patch<AIProviderResponseDTO>(this.endpoints.PROVIDER_BY_ID(id), payload);
  }

  // Delete provider
  async deleteProvider(id: string): Promise<void> {
    await this.delete<void>(this.endpoints.PROVIDER_BY_ID(id));
  }

  // Enable/Disable (optional helpers)
  async enableProvider(id: string): Promise<AIProviderResponseDTO> {
    return this.post<AIProviderResponseDTO>(this.endpoints.PROVIDER_ENABLE(id));
  }
  async disableProvider(id: string): Promise<AIProviderResponseDTO> {
    return this.post<AIProviderResponseDTO>(this.endpoints.PROVIDER_DISABLE(id));
  }

  // Test connection
  async testProvider(id: string): Promise<{ ok?: boolean; success?: boolean; message?: string; [k: string]: any }> {
    return this.post(this.endpoints.PROVIDER_TEST(id));
  }

  // Get remote models using stored credentials
  async getRemoteModels(id: string): Promise<ModelListResponseDTO> {
    return this.get<ModelListResponseDTO>(this.endpoints.PROVIDER_REMOTE_MODELS(id));
  }

  // List models - GET (old paginated endpoint, kept for backward compatibility if needed)
  async listModelsLegacy(params?: { provider?: string | null; limit?: number; offset?: number; search?: string }): Promise<AIModelListResponseDTO> {
    return this.get<AIModelListResponseDTO>(this.endpoints.MODELS, params as any);
  }

  /**
   * Fetch available models from a provider API.
   * POST /v1/ai/models
   * 
   * This endpoint calls the provider's API directly to get the current list
   * of available models. If api_key is not provided, returns default/common
   * models for the specified provider.
   * 
   * @param request - ModelListRequest with provider info
   * @param modelType - Optional filter by model type (chat or embedding)
   */
  async listModels(request: ModelListRequestDTO, modelType?: 'chat' | 'embedding'): Promise<ModelListResponseDTO> {
    let url = "";
    url = this.endpoints.MODELS;
    if (modelType) {
      url = `${url}?model_type=${modelType}`;
    }
    return this.post<ModelListResponseDTO>(url, request);
  }

  // Mapping helpers for provider key ↔ kind
  static kindToProviderKey(kind: ProviderKind): string {
    switch (kind) {
      case 'azure': return 'azure_openai';
      case 'qwen': return 'dashscope';
      default: return kind; // openai, moonshot, deepseek, baichuan, ollama, custom
    }
  }
  static providerKeyToKind(key: string): ProviderKind {
    switch (key) {
      case 'azure_openai': return 'azure';
      case 'dashscope': return 'qwen';
      case 'openai': return 'openai';
      case 'moonshot': return 'moonshot';
      case 'deepseek': return 'deepseek';
      case 'baichuan': return 'baichuan';
      case 'ollama': return 'ollama';
      case 'openai_compatible': return 'custom';
      default: return 'custom';
    }
  }

  /**
   * Check if a backend provider key matches a frontend kind.
   */
  static isMatch(key: string, kind: ProviderKind): boolean {
    if (key === 'openai_compatible' && kind === 'custom') return true;
    return this.kindToProviderKey(kind) === key;
  }

  // Build config from params for backend (snake_case where sensible)
  static buildBackendConfig(kind: ProviderKind, params?: ProviderParams): Record<string, any> | undefined {
    if (!params) return undefined;
    if (kind === 'azure') {
      const az = params.azure || {};
      const cfg: Record<string, any> = {};
      if (az.deployment) cfg.deployment = az.deployment;
      if (az.resource) cfg.resource = az.resource;
      if (az.apiVersion) cfg.api_version = az.apiVersion;
      return cfg;
    }
    return { ...params };
  }

  // Extract params (frontend) from backend config
  static extractParams(kind: ProviderKind, config?: Record<string, any> | null): ProviderParams | undefined {
    if (!config) return undefined;
    if (kind === 'azure') {
      const azAny = (config as any).azure || config;
      return {
        azure: {
          deployment: azAny.deployment,
          resource: azAny.resource,
          apiVersion: azAny.apiVersion || azAny.api_version,
        },
      };
    }
    return { ...config } as ProviderParams;
  }
}

export default AIProvidersApiService;

