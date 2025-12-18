/**
 * Widget 共享组件
 * 可在各 Widget 中复用的通用组件
 */

import React, { useCallback, useState } from 'react';
import { ExternalLink, Copy, MessageSquare, Check } from 'lucide-react';
import { parseActionURI, executeAction, type ActionProtocol } from '../../utils/actionUri';
import type { WidgetAction } from './types';

/**
 * 获取 Action 图标
 */
const getActionIcon = (protocol: ActionProtocol | string): React.ReactNode => {
  switch (protocol) {
    case 'url':
      return <ExternalLink className="inline-block w-3 h-3 ml-1" />;
    case 'copy':
      return <Copy className="inline-block w-3 h-3 ml-1" />;
    case 'msg':
      return <MessageSquare className="inline-block w-3 h-3 ml-1" />;
    default:
      return null;
  }
};

/**
 * 简单的内联 Toast 提示
 */
const InlineToast: React.FC<{
  message: string;
  type: 'success' | 'error';
  onClose: () => void;
}> = ({ message, type, onClose }) => {
  React.useEffect(() => {
    const timer = setTimeout(onClose, 2500);
    return () => clearTimeout(timer);
  }, [onClose]);

  // 内联 keyframes 动画
  React.useEffect(() => {
    const styleId = 'widget-toast-animation';
    if (!document.getElementById(styleId)) {
      const style = document.createElement('style');
      style.id = styleId;
      style.textContent = `
        @keyframes widget-toast-slide-in {
          from {
            transform: translateX(100%);
            opacity: 0;
          }
          to {
            transform: translateX(0);
            opacity: 1;
          }
        }
      `;
      document.head.appendChild(style);
    }
  }, []);

  return (
    <div
      className={`fixed bottom-4 right-4 z-[9999] flex items-center gap-2 px-4 py-3 rounded-lg shadow-lg ${
        type === 'success'
          ? 'bg-green-500 text-white'
          : 'bg-red-500 text-white'
      }`}
      style={{
        animation: 'widget-toast-slide-in 0.3s ease-out',
      }}
    >
      {type === 'success' ? (
        <Check className="w-4 h-4" />
      ) : (
        <ExternalLink className="w-4 h-4" />
      )}
      <span className="text-sm font-medium">{message}</span>
    </div>
  );
};

/**
 * 操作按钮组件 Props
 */
interface ActionButtonsProps {
  actions?: WidgetAction[];
  /** 发送消息回调（用于 msg:// 协议） */
  onSendMessage?: (message: string) => void;
  /** 通用 action 回调（用于非标准 URI 或向后兼容） */
  onAction?: (action: string, payload?: Record<string, unknown>) => void;
  /** 复制成功回调 */
  onCopySuccess?: (text: string) => void;
}

/**
 * 操作按钮组件
 */
