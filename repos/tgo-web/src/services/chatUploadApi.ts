import { apiClient, APIError } from './api';
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

export interface ChatFileUploadResponse {
  file_id: string;
  file_name: string;
  file_size: number;
  file_url: string;
  file_type: string;
  channel_id: string;
  channel_type: number;
  uploaded_at: string;
  uploaded_by: string;
}

export interface UploadProgress {
  progress: number; // 0-100
  loaded: number;
  total: number;
  status: 'uploading' | 'completed' | 'error';
}

export interface ChatUploadOptions {
  onProgress?: (p: UploadProgress) => void;
  signal?: AbortSignal;
}

/**
 * Upload chat image to backend with progress callback
 * Endpoint: POST /v1/chat/upload (multipart/form-data)
 * Required fields: file, channel_id, channel_type
 */
export const uploadChatImageWithProgress = (
  file: File,
  channelId: string,
  channelType: number,
  options: ChatUploadOptions = {}
): Promise<ChatFileUploadResponse> => {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const url = `/v1/chat/upload`;

    const token = apiClient.getToken();
    const formData = new FormData();
    formData.append('file', file);
    formData.append('channel_id', channelId);
    formData.append('channel_type', String(channelType));

    xhr.open('POST', (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000') + url, true);
    if (token) {
      xhr.setRequestHeader('Authorization', `Bearer ${token}`);
    }
    // Add user language header
    xhr.setRequestHeader('X-User-Language', getCurrentLanguage());

    xhr.upload.addEventListener('progress', (event: ProgressEvent) => {
      if (!event.lengthComputable) return;
      const progress = Math.round((event.loaded / event.total) * 100);
      options.onProgress?.({ progress, loaded: event.loaded, total: event.total, status: 'uploading' });
    });

    xhr.onreadystatechange = () => {
      if (xhr.readyState !== XMLHttpRequest.DONE) return;
      const status = xhr.status;
      if (status >= 200 && status < 300) {
        try {
          const response: ChatFileUploadResponse = JSON.parse(xhr.responseText);
          options.onProgress?.({ progress: 100, loaded: 1, total: 1, status: 'completed' });
          resolve(response);
        } catch (e) {
          reject(new APIError(status, {
            error: { code: 'PARSE_ERROR', message: '无法解析上传响应', details: { status_code: status } },
            request_id: 'unknown'
          }));
        }
      } else {
        try {
          const resp = JSON.parse(xhr.responseText);
          reject(new APIError(status, resp));
        } catch {
          reject(new APIError(status, {
            error: { code: 'HTTP_ERROR', message: `HTTP ${status}`, details: { status_code: status } },
            request_id: 'unknown'
          }));
        }
      }
    };

    xhr.onerror = () => {
      reject(new APIError(0, {
        error: { code: 'NETWORK_ERROR', message: '网络错误或服务器不可用', details: { status_code: 0 } },
        request_id: 'unknown'
      }));
    };

    // Abort support
    if (options.signal) {
      options.signal.addEventListener('abort', () => {
        try { xhr.abort(); } catch {}
        reject(new APIError(0, {
          error: { code: 'ABORTED', message: '上传已取消', details: { status_code: 0 } },
          request_id: 'unknown'
        }));
      }, { once: true });
    }

    xhr.send(formData);
  });
};



/**
 * Upload generic chat file (documents, archives, etc.) with progress callback
 * Endpoint: POST /v1/chat/upload (multipart/form-data)
 * Required fields: file, channel_id, channel_type
 */
export const uploadChatFileWithProgress = (
  file: File,
  channelId: string,
  channelType: number,
  options: ChatUploadOptions = {}
): Promise<ChatFileUploadResponse> => {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const url = `/v1/chat/upload`;

    const token = apiClient.getToken();
    const formData = new FormData();
    formData.append('file', file);
    formData.append('channel_id', channelId);
    formData.append('channel_type', String(channelType));

    xhr.open('POST', (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000') + url, true);
    if (token) {
      xhr.setRequestHeader('Authorization', `Bearer ${token}`);
    }
    // Add user language header
    xhr.setRequestHeader('X-User-Language', getCurrentLanguage());

    xhr.upload.addEventListener('progress', (event: ProgressEvent) => {
      if (!event.lengthComputable) return;
      const progress = Math.round((event.loaded / event.total) * 100);
      options.onProgress?.({ progress, loaded: event.loaded, total: event.total, status: 'uploading' });
    });

    xhr.onreadystatechange = () => {
      if (xhr.readyState !== XMLHttpRequest.DONE) return;
      const status = xhr.status;
      if (status >= 200 && status < 300) {
        try {
          const response: ChatFileUploadResponse = JSON.parse(xhr.responseText);
          options.onProgress?.({ progress: 100, loaded: 1, total: 1, status: 'completed' });
          resolve(response);
        } catch (e) {
          reject(new APIError(status, {
            error: { code: 'PARSE_ERROR', message: '无法解析上传响应', details: { status_code: status } },
            request_id: 'unknown'
          }));
        }
      } else {
        try {
          const resp = JSON.parse(xhr.responseText);
          reject(new APIError(status, resp));
        } catch {
          reject(new APIError(status, {
            error: { code: 'HTTP_ERROR', message: `HTTP ${status}`, details: { status_code: status } },
            request_id: 'unknown'
          }));
        }
      }
    };

    xhr.onerror = () => {
      reject(new APIError(0, {
        error: { code: 'NETWORK_ERROR', message: '网络错误或服务器不可用', details: { status_code: 0 } },
        request_id: 'unknown'
      }));
    };

    // Abort support
    if (options.signal) {
      options.signal.addEventListener('abort', () => {
        try { xhr.abort(); } catch {}
        reject(new APIError(0, {
          error: { code: 'ABORTED', message: '上传已取消', details: { status_code: 0 } },
          request_id: 'unknown'
        }));
      }, { once: true });
    }

    xhr.send(formData);
  });
};
