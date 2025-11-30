/**
 * Knowledge Base API Service
 * Handles RAG Collections and Files API endpoints
 */

import { apiClient } from './api';
import BaseApiService from './base/BaseApiService';


// Helper function to check if user is authenticated
export const isAuthenticated = (): boolean => {
  const token = apiClient.getToken();
  return token !== null && token.trim() !== '';
};

// Pagination types
export interface PaginationMetadata {
  total: number;
  limit: number;
  offset: number;
  has_next: boolean;
  has_previous: boolean;
}

export interface PaginatedResponse<T> {
  data: T[];
  pagination: PaginationMetadata;
}

// Error handling utility with Chinese messages
export const handleApiError = (error: unknown): string => {
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
    if (message.includes('400')) {
      return '请求参数错误，请检查输入内容';
    }
    if (message.includes('401')) {
      return '身份验证失败，请重新登录';
    }
    if (message.includes('403')) {
      return '权限不足，无法执行此操作';
    }
    if (message.includes('404')) {
      return '请求的资源不存在';
    }
    if (message.includes('409')) {
      return '资源冲突，请刷新页面后重试';
    }
    if (message.includes('413')) {
      return '文件过大，请选择较小的文件';
    }
    if (message.includes('415')) {
      return '不支持的文件类型';
    }
    if (message.includes('429')) {
      return '请求过于频繁，请稍后重试';
    }
    if (message.includes('500')) {
      return '服务器内部错误，请稍后重试';
    }
    if (message.includes('502') || message.includes('503') || message.includes('504')) {
      return '服务暂时不可用，请稍后重试';
    }

    // Return original message if no specific pattern matches
    return error.message;
  }

  return '发生未知错误，请稍后重试';
};

// API Response Types based on OpenAPI specification
export interface CollectionResponse {
  id: string;
  display_name: string;
  description?: string | null;
  collection_type: 'file' | 'website' | 'qa';
  crawl_config?: Record<string, any> | null;
  collection_metadata?: Record<string, any> | null;
  tags?: string[] | null;
  file_count: number;
  created_at: string;
  updated_at: string;
  deleted_at?: string | null;
}

export interface FileResponse {
  id: string;
  collection_id?: string | null;
  original_filename: string;
  file_size: number;
  content_type: string;
  status: 'pending' | 'processing' | 'completed' | 'failed' | 'archived';
  document_count: number;
  total_tokens: number;
  language?: string | null;
  description?: string | null;
  tags?: string[] | null;
  uploaded_by?: string | null;
  created_at: string;
  updated_at: string;
}

export interface CollectionListResponse extends PaginatedResponse<CollectionResponse> {}
export interface FileListResponse extends PaginatedResponse<FileResponse> {}

export interface CollectionCreateRequest {
  display_name: string;
  description?: string;
  collection_metadata?: Record<string, any>;
  tags?: string[];
}

export interface CollectionUpdateRequest {
  display_name?: string;
  description?: string;
  collection_metadata?: Record<string, any>;
  tags?: string[];
}

export interface FileUploadRequest {
  collection_id?: string;
  description?: string;
  tags?: string[];
  language?: string;
}

// Website Crawl Types
export interface CrawlOptionsRequest {
  render_js?: boolean;
  wait_time?: number;
  follow_external_links?: boolean;
  respect_robots_txt?: boolean;
  user_agent?: string;
}

export interface WebsiteCrawlRequest {
  start_url: string;
  max_pages?: number; // default: 100, max: 10000
  max_depth?: number; // default: 3, max: 10
  include_patterns?: string[];
  exclude_patterns?: string[];
  options?: CrawlOptionsRequest;
}

export interface CrawlProgressResponse {
  pages_discovered: number;
  pages_crawled: number;
  pages_processed: number;
  pages_failed: number;
  progress_percent: number;
}

export interface WebsiteCrawlJobResponse {
  id: string;
  collection_id: string;
  start_url: string;
  max_pages: number;
  max_depth: number;
  include_patterns?: string[] | null;
  exclude_patterns?: string[] | null;
  status: 'pending' | 'crawling' | 'processing' | 'completed' | 'failed' | 'cancelled';
  progress: CrawlProgressResponse;
  crawl_options?: Record<string, any> | null;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
}

