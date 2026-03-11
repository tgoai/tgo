/**
 * Action URI 解析和处理
 * 
 * 支持的协议：
 * - url://  打开外部链接
 * - msg://  发送消息到聊天
 * - copy:// 复制到剪贴板
 */

/**
 * Action 协议类型
 */
export type ActionProtocol = 'url' | 'msg' | 'copy';

/**
 * 解析后的 Action URI
 */
export interface ParsedActionURI {
  /** 协议类型 */
  protocol: ActionProtocol | string;
  /** 内容部分 */
  content: string;
  /** 原始 URI */
  raw: string;
  /** 是否为有效的 Action URI */
  isValid: boolean;
}

/**
 * Action URI 正则表达式
 */
const ACTION_URI_REGEX = /^([a-z]+):\/\/(.*)$/i;

/**
 * 有效的协议列表
 */
const VALID_PROTOCOLS: ActionProtocol[] = ['url', 'msg', 'copy'];

/**
 * 解析 Action URI
 * @param uri Action URI 字符串
 * @returns 解析结果
 */
export function parseActionURI(uri: string): ParsedActionURI {
  if (!uri) {
    return { protocol: '', content: '', raw: uri, isValid: false };
  }

  const match = uri.match(ACTION_URI_REGEX);

  if (!match) {
    return { protocol: '', content: '', raw: uri, isValid: false };
  }

  const [, protocol, content] = match;
  const normalizedProtocol = protocol.toLowerCase();

  return {
    protocol: normalizedProtocol,
    content: content || '',
    raw: uri,
    isValid: VALID_PROTOCOLS.includes(normalizedProtocol as ActionProtocol),
  };
}

/**
 * 构建 Action URI
 * @param protocol 协议类型
 * @param content 内容
 * @returns Action URI 字符串
 */
export function buildActionURI(protocol: ActionProtocol, content: string): string {
  return `${protocol}://${content}`;
}

/**
 * 检查是否为有效的 Action URI
 * @param uri URI 字符串
 */
export function isValidActionURI(uri: string): boolean {
  return parseActionURI(uri).isValid;
}

/**
 * Action 处理结果
 */
export interface ActionResult {
  success: boolean;
  message?: string;
  error?: string;
}

/**
 * Action 处理器配置
 */
export interface ActionHandlerConfig {
  /** 发送消息的回调 */
  onSendMessage?: (message: string) => void;
  /** 复制成功的回调 */
  onCopySuccess?: (text: string) => void;
  /** 复制失败的回调 */
  onCopyError?: (error: Error) => void;
  /** 打开链接前的回调（返回 false 可阻止打开） */
  onBeforeOpenUrl?: (url: string) => boolean;
  /** 处理未知协议的回调 */
  onUnknownProtocol?: (uri: ParsedActionURI) => void;
}

/**
 * 执行 Action
 * @param uri Action URI
 * @param config 处理器配置
 * @returns 处理结果
 */
export async function executeAction(
  uri: string,
  config: ActionHandlerConfig = {}
): Promise<ActionResult> {
  const parsed = parseActionURI(uri);

  if (!parsed.isValid) {
    // 尝试作为旧格式处理（直接的 action 名称）
    config.onUnknownProtocol?.(parsed);
    return {
      success: false,
      error: `无效的 Action URI: ${uri}`,
    };
  }

  switch (parsed.protocol as ActionProtocol) {
    case 'url': {
      // 打开外部链接
      const url = parsed.content;
      if (config.onBeforeOpenUrl && !config.onBeforeOpenUrl(url)) {
        return { success: false, message: '链接打开被阻止' };
      }
      try {
        const newWindow = window.open(url, '_blank', 'noopener,noreferrer');
        if (!newWindow) {
          console.warn('[executeAction] Popup may have been blocked');
        }
        return { success: true, message: `已打开链接: ${url}` };
      } catch (error) {
        console.error('[executeAction] Failed to open URL:', error);
        return { success: false, error: `无法打开链接: ${error}` };
      }
    }

    case 'msg': {
      // 发送消息到聊天
      const message = decodeURIComponent(parsed.content);
      if (config.onSendMessage) {
        config.onSendMessage(message);
        return { success: true, message: `已发送消息` };
      }
      return { success: false, error: '未配置消息发送处理器' };
    }

    case 'copy': {
      // 复制到剪贴板
      const text = decodeURIComponent(parsed.content);
      try {
        await navigator.clipboard.writeText(text);
        config.onCopySuccess?.(text);
        return { success: true, message: `已复制: ${text}` };
      } catch (error) {
        const err = error instanceof Error ? error : new Error(String(error));
        config.onCopyError?.(err);
        return { success: false, error: `复制失败: ${err.message}` };
      }
    }

    default:
      config.onUnknownProtocol?.(parsed);
      return { success: false, error: `未知协议: ${parsed.protocol}` };
  }
}

/**
 * 创建 Action 处理器
 * 用于在组件中处理 Widget 操作按钮点击
 */
export function createActionHandler(config: ActionHandlerConfig = {}) {
  return async (actionUri: string): Promise<ActionResult> => {
    return executeAction(actionUri, config);
  };
}
