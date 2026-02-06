import React from 'react';
import { Monitor, Smartphone } from 'lucide-react';
import type { Device } from '@/types/deviceControl';

interface DeviceTagProps {
  device: Device;
  size?: 'xs' | 'sm' | 'md';
  showIcon?: boolean;
  className?: string;
}

const sizeClasses: Record<NonNullable<DeviceTagProps['size']>, string> = {
  xs: 'px-1.5 py-0.5 text-[11px]',
  sm: 'px-2 py-1 text-xs',
  md: 'px-3 py-1.5 text-sm',
};

const iconSize: Record<NonNullable<DeviceTagProps['size']>, string> = {
  xs: 'w-3 h-3',
  sm: 'w-3.5 h-3.5',
  md: 'w-4 h-4',
};

const statusDotSize: Record<NonNullable<DeviceTagProps['size']>, string> = {
  xs: 'w-1.5 h-1.5',
  sm: 'w-2 h-2',
  md: 'w-2 h-2',
};

/**
 * Device compact tag for displaying bound device on agent cards
 */
const DeviceTag: React.FC<DeviceTagProps> = ({
  device,
  size = 'xs',
  showIcon = true,
  className = '',
}) => {
  const isOnline = device.status === 'online';
  const DeviceIcon = device.device_type === 'mobile' ? Smartphone : Monitor;

  return (
    <span
      className={[
        'inline-flex items-center rounded-md border transition-colors duration-200',
        'bg-violet-50 text-violet-700 border-violet-200 hover:bg-violet-100',
        'dark:bg-violet-900/20 dark:text-violet-300 dark:border-violet-700 dark:hover:bg-violet-900/30',
        sizeClasses[size],
        className,
      ].join(' ')}
      title={`${device.device_name} (${device.os}${device.os_version ? ' ' + device.os_version : ''}) - ${isOnline ? 'Online' : 'Offline'}`}
    >
      {showIcon && (
        <DeviceIcon
          className={`${iconSize[size]} mr-1 text-violet-600 dark:text-violet-400 transition-colors duration-200 hover:opacity-80`}
        />
      )}
      <span className="font-medium truncate max-w-[80px]">{device.device_name}</span>
      <span
        className={`${statusDotSize[size]} rounded-full ml-1 flex-shrink-0 ${
          isOnline ? 'bg-green-500' : 'bg-gray-400'
        }`}
      />
    </span>
  );
};

export default DeviceTag;
