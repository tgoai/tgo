/**
 * Optimized Tool Tool Card Component
 * Uses BaseCard pattern to eliminate duplication and improve consistency
 */

import React from 'react';
import { BaseCard, createCardActions, type BaseCardItem } from '@/components/base/BaseCard';
import type { AiTool } from '@/types';
import { useTranslation } from 'react-i18next';
import { getToolDisplayTitle } from '@/utils/projectToolsTransform';

/**
 * Transform AiTool to BaseCardItem compatible format
 */
type AiToolCardItem = BaseCardItem & {
  // Additional Tool-specific fields
  usageCount: number;
  successRate?: number;
  avgResponseTime?: string;
  capabilities?: string[];
  config?: Record<string, any>;
  input_schema?: Record<string, any>;
};

interface AiToolCardOptimizedProps {
  tool: AiTool;
  onAction: (actionType: string, tool: AiTool) => void;
  onShowToast?: (type: 'success' | 'error' | 'warning' | 'info', title: string, message?: string) => void;
  showActions?: boolean;
  showTags?: boolean;
  showRating?: boolean;
  className?: string;
}

/**
 * Optimized Tool Tool Card Component
 */
const AiToolCardOptimized: React.FC<AiToolCardOptimizedProps> = ({
  tool,
  onAction,
  onShowToast,
  showActions = true,
  showTags = false,
  showRating = false,
  className = '',
}) => {
  const { i18n } = useTranslation();
  const displayTitle = getToolDisplayTitle(tool, i18n.language);

  // Transform AiTool to BaseCardItem format
  const cardItem: AiToolCardItem = {
    ...tool,
    // Ensure all required BaseCardItem fields are present
    name: tool.name,
    title: displayTitle,
    description: tool.description,
    status: tool.status,
    author: tool.author,
    version: tool.version,
    tags: tool.tags,
    rating: tool.rating,
    verified: tool.status === 'active',
    featured: tool.rating >= 4.5,
    isInstalled: tool.status === 'active',
    short_no: tool.short_no,
  };

  // Create actions based on tool state and capabilities
  const actions = showActions ? [
    createCardActions.view(() => handleAction('details')),
    createCardActions.delete(() => handleAction('delete')),
  ] : [];

  const handleAction = (actionType: string) => {
    try {
      onAction(actionType, tool);
    } catch (error) {
      console.error(`Action ${actionType} failed:`, error);
      onShowToast?.('error', '操作失败', `执行 ${actionType} 操作时发生错误`);
    }
  };

  const handleCardClick = () => {
    handleAction('select');
  };

  const handleCardAction = (actionType: string) => {
    handleAction(actionType);
  };

  return (
    <BaseCard
      item={cardItem}
      actions={actions}
      showAvatar={true}
      showStatus={true}
      showTags={showTags}
      showRating={showRating}
      showAuthor={true}
      showVersion={false}
      className={className}
      onClick={handleCardClick}
      onAction={handleCardAction}
    />
  );
};

export default AiToolCardOptimized;