export interface WebsiteCrawlCreateResponse {
  job_id: string;
  status: string;
  start_url: string;
  collection_id: string;
  created_at: string;
  message: string;
}

export interface WebsiteCrawlJobListResponse extends PaginatedResponse<WebsiteCrawlJobResponse> {}

// Website Page Types
export interface WebsitePageResponse {
  id: string;
  crawl_job_id: string;
  url: string;
  title?: string | null;
  depth: number;
  content_length: number;
  status: 'pending' | 'fetched' | 'extracted' | 'processed' | 'failed';
  http_status_code?: number | null;
  file_id?: string | null;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
}

export interface WebsitePageListResponse extends PaginatedResponse<WebsitePageResponse> {}

// Add Page Types
export interface AddPageRequest {
  url: string;
}

export interface AddPageResponse {
  success: boolean;
  page_id?: string | null;
  message: string;
  status: 'added' | 'exists' | 'crawling';
}

// Crawl Deeper Types
export interface CrawlDeeperRequest {
  max_depth?: number; // 1-10, default 1
  include_patterns?: string[] | null;
  exclude_patterns?: string[] | null;
}

export interface CrawlDeeperResponse {
  success: boolean;
  source_page_id: string;
  pages_added: number;
  pages_skipped: number;
  links_found: number;
  message: string;
  added_urls?: string[] | null;
}

// Website Metadata Types
export interface WebsiteMetadataRequest {
  url: string;
}

export interface WebsiteMetadataResponse {
  url: string;
  title?: string | null;
  description?: string | null;
  favicon?: string | null;
  og_image?: string | null;
  success: boolean;
  error?: string | null;
}

// API Endpoints - Use relative paths since the API client already includes the base URL
const API_VERSION = 'v1';

export const KNOWLEDGE_BASE_ENDPOINTS = {
  // Collections
  COLLECTIONS: `/${API_VERSION}/rag/collections`,
  COLLECTION_BY_ID: (id: string) => `/${API_VERSION}/rag/collections/${id}`,
  COLLECTION_CRAWL_JOBS: (collectionId: string) => `/${API_VERSION}/rag/collections/${collectionId}/crawl-jobs`,
  COLLECTION_PAGES: (collectionId: string) => `/${API_VERSION}/rag/collections/${collectionId}/pages`,

  // Files
  FILES: `/${API_VERSION}/rag/files`,
  FILE_BY_ID: (id: string) => `/${API_VERSION}/rag/files/${id}`,
  FILES_BATCH: `/${API_VERSION}/rag/files/batch`,

  // Website Crawl
  WEBSITE_CRAWL: `/${API_VERSION}/rag/websites/crawl`,
  WEBSITE_CRAWL_JOB: (jobId: string) => `/${API_VERSION}/rag/websites/crawl/${jobId}`,
  WEBSITE_CRAWL_CANCEL: (jobId: string) => `/${API_VERSION}/rag/websites/crawl/${jobId}/cancel`,
  WEBSITE_CRAWL_PAGES: (jobId: string) => `/${API_VERSION}/rag/websites/crawl/${jobId}/pages`,

  // Website Pages
  WEBSITE_PAGE_CRAWL_DEEPER: (pageId: string) => `/${API_VERSION}/rag/websites/pages/${pageId}/crawl-deeper`,

  // Utils
  EXTRACT_WEBSITE_METADATA: `/${API_VERSION}/utils/extract-website-metadata`,
} as const;

/**
 * Knowledge Base API Service Class
 */
export class KnowledgeBaseApiService extends BaseApiService {
  protected readonly apiVersion = 'v1';
  protected readonly endpoints = {
    COLLECTIONS: `/${this.apiVersion}/rag/collections`,
    COLLECTION_BY_ID: (id: string) => `/${this.apiVersion}/rag/collections/${id}`,
    FILES: `/${this.apiVersion}/rag/files`,
    FILE_BY_ID: (id: string) => `/${this.apiVersion}/rag/files/${id}`,
    FILES_BATCH: `/${this.apiVersion}/rag/files/batch`,
  } as const;
  
