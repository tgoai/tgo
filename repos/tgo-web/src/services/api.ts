/**
 * API Service Layer for TGO Web
 * Handles all HTTP requests to the backend API
 */

import i18n from '../i18n';

// API Configuration
// Priority: window.ENV (runtime) > import.meta.env (build-time) > default
const getApiBaseUrl = (): string => {
  // First, try runtime configuration (set by docker-entrypoint.sh)
  if (typeof window !== 'undefined' && (window as any).ENV?.VITE_API_BASE_URL) {
    return (window as any).ENV.VITE_API_BASE_URL;
  }
  // Fall back to build-time environment variable
  if (import.meta.env.VITE_API_BASE_URL) {
    return import.meta.env.VITE_API_BASE_URL;
  }
  // Default fallback
  return '/api';
};

const API_BASE_URL = getApiBaseUrl();

/**
 * Get current user language for API requests
 * Returns the current i18n language code (e.g., 'zh', 'en')
 */
const getCurrentLanguage = (): string => {
  try {
    // Get current language from i18n, default to 'zh' if not available
    const lang = i18n.language || 'zh';
    // Return base language code (e.g., 'zh' from 'zh-CN')
    return lang.split('-')[0];
  } catch {
    return 'zh';
  }
};

// API Response Types based on OpenAPI specification
export interface StaffLoginRequest {
  username: string;
  password: string;
  grant_type?: string;
  scope?: string;
  client_id?: string | null;
  client_secret?: string | null;
}

export interface StaffCreateRequest {
  username: string;
  password: string;
  nickname?: string | null;
  avatar_url?: string | null;
  role?: 'user' | 'agent';
  status?: 'online' | 'offline' | 'busy';
  agent_id?: string | null;
  description?: string | null;
}

export interface StaffResponse {
  id: string;
  project_id: string;
  username: string;
  nickname: string | null;
  avatar_url: string | null;
  role: 'user' | 'admin' | 'agent';
  status: 'online' | 'offline' | 'busy';
  is_active: boolean; // 是否停止服务（长期开关）
  service_paused: boolean;
  is_working?: boolean; // 是否在工作时间（根据分配规则计算）
  agent_id: string | null;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface StaffLoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  staff: StaffResponse;
}

export interface APIErrorDetail {
  error: {
    code: string;
    message: string;
    details: {
      status_code: number;
    };
  };
  request_id: string;
}

// Unauthorized handler hook
let onUnauthorized: (() => void) | null = null;
export const setUnauthorizedHandler = (handler: () => void) => { onUnauthorized = handler; };

// HTTP Client Class
class APIClient {
  private baseURL: string;
  private token: string | null = null;

  constructor(baseURL: string) {
    this.baseURL = baseURL;
    // Load token from localStorage on initialization
    this.token = localStorage.getItem('tgo-auth-token');
  }

  // Set authentication token
  setToken(token: string | null) {
    this.token = token;
    if (token) {
      localStorage.setItem('tgo-auth-token', token);
    } else {
      localStorage.removeItem('tgo-auth-token');
    }
  }

  // Get authentication token
  getToken(): string | null {
    return this.token;
  }

