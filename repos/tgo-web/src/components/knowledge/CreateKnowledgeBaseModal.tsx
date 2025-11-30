import React, { useState, useCallback } from 'react';
import { X, FileText, Globe, ChevronDown, ChevronUp, Info, Loader2, RefreshCw } from 'lucide-react';
import { IconPicker, DEFAULT_ICON } from './IconPicker';
import { TagInput } from '@/components/ui/TagInput';
import type { KnowledgeBaseType, WebsiteCrawlConfig, CrawlOptions } from '@/types';
import KnowledgeBaseApiService from '@/services/knowledgeBaseApi';

import { useTranslation } from 'react-i18next';

export interface CreateKnowledgeBaseData {
  name: string;
  description: string;
  icon: string;
  tags: string[];
  type: KnowledgeBaseType;
  crawlConfig?: WebsiteCrawlConfig;
}

interface CreateKnowledgeBaseModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: CreateKnowledgeBaseData) => Promise<void>;
  isLoading?: boolean;
}

const DEFAULT_CRAWL_CONFIG: WebsiteCrawlConfig = {
  start_url: '',
  max_pages: 100,
  max_depth: 3,
  include_patterns: [],
  exclude_patterns: [],
  options: {
    render_js: false,
    wait_time: 0,
    follow_external_links: false,
    respect_robots_txt: true,
  }
};

