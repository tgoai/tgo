/**
 * 价格对比 Widget 组件
 */

import React from 'react';
import { Table2 } from 'lucide-react';
import type { WidgetDefinition, WidgetComponentProps, PriceComparisonWidgetData } from './types';
import { WidgetCard, ActionButtons } from './shared';

/**
 * 价格对比 Widget 组件
 */
const PriceComparisonWidgetComponent: React.FC<WidgetComponentProps<PriceComparisonWidgetData>> = ({ 
  data, 
  onAction,
  onSendMessage,
  onCopySuccess,
}) => {
  return (
    <WidgetCard>
      {/* 标题 */}
      {data.title && (
        <h3 className="font-semibold text-lg text-gray-900 dark:text-gray-100 mb-4">{data.title}</h3>
      )}

      {/* 表格 */}
      <div className="overflow-x-auto -mx-2">
        <table className="w-full border-collapse min-w-full">
          <thead>
            <tr>
              {(data.columns || []).map((col, i) => (
                <th
                  key={i}
                  className="px-3 py-2 text-left text-sm font-semibold text-gray-900 dark:text-gray-100 bg-gray-100 dark:bg-gray-700 border border-gray-200 dark:border-gray-600"
                >
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {(data.items || []).map((item, i) => (
              <tr
                key={i}
                className={`${
                  i === data.recommended_index
                    ? 'bg-green-50 dark:bg-green-900/20'
                    : ''
                }`}
              >
                {(data.columns || []).map((col, j) => (
                  <td
                    key={j}
                    className={`px-3 py-2 text-sm border border-gray-200 dark:border-gray-600 ${
                      i === data.recommended_index
                        ? 'text-green-800 dark:text-green-300'
                        : 'text-gray-700 dark:text-gray-300'
                    }`}
                  >
                    {item[col]}
                    {i === data.recommended_index && j === 0 && (
                      <span className="ml-2 inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-green-100 dark:bg-green-800 text-green-700 dark:text-green-200">
                        推荐
                      </span>
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* 推荐原因 */}
      {data.recommendation_reason && (
        <p className="mt-3 text-sm text-green-600 dark:text-green-400 flex items-start gap-1.5">
          <span className="text-base">💡</span>
          <span>{data.recommendation_reason}</span>
        </p>
      )}

      {/* 操作按钮 */}
      <ActionButtons 
        actions={data.actions} 
        onAction={onAction}
        onSendMessage={onSendMessage}
        onCopySuccess={onCopySuccess}
      />
    </WidgetCard>
  );
};

/**
 * 价格对比 Widget 定义
 */
export const priceComparisonWidgetDefinition: WidgetDefinition<PriceComparisonWidgetData> = {
  type: 'price_comparison',
  displayName: '价格对比',
  description: '以表格形式对比不同选项的价格',
  component: PriceComparisonWidgetComponent,
  icon: <Table2 className="w-4 h-4" />,
  toolbarColor: 'text-teal-600 dark:text-teal-400 bg-teal-50 dark:bg-teal-900/30 hover:bg-teal-100 dark:hover:bg-teal-900/50',
};

export default PriceComparisonWidgetComponent;
