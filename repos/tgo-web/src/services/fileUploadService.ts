/**
 * File Upload Service with Real Progress Tracking
 * Provides accurate upload progress monitoring using XMLHttpRequest
 */

import { apiClient } from './api';
import type { FileResponse } from './knowledgeBaseApi';
import i18n from '../i18n';

/**
 * Get current user language for API requests
 */
const getCurrentLanguage = (): string => {
  try {
    const lang = i18n.language || 'zh';
    return lang.split('-')[0];
  } catch {
    return 'zh';
  }
};

export interface UploadProgressEvent {
  fileId: string;
  fileName: string;
  progress: number; // 0-100
  loaded: number; // bytes loaded
  total: number; // total bytes
  status: 'uploading' | 'processing' | 'completed' | 'error';
  error?: string;
}

export interface FileUploadOptions {
  collection_id?: string;
  description?: string;
  tags?: string[];
  language?: string;
  onProgress?: (event: UploadProgressEvent) => void;
  onComplete?: (response: FileResponse) => void;
  onError?: (error: Error) => void;
}

/**
 * Upload file with real progress tracking using XMLHttpRequest
 */
export const uploadFileWithProgress = (
  file: File,
  options: FileUploadOptions = {}
): Promise<FileResponse> => {
  return new Promise((resolve, reject) => {
    const fileId = `upload_${Date.now()}_${Math.random().toString(36).substring(2, 11)}`;
    const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
    const uploadUrl = `${API_BASE_URL}/v1/rag/files`;

    // Create FormData
    const formData = new FormData();
    formData.append('file', file);
    
    if (options.collection_id) {
      formData.append('collection_id', options.collection_id);
    }
    if (options.description) {
      formData.append('description', options.description);
    }
    if (options.language) {
      formData.append('language', options.language);
    }
    if (options.tags?.length) {
      formData.append('tags', JSON.stringify(options.tags));
    }

    // Create XMLHttpRequest for progress tracking
    const xhr = new XMLHttpRequest();

    // Set up progress tracking
    xhr.upload.addEventListener('progress', (event) => {
      if (event.lengthComputable) {
        const progress = Math.round((event.loaded / event.total) * 100);
        
        const progressEvent: UploadProgressEvent = {
          fileId,
          fileName: file.name,
          progress,
          loaded: event.loaded,
          total: event.total,
          status: progress < 100 ? 'uploading' : 'processing',
        };

        options.onProgress?.(progressEvent);
      }
    });

    // Handle upload completion
    xhr.addEventListener('load', () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          const response: FileResponse = JSON.parse(xhr.responseText);

          // Debug logging for upload response
          console.log('Upload response:', {
            id: response.id,
            filename: response.original_filename,
            created_at: response.created_at,
            status: response.status,
            full_response: response,
          });

          // Notify completion
          const completedEvent: UploadProgressEvent = {
            fileId,
            fileName: file.name,
            progress: 100,
            loaded: file.size,
            total: file.size,
            status: 'completed',
          };
          options.onProgress?.(completedEvent);
          options.onComplete?.(response);

          resolve(response);
        } catch (error) {
          const parseError = new Error('Failed to parse server response');
          
          const errorEvent: UploadProgressEvent = {
            fileId,
            fileName: file.name,
            progress: 0,
            loaded: 0,
            total: file.size,
            status: 'error',
            error: parseError.message,
          };
          options.onProgress?.(errorEvent);
          options.onError?.(parseError);
          
          reject(parseError);
        }
      } else {
        // Handle HTTP errors
        let errorMessage = `Upload failed: ${xhr.statusText}`;
        
        try {
          const errorData = JSON.parse(xhr.responseText);
          if (errorData.error?.message) {
            errorMessage = errorData.error.message;
          }
        } catch {
          // Use default error message if JSON parsing fails
        }

        // Handle specific status codes
        if (xhr.status === 401) {
          errorMessage = '身份验证失败，请重新登录';
        } else if (xhr.status === 403) {
          errorMessage = '权限不足，无法上传文件';
        } else if (xhr.status === 413) {
          errorMessage = '文件过大，请选择较小的文件';
        } else if (xhr.status === 415) {
          errorMessage = '不支持的文件类型';
        } else if (xhr.status >= 500) {
          errorMessage = '服务器错误，请稍后重试';
        }

        const uploadError = new Error(errorMessage);
        
        const errorEvent: UploadProgressEvent = {
          fileId,
          fileName: file.name,
          progress: 0,
          loaded: 0,
          total: file.size,
          status: 'error',
          error: errorMessage,
        };
        options.onProgress?.(errorEvent);
        options.onError?.(uploadError);
        
        reject(uploadError);
      }
    });

    // Handle network errors
    xhr.addEventListener('error', () => {
      const networkError = new Error('网络连接失败，请检查网络连接后重试');
      
      const errorEvent: UploadProgressEvent = {
        fileId,
        fileName: file.name,
        progress: 0,
        loaded: 0,
        total: file.size,
        status: 'error',
        error: networkError.message,
      };
      options.onProgress?.(errorEvent);
      options.onError?.(networkError);
      
      reject(networkError);
    });

    // Handle upload abort
    xhr.addEventListener('abort', () => {
      const abortError = new Error('上传已取消');
      
      const errorEvent: UploadProgressEvent = {
        fileId,
        fileName: file.name,
        progress: 0,
        loaded: 0,
        total: file.size,
        status: 'error',
        error: abortError.message,
      };
      options.onProgress?.(errorEvent);
      options.onError?.(abortError);
      
      reject(abortError);
    });

    // Set up request
    xhr.open('POST', uploadUrl);

    // Add authentication headers
    const token = apiClient.getToken();
    if (token) {
      xhr.setRequestHeader('Authorization', `Bearer ${token}`);
    }

    // Add user language header
    xhr.setRequestHeader('X-User-Language', getCurrentLanguage());

    // Start upload
    xhr.send(formData);
  });
};

/**
 * Upload multiple files with progress tracking
 */
export const uploadMultipleFilesWithProgress = async (
  files: File[],
  options: Omit<FileUploadOptions, 'onProgress' | 'onComplete' | 'onError'> & {
    onProgress?: (fileId: string, event: UploadProgressEvent) => void;
    onFileComplete?: (fileId: string, response: FileResponse) => void;
    onFileError?: (fileId: string, error: Error) => void;
    onAllComplete?: (results: { success: FileResponse[]; errors: Error[] }) => void;
  } = {}
): Promise<{ success: FileResponse[]; errors: Error[] }> => {
  const results: { success: FileResponse[]; errors: Error[] } = {
    success: [],
    errors: [],
  };

  const uploadPromises = files.map((file) => {
    const fileId = `upload_${Date.now()}_${Math.random().toString(36).substring(2, 11)}`;

    return uploadFileWithProgress(file, {
      ...options,
      onProgress: (event) => options.onProgress?.(fileId, event),
      onComplete: (response) => {
        results.success.push(response);
        options.onFileComplete?.(fileId, response);
      },
      onError: (error) => {
        results.errors.push(error);
        options.onFileError?.(fileId, error);
      },
    });
  });

  try {
    await Promise.allSettled(uploadPromises);
    options.onAllComplete?.(results);
    return results;
  } catch (error) {
    // This shouldn't happen with Promise.allSettled, but just in case
    options.onAllComplete?.(results);
    return results;
  }
};

export default uploadFileWithProgress;
