import React, { useCallback, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { generateDefaultAvatar, hasValidAvatar } from '@/utils/avatarUtils';
import { VISITOR_STATUS } from '@/constants';

export interface ChatAvatarProps {
  displayName: string;
  displayAvatar: string;
  visitorStatus?: 'online' | 'offline' | 'away';
  lastSeenMinutes?: number;
}

/**
 * Chat avatar with online indicator and recent "last seen" badge.
 * Memoized to avoid unnecessary re-renders in large chat lists.
 */
export const ChatAvatar: React.FC<ChatAvatarProps> = React.memo(({ displayName, displayAvatar, visitorStatus, lastSeenMinutes }) => {
  const { t } = useTranslation();
  const hasValidAvatarUrl = hasValidAvatar(displayAvatar);

  const defaultAvatar = useMemo(
    () => (!hasValidAvatarUrl ? generateDefaultAvatar(displayName) : null),
    [hasValidAvatarUrl, displayName]
  );

  const handleImageError = useCallback((e: React.SyntheticEvent<HTMLImageElement>) => {
    e.currentTarget.style.display = 'none';
    const defaultAvatarElement = e.currentTarget.nextElementSibling as HTMLElement;
    if (defaultAvatarElement) defaultAvatarElement.style.display = 'flex';
  }, []);

  return (
    <div className="relative mr-3 flex-shrink-0">
      {hasValidAvatarUrl ? (
        <img src={displayAvatar} alt={`${displayName} Avatar`} className="w-10 h-10 rounded-md object-cover bg-gray-200" onError={handleImageError} />
      ) : null}

      <div
        className={`w-10 h-10 rounded-md flex items-center justify-center text-white font-bold text-sm ${hasValidAvatarUrl ? 'hidden' : ''} ${defaultAvatar?.colorClass || 'bg-gradient-to-br from-gray-400 to-gray-500'}`}
        style={{ display: hasValidAvatarUrl ? 'none' : 'flex' }}
      >
        {defaultAvatar?.letter || '?'}
      </div>

      {visitorStatus === VISITOR_STATUS.ONLINE && (
        <div 
          className="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 bg-green-500 rounded-full border-1 border-white" 
          title={t('time.lastSeen.online', '在线')} 
        />
      )}

      {visitorStatus === VISITOR_STATUS.OFFLINE && lastSeenMinutes !== undefined && lastSeenMinutes <= 60 ? (
        <div
          className="absolute -bottom-0.5 -right-0.5 bg-white flex items-center justify-center rounded-[10px] p-0.5"
          title={lastSeenMinutes === 0 
            ? t('time.lastSeen.justNow', '刚刚在线')
            : t('time.lastSeen.minutesAgo', { mins: lastSeenMinutes, defaultValue: `${lastSeenMinutes}分钟前在线` })
          }
        >
          <div className="bg-[rgb(238,249,233)] rounded-[10px]">
            <div className="text-[6px] font-bold text-[rgb(124,208,83)]">
              {lastSeenMinutes === 0 
                ? t('time.lastSeen.justNowShort', '刚刚')
                : t('time.lastSeen.minutesShort', { mins: lastSeenMinutes, defaultValue: `${lastSeenMinutes}分钟` })
              }
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
});

ChatAvatar.displayName = 'ChatAvatar';

