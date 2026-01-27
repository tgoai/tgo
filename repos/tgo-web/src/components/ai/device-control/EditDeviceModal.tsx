/**
 * EditDeviceModal Component
 * Modal for editing device name
 */

import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { X, Monitor, Smartphone, Save } from 'lucide-react';
import type { Device } from '@/types/deviceControl';
import { useDeviceControlStore } from '@/stores/deviceControlStore';

interface EditDeviceModalProps {
  isOpen: boolean;
  device: Device | null;
  onClose: () => void;
}

const EditDeviceModal: React.FC<EditDeviceModalProps> = ({
  isOpen,
  device,
  onClose,
}) => {
  const { t } = useTranslation();
  const [deviceName, setDeviceName] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { updateDevice } = useDeviceControlStore();

  // Initialize form when device changes
  useEffect(() => {
    if (device) {
      setDeviceName(device.device_name);
      setError(null);
    }
  }, [device]);

  // Handle save
  const handleSave = async () => {
    if (!device || !deviceName.trim()) {
      setError(t('deviceControl.edit.nameRequired', '请输入设备名称'));
      return;
    }

    setIsSaving(true);
    setError(null);

    try {
      await updateDevice(device.id, deviceName.trim());
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : t('common.error', '操作失败'));
    } finally {
      setIsSaving(false);
    }
  };

  // Handle close
  const handleClose = () => {
    setDeviceName('');
    setError(null);
    onClose();
  };

  if (!isOpen || !device) return null;

  const DeviceIcon = device.device_type === 'mobile' ? Smartphone : Monitor;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-gray-800 rounded-3xl w-full max-w-md shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-100 dark:bg-blue-900/30 rounded-xl">
              <DeviceIcon className="w-5 h-5 text-blue-600 dark:text-blue-400" />
            </div>
            <h2 className="text-lg font-bold text-gray-900 dark:text-gray-100">
              {t('deviceControl.edit.title', '编辑设备')}
            </h2>
          </div>
          <button
            onClick={handleClose}
            className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-xl transition-colors"
          >
            <X className="w-5 h-5 text-gray-500" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-4">
          {/* Device Name */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              {t('deviceControl.edit.deviceName', '设备名称')}
            </label>
            <input
              type="text"
              value={deviceName}
              onChange={(e) => setDeviceName(e.target.value)}
              placeholder={t('deviceControl.edit.deviceNamePlaceholder', '输入设备名称')}
              className="w-full px-4 py-3 bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-xl focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none transition-all"
            />
          </div>

          {/* Device Info (read-only) */}
          <div className="bg-gray-50 dark:bg-gray-900 rounded-xl p-4 space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-500 dark:text-gray-400">
                {t('deviceControl.edit.os', '操作系统')}
              </span>
              <span className="font-medium text-gray-700 dark:text-gray-300">
                {device.os} {device.os_version && `(${device.os_version})`}
              </span>
            </div>
            {device.screen_resolution && (
              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-500 dark:text-gray-400">
                  {t('deviceControl.edit.resolution', '屏幕分辨率')}
                </span>
                <span className="font-medium text-gray-700 dark:text-gray-300">
                  {device.screen_resolution}
                </span>
              </div>
            )}
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-500 dark:text-gray-400">
                {t('deviceControl.edit.status', '状态')}
              </span>
              <span
                className={`font-medium ${
                  device.status === 'online'
                    ? 'text-green-600 dark:text-green-400'
                    : 'text-gray-500 dark:text-gray-400'
                }`}
              >
                {device.status === 'online'
                  ? t('deviceControl.device.online', '在线')
                  : t('deviceControl.device.offline', '离线')}
              </span>
            </div>
          </div>

          {/* Error */}
          {error && (
            <div className="p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl text-sm text-red-600 dark:text-red-400">
              {error}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 p-6 border-t border-gray-200 dark:border-gray-700">
          <button
            onClick={handleClose}
            className="px-4 py-2 text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-xl font-medium transition-colors"
          >
            {t('common.cancel', '取消')}
          </button>
          <button
            onClick={handleSave}
            disabled={isSaving || !deviceName.trim()}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 dark:disabled:bg-gray-600 text-white rounded-xl font-medium transition-colors"
          >
            <Save className="w-4 h-4" />
            {isSaving ? t('common.saving', '保存中...') : t('common.save', '保存')}
          </button>
        </div>
      </div>
    </div>
  );
};

export default EditDeviceModal;
