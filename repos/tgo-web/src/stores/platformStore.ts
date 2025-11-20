import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';
import type { Platform, PlatformConfig, PlatformType } from '@/types';
import platformsApiService, { PlatformResponse } from '@/services/platformsApi';
import { useOnboardingStore } from './onboardingStore';

interface PlatformState {
  // 平台数据
  platforms: Platform[];
  selectedPlatform: Platform | null;

  // 搜索和筛选
  searchQuery: string;
  statusFilter: 'all' | 'connected' | 'error' | 'pending' | 'disabled';
  typeFilter: 'all' | 'website' | 'wechat' | 'tiktok' | 'email' | 'phone' | 'custom';

  // 加载状态
  isLoading: boolean;
  isConnecting: boolean;
  isUpdating: boolean;
  isDeleting: boolean;
  loadError: string | null;
  isLoadingDetail: boolean;
  detailLoadError: string | null;

  // 配置状态
  configChanges: Record<string, Partial<PlatformConfig>>;
  hasUnsavedChanges: boolean;

  // Actions
  setPlatforms: (platforms: Platform[]) => void;
  setSelectedPlatform: (platform: Platform | null) => void;
  setSearchQuery: (query: string) => void;
  setStatusFilter: (filter: PlatformState['statusFilter']) => void;
  setTypeFilter: (filter: PlatformState['typeFilter']) => void;
  setLoading: (loading: boolean) => void;

  // 平台操作
  createPlatform: (platformData: Partial<Platform>) => Promise<Platform>;
  updatePlatform: (platformId: string, updates: Partial<Platform>) => Promise<void>;
  deletePlatform: (platformId: string) => Promise<void>;
  enablePlatform: (platformId: string) => Promise<void>;
  disablePlatform: (platformId: string) => Promise<void>;
  togglePlatformStatus: (platformId: string) => Promise<void>;
  testPlatformConnection: (platformId: string) => Promise<boolean>;

  // 配置操作
  updatePlatformConfig: (platformId: string, config: Partial<PlatformConfig>) => void;
  savePlatformConfig: (platformId: string) => Promise<void>;

  // 明细拉取与密钥
  fetchPlatformById: (platformId: string) => Promise<void>;
  regenerateApiKey: (platformId: string) => Promise<void>;

  // Initialization
  initializeStore: () => Promise<void>;
  resetPlatformConfig: (platformId: string) => void;
  generateWebhookSecret: (platformId: string) => string;

  // 计算属性
  getFilteredPlatforms: () => Platform[];
  getPlatformById: (platformId: string) => Platform | undefined;
  getPlatformStatistics: () => {
    total: number;
    connected: number;
    error: number;
    pending: number;
    disabled: number;
  };
  hasConfigChanges: (platformId: string) => boolean;
}

