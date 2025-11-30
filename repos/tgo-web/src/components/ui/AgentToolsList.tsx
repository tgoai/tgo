import React from 'react';
import { useTranslation } from 'react-i18next';
import { Wrench } from 'lucide-react';
import AgentToolTag from './AgentToolTag';
import type { AgentToolResponse } from '@/types';

interface AgentToolsListProps {
  tools: AgentToolResponse[];
  onToolClick?: (tool: AgentToolResponse) => void;
  size?: 'xs' | 'sm' | 'md';
  showIcon?: boolean;
  maxDisplay?: number;
  className?: string; // extra classes applied to wrapper
  emptyText?: string;
  showLabel?: boolean;
}

/**
 * Agent工具列表组件
 * 用于显示智能体关联的工具列表（基于API响应的工具对象）
 */
const AgentToolsList: React.FC<AgentToolsListProps> = ({
  tools,
  onToolClick,
  size = 'xs',
  showIcon = true,
  maxDisplay,
  className = '',
  emptyText,
  showLabel = false
}) => {
  const { t } = useTranslation();
  const defaultEmptyText = emptyText ?? t('agents.card.noTools', '未关联工具');
  // 如果没有关联工具，显示空状态
  if (!tools || tools.length === 0) {
    return (
      <div className={`flex items-center text-gray-500 ${className}`}>
        <Wrench className="w-4 h-4 mr-2 opacity-50" />
        <span className="text-sm">{defaultEmptyText}</span>
      </div>
    );
  }

  // 处理显示数量限制
  const displayTools = maxDisplay ? tools.slice(0, maxDisplay) : tools;
  const remainingCount = maxDisplay && tools.length > maxDisplay 
    ? tools.length - maxDisplay 
    : 0;

  return (
    <div className={`${className}`}>
      {showLabel && (
        <div className="flex items-center text-[13px] font-medium text-gray-700 mb-1.5">
          <Wrench className="w-3.5 h-3.5 mr-1.5" />
          {t('agents.toolsList.label', '关联工具')} ({tools.length})
        </div>
      )}

      <div className="flex flex-wrap gap-1.5">
        {displayTools.map((tool) => (
          <AgentToolTag
            key={tool.id}
            tool={tool}
            onClick={onToolClick}
            size={size}
            showIcon={showIcon}
          />
        ))}

        {remainingCount > 0 && (
          <span className={`
            inline-flex items-center rounded-md border bg-gray-100 text-gray-600 border-gray-200
            ${size === 'xs' ? 'px-1.5 py-0.5 text-[11px]' : size === 'sm' ? 'px-2 py-1 text-xs' : 'px-3 py-1.5 text-sm'}
          `}>
            +{remainingCount} {t('common.more', '更多')}
          </span>
        )}
      </div>
    </div>
  );
};

export default AgentToolsList;
