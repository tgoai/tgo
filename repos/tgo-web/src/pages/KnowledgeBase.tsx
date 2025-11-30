import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { RefreshCw, Plus, Search, ArrowUpDown, FolderOpen, Clock, Eye, Pencil, Trash2, FileText, Globe, Play, XCircle, Loader2 } from 'lucide-react';
import { useKnowledgeStore, knowledgeSelectors } from '@/stores';
import { useToast } from '@/hooks/useToast';
import { showKnowledgeBaseSuccess, showKnowledgeBaseError } from '@/utils/toastHelpers';
import { CreateKnowledgeBaseModal, type CreateKnowledgeBaseData } from '@/components/knowledge/CreateKnowledgeBaseModal';
import { EditKnowledgeBaseModal } from '@/components/knowledge/EditKnowledgeBaseModal';
import { formatKnowledgeBaseUpdatedTime } from '@/utils/timeFormatting';
import { getIconComponent, getIconColor } from '@/components/knowledge/IconPicker';
import { getTagClasses } from '@/utils/tagColors';
import type { KnowledgeBaseItem, CrawlJobStatus } from '@/types';
import { useTranslation } from 'react-i18next';
import KnowledgeBaseApiService from '@/services/knowledgeBaseApi';



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
  const [crawlingKbs, setCrawlingKbs] = useState<Set<string>>(new Set()); // Track which KBs are being crawled

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

  const handleCreateKnowledgeBase = async (data: CreateKnowledgeBaseData): Promise<void> => {
    try {
      const newKb = await createKnowledgeBase({
        title: data.name,
        content: data.description,
        category: 'general',
        icon: data.icon,
        tags: data.tags,
        type: data.type,
        crawlConfig: data.crawlConfig
      });
      showKnowledgeBaseSuccess(showToast, 'create', data.name);

      // If it's a website type, automatically start crawling
      if (data.type === 'website' && data.crawlConfig && newKb?.id) {
        try {
          await KnowledgeBaseApiService.createCrawlJob(newKb.id, data.crawlConfig);
          showToast(
            'success',
            t('knowledge.crawl.started', '爬取已开始'),
            t('knowledge.crawl.startedDesc', '网站爬取任务已启动')
          );
        } catch (crawlError) {
          console.error('Failed to start crawl job:', crawlError);
          showToast(
            'warning',
            t('knowledge.crawl.startFailed', '爬取启动失败'),
            t('knowledge.crawl.startFailedDesc', '知识库已创建，但爬取任务启动失败，请手动开始爬取')
          );
        }
      }
    } catch (error) {
      console.error('Failed to create knowledge base:', error);
      showKnowledgeBaseError(showToast, 'create', error, data.name);
      throw error; // Re-throw to let modal handle the error
    }
  };

  // Start crawl job for a website knowledge base
  const handleStartCrawl = useCallback(async (kb: KnowledgeBaseItem) => {
    if (!kb.crawlConfig) {
      showToast(
        'error',
        t('knowledge.crawl.noConfig', '无爬取配置'),
        t('knowledge.crawl.noConfigDesc', '该知识库没有爬取配置')
      );
      return;
    }

    setCrawlingKbs(prev => new Set(prev).add(kb.id));
    try {
      await KnowledgeBaseApiService.createCrawlJob(kb.id, kb.crawlConfig);
      showToast(
        'success',
        t('knowledge.crawl.started', '爬取已开始'),
        t('knowledge.crawl.startedDesc', '网站爬取任务已启动')
      );
      // Refresh to get updated status
      await refreshKnowledgeBases();
    } catch (error) {
      console.error('Failed to start crawl job:', error);
      showToast(
        'error',
        t('knowledge.crawl.startFailed', '爬取启动失败'),
        error instanceof Error ? error.message : t('knowledge.crawl.startFailedDesc', '启动爬取任务时发生错误')
      );
    } finally {
      setCrawlingKbs(prev => {
        const next = new Set(prev);
        next.delete(kb.id);
        return next;
      });
    }
  }, [showToast, t, refreshKnowledgeBases]);

  // Cancel crawl job
  const handleCancelCrawl = useCallback(async (kb: KnowledgeBaseItem) => {
    if (!kb.crawlJob?.id) return;

    try {
      await KnowledgeBaseApiService.cancelCrawlJob(kb.crawlJob.id);
      showToast(
        'success',
        t('knowledge.crawl.cancelled', '爬取已取消'),
        t('knowledge.crawl.cancelledDesc', '网站爬取任务已取消')
      );
      await refreshKnowledgeBases();
    } catch (error) {
      console.error('Failed to cancel crawl job:', error);
      showToast(
        'error',
        t('knowledge.crawl.cancelFailed', '取消失败'),
        error instanceof Error ? error.message : t('knowledge.crawl.cancelFailedDesc', '取消爬取任务时发生错误')
      );
    }
  }, [showToast, t, refreshKnowledgeBases]);

  // Get crawl status badge
  const getCrawlStatusBadge = (status: CrawlJobStatus) => {
    const statusConfig: Record<CrawlJobStatus, { color: string; text: string }> = {
      pending: { color: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300', text: t('knowledge.crawl.status.pending', '等待中') },
      crawling: { color: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300', text: t('knowledge.crawl.status.crawling', '爬取中') },
      processing: { color: 'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300', text: t('knowledge.crawl.status.processing', '处理中') },
      completed: { color: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300', text: t('knowledge.crawl.status.completed', '已完成') },
      failed: { color: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300', text: t('knowledge.crawl.status.failed', '失败') },
      cancelled: { color: 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300', text: t('knowledge.crawl.status.cancelled', '已取消') }
    };
    const config = statusConfig[status];
    return (
      <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${config.color}`}>
        {config.text}
      </span>
    );
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
    if (knowledgeBase.type === 'website') {
      navigate(`/knowledge/website/${knowledgeBase.id}`);
    } else {
      navigate(`/knowledge/${knowledgeBase.id}`);
    }
  };

  return (
    <main className="flex-grow flex flex-col bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-900 dark:to-gray-800">
      {/* Header */}
      <header className="px-6 py-4 border-b border-gray-200/80 dark:border-gray-700/80 sticky top-0 bg-white/60 dark:bg-gray-800/60 backdrop-blur-lg z-10">
        <div className="flex justify-between items-center">
          <div>
            <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-100">{t('knowledge.manage', '知识库管理')}</h2>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">{t('knowledge.subtitle', '管理可供智能体使用的知识来源。')}</p>
          </div>
          <div className="flex items-center space-x-3">
            <button
              className="p-1.5 text-gray-500 dark:text-gray-400 hover:bg-gray-200/70 dark:hover:bg-gray-700/70 rounded-md transition-colors duration-200"
              title={t('knowledge.detail.refresh', '刷新')}
              onClick={handleRefresh}
            >
              <RefreshCw className="w-5 h-5" />
            </button>
            <button
              className="flex items-center px-3 py-1.5 bg-blue-500 dark:bg-blue-600 text-white text-sm rounded-md hover:bg-blue-600 dark:hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1 transition-colors duration-200"
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
              className="w-full pl-9 pr-3 py-1.5 text-sm border border-gray-300/70 dark:border-gray-600 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500 bg-white/80 dark:bg-gray-700/80 dark:text-gray-100 dark:placeholder-gray-400"
            />
            <Search className="w-4 h-4 absolute left-2.5 top-1/2 transform -translate-y-1/2 text-gray-400 dark:text-gray-500" />
          </div>

        </div>


      </header>

      {/* Content Area: Knowledge Base List */}
      <div className="flex-grow overflow-y-auto p-6" style={{ height: 0 }}>
        <div className="bg-white/80 dark:bg-gray-800/80 backdrop-blur-md rounded-lg shadow-sm border border-gray-200/60 dark:border-gray-700/60 overflow-hidden">
          {/* Table Header */}
          <div className="grid grid-cols-[minmax(0,_3fr)_80px_1fr_1fr_auto] gap-4 px-4 py-2 border-b border-gray-200/60 dark:border-gray-700/60 bg-gray-50/50 dark:bg-gray-900/50">
            <div className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider flex items-center cursor-pointer hover:text-gray-700 dark:hover:text-gray-200">
              {t('knowledge.list.columns.name', '名称')} <ArrowUpDown className="w-3 h-3 ml-1" />
            </div>
            <div className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider flex items-center">
              {t('knowledge.list.columns.type', '类型')}
            </div>
            <div className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider flex items-center cursor-pointer hover:text-gray-700 dark:hover:text-gray-200">
              {t('knowledge.list.columns.documents', '文档数量')} <ArrowUpDown className="w-3 h-3 ml-1" />
            </div>
            <div className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider flex items-center cursor-pointer hover:text-gray-700 dark:hover:text-gray-200">
              {t('knowledge.list.columns.lastUpdated', '最近更新')} <ArrowUpDown className="w-3 h-3 ml-1" />
            </div>
            <div className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider text-right pr-2">
              {t('knowledge.list.columns.actions', '操作')}
            </div>
          </div>

          {/* Table Body */}
          <div>
            {isLoading ? (
              <div className="text-center py-12">
                <div className="inline-flex items-center">
                  <RefreshCw className="w-5 h-5 animate-spin text-blue-500 dark:text-blue-400 mr-2" />
                  <span className="text-gray-500 dark:text-gray-400">{t('common.loading', '加载中...')}</span>
                </div>
              </div>
            ) : hasError ? (
              <div className="text-center py-12">
                <div className="w-16 h-16 mx-auto bg-red-100 dark:bg-red-900/30 rounded-full flex items-center justify-center mb-4">
                  <svg className="w-8 h-8 text-red-500 dark:text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
                <h3 className="text-lg font-medium text-gray-800 dark:text-gray-100 mb-2">{t('common.loadFailed', '加载失败')}</h3>
                <p className="text-gray-500 dark:text-gray-400 mb-4">{error || t('knowledge.list.loadFailedDesc', '获取知识库列表时发生错误')}</p>
                <div className="flex justify-center space-x-3">
                  <button
                    onClick={retry}
                    className="inline-flex items-center px-4 py-2 bg-blue-500 dark:bg-blue-600 text-white rounded-lg hover:bg-blue-600 dark:hover:bg-blue-700 transition-colors"
                  >
                    <RefreshCw className="w-4 h-4 mr-2" />
                    {t('common.retry', '重试')}
                  </button>
                  <button
                    onClick={clearError}
                    className="inline-flex items-center px-4 py-2 bg-gray-500 dark:bg-gray-600 text-white rounded-lg hover:bg-gray-600 dark:hover:bg-gray-700 transition-colors"
                  >
                    {t('knowledge.error.clear', '清除错误')}
                  </button>
                </div>
              </div>
            ) : filteredKnowledgeBases.length === 0 ? (
              <div className="text-center py-12">
                <FolderOpen className="w-16 h-16 mx-auto text-gray-300 dark:text-gray-600 mb-4" />
                <h3 className="text-lg font-medium text-gray-800 dark:text-gray-100 mb-2">{t('knowledge.empty.title', '暂无知识库')}</h3>
                <p className="text-gray-500 dark:text-gray-400 mb-4">{t('knowledge.empty.description', '创建您的第一个知识库开始使用')}</p>
                <button
                  onClick={handleOpenCreateModal}
                  className="inline-flex items-center px-4 py-2 bg-blue-500 dark:bg-blue-600 text-white rounded-lg hover:bg-blue-600 dark:hover:bg-blue-700 transition-colors"
                >
                  <Plus className="w-4 h-4 mr-2" />
                  {t('knowledge.create', '创建知识库')}
                </button>
              </div>
            ) : (
              filteredKnowledgeBases.map((kb: KnowledgeBaseItem, index: number) => {
                const isWebsite = kb.type === 'website';
                const isCrawling = crawlingKbs.has(kb.id);
                const crawlStatus = kb.crawlJob?.status;
                const isActiveCrawl = crawlStatus === 'pending' || crawlStatus === 'crawling' || crawlStatus === 'processing';

                return (
                  <div
                    key={kb.id}
                    className={`grid grid-cols-[minmax(0,_3fr)_80px_1fr_1fr_auto] gap-4 px-4 py-3 items-center hover:bg-gray-50/30 dark:hover:bg-gray-700/30 transition-colors ${
                      index < filteredKnowledgeBases.length - 1 ? 'border-b border-gray-200/60 dark:border-gray-700/60' : ''
                    }`}
                  >
                    <div
                      className="flex items-start space-x-3 cursor-pointer hover:bg-blue-50/50 dark:hover:bg-blue-900/30 -mx-2 px-2 py-1 rounded transition-all duration-200 group"
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
                        <p className="text-sm font-medium text-gray-800 dark:text-gray-100 group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors duration-200">{kb.title}</p>
                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 leading-snug">{kb.content}</p>
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
                                style={{ fontSize: '10px' }}
                              >
                                {tagName}
                              </span>
                            );
                          })}
                        </div>
                      </div>
                    </div>

                    {/* Type Column */}
                    <div className="flex flex-col gap-1">
                      <div className="flex items-center gap-1">
                        {isWebsite ? (
                          <>
                            <Globe className="w-3.5 h-3.5 text-blue-500" />
                            <span className="text-xs text-gray-600 dark:text-gray-300">{t('knowledge.typeWebsite', '网站')}</span>
                          </>
                        ) : (
                          <>
                            <FileText className="w-3.5 h-3.5 text-green-500" />
                            <span className="text-xs text-gray-600 dark:text-gray-300">{t('knowledge.typeFile', '文件')}</span>
                          </>
                        )}
                      </div>
                      {isWebsite && crawlStatus && getCrawlStatusBadge(crawlStatus)}
                    </div>

                    <div className="text-sm text-gray-600 dark:text-gray-300">{t('knowledge.filesCount', { count: kb.fileCount, defaultValue: `${kb.fileCount} 文件` })}</div>
                    <div className="text-sm text-gray-600 dark:text-gray-300 flex items-center">
                      <Clock className="w-3.5 h-3.5 mr-1 text-gray-400 dark:text-gray-500" />
                      {formatKnowledgeBaseUpdatedTime(kb.updatedAt)}
                    </div>

                    <div className="flex justify-end space-x-2">
                      {/* Crawl actions for website type */}
                      {isWebsite && (
                        <>
                          {isActiveCrawl ? (
                            <button
                              className="text-gray-400 dark:text-gray-500 hover:text-orange-600 dark:hover:text-orange-400 transition-colors"
                              title={t('knowledge.crawl.cancel', '取消爬取')}
                              onClick={() => handleCancelCrawl(kb)}
                            >
                              <XCircle className="w-4 h-4" />
                            </button>
                          ) : (
                            <button
                              className="text-gray-400 dark:text-gray-500 hover:text-green-600 dark:hover:text-green-400 transition-colors disabled:opacity-50"
                              title={t('knowledge.crawl.start', '开始爬取')}
                              onClick={() => handleStartCrawl(kb)}
                              disabled={isCrawling}
                            >
                              {isCrawling ? (
                                <Loader2 className="w-4 h-4 animate-spin" />
                              ) : (
                                <Play className="w-4 h-4" />
                              )}
                            </button>
                          )}
                        </>
                      )}

                      <button
                        className="text-gray-400 dark:text-gray-500 hover:text-blue-600 dark:hover:text-blue-400 transition-colors"
                        title={t('common.details', '详情')}
                        onClick={() => navigate(`/knowledge/${kb.id}`)}
                      >
                        <Eye className="w-4 h-4" />
                      </button>

                      <button
                        className="text-gray-400 dark:text-gray-500 hover:text-blue-600 dark:hover:text-blue-400 transition-colors"
                        title={t('common.edit', '编辑')}
                        onClick={() => handleKnowledgeBaseAction('edit', kb)}
                      >
                        <Pencil className="w-4 h-4" />
                      </button>

                      <button
                        className="text-gray-400 dark:text-gray-500 hover:text-red-600 dark:hover:text-red-400 transition-colors"
                        title={t('common.delete', '删除')}
                        onClick={() => handleKnowledgeBaseAction('delete', kb)}
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                );
              })
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
