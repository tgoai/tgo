import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useAIStore } from '@/stores/aiStore';
import type { Platform, PlatformAIMode } from '@/types';
import { FiChevronDown, FiChevronRight, FiX } from 'react-icons/fi';

interface PlatformAISettingsProps {
  platform: Platform;
  /** Current agent selection (controlled as an array for existing callers) */
  agentIds: string[];
  /** Current AI mode (controlled) */
  aiMode: PlatformAIMode;
  /** Current fallback timeout in seconds (controlled) */
  fallbackTimeout: number | null;
  /** Callback when selected agent changes */
  onAgentIdsChange: (agentIds: string[]) => void;
  /** Callback when AI mode changes */
  onAIModeChange: (mode: PlatformAIMode) => void;
  /** Callback when fallback timeout changes */
  onFallbackTimeoutChange: (timeout: number | null) => void;
  /** Whether the section is initially expanded (default: false) */
  defaultExpanded?: boolean;
}

/**
 * Reusable AI Settings component for platform configuration
 * Includes:
 * - Single-select dropdown for AI agents
 * - Radio buttons for AI mode (auto/assist/off)
 * - Timeout input for assist mode
 */
const PlatformAISettings: React.FC<PlatformAISettingsProps> = ({
  platform,
  agentIds,
  aiMode,
  fallbackTimeout,
  onAgentIdsChange,
  onAIModeChange,
  onFallbackTimeoutChange,
  defaultExpanded = false,
}) => {
  const { t } = useTranslation();
  const agents = useAIStore(s => s.agents);
  const loadAgents = useAIStore(s => s.loadAgents);
  const isLoadingAgents = useAIStore(s => s.isLoadingAgents);

  // Collapsible section state (default collapsed)
  const [expanded, setExpanded] = useState(defaultExpanded);

  // Load agents on mount if not already loaded
  useEffect(() => {
    if (agents.length === 0) {
      loadAgents();
    }
  }, [agents.length, loadAgents]);

  // Dropdown state
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Get selected agent objects
  const selectedAgents = useMemo(() => {
    return agents.filter(agent => agentIds.includes(agent.id));
  }, [agents, agentIds]);

  // Handle agent selection toggle. Backend routing supports one platform agent.
  const toggleAgent = (agentId: string) => {
    if (agentIds.includes(agentId)) {
      onAgentIdsChange([]);
    } else {
      onAgentIdsChange([agentId]);
      setDropdownOpen(false);
    }
  };

  // Remove a selected agent
  const removeAgent = (agentId: string) => {
    onAgentIdsChange(agentIds.filter(id => id !== agentId));
  };

  // Handle timeout input change
  const handleTimeoutChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    if (value === '') {
      onFallbackTimeoutChange(null);
    } else {
      const num = parseInt(value, 10);
      if (!isNaN(num) && num >= 0) {
        onFallbackTimeoutChange(num);
      }
    }
  };

  return (
    <div className="pt-4 border-t border-gray-200 dark:border-gray-600 mt-4">
      {/* Collapsible Header */}
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between text-sm font-semibold text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100 transition-colors"
      >
        <span className="flex items-center gap-2">
          {expanded ? <FiChevronDown className="w-4 h-4" /> : <FiChevronRight className="w-4 h-4" />}
          {t('platforms.aiSettings.title', 'AI 设置')}
          <span className="text-xs font-normal text-gray-400 dark:text-gray-500">
            ({t('platforms.aiSettings.optional', '可选')})
          </span>
        </span>
      </button>

      {/* Collapsible Content */}
      {expanded && (
        <div className="space-y-4 mt-4 animate-fadeIn">
          {/* AI Agent selector */}
          <div>
            <label className="block text-sm font-medium text-gray-600 dark:text-gray-300 mb-1">
              {t('platforms.aiSettings.agents', 'AI 员工')}
            </label>
            <div ref={dropdownRef} className="relative">
              {/* Selected agents display / trigger */}
              <div
                onClick={() => setDropdownOpen(!dropdownOpen)}
                className="w-full min-h-[38px] text-sm p-1.5 border border-gray-300/80 dark:border-gray-600/80 rounded-md bg-white/90 dark:bg-gray-700/50 dark:text-gray-200 cursor-pointer flex items-center flex-wrap gap-1"
              >
                {selectedAgents.length === 0 ? (
                  <span className="text-gray-400 dark:text-gray-500 px-1">
                    {isLoadingAgents
                      ? t('platforms.aiSettings.loadingAgents', '加载中...')
                      : t('platforms.aiSettings.selectAgents', '选择 AI 员工')}
                  </span>
                ) : (
                  selectedAgents.map(agent => (
                    <span
                      key={agent.id}
                      className="inline-flex items-center gap-1 bg-blue-100 dark:bg-blue-900/50 text-blue-800 dark:text-blue-200 text-xs px-2 py-0.5 rounded"
                    >
                      {agent.name}
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          removeAgent(agent.id);
                        }}
                        className="hover:text-blue-600 dark:hover:text-blue-400"
                      >
                        <FiX className="w-3 h-3" />
                      </button>
                    </span>
                  ))
                )}
                <FiChevronDown className={`ml-auto w-4 h-4 text-gray-400 transition-transform ${dropdownOpen ? 'rotate-180' : ''}`} />
              </div>

              {/* Dropdown list */}
              {dropdownOpen && (
                <div className="absolute z-20 w-full mt-1 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded-md shadow-lg max-h-48 overflow-y-auto">
                  {agents.length === 0 ? (
                    <div className="px-3 py-2 text-sm text-gray-500 dark:text-gray-400">
                      {isLoadingAgents
                        ? t('platforms.aiSettings.loadingAgents', '加载中...')
                        : t('platforms.aiSettings.noAgents', '暂无 AI 员工')}
                    </div>
                  ) : (
                    agents.map(agent => (
                      <div
                        key={agent.id}
                        onClick={() => toggleAgent(agent.id)}
                        className={`px-3 py-2 text-sm cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center gap-2 ${
                          agentIds.includes(agent.id) ? 'bg-blue-50 dark:bg-blue-900/30' : ''
                        }`}
                      >
                        <input
                          type="radio"
                          checked={agentIds.includes(agent.id)}
                          onChange={() => {}}
                          className="w-4 h-4 text-blue-600 border-gray-300 dark:border-gray-600 focus:ring-blue-500"
                        />
                        <span className="text-gray-700 dark:text-gray-200">{agent.name}</span>
                        {agent.description && (
                          <span className="text-xs text-gray-400 dark:text-gray-500 truncate">
                            - {agent.description}
                          </span>
                        )}
                      </div>
                    ))
                  )}
                </div>
              )}
            </div>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
              {agentIds.length === 0
                ? t('platforms.aiSettings.agentsHintDefault', '未选择时默认使用项目默认 AI 员工。')
                : t('platforms.aiSettings.agentsHint', '选择分配给此平台的 AI 员工。')}
            </p>
          </div>

          {/* AI Mode Selection */}
          <div>
            <label className="block text-sm font-medium text-gray-600 dark:text-gray-300 mb-2">
              {t('platforms.aiSettings.mode', 'AI 模式')}
            </label>
            <div className="flex flex-wrap gap-4">
              <label className="inline-flex items-center cursor-pointer">
                <input
                  type="radio"
                  name={`ai-mode-${platform.id}`}
                  value="auto"
                  checked={aiMode === 'auto'}
                  onChange={() => onAIModeChange('auto')}
                  className="w-4 h-4 text-blue-600 border-gray-300 dark:border-gray-600 focus:ring-blue-500"
                />
                <span className="ml-2 text-sm text-gray-700 dark:text-gray-200">
                  {t('platforms.aiSettings.modeAuto', '自动')}
                </span>
              </label>
              <label className="inline-flex items-center cursor-pointer">
                <input
                  type="radio"
                  name={`ai-mode-${platform.id}`}
                  value="assist"
                  checked={aiMode === 'assist'}
                  onChange={() => onAIModeChange('assist')}
                  className="w-4 h-4 text-blue-600 border-gray-300 dark:border-gray-600 focus:ring-blue-500"
                />
                <span className="ml-2 text-sm text-gray-700 dark:text-gray-200">
                  {t('platforms.aiSettings.modeAssist', '辅助')}
                </span>
              </label>
              <label className="inline-flex items-center cursor-pointer">
                <input
                  type="radio"
                  name={`ai-mode-${platform.id}`}
                  value="off"
                  checked={aiMode === 'off'}
                  onChange={() => onAIModeChange('off')}
                  className="w-4 h-4 text-blue-600 border-gray-300 dark:border-gray-600 focus:ring-blue-500"
                />
                <span className="ml-2 text-sm text-gray-700 dark:text-gray-200">
                  {t('platforms.aiSettings.modeOff', '关闭')}
                </span>
              </label>
            </div>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
              {aiMode === 'auto' && t('platforms.aiSettings.modeAutoHint', 'AI 自动处理所有消息。')}
              {aiMode === 'assist' && t('platforms.aiSettings.modeAssistHint', '人工优先处理，超时后 AI 自动接管。')}
              {aiMode === 'off' && t('platforms.aiSettings.modeOffHint', '禁用 AI，仅人工处理消息。')}
            </p>
          </div>

          {/* Fallback Timeout (only shown when mode is 'assist') */}
          {aiMode === 'assist' && (
            <div>
              <label className="block text-sm font-medium text-gray-600 dark:text-gray-300 mb-1">
                {t('platforms.aiSettings.timeout', '超时时间 (秒)')}
              </label>
              <input
                type="number"
                min="0"
                value={fallbackTimeout ?? ''}
                onChange={handleTimeoutChange}
                placeholder={t('platforms.aiSettings.timeoutPlaceholder', '例如：60')}
                className="w-full max-w-xs text-sm p-1.5 border border-gray-300/80 dark:border-gray-600/80 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 dark:focus:ring-blue-400 focus:border-blue-500 dark:focus:border-blue-400 bg-white/90 dark:bg-gray-700/50 dark:text-gray-200"
              />
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                {t('platforms.aiSettings.timeoutHint', '消息多少秒无回复后 AI 自动接管。设置为 0 表示 AI 不会接管。')}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default PlatformAISettings;
