import axios, { InternalAxiosRequestConfig, AxiosResponse } from 'axios';
import apiClient from '@/services/api';
import { 
  ToolStoreItem, 
  ToolStoreLoginResponse, 
  ToolStoreRefreshResponse
} from '@/types';
import { STORAGE_KEYS } from '@/constants';
import type { ToolStoreCategory } from '@/types';

// 获取商店 API 地址
const getStoreBaseUrl = () => {
  // 如果没有环境变量配置，默认直接请求商店后端 (Port 8095)
  return (window as any).ENV?.VITE_STORE_API_URL || (window as any).ENV?.VITE_TOOLSTORE_API_URL || 'http://localhost:8095/api/v1';
};

const storeClient = axios.create({
  baseURL: getStoreBaseUrl(),
});

// 请求拦截器：注入 Access Token
storeClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const authDataStr = localStorage.getItem(STORAGE_KEYS.TOOLSTORE_AUTH);
    if (authDataStr) {
      try {
        const authData = JSON.parse(authDataStr);
        const token = authData.state?.accessToken;
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
      } catch (e) {
        console.error('Failed to parse store auth data', e);
      }
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// 响应拦截器：处理 401 并尝试刷新 Token
storeClient.interceptors.response.use(
  (response: AxiosResponse) => response,
  async (error) => {
    const originalRequest = error.config;
    
    // 如果是 401 且不是刷新 token 的请求
    if (error.response?.status === 401 && !originalRequest._retry && !originalRequest.url?.includes('/auth/refresh')) {
      originalRequest._retry = true;
      
      try {
        const authDataStr = localStorage.getItem(STORAGE_KEYS.TOOLSTORE_AUTH);
        if (authDataStr) {
          const authData = JSON.parse(authDataStr);
          const refreshToken = authData.state?.refreshToken;
          
          if (refreshToken) {
            // 调用刷新接口
            const response = await storeApi.refreshToken(refreshToken);
            
            // 更新本地存储（Zustand 会自动处理，但拦截器需要同步获取新 token）
            authData.state.accessToken = response.access_token;
            authData.state.refreshToken = response.refresh_token;
            localStorage.setItem(STORAGE_KEYS.TOOLSTORE_AUTH, JSON.stringify(authData));
            
            // 重试原请求
            originalRequest.headers.Authorization = `Bearer ${response.access_token}`;
            return storeClient(originalRequest);
          }
        }
      } catch (refreshError) {
        // 刷新失败，清除登录状态
        localStorage.removeItem(STORAGE_KEYS.TOOLSTORE_AUTH);
        window.dispatchEvent(new Event('store-unauthorized'));
        return Promise.reject(refreshError);
      }
    }
    
    return Promise.reject(error);
  }
);

export const storeApi = {
  // --- 认证相关 ---
  
  login: async (credentials: { username: string; password: string }): Promise<ToolStoreLoginResponse> => {
    const formData = new URLSearchParams();
    formData.append('username', credentials.username);
    formData.append('password', credentials.password);
    
    const response = await storeClient.post<ToolStoreLoginResponse>('/auth/login', formData, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
    });

    // 登录成功后自动绑定到当前项目
    try {
      await apiClient.post('/v1/store/bind', {
        access_token: response.data.access_token
      });
    } catch (e) {
      console.error('Failed to bind Store credential automatically', e);
    }

    return response.data;
  },

  exchangeCode: async (code: string, codeVerifier: string): Promise<ToolStoreLoginResponse> => {
    const response = await storeClient.post<ToolStoreLoginResponse>('/auth/exchange', null, {
      params: { code, code_verifier: codeVerifier }
    });

    // 交换成功后自动绑定到当前项目
    try {
      await apiClient.post('/v1/store/bind', {
        access_token: response.data.access_token
      });
    } catch (e) {
      console.error('Failed to bind Store credential automatically', e);
    }

    return response.data;
  },

  refreshToken: async (refreshToken: string): Promise<ToolStoreRefreshResponse> => {
    const response = await storeClient.post<ToolStoreRefreshResponse>(`/auth/refresh?refresh_token=${refreshToken}`);
    return response.data;
  },

  logout: async (refreshToken: string): Promise<void> => {
    await storeClient.post(`/auth/logout?refresh_token=${refreshToken}`);
  },

  getMe: async () => {
    const response = await storeClient.get('/auth/me');
    return response.data;
  },

  // --- 工具相关 ---

  getToolCategories: async (): Promise<ToolStoreCategory[]> => {
    const response = await storeClient.get<ToolStoreCategory[]>('/tools/categories');
    return response.data;
  },

  getTools: async (params?: { category?: string; search?: string; skip?: number; limit?: number }) => {
    const response = await storeClient.get<{ items: ToolStoreItem[]; total: number }>('/tools', { params });
    return response.data;
  },

  getTool: async (id: string) => {
    const response = await storeClient.get<ToolStoreItem>(`/tools/${id}`);
    return response.data;
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
    const response = await storeClient.get<any[]>('/models/categories');
    return response.data;
  },

  getModels: async (params?: { category?: string; search?: string; skip?: number; limit?: number }) => {
    const response = await storeClient.get<{ items: any[]; total: number }>('/models', { params });
    return response.data;
  },

  getModel: async (id: string) => {
    const response = await storeClient.get<any>(`/models/${id}`);
    return response.data;
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
};

export default storeApi;