export const CreateKnowledgeBaseModal: React.FC<CreateKnowledgeBaseModalProps> = ({
  isOpen,
  onClose,
  onSubmit,
  isLoading = false
}) => {
  const { t } = useTranslation();

  const [formData, setFormData] = useState({
    name: '',
    description: '',
    icon: DEFAULT_ICON,
    tags: [] as string[],
    type: 'file' as KnowledgeBaseType,
    crawlConfig: { ...DEFAULT_CRAWL_CONFIG }
  });
  const [errors, setErrors] = useState({
    name: '',
    description: '',
    startUrl: ''
  });
  const [showAdvancedOptions, setShowAdvancedOptions] = useState(false);
  const [isLoadingMetadata, setIsLoadingMetadata] = useState(false);
  const [metadataError, setMetadataError] = useState<string | null>(null);
  const [metadataFetched, setMetadataFetched] = useState(false);

  // Reset form when modal opens/closes
  React.useEffect(() => {
    if (isOpen) {
      setFormData({
        name: '',
        description: '',
        icon: DEFAULT_ICON,
        tags: [],
        type: 'file',
        crawlConfig: { ...DEFAULT_CRAWL_CONFIG }
      });
      setErrors({ name: '', description: '', startUrl: '' });
      setShowAdvancedOptions(false);
      setIsLoadingMetadata(false);
      setMetadataError(null);
      setMetadataFetched(false);
    }
  }, [isOpen]);

  // Fetch website metadata
  const fetchWebsiteMetadata = useCallback(async (url: string) => {
    if (!url.trim()) return;

    // Validate URL first
    let parsedUrl: URL;
    try {
      parsedUrl = new URL(url);
    } catch {
      return; // Invalid URL, don't fetch
    }

    setIsLoadingMetadata(true);
    setMetadataError(null);

    try {
      const metadata = await KnowledgeBaseApiService.extractWebsiteMetadata(url);

      if (metadata.success) {
        // Fallback logic: use domain as title if title is empty
        const hostname = parsedUrl.hostname;
        const fallbackTitle = metadata.title?.trim() || hostname;
        // Fallback logic: use default description if description is empty
        const fallbackDescription = metadata.description?.trim() ||
          t('knowledge.metadata.defaultDescription', '来自 {{domain}} 的知识库', { domain: hostname });

        setFormData(prev => ({
          ...prev,
          name: fallbackTitle,
          description: fallbackDescription,
          icon: 'globe' // Default to globe icon for websites
        }));
        setMetadataFetched(true);
      } else {
        // API call succeeded but returned error - still apply fallback
        const hostname = parsedUrl.hostname;
        setFormData(prev => ({
          ...prev,
          name: prev.name || hostname,
          description: prev.description || t('knowledge.metadata.defaultDescription', '来自 {{domain}} 的知识库', { domain: hostname }),
          icon: 'globe'
        }));
        setMetadataError(metadata.error || t('knowledge.metadata.fetchFailed', '无法获取网站信息'));
        setMetadataFetched(true); // Still mark as fetched since we applied fallback
      }
    } catch (error) {
      // Network error or other failure - apply fallback
      const hostname = parsedUrl.hostname;
      setFormData(prev => ({
        ...prev,
        name: prev.name || hostname,
        description: prev.description || t('knowledge.metadata.defaultDescription', '来自 {{domain}} 的知识库', { domain: hostname }),
        icon: 'globe'
      }));
      console.error('Failed to fetch website metadata:', error);
      setMetadataError(error instanceof Error ? error.message : t('knowledge.metadata.fetchFailed', '无法获取网站信息'));
      setMetadataFetched(true); // Still mark as fetched since we applied fallback
    } finally {
      setIsLoadingMetadata(false);
    }
  }, [t]);

  const validateForm = (): boolean => {
    const newErrors = { name: '', description: '', startUrl: '' };
    let isValid = true;

    // Validate name
    if (!formData.name.trim()) {
      newErrors.name = t('knowledge.validation.nameRequired', '知识库名称不能为空');
      isValid = false;
    } else if (formData.name.trim().length < 2) {
      newErrors.name = t('knowledge.validation.nameMin', '知识库名称至少需要2个字符');
      isValid = false;
    } else if (formData.name.trim().length > 50) {
      newErrors.name = t('knowledge.validation.nameMax', '知识库名称不能超过50个字符');
      isValid = false;
    }

    // Validate description
    if (!formData.description.trim()) {
      newErrors.description = t('knowledge.validation.descRequired', '知识库描述不能为空');
      isValid = false;
    } else if (formData.description.trim().length < 5) {
      newErrors.description = t('knowledge.validation.descMin', '知识库描述至少需要5个字符');
      isValid = false;
    } else if (formData.description.trim().length > 500) {
      newErrors.description = t('knowledge.validation.descMax', '知识库描述不能超过500个字符');
      isValid = false;
    }

    // Validate website-specific fields
    if (formData.type === 'website') {
      const url = formData.crawlConfig.start_url.trim();
      if (!url) {
        newErrors.startUrl = t('knowledge.validation.urlRequired', '网站URL不能为空');
        isValid = false;
      } else {
        try {
          new URL(url);
        } catch {
          newErrors.startUrl = t('knowledge.validation.urlInvalid', '请输入有效的URL地址');
          isValid = false;
        }
      }
    }

    setErrors(newErrors);
    return isValid;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validateForm()) {
      return;
    }

    try {
      const submitData: CreateKnowledgeBaseData = {
        name: formData.name.trim(),
        description: formData.description.trim(),
        icon: formData.icon,
        tags: formData.tags,
        type: formData.type
      };

      if (formData.type === 'website') {
        submitData.crawlConfig = {
          ...formData.crawlConfig,
          start_url: formData.crawlConfig.start_url.trim()
        };
      }

      await onSubmit(submitData);
      onClose();
    } catch (error) {
      // Error handling is done by the parent component
      console.error('Failed to create knowledge base:', error);
    }
  };

  const handleInputChange = (field: 'name' | 'description', value: string) => {
    setFormData(prev => ({ ...prev, [field]: value }));

    // Clear error when user starts typing
    if (errors[field]) {
      setErrors(prev => ({ ...prev, [field]: '' }));
    }
  };

  const handleIconChange = (iconName: string) => {
    setFormData(prev => ({ ...prev, icon: iconName }));
  };

  const handleTagsChange = (tags: string[]) => {
    setFormData(prev => ({ ...prev, tags }));
  };

  const handleTypeChange = (type: KnowledgeBaseType) => {
    setFormData(prev => ({
      ...prev,
      type,
      // Set default icon based on type
      icon: type === 'website' ? 'globe' : DEFAULT_ICON
    }));
    if (type === 'file') {
      setErrors(prev => ({ ...prev, startUrl: '' }));
      setMetadataError(null);
      setMetadataFetched(false);
    }
  };

  const handleCrawlConfigChange = <K extends keyof WebsiteCrawlConfig>(
    key: K,
    value: WebsiteCrawlConfig[K]
  ) => {
    setFormData(prev => ({
      ...prev,
      crawlConfig: { ...prev.crawlConfig, [key]: value }
    }));
    if (key === 'start_url' && errors.startUrl) {
      setErrors(prev => ({ ...prev, startUrl: '' }));
    }
  };

  const handleCrawlOptionsChange = <K extends keyof CrawlOptions>(
    key: K,
    value: CrawlOptions[K]
  ) => {
    setFormData(prev => ({
      ...prev,
      crawlConfig: {
        ...prev.crawlConfig,
        options: { ...prev.crawlConfig.options, [key]: value }
      }
    }));
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-lg mx-4 max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200 dark:border-gray-700 flex-shrink-0">
          <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-100">{t('knowledge.create', '创建知识库')}</h2>
          <button
            onClick={onClose}
            disabled={isLoading}
            className="text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 dark:bg-gray-900 overflow-y-auto flex-1">
          <div className="space-y-4">
            {/* Type Selection */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-2">
                {t('knowledge.type', '知识库类型')} <span className="text-red-500 dark:text-red-400">*</span>
              </label>
              <div className="grid grid-cols-2 gap-3">
                <button
                  type="button"
                  onClick={() => handleTypeChange('file')}
                  disabled={isLoading}
                  className={`flex items-center justify-center gap-2 p-3 border-2 rounded-lg transition-all ${
                    formData.type === 'file'
                      ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300'
                      : 'border-gray-200 dark:border-gray-600 hover:border-gray-300 dark:hover:border-gray-500'
                  } ${isLoading ? 'cursor-not-allowed opacity-50' : ''}`}
                >
                  <FileText className="w-5 h-5" />
                  <span className="font-medium">{t('knowledge.typeFile', '文件')}</span>
                </button>
                <button
                  type="button"
                  onClick={() => handleTypeChange('website')}
                  disabled={isLoading}
                  className={`flex items-center justify-center gap-2 p-3 border-2 rounded-lg transition-all ${
                    formData.type === 'website'
                      ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300'
                      : 'border-gray-200 dark:border-gray-600 hover:border-gray-300 dark:hover:border-gray-500'
                  } ${isLoading ? 'cursor-not-allowed opacity-50' : ''}`}
                >
                  <Globe className="w-5 h-5" />
                  <span className="font-medium">{t('knowledge.typeWebsite', '网站')}</span>
                </button>
              </div>
              <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                {formData.type === 'file'
                  ? t('knowledge.typeFileDesc', '上传文档文件来构建知识库')
                  : t('knowledge.typeWebsiteDesc', '爬取网站内容来构建知识库')}
              </p>
            </div>

            {/* File Type: Show all fields directly */}
            {formData.type === 'file' && (
              <>
                {/* Icon Field */}
                <div>
                  <label htmlFor="kb-icon" className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-1">
                    {t('knowledge.icon', '知识库图标')}
                  </label>
                  <IconPicker
                    selectedIcon={formData.icon}
                    onIconSelect={handleIconChange}
                    disabled={isLoading}
                  />
                  <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                    {t('knowledge.iconHelper', '选择一个图标来标识您的知识库')}
                  </p>
                </div>

                {/* Name Field */}
                <div>
                  <label htmlFor="kb-name" className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-1">
                    {t('knowledge.name', '知识库名称')} <span className="text-red-500 dark:text-red-400">*</span>
                  </label>
                  <input
                    id="kb-name"
                    type="text"
                    value={formData.name}
                    onChange={(e) => handleInputChange('name', e.target.value)}
                    placeholder={t('knowledge.namePlaceholder', '请输入知识库名称')}
                    disabled={isLoading}
                    className={`w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors dark:bg-gray-700 dark:text-gray-100 ${
                      errors.name ? 'border-red-300 bg-red-50 dark:border-red-600 dark:bg-red-950' : 'border-gray-300 dark:border-gray-600'
                    } ${isLoading ? 'bg-gray-100 dark:bg-gray-800 cursor-not-allowed' : ''}`}
                    maxLength={50}
                  />
                  {errors.name && (
                    <p className="mt-1 text-sm text-red-600 dark:text-red-400">{errors.name}</p>
                  )}
                  <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                    {formData.name.length}/50 {t('common.characters', '字符')}
                  </p>
                </div>

                {/* Description Field */}
                <div>
                  <label htmlFor="kb-description" className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-1">
                    {t('knowledge.description', '知识库描述')} <span className="text-red-500 dark:text-red-400">*</span>
                  </label>
                  <textarea
                    id="kb-description"
                    value={formData.description}
                    onChange={(e) => handleInputChange('description', e.target.value)}
                    placeholder={t('knowledge.descriptionPlaceholder', '请输入知识库描述，简要说明这个知识库的用途和内容')}
                    disabled={isLoading}
                    rows={3}
                    className={`w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors resize-none dark:bg-gray-700 dark:text-gray-100 ${
                      errors.description ? 'border-red-300 bg-red-50 dark:border-red-600 dark:bg-red-950' : 'border-gray-300 dark:border-gray-600'
                    } ${isLoading ? 'bg-gray-100 dark:bg-gray-800 cursor-not-allowed' : ''}`}
                    maxLength={500}
                  />
                  {errors.description && (
                    <p className="mt-1 text-sm text-red-600 dark:text-red-400">{errors.description}</p>
                  )}
                  <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                    {formData.description.length}/500 {t('common.characters', '字符')}
                  </p>
                </div>

                {/* Tags Field */}
                <div>
                  <label htmlFor="kb-tags" className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-1">
                    {t('knowledge.tags', '知识库标签')}
                  </label>
                  <TagInput
                    tags={formData.tags}
                    onTagsChange={handleTagsChange}
                    placeholder={t('knowledge.tagsPlaceholder', '输入标签并按回车键添加')}
                    maxTags={10}
                    maxTagLength={20}
                    disabled={isLoading}
                  />
                  <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                    {t('knowledge.tagsHelper', '添加标签可以帮助您更好地组织和查找知识库')}
                  </p>
                </div>
              </>
            )}

            {/* Website Type: Simplified form with URL input + auto-fetch + advanced settings */}
            {formData.type === 'website' && (
              <div className="space-y-4">
                {/* Start URL - Main input */}
                <div>
                  <label htmlFor="crawl-url" className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-1">
                    {t('knowledge.crawl.startUrl', '网站URL')} <span className="text-red-500 dark:text-red-400">*</span>
                  </label>
                  <div className="flex gap-2">
                    <input
                      id="crawl-url"
                      type="url"
                      value={formData.crawlConfig.start_url}
                      onChange={(e) => {
                        handleCrawlConfigChange('start_url', e.target.value);
                        setMetadataFetched(false);
                        setMetadataError(null);
                      }}
                      onBlur={(e) => {
                        if (e.target.value && !metadataFetched) {
                          fetchWebsiteMetadata(e.target.value);
                        }
                      }}
                      placeholder={t('knowledge.crawl.startUrlPlaceholder', 'https://example.com')}
                      disabled={isLoading || isLoadingMetadata}
                      className={`flex-1 px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors dark:bg-gray-700 dark:text-gray-100 ${
                        errors.startUrl ? 'border-red-300 bg-red-50 dark:border-red-600 dark:bg-red-950' : 'border-gray-300 dark:border-gray-600'
                      } ${isLoading || isLoadingMetadata ? 'bg-gray-100 dark:bg-gray-800 cursor-not-allowed' : ''}`}
                    />
                    <button
                      type="button"
                      onClick={() => fetchWebsiteMetadata(formData.crawlConfig.start_url)}
                      disabled={isLoading || isLoadingMetadata || !formData.crawlConfig.start_url}
                      className="px-3 py-2 bg-gray-100 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-md hover:bg-gray-200 dark:hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-1"
                      title={t('knowledge.metadata.fetch', '获取信息')}
                    >
                      {isLoadingMetadata ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <RefreshCw className="w-4 h-4" />
                      )}
                    </button>
                  </div>
                  {errors.startUrl && (
                    <p className="mt-1 text-sm text-red-600 dark:text-red-400">{errors.startUrl}</p>
                  )}
                  {isLoadingMetadata && (
                    <p className="mt-1 text-xs text-blue-600 dark:text-blue-400 flex items-center gap-1">
                      <Loader2 className="w-3 h-3 animate-spin" />
                      {t('knowledge.metadata.fetching', '正在获取网站信息...')}
                    </p>
                  )}
                  {metadataError && (
                    <p className="mt-1 text-xs text-amber-600 dark:text-amber-400">
                      {metadataError}
                    </p>
                  )}
                  {metadataFetched && !isLoadingMetadata && (
                    <p className="mt-1 text-xs text-green-600 dark:text-green-400">
                      {t('knowledge.metadata.fetchSuccess', '已获取网站信息')}
                    </p>
                  )}
                  {!isLoadingMetadata && !metadataFetched && !metadataError && (
                    <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                      {t('knowledge.metadata.hint', '输入URL后将自动获取网站标题和描述')}
                    </p>
                  )}
                </div>

                {/* Advanced Settings Toggle */}
                <button
                  type="button"
                  onClick={() => setShowAdvancedOptions(!showAdvancedOptions)}
                  className="flex items-center gap-1 text-sm text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300"
                >
                  {showAdvancedOptions ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                  {t('knowledge.advancedSettings', '高级设置')}
                </button>

                {/* Advanced Settings Panel */}
                {showAdvancedOptions && (
                  <div className="space-y-4 p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
                    {/* Name Field */}
                    <div>
                      <label htmlFor="kb-name-website" className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-1">
                        {t('knowledge.name', '知识库名称')} <span className="text-red-500 dark:text-red-400">*</span>
                      </label>
                      <input
                        id="kb-name-website"
                        type="text"
                        value={formData.name}
                        onChange={(e) => handleInputChange('name', e.target.value)}
                        placeholder={t('knowledge.namePlaceholder', '请输入知识库名称')}
                        disabled={isLoading}
                        className={`w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors dark:bg-gray-700 dark:text-gray-100 ${
                          errors.name ? 'border-red-300 bg-red-50 dark:border-red-600 dark:bg-red-950' : 'border-gray-300 dark:border-gray-600'
                        } ${isLoading ? 'bg-gray-100 dark:bg-gray-800 cursor-not-allowed' : ''}`}
                        maxLength={50}
                      />
                      {errors.name && (
                        <p className="mt-1 text-sm text-red-600 dark:text-red-400">{errors.name}</p>
                      )}
                      <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                        {formData.name.length}/50 {t('common.characters', '字符')}
                      </p>
                    </div>

                    {/* Description Field */}
                    <div>
                      <label htmlFor="kb-description-website" className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-1">
                        {t('knowledge.description', '知识库描述')} <span className="text-red-500 dark:text-red-400">*</span>
                      </label>
                      <textarea
                        id="kb-description-website"
                        value={formData.description}
                        onChange={(e) => handleInputChange('description', e.target.value)}
                        placeholder={t('knowledge.descriptionPlaceholder', '请输入知识库描述，简要说明这个知识库的用途和内容')}
                        disabled={isLoading}
                        rows={2}
                        className={`w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors resize-none dark:bg-gray-700 dark:text-gray-100 ${
                          errors.description ? 'border-red-300 bg-red-50 dark:border-red-600 dark:bg-red-950' : 'border-gray-300 dark:border-gray-600'
                        } ${isLoading ? 'bg-gray-100 dark:bg-gray-800 cursor-not-allowed' : ''}`}
                        maxLength={500}
                      />
                      {errors.description && (
                        <p className="mt-1 text-sm text-red-600 dark:text-red-400">{errors.description}</p>
                      )}
                    </div>

                    {/* Icon Field */}
                    <div>
                      <label htmlFor="kb-icon-website" className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-1">
                        {t('knowledge.icon', '知识库图标')}
                      </label>
                      <IconPicker
                        selectedIcon={formData.icon}
                        onIconSelect={handleIconChange}
                        disabled={isLoading}
                      />
                    </div>

                    {/* Tags Field */}
                    <div>
                      <label htmlFor="kb-tags-website" className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-1">
                        {t('knowledge.tags', '知识库标签')}
                      </label>
                      <TagInput
                        tags={formData.tags}
                        onTagsChange={handleTagsChange}
                        placeholder={t('knowledge.tagsPlaceholder', '输入标签并按回车键添加')}
                        maxTags={10}
                        maxTagLength={20}
                        disabled={isLoading}
                      />
                    </div>

                    {/* Crawl Configuration Section */}
                    <div className="pt-4 border-t border-gray-200 dark:border-gray-700">
                      <h4 className="text-sm font-medium text-gray-700 dark:text-gray-200 mb-3 flex items-center gap-2">
                        <Globe className="w-4 h-4" />
                        {t('knowledge.crawl.title', '爬取配置')}
                      </h4>

                      {/* Max Pages & Max Depth */}
                      <div className="grid grid-cols-2 gap-4 mb-4">
                        <div>
                          <label htmlFor="crawl-max-pages" className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-1">
                            {t('knowledge.crawl.maxPages', '最大页面数')}
                          </label>
                          <input
                            id="crawl-max-pages"
                            type="number"
                            min={1}
                            max={10000}
                            value={formData.crawlConfig.max_pages}
                            onChange={(e) => handleCrawlConfigChange('max_pages', Math.min(10000, Math.max(1, parseInt(e.target.value) || 100)))}
                            disabled={isLoading}
                            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors dark:bg-gray-700 dark:text-gray-100"
                          />
                          <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                            {t('knowledge.crawl.maxPagesHint', '1-10000，默认100')}
                          </p>
                        </div>
                        <div>
                          <label htmlFor="crawl-max-depth" className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-1">
                            {t('knowledge.crawl.maxDepth', '最大深度')}
                          </label>
                          <input
                            id="crawl-max-depth"
                            type="number"
                            min={1}
                            max={10}
                            value={formData.crawlConfig.max_depth}
                            onChange={(e) => handleCrawlConfigChange('max_depth', Math.min(10, Math.max(1, parseInt(e.target.value) || 3)))}
                            disabled={isLoading}
                            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors dark:bg-gray-700 dark:text-gray-100"
                          />
                          <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                            {t('knowledge.crawl.maxDepthHint', '1-10，默认3')}
                          </p>
                        </div>
                      </div>

                      {/* Include Patterns */}
                      <div className="mb-4">
                        <label htmlFor="crawl-include" className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-1">
                          {t('knowledge.crawl.includePatterns', '包含模式')}
                        </label>
                        <input
                          id="crawl-include"
                          type="text"
                          value={formData.crawlConfig.include_patterns?.join(', ') || ''}
                          onChange={(e) => handleCrawlConfigChange('include_patterns', e.target.value.split(',').map(s => s.trim()).filter(Boolean))}
                          placeholder={t('knowledge.crawl.includePatternsPlaceholder', '/docs/*, /blog/*')}
                          disabled={isLoading}
                          className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors dark:bg-gray-700 dark:text-gray-100"
                        />
                        <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                          {t('knowledge.crawl.includePatternsHint', '用逗号分隔的URL模式，只爬取匹配的页面')}
                        </p>
                      </div>

                      {/* Exclude Patterns */}
                      <div className="mb-4">
                        <label htmlFor="crawl-exclude" className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-1">
                          {t('knowledge.crawl.excludePatterns', '排除模式')}
                        </label>
                        <input
                          id="crawl-exclude"
                          type="text"
                          value={formData.crawlConfig.exclude_patterns?.join(', ') || ''}
                          onChange={(e) => handleCrawlConfigChange('exclude_patterns', e.target.value.split(',').map(s => s.trim()).filter(Boolean))}
                          placeholder={t('knowledge.crawl.excludePatternsPlaceholder', '/admin/*, /login/*')}
                          disabled={isLoading}
                          className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors dark:bg-gray-700 dark:text-gray-100"
                        />
                        <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                          {t('knowledge.crawl.excludePatternsHint', '用逗号分隔的URL模式，跳过匹配的页面')}
                        </p>
                      </div>

                      {/* Crawl Options */}
                      <div className="space-y-3 mb-4">
                        <label className="flex items-center gap-2 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={formData.crawlConfig.options?.render_js || false}
                            onChange={(e) => handleCrawlOptionsChange('render_js', e.target.checked)}
                            disabled={isLoading}
                            className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                          />
                          <span className="text-sm text-gray-700 dark:text-gray-200">
                            {t('knowledge.crawl.renderJs', '渲染JavaScript')}
                          </span>
                          <span title={t('knowledge.crawl.renderJsHint', '启用后会执行页面JavaScript，适用于动态内容网站')}>
                            <Info className="w-4 h-4 text-gray-400" />
                          </span>
                        </label>

                        <label className="flex items-center gap-2 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={formData.crawlConfig.options?.follow_external_links || false}
                            onChange={(e) => handleCrawlOptionsChange('follow_external_links', e.target.checked)}
                            disabled={isLoading}
                            className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                          />
                          <span className="text-sm text-gray-700 dark:text-gray-200">
                            {t('knowledge.crawl.followExternal', '跟踪外部链接')}
                          </span>
                        </label>

                        <label className="flex items-center gap-2 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={formData.crawlConfig.options?.respect_robots_txt !== false}
                            onChange={(e) => handleCrawlOptionsChange('respect_robots_txt', e.target.checked)}
                            disabled={isLoading}
                            className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                          />
                          <span className="text-sm text-gray-700 dark:text-gray-200">
                            {t('knowledge.crawl.respectRobots', '遵守robots.txt')}
                          </span>
                        </label>
                      </div>

                      {/* Wait Time */}
                      <div>
                        <label htmlFor="crawl-wait-time" className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-1">
                          {t('knowledge.crawl.waitTime', '等待时间（秒）')}
                        </label>
                        <input
                          id="crawl-wait-time"
                          type="number"
                          min={0}
                          max={30}
                          value={formData.crawlConfig.options?.wait_time || 0}
                          onChange={(e) => handleCrawlOptionsChange('wait_time', Math.min(30, Math.max(0, parseInt(e.target.value) || 0)))}
                          disabled={isLoading}
                          className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors dark:bg-gray-700 dark:text-gray-100"
                        />
                        <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                          {t('knowledge.crawl.waitTimeHint', '页面加载后等待的时间，用于动态内容')}
                        </p>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="flex justify-end space-x-3 mt-6 pt-4 border-t border-gray-200 dark:border-gray-700">
            <button
              type="button"
              onClick={onClose}
              disabled={isLoading || isLoadingMetadata}
              className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-200 bg-gray-100 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-md hover:bg-gray-200 dark:hover:bg-gray-600 focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {t('common.cancel', '取消')}
            </button>
            <button
              type="submit"
              disabled={isLoading || isLoadingMetadata}
              className="px-4 py-2 text-sm font-medium text-white bg-blue-500 dark:bg-blue-600 border border-transparent rounded-md hover:bg-blue-600 dark:hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center"
            >
              {isLoading ? (
                <>
                  <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  {t('common.creating', '创建中...')}
                </>
              ) : isLoadingMetadata ? (
                <>
                  <Loader2 className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" />
                  {t('knowledge.metadata.fetching', '正在获取信息...')}
                </>
              ) : (
                t('knowledge.create', '创建知识库')
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
