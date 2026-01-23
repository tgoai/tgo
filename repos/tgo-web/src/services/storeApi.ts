import apiClient from '@/services/api';
import { 
  ToolStoreItem, 
  ToolStoreLoginResponse, 
  ToolStoreRefreshResponse,
  AgentStoreItem,
  AgentDependencyCheckResponse
} from '@/types';
import type { ToolStoreCategory } from '@/types';
import { STORAGE_KEYS } from '@/constants';

// 获取商店 API 地址 (通过 tgo-api 代理)
const PROXY_PATH = '/v1/store/proxy';

// 获取商店的 access token（从 localStorage 中的 Zustand 存储读取）
const getStoreAccessToken = (): string | null => {
  try {
    const authDataStr = localStorage.getItem(STORAGE_KEYS.TOOLSTORE_AUTH);
    if (authDataStr) {
      const authData = JSON.parse(authDataStr);
      return authData.state?.accessToken || null;
    }
  } catch (e) {
    console.error('Failed to get store access token', e);
  }
  return null;
};

// 获取 API base URL
const getApiBaseUrl = (): string => {
  // 优先使用运行时配置 (由 docker-entrypoint.sh 设置)
  if (typeof window !== 'undefined' && (window as any).ENV?.VITE_API_BASE_URL) {
    return (window as any).ENV.VITE_API_BASE_URL;
  }
  // 其次使用构建时环境变量
  if (import.meta.env.VITE_API_BASE_URL) {
    return import.meta.env.VITE_API_BASE_URL;
  }
  return '/api';
};

// 带商店认证的请求函数
const storeAuthFetch = async <T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> => {
  const url = `${getApiBaseUrl()}${endpoint}`;
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...options.headers,
  };

  // 添加 TGO API 的 token
  const tgoToken = localStorage.getItem('tgo-auth-token');
  if (tgoToken) {
    (headers as Record<string, string>)['Authorization'] = `Bearer ${tgoToken}`;
  }

  // 添加商店的 token 作为自定义头
  const storeToken = getStoreAccessToken();
  if (storeToken) {
    (headers as Record<string, string>)['X-Store-Authorization'] = `Bearer ${storeToken}`;
  }

  const response = await fetch(url, { ...options, headers });
  
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `HTTP ${response.status}`);
  }

  if (response.status === 204) {
    return {} as T;
  }

  return response.json();
};

