import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { STORAGE_KEYS } from '@/constants';
import { storeApi } from '@/services/storeApi';
import apiClient from '@/services/api';
import type { ToolStoreUser, LoginFormData } from '@/types';

interface StoreAuthState {
  isAuthenticated: boolean;
  accessToken: string | null;
  refreshToken: string | null;
  user: ToolStoreUser | null;
  isLoading: boolean;
  isVerifying: boolean;
  error: string | null;

  login: (credentials: LoginFormData) => Promise<void>;
  exchangeCode: (code: string, codeVerifier: string) => Promise<void>;
  logout: () => void;
  refreshAccessToken: () => Promise<void>;
  verifySession: () => Promise<boolean>;
  bindToProject: () => Promise<void>;
  clearError: () => void;
}

export const useStoreAuthStore = create<StoreAuthState>()(
  persist(
    (set, get) => ({
      isAuthenticated: false,
      accessToken: null,
      refreshToken: null,
      user: null,
      isLoading: false,
      isVerifying: false,
      error: null,

      login: async (credentials: LoginFormData) => {
        set({ isLoading: true, error: null });
        try {
          const response = await storeApi.login({
            username: credentials.email,
            password: credentials.password,
          });

          set({
            isAuthenticated: true,
            accessToken: response.access_token,
            refreshToken: response.refresh_token,
            user: response.user,
            isLoading: false,
          });
        } catch (error: any) {
          set({
            isLoading: false,
            error: error.response?.data?.detail || '登录失败',
          });
          throw error;
        }
      },

      exchangeCode: async (code: string, codeVerifier: string) => {
        set({ isLoading: true, error: null });
        try {
          const response = await storeApi.exchangeCode(code, codeVerifier);
          set({
            isAuthenticated: true,
            accessToken: response.access_token,
            refreshToken: response.refresh_token,
            user: response.user,
            isLoading: false,
          });
        } catch (error: any) {
          set({
            isLoading: false,
            error: error.response?.data?.detail || '授权码交换失败',
          });
          throw error;
        }
      },

      logout: () => {
        const { refreshToken } = get();
        if (refreshToken) {
          storeApi.logout(refreshToken).catch(console.error);
        }
        set({
          isAuthenticated: false,
          accessToken: null,
          refreshToken: null,
          user: null,
          error: null,
        });
        
        // 同时清理相关的持久化存储
        localStorage.removeItem(STORAGE_KEYS.TOOLSTORE_AUTH);
        localStorage.removeItem(STORAGE_KEYS.TOOLSTORE_TOKEN);
        localStorage.removeItem(STORAGE_KEYS.TOOLSTORE_REFRESH_TOKEN);
      },

      refreshAccessToken: async () => {
        const { refreshToken } = get();
        if (!refreshToken) return;

        try {
          const response = await storeApi.refreshToken(refreshToken);
          set({
            accessToken: response.access_token,
            refreshToken: response.refresh_token,
          });
        } catch (error) {
          set({
            isAuthenticated: false,
            accessToken: null,
            refreshToken: null,
            user: null,
          });
          throw error;
        }
      },

      verifySession: async () => {
        const { accessToken, refreshToken, logout, refreshAccessToken } = get();
        if (!accessToken) return false;

        set({ isVerifying: true });
        try {
          const user = await storeApi.getMe();
          set({ user, isAuthenticated: true, isVerifying: false });
          return true;
        } catch (error: any) {
          // 如果 401 且有 refresh token，尝试刷新
          if (error.response?.status === 401 && refreshToken) {
            try {
              await refreshAccessToken();
              // 刷新成功后再试一次 verify
              const user = await storeApi.getMe();
              set({ user, isAuthenticated: true, isVerifying: false });
              return true;
            } catch (refreshError) {
              logout();
              set({ isVerifying: false });
              return false;
            }
          }
          
          // 其他错误或刷新失败
          logout();
          set({ isVerifying: false });
          return false;
        }
      },

      bindToProject: async () => {
        const { accessToken } = get();
        if (!accessToken) return;

        await apiClient.post('/v1/store/bind', {
          access_token: accessToken,
        });
      },

      clearError: () => set({ error: null }),
    }),
    {
      name: STORAGE_KEYS.TOOLSTORE_AUTH,
      partialize: (state) => ({
        isAuthenticated: state.isAuthenticated,
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        user: state.user,
      }),
    }
  )
);
