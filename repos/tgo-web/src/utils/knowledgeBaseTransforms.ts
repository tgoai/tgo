/**
 * Data transformation utilities for Knowledge Base API responses
 * Converts API response formats to UI-compatible formats
 */

import type { KnowledgeBase, KnowledgeFile, KnowledgeBaseItem } from '@/types';
import type { CollectionResponse, FileResponse } from '@/services/knowledgeBaseApi';

import i18n from '@/i18n';

/**
 * Transform CollectionResponse to KnowledgeBase format
 */
export const transformCollectionToKnowledgeBase = (collection: CollectionResponse): KnowledgeBase => {
  return {
    id: collection.id,
    name: collection.display_name,
    title: collection.display_name,
    description: collection.description || undefined,
    content: collection.description || undefined,
    category: extractCategoryFromTags(collection.tags),
    status: 'active', // Collections are active by default
    createdAt: collection.created_at, // Preserve full ISO timestamp
    updatedAt: collection.updated_at, // Preserve full ISO timestamp
    author: undefined, // Not available in collection response
    tags: collection.tags || [],
    icon: collection.collection_metadata?.icon || undefined, // Extract icon from metadata
    // API-specific fields
    display_name: collection.display_name,
    collection_metadata: collection.collection_metadata || undefined,
    created_at: collection.created_at,
    updated_at: collection.updated_at,
    deleted_at: collection.deleted_at,
  };
};

/**
 * Transform CollectionResponse to KnowledgeBaseItem format (for list compatibility)
 */
export const transformCollectionToKnowledgeBaseItem = (collection: CollectionResponse): KnowledgeBaseItem => {
  // Transform crawl_config from API format to frontend format
  let crawlConfig = undefined;
  if (collection.collection_type === 'website' && collection.crawl_config) {
    crawlConfig = {
      start_url: collection.crawl_config.start_url || '',
      max_pages: collection.crawl_config.max_pages,
      max_depth: collection.crawl_config.max_depth,
      include_patterns: collection.crawl_config.include_patterns,
      exclude_patterns: collection.crawl_config.exclude_patterns,
      options: {
        render_js: collection.crawl_config.js_rendering,
        respect_robots_txt: collection.crawl_config.respect_robots_txt,
        wait_time: collection.crawl_config.delay_between_requests,
      },
    };
  }

  return {
    id: collection.id,
    title: collection.display_name,
    content: collection.description || '',
    category: extractCategoryFromTags(collection.tags) as 'product' | 'support' | 'other',
    status: 'published', // Map to existing status format
    createdAt: collection.created_at, // Preserve full ISO timestamp
    updatedAt: collection.updated_at, // Preserve full ISO timestamp
    author: 'System',
    tags: transformTagsToKnowledgeBaseTags(collection.tags) || [],
    views: 0, // Default views count
    fileCount: collection.file_count, // Default file count
    icon: collection.collection_metadata?.icon || undefined, // Extract icon from metadata
    type: collection.collection_type, // Map collection_type directly to type
    crawlConfig, // Website crawl configuration
  };
};

/**
 * Transform FileResponse to KnowledgeFile format
 */
