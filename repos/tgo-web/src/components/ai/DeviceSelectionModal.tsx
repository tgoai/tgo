/**
 * Device Selection Modal
 * Modal for selecting devices to bind to a Computer Use agent
 */

import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { LuMonitor, LuSmartphone, LuCheck, LuX, LuLoader, LuWifi, LuWifiOff } from 'react-icons/lu';
import { useDeviceControlStore } from '@/stores/deviceControlStore';
import type { Device } from '@/types/deviceControl';
import Button from '@/components/ui/Button';

interface DeviceSelectionModalProps {
  isOpen: boolean;
  onClose: () => void;
  selectedDeviceId: string | null;
  onConfirm: (deviceId: string) => void;
}

export function DeviceSelectionModal({
  isOpen,
  onClose,
  selectedDeviceId: initialSelectedDeviceId,
  onConfirm,
}: DeviceSelectionModalProps) {
  const { t } = useTranslation();
  const { devices, isLoading, error, loadDevices, clearError } = useDeviceControlStore();
  
  const [selectedId, setSelectedId] = useState<string | null>(initialSelectedDeviceId);

  // Load devices when modal opens
  useEffect(() => {
    if (isOpen) {
      loadDevices();
      setSelectedId(initialSelectedDeviceId);
    }
  }, [isOpen, loadDevices, initialSelectedDeviceId]);

  // Toggle device selection
  const toggleDevice = (deviceId: string, device: Device) => {
    // Only allow selecting online devices
    if (device.status !== 'online') {
      return;
    }

    setSelectedId((prev) => (prev === deviceId ? null : deviceId));
  };

  // Handle confirm
  const handleConfirm = () => {
    if (selectedId) {
      onConfirm(selectedId);
      onClose();
    }
  };

  // Get device icon
  const getDeviceIcon = (deviceType: string) => {
    switch (deviceType) {
      case 'mobile':
        return <LuSmartphone className="w-5 h-5" />;
      default:
        return <LuMonitor className="w-5 h-5" />;
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />
      
      {/* Modal */}
      <div className="relative bg-white dark:bg-gray-800 rounded-xl shadow-2xl w-full max-w-lg mx-4 max-h-[80vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
            {t('agents.deviceSelection.title', '选择设备')}
          </h3>
          <button
            onClick={onClose}
            className="p-1 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
          >
            <LuX className="w-5 h-5 text-gray-500" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4">
          {/* Error message */}
          {error && (
            <div className="mb-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
              <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
              <button
                onClick={clearError}
                className="mt-1 text-xs text-red-500 hover:text-red-700 underline"
              >
                {t('common.dismiss', '关闭')}
              </button>
            </div>
          )}

          {/* Loading state */}
          {isLoading && (
            <div className="flex items-center justify-center py-12">
              <LuLoader className="w-8 h-8 text-primary animate-spin" />
            </div>
          )}

          {/* Empty state */}
          {!isLoading && devices.length === 0 && (
            <div className="text-center py-12">
              <LuMonitor className="w-12 h-12 text-gray-400 mx-auto mb-3" />
              <p className="text-gray-500 dark:text-gray-400">
                {t('agents.deviceSelection.noDevices', '暂无可用设备')}
              </p>
              <p className="text-sm text-gray-400 dark:text-gray-500 mt-1">
                {t('agents.deviceSelection.noDevicesHint', '请先在设备管理中添加设备')}
              </p>
            </div>
          )}

          {/* Device list */}
          {!isLoading && devices.length > 0 && (
            <div className="space-y-2">
              <p className="text-sm text-gray-500 dark:text-gray-400 mb-3">
                {t('agents.deviceSelection.selectHint', '选择要绑定到此AI员工的设备（仅支持在线设备）')}
              </p>
              
              {devices.map((device) => {
                const isSelected = selectedId === device.id;
                const isOnline = device.status === 'online';
                
                return (
                  <div
                    key={device.id}
                    onClick={() => toggleDevice(device.id, device)}
                    className={`
                      flex items-center p-3 rounded-lg border transition-all
                      ${isOnline ? 'cursor-pointer' : 'cursor-not-allowed opacity-60'}
                      ${isSelected
                        ? 'border-primary bg-primary/5 dark:bg-primary/10'
                        : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
                      }
                    `}
                  >
                    {/* Selection indicator */}
                    <div
                      className={`
                        w-5 h-5 rounded-md border-2 flex items-center justify-center mr-3 flex-shrink-0
                        ${isSelected
                          ? 'border-primary bg-primary text-white'
                          : 'border-gray-300 dark:border-gray-600'
                        }
                      `}
                    >
                      {isSelected && <LuCheck className="w-3 h-3" />}
                    </div>

                    {/* Device icon */}
                    <div className="flex-shrink-0 mr-3 text-gray-500 dark:text-gray-400">
                      {getDeviceIcon(device.device_type)}
                    </div>

                    {/* Device info */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="font-medium text-gray-900 dark:text-white truncate">
                          {device.device_name}
                        </p>
                        {/* Status badge */}
                        <span
                          className={`
                            inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs
                            ${isOnline
                              ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400'
                              : 'bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400'
                            }
                          `}
                        >
                          {isOnline ? (
                            <>
                              <LuWifi className="w-3 h-3" />
                              {t('devices.status.online', '在线')}
                            </>
                          ) : (
                            <>
                              <LuWifiOff className="w-3 h-3" />
                              {t('devices.status.offline', '离线')}
                            </>
                          )}
                        </span>
                      </div>
                      <p className="text-sm text-gray-500 dark:text-gray-400 truncate">
                        {device.os} {device.os_version}
                        {device.screen_resolution && ` • ${device.screen_resolution}`}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between p-4 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 rounded-b-xl">
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {selectedId ? t('agents.deviceSelection.selected', '已选择 1 个设备') : t('agents.deviceSelection.noneSelected', '未选择设备')}
          </p>
          <div className="flex gap-2">
            <Button variant="secondary" onClick={onClose}>
              {t('common.cancel', '取消')}
            </Button>
            <Button
              onClick={handleConfirm}
              disabled={!selectedId}
            >
              {t('common.confirm', '确认')}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default DeviceSelectionModal;
