import React, { useEffect, useState, useMemo } from 'react';
import { ChevronDown, ChevronUp, Puzzle, Loader2 } from 'lucide-react';
import * as LucideIcons from 'lucide-react';
import { usePluginStore } from '@/stores/pluginStore';
import PluginTemplateRenderer from './PluginTemplateRenderer';
import { useTranslation } from 'react-i18next';
import CollapsibleSection from '../ui/CollapsibleSection';

interface PluginPanelSectionProps {
  visitorId: string;
  context: any;
  className?: string;
  draggable?: boolean;
  expanded?: boolean;
  onToggle?: (expanded: boolean) => void;
  onDragStart?: (e: React.DragEvent) => void;
  onDragEnd?: (e: React.DragEvent) => void;
  onDragOver?: (e: React.DragEvent) => void;
  onDrop?: (e: React.DragEvent) => void;
}

const EMPTY_ARRAY: any[] = [];

const PluginPanelSection: React.FC<PluginPanelSectionProps> = ({ 
  visitorId, 
  context,
  className = '',
  draggable,
  expanded,
  onToggle,
  onDragStart,
  onDragEnd,
  onDragOver,
  onDrop,
}) => {
  const { t } = useTranslation();
  const visitorPanels = usePluginStore((state) => state.visitorPanels[visitorId] || EMPTY_ARRAY);
  const fetchVisitorPanels = usePluginStore((state) => state.fetchVisitorPanels);
  const isLoading = usePluginStore((state) => state.isLoadingVisitorPanels);
  const [expandedPanels, setExpandedPanels] = useState<Record<string, boolean>>({});

  // Memoize context to avoid unnecessary re-renders if the object hasn't changed its values
  const memoizedContext = useMemo(() => context, [
    context.visitor_id,
    context.channel_id,
    context.channel_type,
    context.platform_type
  ]);

  useEffect(() => {
    if (visitorId) {
      fetchVisitorPanels(visitorId, memoizedContext);
    }
  }, [visitorId, fetchVisitorPanels, memoizedContext]);

  const togglePanel = (id: string) => {
    setExpandedPanels((prev) => ({
      ...prev,
      [id]: !prev[id],
    }));
  };

  const renderIcon = (iconName?: string) => {
    if (!iconName) return <Puzzle size={14} className="mr-2" />;
    
    // Convert crown -> Crown, external-link -> ExternalLink
    const pascalName = iconName
      .split(/[-_]/)
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join('');
      
    const Icon = (LucideIcons as any)[pascalName] || (LucideIcons as any)[iconName];
    if (!Icon) return <Puzzle size={14} className="mr-2" />;
    return <Icon size={14} className="mr-2" />;
  };

  if (isLoading && visitorPanels.length === 0) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="w-5 h-5 text-gray-400 animate-spin mr-2" />
        <span className="text-xs text-gray-400 italic">{t('plugin.ui.loading', '正在加载插件...')}</span>
      </div>
    );
  }

  if (visitorPanels.length === 0) return null;

  return (
    <CollapsibleSection
      title={t('plugin.ui.title', '扩展功能')}
      defaultExpanded={true}
      expanded={expanded}
      onToggle={onToggle}
      className={className}
      draggable={draggable}
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
      onDragOver={onDragOver}
      onDrop={onDrop}
    >
      <div className="space-y-3 pt-1 px-0.5">
        {visitorPanels.map((panel) => {
          const isExpanded = expandedPanels[panel.plugin_id] !== false; // Default expanded
          
          return (
            <div
              key={panel.plugin_id}
              className="rounded-lg border border-gray-100 dark:border-gray-800 overflow-hidden bg-white dark:bg-gray-900 shadow-sm"
            >
              <button
                onClick={() => togglePanel(panel.plugin_id)}
                className="w-full flex items-center justify-between p-2.5 text-[12px] font-bold text-gray-700 dark:text-gray-200 bg-gray-50/50 dark:bg-gray-800/50 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
              >
                <div className="flex items-center">
                  <span className="text-gray-400 dark:text-gray-500 mr-2">
                    {renderIcon(panel.icon)}
                  </span>
                  {panel.title}
                </div>
                <span className="text-gray-400 dark:text-gray-500">
                  {isExpanded ? <ChevronUp size={12} strokeWidth={2.5} /> : <ChevronDown size={12} strokeWidth={2.5} />}
                </span>
              </button>
              
              {isExpanded && (
                <div className="p-3 border-t border-gray-50 dark:border-gray-800">
                  <PluginTemplateRenderer
                    pluginId={panel.plugin_id}
                    template={panel.ui.template}
                    data={panel.ui.data}
                    context={context}
                  />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </CollapsibleSection>
  );
};

export default PluginPanelSection;

