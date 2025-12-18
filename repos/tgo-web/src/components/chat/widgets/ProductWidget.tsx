/**
 * 产品 Widget 组件
 */

import React from 'react';
import { ShoppingBag, Star } from 'lucide-react';
import type { WidgetDefinition, WidgetComponentProps, ProductWidgetData } from './types';
import { ActionButtons, formatPrice } from './shared';

/**
 * 产品 Widget 组件
 */
const ProductWidgetComponent: React.FC<WidgetComponentProps<ProductWidgetData>> = ({ data, onAction, onSendMessage }) => {
  if (!data) return null;
  const currency = data.currency || '¥';
  const hasDiscount = data.original_price && data.original_price > data.price;

  return (
    <div className="border border-gray-200 dark:border-gray-700 rounded-xl overflow-hidden shadow-sm bg-white dark:bg-gray-800 my-3">
      {/* 图片 */}
      {data.thumbnail && (
        <div className="relative">
          <img
            src={data.thumbnail.url}
            alt={data.thumbnail.alt || data.name}
            className="w-full h-48 object-cover"
          />
          {data.discount_label && (
            <span className="absolute top-2 left-2 px-2 py-1 bg-red-500 text-white text-xs font-medium rounded">
              {data.discount_label}
            </span>
          )}
        </div>
      )}

      <div className="p-4">
        {/* 标签 */}
        {data.tags && data.tags.length > 0 && (
          <div className="flex flex-wrap gap-1 mb-2">
            {data.tags.slice(0, 3).map((tag, index) => (
              <span
                key={index}
                className="px-2 py-0.5 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 text-xs rounded"
              >
                {tag}
              </span>
            ))}
          </div>
        )}

        {/* 名称 */}
        <h3 className="font-semibold text-lg text-gray-900 dark:text-gray-100 line-clamp-2">{data.name}</h3>

        {/* 品牌 */}
        {data.brand && (
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">{data.brand}</p>
        )}

        {/* 描述 */}
        {data.description && (
          <p className="text-sm text-gray-600 dark:text-gray-400 mt-2 line-clamp-2">{data.description}</p>
        )}

        {/* 价格 */}
        <div className="mt-3 flex items-baseline gap-2">
          <span className="text-2xl text-red-500 dark:text-red-400 font-bold">
            {formatPrice(data.price, currency)}
          </span>
          {hasDiscount && (
            <span className="text-sm text-gray-400 dark:text-gray-500 line-through">
              {formatPrice(data.original_price!, currency)}
            </span>
          )}
        </div>

        {/* 评分 */}
        {data.rating !== undefined && !isNaN(Number(data.rating)) && (
          <div className="mt-2 flex items-center gap-1.5 text-sm">
            <Star className="w-4 h-4 text-yellow-400 fill-yellow-400" />
            <span className="font-medium text-gray-900 dark:text-gray-100">{Number(data.rating).toFixed(1)}</span>
            {data.review_count !== undefined && (
              <span className="text-gray-400 dark:text-gray-500">({data.review_count}条评价)</span>
            )}
          </div>
        )}

        {/* 库存状态 */}
        <p className={`mt-2 text-sm font-medium ${data.in_stock !== false ? 'text-green-600 dark:text-green-400' : 'text-red-500 dark:text-red-400'}`}>
          {data.in_stock !== false ? (data.stock_status || '有货') : '暂时缺货'}
        </p>

        {/* 规格 */}
        {data.specs && data.specs.length > 0 && (
          <div className="mt-3 pt-3 border-t border-gray-100 dark:border-gray-700 space-y-1">
            {data.specs.slice(0, 4).map((spec, index) => (
              <div key={index} className="flex text-sm">
                <span className="text-gray-500 dark:text-gray-400 w-20 flex-shrink-0">{spec.name}</span>
                <span className="text-gray-700 dark:text-gray-300">{spec.value}</span>
              </div>
            ))}
          </div>
        )}

        {/* 操作按钮 */}
        <ActionButtons actions={data.actions} onAction={onAction} onSendMessage={onSendMessage} />
      </div>
    </div>
  );
};

/**
 * 产品 Widget 定义
 */
export const productWidgetDefinition: WidgetDefinition<ProductWidgetData> = {
  type: 'product',
  displayName: '商品详情',
  description: '显示单个商品的详细信息',
  component: ProductWidgetComponent,
  icon: <ShoppingBag className="w-4 h-4" />,
  toolbarColor: 'text-green-600 dark:text-green-400 bg-green-50 dark:bg-green-900/30 hover:bg-green-100 dark:hover:bg-green-900/50',
};

export default ProductWidgetComponent;

