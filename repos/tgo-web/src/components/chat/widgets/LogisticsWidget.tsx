/**
 * 物流 Widget 组件
 */

import React from 'react';
import { Truck, Phone, MapPin, Clock } from 'lucide-react';
import type { WidgetDefinition, WidgetComponentProps, LogisticsWidgetData, LogisticsStatus } from './types';
import { WidgetCard, WidgetHeader, StatusBadge, ActionButtons } from './shared';

/**
 * 物流状态配色映射
 */
const logisticsStatusConfig: Record<LogisticsStatus, { bgColor: string }> = {
  pending: { bgColor: 'bg-gray-400' },
  picked_up: { bgColor: 'bg-blue-500' },
  in_transit: { bgColor: 'bg-purple-500' },
  out_for_delivery: { bgColor: 'bg-orange-500' },
  delivered: { bgColor: 'bg-green-500' },
  exception: { bgColor: 'bg-red-500' },
  returned: { bgColor: 'bg-gray-500' },
};

/**
 * 物流 Widget 组件
 */
const LogisticsWidgetComponent: React.FC<WidgetComponentProps<LogisticsWidgetData>> = ({ data, onAction, onSendMessage }) => {
  if (!data) return null;

  return (
    <WidgetCard>
      {/* 头部 */}
      <WidgetHeader
        icon={
          data.carrier_logo ? (
            <img src={data.carrier_logo} alt={data.carrier} className="w-5 h-5 rounded" />
          ) : (
            <Truck className="w-5 h-5 text-purple-600 dark:text-purple-400" />
          )
        }
        iconBgColor="bg-purple-50 dark:bg-purple-900/30"
        title={data.carrier}
        subtitle={<span className="font-mono">{data.tracking_number}</span>}
        badge={
          <StatusBadge>
            {data.status_text || data.status}
          </StatusBadge>
        }
      />

      {/* 预计送达 */}
      {data.estimated_delivery && (
        <div className="flex items-center gap-2 text-sm text-green-600 dark:text-green-400 mb-4 p-2 bg-green-50 dark:bg-green-900/20 rounded-lg">
          <Clock className="w-4 h-4" />
          <span>预计送达: {data.estimated_delivery}</span>
        </div>
      )}

      {/* 配送员信息 */}
      {data.courier_name && (
        <div className="p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg mb-4">
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-600 dark:text-gray-400">
              配送员: <span className="font-medium text-gray-900 dark:text-gray-100">{data.courier_name}</span>
            </span>
            {data.courier_phone && (
              <a
                href={`tel:${data.courier_phone}`}
                className="inline-flex items-center gap-1 text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300"
              >
                <Phone className="w-4 h-4" />
                <span className="text-sm">{data.courier_phone}</span>
              </a>
            )}
          </div>
        </div>
      )}

      {/* 时间线 */}
      {data.timeline && data.timeline.length > 0 && (
        <div className="space-y-0">
          {data.timeline.map((event, index) => {
            const eventStatusStyle = event.status
              ? logisticsStatusConfig[event.status]
              : (index === 0 ? { bgColor: 'bg-blue-500' } : { bgColor: 'bg-gray-300 dark:bg-gray-600' });

            return (
              <div key={index} className="flex gap-3">
                <div className="flex flex-col items-center">
                  <div className={`w-3 h-3 rounded-full ${eventStatusStyle.bgColor} ring-4 ring-white dark:ring-gray-800`} />
                  {index < data.timeline.length - 1 && (
                    <div className="w-0.5 flex-1 bg-gray-200 dark:bg-gray-700 my-1 min-h-[24px]" />
                  )}
                </div>
                <div className="flex-1 pb-4">
                  <p className="text-xs text-gray-500 dark:text-gray-400">{event.time}</p>
                  <p className={`text-sm ${index === 0 ? 'font-medium text-gray-900 dark:text-gray-100' : 'text-gray-700 dark:text-gray-300'}`}>
                    {event.description}
                  </p>
                  {event.location && (
                    <p className="text-xs text-gray-500 dark:text-gray-400 flex items-center gap-1 mt-0.5">
                      <MapPin className="w-3 h-3" />
                      {event.location}
                    </p>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* 操作按钮 */}
      <ActionButtons actions={data.actions} onAction={onAction} onSendMessage={onSendMessage} />
    </WidgetCard>
  );
};

/**
 * 物流 Widget 定义
 */
export const logisticsWidgetDefinition: WidgetDefinition<LogisticsWidgetData> = {
  type: 'logistics',
  displayName: '物流追踪',
  description: '显示物流状态和时间线',
  component: LogisticsWidgetComponent,
  icon: <Truck className="w-4 h-4" />,
  toolbarColor: 'text-purple-600 dark:text-purple-400 bg-purple-50 dark:bg-purple-900/30 hover:bg-purple-100 dark:hover:bg-purple-900/50',
};

export default LogisticsWidgetComponent;

