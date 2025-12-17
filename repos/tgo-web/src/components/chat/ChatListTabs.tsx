import React, { useRef, useEffect, useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';

export type ChatTabType = 'mine' | 'unassigned' | 'all' | 'manual';

interface ChatListTabsProps {
  activeTab: ChatTabType;
  onTabChange: (tab: ChatTabType) => void;
  counts: {
    mine: number;      // "我的" tab 显示未读数量
    unassigned: number; // "未分配" tab 显示等待数量
    // "全部" tab 不显示数量
  };
}

export const ChatListTabs: React.FC<ChatListTabsProps> = ({ activeTab, onTabChange, counts }) => {
  const { t } = useTranslation();
  const containerRef = useRef<HTMLDivElement>(null);
  const [indicatorStyle, setIndicatorStyle] = useState({ left: 0, width: 0 });

  const tabs: { key: ChatTabType; label: string; count?: number }[] = [
    { key: 'mine', label: t('chat.list.tabs.mine', '我的'), count: counts.mine > 0 ? counts.mine : undefined },
    { key: 'unassigned', label: t('chat.list.tabs.unassigned', '未分配'), count: counts.unassigned > 0 ? counts.unassigned : undefined },
    { key: 'all', label: t('chat.list.tabs.all', '已完成') }, // 已完成 tab 不显示数量
    // { key: 'manual', label: t('chat.list.tabs.manual', '转人工') }, // 转人工 tab 不显示数量
  ];

  const updateIndicator = useCallback(() => {
    if (!containerRef.current) return;
    const activeButton = containerRef.current.querySelector(`[data-tab="${activeTab}"]`) as HTMLElement;
    if (activeButton) {
      const buttonLeft = activeButton.offsetLeft;
      const buttonWidth = activeButton.offsetWidth;
      // Match indicator width to button content width
      setIndicatorStyle({
        left: buttonLeft,
        width: buttonWidth,
      });
    }
  }, [activeTab]);

  useEffect(() => {
    updateIndicator();
    window.addEventListener('resize', updateIndicator);
    return () => window.removeEventListener('resize', updateIndicator);
  }, [updateIndicator]);

  return (
    <div 
      ref={containerRef}
      className="relative flex items-stretch px-4 gap-5 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700"
    >
      {tabs.map((tab) => {
        const isActive = activeTab === tab.key;
        return (
          <button
            key={tab.key}
            data-tab={tab.key}
            onClick={() => onTabChange(tab.key)}
            className={`
              relative py-2.5 text-[13px] font-medium transition-all duration-200 outline-none
              flex items-center gap-1.5
              ${isActive 
                ? 'text-gray-900 dark:text-white' 
                : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
              }
            `}
          >
            <span>{tab.label}</span>
            {/* Count number - only show if count exists and > 0 */}
            {tab.count !== undefined && (
              <span
                className={`
                  text-[11px] tabular-nums
                  ${isActive
                    ? 'text-gray-400 dark:text-gray-500'
                    : 'text-gray-400 dark:text-gray-500'
                  }
                `}
              >
                {tab.count}
              </span>
            )}
          </button>
        );
      })}
      
      {/* Animated indicator line */}
      <div
        className="absolute bottom-0 h-0.5 bg-blue-500 dark:bg-blue-400 rounded-full transition-all duration-300 ease-[cubic-bezier(0.4,0,0.2,1)]"
        style={{
          left: indicatorStyle.left,
          width: indicatorStyle.width,
          transform: 'translateZ(0)', // GPU acceleration
        }}
      />
    </div>
  );
};
