import React from 'react';
import AIInfoCard from './AIInfoCard';
import ReplySuggestions from './ReplySuggestions';

import type { Message } from '@/types';
import { MessagePayloadType } from '@/types';

import { useAuthStore } from '@/stores/authStore';

import { generateDefaultAvatar, hasValidAvatar } from '@/utils/avatarUtils';
import { useChannelStore, getChannelKey } from '@/stores/channelStore';
import { getPlatformIconComponent, getPlatformLabel, toPlatformType, getPlatformColor } from '@/utils/platformUtils';
import { PlatformType } from '@/types';
import { AlertCircle, Loader2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';










import TextMessage from './messages/TextMessage';
import ImageMessage from './messages/ImageMessage';
import FileMessage from './messages/FileMessage';
import RichTextMessage from './messages/RichTextMessage';



interface ChatMessageProps {
  message: Message;
  onSuggestionClick?: (suggestion: string) => void;
}

/**
 * Individual chat message component
 */
const ChatMessage: React.FC<ChatMessageProps> = ({ message, onSuggestionClick }) => {
  const { t } = useTranslation();

  const typedPayload = message.payload as any | undefined;
  const isRichText = (typedPayload?.type === MessagePayloadType.RICH_TEXT) || (message.payloadType === MessagePayloadType.RICH_TEXT) || Array.isArray(message.metadata?.images);


  // Current user uid to judge own message
  const user = useAuthStore(state => state.user);
  const currentUid = React.useMemo(() => (user?.id ? `${user.id}-staff` : null), [user?.id]);


  const fromUid = message.fromUid;
  const isSystemMessage = message.type === 'system';
  const isOwnMessage = currentUid ? fromUid === currentUid : false;

  // Failure indicators from metadata
  const meta: any = message.metadata || {};
  const platformSendError = Boolean(meta.platform_send_error);
  const wsSendError = Boolean(meta.ws_send_error);
  const uploadError = meta.upload_status === 'error';
  const hasError = platformSendError || wsSendError || uploadError;

  // Determine error text based on error type
  const getErrorText = () => {
    if (typeof meta.error_text === 'string' && meta.error_text.trim().length > 0) {
      return meta.error_text;
    }
    if (platformSendError) {
      return t('chat.input.errors.platformFailed', '平台消息发送失败，请稍后重试');
    }
    if (wsSendError) {
      return t('chat.input.errors.websocketFailed', 'WebSocket 发送失败，请检查网络连接');
    }
    if (uploadError) {
      // Check message type for appropriate upload error message
      const isImageMsg = message.payloadType === MessagePayloadType.IMAGE || Boolean(meta.image_url || meta.image_preview_url);
      return isImageMsg ? t('chat.messages.image.uploadFailed', '上传失败') : t('chat.input.upload.failed', '上传失败');
    }
    return '';
  };
  const errorText = getErrorText();
  const [errorOpen, setErrorOpen] = React.useState(false);

  // Sending status indicator
  // A message is considered "sending" if it's a local message (isLocal) and hasn't been sent yet (ws_sent !== true)
  // and doesn't have any errors
  const isSending = Boolean(meta.isLocal) && !hasError && meta.ws_sent !== true;

  // Sender channel info lazy-loading
  const senderChannelId = message.fromUid;
  const senderChannelType = 1;
  const compositeKey = React.useMemo(() => {
    if (!senderChannelId || senderChannelType == null) return null;
    return getChannelKey(senderChannelId, senderChannelType);
  }, [senderChannelId, senderChannelType]);

  const channelInfoCache = useChannelStore(state => (senderChannelId && senderChannelType != null ? state.getChannel(senderChannelId, senderChannelType) : undefined));
  const isChannelFetching = useChannelStore(state => (compositeKey ? Boolean(state.inFlight[compositeKey]) : false));
  const channelStoreError = useChannelStore(state => (compositeKey ? state.errors[compositeKey] : null));
  const ensureChannelInfo = useChannelStore(state => state.ensureChannel);

  // Avoid fetching staff/self; only attempt for visitor messages when fromInfo missing/incomplete
  const needsSenderInfo = !message.fromInfo?.name || !message.fromInfo?.avatar;
  React.useEffect(() => {
    if (!senderChannelId || senderChannelType == null) return;
    if (isOwnMessage || (senderChannelId && senderChannelId.endsWith('-staff'))) return;
    if (!needsSenderInfo) return;
    if (channelInfoCache || isChannelFetching || channelStoreError) return;
    ensureChannelInfo({ channel_id: senderChannelId, channel_type: senderChannelType }).catch(() => {});
  }, [senderChannelId, senderChannelType, isOwnMessage, needsSenderInfo, channelInfoCache, isChannelFetching, channelStoreError, ensureChannelInfo]);

  const displayName = message.fromInfo?.name || channelInfoCache?.name || (isOwnMessage ? t('chat.header.staffFallback', '客服') : t('chat.header.visitorFallback', { suffix: String(senderChannelId || '').slice(-4), defaultValue: `访客${String(senderChannelId || '').slice(-4)}` }));
  const displayAvatar = message.fromInfo?.avatar || channelInfoCache?.avatar || message.avatar || '';

  const hasAvatar = hasValidAvatar(displayAvatar);
  const defaultAvatar = !hasAvatar ? generateDefaultAvatar(displayName) : null;

  // System message (date separator)
  if (isSystemMessage) {
    return (
      <div className="text-center text-xs text-gray-400">
        {message.content}
      </div>
    );
  }

  const isImage = (typedPayload?.type === MessagePayloadType.IMAGE) || message.payloadType === MessagePayloadType.IMAGE || Boolean(message.metadata?.image_url || message.metadata?.image_preview_url);

  // File message derived state (only need boolean for routing)
  const isFile = (typedPayload?.type === MessagePayloadType.FILE) || message.payloadType === MessagePayloadType.FILE || Boolean(message.metadata?.file_url || (message.metadata as any)?.file_name);


  if (!isOwnMessage) {
    return (
      <div className="flex flex-col items-start max-w-xl">
        <div className="text-xs text-gray-600 mb-1 ml-1">
          {displayName}{' '}
          {(() => {
            const fromInfoExtra: any = message.fromInfo?.extra;
            const extraType: PlatformType | undefined = (fromInfoExtra && typeof fromInfoExtra === 'object' && 'platform_type' in fromInfoExtra)
              ? (fromInfoExtra.platform_type as PlatformType)
              : undefined;
            const cacheExtra: any = channelInfoCache?.extra;
            const cacheType: PlatformType | undefined = (cacheExtra && typeof cacheExtra === 'object' && 'platform_type' in cacheExtra)
              ? (cacheExtra.platform_type as PlatformType)
              : undefined;
            const type = (extraType ?? cacheType) ?? toPlatformType(message.platform);
            const IconComp = getPlatformIconComponent(type);
            const label = getPlatformLabel(type);
            return (
              <span title={label}>
                <IconComp size={14} className={`w-3.5 h-3.5 inline-block ml-1 -mt-0.5 ${getPlatformColor(type)}`} />
              </span>
            );
          })()}

        </div>
        <div className="flex items-start space-x-2">
          <div className="w-8 h-8 flex-shrink-0 self-start">
            {hasAvatar ? (
              <img
                src={displayAvatar}
                alt="Visitor Avatar"
                className="w-full h-full rounded-md object-cover"
              />
            ) : (
              <div
                className={`w-full h-full rounded-md flex items-center justify-center text-white font-bold text-sm ${
                  defaultAvatar?.colorClass || 'bg-gradient-to-br from-gray-400 to-gray-500'
                }`}
              >
                {defaultAvatar?.letter || '?'}
              </div>
            )}
          </div>
          {isRichText ? (
            <RichTextMessage message={message} isStaff={false} />
          ) : (
            isImage ? (
              <ImageMessage message={message} isStaff={false} />
            ) : isFile ? (
              <FileMessage message={message} isStaff={false} />
            ) : (
              <TextMessage message={message} isStaff={false} />
            )
          )}
        </div>

        <AIInfoCard aiInfo={message.aiInfo} />
        <ReplySuggestions
          suggestions={(message as any).suggestions}
          onSuggestionClick={onSuggestionClick}
        />
      </div>
    );

  }

  return (
    <div className="flex flex-col items-end ml-auto max-w-xl">
      <div className="flex items-start flex-row-reverse mt-1">
        <div className="w-8 h-8 flex-shrink-0 self-start ml-2">
          {hasAvatar ? (
            <img
              src={displayAvatar}
              alt="Agent Avatar"
              className="w-full h-full rounded-md object-cover"
            />
          ) : (
            <div
              className={`w-full h-full rounded-md flex items-center justify-center text-white font-bold text-sm ${defaultAvatar?.colorClass || 'bg-gradient-to-br from-blue-400 to-blue-500'}`}
            >
              {defaultAvatar?.letter || '?'}
            </div>
          )}
        </div>
        <div className="ml-2">
          {isRichText ? (
            <RichTextMessage message={message} isStaff={true} />
          ) : (
            isImage ? (
              <ImageMessage message={message} isStaff={true} />
            ) : isFile ? (
              <FileMessage message={message} isStaff={true} />
            ) : (
              <TextMessage message={message} isStaff={true} />
            )
          )}
        </div>
        {isSending && (
          <div
            className="relative self-center text-gray-400"
            title={t('chat.messages.sending', '发送中...')}
          >
            <Loader2 className="w-5 h-5 animate-spin" />
          </div>
        )}
        {hasError && (
          <div
            className="relative self-center text-red-500 cursor-pointer"
            onClick={() => setErrorOpen(v => !v)}
            title={t('chat.messages.sendFailedTitle', '发送失败')}
          >
            <AlertCircle className="w-5 h-5" />
            {errorOpen && (
              <div className="absolute right-full mr-2 top-1/2 -translate-y-1/2 bg-white border border-red-200 text-red-700 text-xs rounded-md py-2 px-3 shadow-lg z-50 w-fit min-w-[240px] max-w-[80vw] sm:max-w-md max-h-[60vh] overflow-auto whitespace-pre-wrap break-words">
                {errorText}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default ChatMessage;
