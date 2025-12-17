import React from 'react';
import { AlertCircle, Loader2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import type { Message, PayloadSystem } from '@/types';
import { MessagePayloadType, PlatformType, isSystemMessageType } from '@/types';
import { useAuthStore } from '@/stores/authStore';
import { StreamEndReason } from '@/stores/chatStore';
import { useChannelDisplay } from '@/hooks/useChannelDisplay';
import { getPlatformIconComponent, getPlatformLabel, toPlatformType, getPlatformColor } from '@/utils/platformUtils';

import AIInfoCard from './AIInfoCard';
import ReplySuggestions from './ReplySuggestions';
import { ChatAvatar } from './ChatAvatar';

import TextMessage from './messages/TextMessage';
import ImageMessage from './messages/ImageMessage';
import FileMessage from './messages/FileMessage';
import RichTextMessage from './messages/RichTextMessage';
import LoadingMessage from './messages/LoadingMessage';
import AIErrorMessage from './messages/AIErrorMessage';
import SystemMessage from './messages/SystemMessage';

interface ChatMessageProps {
  message: Message;
  onSuggestionClick?: (suggestion: string) => void;
  /** 发送消息回调（用于 Widget 中的 msg:// 协议） */
  onSendMessage?: (message: string) => void;
}

/**
 * Renders the appropriate message content component based on message type
 */
const MessageContent: React.FC<{
  message: Message;
  isStaff: boolean;
  streamError: boolean;
  streamErrorText: string;
  isStreamLoading: boolean;
  isRichText: boolean;
  isImage: boolean;
  isFile: boolean;
  onSendMessage?: (message: string) => void;
}> = ({ message, isStaff, streamError, streamErrorText, isStreamLoading, isRichText, isImage, isFile, onSendMessage }) => {
  if (streamError) return <AIErrorMessage isStaff={isStaff} errorText={streamErrorText} />;
  if (isStreamLoading) return <LoadingMessage isStaff={isStaff} />;
  if (isRichText) return <RichTextMessage message={message} isStaff={isStaff} onSendMessage={onSendMessage} />;
  if (isImage) return <ImageMessage message={message} isStaff={isStaff} />;
  if (isFile) return <FileMessage message={message} isStaff={isStaff} />;
  return <TextMessage message={message} isStaff={isStaff} onSendMessage={onSendMessage} />;
};

/**
 * Individual chat message component
 */
const ChatMessage: React.FC<ChatMessageProps> = ({ message, onSuggestionClick, onSendMessage }) => {
  const { t } = useTranslation();
  const user = useAuthStore(state => state.user);
  const currentUid = React.useMemo(() => (user?.id ? `${user.id}-staff` : null), [user?.id]);

  const meta: any = message.metadata || {};
  const typedPayload = message.payload as any | undefined;

  // Message type flags
  // 系统消息：message.type === 'system' 或 payload.type 在 1000-2000 范围内
  const payloadType = typedPayload?.type ?? message.payloadType;
  const isSystemMessage = message.type === 'system' || (typeof payloadType === 'number' && isSystemMessageType(payloadType));
  const isOwnMessage = currentUid ? message.fromUid === currentUid : false;

  // Error state detection
  const platformSendError = Boolean(meta.platform_send_error);
  const wsSendError = Boolean(meta.ws_send_error);
  const uploadError = meta.upload_status === 'error';
  const hasSendError = platformSendError || wsSendError || uploadError;

  // Stream error: end=1 and end_reason > 0 (Timeout/Error/Cancelled/Force) OR has error message
  const streamEndReasonNum = typeof meta.stream_end_reason === 'string'
    ? parseInt(meta.stream_end_reason, 10)
    : (typeof meta.stream_end_reason === 'number' ? meta.stream_end_reason : 0);
  const hasStreamEndError = meta.stream_end === 1 && meta.stream_end_reason != null && meta.stream_end_reason !== '' && streamEndReasonNum > 0;
  // Also check for error message from ___TextMessageEnd event or offline API
  const hasErrorMessage = Boolean(meta.error && typeof meta.error === 'string' && meta.error.trim() !== '');
  const streamError = hasStreamEndError || hasErrorMessage;
  const hasError = hasSendError || streamError;

  // Get AI stream error text based on end reason or error message
  const getStreamErrorText = (): string => {
    // If there's a specific error message from the stream end event or API, use it
    if (hasErrorMessage) {
      return meta.error;
    }
    
    // Otherwise, use generic error messages based on end reason
    switch (streamEndReasonNum) {
      case StreamEndReason.TIMEOUT:
        return t('chat.messages.stream.timeout', 'AI 回复超时');
      case StreamEndReason.ERROR:
        return t('chat.messages.stream.error', 'AI 回复生成失败');
      case StreamEndReason.CANCELLED:
        return t('chat.messages.stream.cancelled', 'AI 回复已取消');
      case StreamEndReason.FORCE:
        return t('chat.messages.stream.force', 'AI 回复被强制终止');
      default:
        return t('chat.messages.stream.error', 'AI 回复生成失败');
    }
  };

  // Get send error text for error icon popup
  const getSendErrorText = (): string => {
    if (typeof meta.error_text === 'string' && meta.error_text.trim().length > 0) {
      return meta.error_text;
    }
    if (platformSendError) return t('chat.input.errors.platformFailed', '平台消息发送失败，请稍后重试');
    if (wsSendError) return t('chat.input.errors.websocketFailed', 'WebSocket 发送失败，请检查网络连接');
    if (uploadError) {
      const isImageMsg = message.payloadType === MessagePayloadType.IMAGE || Boolean(meta.image_url || meta.image_preview_url);
      return isImageMsg ? t('chat.messages.image.uploadFailed', '上传失败') : t('chat.input.upload.failed', '上传失败');
    }
    return '';
  };

  const [errorOpen, setErrorOpen] = React.useState(false);
  const isSending = Boolean(meta.isLocal) && !hasError && meta.ws_sent !== true;

  // Message type detection
  const isRichText = typedPayload?.type === MessagePayloadType.RICH_TEXT || message.payloadType === MessagePayloadType.RICH_TEXT || Array.isArray(meta.images);
  const isImage = typedPayload?.type === MessagePayloadType.IMAGE || message.payloadType === MessagePayloadType.IMAGE || Boolean(meta.image_url || meta.image_preview_url);
  const isFile = typedPayload?.type === MessagePayloadType.FILE || message.payloadType === MessagePayloadType.FILE || Boolean(meta.file_url || meta.file_name);
  const isStreamType = typedPayload?.type === MessagePayloadType.STREAM || message.payloadType === MessagePayloadType.STREAM;

  // Stream loading: only show loading if stream type AND no content AND not ended (end !== 1)
  // Once end=1, the stream is complete regardless of end_reason
  const isStreamEnded = meta.stream_end === 1;
  const isStreamLoading = isStreamType && !meta.has_stream_data && !message.content?.trim() && !hasError && !isStreamEnded;

  // Sender channel info - use fromUid as the sender's channel ID
  // This is different from message.channelId which is the conversation channel
  const senderChannelId = message.fromUid;
  const senderChannelType = 1; // Person-to-person channel type
  
  // For avatar color consistency with chat list, use message.channelId for non-own messages (visitors)
  // This ensures visitor avatar color matches the conversation list item
  const colorSeedChannelId = isOwnMessage ? senderChannelId : (senderChannelId || message.channelId );

  // Use unified hook for sender display info
  // Priority: message.fromInfo > channelStore cache > fallback
  const {
    name: channelName,
    avatar: channelAvatar,
    extra: channelExtra,
  } = useChannelDisplay({
    channelId: senderChannelId,
    channelType: senderChannelType,
    overrideName: message.fromInfo?.name,
    overrideAvatar: message.fromInfo?.avatar || message.avatar,
    skipFetch: false,
  });
  
  // Display info with staff fallback
  const displayName = isOwnMessage
    ? (message.fromInfo?.name || t('chat.header.staffFallback', '客服'))
    : channelName;
  const displayAvatar = channelAvatar;

  // System message - payload.type 在 1000-2000 范围内
  if (isSystemMessage) {
    // 如果有 payload 且是系统消息格式，使用 SystemMessage 组件
    if (typedPayload && typeof payloadType === 'number' && isSystemMessageType(payloadType)) {
      return <SystemMessage payload={typedPayload as PayloadSystem} />;
    }
    // 兼容旧的简单系统消息格式
    return (
      <div className="flex justify-center my-3">
        <div className="inline-flex items-center px-3 py-1.5 rounded-full bg-gray-100/80 dark:bg-gray-700/50 text-xs text-gray-500 dark:text-gray-400">
          {message.content}
        </div>
      </div>
    );
  }

  // Get platform icon for visitor messages
  const getPlatformIcon = () => {
    const fromInfoExtra: any = message.fromInfo?.extra;
    const extraType: PlatformType | undefined = fromInfoExtra?.platform_type;
    const cacheExtra: any = channelExtra;
    const cacheType: PlatformType | undefined = cacheExtra?.platform_type;
    const type = extraType ?? cacheType ?? toPlatformType(message.platform);
    const IconComp = getPlatformIconComponent(type);
    const label = getPlatformLabel(type);
    return (
      <span title={label}>
        <IconComp size={14} className={`w-3.5 h-3.5 inline-block ml-1 -mt-0.5 ${getPlatformColor(type)}`} />
      </span>
    );
  };


  // Visitor/AI message (left side)
  if (!isOwnMessage) {
    return (
      <div className="flex flex-col items-start max-w-xl">
        <div className="text-xs text-gray-600 dark:text-gray-400 mb-1 ml-1">
          {displayName} {getPlatformIcon()}
        </div>
        <div className="flex items-start space-x-2">
          <ChatAvatar
            displayName={displayName}
            displayAvatar={displayAvatar}
            colorSeed={colorSeedChannelId}
            sizePx={32} // keep existing 8x8 size
            wrapperClassName="relative flex-shrink-0 self-start"
          />
          <MessageContent
            message={message}
            isStaff={false}
            streamError={streamError}
            streamErrorText={getStreamErrorText()}
            isStreamLoading={isStreamLoading}
            isRichText={isRichText}
            isImage={isImage}
            isFile={isFile}
            onSendMessage={onSendMessage}
          />
        </div>
        <AIInfoCard aiInfo={message.aiInfo} />
        <ReplySuggestions suggestions={(message as any).suggestions} onSuggestionClick={onSuggestionClick} />
      </div>
    );
  }

  // Own message (right side)
  return (
    <div className="flex flex-col items-end ml-auto max-w-xl">
      <div className="flex items-start flex-row-reverse mt-1">
        <MessageContent
          message={message}
          isStaff={true}
          streamError={streamError}
          streamErrorText={getStreamErrorText()}
          isStreamLoading={isStreamLoading}
          isRichText={isRichText}
          isImage={isImage}
          isFile={isFile}
          onSendMessage={onSendMessage}
        />
        {isSending && (
          <div className="relative self-center text-gray-400 dark:text-gray-500 mr-2" title={t('chat.messages.sending', '发送中...')}>
            <Loader2 className="w-5 h-5 animate-spin" />
          </div>
        )}
        {hasSendError && (
          <div
            className="relative self-center text-red-500 dark:text-red-400 cursor-pointer mr-2"
            onClick={() => setErrorOpen(v => !v)}
            title={t('chat.messages.sendFailedTitle', '发送失败')}
          >
            <AlertCircle className="w-5 h-5" />
            {errorOpen && (
              <div className="absolute right-full mr-2 top-1/2 -translate-y-1/2 bg-white dark:bg-gray-800 border border-red-200 dark:border-red-800/50 text-red-700 dark:text-red-400 text-xs rounded-md py-2 px-3 shadow-lg z-50 w-fit min-w-[240px] max-w-[80vw] sm:max-w-md max-h-[60vh] overflow-auto whitespace-pre-wrap break-words">
                {getSendErrorText()}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default ChatMessage;
