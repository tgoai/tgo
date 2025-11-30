import React, { useState, useEffect, useRef, useMemo } from 'react';
import { useTranslation } from 'react-i18next';

import { X, Check, Edit3, RefreshCw } from 'lucide-react';
import type { VisitorTag } from '@/data/mockVisitor';

interface SuggestedTag {
  id: string;
  name: string;
  color: string;
  weight: number;
}

interface TagManagerProps {
  tags: VisitorTag[];
  onAddTag: (tag: Omit<VisitorTag, 'id'>) => void;
  onUpdateTag: (id: string, updates: Partial<VisitorTag>) => void;
  onRemoveTag: (id: string) => void;
  // New props for API-driven suggestions and association
  fetchCommonTags: () => Promise<SuggestedTag[]>;
  onAssociateExistingTag: (id: string) => void;
  maxTags?: number;
  className?: string;
}

// 颜色选项 - hex 值使用大写格式，用于提交到后端
// bgHex: 背景色（浅色），textHex: 文本色（深色），用于动态样式
const COLOR_OPTIONS = [
  { name: 'red', label: '红色', hex: '#EF4444', bgHex: '#FEE2E2', textHex: '#B91C1C' },
  { name: 'orange', label: '橙色', hex: '#F97316', bgHex: '#FFEDD5', textHex: '#C2410C' },
  { name: 'yellow', label: '黄色', hex: '#EAB308', bgHex: '#FEF9C3', textHex: '#A16207' },
  { name: 'green', label: '绿色', hex: '#22C55E', bgHex: '#DCFCE7', textHex: '#15803D' },
  { name: 'emerald', label: '翠绿', hex: '#10B981', bgHex: '#D1FAE5', textHex: '#047857' },
  { name: 'teal', label: '青色', hex: '#14B8A6', bgHex: '#CCFBF1', textHex: '#0F766E' },
  { name: 'blue', label: '蓝色', hex: '#3B82F6', bgHex: '#DBEAFE', textHex: '#1D4ED8' },
  { name: 'indigo', label: '靛蓝', hex: '#6366F1', bgHex: '#E0E7FF', textHex: '#4338CA' },
  { name: 'purple', label: '紫色', hex: '#A855F7', bgHex: '#F3E8FF', textHex: '#7E22CE' },
  { name: 'pink', label: '粉色', hex: '#EC4899', bgHex: '#FCE7F3', textHex: '#BE185D' },
  { name: 'gray', label: '灰色', hex: '#6B7280', bgHex: '#F3F4F6', textHex: '#374151' }
];

// 默认颜色（蓝色）
const DEFAULT_COLOR = COLOR_OPTIONS.find(c => c.name === 'blue')!;

/**
 * 将颜色值转换为大写十六进制格式
 * 支持输入：颜色名称（如 'blue'）、十六进制（如 '#3b82f6' 或 '3B82F6'）
 * 输出：大写十六进制格式（如 '#3B82F6'）
 */
const toUppercaseHex = (color: string | null | undefined): string => {
  if (!color) return DEFAULT_COLOR.hex;
  
  const trimmed = color.trim();
  
  // 如果已经是十六进制格式，转换为大写
  if (/^#?[0-9A-Fa-f]{6}$/.test(trimmed)) {
    const hex = trimmed.startsWith('#') ? trimmed : `#${trimmed}`;
    return hex.toUpperCase();
  }
  
  // 如果是颜色名称，查找对应的 hex 值
  const found = COLOR_OPTIONS.find(c => c.name.toLowerCase() === trimmed.toLowerCase());
  return found ? found.hex : DEFAULT_COLOR.hex;
};

/**
 * 根据颜色值获取颜色配置（支持颜色名称和 hex 值）
 */
const getColorConfig = (color: string | null | undefined) => {
  if (!color) return DEFAULT_COLOR;
  
  const trimmed = color.trim().toLowerCase();
  
  // 先尝试按名称匹配
  const byName = COLOR_OPTIONS.find(c => c.name === trimmed);
  if (byName) return byName;
  
  // 再尝试按 hex 匹配（忽略大小写）
  const normalizedHex = trimmed.startsWith('#') ? trimmed : `#${trimmed}`;
  const byHex = COLOR_OPTIONS.find(c => c.hex.toLowerCase() === normalizedHex);
  if (byHex) return byHex;
  
  return DEFAULT_COLOR;
};

// 获取权重样式
const getWeightStyle = (weight: number): string => {
  if (weight >= 9) return 'ring-2 ring-offset-1 font-bold'; // 高权重：双环边框 + 粗体
  if (weight >= 7) return 'border-2 font-semibold'; // 中高权重：粗边框 + 半粗体
  if (weight >= 4) return 'font-medium'; // 中权重：中等字体
  if (weight >= 1) return ''; // 低权重：默认样式
  return 'opacity-60'; // 权重为0：半透明显示
};