export const transformFileToKnowledgeFile = (file: FileResponse): KnowledgeFile => {
  // Debug logging for date issues (dev only)
  if (import.meta && import.meta.env && import.meta.env.DEV) {
    console.log('Transforming file:', {
      id: file.id,
      filename: file.original_filename,
      created_at: file.created_at,
      created_at_type: typeof file.created_at,
    });
  }

  // Ensure we have a valid date - use current date if API date is invalid
  let uploadDate: string;
  try {
    // Check if created_at exists and is not empty
    if (!file.created_at || file.created_at.trim() === '') {
      if (import.meta && import.meta.env && import.meta.env.DEV) {
        console.warn('No created_at field in API response, using current date');
      }
      uploadDate = getCurrentDateFormatted();
    } else {
      uploadDate = formatDate(file.created_at);
    }
  } catch (error) {
    if (import.meta && import.meta.env && import.meta.env.DEV) {
      console.warn('Failed to format file date, using current date:', error);
    }
    uploadDate = getCurrentDateFormatted();
  }

  return {
    id: file.id,
    name: file.original_filename,
    size: formatFileSize(file.file_size),
    sizeBytes: file.file_size,
    type: extractFileType(file.content_type, file.original_filename),
    uploadDate,
    status: transformFileStatus(file.status),
    statusType: transformFileStatusType(file.status),
    knowledgeBaseId: file.collection_id || '',
    url: undefined, // Would need to be constructed from file ID
    // API-specific fields
    collection_id: file.collection_id,
    original_filename: file.original_filename,
    file_size: file.file_size,
    content_type: file.content_type,
    document_count: file.document_count,
    total_tokens: file.total_tokens,
    language: file.language,
    description: file.description,
    tags: file.tags,
    uploaded_by: file.uploaded_by,
    created_at: file.created_at,
    updated_at: file.updated_at,
  };
};

/**
 * Extract category from tags array
 */
const extractCategoryFromTags = (tags?: string[] | null): string => {
  if (!tags || tags.length === 0) return 'other';

  // Look for common category indicators
  const categoryMap: Record<string, string> = {
    'product': 'product',
    'documentation': 'product',
    'manual': 'product',
    'support': 'support',
    'faq': 'support',
    'help': 'support',
    'guide': 'support',
  };

  for (const tag of tags) {
    const lowerTag = tag.toLowerCase();
    if (categoryMap[lowerTag]) {
      return categoryMap[lowerTag];
    }
  }

  return 'other';
};

/**
 * Transform tags array to KnowledgeBaseTag format
 */
const transformTagsToKnowledgeBaseTags = (tags?: string[] | null) => {
  if (!tags || tags.length === 0) return [];

  return tags.map((tag, index) => ({
    id: `tag_${index}`,
    name: tag,
    color: getTagColor(index),
  }));
};

/**
 * Get tag color based on index
 */
const getTagColor = (index: number): string => {
  const colors = ['blue', 'green', 'yellow', 'red', 'purple', 'indigo', 'pink'];
  return colors[index % colors.length];
};

/**
 * Format file size from bytes to human readable format
 */
export const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 B';

  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));

  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
};

/**
 * Extract file type from content type and filename
 */
const extractFileType = (contentType: string, filename: string): string => {
  // First try to extract from content type
  if (contentType.includes('pdf')) return 'pdf';
  if (contentType.includes('word') || contentType.includes('document')) return 'doc';
  if (contentType.includes('text')) return 'txt';
  if (contentType.includes('spreadsheet') || contentType.includes('excel')) return 'xlsx';
  if (contentType.includes('presentation') || contentType.includes('powerpoint')) return 'ppt';

  // Fallback to file extension
  const extension = filename.split('.').pop()?.toLowerCase();
  const typeMap: Record<string, string> = {
    'pdf': 'pdf',
    'doc': 'doc',
    'docx': 'doc',
    'txt': 'txt',
    'md': 'txt',
    'xls': 'xlsx',
    'xlsx': 'xlsx',
    'ppt': 'ppt',
    'pptx': 'ppt',
  };

  return typeMap[extension || ''] || 'file';
};

/**
 * Transform API file status to display status
 */
const transformFileStatus = (status: string): string => {
  switch (status) {
    case 'pending':
      return i18n.t('knowledge.detail.pending', { defaultValue: '等待处理' });
    case 'processing':
      return i18n.t('knowledge.detail.processing', { defaultValue: '处理中' });
    case 'chunking_documents':
      return i18n.t('knowledge.detail.chunking', { defaultValue: '分段中' });
    case 'generating_embeddings':
      return i18n.t('knowledge.detail.embedding', { defaultValue: '生成向量中' });
    case 'completed':
      return i18n.t('knowledge.detail.processed', { defaultValue: '已处理' });
    case 'failed':
      return i18n.t('knowledge.detail.error', { defaultValue: '错误' });
    case 'archived':
      return i18n.t('knowledge.detail.archived', { defaultValue: '已归档' });
    default:
      return status;
  }
};

