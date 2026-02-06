import React from 'react';
import { Plus, Monitor, Smartphone, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { Device } from '@/types/deviceControl';

interface AgentDeviceSectionProps {
  device: Device | null;
  disabled?: boolean;
  onAdd: () => void;
  onRemove: () => void;
}

const AgentDeviceSection: React.FC<AgentDeviceSectionProps> = ({
  device,
  disabled = false,
  onAdd,
  onRemove,
}) => {
  const { t } = useTranslation();

  return (
    <>
      <div className="flex items-center justify-between mb-4 gap-3">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-sm font-medium text-gray-700 truncate">
            {t('agents.deviceSection.title', '绑定设备')}
          </span>
          {device && (
            <span className="px-2 py-1 text-xs font-medium bg-purple-100 text-purple-800 rounded-full whitespace-nowrap">
              {t('agents.deviceSection.boundCount', '1 已绑定')}
            </span>
          )}
        </div>
        <button
          type="button"
          onClick={onAdd}
          className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-purple-700 bg-purple-100 hover:bg-purple-200 rounded-lg transition-colors shrink-0"
          disabled={disabled}
        >
          <Plus className="w-4 h-4" />
          <span>{t('agents.deviceSection.addButton', '选择设备')}</span>
        </button>
      </div>

      {device ? (
        <div className="flex items-center justify-between p-3 rounded-md border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800">
          <div className="flex items-center space-x-3">
            {device.device_type === 'mobile' ? (
              <Smartphone className="w-5 h-5 text-purple-500 flex-shrink-0" />
            ) : (
              <Monitor className="w-5 h-5 text-purple-500 flex-shrink-0" />
            )}
            <div>
              <div className="text-sm font-medium text-gray-800 dark:text-gray-100">
                {device.device_name}
              </div>
              <div className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                {device.os}
                {device.os_version ? ` ${device.os_version}` : ''}
                {device.screen_resolution ? ` · ${device.screen_resolution}` : ''}
              </div>
            </div>
          </div>
          <div className="flex items-center space-x-3">
            <span
              className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                device.status === 'online'
                  ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                  : 'bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400'
              }`}
            >
              <span
                className={`w-1.5 h-1.5 rounded-full mr-1 ${
                  device.status === 'online' ? 'bg-green-500' : 'bg-gray-400'
                }`}
              />
              {device.status === 'online'
                ? t('agents.deviceSelectModal.statusOnline', '在线')
                : t('agents.deviceSelectModal.statusOffline', '离线')}
            </span>
            <button
              type="button"
              onClick={onRemove}
              disabled={disabled}
              className="p-1 text-gray-400 hover:text-red-500 dark:text-gray-500 dark:hover:text-red-400 transition-colors disabled:opacity-50"
              title={t('agents.deviceSection.unbind', '解绑设备')}
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>
      ) : (
        <div className="text-center py-8 text-gray-500">
          <Monitor className="w-12 h-12 mx-auto mb-3 opacity-30" />
          <p className="text-sm font-medium">
            {t('agents.deviceSection.emptyTitle', '暂未绑定设备')}
          </p>
          <p className="text-xs mt-1">
            {t('agents.deviceSection.emptyDescription', '点击「选择设备」按钮绑定一个远程设备')}
          </p>
        </div>
      )}
    </>
  );
};

export default AgentDeviceSection;
