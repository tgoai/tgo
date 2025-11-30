import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';
import type { KnowledgeBaseItem } from '@/types';
import { KnowledgeBaseApiService } from '@/services/knowledgeBaseApi';
import {
  transformCollectionsToKnowledgeBaseItems,
  transformKnowledgeBaseItemToCreateRequest
} from '@/utils/knowledgeBaseTransforms';

type FilterType = 'all' | 'published' | 'draft' | 'archived';
type SortField = 'title' | 'updatedAt' | 'views' | 'status';
type SortDirection = 'asc' | 'desc';

interface KnowledgeState {
  // 知识库数据
  knowledgeBases: KnowledgeBaseItem[];
  selectedKnowledgeBase: KnowledgeBaseItem | null;
  
  // 搜索和筛选
  searchQuery: string;
  selectedFilter: FilterType;
  quickFilter: string;
  
  // 排序
  sortField: SortField;
  sortDirection: SortDirection;
  
  // 分页
  currentPage: number;
  pageSize: number;
  
  // 加载状态
  isLoading: boolean;
  isCreating: boolean;
  isUpdating: boolean;
  isDeleting: boolean;

  // 错误状态
  error: string | null;
  hasError: boolean;
  
  // Actions
  setKnowledgeBases: (items: KnowledgeBaseItem[]) => void;
  setSelectedKnowledgeBase: (item: KnowledgeBaseItem | null) => void;
  setSearchQuery: (query: string) => void;
  setSelectedFilter: (filter: FilterType) => void;
  setQuickFilter: (filter: string) => void;
  setSorting: (field: SortField, direction: SortDirection) => void;
  setCurrentPage: (page: number) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  clearError: () => void;
  retry: () => Promise<void>;
  
  // CRUD操作
  createKnowledgeBase: (data: Partial<KnowledgeBaseItem>) => Promise<KnowledgeBaseItem | undefined>;
  updateKnowledgeBase: (id: string, updates: Partial<KnowledgeBaseItem>) => Promise<void>;
  deleteKnowledgeBase: (id: string) => Promise<void>;
  duplicateKnowledgeBase: (id: string) => Promise<void>;
  
  // 批量操作
  bulkDelete: (ids: string[]) => Promise<void>;
  bulkUpdateStatus: (ids: string[], status: KnowledgeBaseItem['status']) => Promise<void>;

  // API集成方法
  fetchKnowledgeBases: (params?: {
    limit?: number;
    offset?: number;
    search?: string;
    tags?: string[];
  }) => Promise<void>;
  refreshKnowledgeBases: () => Promise<void>;

  // 计算属性
  getFilteredAndSortedKnowledgeBases: () => KnowledgeBaseItem[];
  getPaginatedKnowledgeBases: () => { items: KnowledgeBaseItem[]; totalPages: number };
  getKnowledgeBaseById: (id: string) => KnowledgeBaseItem | undefined;
  getStatistics: () => {
    total: number;
    published: number;
    draft: number;
    archived: number;
  };
}

