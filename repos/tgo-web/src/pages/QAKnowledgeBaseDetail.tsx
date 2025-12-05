import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  ArrowLeft,
  Plus,
  Loader2,
  Search,
  Pencil,
  Trash2,
  Upload,
  MessageSquare,
  X,
  CheckCircle,
  Clock,
  AlertCircle,
  Filter,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { useToast } from '@/hooks/useToast';
import { KnowledgeBaseApiService, type QAPairResponse, type QAPairListResponse, type QACategoryListResponse } from '@/services/knowledgeBaseApi';
import { transformCollectionToKnowledgeBase } from '@/utils/knowledgeBaseTransforms';
import type { KnowledgeBase } from '@/types';

/**
 * QA Knowledge Base Detail Page Component
 * Displays QA pairs with CRUD operations
 */
const QAKnowledgeBaseDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { showToast } = useToast();
  const { t } = useTranslation();

  // State
  const [knowledgeBase, setKnowledgeBase] = useState<KnowledgeBase | null>(null);
  const [qaPairs, setQaPairs] = useState<QAPairResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingPairs, setIsLoadingPairs] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Pagination state
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [limit] = useState(10);

  // Filter state
  const [categoryFilter, setCategoryFilter] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [searchTerm, setSearchTerm] = useState('');
  const [categories, setCategories] = useState<string[]>([]);

  // Dialog state
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const [isImportDialogOpen, setIsImportDialogOpen] = useState(false);
  const [editingPair, setEditingPair] = useState<QAPairResponse | null>(null);

  // Form state
  const [formQuestion, setFormQuestion] = useState('');
  const [formAnswer, setFormAnswer] = useState('');
  const [formCategory, setFormCategory] = useState('');
  const [formTags, setFormTags] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Import state
  const [importFormat, setImportFormat] = useState<'json' | 'csv'>('json');
  const [importData, setImportData] = useState('');
  const [isImporting, setIsImporting] = useState(false);

  // Delete state
  const [deletingIds, setDeletingIds] = useState<Set<string>>(new Set());

  // Statistics
  const stats = {
    total: total,
    pending: qaPairs.filter(p => p.status === 'pending').length,
    processing: qaPairs.filter(p => p.status === 'processing').length,
    processed: qaPairs.filter(p => p.status === 'processed').length,
    failed: qaPairs.filter(p => p.status === 'failed').length,
  };

  // Load knowledge base
  const loadKnowledgeBase = useCallback(async () => {
    if (!id) return;
    try {
      const collection = await KnowledgeBaseApiService.getCollection(id);
      const kb = transformCollectionToKnowledgeBase(collection);
      setKnowledgeBase(kb);
      if (collection.collection_type !== 'qa') {
        if (collection.collection_type === 'website') {
          navigate(`/knowledge/website/${id}`, { replace: true });
        } else {
          navigate(`/knowledge/${id}`, { replace: true });
        }
      }
    } catch (err) {
      console.error('Failed to load knowledge base:', err);
      setError(err instanceof Error ? err.message : t('knowledge.qa.loadFailed'));
    }
  }, [id, navigate, t]);

  // Load QA pairs
  const loadQAPairs = useCallback(async () => {
    if (!id) return;
    setIsLoadingPairs(true);
    try {
      const response: QAPairListResponse = await KnowledgeBaseApiService.getQAPairs(id, {
        limit,
        offset,
        category: categoryFilter || undefined,
        status: statusFilter || undefined,
      });
      setQaPairs(response.data);
      setTotal(response.total);
    } catch (err) {
      console.error('Failed to load QA pairs:', err);
      showToast('error', t('knowledge.qa.loadPairsFailed'));
    } finally {
      setIsLoadingPairs(false);
    }
  }, [id, limit, offset, categoryFilter, statusFilter, showToast, t]);

  // Load categories
  const loadCategories = useCallback(async () => {
    if (!id) return;
    try {
      const response: QACategoryListResponse = await KnowledgeBaseApiService.getQACategories(id);
      setCategories(response.categories);
    } catch (err) {
      console.error('Failed to load categories:', err);
      // Don't show toast for category loading failure, it's not critical
    }
  }, [id]);

  // Initial load
  useEffect(() => {
    const init = async () => {
      setIsLoading(true);
      await loadKnowledgeBase();
      setIsLoading(false);
    };
    init();
  }, [loadKnowledgeBase]);

  // Load pairs and categories when knowledge base is loaded
  useEffect(() => {
    if (knowledgeBase) {
      loadQAPairs();
      loadCategories();
    }
  }, [knowledgeBase, loadQAPairs, loadCategories]);

  // Reset form
  const resetForm = () => {
    setFormQuestion('');
    setFormAnswer('');
    setFormCategory('');
    setFormTags('');
  };

  // Handle add QA pair
  const handleAddPair = async () => {
    if (!id || !formQuestion.trim() || !formAnswer.trim()) return;
    setIsSubmitting(true);
    try {
      await KnowledgeBaseApiService.createQAPair(id, {
        question: formQuestion.trim(),
        answer: formAnswer.trim(),
        category: formCategory.trim() || null,
        tags: formTags.trim() ? formTags.split(',').map(t => t.trim()) : null,
      });
      showToast('success', t('knowledge.qa.addSuccess'));
      setIsAddDialogOpen(false);
      resetForm();
      loadQAPairs();
      loadCategories(); // Refresh categories in case a new one was added
    } catch (err) {
      console.error('Failed to add QA pair:', err);
      showToast('error', t('knowledge.qa.addFailed'));
    } finally {
      setIsSubmitting(false);
    }
  };

  // Handle edit QA pair
  const handleEditPair = async () => {
    if (!editingPair || !formQuestion.trim() || !formAnswer.trim()) return;
    setIsSubmitting(true);
    try {
      await KnowledgeBaseApiService.updateQAPair(editingPair.id, {
        question: formQuestion.trim(),
        answer: formAnswer.trim(),
        category: formCategory.trim() || null,
        tags: formTags.trim() ? formTags.split(',').map(t => t.trim()) : null,
      });
      showToast('success', t('knowledge.qa.editSuccess'));
      setIsEditDialogOpen(false);
      setEditingPair(null);
      resetForm();
      loadQAPairs();
      loadCategories(); // Refresh categories in case category was changed
    } catch (err) {
      console.error('Failed to update QA pair:', err);
      showToast('error', t('knowledge.qa.editFailed'));
    } finally {
      setIsSubmitting(false);
    }
  };

  // Handle delete QA pair
  const handleDeletePair = async (pairId: string) => {
    if (deletingIds.has(pairId)) return;
    setDeletingIds(prev => new Set(prev).add(pairId));
    try {
      await KnowledgeBaseApiService.deleteQAPair(pairId);
      showToast('success', t('knowledge.qa.deleteSuccess'));
      loadQAPairs();
    } catch (err) {
      console.error('Failed to delete QA pair:', err);
      showToast('error', t('knowledge.qa.deleteFailed'));
    } finally {
      setDeletingIds(prev => {
        const next = new Set(prev);
        next.delete(pairId);
        return next;
      });
    }
  };

  // Handle import
  const handleImport = async () => {
    if (!id || !importData.trim()) return;
    setIsImporting(true);
    try {
      const response = await KnowledgeBaseApiService.importQAPairs(id, {
        format: importFormat,
        data: importData,
      });
      showToast(
        'success',
        t('knowledge.qa.importSuccess', { count: response.created_count })
      );
      setIsImportDialogOpen(false);
      setImportData('');
      loadQAPairs();
      loadCategories(); // Refresh categories in case new ones were imported
    } catch (err) {
      console.error('Failed to import QA pairs:', err);
      showToast('error', t('knowledge.qa.importFailed'));
    } finally {
      setIsImporting(false);
    }
  };

  // Open edit dialog
  const openEditDialog = (pair: QAPairResponse) => {
    setEditingPair(pair);
    setFormQuestion(pair.question);
    setFormAnswer(pair.answer);
    setFormCategory(pair.category || '');
    setFormTags(pair.tags?.join(', ') || '');
    setIsEditDialogOpen(true);
  };

  // Pagination
  const totalPages = Math.ceil(total / limit);
  const currentPage = Math.floor(offset / limit) + 1;
  const goToPage = (page: number) => {
    setOffset((page - 1) * limit);
  };

  // Get status icon
  const getStatusIcon = (status: QAPairResponse['status']) => {
    switch (status) {
      case 'processed':
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'pending':
        return <Clock className="h-4 w-4 text-yellow-500" />;
      case 'processing':
        return <Loader2 className="h-4 w-4 text-blue-500 animate-spin" />;
      case 'failed':
        return <AlertCircle className="h-4 w-4 text-red-500" />;
      default:
        return null;
    }
  };

  // Filter QA pairs by search term (client-side)
  const filteredPairs = qaPairs.filter(pair => {
    if (!searchTerm.trim()) return true;
    const term = searchTerm.toLowerCase();
    return (
      pair.question.toLowerCase().includes(term) ||
      pair.answer.toLowerCase().includes(term)
    );
  });

  // Loading state
  if (isLoading) {
    return (
      <div className="h-full w-full flex items-center justify-center bg-gray-100 dark:bg-gray-900">
        <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
        <span className="ml-2 text-gray-500">{t('knowledge.qa.loading')}</span>
      </div>
    );
  }

  // Error state
  if (error || !knowledgeBase) {
    return (
      <div className="h-full w-full flex flex-col items-center justify-center bg-gray-100 dark:bg-gray-900">
        <p className="text-red-500 mb-4">{error || t('knowledge.qa.loadFailed')}</p>
        <button
          onClick={() => navigate('/knowledge')}
          className="flex items-center text-blue-500 hover:text-blue-600"
        >
          <ArrowLeft className="h-4 w-4 mr-1" />
          {t('common.back')}
        </button>
      </div>
    );
  }

  return (
    <div className="h-full w-full flex flex-col bg-gray-100 dark:bg-gray-900">
      {/* Fixed Header */}
      <div className="flex-shrink-0 w-full bg-gray-100 dark:bg-gray-900 px-6 pt-6 pb-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center">
            <button
              onClick={() => navigate('/knowledge')}
              className="mr-4 p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800"
            >
              <ArrowLeft className="h-5 w-5" />
            </button>
            <div>
              <h1 className="text-2xl font-bold flex items-center gap-2">
                <MessageSquare className="h-6 w-6 text-green-500" />
                {knowledgeBase.name}
              </h1>
              {knowledgeBase.description && (
                <p className="text-gray-500 text-sm mt-1">{knowledgeBase.description}</p>
              )}
            </div>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => setIsImportDialogOpen(true)}
              className="flex items-center gap-2 px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800"
            >
              <Upload className="h-4 w-4" />
              {t('knowledge.qa.import')}
            </button>
            <button
              onClick={() => {
                resetForm();
                setIsAddDialogOpen(true);
              }}
              className="flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600"
            >
              <Plus className="h-4 w-4" />
              {t('knowledge.qa.add')}
            </button>
          </div>
        </div>
      </div>

      {/* Scrollable Content */}
      <div className="flex-1 w-full overflow-y-auto px-6 pb-6" style={{ height: 0 }}>
        {/* Statistics Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <div className="bg-white dark:bg-gray-800 rounded-lg p-4 shadow-sm border border-gray-200 dark:border-gray-700">
            <div className="text-2xl font-bold text-gray-900 dark:text-white">{stats.total}</div>
            <div className="text-sm text-gray-500">{t('knowledge.qa.stats.total')}</div>
          </div>
          <div className="bg-white dark:bg-gray-800 rounded-lg p-4 shadow-sm border border-gray-200 dark:border-gray-700">
            <div className="text-2xl font-bold text-yellow-500">{stats.pending}</div>
            <div className="text-sm text-gray-500">{t('knowledge.qa.stats.pending')}</div>
          </div>
          <div className="bg-white dark:bg-gray-800 rounded-lg p-4 shadow-sm border border-gray-200 dark:border-gray-700">
            <div className="text-2xl font-bold text-green-500">{stats.processed}</div>
            <div className="text-sm text-gray-500">{t('knowledge.qa.stats.processed')}</div>
          </div>
          <div className="bg-white dark:bg-gray-800 rounded-lg p-4 shadow-sm border border-gray-200 dark:border-gray-700">
            <div className="text-2xl font-bold text-red-500">{stats.failed}</div>
            <div className="text-sm text-gray-500">{t('knowledge.qa.stats.failed')}</div>
          </div>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap gap-4 mb-6">
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
            <input
              type="text"
              placeholder={t('knowledge.qa.searchPlaceholder')}
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800"
            />
          </div>
          <select
            value={categoryFilter}
            onChange={(e) => {
              setCategoryFilter(e.target.value);
              setOffset(0);
            }}
            className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800"
          >
            <option value="">{t('knowledge.qa.allCategories')}</option>
            {categories.map((category) => (
              <option key={category} value={category}>
                {category}
              </option>
            ))}
          </select>
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setOffset(0);
            }}
            className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800"
          >
            <option value="">{t('knowledge.qa.allStatuses')}</option>
            <option value="pending">{t('knowledge.qa.status.pending')}</option>
            <option value="processing">{t('knowledge.qa.status.processing')}</option>
            <option value="processed">{t('knowledge.qa.status.processed')}</option>
            <option value="failed">{t('knowledge.qa.status.failed')}</option>
          </select>
        </div>

        {/* QA Pairs List */}
        {isLoadingPairs ? (
          <div className="flex items-center justify-center h-32">
            <Loader2 className="h-6 w-6 animate-spin text-blue-500" />
          </div>
        ) : filteredPairs.length === 0 ? (
          <div className="text-center py-12 text-gray-500">
            <MessageSquare className="h-12 w-12 mx-auto mb-4 text-gray-300" />
            <p>{t('knowledge.qa.noPairs')}</p>
          </div>
        ) : (
          <div className="space-y-4">
            {filteredPairs.map((pair) => (
              <div
                key={pair.id}
                className="bg-white dark:bg-gray-800 rounded-lg p-4 shadow-sm border border-gray-200 dark:border-gray-700"
              >
                <div className="flex justify-between items-start mb-2">
                  <div className="flex-1">
                    <div className="font-medium text-gray-900 dark:text-white mb-1">
                      Q: {pair.question}
                    </div>
                    <div className="text-gray-600 dark:text-gray-400 text-sm">
                      A: {pair.answer.length > 200 ? `${pair.answer.slice(0, 200)}...` : pair.answer}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 ml-4">
                    <button
                      onClick={() => openEditDialog(pair)}
                      className="p-2 text-gray-500 hover:text-blue-500 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded"
                    >
                      <Pencil className="h-4 w-4" />
                    </button>
                    <button
                      onClick={() => handleDeletePair(pair.id)}
                      disabled={deletingIds.has(pair.id)}
                      className="p-2 text-gray-500 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 rounded"
                    >
                      {deletingIds.has(pair.id) ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Trash2 className="h-4 w-4" />
                      )}
                    </button>
                  </div>
                </div>
                <div className="flex items-center gap-4 text-xs text-gray-500">
                  <span className="flex items-center gap-1">
                    {getStatusIcon(pair.status)}
                    {t(`knowledge.qa.status.${pair.status}`)}
                  </span>
                  {pair.category && (
                    <span className="flex items-center gap-1">
                      <Filter className="h-3 w-3" />
                      {pair.category}
                    </span>
                  )}
                  {pair.tags && pair.tags.length > 0 && (
                    <span>{pair.tags.join(', ')}</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-center gap-2 mt-6">
            <button
              onClick={() => goToPage(currentPage - 1)}
              disabled={currentPage === 1}
              className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <ChevronLeft className="h-5 w-5" />
            </button>
            <span className="text-sm text-gray-500">
              {t('knowledge.qa.pagination', { current: currentPage, total: totalPages })}
            </span>
            <button
              onClick={() => goToPage(currentPage + 1)}
              disabled={currentPage === totalPages}
              className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <ChevronRight className="h-5 w-5" />
            </button>
          </div>
        )}

      {/* Add/Edit Dialog */}
      {(isAddDialogOpen || isEditDialogOpen) && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-gray-800 rounded-lg w-full max-w-2xl mx-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
              <h2 className="text-lg font-semibold">
                {isEditDialogOpen ? t('knowledge.qa.editTitle') : t('knowledge.qa.addTitle')}
              </h2>
              <button
                onClick={() => {
                  setIsAddDialogOpen(false);
                  setIsEditDialogOpen(false);
                  setEditingPair(null);
                  resetForm();
                }}
                className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="p-4 space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">
                  {t('knowledge.qa.form.question')} *
                </label>
                <textarea
                  value={formQuestion}
                  onChange={(e) => setFormQuestion(e.target.value)}
                  rows={3}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-900"
                  placeholder={t('knowledge.qa.form.questionPlaceholder')}
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">
                  {t('knowledge.qa.form.answer')} *
                </label>
                <textarea
                  value={formAnswer}
                  onChange={(e) => setFormAnswer(e.target.value)}
                  rows={5}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-900"
                  placeholder={t('knowledge.qa.form.answerPlaceholder')}
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">
                  {t('knowledge.qa.form.category')}
                </label>
                <input
                  type="text"
                  value={formCategory}
                  onChange={(e) => setFormCategory(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-900"
                  placeholder={t('knowledge.qa.form.categoryPlaceholder')}
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">
                  {t('knowledge.qa.form.tags')}
                </label>
                <input
                  type="text"
                  value={formTags}
                  onChange={(e) => setFormTags(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-900"
                  placeholder={t('knowledge.qa.form.tagsPlaceholder')}
                />
                <p className="text-xs text-gray-500 mt-1">{t('knowledge.qa.form.tagsHint')}</p>
              </div>
            </div>
            <div className="flex justify-end gap-2 p-4 border-t border-gray-200 dark:border-gray-700">
              <button
                onClick={() => {
                  setIsAddDialogOpen(false);
                  setIsEditDialogOpen(false);
                  setEditingPair(null);
                  resetForm();
                }}
                className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700"
              >
                {t('common.cancel')}
              </button>
              <button
                onClick={isEditDialogOpen ? handleEditPair : handleAddPair}
                disabled={isSubmitting || !formQuestion.trim() || !formAnswer.trim()}
                className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {isSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
                {isEditDialogOpen ? t('common.save') : t('common.add')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Import Dialog */}
      {isImportDialogOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-gray-800 rounded-lg w-full max-w-2xl mx-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
              <h2 className="text-lg font-semibold">{t('knowledge.qa.importTitle')}</h2>
              <button
                onClick={() => {
                  setIsImportDialogOpen(false);
                  setImportData('');
                }}
                className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="p-4 space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">
                  {t('knowledge.qa.importFormat')}
                </label>
                <div className="flex gap-4">
                  <label className="flex items-center gap-2">
                    <input
                      type="radio"
                      value="json"
                      checked={importFormat === 'json'}
                      onChange={() => setImportFormat('json')}
                    />
                    JSON
                  </label>
                  <label className="flex items-center gap-2">
                    <input
                      type="radio"
                      value="csv"
                      checked={importFormat === 'csv'}
                      onChange={() => setImportFormat('csv')}
                    />
                    CSV
                  </label>
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">
                  {t('knowledge.qa.importData')}
                </label>
                <textarea
                  value={importData}
                  onChange={(e) => setImportData(e.target.value)}
                  rows={10}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-900 font-mono text-sm"
                  placeholder={
                    importFormat === 'json'
                      ? t('knowledge.qa.importJsonPlaceholder')
                      : t('knowledge.qa.importCsvPlaceholder')
                  }
                />
              </div>
              <div className="text-sm text-gray-500">
                {importFormat === 'json' ? (
                  <div>
                    <p className="font-medium mb-1">{t('knowledge.qa.importJsonFormat')}</p>
                    <pre className="bg-gray-100 dark:bg-gray-900 p-2 rounded text-xs overflow-x-auto">
{`[
  {"question": "问题1", "answer": "答案1"},
  {"question": "问题2", "answer": "答案2"}
]`}
                    </pre>
                  </div>
                ) : (
                  <div>
                    <p className="font-medium mb-1">{t('knowledge.qa.importCsvFormat')}</p>
                    <pre className="bg-gray-100 dark:bg-gray-900 p-2 rounded text-xs overflow-x-auto">
{`question,answer
问题1,答案1
问题2,答案2`}
                    </pre>
                  </div>
                )}
              </div>
            </div>
            <div className="flex justify-end gap-2 p-4 border-t border-gray-200 dark:border-gray-700">
              <button
                onClick={() => {
                  setIsImportDialogOpen(false);
                  setImportData('');
                }}
                className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700"
              >
                {t('common.cancel')}
              </button>
              <button
                onClick={handleImport}
                disabled={isImporting || !importData.trim()}
                className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {isImporting && <Loader2 className="h-4 w-4 animate-spin" />}
                {t('knowledge.qa.importButton')}
              </button>
            </div>
          </div>
        </div>
      )}
      </div>
    </div>
  );
};

export default QAKnowledgeBaseDetail;

