import React, { useState, useMemo } from 'react';
import { useTranslation } from 'react-i18next';

import { Plus, Trash2, Check, X, Edit3 } from 'lucide-react';
import type { CustomAttribute } from '@/data/mockVisitor';

interface CustomAttributeManagerProps {
  attributes: CustomAttribute[];
  onAdd: (key: string, value: string) => void;
  onUpdate: (id: string, key: string, value: string) => void;
  onDelete: (id: string) => void;
  className?: string;
}



/**
 * Custom attribute manager component
 */
const CustomAttributeManager: React.FC<CustomAttributeManagerProps> = ({
  attributes,
  onAdd,
  onUpdate,
  onDelete,
  className = ''
}) => {
  const { t } = useTranslation();

  const [isAdding, setIsAdding] = useState(false);
  const [newKey, setNewKey] = useState('');
  const [newValue, setNewValue] = useState('');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editKey, setEditKey] = useState('');
  const [editValue, setEditValue] = useState('');
  const COMMON_TEMPLATES = useMemo(
    () => [
      t('visitor.customAttr.templates.company', '公司'),
      t('visitor.customAttr.templates.jobTitle', '职位'),
      t('visitor.customAttr.templates.department', '部门'),
      t('visitor.customAttr.templates.industry', '行业'),
      t('visitor.customAttr.templates.sourceChannel', '来源渠道'),
      t('visitor.customAttr.templates.budgetRange', '预算范围'),
      t('visitor.customAttr.templates.decisionAuthority', '决策权限'),
      t('visitor.customAttr.templates.urgency', '紧急程度'),
      t('visitor.customAttr.templates.note', '备注'),
    ],
    [t]
  );

  const [showTemplates, setShowTemplates] = useState(false);

  const handleStartAdd = () => {
    setIsAdding(true);
    setNewKey('');
    setNewValue('');
    setShowTemplates(true);
  };

  const handleCancelAdd = () => {
    setIsAdding(false);
    setNewKey('');
    setNewValue('');
    setShowTemplates(false);
  };

  const handleSaveAdd = () => {
    if (newKey.trim() && newValue.trim()) {
      onAdd(newKey.trim(), newValue.trim());
      handleCancelAdd();
    }
  };

  const handleStartEdit = (attr: CustomAttribute) => {
    setEditingId(attr.id);
    setEditKey(attr.key);
    setEditValue(attr.value);
  };

  const handleCancelEdit = () => {
    setEditingId(null);
    setEditKey('');
    setEditValue('');
  };

  const handleSaveEdit = () => {
    if (editingId && editKey.trim() && editValue.trim()) {
      onUpdate(editingId, editKey.trim(), editValue.trim());
      handleCancelEdit();
    }
  };

  const handleDeleteInEdit = (id: string) => {
    onDelete(id);
    handleCancelEdit(); // 删除后退出编辑状态
  };

  const handleTemplateSelect = (template: string) => {
    setNewKey(template);
    setShowTemplates(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent, action: 'add' | 'edit') => {
    if (e.key === 'Enter') {
      e.preventDefault();
      if (action === 'add') {
        handleSaveAdd();
      } else {
        handleSaveEdit();
      }
    } else if (e.key === 'Escape') {
      e.preventDefault();
      if (action === 'add') {
        handleCancelAdd();
      } else {
        handleCancelEdit();
      }
    }
  };

  return (
    <div className={className}>
      {/* Existing attributes */}
      {attributes.map((attr) => (
        <div key={attr.id} className="flex justify-between items-start group py-0.5">
          {editingId === attr.id ? (
            <div className="flex-1 space-y-2 min-w-0">
              <div className="flex items-center space-x-1">
                <input
                  type="text"
                  value={editKey}
                  onChange={(e) => setEditKey(e.target.value)}
                  onKeyDown={(e) => handleKeyDown(e, 'edit')}
                  placeholder={t('visitor.customAttr.namePlaceholder', '属性名')}
                  className="w-16 px-2 py-1 text-[12px] leading-5 text-gray-800 dark:text-gray-100 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded transition-all focus:outline-none focus:ring-1 focus:ring-blue-500/50"
                />
                <input
                  type="text"
                  value={editValue}
                  onChange={(e) => setEditValue(e.target.value)}
                  onKeyDown={(e) => handleKeyDown(e, 'edit')}
                  placeholder={t('visitor.customAttr.valuePlaceholder', '属性值')}
                  className="flex-1 min-w-0 max-w-[120px] px-2 py-1 text-[12px] leading-5 text-gray-800 dark:text-gray-100 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded transition-all focus:outline-none focus:ring-1 focus:ring-blue-500/50"
                />
                <button
                  onClick={handleSaveEdit}
                  className="p-1 text-green-600 dark:text-green-500 hover:bg-green-50 dark:hover:bg-green-900/20 rounded transition-colors"
                >
                  <Check className="w-3.5 h-3.5" />
                </button>
                <button
                  onClick={handleCancelEdit}
                  className="p-1 text-gray-400 dark:text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
                <button
                  onClick={() => handleDeleteInEdit(editingId!)}
                  className="p-1 text-red-500 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded transition-colors"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          ) : (
            <>
              <span className="text-gray-400 dark:text-gray-500 text-[12px] leading-6 flex-shrink-0">{attr.key}</span>
              <div className="flex items-center space-x-1.5 flex-1 min-w-0 ml-3 justify-end">
                <span
                  className="text-gray-700 dark:text-gray-200 font-medium text-[12px] leading-6 cursor-pointer hover:text-blue-600 dark:hover:text-blue-400 transition-colors truncate max-w-full text-right"
                  onClick={() => handleStartEdit(attr)}
                  title={attr.value}
                >
                  {attr.value}
                </span>
                <Edit3 className="w-2.5 h-2.5 text-gray-300 dark:text-gray-600 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0 cursor-pointer" onClick={() => handleStartEdit(attr)} />
              </div>
            </>
          )}
        </div>
      ))}

      {/* Add new attribute */}
      {isAdding ? (
        <div className="space-y-2.5 pt-2.5 border-t border-gray-100 dark:border-gray-700">
          <div className="flex items-center space-x-1.5">
            <input
              type="text"
              value={newKey}
              onChange={(e) => setNewKey(e.target.value)}
              onKeyDown={(e) => handleKeyDown(e, 'add')}
              placeholder={t('visitor.customAttr.namePlaceholder', '属性名')}
              className="w-16 px-2 py-1.5 text-[13px] leading-5 text-gray-800 dark:text-gray-200 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 dark:focus:ring-blue-400 focus:border-blue-500 dark:focus:border-blue-400 transition-colors"
            />
            <input
              type="text"
              value={newValue}
              onChange={(e) => setNewValue(e.target.value)}
              onKeyDown={(e) => handleKeyDown(e, 'add')}
              placeholder={t('visitor.customAttr.valuePlaceholder', '属性值')}
              className="flex-1 min-w-0 max-w-[100px] px-2 py-1.5 text-[13px] leading-5 text-gray-800 dark:text-gray-200 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 dark:focus:ring-blue-400 focus:border-blue-500 dark:focus:border-blue-400 transition-colors"
            />
            <button
              onClick={handleSaveAdd}
              disabled={!newKey.trim() || !newValue.trim()}
              className="p-1.5 text-green-600 dark:text-green-400 hover:text-green-700 dark:hover:text-green-300 hover:bg-green-50 dark:hover:bg-green-900/30 rounded-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex-shrink-0"
              title={t('common.save', '保存')}
            >
              <Check className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={handleCancelAdd}
              className="p-1.5 text-gray-500 dark:text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 rounded-md transition-colors flex-shrink-0"
              title={t('common.cancel', '取消')}
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>

          {/* Template suggestions */}
          {showTemplates && (
            <div className="flex flex-wrap gap-1.5">
              {COMMON_TEMPLATES.filter(template =>
                !attributes.some(attr => attr.key === template) &&
                template.toLowerCase().includes(newKey.toLowerCase())
              ).slice(0, 6).map((template) => (
                <button
                  key={template}
                  onClick={() => handleTemplateSelect(template)}
                  className="px-2 py-1 text-[11px] leading-tight bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-700 rounded-full hover:bg-blue-100 dark:hover:bg-blue-900/50 transition-colors font-medium"
                >
                  {template}
                </button>
              ))}
            </div>
          )}
        </div>
      ) : (
        <button
          onClick={handleStartAdd}
          className="flex items-center space-x-1.5 text-xs text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 hover:bg-blue-50 dark:hover:bg-blue-900/30 px-2.5 py-1.5 rounded-md transition-colors mt-2 font-medium"
        >
          <Plus className="w-3 h-3" />
          <span>{t('visitor.customAttr.addButton', '添加自定义属性')}</span>
        </button>
      )}
    </div>
  );
};

export default CustomAttributeManager;
