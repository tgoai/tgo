/**
 * Base API Service
 * Provides common functionality for all API services
 */

import { apiClient, APIError } from '../api';

// Common query parameters interface
export interface BaseQueryParams {
  page?: number;
  limit?: number;
  offset?: number;
  search?: string;
  category?: string;
  status?: string | null;
  tags?: string[];
  // Agent-specific parameters (allowing null for API compatibility)
  model?: string | null;
  is_default?: boolean | null;
  team_id?: string | null;
  // Model-specific parameters (allowing null for API compatibility)
  provider?: string | null;
  type?: string | null;
  model_type?: string | null;
}

// Common response metadata interface
export interface BaseResponseMeta {
  page: number;
  limit: number;
  total: number;
  total_pages: number;
  has_next: boolean;
  has_prev: boolean;
}

// Common list response interface
export interface BaseListResponse<T> {
  data: T[];
  meta: BaseResponseMeta;
}

/**
 * Base API Service Class
 * Provides common functionality for all API services
 */
export abstract class BaseApiService {
  protected abstract readonly endpoints: Record<string, string | ((...args: any[]) => string)>;
  protected abstract readonly apiVersion: string;

  /**
   * Handle API errors consistently across all services
   */
  protected handleApiError(error: unknown): string {
    if (error instanceof APIError) {
      return error.getUserMessage();
    }
    
    if (error instanceof Error) {
      const message = error.message.toLowerCase();
      
      // Network errors
      if (message.includes('network') || message.includes('fetch')) {
        return '网络连接失败，请检查网络连接后重试';
      }
      
      // Timeout errors
      if (message.includes('timeout')) {
        return '请求超时，请稍后重试';
      }
      
      // HTTP status errors
      if (message.includes('400')) return '请求参数错误，请检查输入内容';
      if (message.includes('401')) return '身份验证失败，请重新登录';
      if (message.includes('403')) return '权限不足，无法执行此操作';
      if (message.includes('404')) return '请求的资源不存在';
      if (message.includes('409')) return '资源冲突，请刷新页面后重试';
      if (message.includes('413')) return '文件过大，请选择较小的文件';
      if (message.includes('415')) return '不支持的文件类型';
      if (message.includes('500')) return '服务器错误，请稍后重试';
      
      return error.message;
    }
    
    return 'An unexpected error occurred';
  }

  /**
   * Check if user is authenticated
   */
  protected isAuthenticated(): boolean {
    const token = apiClient.getToken();
    return token !== null && token.trim() !== '';
  }

  /**
   * Build query string from parameters
   */
  protected buildQueryString(params?: BaseQueryParams): string {
    if (!params) return '';

    const queryParams = new URLSearchParams();

    if (params.page) queryParams.append('page', params.page.toString());
    if (params.limit) queryParams.append('limit', params.limit.toString());
    if (params.offset !== undefined) queryParams.append('offset', params.offset.toString());
    if (params.search) queryParams.append('search', params.search);
    if (params.category) queryParams.append('category', params.category);
    if (params.status !== undefined && params.status !== null) {
      queryParams.append('status', params.status);
    }
    if (params.tags?.length) {
      params.tags.forEach(tag => queryParams.append('tags', tag));
    }

    // Agent-specific parameters
    if (params.model !== undefined && params.model !== null) {
      queryParams.append('model', params.model);
    }
    if (params.is_default !== undefined && params.is_default !== null) {
      queryParams.append('is_default', params.is_default.toString());
    }
    if (params.team_id !== undefined) {
      if (params.team_id === null) {
        queryParams.append('team_id', 'null');
      } else {
        queryParams.append('team_id', params.team_id);
      }
    }

    // Model-specific parameters
    if (params.provider !== undefined && params.provider !== null) {
      queryParams.append('provider', params.provider);
    }
    if (params.type !== undefined && params.type !== null) {
      queryParams.append('type', params.type);
    }
    if (params.model_type !== undefined && params.model_type !== null) {
      queryParams.append('model_type', params.model_type);
    }

    return queryParams.toString();
  }

