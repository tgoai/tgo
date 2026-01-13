/**
 * Agent Workflows Section Component
 * Displays and manages workflows associated with an agent
 */

import React from 'react';
import { useTranslation } from 'react-i18next';
import { Plus, X, GitBranch, ExternalLink } from 'lucide-react';
import type { WorkflowSummary } from '@/types/workflow';

interface AgentWorkflowsSectionProps {
  workflows: WorkflowSummary[];
  onAdd: () => void;
  onRemove: (workflowId: string) => void;
  onEdit?: (workflowId: string) => void;
  disabled?: boolean;
}

const AgentWorkflowsSection: React.FC<AgentWorkflowsSectionProps> = ({
  workflows,
  onAdd,
  onRemove,
  onEdit,
  disabled = false,
}) => {
  const { t } = useTranslation();

  const getStatusBadge = (status: string) => {
    const styles: Record<string, string> = {
      active: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300',
      draft: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300',
      archived: 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400',
    };
    const labels: Record<string, string> = {
      active: t('workflow.status.active', '已启用'),
      draft: t('workflow.status.draft', '草稿'),
      archived: t('workflow.status.archived', '已归档'),
    };
    return (
      <span className={`px-1.5 py-0.5 text-xs rounded ${styles[status] || styles.draft}`}>
        {labels[status] || status}
      </span>
    );
  };

  return (
    <div className="space-y-3">
      {/* Workflow List */}
      {workflows.length > 0 ? (
        <div className="space-y-2">
          {workflows.map((workflow) => (
            <div
              key={workflow.id}
              className="flex items-center justify-between p-3 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg group"
            >
              <div className="flex items-center gap-3 min-w-0 flex-1">
                <div className="w-9 h-9 rounded-lg bg-purple-100 dark:bg-purple-900/50 text-purple-600 dark:text-purple-400 flex items-center justify-center flex-shrink-0">
                  <GitBranch className="w-5 h-5" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">
                      {workflow.name}
                    </span>
                    {getStatusBadge(workflow.status)}
                  </div>
                  <div className="text-xs text-gray-500 dark:text-gray-400 mt-0.5 truncate">
                    {workflow.description || t('workflow.noDescription', '暂无描述')}
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                {onEdit && (
                  <button
                    type="button"
                    onClick={() => onEdit(workflow.id)}
                    disabled={disabled}
                    className="p-1.5 text-gray-400 hover:text-blue-600 dark:hover:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/30 rounded transition-colors disabled:opacity-50"
                    title={t('workflow.actions.edit', '编辑')}
                  >
                    <ExternalLink className="w-4 h-4" />
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => onRemove(workflow.id)}
                  disabled={disabled}
                  className="p-1.5 text-gray-400 hover:text-red-600 dark:hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/30 rounded transition-colors disabled:opacity-50"
                  title={t('common.remove', '移除')}
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="text-center py-6 bg-gray-50 dark:bg-gray-900/50 rounded-lg border border-dashed border-gray-300 dark:border-gray-600">
          <GitBranch className="w-8 h-8 text-gray-400 dark:text-gray-500 mx-auto mb-2" />
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {t('workflow.empty.title', '暂未关联工作流')}
          </p>
        </div>
      )}

      {/* Add Button */}
      <button
        type="button"
        onClick={onAdd}
        disabled={disabled}
        className="w-full flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium text-purple-600 dark:text-purple-400 bg-purple-50 dark:bg-purple-900/20 hover:bg-purple-100 dark:hover:bg-purple-900/40 border border-purple-200 dark:border-purple-800 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      >
        <Plus className="w-4 h-4" />
        <span>{t('workflow.addWorkflow', '添加工作流')}</span>
      </button>
    </div>
  );
};

export default AgentWorkflowsSection;

