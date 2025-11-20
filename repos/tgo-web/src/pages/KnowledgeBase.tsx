import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { RefreshCw, Plus, Search, ArrowUpDown, FolderOpen, Clock, Eye, Pencil, Trash2 } from 'lucide-react';
import { useKnowledgeStore, knowledgeSelectors } from '@/stores';
import { useToast } from '@/hooks/useToast';
import { showKnowledgeBaseSuccess, showKnowledgeBaseError } from '@/utils/toastHelpers';
import { CreateKnowledgeBaseModal } from '@/components/knowledge/CreateKnowledgeBaseModal';
import { EditKnowledgeBaseModal } from '@/components/knowledge/EditKnowledgeBaseModal';
import { formatKnowledgeBaseUpdatedTime } from '@/utils/timeFormatting';
import { getIconComponent, getIconColor } from '@/components/knowledge/IconPicker';
import { getTagClasses } from '@/utils/tagColors';
import type { KnowledgeBaseItem } from '@/types';
import { useTranslation } from 'react-i18next';



/**
 * Knowledge Base management page component
 */
const KnowledgeBase: React.FC = () => {
  const navigate = useNavigate();
  const { showToast } = useToast();
  const { t } = useTranslation();
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [editingKnowledgeBase, setEditingKnowledgeBase] = useState<KnowledgeBaseItem | null>(null);

  const knowledgeBases = useKnowledgeStore(knowledgeSelectors.knowledgeBases);
  const searchQuery = useKnowledgeStore(knowledgeSelectors.searchQuery);
  const isLoading = useKnowledgeStore(state => state.isLoading);
  const error = useKnowledgeStore(state => state.error);
  const hasError = useKnowledgeStore(state => state.hasError);

  const setSearchQuery = useKnowledgeStore(state => state.setSearchQuery);
  const createKnowledgeBase = useKnowledgeStore(state => state.createKnowledgeBase);
  const updateKnowledgeBase = useKnowledgeStore(state => state.updateKnowledgeBase);
  const deleteKnowledgeBase = useKnowledgeStore(state => state.deleteKnowledgeBase);
  const fetchKnowledgeBases = useKnowledgeStore(state => state.fetchKnowledgeBases);
  const refreshKnowledgeBases = useKnowledgeStore(state => state.refreshKnowledgeBases);
  const clearError = useKnowledgeStore(state => state.clearError);
  const retry = useKnowledgeStore(state => state.retry);

  // 初始化时获取知识库数据
  useEffect(() => {
    const loadData = async () => {
      try {
        await fetchKnowledgeBases();
      } catch (error) {
        console.error('Failed to load knowledge bases:', error);
        // Error is already handled in the store
      }
    };

    loadData();
  }, [fetchKnowledgeBases]);

  // 搜索变化时重新获取数据
  useEffect(() => {
    const loadFilteredData = async () => {
      try {
        const params: any = {};
        if (searchQuery) params.search = searchQuery;

        await fetchKnowledgeBases(params);
      } catch (error) {
        console.error('Failed to load filtered knowledge bases:', error);
        // Error is already handled in the store
      }
    };

    loadFilteredData();
  }, [searchQuery, fetchKnowledgeBases]);

  // 在组件中计算过滤和排序（移除分页和状态过滤）
  const filteredKnowledgeBases = React.useMemo(() => {
    let filtered = knowledgeBases;

    // 搜索过滤
    if (searchQuery.trim()) {
      filtered = filtered.filter((kb: KnowledgeBaseItem) =>
        kb.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        kb.content.toLowerCase().includes(searchQuery.toLowerCase())
      );
    }

    // 排序 - 按最近更新时间降序排列
    filtered.sort((a: KnowledgeBaseItem, b: KnowledgeBaseItem) => {
      const aDate = new Date(a.updatedAt);
      const bDate = new Date(b.updatedAt);

      // Handle invalid dates by putting them at the end
      if (isNaN(aDate.getTime()) && isNaN(bDate.getTime())) return 0;
      if (isNaN(aDate.getTime())) return 1;
      if (isNaN(bDate.getTime())) return -1;

      return bDate.getTime() - aDate.getTime();
    });

    return filtered;
  }, [knowledgeBases, searchQuery]);

  const handleCreateKnowledgeBase = async (data: { name: string; description: string; icon: string; tags: string[] }): Promise<void> => {
    try {
      await createKnowledgeBase({
        title: data.name,
        content: data.description,
        category: 'general',
        icon: data.icon,
        tags: data.tags
      });
      showKnowledgeBaseSuccess(showToast, 'create', data.name);
    } catch (error) {
      console.error('Failed to create knowledge base:', error);
      showKnowledgeBaseError(showToast, 'create', error, data.name);
      throw error; // Re-throw to let modal handle the error
    }
  };

  const handleOpenCreateModal = (): void => {
    setIsCreateModalOpen(true);
  };

  const handleCloseCreateModal = (): void => {
    setIsCreateModalOpen(false);
  };

  const handleEditKnowledgeBase = async (id: string, data: { name: string; description: string; icon: string; tags: string[] }): Promise<void> => {
    try {
      await updateKnowledgeBase(id, {
        title: data.name,
        content: data.description,
        icon: data.icon,
        tags: data.tags
      });
      showKnowledgeBaseSuccess(showToast, 'update', data.name);
    } catch (error) {
      console.error('Failed to update knowledge base:', error);
      showKnowledgeBaseError(showToast, 'update', error, data.name);
      throw error; // Re-throw to let modal handle the error
    }
  };

  const handleOpenEditModal = (knowledgeBase: KnowledgeBaseItem): void => {
    setEditingKnowledgeBase(knowledgeBase);
    setIsEditModalOpen(true);
  };

  const handleCloseEditModal = (): void => {
    setIsEditModalOpen(false);
    setEditingKnowledgeBase(null);
  };

  const handleRefresh = async (): Promise<void> => {
    try {
      clearError(); // Clear any existing errors
      await refreshKnowledgeBases();
    } catch (error) {
      console.error('Failed to refresh knowledge bases:', error);
      // Error is already handled in the store
    }
  };

  const handleKnowledgeBaseAction = async (actionType: string, knowledgeBase: KnowledgeBaseItem): Promise<void> => {
    switch (actionType) {
      case 'edit':
        handleOpenEditModal(knowledgeBase);
        break;
      case 'delete':
        if (confirm(t('knowledge.confirmDelete.message', { name: knowledgeBase.title, defaultValue: `确定要删除知识库 "${knowledgeBase.title}" 吗？此操作无法撤销。` }))) {
          try {
            await deleteKnowledgeBase(knowledgeBase.id);
            showKnowledgeBaseSuccess(showToast, 'delete', knowledgeBase.title);
          } catch (error) {
            console.error('Failed to delete knowledge base:', error);
            showKnowledgeBaseError(showToast, 'delete', error, knowledgeBase.title);
          }
        }
        break;
      default:
        console.log('Unknown action:', actionType);
    }
  };

  const handleSearchChange = (query: string): void => {
    setSearchQuery(query);
  };



  // Navigate to knowledge base detail view
  const handleKnowledgeBaseClick = (knowledgeBase: KnowledgeBaseItem): void => {
    navigate(`/knowledge/${knowledgeBase.id}`);
  };

  return (
    <main className="flex-grow flex flex-col bg-gradient-to-br from-gray-50 to-gray-100">
      {/* Header */}
      <header className="px-6 py-4 border-b border-gray-200/80 sticky top-0 bg-white/60 backdrop-blur-lg z-10">
        <div className="flex justify-between items-center">
          <div>
            <h2 className="text-lg font-semibold text-gray-800">{t('knowledge.manage', '知识库管理')}</h2>
            <p className="text-sm text-gray-500 mt-0.5">{t('knowledge.subtitle', '管理可供智能体使用的知识来源。')}</p>
          </div>
          <div className="flex items-center space-x-3">
            <button
              className="p-1.5 text-gray-500 hover:bg-gray-200/70 rounded-md transition-colors duration-200"
              title={t('knowledge.detail.refresh', '刷新')}
              onClick={handleRefresh}
            >
              <RefreshCw className="w-5 h-5" />
            </button>
            <button
              className="flex items-center px-3 py-1.5 bg-blue-500 text-white text-sm rounded-md hover:bg-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1 transition-colors duration-200"
              onClick={handleOpenCreateModal}
            >
              <Plus className="w-4 h-4 mr-1" />
              <span>{t('knowledge.create', '创建知识库')}</span>
            </button>
          </div>
        </div>

        {/* Search and Filters */}
        <div className="mt-4 flex flex-col md:flex-row md:items-center md:justify-between gap-3">
          <div className="relative flex-grow max-w-xs">
            <input
              type="text"
              placeholder={t('knowledge.selectModal.searchPlaceholder', '搜索知识库...')}
              value={searchQuery}
              onChange={(e) => handleSearchChange(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 text-sm border border-gray-300/70 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500 bg-white/80"
            />
            <Search className="w-4 h-4 absolute left-2.5 top-1/2 transform -translate-y-1/2 text-gray-400" />
          </div>

        </div>


      </header>

      {/* Content Area: Knowledge Base List */}
      <div className="flex-grow overflow-y-auto p-6" style={{ height: 0 }}>
        <div className="bg-white/80 backdrop-blur-md rounded-lg shadow-sm border border-gray-200/60 overflow-hidden">
          {/* Table Header */}
          <div className="grid grid-cols-[minmax(0,_3fr)_1fr_1fr_auto] gap-4 px-4 py-2 border-b border-gray-200/60 bg-gray-50/50">
            <div className="text-xs font-medium text-gray-500 uppercase tracking-wider flex items-center cursor-pointer hover:text-gray-700">
              {t('knowledge.list.columns.name', '名称')} <ArrowUpDown className="w-3 h-3 ml-1" />
            </div>
            <div className="text-xs font-medium text-gray-500 uppercase tracking-wider flex items-center cursor-pointer hover:text-gray-700">
              {t('knowledge.list.columns.documents', '文档数量')} <ArrowUpDown className="w-3 h-3 ml-1" />
            </div>
            <div className="text-xs font-medium text-gray-500 uppercase tracking-wider flex items-center cursor-pointer hover:text-gray-700">
              {t('knowledge.list.columns.lastUpdated', '最近更新')} <ArrowUpDown className="w-3 h-3 ml-1" />
            </div>
            <div className="text-xs font-medium text-gray-500 uppercase tracking-wider text-right pr-2">
              {t('knowledge.list.columns.actions', '操作')}
            </div>
          </div>

          {/* Table Body */}
          <div>
            {isLoading ? (
              <div className="text-center py-12">
                <div className="inline-flex items-center">
                  <RefreshCw className="w-5 h-5 animate-spin text-blue-500 mr-2" />
                  <span className="text-gray-500">{t('common.loading', '加载中...')}</span>
                </div>
              </div>
            ) : hasError ? (
              <div className="text-center py-12">
                <div className="w-16 h-16 mx-auto bg-red-100 rounded-full flex items-center justify-center mb-4">
                  <svg className="w-8 h-8 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
                <h3 className="text-lg font-medium text-gray-800 mb-2">{t('common.loadFailed', '加载失败')}</h3>
                <p className="text-gray-500 mb-4">{error || t('knowledge.list.loadFailedDesc', '获取知识库列表时发生错误')}</p>
                <div className="flex justify-center space-x-3">
                  <button
                    onClick={retry}
                    className="inline-flex items-center px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors"
                  >
                    <RefreshCw className="w-4 h-4 mr-2" />
                    {t('common.retry', '重试')}
                  </button>
                  <button
                    onClick={clearError}
                    className="inline-flex items-center px-4 py-2 bg-gray-500 text-white rounded-lg hover:bg-gray-600 transition-colors"
                  >
                    {t('knowledge.error.clear', '清除错误')}
                  </button>
                </div>
              </div>
            ) : filteredKnowledgeBases.length === 0 ? (
              <div className="text-center py-12">
                <FolderOpen className="w-16 h-16 mx-auto text-gray-300 mb-4" />
                <h3 className="text-lg font-medium text-gray-800 mb-2">{t('knowledge.empty.title', '暂无知识库')}</h3>
                <p className="text-gray-500 mb-4">{t('knowledge.empty.description', '创建您的第一个知识库开始使用')}</p>
                <button
                  onClick={handleOpenCreateModal}
                  className="inline-flex items-center px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors"
                >
                  <Plus className="w-4 h-4 mr-2" />
                  {t('knowledge.create', '创建知识库')}
                </button>
              </div>
            ) : (
              filteredKnowledgeBases.map((kb: KnowledgeBaseItem, index: number) => (
              <div
                key={kb.id}
                className={`grid grid-cols-[minmax(0,_3fr)_1fr_1fr_auto] gap-4 px-4 py-3 items-center hover:bg-gray-50/30 transition-colors ${
                  index < filteredKnowledgeBases.length - 1 ? 'border-b border-gray-200/60' : ''
                }`}
              >
                <div
                  className="flex items-start space-x-3 cursor-pointer hover:bg-blue-50/50 -mx-2 px-2 py-1 rounded transition-all duration-200 group"
                  onClick={() => handleKnowledgeBaseClick(kb)}
                >
                  {(() => {
                    const IconComponent = getIconComponent(kb.icon);
                    const iconColor = getIconColor(kb.icon);
                    return (
                      <IconComponent
                        className={`w-5 h-5 flex-shrink-0 mt-0.5 transition-colors duration-200 ${iconColor} hover:opacity-80`}
                      />
                    );
                  })()}
                  <div>
                    <p className="text-sm font-medium text-gray-800 group-hover:text-blue-600 transition-colors duration-200">{kb.title}</p>
                    <p className="text-xs text-gray-500 mt-1 leading-snug">{kb.content}</p>
                    <div className="mt-1.5 flex flex-wrap gap-1.5">
                      {kb.tags.map((tag: any, tagIndex: number) => {
                        const tagName = typeof tag === 'string' ? tag : tag.name;
                        return (
                          <span
                            key={tagIndex}
                            className={getTagClasses(tagName, {
                              size: 'sm',
                              includeHover: false,
                              includeBorder: false,
                              rounded: true
                            })}
                            style={{ fontSize: '10px' }} // Override for extra small size
                          >
                            {tagName}
                          </span>
                        );
                      })}
                    </div>
                  </div>
                </div>
                <div className="text-sm text-gray-600">{t('knowledge.filesCount', { count: kb.fileCount, defaultValue: `${kb.fileCount} 文件` })}</div>
                <div className="text-sm text-gray-600 flex items-center">
                  <Clock className="w-3.5 h-3.5 mr-1 text-gray-400" />
                  {formatKnowledgeBaseUpdatedTime(kb.updatedAt)}
                </div>

                <div className="flex justify-end space-x-2">
                  <button
                    className="text-gray-400 hover:text-blue-600 transition-colors"
                    title={t('common.details', '详情')}
                    onClick={() => navigate(`/knowledge/${kb.id}`)}
                  >
                    <Eye className="w-4 h-4" />
                  </button>

                  <button
                    className="text-gray-400 hover:text-blue-600 transition-colors"
                    title={t('common.edit', '编辑')}
                    onClick={() => handleKnowledgeBaseAction('edit', kb)}
                  >
                    <Pencil className="w-4 h-4" />
                  </button>

                  <button
                    className="text-gray-400 hover:text-red-600 transition-colors"
                    title={t('common.delete', '删除')}
                    onClick={() => handleKnowledgeBaseAction('delete', kb)}
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
              ))
            )}
          </div>
        </div>


      </div>

      {/* Create Knowledge Base Modal */}
      <CreateKnowledgeBaseModal
        isOpen={isCreateModalOpen}
        onClose={handleCloseCreateModal}
        onSubmit={handleCreateKnowledgeBase}
        isLoading={isLoading}
      />

      {/* Edit Knowledge Base Modal */}
      <EditKnowledgeBaseModal
        isOpen={isEditModalOpen}
        onClose={handleCloseEditModal}
        onSubmit={handleEditKnowledgeBase}
        knowledgeBase={editingKnowledgeBase}
        isLoading={isLoading}
      />
    </main>
  );
};

export default KnowledgeBase;
