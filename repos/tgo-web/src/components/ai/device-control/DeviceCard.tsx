/**
 * DeviceCard Component
 * Displays a single device with its status and actions
 */

import React from 'react';
import { useTranslation } from 'react-i18next';
import {
  Monitor,
  Smartphone,
  MoreVertical,
  Power,
  Pencil,
  Trash2,
  Wifi,
  WifiOff,
} from 'lucide-react';
import type { Device } from '@/types/deviceControl';

interface DeviceCardProps {
  device: Device;
  onEdit: (device: Device) => void;
  onDelete: (device: Device) => void;
  onDisconnect: (device: Device) => void;
}

const DeviceCard: React.FC<DeviceCardProps> = ({
  device,
  onEdit,
  onDelete,
  onDisconnect,
}) => {
  const { t } = useTranslation();
  const [showMenu, setShowMenu] = React.useState(false);
  const menuRef = React.useRef<HTMLDivElement>(null);

  // Close menu when clicking outside
  React.useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setShowMenu(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const isOnline = device.status === 'online';
  const DeviceIcon = device.device_type === 'mobile' ? Smartphone : Monitor;

  // Format last seen time
  const formatLastSeen = (dateString?: string) => {
    if (!dateString) return t('deviceControl.device.neverConnected', '从未连接');
    const date = new Date(dateString);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);

    if (minutes < 1) return t('deviceControl.device.justNow', '刚刚');
    if (minutes < 60) return t('deviceControl.device.minutesAgo', '{{count}} 分钟前', { count: minutes });
    if (hours < 24) return t('deviceControl.device.hoursAgo', '{{count}} 小时前', { count: hours });
    return t('deviceControl.device.daysAgo', '{{count}} 天前', { count: days });
  };

  // Get OS icon/text
  const getOSDisplay = () => {
    const os = device.os.toLowerCase();
    if (os.includes('darwin') || os.includes('mac')) return 'macOS';
    if (os.includes('windows')) return 'Windows';
    if (os.includes('linux')) return 'Linux';
    if (os.includes('android')) return 'Android';
    if (os.includes('ios')) return 'iOS';
    return device.os;
  };

  return (
    <div className="bg-white dark:bg-gray-800 rounded-2xl border border-gray-200 dark:border-gray-700 p-5 hover:shadow-lg hover:-translate-y-1 transition-all duration-300">
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div
            className={`p-3 rounded-xl ${
              isOnline
                ? 'bg-green-100 dark:bg-green-900/30'
                : 'bg-gray-100 dark:bg-gray-700'
            }`}
          >
            <DeviceIcon
              className={`w-6 h-6 ${
                isOnline
                  ? 'text-green-600 dark:text-green-400'
                  : 'text-gray-400 dark:text-gray-500'
              }`}
            />
          </div>
          <div>
            <h3 className="font-semibold text-gray-900 dark:text-gray-100">
              {device.device_name}
            </h3>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              {getOSDisplay()} {device.os_version && `(${device.os_version})`}
            </p>
          </div>
        </div>

        {/* Menu */}
        <div className="relative" ref={menuRef}>
          <button
            onClick={() => setShowMenu(!showMenu)}
            className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
          >
            <MoreVertical className="w-4 h-4 text-gray-500" />
          </button>

          {showMenu && (
            <div className="absolute right-0 mt-1 w-40 bg-white dark:bg-gray-800 rounded-xl shadow-lg border border-gray-200 dark:border-gray-700 py-1 z-10">
              <button
                onClick={() => {
                  onEdit(device);
                  setShowMenu(false);
                }}
                className="w-full px-4 py-2 text-left text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center gap-2"
              >
                <Pencil className="w-4 h-4" />
                {t('common.edit', '编辑')}
              </button>
              {isOnline && (
                <button
                  onClick={() => {
                    onDisconnect(device);
                    setShowMenu(false);
                  }}
                  className="w-full px-4 py-2 text-left text-sm text-orange-600 dark:text-orange-400 hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center gap-2"
                >
                  <Power className="w-4 h-4" />
                  {t('deviceControl.device.disconnect', '断开连接')}
                </button>
              )}
              <button
                onClick={() => {
                  onDelete(device);
                  setShowMenu(false);
                }}
                className="w-full px-4 py-2 text-left text-sm text-red-600 dark:text-red-400 hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center gap-2"
              >
                <Trash2 className="w-4 h-4" />
                {t('common.delete', '删除')}
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Status */}
      <div className="flex items-center gap-2 mb-3">
        {isOnline ? (
          <>
            <Wifi className="w-4 h-4 text-green-500" />
            <span className="text-sm font-medium text-green-600 dark:text-green-400">
              {t('deviceControl.device.online', '在线')}
            </span>
          </>
        ) : (
          <>
            <WifiOff className="w-4 h-4 text-gray-400" />
            <span className="text-sm text-gray-500 dark:text-gray-400">
              {t('deviceControl.device.offline', '离线')}
            </span>
          </>
        )}
      </div>

      {/* Info */}
      <div className="space-y-2 text-sm text-gray-500 dark:text-gray-400">
        {device.screen_resolution && (
          <div className="flex items-center justify-between">
            <span>{t('deviceControl.device.resolution', '分辨率')}</span>
            <span className="font-medium text-gray-700 dark:text-gray-300">
              {device.screen_resolution}
            </span>
          </div>
        )}
        <div className="flex items-center justify-between">
          <span>{t('deviceControl.device.lastSeen', '最后在线')}</span>
          <span className="font-medium text-gray-700 dark:text-gray-300">
            {isOnline ? t('deviceControl.device.now', '现在') : formatLastSeen(device.last_seen_at)}
          </span>
        </div>
      </div>
    </div>
  );
};

export default DeviceCard;
