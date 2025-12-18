/**
 * 订单 Widget 组件
 */

import React from 'react';
import { Package, Truck, MapPin, Clock, CheckCircle, XCircle, AlertCircle } from 'lucide-react';
import type { WidgetDefinition, WidgetComponentProps, OrderWidgetData, OrderStatus } from './types';
import { WidgetCard, WidgetHeader, StatusBadge, ActionButtons, InfoRow, formatPrice } from './shared';

/**
 * 订单状态配色映射
 */
const orderStatusConfig: Record<OrderStatus, { bg: string; text: string; icon: React.ReactNode }> = {
  pending: { bg: 'bg-yellow-100 dark:bg-yellow-900/30', text: 'text-yellow-800 dark:text-yellow-300', icon: <Clock className="w-4 h-4" /> },
  paid: { bg: 'bg-blue-100 dark:bg-blue-900/30', text: 'text-blue-800 dark:text-blue-300', icon: <CheckCircle className="w-4 h-4" /> },
  processing: { bg: 'bg-indigo-100 dark:bg-indigo-900/30', text: 'text-indigo-800 dark:text-indigo-300', icon: <Package className="w-4 h-4" /> },
  shipped: { bg: 'bg-purple-100 dark:bg-purple-900/30', text: 'text-purple-800 dark:text-purple-300', icon: <Truck className="w-4 h-4" /> },
  delivered: { bg: 'bg-green-100 dark:bg-green-900/30', text: 'text-green-800 dark:text-green-300', icon: <CheckCircle className="w-4 h-4" /> },
  completed: { bg: 'bg-green-100 dark:bg-green-900/30', text: 'text-green-800 dark:text-green-300', icon: <CheckCircle className="w-4 h-4" /> },
  cancelled: { bg: 'bg-gray-100 dark:bg-gray-700', text: 'text-gray-800 dark:text-gray-300', icon: <XCircle className="w-4 h-4" /> },
  refunded: { bg: 'bg-red-100 dark:bg-red-900/30', text: 'text-red-800 dark:text-red-300', icon: <AlertCircle className="w-4 h-4" /> },
};

/**
 * 订单 Widget 组件
 */
const OrderWidgetComponent: React.FC<WidgetComponentProps<OrderWidgetData>> = ({ data, onAction, onSendMessage }) => {
  if (!data) return null;
  const statusStyle = orderStatusConfig[data.status] || orderStatusConfig.pending;
  const currency = data.currency || '¥';

  return (
    <WidgetCard>
      {/* 头部 */}
      <WidgetHeader
        icon={<Package className="w-5 h-5 text-blue-600 dark:text-blue-400" />}
        iconBgColor="bg-blue-50 dark:bg-blue-900/30"
        subtitle="订单号"
        title={<span className="font-mono">{data.order_id}</span>}
        badge={
          <StatusBadge bgColor={statusStyle.bg} textColor={statusStyle.text} icon={statusStyle.icon}>
            {data.status_text || data.status}
          </StatusBadge>
        }
      />

      {/* 商品列表 */}
      {data.items && data.items.length > 0 && (
        <div className="border-t border-b border-gray-100 dark:border-gray-700 py-3 my-3 space-y-3">
          {data.items.map((item, index) => (
            <div key={index} className="flex justify-between items-center">
              <div className="flex items-center gap-3">
                {item.image && (
                  <img
                    src={item.image.url}
                    alt={item.image.alt || item.name}
                    className="w-14 h-14 object-cover rounded-lg border border-gray-100 dark:border-gray-700"
                  />
                )}
                <div>
                  <p className="font-medium text-gray-900 dark:text-gray-100">{item.name}</p>
                  {item.attributes && Object.keys(item.attributes).length > 0 && (
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                      {Object.entries(item.attributes).map(([k, v]) => `${k}: ${v}`).join(' | ')}
                    </p>
                  )}
                  {item.sku && (
                    <p className="text-xs text-gray-400 dark:text-gray-500">SKU: {item.sku}</p>
                  )}
                </div>
              </div>
              <div className="text-right">
                <p className="text-sm text-gray-500 dark:text-gray-400">×{item.quantity}</p>
                <p className="font-medium text-gray-900 dark:text-gray-100">{formatPrice(item.total_price, currency)}</p>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* 金额信息 */}
      <div className="space-y-2">
        <InfoRow label="商品小计" value={formatPrice(data.subtotal, currency)} />
        {data.shipping_fee !== undefined && data.shipping_fee > 0 && (
          <InfoRow label="运费" value={formatPrice(data.shipping_fee, currency)} />
        )}
        {data.discount !== undefined && data.discount > 0 && (
          <div className="flex justify-between text-sm text-red-500 dark:text-red-400">
            <span>优惠</span>
            <span>-{formatPrice(data.discount, currency)}</span>
          </div>
        )}
        <InfoRow label="合计" value={formatPrice(data.total, currency)} highlight />
      </div>

      {/* 收货信息 */}
      {data.shipping_address && (
        <div className="mt-4 p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg text-sm">
          <div className="flex items-start gap-2">
            <MapPin className="w-4 h-4 text-gray-400 mt-0.5 flex-shrink-0" />
            <div>
              <p className="font-medium text-gray-900 dark:text-gray-100">
                {data.receiver_name} {data.receiver_phone}
              </p>
              <p className="text-gray-600 dark:text-gray-400">{data.shipping_address}</p>
            </div>
          </div>
        </div>
      )}

      {/* 物流信息 */}
      {data.tracking_number && (
        <div className="mt-3 flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
          <Truck className="w-4 h-4" />
          <span>{data.carrier}</span>
          <span className="font-mono">{data.tracking_number}</span>
        </div>
      )}

      {/* 操作按钮 */}
      <ActionButtons actions={data.actions} onAction={onAction} onSendMessage={onSendMessage} />
    </WidgetCard>
  );
};

/**
 * 订单 Widget 定义
 */
export const orderWidgetDefinition: WidgetDefinition<OrderWidgetData> = {
  type: 'order',
  displayName: '订单卡片',
  description: '显示订单详情、商品列表、价格和状态',
  component: OrderWidgetComponent,
  icon: <Package className="w-4 h-4" />,
  toolbarColor: 'text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/30 hover:bg-blue-100 dark:hover:bg-blue-900/50',
};

export default OrderWidgetComponent;

