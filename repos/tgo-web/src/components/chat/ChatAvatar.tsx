import React, { useCallback, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { generateDefaultAvatar, hasValidAvatar } from '@/utils/avatarUtils';
import { VISITOR_STATUS } from '@/constants';

export interface ChatAvatarProps {
  displayName: string;
  displayAvatar: string;
  visitorStatus?: 'online' | 'offline' | 'away';
  lastSeenMinutes?: number;
  /** Optional seed for consistent color generation (e.g., channel_id, visitor_id, staff_id) */
  colorSeed?: string;
  /** Avatar size in pixels (keeps existing size if omitted) */
  sizePx?: number;
  /** Wrapper class (overrides default spacing when needed) */
  wrapperClassName?: string;
  /** Additional class for the <img> element */
  imageClassName?: string;
  /** Additional class for the fallback avatar element */
  fallbackClassName?: string;
  /** Additional class for the letter in fallback avatar */
  letterClassName?: string;
  /** Optional overlay node rendered above avatar (e.g. upload icon/spinner) */
  overlay?: React.ReactNode;
  /** Optional click handler; when provided, avatar becomes accessible button */
  onClick?: () => void;
  /** Optional title (tooltip) */
  title?: string;
}

/**
 * Chat avatar with online indicator and recent "last seen" badge.
 * Memoized to avoid unnecessary re-renders in large chat lists.
 */
export const ChatAvatar: React.FC<ChatAvatarProps> = React.memo(({
  displayName,
  displayAvatar,
  visitorStatus,
  lastSeenMinutes,
  colorSeed,
  sizePx,
  wrapperClassName,
  imageClassName,
  fallbackClassName,
  letterClassName,
  overlay,
  onClick,
  title,
}) => {
  const { t } = useTranslation();
  const hasValidAvatarUrl = hasValidAvatar(displayAvatar);

  const defaultAvatar = useMemo(
    () => (!hasValidAvatarUrl ? generateDefaultAvatar(displayName, colorSeed) : null),
    [hasValidAvatarUrl, displayName, colorSeed]
  );

  const handleImageError = useCallback((e: React.SyntheticEvent<HTMLImageElement>) => {
    e.currentTarget.style.display = 'none';
    const defaultAvatarElement = e.currentTarget.nextElementSibling as HTMLElement;
    if (defaultAvatarElement) defaultAvatarElement.style.display = 'flex';
  }, []);

  const sizeStyle = useMemo<React.CSSProperties | undefined>(() => {
    if (!sizePx) return undefined;
    return { width: sizePx, height: sizePx };
  }, [sizePx]);

  const isClickable = typeof onClick === 'function';

  return (
    <div
      className={wrapperClassName ?? 'relative mr-3 flex-shrink-0'}
      onClick={isClickable ? onClick : undefined}
      title={title}
      role={isClickable ? 'button' : undefined}
      tabIndex={isClickable ? 0 : undefined}
      onKeyDown={
        isClickable
          ? (e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                onClick?.();
              }
            }
          : undefined
      }
    >
      {hasValidAvatarUrl ? (
        <img
          src={displayAvatar}
          alt={`${displayName} Avatar`}
          className={`rounded-md object-cover bg-gray-200 ${!sizePx ? 'w-10 h-10' : ''} ${imageClassName ?? ''}`}
          style={sizeStyle}
          onError={handleImageError}
        />
      ) : null}

      <div
        className={`${!sizePx ? 'w-10 h-10' : ''} rounded-md flex items-center justify-center text-white font-bold ${letterClassName ?? 'text-sm'} ${hasValidAvatarUrl ? 'hidden' : ''} ${defaultAvatar?.colorClass || 'bg-gradient-to-br from-gray-400 to-gray-500'} ${fallbackClassName ?? ''}`}
        style={{ ...(sizeStyle ?? {}), display: hasValidAvatarUrl ? 'none' : 'flex' }}
      >
        <span className={letterClassName ?? 'text-sm'}>{defaultAvatar?.letter || '?'}</span>
      </div>

      {overlay}

      {visitorStatus === VISITOR_STATUS.ONLINE && (
        <div 
          className="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 bg-green-500 rounded-full border border-white" 
          title={t('time.lastSeen.online', '在线')} 
        />
      )}
      {visitorStatus === VISITOR_STATUS.OFFLINE && lastSeenMinutes !== undefined && lastSeenMinutes <= 60 && (
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
      )}
    </div>
  );
});

ChatAvatar.displayName = 'ChatAvatar';