  /**
   * Build URL with query parameters
   */
  protected buildUrl(endpoint: string, params?: BaseQueryParams): string {
    const queryString = this.buildQueryString(params);
    return queryString ? `${endpoint}?${queryString}` : endpoint;
  }

  /**
   * Generic GET request with error handling
   */
  protected async get<T>(endpoint: string, params?: BaseQueryParams): Promise<T> {
    try {
      const url = this.buildUrl(endpoint, params);
      return await apiClient.get<T>(url);
    } catch (error) {
      console.error(`GET ${endpoint} failed:`, error);
      throw new Error(this.handleApiError(error));
    }
  }

  /**
   * Generic POST request with error handling
   */
  protected async post<T>(endpoint: string, data?: any): Promise<T> {
    try {
      return await apiClient.post<T>(endpoint, data);
    } catch (error) {
      console.error(`POST ${endpoint} failed:`, error);
      throw new Error(this.handleApiError(error));
    }
  }

  /**
   * Generic PUT request with error handling
   */
  protected async put<T>(endpoint: string, data: any): Promise<T> {
    try {
      return await apiClient.put<T>(endpoint, data);
    } catch (error) {
      console.error(`PUT ${endpoint} failed:`, error);
      throw new Error(this.handleApiError(error));
    }
  }

  /**
   * Generic PATCH request with error handling
   */
  protected async patch<T>(endpoint: string, data: any): Promise<T> {
    try {
      return await apiClient.patch<T>(endpoint, data);
    } catch (error) {
      console.error(`PATCH ${endpoint} failed:`, error);
      throw new Error(this.handleApiError(error));
    }
  }

  /**
   * Generic DELETE request with error handling
   */
  protected async delete<T>(endpoint: string): Promise<T> {
    try {
      return await apiClient.delete<T>(endpoint);
    } catch (error) {
      console.error(`DELETE ${endpoint} failed:`, error);
      throw new Error(this.handleApiError(error));
    }
  }

  /**
   * Get list with pagination
   */
  protected async getList<T>(
    baseEndpoint: string, 
    params?: BaseQueryParams
  ): Promise<BaseListResponse<T>> {
    return this.get<BaseListResponse<T>>(baseEndpoint, params);
  }

  /**
   * Get single item by ID
   */
  protected async getById<T>(baseEndpoint: string | ((id: string) => string), id: string): Promise<T> {
    const endpoint = typeof baseEndpoint === 'function'
      ? baseEndpoint(id)
      : `${baseEndpoint}/${id}`;
    return this.get<T>(endpoint);
  }

  /**
   * Search items with filters
   */
  protected async search<T>(
    baseEndpoint: string,
    query: string,
    filters?: Omit<BaseQueryParams, 'search'>
  ): Promise<BaseListResponse<T>> {
    return this.getList<T>(baseEndpoint, { ...filters, search: query });
  }

  /**
   * Get items by category
   */
  protected async getByCategory<T>(
    baseEndpoint: string,
    category: string,
    params?: Omit<BaseQueryParams, 'category'>
  ): Promise<BaseListResponse<T>> {
    return this.getList<T>(baseEndpoint, { ...params, category });
  }

  /**
   * Get items by status
   */
  protected async getByStatus<T>(
    baseEndpoint: string,
    status: string,
    params?: Omit<BaseQueryParams, 'status'>
  ): Promise<BaseListResponse<T>> {
    return this.getList<T>(baseEndpoint, { ...params, status });
  }

  /**
   * Get paginated items
   */
  protected async getPage<T>(
    baseEndpoint: string,
    page: number,
    pageSize: number = 20,
    filters?: Omit<BaseQueryParams, 'limit' | 'page'>
  ): Promise<BaseListResponse<T>> {
    return this.getList<T>(baseEndpoint, {
      ...filters,
      page,
      limit: pageSize,
    });
  }
}

export default BaseApiService;
