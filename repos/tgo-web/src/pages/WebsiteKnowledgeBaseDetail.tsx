import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft, RefreshCw, Globe, Clock, ExternalLink,
  Plus, XCircle, Loader2, CheckCircle, AlertCircle,
  FileText, ArrowDownRight, X
} from 'lucide-react';
import { KnowledgeBaseApiService, type WebsiteCrawlJobResponse, type WebsitePageResponse } from '@/services/knowledgeBaseApi';
import { transformCollectionToKnowledgeBase } from '@/utils/knowledgeBaseTransforms';
import { useToast } from '@/hooks/useToast';
import type { KnowledgeBase } from '@/types';
import { useTranslation } from 'react-i18next';

/**
 * Website Knowledge Base Detail Page Component
 * Displays crawled pages and crawl job status for website-type knowledge bases
 */
const WebsiteKnowledgeBaseDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { showToast } = useToast();
  const { t } = useTranslation();

  // State
  const [knowledgeBase, setKnowledgeBase] = useState<KnowledgeBase | null>(null);
  const [currentJob, setCurrentJob] = useState<WebsiteCrawlJobResponse | null>(null);
  const [pages, setPages] = useState<WebsitePageResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingPages, setIsLoadingPages] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isCancellingJob, setIsCancellingJob] = useState(false);

  // Add page dialog state
  const [isAddPageDialogOpen, setIsAddPageDialogOpen] = useState(false);
  const [newPageUrl, setNewPageUrl] = useState('');
  const [isAddingPage, setIsAddingPage] = useState(false);

  // Crawl deeper state
  const [crawlingDeeperPages, setCrawlingDeeperPages] = useState<Set<string>>(new Set());

  // Pagination state
  const [pagesPagination, setPagesPagination] = useState({ total: 0, limit: 20, offset: 0 });

  // Load knowledge base data and current job
  const loadKnowledgeBase = useCallback(async () => {
    if (!id) return;

    try {
      const collection = await KnowledgeBaseApiService.getCollection(id);
      const kb = transformCollectionToKnowledgeBase(collection);
      setKnowledgeBase(kb);

      // Check if it's a website type, if not redirect
      if (collection.collection_type !== 'website') {
        navigate(`/knowledge/${id}`, { replace: true });
        return;
      }

      // Load the current/latest crawl job
      const jobsResponse = await KnowledgeBaseApiService.getCollectionCrawlJobs(id, { limit: 1 });
      if (jobsResponse.data.length > 0) {
        setCurrentJob(jobsResponse.data[0]);
      }
    } catch (err) {
      console.error('Failed to load knowledge base:', err);
      setError(err instanceof Error ? err.message : t('knowledge.website.loadFailed'));
    }
  }, [id, navigate, t]);

  // Reload current job status
  const reloadJobStatus = useCallback(async () => {
    if (!id) return;
    try {
      const jobsResponse = await KnowledgeBaseApiService.getCollectionCrawlJobs(id, { limit: 1 });
      if (jobsResponse.data.length > 0) {
        setCurrentJob(jobsResponse.data[0]);
      }
    } catch (err) {
      console.error('Failed to reload job status:', err);
    }
  }, [id]);

  // Load pages
  const loadPages = useCallback(async () => {
    if (!id) return;
    
    setIsLoadingPages(true);
    try {
      const response = await KnowledgeBaseApiService.getCollectionPages(id, {
        limit: pagesPagination.limit,
        offset: pagesPagination.offset,
      });
      setPages(response.data);
      setPagesPagination(prev => ({ ...prev, total: response.pagination.total }));
    } catch (err) {
      console.error('Failed to load pages:', err);
      showToast('error', t('knowledge.website.loadPagesFailed'));
    } finally {
      setIsLoadingPages(false);
    }
  }, [id, pagesPagination.limit, pagesPagination.offset, showToast, t]);

  // Initial load
  useEffect(() => {
    const initialize = async () => {
      setIsLoading(true);
      await loadKnowledgeBase();
      setIsLoading(false);
    };
    initialize();
  }, [loadKnowledgeBase]);

  // Load pages when knowledge base is loaded
  useEffect(() => {
    if (knowledgeBase) {
      loadPages();
    }
  }, [knowledgeBase, loadPages]);

  // Handle refresh
  const handleRefresh = async () => {
    await Promise.all([loadPages(), reloadJobStatus()]);
  };

  // Handle back navigation
  const handleBack = () => {
    navigate('/knowledge');
  };

  // Cancel current crawl job
  const handleCancelJob = async () => {
    if (!currentJob) return;

    setIsCancellingJob(true);
    try {
      await KnowledgeBaseApiService.cancelCrawlJob(currentJob.id);
      showToast('success', t('knowledge.crawl.cancelled'));
      await reloadJobStatus();
    } catch (err) {
      console.error('Failed to cancel job:', err);
      showToast('error', t('knowledge.crawl.cancelFailed'), err instanceof Error ? err.message : undefined);
    } finally {
      setIsCancellingJob(false);
    }
  };

  // Add page to crawl queue
  const handleAddPage = async () => {
    if (!currentJob || !newPageUrl.trim()) return;

    // Validate URL
    try {
      new URL(newPageUrl.trim());
    } catch {
      showToast('error', t('knowledge.validation.urlInvalid'));
      return;
    }

    setIsAddingPage(true);
    try {
      const response = await KnowledgeBaseApiService.addPageToCrawlJob(currentJob.id, { url: newPageUrl.trim() });
      if (response.success) {
        showToast('success', t('knowledge.website.addPage.success'), response.message);
        setNewPageUrl('');
        setIsAddPageDialogOpen(false);
        await Promise.all([loadPages(), reloadJobStatus()]);
      } else {
        showToast('warning', t('knowledge.website.addPage.skipped'), response.message);
      }
    } catch (err) {
      console.error('Failed to add page:', err);
      showToast('error', t('knowledge.website.addPage.failed'), err instanceof Error ? err.message : undefined);
    } finally {
      setIsAddingPage(false);
    }
  };

  // Crawl deeper from a page
  const handleCrawlDeeper = async (pageId: string) => {
    setCrawlingDeeperPages(prev => new Set(prev).add(pageId));
    try {
      const response = await KnowledgeBaseApiService.crawlDeeperFromPage(pageId, { max_depth: 1 });
      if (response.success) {
        showToast('success', t('knowledge.website.crawlDeeper.success'),
          t('knowledge.website.crawlDeeper.successDesc', {
            added: response.pages_added,
            found: response.links_found
          })
        );
        await Promise.all([loadPages(), reloadJobStatus()]);
      } else {
        showToast('warning', t('knowledge.website.crawlDeeper.noNewPages'), response.message);
      }
    } catch (err) {
      console.error('Failed to crawl deeper:', err);
      showToast('error', t('knowledge.website.crawlDeeper.failed'), err instanceof Error ? err.message : undefined);
    } finally {
      setCrawlingDeeperPages(prev => {
        const next = new Set(prev);
        next.delete(pageId);
        return next;
      });
    }
  };

  // Get status badge for crawl job
  const getJobStatusBadge = (status: string) => {
    const statusConfig: Record<string, { color: string; icon: React.ReactNode; label: string }> = {
      pending: { color: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400', icon: <Clock className="w-3 h-3" />, label: t('knowledge.crawl.status.pending') },
      crawling: { color: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400', icon: <Loader2 className="w-3 h-3 animate-spin" />, label: t('knowledge.crawl.status.crawling') },
      processing: { color: 'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-400', icon: <Loader2 className="w-3 h-3 animate-spin" />, label: t('knowledge.crawl.status.processing') },
      completed: { color: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400', icon: <CheckCircle className="w-3 h-3" />, label: t('knowledge.crawl.status.completed') },
      failed: { color: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400', icon: <AlertCircle className="w-3 h-3" />, label: t('knowledge.crawl.status.failed') },
      cancelled: { color: 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-400', icon: <XCircle className="w-3 h-3" />, label: t('knowledge.crawl.status.cancelled') },
    };

    const config = statusConfig[status] || statusConfig.pending;
    return (
      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${config.color}`}>
        {config.icon}
        {config.label}
      </span>
    );
  };

  // Get status badge for page
  const getPageStatusBadge = (status: string) => {
    const statusConfig: Record<string, { color: string; label: string }> = {
      pending: { color: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400', label: t('knowledge.website.pageStatus.pending') },
      fetched: { color: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400', label: t('knowledge.website.pageStatus.fetched') },
      extracted: { color: 'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-400', label: t('knowledge.website.pageStatus.extracted') },
      processed: { color: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400', label: t('knowledge.website.pageStatus.processed') },
      failed: { color: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400', label: t('knowledge.website.pageStatus.failed') },
    };

    const config = statusConfig[status] || statusConfig.pending;
    return (
      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${config.color}`}>
        {config.label}
      </span>
    );
  };

  // Format date
  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleString();
  };

  // Render loading state
  if (isLoading) {
    return (
      <div className="flex-grow flex items-center justify-center bg-gray-100 dark:bg-gray-900">
        <div className="inline-flex items-center">
          <Loader2 className="w-5 h-5 animate-spin text-blue-500 mr-2" />
          <span className="text-gray-500 dark:text-gray-400">{t('knowledge.website.loading')}</span>
        </div>
      </div>
    );
  }

  // Render error state
  if (error || !knowledgeBase) {
    return (
      <div className="flex-grow flex items-center justify-center bg-gray-100 dark:bg-gray-900">
        <div className="text-center">
          <AlertCircle className="w-12 h-12 text-red-500 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-800 dark:text-gray-100 mb-2">
            {t('knowledge.website.loadFailed')}
          </h3>
          <p className="text-gray-500 dark:text-gray-400 mb-4">{error}</p>
          <button
            onClick={() => navigate('/knowledge')}
            className="inline-flex items-center px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600"
          >
            {t('knowledge.detail.backToList')}
          </button>
        </div>
      </div>
    );
  }

  const isJobActive = currentJob && ['pending', 'crawling', 'processing'].includes(currentJob.status);

  return (
    <div className="flex h-full w-full bg-gray-100 dark:bg-gray-900">
      <div className="flex-grow flex flex-col overflow-hidden">
        {/* Header */}
        <div className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <button
                onClick={handleBack}
                className="p-2 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
              >
                <ArrowLeft className="w-5 h-5" />
              </button>
              <div className="flex items-center gap-3">
                <Globe className="w-6 h-6 text-blue-500" />
                <div>
                  <h1 className="text-xl font-semibold text-gray-800 dark:text-gray-100">
                    {knowledgeBase.name}
                  </h1>
                  {knowledgeBase.description && (
                    <p className="text-sm text-gray-500 dark:text-gray-400">{knowledgeBase.description}</p>
                  )}
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={handleRefresh}
                className="p-2 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
                title={t('common.refresh')}
              >
                <RefreshCw className="w-5 h-5" />
              </button>
              <button
                onClick={() => setIsAddPageDialogOpen(true)}
                disabled={!currentJob}
                className="inline-flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                <Plus className="w-4 h-4" />
                {t('knowledge.website.addPage.button')}
              </button>
            </div>
          </div>
        </div>

        {/* Job Status Card */}
        {currentJob && (
          <div className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 px-6 py-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-6">
                <div className="flex items-center gap-2">
                  <span className="text-sm text-gray-500 dark:text-gray-400">{t('knowledge.website.jobStatus.status')}:</span>
                  {getJobStatusBadge(currentJob.status)}
                </div>
                <div className="flex items-center gap-4 text-sm">
                  <span className="text-gray-500 dark:text-gray-400">
                    {t('knowledge.website.jobDetails.discovered')}: <span className="text-gray-700 dark:text-gray-200 font-medium">{currentJob.progress.pages_discovered}</span>
                  </span>
                  <span className="text-gray-500 dark:text-gray-400">
                    {t('knowledge.website.jobDetails.crawled')}: <span className="text-gray-700 dark:text-gray-200 font-medium">{currentJob.progress.pages_crawled}</span>
                  </span>
                  <span className="text-gray-500 dark:text-gray-400">
                    {t('knowledge.website.jobDetails.processed')}: <span className="text-gray-700 dark:text-gray-200 font-medium">{currentJob.progress.pages_processed}</span>
                  </span>
                  {currentJob.progress.pages_failed > 0 && (
                    <span className="text-red-500 dark:text-red-400">
                      {t('knowledge.website.jobDetails.failed')}: <span className="font-medium">{currentJob.progress.pages_failed}</span>
                    </span>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-3">
                {isJobActive && (
                  <>
                    <div className="text-sm text-gray-500 dark:text-gray-400">
                      {t('knowledge.website.progress')}: {currentJob.progress.progress_percent}%
                    </div>
                    <button
                      onClick={handleCancelJob}
                      disabled={isCancellingJob}
                      className="inline-flex items-center gap-1 px-3 py-1.5 text-red-600 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-colors text-sm"
                    >
                      {isCancellingJob ? <Loader2 className="w-4 h-4 animate-spin" /> : <XCircle className="w-4 h-4" />}
                      {t('knowledge.crawl.cancel')}
                    </button>
                  </>
                )}
                {currentJob.error_message && (
                  <span className="text-sm text-red-500 dark:text-red-400 max-w-xs truncate" title={currentJob.error_message}>
                    {currentJob.error_message}
                  </span>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Page Title */}
        <div className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 px-6 py-3">
          <div className="flex items-center gap-2">
            <FileText className="w-4 h-4 text-gray-400" />
            <span className="text-sm font-medium text-gray-700 dark:text-gray-200">
              {t('knowledge.website.tabs.pages')} ({pagesPagination.total})
            </span>
          </div>
        </div>

        {/* Content - Pages List */}
        <div className="flex-grow overflow-y-auto p-6">
          <div className="space-y-4">
            {isLoadingPages ? (
              <div className="flex justify-center py-8">
                <Loader2 className="w-6 h-6 animate-spin text-blue-500" />
              </div>
            ) : pages.length === 0 ? (
              <div className="text-center py-8 text-gray-500 dark:text-gray-400">
                {t('knowledge.website.noPages')}
              </div>
            ) : (
              <div className="bg-white dark:bg-gray-800 rounded-lg shadow overflow-hidden">
                <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                  <thead className="bg-gray-50 dark:bg-gray-700">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                        {t('knowledge.website.columns.url')}
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                        {t('knowledge.website.columns.title')}
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                        {t('knowledge.website.columns.status')}
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                        {t('knowledge.website.columns.depth')}
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                        {t('knowledge.website.columns.crawledAt')}
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                        {t('knowledge.website.columns.actions')}
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                    {pages.map((page) => {
                      const isCrawlingDeeper = crawlingDeeperPages.has(page.id);
                      const canCrawlDeeper = page.status === 'processed';

                      return (
                        <tr key={page.id} className="hover:bg-gray-50 dark:hover:bg-gray-700/50">
                          <td className="px-4 py-3">
                            <a
                              href={page.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="flex items-center gap-1 text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300 text-sm truncate max-w-xs"
                            >
                              {page.url}
                              <ExternalLink className="w-3 h-3 flex-shrink-0" />
                            </a>
                          </td>
                          <td className="px-4 py-3 text-sm text-gray-700 dark:text-gray-300 truncate max-w-xs">
                            {page.title || '-'}
                          </td>
                          <td className="px-4 py-3">
                            {getPageStatusBadge(page.status)}
                          </td>
                          <td className="px-4 py-3 text-sm text-gray-500 dark:text-gray-400">
                            {page.depth}
                          </td>
                          <td className="px-4 py-3 text-sm text-gray-500 dark:text-gray-400">
                            {formatDate(page.created_at)}
                          </td>
                          <td className="px-4 py-3">
                            <button
                              onClick={() => handleCrawlDeeper(page.id)}
                              disabled={isCrawlingDeeper || !canCrawlDeeper}
                              className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                              title={canCrawlDeeper ? t('knowledge.website.crawlDeeper.button') : t('knowledge.website.crawlDeeper.notReady')}
                            >
                              {isCrawlingDeeper ? (
                                <Loader2 className="w-3 h-3 animate-spin" />
                              ) : (
                                <ArrowDownRight className="w-3 h-3" />
                              )}
                              {t('knowledge.website.crawlDeeper.button')}
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Add Page Dialog */}
      {isAddPageDialogOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-md mx-4">
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
              <h3 className="text-lg font-semibold text-gray-800 dark:text-gray-100">
                {t('knowledge.website.addPage.title')}
              </h3>
              <button
                onClick={() => { setIsAddPageDialogOpen(false); setNewPageUrl(''); }}
                className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 rounded"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="px-6 py-4">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                {t('knowledge.website.addPage.urlLabel')}
              </label>
              <input
                type="url"
                value={newPageUrl}
                onChange={(e) => setNewPageUrl(e.target.value)}
                placeholder={t('knowledge.website.addPage.urlPlaceholder')}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                autoFocus
              />
              <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">
                {t('knowledge.website.addPage.hint')}
              </p>
            </div>
            <div className="flex justify-end gap-3 px-6 py-4 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-700/30">
              <button
                onClick={() => { setIsAddPageDialogOpen(false); setNewPageUrl(''); }}
                className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-600 rounded-lg transition-colors"
              >
                {t('common.cancel')}
              </button>
              <button
                onClick={handleAddPage}
                disabled={isAddingPage || !newPageUrl.trim()}
                className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-500 hover:bg-blue-600 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isAddingPage && <Loader2 className="w-4 h-4 animate-spin" />}
                {t('knowledge.website.addPage.submit')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default WebsiteKnowledgeBaseDetail;