  // Generic request method
  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseURL}${endpoint}`;
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      ...options.headers,
    };

    // Add authorization header if token exists
    if (this.token) {
      (headers as Record<string, string>)['Authorization'] = `Bearer ${this.token}`;
    }

    // Add user language header
    (headers as Record<string, string>)['X-User-Language'] = getCurrentLanguage();

    const config: RequestInit = {
      ...options,
      headers,
    };

    try {
      const response = await fetch(url, config);
      
      // Handle different response types
      if (!response.ok) {
        // Trigger global unauthorized handler on 401 when token exists
        if (response.status === 401 && this.token) {
          try { onUnauthorized?.(); } catch {}
        }
        let errorData: APIErrorDetail;
        try {
          const responseData = await response.json();

          // Check if response matches the expected API error format
          if (responseData.error && responseData.error.message) {
            errorData = responseData;
          } else {
            // Fallback for unexpected error formats
            errorData = {
              error: {
                code: 'HTTP_ERROR',
                message: responseData.message || responseData.detail || `HTTP ${response.status}: ${response.statusText}`,
                details: {
                  status_code: response.status
                }
              },
              request_id: responseData.request_id || 'unknown'
            };
          }
        } catch {
          // Fallback for non-JSON responses
          errorData = {
            error: {
              code: 'HTTP_ERROR',
              message: `HTTP ${response.status}: ${response.statusText}`,
              details: {
                status_code: response.status
              }
            },
            request_id: 'unknown'
          };
        }
        throw new APIError(response.status, errorData);
      }

      // Handle 204 No Content responses
      if (response.status === 204) {
        return {} as T;
      }

      return await response.json();
    } catch (error) {
      if (error instanceof APIError) {
        throw error;
      }
      console.error('Network error:', error);
      throw new APIError(0, {
        error: {
          code: 'NETWORK_ERROR',
          message: 'Network error or server unavailable',
          details: {
            status_code: 0
          }
        },
        request_id: 'unknown'
      });
    }
  }

  // GET request
  async get<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: 'GET' });
  }

  // GET request with body (some APIs use this for complex queries)
  async getWithBody<T>(endpoint: string, data?: any): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'GET',
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  // POST request
  async post<T>(endpoint: string, data?: any): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'POST',
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  /**
   * Streaming POST request using Fetch API and ReadableStream
   * Specifically designed for text/event-stream (SSE)
   */
  async stream(
    endpoint: string,
    data: any,
    options: {
      onMessage: (event: string, data: any) => void;
      onClose?: () => void;
      onError?: (error: any) => void;
      signal?: AbortSignal;
    }
  ): Promise<void> {
    const url = `${this.baseURL}${endpoint}`;
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
    };

    if (this.token) {
      (headers as Record<string, string>)['Authorization'] = `Bearer ${this.token}`;
    }
    (headers as Record<string, string>)['X-User-Language'] = getCurrentLanguage();

    try {
      const response = await fetch(url, {
        method: 'POST',
        headers,
        body: data ? JSON.stringify(data) : undefined,
        signal: options.signal,
      });

      if (!response.ok) {
        let errorData: any;
        try {
          errorData = await response.json();
        } catch {
          errorData = { error: { message: `HTTP ${response.status}: ${response.statusText}` } };
        }
        throw new APIError(response.status, errorData);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error('Response body is null');

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        
        // SSE parsing logic
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        let currentEvent = 'message';

        for (const line of lines) {
          const trimmedLine = line.trim();
          if (!trimmedLine) continue;

          if (trimmedLine.startsWith('event:')) {
            currentEvent = trimmedLine.replace('event:', '').trim();
          } else if (trimmedLine.startsWith('data:')) {
            const dataStr = trimmedLine.replace('data:', '').trim();
            try {
              const parsedData = JSON.parse(dataStr);
              options.onMessage(currentEvent, parsedData);
            } catch (e) {
              console.error('Failed to parse SSE data:', dataStr, e);
            }
            // Reset event for next message if it wasn't explicitly set
            currentEvent = 'message';
          }
        }
      }
      
      options.onClose?.();
    } catch (error: any) {
      if (error.name === 'AbortError') {
        options.onClose?.();
        return;
      }
      options.onError?.(error);
      throw error;
    }
  }

  // POST request with form data
  async postForm<T>(endpoint: string, data: Record<string, string>): Promise<T> {
    const formData = new URLSearchParams();
    Object.entries(data).forEach(([key, value]) => {
      formData.append(key, value);
    });

    return this.request<T>(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: formData.toString(),
    });
  }

  // POST multipart/form-data (FormData)
  async postFormData<T>(endpoint: string, formData: FormData, extraHeaders?: HeadersInit): Promise<T> {
    const url = `${this.baseURL}${endpoint}`;
    const headers: HeadersInit = {
      ...(extraHeaders || {}),
    };
    if (this.token) {
      (headers as Record<string, string>)['Authorization'] = `Bearer ${this.token}`;
    }
    // Add user language header
    (headers as Record<string, string>)['X-User-Language'] = getCurrentLanguage();
    const config: RequestInit = {
      method: 'POST',
      headers,
      body: formData,
    };
    try {
      const response = await fetch(url, config);
      if (!response.ok) {
        // Trigger global unauthorized handler on 401 when token exists
        if (response.status === 401 && this.token) {
          try { onUnauthorized?.(); } catch {}
        }
        let errorData: APIErrorDetail;
        try {
          const responseData = await response.json();
          if (responseData.error && responseData.error.message) {
            errorData = responseData;
          } else {
            errorData = {
              error: {
                code: 'HTTP_ERROR',
                message: responseData.message || responseData.detail || `HTTP ${response.status}: ${response.statusText}`,
                details: {
                  status_code: response.status
                }
              },
              request_id: responseData.request_id || 'unknown'
            };
          }
        } catch {
          errorData = {
            error: {
              code: 'HTTP_ERROR',
              message: `HTTP ${response.status}: ${response.statusText}`,
              details: { status_code: response.status }
            },
            request_id: 'unknown'
          };
        }
        throw new APIError(response.status, errorData);
      }
      return await response.json();
    } catch (error) {
      if (error instanceof APIError) throw error;
      throw new APIError(0, {
        error: { code: 'NETWORK_ERROR', message: 'Network error or server unavailable', details: { status_code: 0 } },
        request_id: 'unknown'
      });
    }
  }

  // GET raw response (e.g., for binary downloads)
  async getResponse(endpoint: string, extraHeaders?: HeadersInit): Promise<Response> {
    const url = `${this.baseURL}${endpoint}`;
    const headers: HeadersInit = { ...(extraHeaders || {}) };
    if (this.token) {
      (headers as Record<string, string>)['Authorization'] = `Bearer ${this.token}`;
    }
    // Add user language header
    (headers as Record<string, string>)['X-User-Language'] = getCurrentLanguage();
    const config: RequestInit = { method: 'GET', headers };
    const response = await fetch(url, config);
    if (!response.ok) {
      // Trigger global unauthorized handler on 401 when token exists
      if (response.status === 401 && this.token) {
        try { onUnauthorized?.(); } catch {}
      }
      // Let caller handle specific status, but throw a structured error for consistency
      let message = `HTTP ${response.status}: ${response.statusText}`;
      try {
        const data = await response.json();
        message = data?.error?.message || message;
      } catch {}
      throw new APIError(response.status, {
        error: { code: 'HTTP_ERROR', message, details: { status_code: response.status } },
        request_id: 'unknown'
      });
    }
    return response;
  }

  // PUT request
  async put<T>(endpoint: string, data: any): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  // PATCH request
  async patch<T>(endpoint: string, data: any): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  }

  // DELETE request
  async delete<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: 'DELETE' });
  }
}

// Custom API Error class
export class APIError extends Error {
  public status: number;
  public data: APIErrorDetail;
  public requestId?: string;

  constructor(status: number, data: APIErrorDetail) {
    const message = data.error?.message || 'API Error';

    super(message);
    this.name = 'APIError';
    this.status = status;
    this.data = data;
    this.requestId = data.request_id;
  }

  // Get user-friendly error message
  getUserMessage(): string {
    return this.data.error?.message || 'An unexpected error occurred';
  }

  // Get error code
  getErrorCode(): string {
    return this.data.error?.code || 'UNKNOWN_ERROR';
  }

  // Get request ID for debugging
  getRequestId(): string | undefined {
    return this.requestId;
  }
}

// Create API client instance
export const apiClient = new APIClient(API_BASE_URL);

// Authentication API methods
export const authAPI = {
  // Staff login
  async login(credentials: { username: string; password: string }): Promise<StaffLoginResponse> {
    const loginData = {
      username: credentials.username,
      password: credentials.password,
      grant_type: 'password',
    };

    const response = await apiClient.postForm<StaffLoginResponse>('/v1/staff/login', loginData);
    
    // Set token in client for future requests
    apiClient.setToken(response.access_token);
    
    return response;
  },

  // Staff registration
  async register(userData: { username: string; password: string; nickname?: string }): Promise<StaffResponse> {
    const registerData: StaffCreateRequest = {
      username: userData.username,
      password: userData.password,
      nickname: userData.nickname || null,
      role: 'user',
      status: 'offline',
    };

    return apiClient.post<StaffResponse>('/v1/staff', registerData);
  },

  // Logout (clear token)
  logout(): void {
    apiClient.setToken(null);
  },

  // Get current user info
  async getCurrentUser(): Promise<StaffResponse> {
    // This would require the current user endpoint, but it's not in the API spec
    // For now, we'll rely on the user data from login response
    throw new Error('getCurrentUser not implemented - user data available from login response');
  },
};

export default apiClient;
