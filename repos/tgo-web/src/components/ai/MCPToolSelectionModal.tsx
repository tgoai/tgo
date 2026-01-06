import React, { useState, useMemo, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { X, Search, ExternalLink, Wrench, Settings, RefreshCw } from 'lucide-react';
import { useProjectToolsStore } from '@/stores/projectToolsStore';
import { transformAiToolResponseList, searchProjectTools } from '@/utils/projectToolsTransform';
import { generateDefaultAvatar } from '@/utils/avatarUtils';
import MCPToolConfigModal from './MCPToolConfigModal';
import { useToast } from '@/hooks/useToast';
import type { MCPTool } from '@/types';
import { useDebouncedValue } from '@/hooks/useDebouncedValue';

interface MCPToolSelectionModalProps {
  isOpen: boolean;
  onClose: () => void;
  selectedTools: string[];
  toolConfigs?: Record<string, Record<string, any>>;
  onConfirm: (selectedToolIds: string[], toolConfigs: Record<string, Record<string, any>>) => void;
}

// Tool categories for filtering
const TOOL_CATEGORIES = [
  { id: 'all', label: 'common.all' },
  { id: 'mcp_server', label: 'mcp.selectModal.category.mcpServer' },
  { id: 'custom', label: 'mcp.selectModal.category.custom' },
  { id: 'plugin', label: 'mcp.selectModal.category.plugin' },
];



/**
 * MCP Tool Selection Modal Component
 * Allows users to browse and select MCP tools to associate with agents
 */
const MCPToolSelectionModal: React.FC<MCPToolSelectionModalProps> = ({
  isOpen,
  onClose,
  selectedTools,
  toolConfigs = {},
  onConfirm
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const debouncedSearch = useDebouncedValue(searchQuery, 300);
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [tempSelectedTools, setTempSelectedTools] = useState<string[]>([]);
  const [tempToolConfigs, setTempToolConfigs] = useState<Record<string, Record<string, any>>>({});
  const [showConfigModal, setShowConfigModal] = useState(false);
  const [configTool, setConfigTool] = useState<MCPTool | null>(null);

  // Navigation hook
  const navigate = useNavigate();

  // Project Tools store integration (using NEW /v1/ai/tools API)
  const {
    aiTools,
    isLoading,
    error,
    loadMcpTools,
    clearError,
  } = useProjectToolsStore();

  const { showToast } = useToast();
  const { t } = useTranslation();

  // Load tools when modal opens (only active MCP tools)
  useEffect(() => {
    if (isOpen && aiTools.length === 0) {
      loadMcpTools(false).catch(error => {
        console.error('Failed to load MCP tools:', error);
        showToast('error', t('common.loadFailed', '加载失败'), t('mcp.selectModal.loadFailedDesc', '无法加载MCP工具列表，请稍后重试'));
      });
    }
  }, [isOpen, aiTools.length, loadMcpTools, showToast, t]);

  // Initialize temporary selection state when modal opens
  useEffect(() => {
    if (isOpen) {
      setTempSelectedTools([...selectedTools]);
      setTempToolConfigs({ ...toolConfigs });
    }
  }, [isOpen, selectedTools, toolConfigs]);

  // Transform API tools to MCPTool format and filter
  const filteredTools = useMemo(() => {
    // Transform AI tools (from NEW /v1/ai/tools API) to MCPTool format
    const mcpTools = transformAiToolResponseList(aiTools);
    let filtered = mcpTools;

    // Filter by category
    if (selectedCategory !== 'all') {
      filtered = filtered.filter(tool => {
        if (selectedCategory === 'mcp_server') {
          return tool.config?.transport_type === 'http' || tool.config?.transport_type === 'sse';
        } else if (selectedCategory === 'custom') {
          return tool.config?.transport_type === undefined || tool.config?.transport_type === null;
        } else if (selectedCategory === 'plugin') {
          return tool.config?.transport_type === 'plugin';
        }
        return false;
      });
    }

    // Filter by search query
    if (debouncedSearch.trim()) {
      filtered = searchProjectTools(filtered, debouncedSearch);
    }

    return filtered;
  }, [aiTools, debouncedSearch, selectedCategory]);

  const handleToolClick = (tool: MCPTool) => {
    setTempSelectedTools(prev => {
      if (prev.includes(tool.id)) {
        return prev.filter(id => id !== tool.id);
      } else {
        return [...prev, tool.id];
      }
    });
  };

  const handleConfirm = () => {
    onConfirm(tempSelectedTools, tempToolConfigs);
    onClose();
  };

  const handleConfigTool = (tool: MCPTool) => {
    setConfigTool(tool);
    setShowConfigModal(true);
  };

  const handleSaveConfig = (toolId: string, config: Record<string, any>) => {
    setTempToolConfigs(prev => ({
      ...prev,
      [toolId]: config
    }));
  };

  const handleCancel = () => {
    // Reset temporary selection to original state
    setTempSelectedTools([...selectedTools]);
    onClose();
  };

  const handleRetry = () => {
    clearError();
    loadMcpTools(false).catch(error => {
      console.error('Failed to retry loading MCP tools:', error);
      showToast('error', t('mcp.selectModal.retryFailedTitle', '重试失败'), t('mcp.selectModal.retryFailedDesc', '无法加载MCP工具列表，请检查网络连接'));
    });
  };

  const handleManageTools = () => {
    // Close the modal first
    onClose();
    // Navigate to MCP tools management page
    navigate('/ai/mcp-tools');
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-2xl max-h-[90vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700 flex-shrink-0">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">{t('mcp.selectModal.title', '选择工具')}</h3>
          <button
            onClick={onClose}
            className="text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Search Bar */}
        <div className="p-4 border-b border-gray-200 dark:border-gray-700 flex-shrink-0">
          <div className="relative">
            <Search className="w-4 h-4 absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 dark:text-gray-500" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder={t('mcp.selectModal.searchPlaceholder', '搜索工具...')}
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100 dark:placeholder-gray-400"
            />
          </div>
        </div>

        {/* Category Filters */}
        <div className="p-4 border-b border-gray-200 dark:border-gray-700 flex-shrink-0">
          <div className="flex space-x-2">
            {TOOL_CATEGORIES.map(category => (
              <button
                key={category.id}
                onClick={() => setSelectedCategory(category.id)}
                className={`px-3 py-1.5 text-sm rounded-md transition-colors ${
                  selectedCategory === category.id
                    ? 'bg-blue-100 text-blue-700 border border-blue-200 dark:bg-blue-900/30 dark:text-blue-300 dark:border-blue-700'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600'
                }`}
              >
                {t(category.label)}
              </button>
            ))}
          </div>
        </div>

        {/* Tools List - Scrollable Content Area */}
        <div className="flex-1 overflow-y-auto min-h-0 dark:bg-gray-900">
          <div className="p-4">
            {/* Loading State */}
            {isLoading && (
              <div className="flex items-center justify-center py-8">
                <div className="text-center">
                  <RefreshCw className="w-6 h-6 animate-spin text-gray-400 dark:text-gray-500 mx-auto mb-2" />
                  <p className="text-gray-500 dark:text-gray-400 text-sm">{t('mcp.selectModal.loading', '正在加载MCP工具...')}</p>
                </div>
              </div>
            )}

            {/* Error State */}
            {error && !isLoading && (
              <div className="flex items-center justify-center py-8">
                <div className="text-center">
                  <div className="w-12 h-12 bg-red-100 dark:bg-red-900/30 rounded-full flex items-center justify-center mx-auto mb-3">
                    <X className="w-6 h-6 text-red-600 dark:text-red-400" />
                  </div>
                  <h3 className="text-sm font-medium text-gray-900 dark:text-gray-100 mb-1">{t('common.loadFailed', '加载失败')}</h3>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mb-3">{error}</p>
                  <button
                    onClick={handleRetry}
                    className="px-3 py-1.5 bg-blue-500 dark:bg-blue-600 text-white text-xs rounded hover:bg-blue-600 dark:hover:bg-blue-700 transition-colors"
                  >
                    {t('common.retry', '重试')}
                  </button>
                </div>
              </div>
            )}

            {/* Tools List */}
            {!isLoading && !error && (
              <div className="space-y-2">
                {filteredTools.length === 0 ? (
                  <div className="text-center py-8 text-gray-500 dark:text-gray-400">
                    <Wrench className="w-8 h-8 mx-auto mb-2 opacity-50" />
                    <p>{t('mcp.selectModal.noMatch', '未找到匹配的MCP工具')}</p>
                  </div>
                ) : (
                  filteredTools.map((tool: MCPTool) => {
                    const isSelected = tempSelectedTools.includes(tool.id);
                    // Use consistent avatar generation like other components
                    const displayName = tool.title || tool.name;
                    const toolAvatar = generateDefaultAvatar(displayName, tool.id);

                    return (
                      <div
                        key={tool.id}
                        onClick={() => handleToolClick(tool)}
                        className={`flex items-center justify-between p-3 rounded-md border cursor-pointer transition-colors ${
                          isSelected
                            ? 'bg-blue-50 border-blue-200 hover:bg-blue-100 dark:bg-blue-900/30 dark:border-blue-700 dark:hover:bg-blue-900/50'
                            : 'bg-white border-gray-200 hover:bg-gray-50 dark:bg-gray-800 dark:border-gray-700 dark:hover:bg-gray-700'
                        }`}
                      >
                    <div className="flex items-center space-x-3">
                      <div className={`w-10 h-10 rounded-lg flex items-center justify-center text-white font-bold text-sm ${toolAvatar.colorClass}`}>
                        {toolAvatar.letter}
                      </div>
                      <div>
                        <div className={`text-sm font-semibold ${isSelected ? 'text-blue-900 dark:text-blue-300' : 'text-gray-800 dark:text-gray-100'}`}>
                          {tool.name}
                        </div>
                        <div className="text-xs text-gray-500 dark:text-gray-400">{tool.short_no || tool.author}</div>
                        <div className="text-xs text-gray-500 dark:text-gray-400 mt-1 leading-snug">
                          {tool.description}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center space-x-2">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleConfigTool(tool);
                        }}
                        className="p-1.5 text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors"
                        title={t('mcp.selectModal.configTool', '配置工具')}
                      >
                        <Settings className="w-4 h-4" />
                      </button>
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => handleToolClick(tool)}
                        className="rounded border-gray-300 dark:border-gray-600 text-blue-600 dark:text-blue-500 focus:ring-blue-500 dark:bg-gray-700"
                      />
                    </div>
                  </div>
                    );
                  })
                )}
              </div>
            )}
          </div>
        </div>

        {/* Tool Management Link */}
        <div className="p-4 border-t border-gray-200 dark:border-gray-700 flex-shrink-0">
          <button
            onClick={handleManageTools}
            className="flex items-center space-x-2 text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 text-sm transition-colors"
          >
            <span>{t('mcp.selectModal.manageTools', '管理MCP工具')}</span>
            <ExternalLink className="w-4 h-4" />
          </button>
        </div>

        {/* Footer - Always Visible */}
        <div className="flex justify-end space-x-3 p-4 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900 flex-shrink-0">
          <button
            onClick={handleCancel}
            className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-200 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-md hover:bg-gray-50 dark:hover:bg-gray-600"
          >
            {t('common.cancel', '取消')}
          </button>
          <button
            onClick={handleConfirm}
            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 dark:bg-blue-700 border border-transparent rounded-md hover:bg-blue-700 dark:hover:bg-blue-800"
          >
            {t('mcp.selectModal.confirmSelection', '确认选择 ({{count}})', { count: tempSelectedTools.length })}
          </button>
        </div>
      </div>

      {/* Tool Configuration Modal */}
      <MCPToolConfigModal
        isOpen={showConfigModal}
        onClose={() => setShowConfigModal(false)}
        tool={configTool}
        initialConfig={configTool ? tempToolConfigs[configTool.id] : undefined}
        onSave={handleSaveConfig}
      />
    </div>
  );
};

export default MCPToolSelectionModal;
