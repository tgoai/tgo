/**
 * 产品列表 Widget 组件
 */

import React from 'react';
import { LayoutGrid, Star } from 'lucide-react';
import type { WidgetDefinition, WidgetComponentProps, ProductListWidgetData } from './types';
import { WidgetCard, ActionButtons } from './shared';

/**
 * 产品列表 Widget 组件
 */
const ProductListWidgetComponent: React.FC<WidgetComponentProps<ProductListWidgetData>> = ({ 
  data, 
  onAction,
  onSendMessage,
  onCopySuccess,
}) => {
  return (
    <WidgetCard>
      {/* 标题 */}
      {(data.title || data.subtitle) && (
        <div className="mb-4">
          {data.title && (
            <h3 className="font-semibold text-lg text-gray-900 dark:text-gray-100 flex items-center gap-2">
              <LayoutGrid className="w-5 h-5 text-blue-600 dark:text-blue-400" />
              {data.title}
            </h3>
          )}
          {data.subtitle && (
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">{data.subtitle}</p>
          )}
        </div>
      )}

      {/* 产品网格 */}
      <div className="grid grid-cols-2 gap-3">
        {(data.products || []).map((product, index) => (
          <div
            key={index}
            className="border border-gray-100 dark:border-gray-700 rounded-lg p-3 hover:shadow-md transition-shadow cursor-pointer bg-gray-50 dark:bg-gray-700/50"
          >
            {product.thumbnail && (
              <img
                src={product.thumbnail}
                alt={product.name}
                className="w-full h-24 object-cover rounded mb-2"
              />
            )}
            <p className="font-medium text-sm text-gray-900 dark:text-gray-100 truncate">{product.name}</p>
            <div className="flex items-center justify-between mt-1">
              <span className="text-red-500 dark:text-red-400 font-semibold">¥{product.price}</span>
              {product.rating !== undefined && (
                <span className="text-xs text-gray-500 dark:text-gray-400 flex items-center gap-0.5">
                  <Star className="w-3 h-3 text-yellow-400 fill-yellow-400" />
                  {product.rating}
                </span>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* 分页信息 */}
      {data.total_count !== undefined && (
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-3 text-center">
          共 {data.total_count} 件商品
          {data.has_more && ' · 还有更多'}
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
 * 产品列表 Widget 定义
 */
export const productListWidgetDefinition: WidgetDefinition<ProductListWidgetData> = {
  type: 'product_list',
  displayName: '商品列表',
  description: '显示多个商品的网格列表',
  component: ProductListWidgetComponent,
  icon: <LayoutGrid className="w-4 h-4" />,
  toolbarColor: 'text-orange-600 dark:text-orange-400 bg-orange-50 dark:bg-orange-900/30 hover:bg-orange-100 dark:hover:bg-orange-900/50',
};

export default ProductListWidgetComponent;