/**
 * Transform API file status to status type
 */
const transformFileStatusType = (status: string): 'success' | 'processing' | 'error' => {
  switch (status) {
    case 'completed':
      return 'success';
    case 'processing':
    case 'pending':
    case 'chunking_documents':
    case 'generating_embeddings':
      return 'processing';
    case 'failed':
      return 'error';
    default:
      return 'processing';
  }
};

/**
 * Get current date in Chinese locale format
 */
export const getCurrentDateFormatted = (): string => {
  return new Date().toLocaleDateString(i18n.language);
};

/**
 * Format date string to locale format with enhanced error handling
 */
const formatDate = (dateString: string): string => {
  try {
    // Handle null, undefined, or empty strings
    if (!dateString || dateString.trim() === '') {
      if (import.meta && import.meta.env && import.meta.env.DEV) {
        console.warn('Empty date string, using current date');
      }
      return new Date().toLocaleDateString(i18n.language);
    }

    // Try to parse the date string
    let date: Date;

    // Handle ISO date strings (most common API format)
    if (typeof dateString === 'string' && dateString.includes('T')) {
      date = new Date(dateString);
    } else if (typeof dateString === 'string' && dateString.includes('-')) {
      // Handle YYYY-MM-DD format
      date = new Date(dateString);
    } else {
      // Try direct parsing
      date = new Date(dateString);
    }

    // Check if the date is valid
    if (isNaN(date.getTime())) {
      if (import.meta && import.meta.env && import.meta.env.DEV) {
        console.warn('Invalid date string:', dateString, 'type:', typeof dateString);
      }
      // Return current date as fallback
      return new Date().toLocaleDateString(i18n.language);
    }

    // Format the date
    const formattedDate = date.toLocaleDateString(i18n.language);
    console.log('Date formatted:', dateString, '->', formattedDate);
    return formattedDate;

  } catch (error) {
    if (import.meta && import.meta.env && import.meta.env.DEV) {
      console.error('Error formatting date:', error, 'dateString:', dateString, 'type:', typeof dateString);
    }
    // Return current date as fallback
    return new Date().toLocaleDateString(i18n.language);
  }
};

/**
 * Transform KnowledgeBaseItem to CollectionCreateRequest
 */
export const transformKnowledgeBaseItemToCreateRequest = (item: Partial<KnowledgeBaseItem>) => {
  // Handle tags - prioritize direct tags array if provided
  let tags: string[] | undefined = undefined;
  if (Array.isArray(item.tags)) {
    tags = item.tags.map(tag => typeof tag === 'string' ? tag : tag.name).filter(Boolean);
  }

  // Transform crawl config if present
  let crawl_config = undefined;
  if (item.type === 'website' && item.crawlConfig) {
    crawl_config = {
      start_url: item.crawlConfig.start_url,
      max_pages: item.crawlConfig.max_pages,
      max_depth: item.crawlConfig.max_depth,
      include_patterns: item.crawlConfig.include_patterns,
      exclude_patterns: item.crawlConfig.exclude_patterns,
      js_rendering: item.crawlConfig.options?.render_js,
      respect_robots_txt: item.crawlConfig.options?.respect_robots_txt,
      delay_between_requests: item.crawlConfig.options?.wait_time,
    };
  }

  return {
    display_name: item.title || 'Untitled Collection',
    description: item.content || undefined,
    tags: tags,
    collection_type: item.type || 'file',
    crawl_config: crawl_config,
    collection_metadata: {
      category: item.category,
      icon: item.icon,
    },
  };
};

/**
 * Batch transform collections to knowledge base items
 */
export const transformCollectionsToKnowledgeBaseItems = (collections: CollectionResponse[]): KnowledgeBaseItem[] => {
  return collections.map(transformCollectionToKnowledgeBaseItem);
};

/**
 * Batch transform files to knowledge files
 */
export const transformFilesToKnowledgeFiles = (files: FileResponse[]): KnowledgeFile[] => {
  return files.map(transformFileToKnowledgeFile);
};
