import { WKIM, WKIMEvent, ReasonCode } from 'easyjssdk';
import type { RecvMessage, EventNotification } from 'easyjssdk';
import { loadConfig, resolveServer } from './config.js';

const isDebug = !!process.env.TGO_DEBUG;

const _origConsoleLog = console.log;
const _origConsoleWarn = console.warn;
const _origConsoleDebug = console.debug;

function suppressSDKLogs(): void {
  if (isDebug) return;
  console.log = () => {};
  console.warn = () => {};
  console.debug = () => {};
}

export function restoreSDKLogs(): void {
  console.log = _origConsoleLog;
  console.warn = _origConsoleWarn;
  console.debug = _origConsoleDebug;
}

export interface WuKongIMSendResult {
  messageId: string;
  messageSeq: number;
  reasonCode: number;
}

export interface WuKongIMRecvMessage {
  messageId: string;
  messageSeq: number;
  timestamp: number;
  channelId: string;
  channelType: number;
  fromUid: string;
  payload: unknown;
  clientMsgNo?: string;
}

export interface WuKongIMEvent {
  id: string;
  type: string;
  timestamp: number;
  data: unknown;
}

type MessageHandler = (msg: WuKongIMRecvMessage) => void;
type EventHandler = (evt: WuKongIMEvent) => void;

/**
 * WuKongIM WebSocket client for tgo-widget-cli.
 * Visitor mode: uid = platform_open_id, token = im_token (from register response).
 * No -staff suffix, no JWT — uses im_token directly.
 */
export class WuKongIMClient {
  private im?: WKIM;
  private _uid?: string;
  private _isConnected = false;
  private messageHandlers: MessageHandler[] = [];
  private eventHandlers: EventHandler[] = [];

  get isConnected(): boolean {
    return this._isConnected;
  }

  get uid(): string | undefined {
    return this._uid;
  }

  /**
   * Connect to WuKongIM WebSocket in visitor mode.
   * @param serverUrl API server URL for route resolution
   * @param uid platform_open_id from visitor register
   * @param imToken im_token from visitor register
   */
  async connect(params: { serverUrl: string; uid: string; imToken: string }): Promise<void> {
    if (this._isConnected && this.im) {
      return;
    }

    this._uid = params.uid;

    // Resolve WebSocket route
    const routeUrl = `${params.serverUrl.replace(/\/+$/, '')}/v1/wukongim/route?uid=${encodeURIComponent(params.uid)}`;
    const routeRes = await fetch(routeUrl);
    if (!routeRes.ok) {
      throw new Error(`Failed to resolve WuKongIM route: ${routeRes.status}`);
    }
    const route = await routeRes.json() as { tcp_addr: string; ws_addr: string; wss_addr: string };

    let wsUrl = route.wss_addr || route.ws_addr;
    if (wsUrl && !wsUrl.includes('://')) {
      wsUrl = `ws://${wsUrl}`;
    }
    if (!wsUrl) {
      throw new Error('No WebSocket address returned from route API');
    }

    suppressSDKLogs();

    this.im = WKIM.init(wsUrl, { uid: params.uid, token: params.imToken }, {});
    this.setupListeners();

    const timeout = new Promise<never>((_, reject) =>
      setTimeout(() => reject(new Error('WuKongIM connection timeout (10s)')), 10000),
    );
    await Promise.race([this.im!.connect(), timeout]);
    this._isConnected = true;
  }

  async send(
    channelId: string,
    channelType: number,
    payload: object,
    clientMsgNo?: string,
  ): Promise<WuKongIMSendResult> {
    if (!this.im || !this._isConnected) {
      throw new Error('WuKongIM not connected. Call connect() first.');
    }

    const opts: { clientMsgNo?: string } = {};
    if (clientMsgNo) opts.clientMsgNo = clientMsgNo;

    const result = await this.im!.send(channelId, channelType, payload, opts);

    if (result.reasonCode !== ReasonCode.Success) {
      const msg = REASON_CODE_MESSAGES[result.reasonCode] || `Send failed (code: ${result.reasonCode})`;
      throw new Error(msg);
    }

    return {
      messageId: result.messageId,
      messageSeq: result.messageSeq,
      reasonCode: result.reasonCode,
    };
  }

  onMessage(handler: MessageHandler): () => void {
    this.messageHandlers.push(handler);
    return () => {
      const idx = this.messageHandlers.indexOf(handler);
      if (idx > -1) this.messageHandlers.splice(idx, 1);
    };
  }