export const storeApi = {
  // --- 认证相关 ---
  
  login: async (credentials: { username: string; password: string }): Promise<ToolStoreLoginResponse> => {
    const response = await storeAuthFetch<ToolStoreLoginResponse>(`${PROXY_PATH}/auth/login`, {
      method: 'POST',
      body: JSON.stringify({
        username: credentials.username,
        password: credentials.password,
      }),
    });

    // 登录成功后自动绑定到当前项目
    try {
      await apiClient.post('/v1/store/bind', {
        access_token: response.access_token
      });
    } catch (e) {
      console.error('Failed to bind Store credential automatically', e);
    }

    return response;
  },

  exchangeCode: async (code: string, codeVerifier: string): Promise<ToolStoreLoginResponse> => {
    const response = await storeAuthFetch<ToolStoreLoginResponse>(`${PROXY_PATH}/auth/exchange?code=${code}&code_verifier=${codeVerifier}`, {
      method: 'POST',
    });

    // 交换成功后自动绑定到当前项目
    try {
      await apiClient.post('/v1/store/bind', {
        access_token: response.access_token
      });
    } catch (e) {
      console.error('Failed to bind Store credential automatically', e);
    }

    return response;
  },

  refreshToken: async (refreshToken: string): Promise<ToolStoreRefreshResponse> => {
    const response = await storeAuthFetch<ToolStoreRefreshResponse>(`${PROXY_PATH}/auth/refresh?refresh_token=${refreshToken}`, {
      method: 'POST',
    });
    return response;
  },

  logout: async (refreshToken: string): Promise<void> => {
    await storeAuthFetch(`${PROXY_PATH}/auth/logout?refresh_token=${refreshToken}`, {
      method: 'POST',
    });
  },

  getMe: async () => {
    const response = await storeAuthFetch<any>(`${PROXY_PATH}/auth/me`, {
      method: 'GET',
    });
    return response;
  },

  // --- 工具相关 ---

  getToolCategories: async (): Promise<ToolStoreCategory[]> => {
    const response = await storeAuthFetch<ToolStoreCategory[]>(`${PROXY_PATH}/tools/categories`, {
      method: 'GET',
    });
    return response;
  },

  getTools: async (params?: { category?: string; search?: string; skip?: number; limit?: number }) => {
    const filteredParams = Object.fromEntries(
      Object.entries(params || {}).filter(([_, v]) => v !== undefined && v !== 'undefined' && v !== '')
    );
    const query = Object.keys(filteredParams).length > 0 
      ? `?${new URLSearchParams(filteredParams as any).toString()}` 
      : '';
    const response = await storeAuthFetch<{ items: ToolStoreItem[]; total: number }>(`${PROXY_PATH}/tools${query}`, {
      method: 'GET',
    });
    return response;
  },

  getTool: async (id: string) => {
    const response = await storeAuthFetch<ToolStoreItem>(`${PROXY_PATH}/tools/${id}`, {
      method: 'GET',
    });
    return response;
  },

  installTool: async (id: string) => {
    // 调用 TGO API 同步工具到本地项目 (TGO API 内部会处理商店状态)
    const response = await apiClient.post<any>('/v1/store/install-tool', { resource_id: id });
    return response;
  },

  uninstallTool: async (id: string) => {
    // 调用 TGO API 卸载 (TGO API 内部会处理商店状态)
    const response = await apiClient.delete<any>(`/v1/store/uninstall-tool/${id}`);
    return response;
  },

  // --- 模型相关 ---

  getModelCategories: async (): Promise<any[]> => {
    const response = await storeAuthFetch<any[]>(`${PROXY_PATH}/models/categories`, {
      method: 'GET',
    });
    return response;
  },

  getModels: async (params?: { category?: string; provider?: string; provider_id?: string; search?: string; skip?: number; limit?: number }) => {
    const filteredParams = Object.fromEntries(
      Object.entries(params || {}).filter(([_, v]) => v !== undefined && v !== 'undefined' && v !== '')
    );
    const query = Object.keys(filteredParams).length > 0 
      ? `?${new URLSearchParams(filteredParams as any).toString()}` 
      : '';
    const response = await storeAuthFetch<{ items: any[]; total: number }>(`${PROXY_PATH}/models${query}`, {
      method: 'GET',
    });
    return response;
  },

  getModelsByProvider: async (providerId: string) => {
    const response = await storeAuthFetch<{ items: any[]; total: number }>(`${PROXY_PATH}/models?provider_id=${providerId}&limit=100`, {
      method: 'GET',
    });
    return (response as any).items || [];
  },

  getModel: async (id: string) => {
    const response = await storeAuthFetch<any>(`${PROXY_PATH}/models/${id}`, {
      method: 'GET',
    });
    return response;
  },

  installModel: async (id: string) => {
    // 调用 TGO API 同步模型到本地项目 (TGO API 内部会处理商店状态)
    const response = await apiClient.post<any>('/v1/store/install-model', { resource_id: id });
    return response;
  },

  uninstallModel: async (id: string) => {
    // 调用 TGO API 卸载 (TGO API 内部会处理商店状态)
    const response = await apiClient.delete<any>(`/v1/store/uninstall-model/${id}`);
    return response;
  },

  getInstalledModels: async (): Promise<string[]> => {
    // 从本地 TGO API 获取已安装模型列表 (model_id 列表)
    const response = await apiClient.get<string[]>('/v1/store/installed-models');
    return response;
  },

  // --- 员工模板相关 ---

  getAgentCategories: async (): Promise<any[]> => {
    const response = await storeAuthFetch<any[]>(`${PROXY_PATH}/agents/categories`, {
      method: 'GET',
    });
    return response;
  },

  getAgents: async (params?: { category?: string; search?: string; skip?: number; limit?: number }) => {
    const filteredParams = Object.fromEntries(
      Object.entries(params || {}).filter(([_, v]) => v !== undefined && v !== 'undefined' && v !== '')
    );
    const query = Object.keys(filteredParams).length > 0 
      ? `?${new URLSearchParams(filteredParams as any).toString()}` 
      : '';
    const response = await storeAuthFetch<{ items: any[]; total: number }>(`${PROXY_PATH}/agents${query}`, {
      method: 'GET',
    });
    return response;
  },

  getAgent: async (id: string): Promise<AgentStoreItem> => {
    const response = await storeAuthFetch<AgentStoreItem>(`${PROXY_PATH}/agents/${id}`, {
      method: 'GET',
    });
    return response;
  },

  checkAgentDependencies: async (id: string): Promise<AgentDependencyCheckResponse> => {
    return await apiClient.get<AgentDependencyCheckResponse>(`/v1/store/agent/${id}/check-dependencies`);
  },

  installAgent: async (id: string, options?: { install_tool_ids?: string[], install_model?: boolean }) => {
    // 调用 TGO API 招聘员工到本地项目
    const response = await apiClient.post<any>('/v1/store/install-agent', { 
      resource_id: id,
      ...options
    });
    return response;
  },

  uninstallAgent: async (id: string) => {
    const response = await apiClient.delete<any>(`/v1/store/uninstall-agent/${id}`);
    return response;
  },

  getStoreConfig: async () => {
    const response = await apiClient.get<{ store_web_url: string; store_api_url: string }>('/v1/store/config');
    return response;
  },
};

export default storeApi;
