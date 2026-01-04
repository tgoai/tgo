import React, { useState } from 'react';
import { ChevronDown, ChevronUp, GripVertical } from 'lucide-react';

interface CollapsibleSectionProps {
  title: string;
  icon?: React.ReactNode;
  defaultExpanded?: boolean;
  expanded?: boolean;
  onToggle?: (expanded: boolean) => void;
  children: React.ReactNode;
  className?: string;
  headerClassName?: string;
  rightContent?: React.ReactNode;
  draggable?: boolean;
  onDragStart?: (e: React.DragEvent) => void;
  onDragEnd?: (e: React.DragEvent) => void;
  onDragOver?: (e: React.DragEvent) => void;
  onDrop?: (e: React.DragEvent) => void;
}

/**
 * A reusable collapsible section component for panels.
 */
const CollapsibleSection: React.FC<CollapsibleSectionProps> = ({
  title,
  icon,
  defaultExpanded = true,
  expanded,
  onToggle,
  children,
  className = '',
  headerClassName = '',
  rightContent,
  draggable = false,
  onDragStart,
  onDragEnd,
  onDragOver,
  onDrop,
}) => {
  const [internalExpanded, setInternalExpanded] = useState(defaultExpanded);
  const [isHandlePressed, setIsHandlePressed] = useState(false);

  const isExpanded = expanded !== undefined ? expanded : internalExpanded;

  const handleToggle = () => {
    const nextState = !isExpanded;
    if (onToggle) {
      onToggle(nextState);
    } else {
      setInternalExpanded(nextState);
    }
  };

  return (
    <div 
      className={`space-y-2.5 ${className}`}
      draggable={draggable && isHandlePressed}
      onDragStart={onDragStart}
      onDragEnd={(e) => {
        setIsHandlePressed(false);
        onDragEnd?.(e);
      }}
      onDragOver={onDragOver}
      onDrop={onDrop}
    >
      <div
        className={`flex items-center justify-between cursor-pointer group select-none py-1 ${headerClassName}`}
        onClick={handleToggle}
        onMouseDown={(e) => {
          // 只有点击句柄或标题区域才允许拖拽
          const target = e.target as HTMLElement;
          if (target.closest('.drag-handle') || target.tagName === 'H4' || target.closest('h4')) {
            setIsHandlePressed(true);
          }
        }}
        onMouseUp={() => setIsHandlePressed(false)}
      >
        <div className="flex items-center space-x-2 flex-1 min-w-0">
          {draggable && (
            <div 
              className="drag-handle text-gray-300 dark:text-gray-600 hover:text-gray-500 dark:hover:text-gray-400 cursor-grab active:cursor-grabbing p-0.5 -ml-1 flex-shrink-0 transition-colors"
              onClick={(e) => e.stopPropagation()} // Prevent collapse when clicking handle
            >
              <GripVertical size={14} />
            </div>
          )}
          {icon && <span className="text-gray-400 dark:text-gray-500 flex-shrink-0">{icon}</span>}
          <h4 className="text-[11px] font-bold text-gray-500 dark:text-gray-400 uppercase tracking-widest truncate">
            {title}
          </h4>
          <span className="text-gray-300 group-hover:text-gray-500 dark:text-gray-600 dark:group-hover:text-gray-400 transition-colors flex-shrink-0">
            {isExpanded ? <ChevronUp size={12} strokeWidth={2.5} /> : <ChevronDown size={12} strokeWidth={2.5} />}
          </span>
        </div>
        {rightContent}
      </div>
      {isExpanded && (
        <div 
          className="animate-in fade-in slide-in-from-top-1 duration-200"
          onMouseDown={() => setIsHandlePressed(false)} // 在内容区按下鼠标时强制禁用拖拽
        >
          {children}
        </div>
      )}
    </div>
  );
};

export default CollapsibleSection;