  // Collections API
  static async getCollections(params?: {
    limit?: number;
    offset?: number;
    search?: string;
    tags?: string[];
  }): Promise<CollectionListResponse> {
    const service = new KnowledgeBaseApiService();
    try {
      const queryParams = new URLSearchParams();
      if (params?.limit) queryParams.append('limit', params.limit.toString());
      if (params?.offset !== undefined) queryParams.append('offset', params.offset.toString());
      if (params?.search) queryParams.append('search', params.search);
      if (params?.tags?.length) queryParams.append('tags', params.tags.join(','));

      const url = queryParams.toString()
        ? `${service.endpoints.COLLECTIONS}?${queryParams.toString()}`
        : service.endpoints.COLLECTIONS;

      return await service.get<CollectionListResponse>(url);
    } catch (error) {
      throw new Error(service['handleApiError'](error));
    }
  }

  static async getCollection(id: string): Promise<CollectionResponse> {
    const service = new KnowledgeBaseApiService();
    try {
      const endpoint = service.endpoints.COLLECTION_BY_ID(id);
      return await service.get<CollectionResponse>(endpoint);
    } catch (error) {
      throw new Error(service['handleApiError'](error));
    }
  }

  static async createCollection(data: CollectionCreateRequest): Promise<CollectionResponse> {
    const service = new KnowledgeBaseApiService();
    try {
      return await service.post<CollectionResponse>(
        service.endpoints.COLLECTIONS,
        data
      );
    } catch (error) {
      throw new Error(service['handleApiError'](error));
    }
  }

  static async updateCollection(id: string, data: CollectionUpdateRequest): Promise<CollectionResponse> {
    const service = new KnowledgeBaseApiService();
    try {
      return await service.patch<CollectionResponse>(
        service.endpoints.COLLECTION_BY_ID(id),
        data
      );
    } catch (error) {
      throw new Error(service['handleApiError'](error));
    }
  }

  static async deleteCollection(id: string): Promise<void> {
    const service = new KnowledgeBaseApiService();
    try {
      await service.delete<void>(
        service.endpoints.COLLECTION_BY_ID(id)
      );
    } catch (error) {
      throw new Error(service['handleApiError'](error));
    }
  }



  // Files API
  static async getFiles(params?: {
    limit?: number;
    offset?: number;
    collection_id?: string;
    status?: string;
    search?: string;
    tags?: string[];
  }): Promise<FileListResponse> {
    const service = new KnowledgeBaseApiService();
    try {
      const queryParams = new URLSearchParams();
      if (params?.limit) queryParams.append('limit', params.limit.toString());
      if (params?.offset !== undefined) queryParams.append('offset', params.offset.toString());
      if (params?.collection_id) queryParams.append('collection_id', params.collection_id);
      if (params?.status) queryParams.append('status', params.status);
      if (params?.search) queryParams.append('search', params.search);
      if (params?.tags?.length) queryParams.append('tags', params.tags.join(','));

      const url = queryParams.toString()
        ? `${service.endpoints.FILES}?${queryParams.toString()}`
        : service.endpoints.FILES;

      return await service.get<FileListResponse>(url);
    } catch (error) {
      throw new Error(service['handleApiError'](error));
    }
  }

  static async getFile(id: string): Promise<FileResponse> {
    const service = new KnowledgeBaseApiService();
    try {
      const endpoint = service.endpoints.FILE_BY_ID(id);
      return await service.get<FileResponse>(endpoint);
    } catch (error) {
      throw new Error(service['handleApiError'](error));
    }
  }