export const ActionButtons: React.FC<ActionButtonsProps> = ({ 
  actions, 
  onSendMessage,
  onAction,
  onCopySuccess,
}) => {
  // Toast 状态
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  const showToast = useCallback((message: string, type: 'success' | 'error' = 'success') => {
    setToast({ message, type });
  }, []);

  const hideToast = useCallback(() => {
    setToast(null);
  }, []);

  const handleClick = useCallback(async (action: WidgetAction) => {
    const parsed = parseActionURI(action.action);

    if (parsed.isValid) {
      // 使用 Action URI 处理
      const result = await executeAction(action.action, {
        onSendMessage: (msg) => {
          if (onSendMessage) {
            onSendMessage(msg);
            showToast('消息已发送', 'success');
          } else {
            console.warn('[ActionButtons] onSendMessage not provided');
            showToast('消息发送功能不可用', 'error');
          }
        },
        onCopySuccess: (text) => {
          // 显示复制成功提示
          showToast('已复制到剪贴板', 'success');
          // 调用外部回调
          onCopySuccess?.(text);
        },
        onCopyError: (error) => {
          console.error('[ActionButtons] Copy failed:', error);
          showToast('复制失败', 'error');
        },
        onUnknownProtocol: (uri) => {
          // 回退到旧的处理方式
          console.log('[ActionButtons] Unknown protocol, fallback:', uri.raw);
          onAction?.(uri.raw, action.payload);
        },
      });

      // 如果是 url:// 协议，不需要额外提示，window.open 会打开新窗口
      if (!result.success && parsed.protocol !== 'url') {
        console.warn('[ActionButtons] Action failed:', result.error);
      }
    } else if (action.url) {
      // 兼容旧的 url 字段
      window.open(action.url, '_blank', 'noopener,noreferrer');
    } else {
      // 兼容旧的 action 字段（非 URI 格式）
      onAction?.(action.action, action.payload);
    }
  }, [onSendMessage, onAction, onCopySuccess, showToast]);

  if (!actions || actions.length === 0) return null;

  return (
    <>
      <div className="mt-4 flex flex-wrap gap-2">
        {actions.map((action, index) => {
          const parsed = parseActionURI(action.action);
          const icon = parsed.isValid ? getActionIcon(parsed.protocol) : (action.url ? <ExternalLink className="inline-block w-3 h-3 ml-1" /> : null);

          return (
            <button
              key={index}
              onClick={() => handleClick(action)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                action.style === 'primary'
                  ? 'bg-blue-600 text-white hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600'
                  : action.style === 'danger'
                    ? 'bg-red-500 text-white hover:bg-red-600 dark:bg-red-600 dark:hover:bg-red-700'
                    : action.style === 'link'
                      ? 'text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300 underline'
                      : 'border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700'
              }`}
            >
              {action.label}
              {icon}
            </button>
          );
        })}
      </div>
      {/* Toast 提示 */}
      {toast && (
        <InlineToast
          message={toast.message}
          type={toast.type}
          onClose={hideToast}
        />
      )}
    </>
  );
};

/**
 * Widget 卡片容器
 */
export const WidgetCard: React.FC<{
  children: React.ReactNode;
  className?: string;
}> = ({ children, className = '' }) => (
  <div className={`border border-gray-200 dark:border-gray-700 rounded-xl p-5 shadow-sm bg-white dark:bg-gray-800 my-3 ${className}`}>
    {children}
  </div>
);

/**
 * Widget 头部
 */
export const WidgetHeader: React.FC<{
  icon?: React.ReactNode;
  iconBgColor?: string;
  title: React.ReactNode;
  subtitle?: React.ReactNode;
  badge?: React.ReactNode;
}> = ({ icon, iconBgColor = 'bg-blue-50 dark:bg-blue-900/30', title, subtitle, badge }) => (
  <div className="flex justify-between items-start mb-4">
    <div className="flex items-center gap-3">
      {icon && (
        <div className={`p-2 ${iconBgColor} rounded-lg`}>
          {icon}
        </div>
      )}
      <div>
        {subtitle && <span className="text-xs text-gray-500 dark:text-gray-400">{subtitle}</span>}
        <div className="font-semibold text-gray-900 dark:text-gray-100">{title}</div>
      </div>
    </div>
    {badge}
  </div>
);

/**
 * 状态徽章
 */
export const StatusBadge: React.FC<{
  children: React.ReactNode;
  icon?: React.ReactNode;
  bgColor?: string;
  textColor?: string;
}> = ({ 
  children, 
  icon, 
  bgColor = 'bg-blue-100 dark:bg-blue-900/30', 
  textColor = 'text-blue-800 dark:text-blue-300' 
}) => (
  <span className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium ${bgColor} ${textColor}`}>
    {icon}
    {children}
  </span>
);

/**
 * 信息行
 */
export const InfoRow: React.FC<{
  label: string;
  value: React.ReactNode;
  highlight?: boolean;
}> = ({ label, value, highlight }) => (
  <div className={`flex justify-between ${highlight ? 'font-semibold text-base pt-2 border-t border-gray-100 dark:border-gray-700' : 'text-sm'}`}>
    <span className={highlight ? 'text-gray-900 dark:text-gray-100' : 'text-gray-500 dark:text-gray-400'}>{label}</span>
    <span className={highlight ? 'text-red-500 dark:text-red-400' : 'text-gray-700 dark:text-gray-300'}>{value}</span>
  </div>
);

/**
 * 分隔线
 */
export const Divider: React.FC<{ className?: string }> = ({ className = '' }) => (
  <div className={`border-t border-gray-100 dark:border-gray-700 ${className}`} />
);

/**
 * 格式化价格
 */
export function formatPrice(price: number | undefined | null, currency: string = '¥'): string {
  if (price === undefined || price === null) {
    return `${currency}0.00`;
  }
  return `${currency}${price.toFixed(2)}`;
}
