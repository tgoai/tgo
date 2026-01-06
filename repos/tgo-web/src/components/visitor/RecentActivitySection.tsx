import React, { useMemo } from 'react';
import { Eye, LogIn, LogOut, Activity as ActivityIcon, History } from 'lucide-react';
import type { VisitorActivity } from '@/types';
import { useTranslation } from 'react-i18next';
import CollapsibleSection from '../ui/CollapsibleSection';
import { formatRelativeTime } from '@/utils/dateUtils';

interface RecentActivitySectionProps {
  activities?: VisitorActivity[];
  className?: string;
  draggable?: boolean;
  expanded?: boolean;
  onToggle?: (expanded: boolean) => void;
  onDragStart?: (e: React.DragEvent) => void;
  onDragEnd?: (e: React.DragEvent) => void;
  onDragOver?: (e: React.DragEvent) => void;
  onDrop?: (e: React.DragEvent) => void;
}

function formatDuration(seconds?: number | null, t?: any): string | null {
  if (seconds == null || !Number.isFinite(seconds)) return null;
  const s = Math.floor(seconds);
  if (s < 60) return t ? t('visitor.activity.duration.seconds', { count: s, defaultValue: `\u6301\u7eed ${s}\u79d2` }) : `持续 ${s}秒`;
  const m = Math.floor(s / 60);
  const rs = s % 60;
  if (rs) {
    return t ? t('visitor.activity.duration.minutesSeconds', { m, s: rs, defaultValue: `\u6301\u7eed ${m}\u5206${rs}\u79d2` }) : `持续 ${m}分${rs}秒`;
  }
  return t ? t('visitor.activity.duration.minutes', { count: m, defaultValue: `\u6301\u7eed ${m}\u5206\u949f` }) : `持续 ${m}分钟`;
}

function getActivityIconAndColor(type: string) {
  const wrap = (el: React.ReactNode, bg: string, fg: string) => (
    <div className={`h-7 w-7 rounded-full ${bg} flex items-center justify-center flex-shrink-0`}
         aria-hidden="true">
      <span className={`inline-flex ${fg}`}>
        {el}
      </span>
    </div>
  );
  switch (type) {
    case 'session_start':
      return wrap(<LogIn className="w-3.5 h-3.5" />, 'bg-emerald-50 dark:bg-emerald-900/30', 'text-emerald-600 dark:text-emerald-400');
    case 'session_end':
      return wrap(<LogOut className="w-3.5 h-3.5" />, 'bg-gray-50 dark:bg-gray-700', 'text-gray-500 dark:text-gray-400');
    case 'page_view':
      return wrap(<Eye className="w-3.5 h-3.5" />, 'bg-blue-50 dark:bg-blue-900/30', 'text-blue-600 dark:text-blue-400');
    default:
      return wrap(<ActivityIcon className="w-3.5 h-3.5" />, 'bg-gray-50 dark:bg-gray-700', 'text-gray-500 dark:text-gray-400');
  }
}

/**
 * 最近活动模块组件（使用渠道详情 API 的 recent_activities 数据）
 */
const RecentActivitySection: React.FC<RecentActivitySectionProps> = ({ 
  activities, 
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
  const list = useMemo(() => {
    const arr = Array.isArray(activities) ? [...activities] : [];
    arr.sort((a, b) => new Date(b.occurred_at).getTime() - new Date(a.occurred_at).getTime());
    return arr;
  }, [activities]);

  return (
    <CollapsibleSection
      title={t('visitor.sections.recentActivity', '最近活动')}
      className={className}
      defaultExpanded={false}
      expanded={expanded}
      onToggle={onToggle}
      draggable={draggable}
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
      onDragOver={onDragOver}
      onDrop={onDrop}
    >
      <div className="space-y-3 relative before:absolute before:inset-0 before:left-[13px] before:w-px before:bg-gray-100 dark:before:bg-gray-800 before:pointer-events-none px-0.5">
        {list.map((act) => {
          const durationText = formatDuration(act.duration_seconds, t);
          const pageUrl = act.context?.page_url;
          return (
            <div key={act.id} className="relative flex items-start gap-4 group/item">
              <div className="z-10 bg-white dark:bg-gray-900 ring-4 ring-white dark:ring-gray-800">
                {getActivityIconAndColor(act.activity_type)}
              </div>
              <div className="flex-1 min-w-0 pt-0.5 pb-2 border-b border-gray-50 dark:border-gray-800/50 group-last/item:border-0">
                <div className="flex justify-between items-center gap-2">
                  <span className="text-[12px] font-bold text-gray-700 dark:text-gray-200 truncate" title={act.title || act.activity_type}>
                    {act.title || act.activity_type}
                  </span>
                  <span className="text-[10px] text-gray-400 dark:text-gray-500 font-medium whitespace-nowrap">
                    {formatRelativeTime(act.occurred_at)}
                  </span>
                </div>
                
                <div className="mt-1 flex items-center gap-2 flex-wrap">
                  {durationText && (
                    <span className="text-[11px] text-gray-500 dark:text-gray-400 flex items-center">
                      <History className="w-2.5 h-2.5 mr-1" />
                      {durationText}
                    </span>
                  )}
                  {pageUrl && (
                    <a
                      href={pageUrl}
                      target="_blank"
                      rel="noreferrer"
                      className="text-[11px] text-blue-500 hover:underline truncate max-w-[180px]"
                      title={pageUrl}
                    >
                      {pageUrl.replace(/^(https?:\/\/)/, '')}
                    </a>
                  )}
                </div>
                
                {act.description && (
                  <div className="text-[11px] text-gray-400 dark:text-gray-500 mt-1 line-clamp-2 leading-relaxed italic">
                    {act.description}
                  </div>
                )}
              </div>
            </div>
          );
        })}
        {(!list || list.length === 0) && (
          <div className="py-8 text-center bg-gray-50/50 dark:bg-gray-900/30 rounded-lg border border-dashed border-gray-200 dark:border-gray-800">
            <History className="w-5 h-5 mx-auto mb-2 text-gray-300 dark:text-gray-600" />
            <div className="text-[12px] text-gray-400 dark:text-gray-500 italic">{t('visitor.activity.noActivity', '暂无活动记录')}</div>
          </div>
        )}
      </div>
    </CollapsibleSection>
  );
};

export default RecentActivitySection;