  onEvent(handler: EventHandler): () => void {
    this.eventHandlers.push(handler);
    return () => {
      const idx = this.eventHandlers.indexOf(handler);
      if (idx > -1) this.eventHandlers.splice(idx, 1);
    };
  }

  disconnect(): void {
    if (this.im) {
      try {
        this.im.disconnect();
      } catch {
        // Ignore close errors
      }
      this.im = undefined;
    }
    this._isConnected = false;
    this._uid = undefined;
    restoreSDKLogs();
  }

  private setupListeners(): void {
    if (!this.im) return;

    this.im.on(WKIMEvent.Connect, () => {
      this._isConnected = true;
    });

    this.im.on(WKIMEvent.Disconnect, () => {
      this._isConnected = false;
    });

    this.im.on(WKIMEvent.Message, (msg: RecvMessage) => {
      const converted: WuKongIMRecvMessage = {
        messageId: msg.messageId,
        messageSeq: msg.messageSeq,
        timestamp: msg.timestamp,
        channelId: msg.channelId,
        channelType: msg.channelType,
        fromUid: msg.fromUid,
        payload: msg.payload,
        clientMsgNo: msg.clientMsgNo,
      };
      for (const handler of this.messageHandlers) {
        try { handler(converted); } catch { /* ignore */ }
      }
    });

    this.im.on(WKIMEvent.CustomEvent, (evt: EventNotification) => {
      const converted: WuKongIMEvent = {
        id: evt.id,
        type: evt.type,
        timestamp: evt.timestamp,
        data: typeof evt.data === 'string' ? tryParseJSON(evt.data) : evt.data,
      };
      for (const handler of this.eventHandlers) {
        try { handler(converted); } catch { /* ignore */ }
      }
    });

    this.im.on(WKIMEvent.Error, (error: unknown) => {
      this._isConnected = false;
      if (process.env.TGO_DEBUG) {
        console.error('[wukongim] error:', error);
      }
    });
  }
}

// Singleton
let _sharedClient: WuKongIMClient | undefined;

export function getSharedWuKongIMClient(): WuKongIMClient {
  if (!_sharedClient) {
    _sharedClient = new WuKongIMClient();
  }
  return _sharedClient;
}

/**
 * Ensure the shared WuKongIM client is connected.
 * Reads uid (platform_open_id) and imToken from config.
 */
export async function ensureWuKongIMConnected(serverUrl?: string): Promise<WuKongIMClient> {
  const wkim = getSharedWuKongIMClient();
  if (!wkim.isConnected) {
    const config = loadConfig();
    const server = serverUrl || resolveServer();
    if (!server) throw new Error('No server configured. Run: tgo-widget init');
    if (!config.platform_open_id) throw new Error('No platform_open_id. Run: tgo-widget init');
    if (!config.im_token) throw new Error('No im_token. Run: tgo-widget init');

    await wkim.connect({
      serverUrl: server,
      uid: config.platform_open_id,
      imToken: config.im_token,
    });

    const cleanup = () => { wkim.disconnect(); };
    process.once('exit', cleanup);
    process.once('SIGINT', () => { cleanup(); process.exit(0); });
    process.once('SIGTERM', () => { cleanup(); process.exit(0); });
  }
  return wkim;
}

function tryParseJSON(str: string): unknown {
  try { return JSON.parse(str); } catch { return str; }
}

const REASON_CODE_MESSAGES: Record<number, string> = {
  [ReasonCode.Unknown]: 'Unknown error',
  [ReasonCode.AuthFail]: 'Authentication failed',
  [ReasonCode.SubscriberNotExist]: 'Subscriber not exist',
  [ReasonCode.InBlacklist]: 'In blacklist',
  [ReasonCode.ChannelNotExist]: 'Channel not exist',
  [ReasonCode.UserNotOnNode]: 'User not on node',
  [ReasonCode.SenderOffline]: 'Sender offline',
  [ReasonCode.PayloadDecodeError]: 'Payload decode error',
  [ReasonCode.NotAllowSend]: 'Not allowed to send',
  [ReasonCode.ConnectKick]: 'Connection kicked',
  [ReasonCode.NotInWhitelist]: 'Not in whitelist',
  [ReasonCode.SystemError]: 'System error',
  [ReasonCode.ChannelIDError]: 'Channel ID error',
  [ReasonCode.Ban]: 'Channel banned',
  [ReasonCode.RateLimit]: 'Rate limited',
  [ReasonCode.NotSupportChannelType]: 'Unsupported channel type',
  [ReasonCode.Disband]: 'Channel disbanded',
  [ReasonCode.SendBan]: 'Send banned',
};