  static async uploadFile(
    file: File,
    metadata?: FileUploadRequest
  ): Promise<FileResponse> {
    const service = new KnowledgeBaseApiService();
    try {
      const formData = new FormData();
      formData.append('file', file);
      if (metadata?.collection_id) formData.append('collection_id', metadata.collection_id);
      if (metadata?.description) formData.append('description', metadata.description);
      if (metadata?.language) formData.append('language', metadata.language);
      if (metadata?.tags?.length) formData.append('tags', JSON.stringify(metadata.tags));
      return await apiClient.postFormData<FileResponse>(service.endpoints.FILES, formData);
    } catch (error) {
      throw new Error(handleApiError(error));
    }
  }

  static async deleteFile(id: string): Promise<void> {
    const service = new KnowledgeBaseApiService();
    try {
      await service.delete<void>(
        service.endpoints.FILE_BY_ID(id)
      );
    } catch (error) {
      throw new Error(service['handleApiError'](error));
    }
  }

  static async downloadFile(id: string): Promise<Response> {
    const service = new KnowledgeBaseApiService();
    try {
      const endpoint = `${service.endpoints.FILE_BY_ID(id)}/download`;
      return await apiClient.getResponse(endpoint);
    } catch (error) {
      throw new Error(handleApiError(error));
    }
  }

  // Batch operations
  static async deleteFiles(fileIds: string[]): Promise<void> {
    const service = new KnowledgeBaseApiService();
    try {
      await service.post<void>(
        `${service.endpoints.FILES_BATCH}/delete`,
        { file_ids: fileIds }
      );
    } catch (error) {
      throw new Error(service['handleApiError'](error));
    }
  }

  // Website Crawl API

  /**
   * Create a new website crawl job
   */
  static async createCrawlJob(
    collectionId: string,
    crawlConfig: WebsiteCrawlRequest
  ): Promise<WebsiteCrawlCreateResponse> {
    const service = new KnowledgeBaseApiService();
    try {
      const url = `${KNOWLEDGE_BASE_ENDPOINTS.WEBSITE_CRAWL}?collection_id=${collectionId}`;
      return await service.post<WebsiteCrawlCreateResponse>(url, crawlConfig);
    } catch (error) {
      throw new Error(service['handleApiError'](error));
    }
  }

  /**
   * List crawl jobs for a collection
   */
  static async getCrawlJobs(params?: {
    collection_id?: string;
    status?: string;
    limit?: number;
    offset?: number;
  }): Promise<WebsiteCrawlJobListResponse> {
    const service = new KnowledgeBaseApiService();
    try {
      const queryParams = new URLSearchParams();
      if (params?.collection_id) queryParams.append('collection_id', params.collection_id);
      if (params?.status) queryParams.append('status', params.status);
      if (params?.limit) queryParams.append('limit', params.limit.toString());
      if (params?.offset !== undefined) queryParams.append('offset', params.offset.toString());

      const url = queryParams.toString()
        ? `${KNOWLEDGE_BASE_ENDPOINTS.WEBSITE_CRAWL}?${queryParams.toString()}`
        : KNOWLEDGE_BASE_ENDPOINTS.WEBSITE_CRAWL;

      return await service.get<WebsiteCrawlJobListResponse>(url);
    } catch (error) {
      throw new Error(service['handleApiError'](error));
    }
  }

  /**
   * Get a specific crawl job
   */
  static async getCrawlJob(jobId: string): Promise<WebsiteCrawlJobResponse> {
    const service = new KnowledgeBaseApiService();
    try {
      return await service.get<WebsiteCrawlJobResponse>(
        KNOWLEDGE_BASE_ENDPOINTS.WEBSITE_CRAWL_JOB(jobId)
      );
    } catch (error) {
      throw new Error(service['handleApiError'](error));
    }
  }

  /**
   * Cancel a running crawl job
   */
  static async cancelCrawlJob(jobId: string): Promise<WebsiteCrawlJobResponse> {
    const service = new KnowledgeBaseApiService();
    try {
      return await service.post<WebsiteCrawlJobResponse>(
        KNOWLEDGE_BASE_ENDPOINTS.WEBSITE_CRAWL_CANCEL(jobId),
        {}
      );
    } catch (error) {
      throw new Error(service['handleApiError'](error));
    }
  }

