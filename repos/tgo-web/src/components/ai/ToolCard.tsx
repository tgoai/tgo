import React, { useState, useRef, useEffect } from 'react';
import { Pencil, Trash2, Copy, Check, Globe, Radio, MoreVertical, Terminal, Wrench, Package } from 'lucide-react';
import type { AiTool } from '@/types';
import { useTranslation } from 'react-i18next';
import { getToolDisplayTitle } from '@/utils/projectToolsTransform';

interface ToolCardProps {
  tool: AiTool;
  onAction: (actionType: string, tool: AiTool) => void;
  onShowToast?: (type: 'success' | 'error' | 'warning' | 'info', title: string, message?: string) => void;
}

/**
 * Tool card component - Redesigned to be more subtle
 */
const ToolCard: React.FC<ToolCardProps> = ({ tool, onAction, onShowToast }) => {
  const [copiedEndpoint, setCopiedEndpoint] = useState(false);
  const [showMenu, setShowMenu] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  
  const { t, i18n } = useTranslation();

  // Determine display title based on language
  const displayTitle = getToolDisplayTitle(tool, i18n.language);

  // Extract tool data
  const toolType = tool.config?.tool_type || 'Tool';
  const transportType = tool.config?.transport_type || 'http';
  const endpoint = tool.config?.endpoint || tool.endpoint || '';

  // Close menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setShowMenu(false);
      }
    };
    if (showMenu) {
      document.addEventListener('mousedown', handleClickOutside);
    } else {
      document.removeEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [showMenu]);

  const handleAction = async (actionType: string): Promise<void> => {
    setShowMenu(false);
    onAction?.(actionType, tool);
  };

  const handleCopyEndpoint = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!endpoint) return;
    try {
      await navigator.clipboard.writeText(endpoint);
      setCopiedEndpoint(true);
      onShowToast?.('success', t('common.copied', '已复制'), t('tools.endpointCopied', '端点地址已复制到剪贴板'));
      setTimeout(() => setCopiedEndpoint(false), 2000);
    } catch (error) {
      onShowToast?.('error', t('common.copyFailed', '复制失败'), t('tools.copyEndpointFailed', '无法复制端点地址'));
    }
  };

  const getToolIconConfig = (toolType: string, transportType: string) => {
    const isMCP = toolType === 'MCP';
    const isFunction = toolType === 'FUNCTION';
    const transport = transportType.toLowerCase();

    if (isFunction) {
      // Function/HTTP tools use a consistent blue/globe theme
      return {
        icon: Globe,
        color: 'text-blue-600 dark:text-blue-400',
        bgColor: 'bg-blue-50 dark:bg-blue-900/20',
        label: 'HTTP'
      };
    }

    if (isMCP) {
      // MCP tools use a consistent green theme
      let Icon = Package;
      if (transport === 'stdio') Icon = Terminal;
      if (transport === 'sse') Icon = Radio;
      
      return {
        icon: Icon,
        color: 'text-green-600 dark:text-green-400',
        bgColor: 'bg-green-50 dark:bg-green-900/20',
        label: transport.toUpperCase() || 'MCP'
      };
    }

    // Fallback for unknown types
    return {
      icon: Wrench,
      color: 'text-gray-500',
      bgColor: 'bg-gray-50 dark:bg-gray-800/30',
      label: transportType.toUpperCase() || 'TOOL'
    };
  };

  const toolConfig = getToolIconConfig(toolType, transportType);
  const ToolIcon = toolConfig.icon;

  return (
    <div className="group relative bg-white dark:bg-gray-800 rounded-2xl p-5 flex flex-col justify-between shadow-sm hover:shadow-xl hover:-translate-y-1 transition-all duration-300 border border-gray-100 dark:border-gray-700 overflow-hidden">
      <div>
        <div className="flex justify-between items-start mb-4 gap-2">
          <div className="flex items-center space-x-3 flex-1 min-w-0">
            <div className={`flex-shrink-0 w-9 h-9 rounded-lg flex items-center justify-center ${toolConfig.bgColor} ${toolConfig.color} border border-gray-100 dark:border-gray-700/50`}>
              <ToolIcon className="w-5 h-5" />
            </div>
            <div className="flex-1 min-w-0">
              <h3 className="font-bold text-gray-900 dark:text-gray-100 group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors duration-200 truncate text-base" title={displayTitle}>
                {displayTitle}
              </h3>
              <div className="flex items-center mt-0.5">
                <span className={`text-[10px] px-1.5 py-0.5 rounded-md font-medium ${toolConfig.bgColor} ${toolConfig.color} border border-gray-100 dark:border-gray-700 flex-shrink-0`}>
                  {toolConfig.label}
                </span>
                <span className="mx-1.5 text-gray-300 dark:text-gray-600 flex-shrink-0">•</span>
                <span className="text-[10px] text-gray-400 dark:text-gray-500 font-medium truncate uppercase tracking-wider">{toolType}</span>
              </div>
            </div>
          </div>

          <div className="relative flex-shrink-0" ref={menuRef}>
            <button 
              onClick={() => setShowMenu(!showMenu)}
              className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-400 hover:text-gray-600 transition-colors"
            >
              <MoreVertical className="w-5 h-5" />
            </button>
            
            {showMenu && (
              <div className="absolute right-0 mt-2 w-40 bg-white dark:bg-gray-800 rounded-xl shadow-xl border border-gray-100 dark:border-gray-700 py-1 z-20 animate-in fade-in zoom-in-95 duration-200">
                <button onClick={() => handleAction('edit')} className="w-full flex items-center px-3 py-2 text-sm text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors">
                  <Pencil className="w-4 h-4 mr-2" /> {t('common.edit', '编辑')}
                </button>
                {endpoint && (
                  <button onClick={handleCopyEndpoint} className="w-full flex items-center px-3 py-2 text-sm text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors">
                    {copiedEndpoint ? <Check className="w-4 h-4 mr-2 text-green-500" /> : <Copy className="w-4 h-4 mr-2" />}
                    {t('tools.copyEndpoint', '复制端点')}
                  </button>
                )}
                <div className="h-px bg-gray-100 dark:bg-gray-700 my-1"></div>
                <button onClick={() => handleAction('delete')} className="w-full flex items-center px-3 py-2 text-sm text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors">
                  <Trash2 className="w-4 h-4 mr-2" /> {t('common.delete', '删除')}
                </button>
              </div>
            )}
          </div>
        </div>

        <p className="text-sm text-gray-600 dark:text-gray-400 leading-relaxed mb-4 line-clamp-2 h-10 group-hover:text-gray-700 dark:group-hover:text-gray-300 transition-colors">
          {tool.description || t('tools.noDescription', '暂无描述')}
        </p>

        {endpoint && (
          <div className="flex items-center text-[11px] text-gray-500 dark:text-gray-500 bg-gray-50/50 dark:bg-gray-800/50 px-2 py-1.5 rounded-lg border border-gray-100/50 dark:border-gray-700/50 mt-auto">
            <Globe className="w-3.5 h-3.5 mr-2 opacity-50" />
            <span className="font-mono truncate opacity-80">{endpoint}</span>
          </div>
        )}
      </div>

      <div className="mt-5 flex items-center gap-2">
        <button
          onClick={() => handleAction('edit')}
          className="flex-1 flex items-center justify-center gap-2 py-2 px-4 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-xl shadow-lg shadow-blue-200 dark:shadow-none transition-all duration-200 active:scale-95"
        >
          <Pencil className="w-3.5 h-3.5" />
          {t('tools.editTool', '编辑工具')}
        </button>
      </div>
    </div>
  );
};

export default ToolCard;