export const useKnowledgeStore = create<KnowledgeState>()(
  devtools(
    persist(
      (set, get) => ({
        // 初始状态
        knowledgeBases: [],
        selectedKnowledgeBase: null,
        searchQuery: '',
        selectedFilter: 'all',
        quickFilter: 'recent',
        sortField: 'updatedAt',
        sortDirection: 'desc',
        currentPage: 1,
        pageSize: 10,
        isLoading: false,
        isCreating: false,
        isUpdating: false,
        isDeleting: false,
        error: null,
        hasError: false,

        // Actions
        setKnowledgeBases: (items) => set({ knowledgeBases: items }, false, 'setKnowledgeBases'),
        setSelectedKnowledgeBase: (item) => set({ selectedKnowledgeBase: item }, false, 'setSelectedKnowledgeBase'),
        setSearchQuery: (query) => set({ 
          searchQuery: query, 
          currentPage: 1 
        }, false, 'setSearchQuery'),
        setSelectedFilter: (filter) => set({ 
          selectedFilter: filter, 
          currentPage: 1 
        }, false, 'setSelectedFilter'),
        setQuickFilter: (filter) => set({ 
          quickFilter: filter, 
          currentPage: 1 
        }, false, 'setQuickFilter'),
        setSorting: (field, direction) => set({
          sortField: field,
          sortDirection: direction
        }, false, 'setSorting'),
        setCurrentPage: (page) => set({ currentPage: page }, false, 'setCurrentPage'),
        setLoading: (loading) => set({ isLoading: loading }, false, 'setLoading'),
        setError: (error) => set({
          error,
          hasError: error !== null,
          isLoading: false
        }, false, 'setError'),
        clearError: () => set({
          error: null,
          hasError: false
        }, false, 'clearError'),
        retry: async () => {
          const { refreshKnowledgeBases } = get();
          await refreshKnowledgeBases();
        },

        // API集成方法
        fetchKnowledgeBases: async (params) => {
          set({
            isLoading: true,
            error: null,
            hasError: false
          }, false, 'fetchKnowledgeBases');

          try {
            const response = await KnowledgeBaseApiService.getCollections(params);
            const knowledgeBases = transformCollectionsToKnowledgeBaseItems(response.data || []);

            set({
              knowledgeBases,
              isLoading: false,
              error: null,
              hasError: false
            }, false, 'fetchKnowledgeBasesSuccess');
          } catch (error) {
            console.error('获取知识库列表失败:', error);
            const errorMessage = error instanceof Error ? error.message : '获取知识库列表失败';
            set({
              knowledgeBases: [],
              isLoading: false,
              error: errorMessage,
              hasError: true
            }, false, 'fetchKnowledgeBasesError');
          }
        },

        refreshKnowledgeBases: async () => {
          const { searchQuery, selectedFilter } = get();
          const params: any = {};

          if (searchQuery) params.search = searchQuery;
          if (selectedFilter !== 'all') {
            // Map filter to API parameters if needed
            params.status = selectedFilter;
          }

          await get().fetchKnowledgeBases(params);
        },

        // CRUD操作
        createKnowledgeBase: async (data) => {
          set({
            isCreating: true,
            error: null,
            hasError: false
          }, false, 'createKnowledgeBase');

          try {
            const createRequest = transformKnowledgeBaseItemToCreateRequest(data);
            const newCollection = await KnowledgeBaseApiService.createCollection(createRequest);

            // Transform back to KnowledgeBaseItem and add to list
            const newItem: KnowledgeBaseItem = {
              id: newCollection.id,
              title: newCollection.display_name,
              content: newCollection.description || '',
              category: data.category || 'other',
              tags: data.tags || newCollection.tags || [],
              author: data.author || '当前用户',
              createdAt: newCollection.created_at, // Preserve full timestamp
              updatedAt: newCollection.updated_at, // Preserve full timestamp
              views: 0,
              status: 'published',
              icon: newCollection.collection_metadata?.icon || data.icon,
              type: data.type,
              crawlConfig: data.crawlConfig
            };

            set(
              (state) => ({
                knowledgeBases: [newItem, ...state.knowledgeBases],
                isCreating: false,
                error: null,
                hasError: false
              }),
              false,
              'createKnowledgeBaseSuccess'
            );

            return newItem;
          } catch (error) {
            console.error('创建知识库失败:', error);
            const errorMessage = error instanceof Error ? error.message : '创建知识库失败';
            set({
              isCreating: false,
              error: errorMessage,
              hasError: true
            }, false, 'createKnowledgeBaseError');

            throw error;
          }
        },
        
        updateKnowledgeBase: async (id, updates) => {
          set({
            isUpdating: true,
            error: null,
            hasError: false
          }, false, 'updateKnowledgeBase');

          try {
            // Transform tags to string array
            const tagsArray = Array.isArray(updates.tags)
              ? updates.tags.map(tag => typeof tag === 'string' ? tag : tag.name).filter(Boolean)
              : undefined;

            // Call API to update collection
            const updatedCollection = await KnowledgeBaseApiService.updateCollection(id, {
              display_name: updates.title,
              description: updates.content,
              tags: tagsArray,
              collection_metadata: {
                icon: updates.icon,
              },
            });

            // Update local state with API response
            set(
              (state) => ({
                knowledgeBases: state.knowledgeBases.map(item =>
                  item.id === id
                    ? {
                        ...item,
                        title: updatedCollection.display_name,
                        content: updatedCollection.description || '',
                        updatedAt: updatedCollection.updated_at,
                        icon: updatedCollection.collection_metadata?.icon || undefined,
                        tags: updatedCollection.tags || []
                      }
                    : item
                ),
                selectedKnowledgeBase: state.selectedKnowledgeBase?.id === id
                  ? {
                      ...state.selectedKnowledgeBase,
                      title: updatedCollection.display_name,
                      content: updatedCollection.description || '',
                      updatedAt: updatedCollection.updated_at,
                      icon: updatedCollection.collection_metadata?.icon || undefined,
                      tags: updatedCollection.tags || []
                    }
                  : state.selectedKnowledgeBase,
                isUpdating: false
              }),
              false,
              'updateKnowledgeBaseSuccess'
            );
          } catch (error) {
            console.error('更新知识库失败:', error);
            const errorMessage = error instanceof Error ? error.message : '更新知识库失败';
            set({
              isUpdating: false,
              error: errorMessage,
              hasError: true
            }, false, 'updateKnowledgeBaseError');
            throw error;
          }
        },
        
        deleteKnowledgeBase: async (id) => {
          set({
            isDeleting: true,
            error: null,
            hasError: false
          }, false, 'deleteKnowledgeBase');

          try {
            await KnowledgeBaseApiService.deleteCollection(id);

            set(
              (state) => ({
                knowledgeBases: state.knowledgeBases.filter(item => item.id !== id),
                selectedKnowledgeBase: state.selectedKnowledgeBase?.id === id
                  ? null
                  : state.selectedKnowledgeBase,
                isDeleting: false,
                error: null,
                hasError: false
              }),
              false,
              'deleteKnowledgeBaseSuccess'
            );
          } catch (error) {
            console.error('删除知识库失败:', error);
            const errorMessage = error instanceof Error ? error.message : '删除知识库失败';
            set({
              isDeleting: false,
              error: errorMessage,
              hasError: true
            }, false, 'deleteKnowledgeBaseError');

            throw error;
          }
        },
        
        duplicateKnowledgeBase: async (id) => {
          const { knowledgeBases } = get();
          const original = knowledgeBases.find(item => item.id === id);
          
          if (original) {
            const duplicate: KnowledgeBaseItem = {
              ...original,
              id: Date.now().toString(),
              title: `${original.title} (副本)`,
              createdAt: new Date().toISOString().split('T')[0],
              updatedAt: new Date().toISOString().split('T')[0],
              status: 'draft'
            };
            
            set(
              (state) => ({ 
                knowledgeBases: [duplicate, ...state.knowledgeBases] 
              }),
              false,
              'duplicateKnowledgeBase'
            );
          }
        },
        
        bulkDelete: async (ids) => {
          set({ isDeleting: true }, false, 'bulkDelete');
          
          try {
            set(
              (state) => ({
                knowledgeBases: state.knowledgeBases.filter(item => !ids.includes(item.id)),
                isDeleting: false
              }),
              false,
              'bulkDeleteSuccess'
            );
          } catch (error) {
            console.error('批量删除失败:', error);
            set({ isDeleting: false }, false, 'bulkDeleteError');
          }
        },
        
        bulkUpdateStatus: async (ids, status) => {
          set({ isUpdating: true }, false, 'bulkUpdateStatus');
          
          try {
            set(
              (state) => ({
                knowledgeBases: state.knowledgeBases.map(item =>
                  ids.includes(item.id) 
                    ? { ...item, status, updatedAt: new Date().toISOString().split('T')[0] }
                    : item
                ),
                isUpdating: false
              }),
              false,
              'bulkUpdateStatusSuccess'
            );
          } catch (error) {
            console.error('批量更新状态失败:', error);
            set({ isUpdating: false }, false, 'bulkUpdateStatusError');
          }
        },

        // 计算属性
        getFilteredAndSortedKnowledgeBases: () => {
          const { knowledgeBases, searchQuery, selectedFilter, sortField, sortDirection } = get();
          let filtered = knowledgeBases;

          // 搜索过滤
          if (searchQuery.trim()) {
            filtered = filtered.filter(item =>
              item.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
              item.content.toLowerCase().includes(searchQuery.toLowerCase()) ||
              item.tags.some(tag => 
                typeof tag === 'string' 
                  ? tag.toLowerCase().includes(searchQuery.toLowerCase())
                  : tag.name.toLowerCase().includes(searchQuery.toLowerCase())
              )
            );
          }

          // 状态过滤
          if (selectedFilter !== 'all') {
            filtered = filtered.filter(item => item.status === selectedFilter);
          }

          // 排序
          filtered.sort((a, b) => {
            let aValue: any = a[sortField];
            let bValue: any = b[sortField];

            if (sortField === 'views') {
              aValue = Number(aValue);
              bValue = Number(bValue);
            } else if (sortField === 'updatedAt') {
              aValue = new Date(aValue);
              bValue = new Date(bValue);
            }

            if (sortDirection === 'asc') {
              return aValue > bValue ? 1 : -1;
            } else {
              return aValue < bValue ? 1 : -1;
            }
          });

          return filtered;
        },
        
        getPaginatedKnowledgeBases: () => {
          const { currentPage, pageSize } = get();
          const filtered = get().getFilteredAndSortedKnowledgeBases();
          const totalPages = Math.ceil(filtered.length / pageSize);
          const startIndex = (currentPage - 1) * pageSize;
          const items = filtered.slice(startIndex, startIndex + pageSize);
          
          return { items, totalPages };
        },
        
        getKnowledgeBaseById: (id) => {
          const { knowledgeBases } = get();
          return knowledgeBases.find(item => item.id === id);
        },
        
        getStatistics: () => {
          const { knowledgeBases } = get();
          return {
            total: knowledgeBases.length,
            published: knowledgeBases.filter(item => item.status === 'published').length,
            draft: knowledgeBases.filter(item => item.status === 'draft').length,
            archived: knowledgeBases.filter(item => item.status === 'archived').length
          };
        }
      }),
      {
        name: 'knowledge-store',
        partialize: (state) => ({
          // 持久化用户偏好
          searchQuery: state.searchQuery,
          selectedFilter: state.selectedFilter,
          quickFilter: state.quickFilter,
          sortField: state.sortField,
          sortDirection: state.sortDirection,
          pageSize: state.pageSize
        })
      }
    ),
    { name: 'knowledge-store' }
  )
);