  /**
   * Delete a crawl job and all associated pages
   */
  static async deleteCrawlJob(jobId: string): Promise<void> {
    const service = new KnowledgeBaseApiService();
    try {
      await service.delete<void>(
        KNOWLEDGE_BASE_ENDPOINTS.WEBSITE_CRAWL_JOB(jobId)
      );
    } catch (error) {
      throw new Error(service['handleApiError'](error));
    }
  }

  /**
   * Extract metadata (title, description, favicon, og:image) from a website URL
   */
  static async extractWebsiteMetadata(url: string): Promise<WebsiteMetadataResponse> {
    const service = new KnowledgeBaseApiService();
    try {
      return await service.post<WebsiteMetadataResponse>(
        KNOWLEDGE_BASE_ENDPOINTS.EXTRACT_WEBSITE_METADATA,
        { url }
      );
    } catch (error) {
      throw new Error(service['handleApiError'](error));
    }
  }

  /**
   * List crawl jobs for a specific collection
   */
  static async getCollectionCrawlJobs(
    collectionId: string,
    params?: {
      status?: string;
      limit?: number;
      offset?: number;
    }
  ): Promise<WebsiteCrawlJobListResponse> {
    const service = new KnowledgeBaseApiService();
    try {
      const queryParams = new URLSearchParams();
      if (params?.status) queryParams.append('status', params.status);
      if (params?.limit) queryParams.append('limit', params.limit.toString());
      if (params?.offset !== undefined) queryParams.append('offset', params.offset.toString());

      const url = queryParams.toString()
        ? `${KNOWLEDGE_BASE_ENDPOINTS.COLLECTION_CRAWL_JOBS(collectionId)}?${queryParams.toString()}`
        : KNOWLEDGE_BASE_ENDPOINTS.COLLECTION_CRAWL_JOBS(collectionId);

      return await service.get<WebsiteCrawlJobListResponse>(url);
    } catch (error) {
      throw new Error(service['handleApiError'](error));
    }
  }

  /**
   * List pages for a specific collection
   */
  static async getCollectionPages(
    collectionId: string,
    params?: {
      status?: string;
      limit?: number;
      offset?: number;
    }
  ): Promise<WebsitePageListResponse> {
    const service = new KnowledgeBaseApiService();
    try {
      const queryParams = new URLSearchParams();
      if (params?.status) queryParams.append('status', params.status);
      if (params?.limit) queryParams.append('limit', params.limit.toString());
      if (params?.offset !== undefined) queryParams.append('offset', params.offset.toString());

      const url = queryParams.toString()
        ? `${KNOWLEDGE_BASE_ENDPOINTS.COLLECTION_PAGES(collectionId)}?${queryParams.toString()}`
        : KNOWLEDGE_BASE_ENDPOINTS.COLLECTION_PAGES(collectionId);

      return await service.get<WebsitePageListResponse>(url);
    } catch (error) {
      throw new Error(service['handleApiError'](error));
    }
  }

  /**
   * Add a single page URL to an existing crawl job
   */
  static async addPageToCrawlJob(
    jobId: string,
    request: AddPageRequest
  ): Promise<AddPageResponse> {
    const service = new KnowledgeBaseApiService();
    try {
      return await service.post<AddPageResponse>(
        KNOWLEDGE_BASE_ENDPOINTS.WEBSITE_CRAWL_PAGES(jobId),
        request
      );
    } catch (error) {
      throw new Error(service['handleApiError'](error));
    }
  }

  /**
   * Crawl deeper from an existing page - extract links and add them to crawl queue
   */
  static async crawlDeeperFromPage(
    pageId: string,
    request?: CrawlDeeperRequest
  ): Promise<CrawlDeeperResponse> {
    const service = new KnowledgeBaseApiService();
    try {
      return await service.post<CrawlDeeperResponse>(
        KNOWLEDGE_BASE_ENDPOINTS.WEBSITE_PAGE_CRAWL_DEEPER(pageId),
        request || {}
      );
    } catch (error) {
      throw new Error(service['handleApiError'](error));
    }
  }
}

// Export default service instance
export default KnowledgeBaseApiService;
