import { MessagePayloadType, isSystemMessageType, type Chat, type PayloadSystem } from '@/types';
import type { TFunction } from 'i18next';

/**
 * Formats the last message of a chat for display in the conversation list,
 * with support for internationalization and system message templates.
 * 
 * @param chat The chat object
 * @param t i18next translation function
 * @returns Formatted localized string
 */
export function formatChatLastMessage(chat: Chat, t: TFunction): string {
  const { lastMessage, payloadType, lastPayload } = chat;

  // 1. Handle STREAM messages
  if (payloadType === MessagePayloadType.STREAM && !lastMessage) {
    return t('chat.status.ai_typing', 'AI 正在输入...');
  }

  // 2. Handle SYSTEM messages (1000-2000)
  if (typeof payloadType === 'number' && isSystemMessageType(payloadType) && lastPayload) {
    const payload = lastPayload as PayloadSystem;
    const hasExtra = payload.extra && payload.extra.length > 0;

    switch (payloadType) {
      case MessagePayloadType.SYSTEM_STAFF_ASSIGNED:
        return formatSystemTemplate(
          t('chat.messages.system.staffAssigned', 'You have been connected to customer service. Agent {0} will assist you.'),
          payload.extra
        );
      case MessagePayloadType.SESSION_TRANSFERRED:
        return formatSystemTemplate(
          t('chat.messages.system.sessionTransferred', 'Session transferred. Agent {0} has transferred you to Agent {1}.'),
          payload.extra
        );
      case MessagePayloadType.SYSTEM_SESSION_CLOSED:
        if (!hasExtra) {
          return t('chat.messages.system.sessionClosedEmpty', 'Session ended.');
        }
        return formatSystemTemplate(
          t('chat.messages.system.sessionClosed', 'Session ended. Agent {0} has completed the service.'),
          payload.extra
        );
      case MessagePayloadType.MEMORY_CLEARED:
        return t('chat.messages.system.memoryCleared', 'Memory cleared, AI will restart the conversation');
      default:
        // For other system messages, use the template from payload or fallback to lastMessage
        if (payload.content) {
          return formatSystemTemplate(payload.content, payload.extra);
        }
    }
  }

  // 3. Fallback to the stored lastMessage string
  // Strip json-render spec fences so raw JSON patches don't leak into the preview
  const cleaned = stripSpecFences(lastMessage || '');
  // If content is empty after stripping (e.g., message was entirely a json-render UI card),
  // show a generic placeholder instead of blank
  return cleaned || (lastMessage ? t('chat.messages.aiReply', '[AI 回复]') : '');
}

/** Remove ```spec...``` fences (and unclosed trailing fences) from text. */
function stripSpecFences(text: string): string {
  if (!text.includes('```spec')) return text;
  return text.replace(/```spec[\s\S]*?```/g, '').replace(/```spec[\s\S]*/g, '').trim();
}

/**
 * Internal helper to format system message templates with {0}, {1} etc.
 */
function formatSystemTemplate(template: string, extra?: any[]): string {
  if (!template) return '';
  if (!extra || extra.length === 0) return template;

  return template.replace(/\{(\d+)\}/g, (match, index) => {
    const idx = parseInt(index, 10);
    const item = extra[idx];
    return item?.name || match;
  });
}
