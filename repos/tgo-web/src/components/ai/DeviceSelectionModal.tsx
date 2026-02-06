import React, { useState, useMemo, useEffect } from 'react';
import { X, Search, ExternalLink, Monitor, RefreshCw, Smartphone } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import { useDebouncedValue } from '@/hooks/useDebouncedValue';
import { useDeviceControlStore } from '@/stores/deviceControlStore';
import { useToast } from '@/hooks/useToast';
import type { Device } from '@/types/deviceControl';

interface DeviceSelectionModalProps {
  isOpen: boolean;
  onClose: () => void;
  selectedDeviceId: string | null;
  onConfirm: (deviceId: string | null) => void;
}

/**
 * Device Selection Modal Component (single-select)
 * Allows users to browse and select a device to bind with an agent
 */
const DeviceSelectionModal: React.FC<DeviceSelectionModalProps> = ({
  isOpen,
  onClose,
  selectedDeviceId,
  onConfirm,
}) => {
  const navigate = useNavigate();
  const { devices, isLoading, error, loadDevices } = useDeviceControlStore();
  const { showToast } = useToast();
  const [searchQuery, setSearchQuery] = useState('');
  const debouncedSearch = useDebouncedValue(searchQuery, 300);
  const [tempSelectedDeviceId, setTempSelectedDeviceId] = useState<string | null>(null);
  const { t } = useTranslation();

  // Load devices when modal opens
  useEffect(() => {
    if (isOpen) {
      loadDevices().catch((err) => {
        console.error('Failed to load devices:', err);
        showToast('error', t('common.loadFailed', '加载失败'), t('agents.deviceSelectModal.loadFailedDesc', '无法加载设备列表，请稍后重试'));
      });
    }
  }, [isOpen, loadDevices, showToast, t]);

  // Initialize temporary selection state when modal opens
  useEffect(() => {
    if (isOpen) {
      setTempSelectedDeviceId(selectedDeviceId);
    }
  }, [isOpen, selectedDeviceId]);

  // Filter devices based on search
  const filteredDevices = useMemo(() => {
    if (!debouncedSearch.trim()) return devices;
    const query = debouncedSearch.toLowerCase();
    return devices.filter(
      (device) =>
        device.device_name.toLowerCase().includes(query) ||
        device.os.toLowerCase().includes(query) ||
        device.device_type.toLowerCase().includes(query),
    );
  }, [devices, debouncedSearch]);

  const handleDeviceClick = (device: Device) => {
    // Toggle: click again to deselect
    setTempSelectedDeviceId((prev) => (prev === device.id ? null : device.id));
  };

  const handleConfirm = () => {
    onConfirm(tempSelectedDeviceId);
    onClose();
  };

  const handleCancel = () => {
    setTempSelectedDeviceId(selectedDeviceId);
    onClose();
  };

  const handleRetry = () => {
    loadDevices().catch((err) => {
      console.error('Failed to retry loading devices:', err);
      showToast('error', t('common.retryFailed', '重试失败'), t('agents.deviceSelectModal.retryFailedDesc', '无法加载设备列表，请检查网络连接'));
    });
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-2xl max-h-[90vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700 flex-shrink-0">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
            {t('agents.deviceSelectModal.title', '选择设备')}
          </h3>
          <button
            onClick={onClose}
            className="text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Search Bar */}
        <div className="p-4 border-b border-gray-200 dark:border-gray-700 flex-shrink-0">
          <div className="relative">
            <Search className="w-4 h-4 absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 dark:text-gray-500" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder={t('agents.deviceSelectModal.searchPlaceholder', '搜索设备...')}
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100 dark:placeholder-gray-400"
            />
          </div>
        </div>

        {/* Summary */}
        <div className="px-4 py-2 border-b border-gray-200 dark:border-gray-700 flex-shrink-0">
          <div className="flex items-center justify-between text-xs text-gray-600 dark:text-gray-300">
            <span>
              {t('agents.deviceSelectModal.totalDevices', '共 {{count}} 台设备', { count: devices.length })}
            </span>
            <span>
              {tempSelectedDeviceId
                ? t('agents.deviceSelectModal.selectedOne', '已选择 1 台')
                : t('agents.deviceSelectModal.selectedNone', '未选择')}
            </span>
          </div>
        </div>

        {/* Device List - Scrollable */}
        <div className="flex-1 overflow-y-auto min-h-0 dark:bg-gray-900">
          <div className="p-4">
            {/* Loading State */}
            {isLoading && (
              <div className="flex items-center justify-center py-8">
                <div className="text-center">
                  <RefreshCw className="w-6 h-6 animate-spin text-gray-400 dark:text-gray-500 mx-auto mb-2" />
                  <p className="text-gray-500 dark:text-gray-400 text-sm">
                    {t('agents.deviceSelectModal.loading', '正在加载设备...')}
                  </p>
                </div>
              </div>
            )}

            {/* Error State */}
            {error && !isLoading && (
              <div className="flex items-center justify-center py-8">
                <div className="text-center">
                  <div className="w-12 h-12 bg-red-100 dark:bg-red-900/30 rounded-full flex items-center justify-center mx-auto mb-3">
                    <X className="w-6 h-6 text-red-600 dark:text-red-400" />
                  </div>
                  <h3 className="text-sm font-medium text-gray-900 dark:text-gray-100 mb-1">
                    {t('common.loadFailed', '加载失败')}
                  </h3>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mb-3">{error}</p>
                  <button
                    onClick={handleRetry}
                    className="px-3 py-1.5 bg-blue-500 dark:bg-blue-600 text-white text-xs rounded hover:bg-blue-600 dark:hover:bg-blue-700 transition-colors"
                  >
                    {t('common.retry', '重试')}
                  </button>
                </div>
              </div>
            )}

            {/* Device List */}
            {!isLoading && !error && (
              <div className="space-y-2">
                {filteredDevices.length === 0 ? (
                  <div className="text-center py-8 text-gray-500 dark:text-gray-400">
                    <Monitor className="w-8 h-8 mx-auto mb-2 opacity-50" />
                    <p>{t('agents.deviceSelectModal.noDevices', '暂无可用设备')}</p>
                  </div>
                ) : (
                  filteredDevices.map((device) => {
                    const isSelected = tempSelectedDeviceId === device.id;
                    const isOnline = device.status === 'online';
                    const DeviceIcon = device.device_type === 'mobile' ? Smartphone : Monitor;

                    return (
                      <div
                        key={device.id}
                        onClick={() => handleDeviceClick(device)}
                        className={`flex items-center justify-between p-3 rounded-md border cursor-pointer transition-colors ${
                          isSelected
                            ? 'bg-blue-50 border-blue-200 hover:bg-blue-100 dark:bg-blue-900/30 dark:border-blue-700 dark:hover:bg-blue-900/50'
                            : 'bg-white border-gray-200 hover:bg-gray-50 dark:bg-gray-800 dark:border-gray-700 dark:hover:bg-gray-700'
                        }`}
                      >
                        <div className="flex items-center space-x-3">
                          <DeviceIcon
                            className={`w-5 h-5 flex-shrink-0 ${
                              isSelected ? 'text-blue-600 dark:text-blue-400' : 'text-gray-400 dark:text-gray-500'
                            }`}
                          />
                          <div>
                            <div
                              className={`text-sm font-medium ${
                                isSelected ? 'text-blue-900 dark:text-blue-300' : 'text-gray-800 dark:text-gray-100'
                              }`}
                            >
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
                              isOnline
                                ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                                : 'bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400'
                            }`}
                          >
                            <span
                              className={`w-1.5 h-1.5 rounded-full mr-1 ${
                                isOnline ? 'bg-green-500' : 'bg-gray-400'
                              }`}
                            />
                            {isOnline
                              ? t('agents.deviceSelectModal.statusOnline', '在线')
                              : t('agents.deviceSelectModal.statusOffline', '离线')}
                          </span>
                          <input
                            type="radio"
                            checked={isSelected}
                            onChange={() => handleDeviceClick(device)}
                            className="text-blue-600 dark:text-blue-500 focus:ring-blue-500 dark:bg-gray-700"
                          />
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            )}
          </div>
        </div>

        {/* Device Management Link */}
        <div className="p-4 border-t border-gray-200 dark:border-gray-700 flex-shrink-0">
          <button
            className="flex items-center space-x-2 text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 text-sm"
            onClick={() => {
              navigate('/ai/device-control');
              onClose();
            }}
          >
            <span>{t('agents.deviceSelectModal.manageDevices', '管理设备')}</span>
            <ExternalLink className="w-4 h-4" />
          </button>
        </div>

        {/* Footer */}
        <div className="flex justify-end space-x-3 p-4 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900 flex-shrink-0">
          <button
            onClick={handleCancel}
            className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-200 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-md hover:bg-gray-50 dark:hover:bg-gray-600"
          >
            {t('common.cancel', '取消')}
          </button>
          <button
            onClick={handleConfirm}
            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 dark:bg-blue-700 border border-transparent rounded-md hover:bg-blue-700 dark:hover:bg-blue-800"
          >
            {t('agents.deviceSelectModal.confirmSelection', '确认选择')}
          </button>
        </div>
      </div>
    </div>
  );
};

export default DeviceSelectionModal;