/**
 * Tag manager component for adding and removing tags
 */
const TagManager: React.FC<TagManagerProps> = ({
  tags,
  onAddTag,
  onUpdateTag,
  onRemoveTag,
  fetchCommonTags,
  onAssociateExistingTag,
  maxTags = 8,


  className = ''
}) => {
  const { t } = useTranslation();

  const [isAdding, setIsAdding] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [newTag, setNewTag] = useState('');
  const [newColor, setNewColor] = useState('blue');
  const [newWeight, setNewWeight] = useState(0);
  const [showPresets, setShowPresets] = useState(false);
  const [showColorPicker, setShowColorPicker] = useState(false);
  const [panelPosition, setPanelPosition] = useState({ top: 0, left: 16 });
  const [suggestions, setSuggestions] = useState<SuggestedTag[]>([]);
  const [suggestionsLoading, setSuggestionsLoading] = useState(false);
  const [suggestionsError, setSuggestionsError] = useState<string | null>(null);
  const editPanelRef = useRef<HTMLDivElement>(null);
  const tagRefs = useRef<{ [key: string]: HTMLDivElement | null }>({});

  // 点击外部关闭编辑面板
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (editingId && editPanelRef.current && !editPanelRef.current.contains(event.target as Node)) {
        setEditingId(null);
      }
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && editingId) {
        setEditingId(null);
      }
    };

    if (editingId) {
      document.addEventListener('mousedown', handleClickOutside);
      document.addEventListener('keydown', handleKeyDown);
      return () => {
        document.removeEventListener('mousedown', handleClickOutside);
        document.removeEventListener('keydown', handleKeyDown);
      };
    }

    return undefined;
  }, [editingId]);

  // 计算编辑面板位置
  useEffect(() => {
    if (editingId && tagRefs.current[editingId]) {
      const tagElement = tagRefs.current[editingId];
      if (tagElement) {
        const rect = tagElement.getBoundingClientRect();
        const visitorPanelRect = tagElement.closest('aside')?.getBoundingClientRect();

        if (visitorPanelRect) {
          // 计算相对于访客面板的位置
          const relativeTop = rect.top - visitorPanelRect.top;
          setPanelPosition({
            top: Math.max(16, relativeTop + 32), // 确保不会超出顶部，标签下方32px
            left: 16 // 固定在访客面板左侧16px
          });
        }
      }
    }
  }, [editingId]);

  const handleStartAdd = async () => {
    setIsAdding(true);
    setNewTag('');
    setNewColor('blue');
    setNewWeight(0);
    setShowPresets(true);
    setShowColorPicker(false);

    // 获取常用标签（后端接口）
    try {
      setSuggestionsLoading(true);
      setSuggestionsError(null);
      const data = await fetchCommonTags();
      setSuggestions(data);
    } catch (e) {
      setSuggestionsError(t('chat.visitor.tags.common.loadFailed', '获取常用标签失败'));
    } finally {
      setSuggestionsLoading(false);
    }
  };

  const handleCancelAdd = () => {
    setIsAdding(false);
    setNewTag('');
    setShowPresets(false);
    setShowColorPicker(false);
  };

  const handleSaveAdd = () => {
    if (newTag.trim() && !tags.some(tag => tag.name === newTag.trim()) && tags.length < maxTags) {
      onAddTag({
        name: newTag.trim(),
        // 转换为大写十六进制格式提交到后端
        color: toUppercaseHex(newColor),
        weight: newWeight
      });
      handleCancelAdd();
    }
  };

  const handlePresetSelect = (preset: SuggestedTag) => {
    if (!tags.some(tag => tag.name === preset.name) && tags.length < maxTags) {
      // 选择常用标签：直接建立关联
      onAssociateExistingTag(preset.id);
      handleCancelAdd();
    }
  };

  const handleStartEdit = (tag: VisitorTag) => {
    setEditingId(tag.id);
  };

  const handleUpdateWeight = (id: string, weight: number) => {
    onUpdateTag(id, { weight });
  };

  const handleUpdateColor = (id: string, color: string) => {
    // 转换为大写十六进制格式提交到后端
    onUpdateTag(id, { color: toUppercaseHex(color) });
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleSaveAdd();
    } else if (e.key === 'Escape') {
      e.preventDefault();
      handleCancelAdd();
    }
  };

  // 过滤出未使用的建议标签（来自后端）
  const availablePresets = suggestions
    .filter(preset => !tags.some(tag => tag.name === preset.name))
    .filter(preset => preset.name.toLowerCase().includes(newTag.toLowerCase()))
    .slice(0, 6);

  // 只在tags数据变化时重新计算排序，避免编辑状态切换时的不必要计算
  const sortedTags = useMemo(() => {
    return [...tags].sort((a, b) => b.weight - a.weight);
  }, [tags]);


  return (
    <div className={className}>
      {/* 现有标签 */}
      <div className="flex flex-wrap gap-1.5">
        {sortedTags.map((tag) => {
          const colorConfig = getColorConfig(tag.color);
          return (
          <div
            key={tag.id}
            ref={(el) => { tagRefs.current[tag.id] = el; }}
            className="group relative"
          >
            <span
              className={`text-[11px] leading-tight px-2 py-1 rounded-full border ${getWeightStyle(tag.weight)}`}
              style={{
                backgroundColor: colorConfig.bgHex,
                color: colorConfig.textHex,
                borderColor: colorConfig.hex + '40' // 添加透明度
              }}
            >
              {tag.name}
              {tag.weight >= 8 && (
                <span className="ml-1 text-[8px] opacity-70">★</span>
              )}
            </span>

            {/* 编辑和删除按钮 */}
            <div className="absolute -top-1 -right-1 flex space-x-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
              <button
                onClick={() => handleStartEdit(tag)}
                className="w-3.5 h-3.5 bg-blue-500 text-white rounded-full flex items-center justify-center"
                title={t('chat.visitor.tags.editTagTitle', '编辑标签')}
              >
                <Edit3 className="w-2 h-2" />
              </button>
              <button
                onClick={() => onRemoveTag(tag.id)}
                className="w-3.5 h-3.5 bg-red-500 text-white rounded-full flex items-center justify-center"
                title={t('chat.visitor.tags.deleteTagTitle', '删除标签')}
              >
                <X className="w-2 h-2" />
              </button>
            </div>

            {/* 编辑面板 */}
            {editingId === tag.id && (
              <div
                ref={editPanelRef}
                className="fixed z-50 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-xl p-3 min-w-[200px] max-w-[240px]"
                style={{
                  top: `${panelPosition.top}px`,
                  left: `${panelPosition.left}px`,
                  boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)'
                }}
              >
                <div className="space-y-2">
                  <div>
                    <label className="text-[10px] text-gray-500 dark:text-gray-400 block mb-1">{t('chat.visitor.tags.editPanel.weightLabel', '权重 (0-10)')}</label>
                    <input
                      type="range"
                      min="0"
                      max="10"
                      value={tag.weight}
                      onChange={(e) => handleUpdateWeight(tag.id, parseInt(e.target.value))}
                      className="w-full h-1 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer"
                    />
                    <div className="text-[10px] text-gray-400 dark:text-gray-500 text-center">{tag.weight}</div>
                  </div>

                  <div>
                    <label className="text-[10px] text-gray-500 dark:text-gray-400 block mb-1">{t('chat.visitor.tags.editPanel.colorLabel', '颜色')}</label>
                    <div className="flex flex-wrap gap-1.5">
                      {COLOR_OPTIONS.map((color) => {
                        // 比较颜色：支持颜色名称和 hex 值
                        const currentColorConfig = getColorConfig(tag.color);
                        const isSelected = currentColorConfig.name === color.name;
                        return (
                        <button
                          key={color.name}
                          onClick={() => handleUpdateColor(tag.id, color.name)}
                          className={`w-5 h-5 rounded-full border-2 transition-all ${
                            isSelected
                              ? 'border-gray-800 dark:border-white ring-2 ring-offset-1 ring-gray-400 dark:ring-gray-500'
                              : 'border-gray-300 dark:border-gray-600 hover:border-gray-400 dark:hover:border-gray-500'
                          }`}
                          style={{ backgroundColor: color.hex }}
                          title={t(`chat.visitor.tags.colors.${color.name}`, color.label)}
                        />
                        );
                      })}
                    </div>
                  </div>

                  <button
                    onClick={() => setEditingId(null)}
                    className="w-full text-[10px] text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 py-1"
                  >
                    {t('common.done', '完成')}
                  </button>
                </div>
              </div>
            )}
          </div>
        );
        })}

        {/* 添加标签按钮/输入框 */}
        {isAdding ? (
          <div className="relative">
            <div className="flex items-center space-x-1 mb-2">
              <input
                type="text"
                value={newTag}
                onChange={(e) => setNewTag(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={t('chat.visitor.tags.inputPlaceholder', '输入标签名称')}
                className="w-20 px-2 py-1 text-[11px] border border-gray-300 dark:border-gray-600 rounded-full focus:outline-none focus:ring-1 focus:ring-blue-500 dark:focus:ring-blue-400 focus:border-blue-500 dark:focus:border-blue-400 bg-white dark:bg-gray-700 dark:text-gray-200"
                autoFocus
              />
              <button
                onClick={() => setShowColorPicker(!showColorPicker)}
                className="p-1 border border-gray-300 dark:border-gray-600 rounded-full"
                title={t('chat.visitor.tags.colorPicker.title', '选择颜色')}
              >
                <div
                  className="w-3 h-3 rounded-full"
                  style={{ backgroundColor: COLOR_OPTIONS.find(c => c.name === newColor)?.hex || '#f3f4f6' }}
                />
              </button>
              <input
                type="range"
                min="0"
                max="10"
                value={newWeight}
                onChange={(e) => setNewWeight(parseInt(e.target.value))}
                className="w-8 h-1 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer"
                title={t('chat.visitor.tags.weightTitle', { weight: newWeight, defaultValue: '权重: {{weight}}' })}
              />
              <button
                onClick={handleSaveAdd}
                disabled={!newTag.trim() || tags.some(tag => tag.name === newTag.trim()) || tags.length >= maxTags}
                className="p-0.5 text-green-600 hover:bg-green-50 rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                title={t('common.save', '保存')}
              >
                <Check className="w-3 h-3" />
              </button>
              <button
                onClick={handleCancelAdd}
                className="p-0.5 text-gray-500 hover:bg-gray-50 rounded transition-colors"
                title={t('common.cancel', '取消')}
              >
                <X className="w-3 h-3" />
              </button>
            </div>

            {/* 颜色选择器 */}
            {showColorPicker && (
              <div className="absolute top-8 left-0 z-10 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg p-2.5">
                <div className="grid grid-cols-4 gap-1.5">
                  {COLOR_OPTIONS.map((color) => (
                    <button
                      key={color.name}
                      onClick={() => {
                        setNewColor(color.name);
                        setShowColorPicker(false);
                      }}
                      className={`w-6 h-6 rounded-full border-2 transition-all ${
                        newColor === color.name
                          ? 'border-gray-800 dark:border-white ring-2 ring-offset-1 ring-gray-400 dark:ring-gray-500'
                          : 'border-gray-300 dark:border-gray-600 hover:border-gray-400 dark:hover:border-gray-500'
                      }`}
                      style={{ backgroundColor: color.hex }}
                      title={t(`chat.visitor.tags.colors.${color.name}`, color.label)}
                    />
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          tags.length < maxTags && (
            <button
              onClick={handleStartAdd}
              className="text-xs text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 hover:bg-blue-50 dark:hover:bg-blue-900/30 px-2 py-1 rounded-full transition-colors font-medium"
            >
              + {t('chat.visitor.tags.addButton', '添加')}
            </button>
          )
        )}
      </div>

      {/* 预设标签选择 */}
      {isAdding && showPresets && (
        <div className="mt-2 space-y-1">
          <div className="flex items-center justify-between">
            <div className="text-[10px] text-gray-500 dark:text-gray-400 font-medium">{t('chat.visitor.tags.common.title', '常用标签:')}</div>
            {suggestionsLoading && (
              <div className="flex items-center text-[10px] text-gray-400 dark:text-gray-500">
                <RefreshCw className="w-3 h-3 mr-1 animate-spin" /> {t('chat.visitor.tags.common.loading', '加载中')}
              </div>
            )}
          </div>
          {suggestionsError && (
            <div className="text-[10px] text-red-500 dark:text-red-400">{suggestionsError}</div>
          )}
          <div className="flex flex-wrap gap-1">
            {availablePresets.map((preset) => {
              const presetColorConfig = getColorConfig(preset.color);
              return (
              <button
                key={preset.id}
                onClick={() => handlePresetSelect(preset)}
                className={`text-[10px] leading-tight px-1.5 py-0.5 rounded-full border transition-colors hover:opacity-80 ${getWeightStyle(preset.weight)}`}
                style={{
                  backgroundColor: presetColorConfig.bgHex,
                  color: presetColorConfig.textHex,
                  borderColor: presetColorConfig.hex + '40'
                }}
              >
                {preset.name}
                {preset.weight >= 8 && (
                  <span className="ml-1 text-[8px] opacity-70">★</span>
                )}
              </button>
              );
            })}
            {!suggestionsLoading && availablePresets.length === 0 && (
              <div className="text-[10px] text-gray-400 dark:text-gray-500">{t('chat.visitor.tags.common.empty', '暂无可用标签')}</div>
            )}
          </div>
        </div>
      )}

      {/* 标签数量提示 */}
      {tags.length >= maxTags && (
        <div className="mt-1 text-[10px] text-gray-400 dark:text-gray-500">
          {t('chat.visitor.tags.limitReached', { max: maxTags, defaultValue: '已达到标签数量上限 ({{max}}个)' })}
        </div>
      )}
    </div>
  );
};

export default TagManager;
