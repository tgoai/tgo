import React, { useState, useRef, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { UploadCloud, X, CheckCircle, AlertCircle, Loader, Settings } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

interface FileUploadProgress {
  fileId: string;
  fileName: string;
  progress: number;
  status: 'uploading' | 'processing' | 'completed' | 'error';
  error?: string;
}

interface FileUploadProps {
  onUpload: (files: File[]) => void;
  isVisible: boolean;
  onToggle: () => void;
  uploadProgress?: Map<string, FileUploadProgress>;
  hasEmbeddingModel?: boolean;
  isCheckingEmbedding?: boolean;
}

interface UploadFile extends File {
  id: string;
  progress: number;
  status: 'uploading' | 'success' | 'error';
  error?: string;
}

/**
 * File Upload Component with Drag & Drop
 * Based on the HTML reference design
 */
export const FileUpload: React.FC<FileUploadProps> = ({
  onUpload,
  isVisible,
  uploadProgress,
  hasEmbeddingModel = true,
  isCheckingEmbedding = false
}) => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [isDragOver, setIsDragOver] = useState(false);

  // Determine if upload should be disabled
  const isUploadDisabled = isCheckingEmbedding || !hasEmbeddingModel;

  // Convert service progress to display format
  const displayUploadFiles = React.useMemo(() => {
    if (!uploadProgress) return [];

    const files = Array.from(uploadProgress.values()).map(progress => ({
      id: progress.fileId,
      name: progress.fileName,
      size: 0, // Size not tracked during upload, will be available after completion
      progress: progress.progress,
      status: progress.status === 'completed' ? 'success' :
              progress.status === 'error' ? 'error' : 'uploading',
      error: progress.error,
    } as UploadFile));

    // Debug logging
    if (files.length > 0) {
      console.log('FileUpload: Displaying progress for files:', files.map(f => ({
        name: f.name,
        progress: f.progress,
        status: f.status
      })));
    }

    return files;
  }, [uploadProgress]);

  // Auto-hide completed uploads after a delay
  React.useEffect(() => {
    const completedFiles = displayUploadFiles.filter(file => file.status === 'success');

    if (completedFiles.length > 0) {
      const timer = setTimeout(() => {
        // This will be handled by the service's cleanup logic
        console.log('Completed uploads should be cleaned up by the service');
      }, 2000);

      return () => clearTimeout(timer);
    }

    return undefined;
  }, [displayUploadFiles]);

  // Handle drag events
  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);

    const files = Array.from(e.dataTransfer.files);
    handleFiles(files);
  }, []);

  // Handle file selection
  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    handleFiles(files);
    // Reset input
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  // Process selected files
  const handleFiles = (files: File[]) => {
    // Block upload if embedding model is not configured
    if (isUploadDisabled) {
      return;
    }

    const validFiles = files.filter(file => {
      // Check file size (10MB limit)
      if (file.size > 10 * 1024 * 1024) {
        alert(`${file.name}: ${t('knowledge.upload.maxFileSize')}`);
        return false;
      }

      // Check file type
      const allowedTypes = ['.pdf', '.doc', '.docx', '.txt', '.xlsx', '.xls', '.ppt', '.pptx', '.md', '.markdown', '.html', '.htm'];
      const fileExtension = '.' + file.name.split('.').pop()?.toLowerCase();
      if (!allowedTypes.includes(fileExtension)) {
        alert(`${file.name}: ${t('knowledge.upload.unsupportedFormat')}`);
        return false;
      }

      return true;
    });

    if (validFiles.length > 0) {
      // Call parent upload handler - the service will handle progress tracking
      onUpload(validFiles);
    }
  };

  // Remove upload file from progress (this will be handled by the service)
  const removeUploadFile = (fileId: string) => {
    // In a real implementation, this might cancel the upload
    // For now, we'll just hide it from the UI
    console.log('Remove upload file:', fileId);
  };

  // Get file type icon
  const getFileIcon = (fileName: string | undefined) => {
    if (!fileName) return '📄';
    const extension = fileName.split('.').pop()?.toLowerCase();
    switch (extension) {
      case 'pdf': return '📄';
      case 'doc':
      case 'docx': return '📝';
      case 'txt': return '📃';
      case 'xlsx':
      case 'xls': return '📊';
      case 'ppt':
      case 'pptx': return '📊';
      default: return '📄';
    }
  };

  // Format file size
  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  if (!isVisible) return null;

  return (
    <div className="mx-6 mt-4 p-6 bg-white/80 backdrop-blur-md rounded-lg shadow-sm border border-gray-200/60">
      {/* Embedding Model Warning */}
      {!isCheckingEmbedding && !hasEmbeddingModel && (
        <div className="mb-4 p-4 bg-amber-50 border border-amber-200 rounded-lg">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <h4 className="text-sm font-semibold text-amber-900 mb-1">
                {t('knowledge.upload.noEmbeddingModel.title', '⚠️ 无法上传文件')}
              </h4>
              <p className="text-sm text-amber-800 mb-3">
                {t('knowledge.upload.noEmbeddingModel.description', '系统尚未配置嵌入模型。知识库文件需要嵌入模型进行向量化处理，请先前往 AI 模型提供商设置页面配置默认嵌入模型。')}
              </p>
              <button
                onClick={() => navigate('/settings/providers')}
                className="inline-flex items-center gap-2 px-3 py-1.5 bg-amber-600 text-white text-sm rounded-md hover:bg-amber-700 transition-colors"
              >
                <Settings className="w-4 h-4" />
                {t('knowledge.upload.noEmbeddingModel.goToSettings', '前往配置')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Upload Area */}
      <div
        className={`upload-area rounded-lg p-8 text-center border-2 border-dashed transition-all duration-300 ${
          isUploadDisabled
            ? 'border-gray-200 bg-gray-50 cursor-not-allowed opacity-60'
            : isDragOver
              ? 'border-blue-500 bg-blue-50/50'
              : 'border-gray-300 hover:border-gray-400'
        }`}
        onDragOver={isUploadDisabled ? undefined : handleDragOver}
        onDragLeave={isUploadDisabled ? undefined : handleDragLeave}
        onDrop={isUploadDisabled ? undefined : handleDrop}
      >
        {isCheckingEmbedding ? (
          <>
            <Loader className="w-12 h-12 mx-auto text-gray-400 mb-4 animate-spin" />
            <h3 className="text-lg font-medium text-gray-600 mb-2">
              {t('knowledge.upload.checkingEmbedding', '检查嵌入模型配置...')}
            </h3>
          </>
        ) : (
          <>
            <UploadCloud className={`w-12 h-12 mx-auto mb-4 ${isUploadDisabled ? 'text-gray-300' : 'text-gray-400'}`} />
            <h3 className={`text-lg font-medium mb-2 ${isUploadDisabled ? 'text-gray-500' : 'text-gray-800'}`}>
              {t('knowledge.upload.title')}
            </h3>
            <p className={`text-sm mb-4 ${isUploadDisabled ? 'text-gray-400' : 'text-gray-500'}`}>
              {t('knowledge.upload.supportedFormats')}
            </p>

            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept=".pdf,.doc,.docx,.txt,.xlsx,.xls,.ppt,.pptx,.md,.markdown,.html,.htm"
              onChange={handleFileSelect}
              className="hidden"
              disabled={isUploadDisabled}
            />

            <button
              onClick={() => !isUploadDisabled && fileInputRef.current?.click()}
              disabled={isUploadDisabled}
              className={`px-4 py-2 rounded-md transition-colors duration-200 ${
                isUploadDisabled
                  ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                  : 'bg-blue-500 text-white hover:bg-blue-600'
              }`}
            >
              {t('knowledge.upload.selectFiles')}
            </button>
          </>
        )}
      </div>

      {/* Upload Progress */}
      {displayUploadFiles.length > 0 && (
        <div className="mt-4">
          <div className="space-y-2">
            {displayUploadFiles.map(file => (
              <div
                key={file.id}
                className="flex items-center justify-between p-3 bg-gray-50 rounded-lg border"
              >
                <div className="flex items-center flex-1 min-w-0">
                  <span className="text-xl mr-3">{getFileIcon(file.name)}</span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900 truncate">
                      {file.name || 'Unknown file'}
                    </p>
                    <p className="text-xs text-gray-500">
                      {file.size > 0 ? formatFileSize(file.size) : '上传中...'}
                    </p>
                    
                    {/* Progress bar */}
                    {file.status === 'uploading' && (
                      <div className="mt-2">
                        <div className="flex items-center justify-between text-xs text-gray-600 mb-1">
                          <span>{t('knowledge.upload.uploadProgress')}</span>
                          <span>{Math.round(file.progress)}%</span>
                        </div>
                        <div className="w-full bg-gray-200 rounded-full h-1.5">
                          <div 
                            className="bg-blue-500 h-1.5 rounded-full progress-bar"
                            style={{ width: `${file.progress}%` }}
                          />
                        </div>
                      </div>
                    )}
                    
                    {/* Error message */}
                    {file.status === 'error' && file.error && (
                      <p className="text-xs text-red-500 mt-1">{file.error}</p>
                    )}
                  </div>
                </div>
                
                <div className="flex items-center ml-4">
                  {/* Status icon */}
                  {file.status === 'uploading' && (
                    <Loader className="w-4 h-4 text-blue-500 animate-spin mr-2" />
                  )}
                  {file.status === 'success' && (
                    <CheckCircle className="w-4 h-4 text-green-500 mr-2" />
                  )}
                  {file.status === 'error' && (
                    <AlertCircle className="w-4 h-4 text-red-500 mr-2" />
                  )}
                  
                  {/* Remove button */}
                  <button
                    onClick={() => removeUploadFile(file.id)}
                    className="p-1 text-gray-400 hover:text-red-500 transition-colors"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
