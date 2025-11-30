import React, { useState, useEffect } from 'react';
import { X, FileText, Globe } from 'lucide-react';
import { IconPicker, DEFAULT_ICON } from './IconPicker';
import { TagInput } from '@/components/ui/TagInput';
import type { KnowledgeBaseItem } from '@/types';
import { useTranslation } from 'react-i18next';


interface EditKnowledgeBaseModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (id: string, data: { name: string; description: string; icon: string; tags: string[] }) => Promise<void>;
  knowledgeBase: KnowledgeBaseItem | null;
  isLoading?: boolean;
}

export const EditKnowledgeBaseModal: React.FC<EditKnowledgeBaseModalProps> = ({
  isOpen,
  onClose,
  onSubmit,
  knowledgeBase,
  isLoading = false
}) => {
  const { t } = useTranslation();

  const [formData, setFormData] = useState({
    name: '',
    description: '',
    icon: DEFAULT_ICON,
    tags: [] as string[]
  });
  const [errors, setErrors] = useState({
    name: '',
    description: ''
  });

  // Initialize form data when modal opens or knowledge base changes
  useEffect(() => {
    if (isOpen && knowledgeBase) {
      // Extract tags from the knowledge base
      const existingTags = Array.isArray(knowledgeBase.tags)
        ? knowledgeBase.tags.map(tag => typeof tag === 'string' ? tag : tag.name).filter(Boolean)
        : [];

      setFormData({
        name: knowledgeBase.title || '',
        description: knowledgeBase.content || '',
        icon: knowledgeBase.icon || DEFAULT_ICON,
        tags: existingTags
      });
      setErrors({ name: '', description: '' });
    }
  }, [isOpen, knowledgeBase]);

  const validateForm = (): boolean => {
    const newErrors = { name: '', description: '' };
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

    setErrors(newErrors);
    return isValid;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!knowledgeBase || !validateForm()) {
      return;
    }

    try {
      await onSubmit(knowledgeBase.id, {
        name: formData.name.trim(),
        description: formData.description.trim(),
        icon: formData.icon,
        tags: formData.tags
      });
      onClose();
    } catch (error) {
      // Error handling is done by the parent component
      console.error('Failed to update knowledge base:', error);
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

  const handleClose = () => {
    if (!isLoading) {
      onClose();
    }
  };

  if (!isOpen || !knowledgeBase) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-md max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200 dark:border-gray-700 flex-shrink-0">
          <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-100">{t('knowledge.edit', '编辑知识库')}</h2>
          <button
            onClick={handleClose}
            disabled={isLoading}
            className="text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 transition-colors disabled:opacity-50"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="flex flex-col flex-1 overflow-hidden">
          <div className="p-6 dark:bg-gray-900 overflow-y-auto flex-1">
          <div className="space-y-4">
            {/* Type Display (Read-only) */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-1">
                {t('knowledge.type', '知识库类型')}
              </label>
              <div className={`flex items-center gap-2 px-3 py-2 border rounded-md bg-gray-50 dark:bg-gray-800 border-gray-200 dark:border-gray-600`}>
                {knowledgeBase.type === 'website' ? (
                  <>
                    <Globe className="w-4 h-4 text-blue-500" />
                    <span className="text-sm text-gray-700 dark:text-gray-200">{t('knowledge.typeWebsite', '网站')}</span>
                  </>
                ) : (
                  <>
                    <FileText className="w-4 h-4 text-green-500" />
                    <span className="text-sm text-gray-700 dark:text-gray-200">{t('knowledge.typeFile', '文件')}</span>
                  </>
                )}
              </div>
              <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                {t('knowledge.typeReadonly', '知识库类型创建后不可更改')}
              </p>
            </div>

            {/* Website Crawl Info (Read-only, only for website type) */}
            {knowledgeBase.type === 'website' && knowledgeBase.crawlConfig && (
              <div className="p-3 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg">
                <div className="flex items-center gap-2 mb-2">
                  <Globe className="w-4 h-4 text-blue-500" />
                  <span className="text-sm font-medium text-blue-700 dark:text-blue-300">
                    {t('knowledge.crawl.info', '爬取配置')}
                  </span>
                </div>
                <div className="space-y-1 text-sm text-gray-600 dark:text-gray-400">
                  <p><span className="font-medium">{t('knowledge.crawl.startUrl', '起始URL')}:</span> {knowledgeBase.crawlConfig.start_url}</p>
                  <p><span className="font-medium">{t('knowledge.crawl.maxPages', '最大页面数')}:</span> {knowledgeBase.crawlConfig.max_pages || 100}</p>
                  <p><span className="font-medium">{t('knowledge.crawl.maxDepth', '最大深度')}:</span> {knowledgeBase.crawlConfig.max_depth || 3}</p>
                </div>
              </div>
            )}

            {/* Icon Field */}
            <div>
              <label htmlFor="edit-kb-icon" className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-1">
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
              <label htmlFor="edit-kb-name" className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-1">
                {t('knowledge.name', '知识库名称')} <span className="text-red-500 dark:text-red-400">*</span>
              </label>
              <input
                id="edit-kb-name"
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
              <label htmlFor="edit-kb-description" className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-1">
                {t('knowledge.description', '知识库描述')} <span className="text-red-500 dark:text-red-400">*</span>
              </label>
              <textarea
                id="edit-kb-description"
                value={formData.description}
                onChange={(e) => handleInputChange('description', e.target.value)}
                placeholder={t('knowledge.descriptionPlaceholder', '请输入知识库描述，简要说明这个知识库的用途和内容')}
                disabled={isLoading}
                rows={4}
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
              <label htmlFor="edit-kb-tags" className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-1">
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
            </div>
          </div>

          {/* Footer */}
          <div className="flex justify-end space-x-3 p-6 pt-4 border-t border-gray-200 dark:border-gray-700 flex-shrink-0 bg-white dark:bg-gray-900">
            <button
              type="button"
              onClick={handleClose}
              disabled={isLoading}
              className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-200 bg-gray-100 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-md hover:bg-gray-200 dark:hover:bg-gray-600 focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {t('common.cancel', '取消')}
            </button>
            <button
              type="submit"
              disabled={isLoading}
              className="px-4 py-2 text-sm font-medium text-white bg-blue-500 dark:bg-blue-600 border border-transparent rounded-md hover:bg-blue-600 dark:hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center"
            >
              {isLoading ? (
                <>
                  <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  {t('common.updating', '更新中...')}
                </>
              ) : (
                t('knowledge.update', '更新知识库')
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
