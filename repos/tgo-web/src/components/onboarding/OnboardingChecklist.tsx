import React from 'react';
import { useTranslation } from 'react-i18next';
import { Check, ChevronDown, ChevronUp, X } from 'lucide-react';
import { useOnboardingStore } from '@/stores/onboardingStore';

/**
 * Onboarding Checklist Component
 * Displays a floating checklist in the bottom-right corner
 * to guide users through initial setup tasks
 */
const OnboardingChecklist: React.FC = () => {
  const { t } = useTranslation();
  
  const {
    isDismissed,
    tasksCompleted,
    isCollapsed,
    dismissOnboarding,
    toggleCollapse,
    getCompletedCount,
    getTotalCount,
    isAllCompleted,
  } = useOnboardingStore();
  
  // Don't show if dismissed or all tasks completed
  if (isDismissed || isAllCompleted()) {
    return null;
  }
  
  const completedCount = getCompletedCount();
  const totalCount = getTotalCount();
  const progressPercentage = (completedCount / totalCount) * 100;
  
  // Task definitions
  const tasks = [
    {
      id: 'platformCreated',
      label: t('onboarding.tasks.platformCreated', '设置平台'),
      completed: tasksCompleted.platformCreated,
    },
    {
      id: 'knowledgeBaseUploaded',
      label: t('onboarding.tasks.knowledgeBaseUploaded', '上传知识库'),
      completed: tasksCompleted.knowledgeBaseUploaded,
    },
    {
      id: 'agentCreated',
      label: t('onboarding.tasks.agentCreated', '创建 AI Agent 并关联知识库'),
      completed: tasksCompleted.agentCreated,
    },
    {
      id: 'messageReceived',
      label: t('onboarding.tasks.messageReceived', '收到平台发的消息'),
      completed: tasksCompleted.messageReceived,
    },
  ];
  
  return (
    <div className="fixed bottom-6 right-6 w-80 bg-white rounded-lg shadow-2xl border border-gray-200 z-50 animate-fadeIn">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-gray-200">
        <div className="flex-1">
          <h3 className="font-semibold text-gray-900 text-base">
            {t('onboarding.title', '快速开始')}
          </h3>
          <p className="text-xs text-gray-500 mt-0.5">
            {t('onboarding.progress', '{{completed}}/{{total}} 已完成', {
              completed: completedCount,
              total: totalCount,
            })}
          </p>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={toggleCollapse}
            className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded transition-colors"
            title={isCollapsed ? t('onboarding.expand', '展开') : t('onboarding.collapse', '收起')}
          >
            {isCollapsed ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
          <button
            onClick={dismissOnboarding}
            className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded transition-colors"
            title={t('onboarding.dismiss', '关闭')}
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>
      
      {/* Progress Bar */}
      <div className="px-4 pt-3 pb-2">
        <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
          <div
            className="h-full bg-blue-600 transition-all duration-500 ease-out"
            style={{ width: `${progressPercentage}%` }}
          />
        </div>
      </div>
      
      {/* Task List */}
      {!isCollapsed && (
        <div className="p-4 space-y-2">
          {tasks.map((task, index) => (
            <div
              key={task.id}
              className={`flex items-start gap-3 p-3 rounded-md transition-all duration-300 ${
                task.completed
                  ? 'bg-green-50 border border-green-200'
                  : 'bg-gray-50 border border-gray-200'
              }`}
              style={{
                animationDelay: `${index * 50}ms`,
              }}
            >
              {/* Checkbox Icon */}
              <div
                className={`flex-shrink-0 w-5 h-5 rounded-full flex items-center justify-center transition-all duration-300 ${
                  task.completed
                    ? 'bg-green-500 scale-110'
                    : 'bg-white border-2 border-gray-300'
                }`}
              >
                {task.completed && <Check className="w-3 h-3 text-white" strokeWidth={3} />}
              </div>
              
              {/* Task Label */}
              <span
                className={`text-sm flex-1 transition-all duration-300 ${
                  task.completed
                    ? 'text-green-700 font-medium'
                    : 'text-gray-700'
                }`}
              >
                {task.label}
              </span>
            </div>
          ))}
        </div>
      )}
      
      {/* Footer */}
      {!isCollapsed && (
        <div className="px-4 pb-4 pt-2 border-t border-gray-200">
          <button
            onClick={dismissOnboarding}
            className="w-full text-sm text-gray-500 hover:text-gray-700 py-2 hover:bg-gray-50 rounded transition-colors"
          >
            {t('onboarding.dismissButton', '不再显示')}
          </button>
        </div>
      )}
      
      {/* CSS Animation */}
      <style>{`
        @keyframes fadeIn {
          from {
            opacity: 0;
            transform: translateY(20px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
        .animate-fadeIn {
          animation: fadeIn 0.4s ease-out;
        }
      `}</style>
    </div>
  );
};

export default OnboardingChecklist;

