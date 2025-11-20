import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { KnowledgeBaseHeader } from '@/components/knowledge/KnowledgeBaseHeader';
import { FileUpload } from '@/components/knowledge/FileUpload';
import { DocumentList } from '@/components/knowledge/DocumentList';
import { FileManagementService } from '@/services/fileManagementService';
import { transformCollectionToKnowledgeBase } from '@/utils/knowledgeBaseTransforms';
import { KnowledgeBaseApiService } from '@/services/knowledgeBaseApi';
import { useToast } from '@/hooks/useToast';
import { showApiError, showFileSuccess, showFileError } from '@/utils/toastHelpers';
import type { KnowledgeBase, KnowledgeFile } from '@/types';
import { useTranslation } from 'react-i18next';
import ProjectConfigApiService from '@/services/projectConfigApi';
import { useAuthStore } from '@/stores/authStore';

/**
 * Knowledge Base Detail Page Component
 * Based on the HTML reference design
 */
const KnowledgeBaseDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { showToast } = useToast();
  const { t, i18n } = useTranslation();

  const [knowledgeBase, setKnowledgeBase] = useState<KnowledgeBase | null>(null);
  const [documents, setDocuments] = useState<KnowledgeFile[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isUploadVisible, setIsUploadVisible] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [fileTypeFilter, setFileTypeFilter] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [hasError, setHasError] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<Map<string, any>>(new Map());
  const [downloadingFiles, setDownloadingFiles] = useState<Set<string>>(new Set());
  const [deletingFiles, setDeletingFiles] = useState<Set<string>>(new Set());

  // Embedding model check state
  const [hasEmbeddingModel, setHasEmbeddingModel] = useState<boolean>(true);
  const [isCheckingEmbedding, setIsCheckingEmbedding] = useState<boolean>(true);

  // File management service
  const fileServiceRef = useRef<FileManagementService | null>(null);

  // Get project ID from auth store
  const projectId = useAuthStore(state => state.user?.project_id);



  // Check if embedding model is configured
  useEffect(() => {
    const checkEmbeddingModel = async () => {
      if (!projectId) {
        console.warn('No project ID available, skipping embedding model check');
        setIsCheckingEmbedding(false);
        setHasEmbeddingModel(false);
        return;
      }

      setIsCheckingEmbedding(true);
      try {
        const configService = new ProjectConfigApiService();
        const aiConfig = await configService.getAIConfig(projectId);

        // Check if default embedding model is configured
        const hasEmbedding = !!(aiConfig.default_embedding_provider_id && aiConfig.default_embedding_model);
        setHasEmbeddingModel(hasEmbedding);

        console.log('Embedding model check:', {
          hasEmbedding,
          providerId: aiConfig.default_embedding_provider_id,
          model: aiConfig.default_embedding_model
        });
      } catch (error) {
        console.error('Failed to check embedding model configuration:', error);
        // On error, assume no embedding model to be safe
        setHasEmbeddingModel(false);
      } finally {
        setIsCheckingEmbedding(false);
      }
    };

    checkEmbeddingModel();
  }, [projectId]);

  // Initialize page and load knowledge base data
  useEffect(() => {
    if (!id) {
      navigate('/knowledge');
      return;
    }

    const initializePage = async (): Promise<(() => void) | undefined> => {
      setIsLoading(true);
      setError(null);
      setHasError(false);

      try {
        // Get knowledge base from API
        const collection = await KnowledgeBaseApiService.getCollection(id);
        const kb = transformCollectionToKnowledgeBase(collection);
        setKnowledgeBase(kb);

        // Initialize file management service
        fileServiceRef.current = new FileManagementService(id);

        // Subscribe to file service state changes
        const unsubscribe = fileServiceRef.current.subscribe((state) => {
          setDocuments(state.files);
          setIsLoading(state.isLoading);
          setUploadProgress(state.uploadProgress);

          // Debug logging for upload progress
          if (state.uploadProgress.size > 0) {
            console.log('KnowledgeBaseDetail: Upload progress updated:',
              Array.from(state.uploadProgress.values()).map(p => ({
                fileName: p.fileName,
                progress: p.progress,
                status: p.status
              }))
            );
          }
        });

        // Load files
        await fileServiceRef.current.loadFiles();

        setIsLoading(false);
        return unsubscribe;

      } catch (error) {
        console.error('Failed to load knowledge base:', error);
        const errorMessage = error instanceof Error ? error.message : t('knowledge.detail.loadFailedDefault', '加载知识库详情失败');
        setError(errorMessage);
        setHasError(true);
        setIsLoading(false);
        return undefined;
      }
    };

    const cleanup = initializePage();

    return () => {
      cleanup?.then(unsubscribe => unsubscribe?.());
    };
  }, [id, navigate, t]);

  // Handle back navigation
  const handleBack = () => {
    navigate('/knowledge');
  };

  // Handle refresh
  const handleRefresh = async () => {
    if (fileServiceRef.current) {
      try {
        await fileServiceRef.current.loadFiles();
      } catch (error) {
        console.error('Failed to refresh files:', error);
        // Error is already handled in the file service
      }
    }
  };

  // Handle upload toggle
  const handleToggleUpload = () => {
    setIsUploadVisible(!isUploadVisible);
  };

  // Handle file upload
  const handleFileUpload = async (files: File[]) => {
    if (!fileServiceRef.current) {
      console.error('File service not initialized');
      showApiError(showToast, new Error(t('knowledge.detail.fileServiceNotInitialized', '文件服务未初始化')));
      return;
    }

    try {
      await fileServiceRef.current.uploadFiles(files, {
        description: 'Uploaded via web interface',
        tags: ['web-upload'],
      });

      // Show success for multiple files
      if (files.length === 1) {
        showFileSuccess(showToast, 'upload', files[0].name);
      } else {
        showToast('success', t('knowledge.upload.uploadComplete', '上传完成'), t('knowledge.upload.multipleSuccessMessage', { count: files.length, defaultValue: `${files.length} 个文件上传成功` }));
      }
    } catch (error) {
      console.error('File upload failed:', error);
      if (files.length === 1) {
        showFileError(showToast, 'upload', files[0].name, error);
      } else {
        showApiError(showToast, error);
      }
    }
  };

  // Handle document actions
  const handleDownload = async (docId: string) => {
    const doc = documents.find(d => d.id === docId);
    const fileName = doc?.name || 'Unknown file';

    // Add to downloading set
    setDownloadingFiles(prev => new Set(prev).add(docId));

    try {
      const response = await KnowledgeBaseApiService.downloadFile(docId);

      // Get filename from Content-Disposition header or use default
      const contentDisposition = response.headers.get('Content-Disposition');
      let filename = fileName;

      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
        if (filenameMatch && filenameMatch[1]) {
          filename = filenameMatch[1].replace(/['"]/g, '');
        }
      }

      // Create blob and download
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

      showFileSuccess(showToast, 'download', filename);
    } catch (error) {
      console.error('Download failed:', error);
      showFileError(showToast, 'download', fileName, error);
    } finally {
      // Remove from downloading set
      setDownloadingFiles(prev => {
        const newSet = new Set(prev);
        newSet.delete(docId);
        return newSet;
      });
    }
  };

  const handleDelete = async (docId: string) => {
    const doc = documents.find(d => d.id === docId);
    const fileName = doc?.name || 'Unknown file';

    // Show confirmation dialog
    if (!confirm(t('knowledge.file.confirmDelete.message', { name: fileName, defaultValue: `确定要删除文件 "${fileName}" 吗？此操作无法撤销。` }))) {
      return;
    }

    // Add to deleting set
    setDeletingFiles(prev => new Set(prev).add(docId));

    try {
      await KnowledgeBaseApiService.deleteFile(docId);

      // Remove from local documents state
      setDocuments(prev => prev.filter(d => d.id !== docId));

      showFileSuccess(showToast, 'delete', fileName);
    } catch (error) {
      console.error('Delete failed:', error);
      showFileError(showToast, 'delete', fileName, error);
    } finally {
      // Remove from deleting set
      setDeletingFiles(prev => {
        const newSet = new Set(prev);
        newSet.delete(docId);
        return newSet;
      });
    }
  };

  // Calculate stats
  const totalSize = React.useMemo(() => {
    const totalBytes = documents.reduce((sum, doc) => sum + doc.sizeBytes, 0);
    return (totalBytes / (1024 * 1024)).toFixed(1);
  }, [documents]);

  const lastUpdated = React.useMemo(() => {
    if (documents.length === 0) return '';
    const dates = documents.map(doc => new Date(doc.uploadDate));
    const latest = new Date(Math.max(...dates.map(d => d.getTime())));
    return latest.toLocaleDateString(i18n.language || undefined);
  }, [documents]);



  // Show loading state
  if (isLoading) {
    return (
      <div className="flex-grow flex items-center justify-center bg-gray-100">
        <div className="text-center">
          <div className="inline-flex items-center">
            <svg className="w-5 h-5 animate-spin text-blue-500 mr-2" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <span className="text-gray-500">{t('knowledge.detail.loadingDetails', '加载知识库详情中...')}</span>
          </div>
        </div>
      </div>
    );
  }

  // Show error state
  if (hasError) {
    return (
      <div className="flex-grow flex items-center justify-center bg-gray-100">
        <div className="text-center max-w-md">
          <div className="w-16 h-16 mx-auto bg-red-100 rounded-full flex items-center justify-center mb-4">
            <svg className="w-8 h-8 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <h3 className="text-lg font-medium text-gray-800 mb-2">{t('common.loadFailed', '加载失败')}</h3>
          <p className="text-gray-500 mb-4">{error || t('knowledge.detail.loadFailedDesc', '加载知识库详情时发生错误')}</p>
          <div className="flex justify-center space-x-3">
            <button
              onClick={() => window.location.reload()}
              className="inline-flex items-center px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors"
            >
              <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              {t('common.retry', '重试')}
            </button>
            <button
              onClick={() => navigate('/knowledge')}
              className="inline-flex items-center px-4 py-2 bg-gray-500 text-white rounded-lg hover:bg-gray-600 transition-colors"
            >
              {t('knowledge.detail.backToList', '返回列表')}
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Show not found state
  if (!knowledgeBase) {
    return (
      <div className="flex-grow flex items-center justify-center bg-gray-100">
        <div className="text-center">
          <h3 className="text-lg font-medium text-gray-800 mb-2">{t('knowledge.detail.notFound.title', '知识库不存在')}</h3>
          <p className="text-gray-500 mb-4">{t('knowledge.detail.notFound.description', '请检查链接是否正确')}</p>
          <button
            onClick={() => navigate('/knowledge')}
            className="inline-flex items-center px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors"
          >
            {t('knowledge.detail.backToList', '返回列表')}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full w-full bg-gray-100">
      <div className="flex-grow flex flex-col overflow-hidden">
        {/* Header */}
        <KnowledgeBaseHeader
          knowledgeBase={{
            id: knowledgeBase.id,
            name: knowledgeBase.name,
            description: knowledgeBase.description,
            category: knowledgeBase.category,
            tags: knowledgeBase.tags
          }}
          onBack={handleBack}
          onRefresh={handleRefresh}
          onToggleUpload={handleToggleUpload}
          isUploadVisible={isUploadVisible}
          searchTerm={searchTerm}
          onSearchChange={setSearchTerm}
          fileTypeFilter={fileTypeFilter}
          onFilterChange={setFileTypeFilter}
          totalDocuments={documents.length}
          totalSize={totalSize}
          lastUpdated={lastUpdated}
        />
        <div className="flex-grow overflow-y-auto" style={{ height: 0 }}>
          <div className='h-full w-full'>
            {/* Upload Area */}
            <FileUpload
              onUpload={handleFileUpload}
              isVisible={isUploadVisible}
              onToggle={handleToggleUpload}
              uploadProgress={uploadProgress}
              hasEmbeddingModel={hasEmbeddingModel}
              isCheckingEmbedding={isCheckingEmbedding}
            />

            {/* Document List */}
            <DocumentList
              documents={documents}
              isLoading={isLoading}
              onDownload={handleDownload}
              onDelete={handleDelete}
              searchTerm={searchTerm}
              fileTypeFilter={fileTypeFilter}
              downloadingFiles={downloadingFiles}
              deletingFiles={deletingFiles}
            />
          </div>
          <br/><br/><br/><br/>
        </div>

      </div>
    </div>
  );
};

export default KnowledgeBaseDetail;