export const usePlatformStore = create<PlatformState>()(
  devtools(
    persist(
      (set, get) => ({
        // 初始状态 - empty arrays, will be populated in development with mock data
        platforms: [],
        selectedPlatform: null,
        searchQuery: '',
        statusFilter: 'all',
        typeFilter: 'all',
        isLoading: false,
        isConnecting: false,
        isUpdating: false,
        isDeleting: false,
        loadError: null,
        isLoadingDetail: false,
        detailLoadError: null,
        configChanges: {},
        hasUnsavedChanges: false,

        // Actions
        setPlatforms: (platforms) => set({ platforms }, false, 'setPlatforms'),
        setSelectedPlatform: (platform) => set({ selectedPlatform: platform }, false, 'setSelectedPlatform'),
        setSearchQuery: (query) => set({ searchQuery: query }, false, 'setSearchQuery'),
        setStatusFilter: (filter) => set({ statusFilter: filter }, false, 'setStatusFilter'),
        setTypeFilter: (filter) => set({ typeFilter: filter }, false, 'setTypeFilter'),
        setLoading: (loading) => set({ isLoading: loading }, false, 'setLoading'),

        // 平台操作
        createPlatform: async (platformData) => {
          set({ isLoading: true }, false, 'createPlatform');

          try {
            // Prepare request body according to API schema
            const name = platformData.name || '新平台';
            const type = (platformData.type as PlatformType) || 'custom';
            const config = (platformData.config as Record<string, any>) || undefined;

            const apiResp: PlatformResponse = await platformsApiService.createPlatform({
              name,
              type,
              config,
              is_active: true,
            });

            // Map API response to UI Platform type
            const createdPlatform: Platform = {
              id: apiResp.id,
              name: apiResp.name,
              icon: platformData.icon || 'Webhook',
              iconColor: platformData.iconColor || 'text-gray-500',
              status: 'unconfigured',
              statusText: '未配置',
              statusColor: 'bg-gray-400',
              type: apiResp.type as PlatformType,
              description: platformData.description || '',
              config: ({ ...(apiResp.config || {}), ...(apiResp.api_key ? { apiKey: apiResp.api_key } : {}) }) as PlatformConfig,
              callback_url: (apiResp as any).callback_url || '',
              logo_url: (apiResp as any).logo_url ?? null,
            };

            set(
              (state) => ({
                platforms: [createdPlatform, ...state.platforms],
                isLoading: false
              }),
              false,
              'createPlatformSuccess'
            );

            // Mark onboarding task as completed
            try {
              useOnboardingStore.getState().markTaskCompleted('platformCreated');
            } catch (error) {
              console.error('Failed to mark onboarding task completed:', error);
            }

            return createdPlatform;
          } catch (error) {
            console.error('创建平台失败:', error);
            set({ isLoading: false }, false, 'createPlatformError');
            throw error;
          }
        },

        updatePlatform: async (platformId, updates) => {
          set({ isUpdating: true }, false, 'updatePlatform');
          try {
            // Map UI updates to API payload
            const payload: any = {};
            if (Object.prototype.hasOwnProperty.call(updates, 'name')) {
              payload.name = updates.name;
            }
            if (Object.prototype.hasOwnProperty.call(updates, 'config')) {
              payload.config = updates.config as Record<string, any>;
            }
            if (Object.prototype.hasOwnProperty.call(updates, 'status')) {
              payload.is_active = updates.status === 'connected';
            }

            let apiResp: PlatformResponse | null = null;
            if (Object.keys(payload).length > 0) {
              apiResp = await platformsApiService.updatePlatform(platformId, payload);
            }

            set(
              (state) => {
                // If server responded, prefer its values; otherwise apply local updates
                const mapRespToUI = (p: PlatformResponse): Platform => {
                  const status = p.is_active ? 'connected' as const : 'disabled' as const;
                  const statusText = p.is_active ? '已连接' : '已禁用';
                  const statusColor = p.is_active ? 'bg-green-500' : 'bg-gray-400';
                  return {
                    id: p.id,
                    name: p.name,
                    icon: (p as any).icon || '',
                    iconColor: '',
                    status,
                    statusText,
                    statusColor,
                    type: (p as any).type as any,
                    description: state.platforms.find(pp => pp.id === p.id)?.description || '',
                    config: ({ ...(p.config || {}), ...(p.api_key ? { apiKey: p.api_key } : {}) }) as PlatformConfig,
                    callback_url: (p as any).callback_url || '',
                    logo_url: (p as any).logo_url ?? null,
                  };
                };

                const applyUpdate = (old: Platform): Platform => {
                  if (apiResp) return mapRespToUI(apiResp);
                  return { ...old, ...updates } as Platform;
                };

                const newPlatforms = state.platforms.map(platform =>
                  platform.id === platformId ? applyUpdate(platform) : platform
                );

                const newSelected = state.selectedPlatform?.id === platformId
                  ? applyUpdate(state.selectedPlatform)
                  : state.selectedPlatform;

                return { platforms: newPlatforms, selectedPlatform: newSelected, isUpdating: false };
              },
              false,
              'updatePlatformSuccess'
            );
          } catch (error) {
            console.error('更新平台失败:', error);
            set({ isUpdating: false }, false, 'updatePlatformError');
            throw error;
          }
        },

        fetchPlatformById: async (platformId: string) => {
          set({ isLoadingDetail: true, detailLoadError: null }, false, 'fetchPlatformByIdStart');
          try {
            const p = await platformsApiService.getPlatformById(platformId);
            const state = get();
            const status = p.is_active ? 'connected' as const : 'disabled' as const;
            const statusText = p.is_active ? '已连接' : '已禁用';
            const statusColor = p.is_active ? 'bg-green-500' : 'bg-gray-400';
            const mapped: Platform = {
              id: p.id,
              name: p.name,
              display_name: (p as any).display_name,
              icon: (p as any).icon || '',
              iconColor: '',
              status,
              statusText,
              statusColor,
              type: (p as any).type as any,
              is_supported: (p as any).is_supported,
              description: state.platforms.find(pp => pp.id === p.id)?.description || '',
              config: ({ ...(p.config || {}), ...(p.api_key ? { apiKey: p.api_key } : {}) }) as PlatformConfig,
              callback_url: (p as any).callback_url || '',
              logo_url: (p as any).logo_url ?? null,
              chat_url: (p as any).chat_url ?? null,
            };
            set({
              platforms: state.platforms.some(pp => pp.id === platformId)
                ? state.platforms.map(pp => (pp.id === platformId ? mapped : pp))
                : [mapped, ...state.platforms],
              selectedPlatform: mapped, // Always update selectedPlatform when fetching detail
              isLoadingDetail: false,
              detailLoadError: null,
            }, false, 'fetchPlatformByIdSuccess');
          } catch (error) {
            console.error('获取平台详情失败:', error);
            set({
              isLoadingDetail: false,
              detailLoadError: (error as Error).message || '加载平台详情失败'
            }, false, 'fetchPlatformByIdError');
            throw error; // Re-throw to allow caller to handle
          }
        },

        regenerateApiKey: async (platformId: string) => {
          set({ isUpdating: true }, false, 'regenerateApiKey');
          try {
            const resp = await platformsApiService.regenerateApiKey(platformId); // { id, api_key }
            set((state) => {
              // 找到目标平台，仅更新 config.apiKey，不改变其它字段
              const platforms = state.platforms.map((p) => {
                if (p.id !== platformId) return p;
                return {
                  ...p,
                  config: ({ ...(p.config || {}), apiKey: resp.api_key }) as PlatformConfig,
                } as Platform;
              });
              const selected = state.selectedPlatform?.id === platformId
                ? ({
                    ...state.selectedPlatform!,
                    config: ({ ...(state.selectedPlatform!.config || {}), apiKey: resp.api_key }) as PlatformConfig,
                  } as Platform)
                : state.selectedPlatform;
              return { platforms, selectedPlatform: selected, isUpdating: false };
            }, false, 'regenerateApiKeySuccess');
          } catch (error) {
            console.error('重新生成 API Key 失败:', error);
            set({ isUpdating: false }, false, 'regenerateApiKeyError');
            throw error;
          }
        },

        deletePlatform: async (platformId) => {
          set({ isDeleting: true }, false, 'deletePlatform');

          try {
            // Call backend API to delete
            await platformsApiService.deletePlatform(platformId);

            set(
              (state) => {
                const idx = state.platforms.findIndex(p => p.id === platformId);
                const newPlatforms = state.platforms.filter(platform => platform.id !== platformId);
                // Determine next selected platform according to priority
                let nextSelected: Platform | null = null;
                if (newPlatforms.length > 0 && idx !== -1) {
                  if (idx < newPlatforms.length) {
                    nextSelected = newPlatforms[idx]; // next item at same index after removal
                  } else if (idx - 1 >= 0) {
                    nextSelected = newPlatforms[idx - 1]; // previous item if deleted was last
                  }
                }
                return {
                  platforms: newPlatforms,
                  selectedPlatform: nextSelected,
                  isDeleting: false
                };
              },
              false,
              'deletePlatformSuccess'
            );
          } catch (error) {
            console.error('删除平台失败:', error);
            set({ isDeleting: false }, false, 'deletePlatformError');
            throw error;
          }
        },

        enablePlatform: async (platformId) => {
          try {
            await platformsApiService.enablePlatform(platformId);
            set((state) => {
              const map = (p: Platform): Platform => ({
                ...p,
                status: 'connected',
                statusText: '已连接',
                statusColor: 'bg-green-500',
              });
              return {
                platforms: state.platforms.map(p => p.id === platformId ? map(p) : p),
                selectedPlatform: state.selectedPlatform?.id === platformId ? map(state.selectedPlatform) : state.selectedPlatform,
              };
            }, false, 'enablePlatformSuccess');
          } catch (error) {
            console.error('启用平台失败:', error);
            throw error;
          }
        },

        disablePlatform: async (platformId) => {
          try {
            await platformsApiService.disablePlatform(platformId);
            set((state) => {
              const map = (p: Platform): Platform => ({
                ...p,
                status: 'disabled',
                statusText: '已禁用',
                statusColor: 'bg-gray-400',
              });
              return {
                platforms: state.platforms.map(p => p.id === platformId ? map(p) : p),
                selectedPlatform: state.selectedPlatform?.id === platformId ? map(state.selectedPlatform) : state.selectedPlatform,
              };
            }, false, 'disablePlatformSuccess');
          } catch (error) {
            console.error('禁用平台失败:', error);
            throw error;
          }
        },

        togglePlatformStatus: async (platformId) => {
          set({ isConnecting: true }, false, 'togglePlatformStatus');

          try {
            const { platforms } = get();
            const platform = platforms.find(c => c.id === platformId);

            if (platform) {
              const newStatus = platform.status === 'connected' ? 'disabled' : 'connected';
              const newStatusText = newStatus === 'connected' ? '已连接' : '已禁用';
              const newStatusColor = newStatus === 'connected' ? 'bg-green-500' : 'bg-gray-400';

              await get().updatePlatform(platformId, {
                status: newStatus,
                statusText: newStatusText,
                statusColor: newStatusColor
              });
            }

            set({ isConnecting: false }, false, 'togglePlatformStatusSuccess');
          } catch (error) {
            console.error('切换平台状态失败:', error);
            set({ isConnecting: false }, false, 'togglePlatformStatusError');
          }
        },

        testPlatformConnection: async (platformId) => {
          set({ isConnecting: true }, false, 'testPlatformConnection');

          try {
            // 模拟连接测试
            await new Promise(resolve => setTimeout(resolve, 2000));

            const isSuccess = Math.random() > 0.3; // 70% 成功率

            if (isSuccess) {
              await get().updatePlatform(platformId, {
                status: 'connected',
                statusText: '已连接',
                statusColor: 'bg-green-500'
              });
            } else {
              await get().updatePlatform(platformId, {
                status: 'error',
                statusText: '连接失败',
                statusColor: 'bg-red-500'
              });
            }

            set({ isConnecting: false }, false, 'testPlatformConnectionComplete');
            return isSuccess;
          } catch (error) {
            console.error('测试连接失败:', error);
            set({ isConnecting: false }, false, 'testPlatformConnectionError');
            return false;
          }
        },

        // 配置操作
        updatePlatformConfig: (platformId, config) => {
          set(
            (state) => ({
              configChanges: {
                ...state.configChanges,
                [platformId]: {
                  ...state.configChanges[platformId],
                  ...config
                }
              },
              hasUnsavedChanges: true
            }),
            false,
            'updatePlatformConfig'
          );
        },

        savePlatformConfig: async (platformId) => {
          const { configChanges } = get();
          const changes = configChanges[platformId];

          if (changes) {
            await get().updatePlatform(platformId, { config: changes });

            set(
              (state) => {
                const newConfigChanges = { ...state.configChanges };
                delete newConfigChanges[platformId];
                return {
                  configChanges: newConfigChanges,
                  hasUnsavedChanges: Object.values(newConfigChanges).some(Boolean)
                };
              },
              false,
              'savePlatformConfig'
            );
          }
        },

        resetPlatformConfig: (platformId) => {
          set(
            (state) => {
              const newConfigChanges = { ...state.configChanges };
              delete newConfigChanges[platformId];
              return {
                configChanges: newConfigChanges,
                hasUnsavedChanges: Object.values(newConfigChanges).some(Boolean)
              };
            },
            false,
            'resetPlatformConfig'
          );
        },

        generateWebhookSecret: (platformId) => {
          const secret = `sk_${Date.now()}_${Math.random().toString(36).slice(2, 11)}`;

          get().updatePlatformConfig(platformId, {
            secretKey: secret
          });

          return secret;
        },

        // 计算属性
        getFilteredPlatforms: () => {
          const { platforms, searchQuery, statusFilter, typeFilter } = get();
          let filtered = platforms;

          // 搜索过滤
          if (searchQuery.trim()) {
            filtered = filtered.filter(platform =>
              platform.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
              platform.description.toLowerCase().includes(searchQuery.toLowerCase())
            );
          }

          // 状态过滤
          if (statusFilter !== 'all') {
            filtered = filtered.filter(platform => platform.status === statusFilter);
          }

          // 类型过滤
          if (typeFilter !== 'all') {
            filtered = filtered.filter(platform => platform.type === typeFilter);
          }

          return filtered;
        },

        getPlatformById: (platformId) => {
          const { platforms } = get();
          return platforms.find(platform => platform.id === platformId);
        },

        getPlatformStatistics: () => {
          const { platforms } = get();
          return {
            total: platforms.length,
            connected: platforms.filter(c => c.status === 'connected').length,
            error: platforms.filter(c => c.status === 'error').length,
            pending: platforms.filter(c => c.status === 'pending').length,
            disabled: platforms.filter(c => c.status === 'disabled').length
          };
        },

        hasConfigChanges: (platformId) => {
          const { configChanges } = get();
          return Boolean(configChanges[platformId]);
        },

        // Initialize store with backend data
        initializeStore: async () => {
          set({ isLoading: true, loadError: null }, false, 'initializeStoreStart');

          try {
            const pageSize = 50;
            let offset = 0;
            let hasNext = true;
            const all: Platform[] = [];

            while (hasNext) {
              const resp = await platformsApiService.listPlatforms({ limit: pageSize, offset });
              const items = resp.data;

              // Map API responses directly; use API-provided icon (raw SVG) and type
              const mapped: Platform[] = items.map((p) => {
                const status = p.is_active ? 'connected' as const : 'disabled' as const;
                const statusText = p.is_active ? '已连接' : '已禁用';
                const statusColor = p.is_active ? 'bg-green-500' : 'bg-gray-400';

                return {
                  id: p.id,
                  name: p.name,
                  display_name: (p as any).display_name,
                  icon: (p as any).icon || '',
                  iconColor: '',
                  status,
                  statusText,
                  statusColor,
                  type: (p as any).type as any,
                  is_supported: (p as any).is_supported,
                  description: '',
                  config: ({ ...(p.config || {}), ...(p.api_key ? { apiKey: p.api_key } : {}) }) as PlatformConfig,
                  callback_url: (p as any).callback_url || '',
                  logo_url: (p as any).logo_url ?? null,
                };
              });

              all.push(...mapped);
              hasNext = resp.pagination?.has_next ?? false;
              if (hasNext) {
                offset += pageSize;
              }
            }

            set({ platforms: all, isLoading: false, loadError: null }, false, 'initializeStoreSuccess');
          } catch (error) {
            console.error('加载平台列表失败:', error);
            set({ isLoading: false, loadError: error instanceof Error ? error.message : '加载失败' }, false, 'initializeStoreError');
          }
        }
      }),
      {
        name: 'platform-store',
        partialize: (state) => ({
          // 持久化用户偏好
          searchQuery: state.searchQuery,
          statusFilter: state.statusFilter,
          typeFilter: state.typeFilter
        })
      }
    ),
    { name: 'platform-store' }
  )
);

