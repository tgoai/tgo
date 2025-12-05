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

// New Website Page Types (based on new API spec)
export interface WebsitePageResponse {
  id: string;
  collection_id: string;
  parent_page_id?: string | null;
  url: string;
  title?: string | null;
  depth: number;
  content_length: number;
  meta_description?: string | null;
  status: 'pending' | 'crawling' | 'fetched' | 'extracted' | 'processing' | 'processed' | 'failed' | 'skipped';
  crawl_source?: 'initial' | 'discovered' | 'manual' | 'deep_crawl' | null;
  http_status_code?: number | null;
  file_id?: string | null;
  discovered_links?: Array<Record<string, any>> | null;
  error_message?: string | null;
  tree_completed?: boolean; // Whether this page and all its descendant pages have been processed or skipped
  has_children?: boolean; // Whether this page has any child pages
  children?: WebsitePageResponse[] | null; // Child pages (populated when tree_depth > 0)
  created_at: string;
  updated_at: string;
}

export interface WebsitePageListResponse extends PaginatedResponse<WebsitePageResponse> {}

// Add Page Types (new API)
export interface AddPageRequest {
  url: string;
  parent_page_id?: string | null; // Parent page ID. If provided, the new page will be a child of this page
  max_depth?: number; // 0-10, default 0 (only this page)
  include_patterns?: string[] | null;
  exclude_patterns?: string[] | null;
  options?: CrawlOptionsRequest | null;
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

// Crawl Progress Types (new API)
export interface CrawlProgressSchema {
  total_pages: number;
  pages_pending: number;
  pages_crawled: number;
  pages_processing: number;
  pages_processed: number;
  pages_failed: number;
  progress_percent: number;
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

// QA Pair Types
export interface QAPairResponse {
  id: string;
  collection_id: string;
  question: string;
  answer: string;
  question_hash: string;
  category?: string | null;
  subcategory?: string | null;
  tags?: string[] | null;
  qa_metadata?: Record<string, any> | null;
  source_type: 'manual' | 'import' | 'ai_generated';
  status: 'pending' | 'processing' | 'processed' | 'failed';
  priority: number;
  document_id?: string | null;
  created_at: string;
  updated_at: string;
}

export interface QAPairListResponse {
  data: QAPairResponse[];
  total: number;
  limit: number;
  offset: number;
}

export interface QAPairCreateRequest {
  question: string;
  answer: string;
  category?: string | null;
  subcategory?: string | null;
  tags?: string[] | null;
  qa_metadata?: Record<string, any> | null;
  priority?: number;
}

export interface QAPairUpdateRequest {
  question?: string | null;
  answer?: string | null;
  category?: string | null;
  subcategory?: string | null;
  tags?: string[] | null;
  qa_metadata?: Record<string, any> | null;
  priority?: number | null;
}

export interface QAPairBatchCreateRequest {
  qa_pairs: QAPairCreateRequest[];
}

export interface QAPairBatchCreateResponse {
  success: boolean;
  created_count: number;
  skipped_count: number;
  failed_count: number;
  created_ids?: string[] | null;
  errors?: Array<Record<string, any>> | null;
}

export interface QAPairImportRequest {
  format: 'json' | 'csv';
  data: string;
  category?: string | null;
  tags?: string[] | null;
}

export interface QACategoryListResponse {
  categories: string[];
  total: number;
}

// API Endpoints - Use relative paths since the API client already includes the base URL
const API_VERSION = 'v1';

export const KNOWLEDGE_BASE_ENDPOINTS = {
  // Collections
  COLLECTIONS: `/${API_VERSION}/rag/collections`,
  COLLECTION_BY_ID: (id: string) => `/${API_VERSION}/rag/collections/${id}`,

  // Files
  FILES: `/${API_VERSION}/rag/files`,
  FILE_BY_ID: (id: string) => `/${API_VERSION}/rag/files/${id}`,
  FILES_BATCH: `/${API_VERSION}/rag/files/batch`,

  // Website Pages (new API)
  WEBSITE_PAGES: `/${API_VERSION}/rag/websites/pages`,
  WEBSITE_PAGE_BY_ID: (pageId: string) => `/${API_VERSION}/rag/websites/pages/${pageId}`,
  WEBSITE_PAGE_RECRAWL: (pageId: string) => `/${API_VERSION}/rag/websites/pages/${pageId}/recrawl`,
  WEBSITE_PAGE_CRAWL_DEEPER: (pageId: string) => `/${API_VERSION}/rag/websites/pages/${pageId}/crawl-deeper`,
  WEBSITE_CRAWL_PROGRESS: `/${API_VERSION}/rag/websites/progress`,

  // QA Pairs
  QA_PAIRS: (collectionId: string) => `/${API_VERSION}/rag/${collectionId}/qa-pairs`,
  QA_PAIRS_BATCH: (collectionId: string) => `/${API_VERSION}/rag/${collectionId}/qa-pairs/batch`,
  QA_PAIRS_IMPORT: (collectionId: string) => `/${API_VERSION}/rag/${collectionId}/qa-pairs/import`,
  QA_CATEGORIES: `/${API_VERSION}/rag/qa-categories`,
  QA_PAIR_BY_ID: (qaPairId: string) => `/${API_VERSION}/rag/qa-pairs/${qaPairId}`,

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

  // Website Pages API (new API structure)

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
   * List pages for a collection (supports hierarchical queries via parent_page_id)
   * GET /v1/rag/websites/pages?collection_id=...
   */
  static async getWebsitePages(
    collectionId: string,
    params?: {
      status?: string;
      depth?: number;
      parent_page_id?: string | null;
      tree_depth?: number; // Number of child levels to include: 0/undefined=no children, 1=direct children, -1=unlimited
      limit?: number;
      offset?: number;
    }
  ): Promise<WebsitePageListResponse> {
    const service = new KnowledgeBaseApiService();
    try {
      const queryParams = new URLSearchParams();
      queryParams.append('collection_id', collectionId);
      if (params?.status) queryParams.append('status', params.status);
      if (params?.depth !== undefined) queryParams.append('depth', params.depth.toString());
      if (params?.parent_page_id !== undefined) {
        // null means get root pages, string means get children of that page
        if (params.parent_page_id === null) {
          // For root pages, don't send parent_page_id or send empty
        } else {
          queryParams.append('parent_page_id', params.parent_page_id);
        }
      }
      if (params?.tree_depth !== undefined) queryParams.append('tree_depth', params.tree_depth.toString());
      if (params?.limit) queryParams.append('limit', params.limit.toString());
      if (params?.offset !== undefined) queryParams.append('offset', params.offset.toString());

      const url = `${KNOWLEDGE_BASE_ENDPOINTS.WEBSITE_PAGES}?${queryParams.toString()}`;
      return await service.get<WebsitePageListResponse>(url);
    } catch (error) {
      throw new Error(service['handleApiError'](error));
    }
  }

  /**
   * Get a specific page by ID
   * GET /v1/rag/websites/pages/{page_id}
   */
  static async getWebsitePageDetail(pageId: string): Promise<WebsitePageResponse> {
    const service = new KnowledgeBaseApiService();
    try {
      return await service.get<WebsitePageResponse>(
        KNOWLEDGE_BASE_ENDPOINTS.WEBSITE_PAGE_BY_ID(pageId)
      );
    } catch (error) {
      throw new Error(service['handleApiError'](error));
    }
  }

  /**
   * Add a page to a collection
   * POST /v1/rag/websites/pages?collection_id=...
   */
  static async addWebsitePage(
    collectionId: string,
    request: AddPageRequest
  ): Promise<AddPageResponse> {
    const service = new KnowledgeBaseApiService();
    try {
      const url = `${KNOWLEDGE_BASE_ENDPOINTS.WEBSITE_PAGES}?collection_id=${collectionId}`;
      return await service.post<AddPageResponse>(url, request);
    } catch (error) {
      throw new Error(service['handleApiError'](error));
    }
  }

  /**
   * Delete a page from the collection
   * DELETE /v1/rag/websites/pages/{page_id}
   */
  static async deleteWebsitePage(pageId: string): Promise<void> {
    const service = new KnowledgeBaseApiService();
    try {
      await service.delete<void>(
        KNOWLEDGE_BASE_ENDPOINTS.WEBSITE_PAGE_BY_ID(pageId)
      );
    } catch (error) {
      throw new Error(service['handleApiError'](error));
    }
  }

  /**
   * Recrawl an existing page
   * POST /v1/rag/websites/pages/{page_id}/recrawl
   */
  static async recrawlWebsitePage(pageId: string): Promise<AddPageResponse> {
    const service = new KnowledgeBaseApiService();
    try {
      return await service.post<AddPageResponse>(
        KNOWLEDGE_BASE_ENDPOINTS.WEBSITE_PAGE_RECRAWL(pageId),
        {}
      );
    } catch (error) {
      throw new Error(service['handleApiError'](error));
    }
  }

  /**
   * Crawl deeper from an existing page - extract links and add them to crawl queue
   * POST /v1/rag/websites/pages/{page_id}/crawl-deeper
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

  /**
   * Get crawl progress for a collection
   * GET /v1/rag/websites/progress?collection_id=...
   */
  static async getWebsiteCrawlProgress(collectionId: string): Promise<CrawlProgressSchema> {
    const service = new KnowledgeBaseApiService();
    try {
      const url = `${KNOWLEDGE_BASE_ENDPOINTS.WEBSITE_CRAWL_PROGRESS}?collection_id=${collectionId}`;
      return await service.get<CrawlProgressSchema>(url);
    } catch (error) {
      throw new Error(service['handleApiError'](error));
    }
  }

  // QA Pairs API

  /**
   * List QA pairs for a collection
   * GET /v1/rag/{collection_id}/qa-pairs
   */
  static async getQAPairs(
    collectionId: string,
    params?: {
      limit?: number;
      offset?: number;
      category?: string;
      status?: string;
    }
  ): Promise<QAPairListResponse> {
    const service = new KnowledgeBaseApiService();
    try {
      const queryParams = new URLSearchParams();
      if (params?.limit) queryParams.append('limit', params.limit.toString());
      if (params?.offset !== undefined) queryParams.append('offset', params.offset.toString());
      if (params?.category) queryParams.append('category', params.category);
      if (params?.status) queryParams.append('status', params.status);

      const baseUrl = KNOWLEDGE_BASE_ENDPOINTS.QA_PAIRS(collectionId);
      const url = queryParams.toString() ? `${baseUrl}?${queryParams.toString()}` : baseUrl;
      return await service.get<QAPairListResponse>(url);
    } catch (error) {
      throw new Error(service['handleApiError'](error));
    }
  }

  /**
   * Create a single QA pair
   * POST /v1/rag/{collection_id}/qa-pairs
   */
  static async createQAPair(
    collectionId: string,
    request: QAPairCreateRequest
  ): Promise<QAPairResponse> {
    const service = new KnowledgeBaseApiService();
    try {
      return await service.post<QAPairResponse>(
        KNOWLEDGE_BASE_ENDPOINTS.QA_PAIRS(collectionId),
        request
      );
    } catch (error) {
      throw new Error(service['handleApiError'](error));
    }
  }

  /**
   * Get a single QA pair by ID
   * GET /v1/rag/qa-pairs/{qa_pair_id}
   */
  static async getQAPair(qaPairId: string): Promise<QAPairResponse> {
    const service = new KnowledgeBaseApiService();
    try {
      return await service.get<QAPairResponse>(
        KNOWLEDGE_BASE_ENDPOINTS.QA_PAIR_BY_ID(qaPairId)
      );
    } catch (error) {
      throw new Error(service['handleApiError'](error));
    }
  }

  /**
   * Update a QA pair
   * PUT /v1/rag/qa-pairs/{qa_pair_id}
   */
  static async updateQAPair(
    qaPairId: string,
    request: QAPairUpdateRequest
  ): Promise<QAPairResponse> {
    const service = new KnowledgeBaseApiService();
    try {
      return await service.put<QAPairResponse>(
        KNOWLEDGE_BASE_ENDPOINTS.QA_PAIR_BY_ID(qaPairId),
        request
      );
    } catch (error) {
      throw new Error(service['handleApiError'](error));
    }
  }

  /**
   * Delete a QA pair
   * DELETE /v1/rag/qa-pairs/{qa_pair_id}
   */
  static async deleteQAPair(qaPairId: string): Promise<void> {
    const service = new KnowledgeBaseApiService();
    try {
      await service.delete<void>(
        KNOWLEDGE_BASE_ENDPOINTS.QA_PAIR_BY_ID(qaPairId)
      );
    } catch (error) {
      throw new Error(service['handleApiError'](error));
    }
  }

  /**
   * Batch create QA pairs
   * POST /v1/rag/{collection_id}/qa-pairs/batch
   */
  static async batchCreateQAPairs(
    collectionId: string,
    request: QAPairBatchCreateRequest
  ): Promise<QAPairBatchCreateResponse> {
    const service = new KnowledgeBaseApiService();
    try {
      return await service.post<QAPairBatchCreateResponse>(
        KNOWLEDGE_BASE_ENDPOINTS.QA_PAIRS_BATCH(collectionId),
        request
      );
    } catch (error) {
      throw new Error(service['handleApiError'](error));
    }
  }

  /**
   * Import QA pairs from JSON or CSV
   * POST /v1/rag/{collection_id}/qa-pairs/import
   */
  static async importQAPairs(
    collectionId: string,
    request: QAPairImportRequest
  ): Promise<QAPairBatchCreateResponse> {
    const service = new KnowledgeBaseApiService();
    try {
      return await service.post<QAPairBatchCreateResponse>(
        KNOWLEDGE_BASE_ENDPOINTS.QA_PAIRS_IMPORT(collectionId),
        request
      );
    } catch (error) {
      throw new Error(service['handleApiError'](error));
    }
  }

  /**
   * Get QA categories
   * GET /v1/rag/qa-categories
   */
  static async getQACategories(collectionId?: string): Promise<QACategoryListResponse> {
    const service = new KnowledgeBaseApiService();
    try {
      const queryParams = new URLSearchParams();
      if (collectionId) {
        queryParams.append('collection_id', collectionId);
      }
      const url = queryParams.toString()
        ? `${KNOWLEDGE_BASE_ENDPOINTS.QA_CATEGORIES}?${queryParams.toString()}`
        : KNOWLEDGE_BASE_ENDPOINTS.QA_CATEGORIES;
      return await service.get<QACategoryListResponse>(url);
    } catch (error) {
      throw new Error(service['handleApiError'](error));
    }
  }
}

// Export default service instance
export default KnowledgeBaseApiService;
