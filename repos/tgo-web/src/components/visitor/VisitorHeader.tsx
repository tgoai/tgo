import React from 'react';
import { Camera } from 'lucide-react';
import { PlatformType } from '@/types';
import { getPlatformIconComponent, getPlatformLabel, getPlatformColor } from '@/utils/platformUtils';
import { useTranslation } from 'react-i18next';
import { ChatAvatar } from '@/components/chat/ChatAvatar';

interface VisitorHeaderProps {
  name: string;
  status: 'online' | 'away' | 'offline';
  avatar: string;
  platformType?: PlatformType;
  lastSeenText?: string;
  className?: string;
  /** Callback when avatar is clicked for upload */
  onAvatarClick?: () => void;
  /** Whether avatar upload is in progress */
  isUploading?: boolean;
  /** Visitor ID for consistent avatar color */
  visitorId?: string;
}

/**
 * 访客头部信息组件
 */
const VisitorHeader: React.FC<VisitorHeaderProps> = ({
  name,
  status,
  avatar,
  platformType,
  lastSeenText,
  className = '',
  onAvatarClick,
  isUploading = false,
  visitorId
}) => {
  const { t } = useTranslation();
  const getStatusText = (status: string) => {
    switch (status) {
      case 'online': return t('chat.status.online', '在线');
      default: return undefined;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'online': return 'text-green-600 dark:text-green-400';
      case 'away': return 'text-yellow-600 dark:text-yellow-400';
      case 'offline': return 'text-gray-500 dark:text-gray-400';
      default: return 'text-gray-500 dark:text-gray-400';
    }
  };

  return (
    <div className={`flex items-center ${className}`}>
      <ChatAvatar
        displayName={name}
        displayAvatar={avatar}
        colorSeed={visitorId}
        sizePx={48} // keep existing 12x12 size
        letterClassName="text-base"
        wrapperClassName={`relative mr-3 ${onAvatarClick ? 'group cursor-pointer' : ''}`}
        imageClassName={onAvatarClick ? 'group-hover:opacity-75 transition-opacity' : undefined}
        fallbackClassName={onAvatarClick ? 'group-hover:opacity-75 transition-opacity' : undefined}
        onClick={onAvatarClick}
        title={onAvatarClick ? t('chat.visitor.avatar.uploadTitle', '点击上传头像') : undefined}
        overlay={
          onAvatarClick ? (
            isUploading ? (
              <div className="absolute inset-0 flex items-center justify-center bg-black/50 rounded-md">
                <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
              </div>
            ) : (
              <div className="absolute inset-0 flex items-center justify-center bg-black/40 rounded-md opacity-0 group-hover:opacity-100 transition-opacity">
                <Camera className="w-5 h-5 text-white" />
              </div>
            )
          ) : null
        }
      />
      <div className="flex-grow">
        <h3 className="text-base font-semibold text-gray-900 dark:text-gray-100 leading-5 truncate" title={name}>
          {name}
          {(() => {
            const type = platformType ?? PlatformType.WEBSITE;
            const IconComp = getPlatformIconComponent(type);
            const label = getPlatformLabel(type);
            return (
              <span title={label}>
                <IconComp size={14} className={`w-3.5 h-3.5 inline-block ml-1 -mt-0.5 ${getPlatformColor(type)}`} />
              </span>
            );
          })()}
        </h3>
        <p className={`text-xs leading-4 mt-0.5 ${getStatusColor(status)}`}>
          {lastSeenText ?? getStatusText(status)}
        </p>
      </div>
    </div>
  );
};

export default VisitorHeader;
