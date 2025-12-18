import React, { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { createPortal } from 'react-dom';

import { useTranslation } from 'react-i18next';


import { useChatStore, chatSelectors, useMessageStore } from '@/stores';
import { useChannelStore } from '@/stores/channelStore';
import { useAuthStore } from '@/stores/authStore';
import type { ChannelVisitorExtra, Message } from '@/types';
import { MessagePayloadType, PlatformType } from '@/types';
import { DEFAULT_CHANNEL_TYPE } from '@/constants';
import { visitorApiService } from '@/services/visitorApi';
import { conversationsApi } from '@/services/conversationsApi';
import { useToast } from '@/hooks/useToast';
import { showApiError, showSuccess } from '@/utils/toastHelpers';
import Toggle from '@/components/ui/Toggle';
import EmojiPickerPopover from '@/components/chat/EmojiPickerPopover';
import { uploadChatImageWithProgress, uploadChatFileWithProgress } from '@/services/chatUploadApi';
import { useWuKongIMWebSocket } from '@/hooks/useWuKongIMWebSocket';
import { WsSendError } from '@/services/wukongimWebSocket';
import { toAbsoluteApiUrl } from '@/utils/url';
import { getFileIcon } from '@/utils/fileIcons';
import { chatMessagesApiService } from '@/services/chatMessagesApi';
import { APIError } from '@/services/api';

import { Smile, Scissors, Image as ImageIcon, Folder, Pause, Loader2, UserPlus } from 'lucide-react';

/**
 * Extract error message from error object (supports APIError, WsSendError and generic Error)
 * @param error The error object
 * @param t i18n translation function
 * @param fallbackKey Fallback i18n key for unknown errors
 * @param fallbackDefault Fallback default message
 */
const getErrorMessage = (
  error: unknown, 
  t?: (key: string, defaultValue: string) => string,
  fallbackKey?: string,
  fallbackDefault?: string
): string => {
  if (error instanceof WsSendError && t) {
    return t(error.i18nKey, error.defaultMessage);
  }
  if (error instanceof APIError) {
    return error.getUserMessage();
  }
  if (error instanceof Error) {
    return error.message;
  }
  if (t && fallbackKey && fallbackDefault) {
    return t(fallbackKey, fallbackDefault);
  }
  return '上传失败';
};

interface MessageInputProps {
  onSendMessage?: (message: string) => void;
  isSending?: boolean;
  onAcceptVisitor?: () => void;
}

/**
 * Message input component with toolbar and send functionality
 */
const MessageInput: React.FC<MessageInputProps> = ({
  onSendMessage,
  isSending = false,
  onAcceptVisitor,
}) => {
  const { t } = useTranslation();
  const [message, setMessage] = useState<string>('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [isComposing, setIsComposing] = useState<boolean>(false);

  const shouldMaintainFocus = useRef<boolean>(false);
  // Emoji picker state and anchor
  const [showEmoji, setShowEmoji] = useState<boolean>(false);
  // Screenshot tooltip state and anchor
  const [showScreenshotTip, setShowScreenshotTip] = useState<boolean>(false);
  const screenshotBtnRef = useRef<HTMLButtonElement>(null);
  const [screenshotTipPos, setScreenshotTipPos] = useState<{ top: number; left: number }>({ top: 0, left: 0 });
  const TIP_WIDTH = 320;

  const TIP_HEIGHT = 120; // approximate height for positioning
  const TIP_MARGIN = 8;
  // Pasted images preview state (supports multiple)
  type PastedItem = { file: File; previewUrl: string; width: number; height: number; progress?: number; status?: 'idle' | 'uploading' | 'completed' | 'error' };
  const [pastedItems, setPastedItems] = useState<PastedItem[]>([]);

  // Selected files (documents) preview state
  type SelectedFile = { id: string; file: File };
  const [selectedFiles, setSelectedFiles] = useState<SelectedFile[]>([]);






  const computeScreenshotTipPosition = useCallback(() => {
    const anchor = screenshotBtnRef.current as HTMLElement | null;
    if (!anchor) return;
    const rect = anchor.getBoundingClientRect();

    const hasSpaceAbove = rect.top >= TIP_HEIGHT + TIP_MARGIN + 10;
    const hasSpaceBelow = window.innerHeight - rect.bottom >= TIP_HEIGHT + TIP_MARGIN + 10;

    let placement: 'top' | 'bottom' = hasSpaceAbove ? 'top' : 'bottom';
    if (!hasSpaceAbove && !hasSpaceBelow) {
      placement = rect.top > window.innerHeight - rect.bottom ? 'top' : 'bottom';
    }

    let top: number;
    if (placement === 'top') {
      top = Math.max(10, rect.top - TIP_HEIGHT - TIP_MARGIN);
    } else {
      top = Math.min(window.innerHeight - TIP_HEIGHT - 10, rect.bottom + TIP_MARGIN);
    }

    const centerLeft = rect.left + rect.width / 2 - TIP_WIDTH / 2;
    const left = Math.min(Math.max(10, centerLeft), window.innerWidth - TIP_WIDTH - 10);

    setScreenshotTipPos({ top, left });
  }, []);

  useEffect(() => {
    if (!showScreenshotTip) return;
    computeScreenshotTipPosition();
    const handler = () => computeScreenshotTipPosition();
    window.addEventListener('resize', handler);
    window.addEventListener('scroll', handler, true);
    return () => {
      window.removeEventListener('resize', handler);
      window.removeEventListener('scroll', handler, true);
    };
  }, [showScreenshotTip, computeScreenshotTipPosition]);

  const handleClickScreenshotBtn = useCallback(() => {
    setShowEmoji(false);
    setShowScreenshotTip((v) => !v);
    // Slight delay to allow state update before computing position
    setTimeout(() => computeScreenshotTipPosition(), 0);
  }, [computeScreenshotTipPosition]);

  const emojiBtnRef = useRef<HTMLButtonElement>(null);

  const focusTimeoutRef = useRef<number | null>(null);

  // Subscribe to activeChat to focus when switching conversations
  const activeChat = useChatStore(chatSelectors.activeChat);
  const channelId = activeChat?.channelId;
  const channelType = activeChat?.channelType;

  // 判定当前会话是否正在流式响应
  const activeStreamingChannels = useMessageStore(state => state.activeStreamingChannels);
  const isStreamingInProgress = useMemo(() => {
    if (!channelId || channelType == null) return false;
    return Object.values(activeStreamingChannels).some(
      c => c.channelId === channelId && c.channelType === channelType
    );
  }, [activeStreamingChannels, channelId, channelType]);

  // Detect user's platform for keyboard shortcut hints
  const isMac = typeof navigator !== 'undefined' && navigator.platform.toUpperCase().indexOf('MAC') >= 0;
  const newlineHint = isMac
    ? t('chat.input.shortcuts.newline.mac', '⌘ + Enter 换行')
    : t('chat.input.shortcuts.newline.windows', 'Ctrl + Enter 换行');

  // Focus on conversation switch
  useEffect(() => {
    let switchFocusTimeout: number | undefined;
    if (activeChat && textareaRef.current) {
      console.log('Conversation switched, focusing input for:', activeChat.channelInfo?.name || activeChat.channelId);
      // Small delay to ensure the component is fully rendered
      switchFocusTimeout = window.setTimeout(() => {
        if (textareaRef.current) {
          textareaRef.current.focus();
          console.log('Focus applied after conversation switch');
        }
      }, 100);
    }
    return () => {
      if (switchFocusTimeout) clearTimeout(switchFocusTimeout);
    };
  }, [activeChat?.id]); // Only trigger when activeChat ID changes

  // Advanced focus management function with multiple strategies
  const maintainTextareaFocus = useCallback(() => {
    if (!textareaRef.current || !shouldMaintainFocus.current) return;

    // Clear any existing timeout
    if (focusTimeoutRef.current) {
      clearTimeout(focusTimeoutRef.current);
    }

    // Strategy 1: Immediate focus attempt
    textareaRef.current.focus();

    // Strategy 2: Delayed focus attempt (for React state updates)
    focusTimeoutRef.current = window.setTimeout(() => {
      if (textareaRef.current && shouldMaintainFocus.current) {
        textareaRef.current.focus();
        console.log('Delayed focus applied - new active element:', document.activeElement);
      }
    }, 50);

    // Strategy 3: Post-render focus attempt
    requestAnimationFrame(() => {
      if (textareaRef.current && shouldMaintainFocus.current && document.activeElement !== textareaRef.current) {
        textareaRef.current.focus();
        console.log('Animation frame focus applied - new active element:', document.activeElement);
        shouldMaintainFocus.current = false; // Reset flag after successful focus
      }
    });
  }, []);

  // Effect-based focus recovery - runs after every render
  // AI toggle integration
  
  // 判断是否是 agent 会话（channelId 以 -agent 结尾）或 team 会话（channelId 以 -team 结尾）
  const isAgentChat = channelId?.endsWith('-agent') ?? false;
  const isTeamChat = channelId?.endsWith('-team') ?? false;
  const isAIChat = isAgentChat || isTeamChat;
  
  const channelInfo = useChannelStore(state =>
    channelId && typeof channelType === 'number'
      ? state.getChannel(channelId, channelType)
      : undefined
  );
  const visitorExtra = (channelInfo?.extra as ChannelVisitorExtra | undefined);
  const visitorId = visitorExtra?.id;
  const serviceStatus = visitorExtra?.service_status;
  const assignedStaffId = visitorExtra?.assigned_staff_id;
  const isQueued = serviceStatus === 'queued';
  const isClosed = serviceStatus === 'closed';
  const isAIDisabled = visitorExtra?.ai_disabled ?? false;
  
  // 获取分配坐席的频道信息（用于显示坐席名字）
  const assignedStaffChannelId = assignedStaffId ? `${assignedStaffId}-staff` : undefined;
  const assignedStaffChannelInfo = useChannelStore(state => 
    assignedStaffChannelId ? state.getChannel(assignedStaffChannelId, 1) : undefined
  );
  const assignedStaffName = assignedStaffChannelInfo?.name;
  const isAIEnabled = !isAIDisabled;
  // agent/team 会话时不禁用手动输入
  const isManualDisabled = isAIChat ? false : isAIEnabled;
  // 流消息进行中时不禁用输入框，但发送按钮会变成暂停按钮
  const { showToast, showError } = useToast();
  useEffect(() => {
    if (isManualDisabled) {
      setShowEmoji(false);
      setShowScreenshotTip(false);
    }
  }, [isManualDisabled]);

  // 当访客分配给其他坐席时，获取该坐席的频道信息以显示名字
  const ensureChannel = useChannelStore(state => state.ensureChannel);
  useEffect(() => {
    if (assignedStaffChannelId && !assignedStaffChannelInfo) {
      ensureChannel({ channel_id: assignedStaffChannelId, channel_type: DEFAULT_CHANNEL_TYPE });
    }
  }, [assignedStaffChannelId, assignedStaffChannelInfo, ensureChannel]);

  const [isTogglingAI, setIsTogglingAI] = useState(false);
  const [isAccepting, setIsAccepting] = useState(false);
  
  // Handle accepting a visitor from the waiting queue
  const handleAcceptVisitor = useCallback(async () => {
    if (!visitorId || isAccepting) return;
    
    try {
      setIsAccepting(true);
      await conversationsApi.acceptVisitor(visitorId);
      
      // Refresh channel info to get updated service_status
      if (channelId && typeof channelType === 'number') {
        const channelStore = useChannelStore.getState();
        await channelStore.refreshChannel({ channel_id: channelId, channel_type: channelType });
      }
      
      showSuccess(showToast, t('chat.input.accept.successTitle', '接入成功'), t('chat.input.accept.successMessage', '访客已成功接入'));
      
      // Notify parent to switch to "my" tab
      onAcceptVisitor?.();
    } catch (error) {
      showApiError(showToast, error);
    } finally {
      setIsAccepting(false);
    }
  }, [visitorId, isAccepting, channelId, channelType, showToast, t, onAcceptVisitor]);

  // Image upload & send (WeChat-like)
  const user = useAuthStore(state => state.user);
  const addMessage = useChatStore(state => state.addMessage);
  const updateConversationLastMessage = useChatStore(state => state.updateConversationLastMessage);
  const moveConversationToTop = useChatStore(state => state.moveConversationToTop);
  const updateMessageByClientMsgNo = useChatStore(state => state.updateMessageByClientMsgNo);
  const cancelStreamingMessage = useChatStore(state => state.cancelStreamingMessage);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const fileDocInputRef = useRef<HTMLInputElement>(null);

  const { sendMessage: sendWsMessage, isConnected } = useWuKongIMWebSocket();

  // Local sending guard to prevent duplicate sends within this component
  const [isSendingLocal, setIsSendingLocal] = useState(false);

  const getImageDimensions = useCallback(async (file: File): Promise<{ width: number; height: number }> => {
    return new Promise((resolve) => {
      const img = new Image();
      const url = URL.createObjectURL(file);
      img.onload = () => {
        const width = (img as any).naturalWidth || img.width;
        const height = (img as any).naturalHeight || img.height;
        URL.revokeObjectURL(url);
        resolve({ width, height });
      };
      img.onerror = () => {
        URL.revokeObjectURL(url);
        resolve({ width: 0, height: 0 });
      };
      img.src = url;
    });
  }, []);

  const handleClickImageBtn = useCallback(() => {
    if (isManualDisabled) return;
    fileInputRef.current?.click();
  }, [isManualDisabled]);

  const handleClickFileBtn = useCallback(() => {
    if (isManualDisabled) return;
    fileDocInputRef.current?.click();
  }, [isManualDisabled]);

  const handleFileChange = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const filesList = e.target.files;

    // Reset input value to allow re-selecting the same file(s)
    // e.target.value = '';
    if (!filesList || filesList.length === 0) {
      return;
    }

    // Categorize files into images and non-images
    const imageFiles: File[] = [];
    const nonImageFiles: File[] = [];

    Array.from(filesList).forEach(f => {
      const mime = (f.type || '').toLowerCase();
      const name = (f.name || '').toLowerCase();
      const isImageByMime = /^image\//i.test(mime);
      const isImageByExt = /\.(png|jpe?g|gif|webp|bmp|svg|heic|heif|tiff?)$/.test(name);
      const isImage = isImageByMime || isImageByExt;

      if (isImage) {
        imageFiles.push(f);
      } else {
        nonImageFiles.push(f);
      }
    });

    // Handle image files - add to pastedItems (respecting 9-image limit)
    if (imageFiles.length > 0) {
      const currentImageCount = pastedItems.length;
      const availableSlots = 9 - currentImageCount;

      if (availableSlots <= 0) {
        showError(
          t('chat.input.errors.images.limitReachedTitleSimple', '图片数量已达上限'),
          t('chat.input.errors.images.limitReachedAddNine', '最多只能添加 9 张图片')
        );
      } else {
        const imagesToAdd = imageFiles.slice(0, availableSlots);
        const skippedCount = imageFiles.length - imagesToAdd.length;

        // Process images and add to pastedItems
        const newPastedItems: PastedItem[] = await Promise.all(
          imagesToAdd.map(async (file) => {
            const previewUrl = URL.createObjectURL(file);
            const { width, height } = await new Promise<{ width: number; height: number }>((resolve) => {
              const img = new Image();
              img.onload = () => resolve({ width: img.naturalWidth, height: img.naturalHeight });
              img.onerror = () => resolve({ width: 0, height: 0 });
              img.src = previewUrl;
            });

            return {
              file,
              previewUrl,
              width,
              height,
              progress: 0,
              status: 'idle' as const,
            };
          })
        );

        setPastedItems(prev => [...prev, ...newPastedItems]);

        if (skippedCount > 0) {
          showError(
            t('chat.input.errors.images.partialNotAddedTitle', '部分图片未添加'),
            t('chat.input.errors.images.partialNotAddedDesc', '已添加 {{added}} 张图片，跳过 {{skipped}} 张（超出 9 张限制）', { added: imagesToAdd.length, skipped: skippedCount })
          );
        }
      }
    }

    // Handle non-image files - add to selectedFiles (limit to 1)
    if (nonImageFiles.length > 0) {
      if (selectedFiles.length > 0) {
        showError(
          t('chat.input.errors.files.onlyOne', '仅支持发送一个文件'),
          t('chat.input.errors.files.removeCurrent', '请先移除当前文件')
        );
      } else {
        const fileToAdd = nonImageFiles[0];
        const skippedCount = nonImageFiles.length - 1;

        const newItem: SelectedFile = {
          id: `sel-file-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
          file: fileToAdd
        };

        setSelectedFiles([newItem]);

        if (skippedCount > 0) {
          showError(
            t('chat.input.errors.files.onlyOne', '仅支持发送一个文件'),
            t('chat.input.errors.files.skippedOther', '已添加 "{{name}}"，跳过其他 {{count}} 个文件', { name: fileToAdd.name, count: skippedCount })
          );
        }
      }
    }
  }, [pastedItems, selectedFiles, setPastedItems, setSelectedFiles, showError]);

  const handleImageChange = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const filesList = e.target.files;
    // Reset input value to allow re-selecting the same file(s)
    // e.target.value = '';
    if (!filesList || filesList.length === 0) return;

    // Build array of File objects (accept only images)
    const files: File[] = Array.from(filesList).filter(f => /^image\/(png|jpe?g|gif|webp)$/i.test(f.type));
    if (files.length === 0) {
      showError(
        t('chat.input.errors.images.unsupportedTypeTitle', '不支持的文件类型'),
        t('chat.input.errors.images.unsupportedTypeDesc', '仅支持图片文件（jpg/png/gif/webp）')
      );
      return;
    }

    // Enforce 9-image limit with feedback
    const current = pastedItems.length;
    const allowed = Math.max(0, 9 - current);
    if (allowed <= 0) {
      showError(
        t('chat.input.errors.images.limitReachedTitle', '已达到图片数量上限（9张）'),
        t('chat.input.errors.images.limitReachedDesc', '最多只能上传9张图片')
      );
      return;
    }

    const toUse = files.slice(0, allowed);
    if (files.length > allowed) {
      showError(
        t('chat.input.errors.images.tooManyTitle', '最多只能上传9张图片'),
        t('chat.input.errors.images.tooManyDesc', '已超过可添加的图片数量')
      );
    }

    // Build preview items and append to pastedItems (do not send immediately)
    const newItems: PastedItem[] = [];
    for (const f of toUse) {
      try {
        const previewUrl = URL.createObjectURL(f);
        const { width, height } = await getImageDimensions(f);
        newItems.push({ file: f, previewUrl, width, height, progress: 0, status: 'idle' });
      } catch {}
    }
    if (newItems.length) {
      setPastedItems(prev => [...prev, ...newItems]);
    }
  }, [pastedItems, getImageDimensions, showError]);


  const handleChangeAI = useCallback(async (nextEnabled: boolean) => {
    if (!visitorId || !channelId || typeof channelType !== 'number') return;
    if (nextEnabled === isAIEnabled) return; // no change
    try {

      setIsTogglingAI(true);

      const chatStore = useChatStore.getState();
      const channelStore = useChannelStore.getState();

      // Call appropriate API to reach desired state
      const updated = nextEnabled
        ? await visitorApiService.enableAI(visitorId)
        : await visitorApiService.disableAI(visitorId);

      // Toast success
      if (nextEnabled) {
        showSuccess(showToast, t('chat.input.ai.enabledTitle', 'AI已启用'), t('chat.input.ai.enabledMessage', '访客AI助手已启用'));
      } else {
        showSuccess(showToast, t('chat.input.ai.disabledTitle', 'AI已禁用'), t('chat.input.ai.disabledMessage', '访客AI助手已禁用'));
      }

      // Patch local store state to reflect new status immediately
      const current = channelStore.getChannel(channelId, channelType);
      if (current) {
        const newAiDisabled = (updated as any)?.ai_disabled ?? !nextEnabled;
        const newExtra = { ...(current.extra as any), ai_disabled: newAiDisabled };
        channelStore.seedChannel(channelId, channelType, { extra: newExtra });
        chatStore.applyChannelInfo(channelId, channelType, { ...current, extra: newExtra });
      }
    } catch (error) {
      showApiError(showToast, error);
    } finally {
      setIsTogglingAI(false);
    }
  }, [visitorId, channelId, channelType, isAIEnabled, showToast]);

  useEffect(() => {
    if (shouldMaintainFocus.current) {
      maintainTextareaFocus();
    }
  });

  // Focus restoration when isSending changes from true to false
  useEffect(() => {
    if (!isSending && shouldMaintainFocus.current) {
      console.log('isSending changed to false, attempting focus restoration');
      maintainTextareaFocus();
    }
  }, [isSending, maintainTextareaFocus]);

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (focusTimeoutRef.current) {
        clearTimeout(focusTimeoutRef.current);
      }
    };
  }, []);

  // Format bytes for human readable size
  const formatBytes = useCallback((bytes?: number) => {
    if (bytes === undefined || bytes === null) return '';
    if (bytes === 0) return '0 B';
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    const val = bytes / Math.pow(1024, i);
    return `${val.toFixed(i === 0 ? 0 : 1)} ${sizes[i]}`;
  }, []);

  // Remove a selected file from preview
  const removeSelectedFile = useCallback((id: string) => {
    setSelectedFiles(prev => prev.filter(sf => sf.id !== id));
  }, []);


  const handleCancelStream = useCallback(async (): Promise<void> => {
    if (!isStreamingInProgress) return;
    
    // 找到当前会话对应的流式消息 ID
    const entry = Object.entries(activeStreamingChannels).find(
      ([_, c]) => c.channelId === channelId && c.channelType === channelType
    );
    const targetClientMsgNo = entry ? entry[0] : undefined;

    try {
      await cancelStreamingMessage(targetClientMsgNo);
      showSuccess(showToast, t('chat.input.streaming.cancelledTitle', '已暂停'), t('chat.input.streaming.cancelledMessage', '流消息已暂停'));
    } catch (error) {
      console.error('Failed to cancel stream message:', error);
      showApiError(showToast, error);
    }
  }, [isStreamingInProgress, activeStreamingChannels, channelId, channelType, cancelStreamingMessage, showToast, t]);

  const handleSend = async (): Promise<void> => {
    if (isManualDisabled) return;
    if (isSending || isSendingLocal) return;
    
    // If streaming in progress, cancel it instead of sending
    if (isStreamingInProgress) {
      await handleCancelStream();
      return;
    }

    const hasImages = pastedItems.length > 0;
    const hasText = !!message.trim();
    const hasFiles = selectedFiles.length > 0;

    shouldMaintainFocus.current = true;

    // Priority order:
    // 1. Text + Images → RICH_TEXT with images
    // 2. Text + File → RICH_TEXT with file
    // 3. Images only → IMAGE messages
    // 4. File only → FILE message
    // 5. Text only → TEXT message

    try {
      if (hasImages && hasText) {
        setIsSendingLocal(true);
        await sendRichTextWithImages();
      } else if (hasFiles && hasText) {
        setIsSendingLocal(true);
        await sendRichTextWithFile();
      } else if (hasImages) {
        setIsSendingLocal(true);
        await sendImagesOnly();
      } else if (hasFiles) {
        setIsSendingLocal(true);
        await sendSelectedFilesOnly();
      } else if (hasText) {
        onSendMessage?.(message.trim());
        setMessage('');

      }
    } finally {
      setIsSendingLocal(false);
      maintainTextareaFocus();
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent<HTMLTextAreaElement>): void => {
    if (isManualDisabled) {
      e.preventDefault();
      return;
    }
    if (e.key === 'Enter') {
      // Don't handle Enter if IME is composing (Chinese input method active)
      if (isComposing) {
        return;
      }

      // Ctrl + Enter (Windows) or Cmd + Enter (Mac) for new line
      if (e.ctrlKey || e.metaKey) {
        // Insert new line at cursor position
        e.preventDefault();
        const textarea = textareaRef.current;
        if (textarea) {
          const start = textarea.selectionStart;
          const end = textarea.selectionEnd;
          const newValue = `${message.substring(0, start)}\n${message.substring(end)}`;
          setMessage(newValue);

          // Set cursor position after the inserted newline
          setTimeout(() => {
            textarea.selectionStart = textarea.selectionEnd = start + 1;
          }, 0);
        }
        return;
      }

      // Plain Enter to send message (text, images or files)
      const canSend = !isSending && !isSendingLocal && (message.trim() || pastedItems.length > 0 || selectedFiles.length > 0);
      if (canSend) {
        e.preventDefault(); // Prevent new line
        handleSend();
      } else {
        e.preventDefault(); // Prevent new line if nothing to send or currently sending
      }
    }
  };

  // Handle IME composition events for Chinese input methods
  const handleCompositionStart = (): void => {
    setIsComposing(true);
  };

  const handleCompositionEnd = (): void => {
    setIsComposing(false);
  };

  // Insert emoji at current cursor position and keep focus
  const insertEmoji = useCallback((emoji: string) => {
    const ta = textareaRef.current;
    if (!ta) return;
    const start = ta.selectionStart ?? message.length;
    const end = ta.selectionEnd ?? message.length;
    const next = message.slice(0, start) + emoji + message.slice(end);
    setMessage(next);
    requestAnimationFrame(() => {
      ta.focus();
      const pos = start + emoji.length;
      try {
        ta.selectionStart = ta.selectionEnd = pos;
      } catch {
        // Some browsers may throw if not focusable; ignore
      }
    });
  }, [message]);

  const handlePaste = useCallback(async (e: React.ClipboardEvent<HTMLTextAreaElement>) => {
    if (isManualDisabled) { e.preventDefault(); return; }
    const cd = e.clipboardData;
    if (!cd) return;
    const items = Array.from(cd.items).filter(it => it.kind === 'file' && it.type && it.type.startsWith('image/'));
    if (!items.length) return; // allow normal text paste if no image

    // Prevent default text paste when images are present
    e.preventDefault();

    const files: File[] = [];
    for (const it of items) {
      const f = it.getAsFile();
      if (f && /^image\/(png|jpe?g|gif|webp)$/i.test(f.type)) {
        files.push(f);
      }
    }
    if (!files.length) return;

    // Enforce 9-image limit
    const current = pastedItems.length;
    const allowed = Math.max(0, 9 - current);
    if (allowed <= 0) {
      showError(
        t('chat.input.errors.images.limitReachedTitle', '\u5df2\u8fbe\u5230\u56fe\u7247\u6570\u91cf\u4e0a\u9650\uff089\u5f20\uff09'),
        t('chat.input.errors.images.limitReachedDesc', '\u6700\u591a\u53ea\u80fd\u4e0a\u4f209\u5f20\u56fe\u7247')
      );
      return;
    }
    const toUse = files.slice(0, allowed);
    if (files.length > allowed) {
      showError(
        t('chat.input.errors.images.tooManyTitle', '\u6700\u591a\u53ea\u80fd\u4e0a\u4f209\u5f20\u56fe\u7247'),
        t('chat.input.errors.images.tooManyDesc', '\u5df2\u8d85\u8fc7\u53ef\u6dfb\u52a0\u7684\u56fe\u7247\u6570\u91cf')
      );
    }

    setShowScreenshotTip(false);

    // Build new pasted items with preview URLs and dimensions
    const newItems: PastedItem[] = [];
    for (const f of toUse) {
      try {
        const previewUrl = URL.createObjectURL(f);
        const { width, height } = await getImageDimensions(f);
        newItems.push({ file: f, previewUrl, width, height, progress: 0, status: 'idle' });
      } catch {}
    }
    if (newItems.length) {
      setPastedItems(prev => [...prev, ...newItems]);
    }
  }, [pastedItems, getImageDimensions, showError, isManualDisabled]);

  // Cleanup preview URLs on unmount or when items change
  useEffect(() => {
    return () => {
      for (const it of pastedItems) {
        try { URL.revokeObjectURL(it.previewUrl); } catch {}
      }
    };
  }, [pastedItems]);


  const removePastedItem = useCallback((index: number) => {
    setPastedItems(prev => {
      const arr = [...prev];
      const [removed] = arr.splice(index, 1);
      if (removed) {
        try { URL.revokeObjectURL(removed.previewUrl); } catch {}
      }
      return arr;
    });
    // Reset image input so re-selecting the same files will trigger onChange again
    if (fileInputRef.current) fileInputRef.current.value = '';
  }, []);

  const sendImagesOnly = useCallback(async (): Promise<void> => {
    if (!channelId || typeof channelType !== 'number') {
      showError(
        t('chat.input.errors.noConversationTitle', '请选择对话'),
        t('chat.input.errors.noConversationDesc.image', '请选择对话后再发送图片')
      );
      return;
    }

    const items = [...pastedItems];
    for (const it of items) {
      const nowId = `local-img-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
      const width = it.width; const height = it.height;
      const previewUrl = it.previewUrl;

      const localMessage: Message = {
        id: nowId,
        type: 'staff',
        content: '[图片]',
        timestamp: new Date().toISOString(),
        messageId: nowId,
        clientMsgNo: nowId,
        messageSeq: 0,
        fromUid: user?.id ? `${user.id}-staff` : 'staff',
        channelId: channelId,
        channelType: channelType,
        payloadType: MessagePayloadType.IMAGE,
        metadata: {
          isLocal: true,
          image_preview_url: previewUrl,
          image_width: width,
          image_height: height,
          upload_status: 'uploading',
          upload_progress: 0,
        }
      };

      addMessage(localMessage);
      updateConversationLastMessage(channelId, channelType, localMessage);
      moveConversationToTop(channelId, channelType);

      await uploadChatImageWithProgress(it.file, channelId, channelType, {
        onProgress: (p) => {
          updateMessageByClientMsgNo(nowId, {
            metadata: {
              upload_progress: p.progress,
              upload_status: p.status,
            }
          });
        }
      }).then(async (res) => {
        updateMessageByClientMsgNo(nowId, {
          metadata: {
            image_url: toAbsoluteApiUrl(res.file_url),
            upload_progress: 100,
            upload_status: 'completed',
          }
        });

        const payload = {
          type: MessagePayloadType.IMAGE,
          content: '[图片]',
          url: toAbsoluteApiUrl(res.file_url),
          width,
          height,
          timestamp: Date.now(),
        } as any;

        try {
          if (visitorExtra?.platform_type && visitorExtra.platform_type !== PlatformType.WEBSITE) {
            try {
              await chatMessagesApiService.staffSendPlatformMessage({
                channel_id: channelId,
                channel_type: channelType,
                payload,
                client_msg_no: nowId,
              });
            } catch (err) {
              const errMsg = err instanceof Error ? err.message : t('chat.input.errors.platformFailed', '平台消息发送失败，请稍后重试');
              updateMessageByClientMsgNo(nowId, { metadata: { platform_send_error: true, error_text: errMsg } });
              showApiError(showToast, err);
              return;
            }
          }
          if (!isConnected) throw new Error(t('chat.input.errors.websocketNotConnected.image', 'WebSocket 未连接，无法发送图片消息'));
          console.log("Sending image message via WebSocket", payload);
          await sendWsMessage(channelId, channelType, payload, nowId);
          updateMessageByClientMsgNo(nowId, { metadata: { ws_sent: true, ws_send_error: false } });
        } catch (err) {
          const errMsg = getErrorMessage(err, t, 'chat.input.errors.websocketFailed', 'WebSocket 发送失败，请检查网络连接');
          updateMessageByClientMsgNo(nowId, { metadata: { ws_send_error: true, error_text: errMsg } });
          showApiError(showToast, err);
        }
      }).catch((err) => {
        const errorMessage = getErrorMessage(err);
        updateMessageByClientMsgNo(nowId, { metadata: { upload_status: 'error', error_text: errorMessage } });
        showApiError(showToast, err);
      });
    }
    // Clear previews after triggering sends
    setPastedItems([]);
    if (fileInputRef.current) fileInputRef.current.value = '';
  }, [pastedItems, channelId, channelType, user?.id, addMessage, updateConversationLastMessage, moveConversationToTop, updateMessageByClientMsgNo, isConnected, sendWsMessage, showToast, showError, visitorExtra?.platform_type]);

  // Send selected files (each as a separate message)
  const sendSelectedFilesOnly = useCallback(async (): Promise<void> => {
    const items = [...selectedFiles];
    if (!items.length) return;

    if (!channelId || typeof channelType !== 'number') {
      showError(
        t('chat.input.errors.noConversationTitle', '请选择对话'),
        t('chat.input.errors.noConversationDesc.file', '请选择对话后再发送文件')
      );
      return;
    }

    for (const it of items) {
      const f = it.file;
      const nowId = `local-file-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;

      const localMessage: Message = {
        id: nowId,
        type: 'staff',
        content: '[文件]',
        timestamp: new Date().toISOString(),
        messageId: nowId,
        clientMsgNo: nowId,
        messageSeq: 0,
        fromUid: user?.id ? `${user.id}-staff` : 'staff',
        channelId: channelId,
        channelType: channelType,
        payloadType: MessagePayloadType.FILE,
        metadata: {
          isLocal: true,
          file_name: f.name,
          file_size: f.size,
          upload_status: 'uploading',
          upload_progress: 0,
          file: f as any,
        }
      };

      addMessage(localMessage);
      updateConversationLastMessage(channelId, channelType, localMessage);
      moveConversationToTop(channelId, channelType);

      await uploadChatFileWithProgress(f, channelId, channelType, {
        onProgress: (p) => {
          updateMessageByClientMsgNo(nowId, {
            metadata: {
              upload_progress: p.progress,
              upload_status: p.status,
            }
          });
        }
      }).then(async (res) => {
        const fileUrl = toAbsoluteApiUrl(res.file_url);
        updateMessageByClientMsgNo(nowId, {
          metadata: {
            file_url: fileUrl,
            upload_progress: 100,
            upload_status: 'completed',
          }
        });

        const payload = {
          type: MessagePayloadType.FILE,
          content: '[文件]',
          url: fileUrl,
          name: f.name,
          size: f.size,
          timestamp: Date.now(),
        } as any;

        try {
          if (visitorExtra?.platform_type && visitorExtra.platform_type !== PlatformType.WEBSITE) {
            try {
              await chatMessagesApiService.staffSendPlatformMessage({
                channel_id: channelId,
                channel_type: channelType,
                payload,
                client_msg_no: nowId,
              });
            } catch (err) {
              const errMsg = err instanceof Error ? err.message : t('chat.input.errors.platformFailed', '平台消息发送失败，请稍后重试');
              updateMessageByClientMsgNo(nowId, { metadata: { platform_send_error: true, error_text: errMsg } });
              showApiError(showToast, err);
              return;
            }
          }
          if (!isConnected) throw new Error(t('chat.input.errors.websocketNotConnected.file', 'WebSocket 未连接，无法发送文件消息'));
          await sendWsMessage(channelId, channelType, payload, nowId);
          updateMessageByClientMsgNo(nowId, { metadata: { ws_sent: true, ws_send_error: false } });
        } catch (err) {
          const errMsg = getErrorMessage(err, t, 'chat.input.errors.websocketFailed', 'WebSocket 发送失败，请检查网络连接');
          updateMessageByClientMsgNo(nowId, { metadata: { ws_send_error: true, error_text: errMsg } });
          showApiError(showToast, err);
        }
      }).catch((err) => {
        const errorMessage = getErrorMessage(err);
        updateMessageByClientMsgNo(nowId, { metadata: { upload_status: 'error', error_text: errorMessage } });
        showApiError(showToast, err);
      });
    }

    // Clear previews after triggering sends
    setSelectedFiles([]);
  }, [selectedFiles, channelId, channelType, user?.id, addMessage, updateConversationLastMessage, moveConversationToTop, updateMessageByClientMsgNo, isConnected, sendWsMessage, showToast, showError, visitorExtra?.platform_type]);

  // Send rich text message with file attachment (text + file)
  const sendRichTextWithFile = useCallback(async (): Promise<void> => {
    const textContent = message.trim();
    const fileItem = selectedFiles[0];
    if (!fileItem || !textContent) return;

    if (!channelId || typeof channelType !== 'number') {
      showError(
        t('chat.input.errors.noConversationTitle', '请选择对话'),
        t('chat.input.errors.noConversationDesc.message', '请选择对话后再发送消息')
      );
      return;
    }

    const nowId = `local-rich-file-${Date.now()}`;
    const f = fileItem.file;

    const localMessage: Message = {
      id: nowId,
      type: 'staff',
      content: textContent,
      timestamp: new Date().toISOString(),
      messageId: nowId,
      clientMsgNo: nowId,
      messageSeq: 0,
      fromUid: user?.id ? `${user.id}-staff` : 'staff',
      channelId: channelId,
      channelType: channelType,
      payloadType: MessagePayloadType.RICH_TEXT,
      metadata: {
        isLocal: true,
        file_name: f.name,
        file_size: f.size,
        upload_status: 'uploading',
        upload_progress: 0,
        file: f as any,
      }
    };

    addMessage(localMessage);
    updateConversationLastMessage(channelId, channelType, localMessage);
    moveConversationToTop(channelId, channelType);

    try {
      const res = await uploadChatFileWithProgress(f, channelId, channelType, {
        onProgress: (p) => {
          updateMessageByClientMsgNo(nowId, {
            metadata: {
              upload_progress: p.progress,
              upload_status: p.status,
            }
          });
        }
      });

      const fileUrl = toAbsoluteApiUrl(res.file_url);
      updateMessageByClientMsgNo(nowId, {
        metadata: {
          file_url: fileUrl,
          upload_progress: 100,
          upload_status: 'completed',
        }
      });

      const payload = {
        type: MessagePayloadType.RICH_TEXT,
        content: textContent,
        images: [],
        file: {
          url: fileUrl,
          name: f.name,
          size: f.size,
        },
        timestamp: Date.now(),
      } as any;

      try {
        if (visitorExtra?.platform_type && visitorExtra.platform_type !== PlatformType.WEBSITE) {
          try {
            await chatMessagesApiService.staffSendPlatformMessage({
              channel_id: channelId,
              channel_type: channelType,
              payload,
              client_msg_no: nowId,
            });
          } catch (err) {
            const errMsg = err instanceof Error ? err.message : t('chat.input.errors.platformFailed', '平台消息发送失败，请稍后重试');
            updateMessageByClientMsgNo(nowId, { metadata: { platform_send_error: true, error_text: errMsg } });
            showApiError(showToast, err);
            return;
          }
        }
        if (!isConnected) throw new Error(t('chat.input.errors.websocketNotConnected.message', 'WebSocket 未连接，无法发送消息'));
        console.log("Sending rich text with file message via WebSocket", payload);
        await sendWsMessage(channelId, channelType, payload, nowId);
        updateMessageByClientMsgNo(nowId, { metadata: { ws_sent: true, ws_send_error: false } });
      } catch (err) {
        const errMsg = getErrorMessage(err, t, 'chat.input.errors.websocketFailed', 'WebSocket 发送失败，请检查网络连接');
        updateMessageByClientMsgNo(nowId, { metadata: { ws_send_error: true, error_text: errMsg } });
        showApiError(showToast, err);
      }
    } catch (err) {
      const errorMessage = getErrorMessage(err);
      updateMessageByClientMsgNo(nowId, { metadata: { upload_status: 'error', error_text: errorMessage } });
      showApiError(showToast, err);
      return;
    }

    setSelectedFiles([]);
    setMessage('');
  }, [selectedFiles, message, channelId, channelType, user?.id, addMessage, updateConversationLastMessage, moveConversationToTop, updateMessageByClientMsgNo, isConnected, sendWsMessage, showToast, showError, visitorExtra?.platform_type]);

  const sendRichTextWithImages = useCallback(async (): Promise<void> => {
    const items = [...pastedItems];
    if (!items.length) return;
    if (!channelId || typeof channelType !== 'number') {
      showError(
        t('chat.input.errors.noConversationTitle', '请选择对话'),
        t('chat.input.errors.noConversationDesc.image', '请选择对话后再发送图片')
      );
      return;
    }

    const nowId = `local-rich-${Date.now()}`;
    let imagesMeta = items.map(it => ({
      preview_url: it.previewUrl,
      width: it.width,
      height: it.height,
      file: it.file,
      upload_status: 'uploading',
      upload_progress: 0,
    }));

    const localMessage: Message = {
      id: nowId,
      type: 'staff',
      content: message.trim(),
      timestamp: new Date().toISOString(),
      messageId: nowId,
      clientMsgNo: nowId,
      messageSeq: 0,
      fromUid: user?.id ? `${user.id}-staff` : 'staff',
      channelId: channelId,
      channelType: channelType,
      payloadType: MessagePayloadType.RICH_TEXT,
      metadata: {
        isLocal: true,
        images: imagesMeta,
      }
    };

    addMessage(localMessage);
    updateConversationLastMessage(channelId, channelType, localMessage);
    moveConversationToTop(channelId, channelType);
    const finalUrls: (string | null)[] = new Array(items.length).fill(null);

    const uploadPromises = items.map((it, idx) =>
      uploadChatImageWithProgress(it.file, channelId, channelType, {


        onProgress: (p) => {
          imagesMeta = imagesMeta.map((img, i) => i === idx ? { ...img, upload_progress: p.progress, upload_status: p.status } : img);
          updateMessageByClientMsgNo(nowId, { metadata: { images: imagesMeta } });
          setPastedItems(prev => prev.map((pi, i) => i === idx ? { ...pi, progress: p.progress, status: p.status } : pi));
        }
      }).then((res) => {
        const url = toAbsoluteApiUrl(res.file_url);
        finalUrls[idx] = url;
        imagesMeta = imagesMeta.map((img, i) => i === idx ? { ...img, upload_progress: 100, upload_status: 'completed', url } : img);
        updateMessageByClientMsgNo(nowId, { metadata: { images: imagesMeta } });
      }).catch((err) => {
        const errorMessage = getErrorMessage(err);
        imagesMeta = imagesMeta.map((img, i) => i === idx ? { ...img, upload_status: 'error', error_text: errorMessage } : img);
        updateMessageByClientMsgNo(nowId, { metadata: { images: imagesMeta } });
        showApiError(showToast, err);
        throw err;
      })
    );

    try {
      await Promise.all(uploadPromises);
    } catch {
      // If any upload fails, don't send the rich text message
      return;
    }

    const imagesPayload = items.map((it, i) => ({ url: finalUrls[i] as string, width: it.width, height: it.height }));
    const payload = {
      type: MessagePayloadType.RICH_TEXT,
      content: message.trim(),
      images: imagesPayload,
      timestamp: Date.now(),
    } as any;

    try {
      if (visitorExtra?.platform_type && visitorExtra.platform_type !== PlatformType.WEBSITE) {
        try {
          await chatMessagesApiService.staffSendPlatformMessage({
            channel_id: channelId,
            channel_type: channelType,
            payload,
            client_msg_no: nowId,
          });
        } catch (err) {
          const errMsg = err instanceof Error ? err.message : t('chat.input.errors.platformFailed', '平台消息发送失败，请稍后重试');
          updateMessageByClientMsgNo(nowId, { metadata: { platform_send_error: true, error_text: errMsg } });
          showApiError(showToast, err);
          return;
        }
      }
      if (!isConnected) throw new Error(t('chat.input.errors.websocketNotConnected.richText', 'WebSocket 未连接，无法发送图文消息'));
      console.log("Sending rich text with images message via WebSocket", payload);
      await sendWsMessage(channelId, channelType, payload, nowId);
      updateMessageByClientMsgNo(nowId, { metadata: { ws_sent: true, ws_send_error: false } });
    } catch (err) {
      const errMsg = getErrorMessage(err, t, 'chat.input.errors.websocketFailed', 'WebSocket 发送失败，请检查网络连接');
      updateMessageByClientMsgNo(nowId, { metadata: { ws_send_error: true, error_text: errMsg } });
      showApiError(showToast, err);
    }

    setPastedItems([]);
    if (fileInputRef.current) fileInputRef.current.value = '';
    setMessage('');
  }, [pastedItems, channelId, channelType, user?.id, addMessage, updateConversationLastMessage, moveConversationToTop, updateMessageByClientMsgNo, isConnected, sendWsMessage, showToast, showError, message, visitorExtra?.platform_type]);

  const handleMessageChange = (e: React.ChangeEvent<HTMLTextAreaElement>): void => {
    setMessage(e.target.value);
  };

  // If visitor is in queued status, show accept button instead of input area
  if (isQueued && visitorId) {
    return (
      <footer className="p-4 border-t border-gray-200/80 dark:border-gray-700/80 bg-white/80 dark:bg-gray-800/80 backdrop-blur-lg sticky bottom-0 z-10">
        <div className="flex flex-col items-center justify-center py-6 space-y-3">
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {t('chat.input.accept.hint', '该访客正在等待接入')}
          </p>
          <button
            onClick={handleAcceptVisitor}
            disabled={isAccepting}
            className="flex items-center space-x-2 px-6 py-2.5 bg-green-500 hover:bg-green-600 disabled:bg-green-400 text-white text-sm font-medium rounded-lg transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2"
          >
            {isAccepting ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>{t('chat.input.accept.accepting', '接入中...')}</span>
              </>
            ) : (
              <>
                <UserPlus className="w-4 h-4" />
                <span>{t('chat.input.accept.button', '接入访客')}</span>
              </>
            )}
          </button>
        </div>
      </footer>
    );
  }

  // If conversation is closed, don't show input area
  if (isClosed) {
    return (
      <footer className="p-4 border-t border-gray-200/80 dark:border-gray-700/80 bg-white/80 dark:bg-gray-800/80 backdrop-blur-lg sticky bottom-0 z-10">
        <div className="flex items-center justify-center py-4">
          <p className="text-sm text-gray-400 dark:text-gray-500">
            {t('chat.input.closed', '会话已结束')}
          </p>
        </div>
      </footer>
    );
  }

  // If visitor is assigned to another staff, don't show input area
  // Only check when assignedStaffId exists and is not the current user
  const isNotMyVisitor = assignedStaffId && user?.id && assignedStaffId !== user.id;
  if (isNotMyVisitor) {
    const staffDisplayName = assignedStaffName || t('chat.input.otherAgent', '其他坐席');
    return (
      <footer className="p-4 border-t border-gray-200/80 dark:border-gray-700/80 bg-white/80 dark:bg-gray-800/80 backdrop-blur-lg sticky bottom-0 z-10">
        <div className="flex items-center justify-center py-4">
          <p className="text-sm text-gray-400 dark:text-gray-500">
            {t('chat.input.notMyVisitor', '该访客已分配给 {{name}}', { name: staffDisplayName })}
          </p>
        </div>
      </footer>
    );
  }

  return (
    <footer className="p-4 border-t border-gray-200/80 dark:border-gray-700/80 bg-white/80 dark:bg-gray-800/80 backdrop-blur-lg sticky bottom-0 z-10">


      {/* Toolbar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <button
            ref={emojiBtnRef}
            onClick={() => { if (isManualDisabled) return; setShowEmoji(v => !v); }}
            disabled={isManualDisabled}
            className="p-1.5 text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 transition-colors duration-200 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
            aria-label={t('chat.input.emoji.aria', '打开表情选择器')}
            title={isManualDisabled ? t('chat.input.disabled.tooltip', 'AI助手已启用，手动输入已禁用') : t('chat.input.emoji.title', '插入表情')}
          >
            <Smile className="w-6 h-6" />
          </button>
          <button
            ref={screenshotBtnRef}
            onClick={() => { if (isManualDisabled) return; handleClickScreenshotBtn(); }}
            disabled={isManualDisabled}
            className="p-1.5 text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 transition-colors duration-200 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
            aria-label={t('chat.input.screenshot.aria', '截图粘贴说明')}
            title={isManualDisabled ? t('chat.input.disabled.tooltip', 'AI助手已启用，手动输入已禁用') : t('chat.input.screenshot.title', '截图')}
          >
            <Scissors className="w-6 h-6" />
          </button>
          <button onClick={handleClickImageBtn} disabled={isManualDisabled} className="p-1.5 text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 transition-colors duration-200 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed" aria-label={t('chat.input.image.aria', '上传图片')} title={isManualDisabled ? t('chat.input.disabled.tooltip', 'AI助手已启用，手动输入已禁用') : t('chat.input.image.title', '发送图片')}>
            <ImageIcon className="w-6 h-6" />
          </button>
          <button onClick={handleClickFileBtn} disabled={isManualDisabled} className="p-1.5 text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 transition-colors duration-200 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed" aria-label={t('chat.input.file.aria', '上传文件')} title={isManualDisabled ? t('chat.input.disabled.tooltip', 'AI助手已启用，手动输入已禁用') : t('chat.input.file.title', '发送文件')}>
            <Folder className="w-6 h-6" />
          </button>
          {/* <button className="p-1.5 text-gray-500 hover:text-gray-700 transition-colors duration-200">
            <Ellipsis className="w-6 h-6" />
          </button> */}
        </div>

      {/* Hidden file input for image selection */}
      <input ref={fileInputRef} type="file" accept="image/*" multiple className="hidden" onChange={handleImageChange} disabled={isManualDisabled} />

      {/* Hidden file input for document/file selection */}
      <input
        ref={fileDocInputRef}
        type="file"
        accept=".pdf,application/pdf,.doc,application/msword,.docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document,.xls,application/vnd.ms-excel,.xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,.ppt,application/vnd.ms-powerpoint,.pptx,application/vnd.openxmlformats-officedocument.presentationml.presentation,.txt,text/plain,.csv,text/csv,.md,text/markdown,.zip,application/zip,.rar,application/x-rar-compressed,.7z,application/x-7z-compressed"
        multiple
        className="hidden"
        onChange={handleFileChange}
        disabled={isManualDisabled}
      />

        {/* AI 助手开关 - agent/team 会话时不显示 */}
        {!isAIChat && (
          <div className="flex items-center space-x-2" title={isAIEnabled ? t('chat.input.ai.enabled', 'AI已启用') : t('chat.input.ai.disabled', 'AI已禁用')}>
            <span className="text-xs text-gray-600 dark:text-gray-400 select-none">{t('chat.input.ai.label', 'AI助手')}</span>
            <Toggle
              aria-label={t('chat.input.ai.toggleAria', '切换AI助手')}
              checked={isAIEnabled}
              onChange={handleChangeAI}
              disabled={!visitorId || isTogglingAI}
            />
          </div>
        )}
      </div>

      {showEmoji && (
        <EmojiPickerPopover
          anchorRef={emojiBtnRef}

          onSelect={(emoji) => { insertEmoji(emoji); setShowEmoji(false); }}
          onClose={() => setShowEmoji(false)}
        />
      )}
      {showScreenshotTip && (
        <>
          {createPortal(
            <div className="fixed inset-0 z-[999]" onClick={() => setShowScreenshotTip(false)} aria-hidden="true" />,
            document.body
          )}
          {createPortal(
            <div
              className="fixed z-[1000] w-80 bg-white dark:bg-gray-900 rounded-md shadow-lg border border-gray-200 dark:border-gray-700"
              style={{ top: screenshotTipPos.top, left: screenshotTipPos.left, width: TIP_WIDTH }}
              role="dialog"
              aria-label={t('chat.input.screenshotTip.aria', '截图发送提示')}
            >
              <div className="p-3">
                <div className="flex items-center justify-between mb-2">


                  <span className="text-sm font-medium text-gray-900 dark:text-gray-100">{t('chat.input.screenshotTip.title', '截图发送小提示')}</span>
                  <button
                    className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                    aria-label={t('common.close', '关闭')}
                    onClick={() => setShowScreenshotTip(false)}
                  >
                    ×
                  </button>
                </div>
                <div className="text-xs text-gray-700 dark:text-gray-200 leading-relaxed">
                  <p>{t('chat.input.screenshotTip.line1', '您可以使用 QQ、微信 或 系统自带的截图工具 截图后，')}</p>
                  <p>
                    {t('chat.input.screenshotTip.line2.prefix', '在消息输入框中按')}
                    <span className="mx-1 inline-block font-mono text-[11px] px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-800 border border-gray-200 dark:border-gray-700">
                      {isMac ? '⌘ + V' : 'Ctrl + V'}
                    </span>
                    {isMac && (
                      <>
                        {t('common.or', '或')}
                        <span className="ml-1 inline-block font-mono text-[11px] px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-800 border border-gray-200 dark:border-gray-700">Cmd + V</span>
                      </>
                    )}
                    {t('chat.input.screenshotTip.line2.suffix', '粘贴发送图片')}
                  </p>
                </div>
              </div>
            </div>,
            document.body
          )}
        </>
      )}





      {/* Selected files preview (documents) */}
      {selectedFiles.length > 0 && (
        <div className="mt-2">
          <ul className="space-y-2">
            {selectedFiles.map((sf) => (
              <li key={sf.id} className="flex items-center justify-between rounded-md border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2">
                <div className="flex items-center space-x-3 min-w-0">
                  {getFileIcon(sf.file.name, 'w-5 h-5')}
                  <span className="text-sm text-gray-800 dark:text-gray-100 truncate max-w-[280px]">{sf.file.name}</span>
                  <span className="text-xs text-gray-500 dark:text-gray-400 flex-shrink-0">{formatBytes(sf.file.size)}</span>
                </div>
                <button
                  onClick={() => removeSelectedFile(sf.id)}
                  className="text-gray-400 hover:text-red-500 text-sm"
                  aria-label={t('chat.input.file.remove', '移除文件')}
                  title={t('chat.input.file.remove', '移除文件')}
                >
                  ×
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Pasted images preview (multiple) */}
      {pastedItems.length > 0 && (
        <div className="mt-2">
          {(() => {
            const count = pastedItems.length;
            const gridColsClass = count === 1 ? 'grid-cols-1' : count === 2 ? 'grid-cols-2' : 'grid-cols-3';
            const getGridItemClass = (idx: number): string => {
              if (count >= 3) {
                const remainder = count % 3;
                if (remainder === 1 && idx === count - 1) return 'col-start-2'; // 4/7 center single
                // 5/8: left-align last row (no override)
              }
              return '';
            };
            return (
              <div className={`grid ${gridColsClass} gap-2 w-fit`}>
                {pastedItems.map((it, idx) => (
                  <div key={idx} className={"relative rounded-md overflow-hidden border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 " + getGridItemClass(idx)}>
                    <img src={it.previewUrl} alt={t('chat.input.preview.imageAlt', '预览图片{{index}}', { index: idx + 1 })} className="w-[100px] h-[100px] object-cover" />
                    {/* Progress overlay */}
                    {it.status && it.status !== 'idle' && it.status !== 'completed' && (
                      <div className="absolute inset-0 bg-black/40 flex items-center justify-center">
                        <span className="text-white text-xs">{Math.round(it.progress || 0)}%</span>
                      </div>
                    )}
                    {it.status === 'error' && (
                      <div className="absolute inset-0 bg-red-500/20 flex items-center justify-center text-red-700 text-xs text-center px-1 leading-5">
                        {t('chat.input.upload.failed', '上传失败')}
                      </div>
                    )}
                    <button
                      onClick={() => removePastedItem(idx)}
                      className="absolute -top-2 -right-2 bg-black/60 text-white rounded-full w-6 h-6 leading-6 text-center text-xs hover:bg-black/80"
                      aria-label={t('chat.input.preview.removeAria', '移除预览')}
                    >
                      ×
                    </button>
                  </div>
                ))}
              </div>
            );
          })()}
        </div>
      )}

      {/* Message input */}
      <div className="mt-2">
        <textarea
          ref={textareaRef}
          placeholder={isManualDisabled ? t('chat.input.disabled.placeholder', 'AI助手已启用，无法手动输入') : t('chat.input.placeholder', '输入消息...')}
          rows={2}
          value={message}
          onChange={handleMessageChange}
          onKeyDown={handleKeyPress}
          onPaste={handlePaste}
          onCompositionStart={handleCompositionStart}
          onCompositionEnd={handleCompositionEnd}
          readOnly={isSending || isSendingLocal || isManualDisabled}
          disabled={isManualDisabled}
          title={isManualDisabled ? t('chat.input.disabled.placeholder', 'AI助手已启用，无法手动输入') : undefined}
          className={`w-full text-sm p-2 border border-transparent rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 dark:focus:ring-blue-400 resize-none bg-transparent dark:text-gray-200 ${
            isSending || isSendingLocal || isManualDisabled ? 'opacity-50 cursor-not-allowed' : ''
          }`}
        />
      </div>

      {/* Send controls */}
      <div className="flex justify-end mt-1">
        <button className="text-xs text-gray-500 dark:text-gray-400 hover:text-blue-600 dark:hover:text-blue-400 mr-2" title={isManualDisabled ? t('chat.input.disabled.tooltip', 'AI助手已启用，手动输入已禁用') : undefined}>
          {t('chat.input.shortcuts.sendWithHint', 'Enter 发送 • {{hint}}', { hint: newlineHint })}
        </button>
        {isStreamingInProgress ? (
          <button
            className="px-4 py-1 text-white text-sm rounded-md focus:outline-none focus:ring-2 focus:ring-orange-500 dark:focus:ring-orange-400 focus:ring-offset-1 transition-colors duration-200 bg-orange-500 hover:bg-orange-600 dark:bg-orange-600 dark:hover:bg-orange-700 flex items-center space-x-1.5"
            onMouseDown={(e) => e.preventDefault()}
            onClick={handleCancelStream}
            title={t('chat.input.streaming.pauseTooltip', '暂停流消息')}
          >
            <Pause className="w-4 h-4" />
            <span>{t('chat.input.streaming.pause', '暂停')}</span>
          </button>
        ) : (
          <button
            className={`px-4 py-1 text-white text-sm rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:focus:ring-blue-400 focus:ring-offset-1 transition-colors duration-200 ${
              isSending || isSendingLocal || isManualDisabled
                ? 'bg-gray-400 dark:bg-gray-600 cursor-not-allowed'
                : (message.trim() || pastedItems.length > 0 || selectedFiles.length > 0)
                ? 'bg-blue-500 hover:bg-blue-600 dark:bg-blue-600 dark:hover:bg-blue-700'
                : 'bg-gray-400 dark:bg-gray-600 cursor-not-allowed'
            }`}
            onMouseDown={(e) => e.preventDefault()}
            onClick={handleSend}
            disabled={(!message.trim() && pastedItems.length === 0 && selectedFiles.length === 0) || isSending || isSendingLocal || isManualDisabled}
            title={isManualDisabled ? t('chat.input.disabled.cannotSendTooltip', 'AI助手已启用，无法手动发送') : undefined}
          >
            {isSending || isSendingLocal ? t('chat.input.send.sending', '发送中...') : t('chat.input.send.label', '发送')}
          </button>
        )}
      </div>
    </footer>
  );
};

export default MessageInput;
