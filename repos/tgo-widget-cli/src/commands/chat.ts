import { Command } from 'commander';
import { readFileSync } from 'node:fs';
import { basename } from 'node:path';
import { TgoWidgetClient } from '../client.js';
import { loadConfig, resolveOutput, resolveServer, resolveApiKey } from '../config.js';
import { printError, printResult } from '../output.js';
import { ensureWuKongIMConnected, getSharedWuKongIMClient } from '../wukongim.js';

function makeClient(globals: Record<string, string>) {
  return new TgoWidgetClient({ server: resolveServer(globals.server), apiKey: resolveApiKey(globals.apiKey) });
}

export function registerChatCommands(parent: Command): void {
  const chat = parent.command('chat').description('Chat messaging');

  chat
    .command('send')
    .description('Send a message and get AI response (SSE streaming by default)')
    .requiredOption('-m, --message <text>', 'Message text')
    .option('--no-stream', 'Disable streaming, return JSON')
    .action(async (opts, cmd) => {
      const globals = cmd.parent!.parent!.opts();
      const format = resolveOutput(globals.output);
      try {
        const result = await chatSend({
          server: globals.server,
          apiKey: globals.apiKey,
          message: opts.message,
          stream: opts.stream !== false,
        });
        if (!opts.stream || opts.stream === false) {
          printResult(result, format);
        }
        // In stream mode, output is already written to stdout
      } catch (err) {
        printError(err, format);
      }
    });

  chat
    .command('send-ws')
    .description('Send a message via WuKongIM WebSocket (raw IM, no AI reply)')
    .requiredOption('-m, --message <text>', 'Message text')
    .action(async (opts, cmd) => {
      const globals = cmd.parent!.parent!.opts();
      const format = resolveOutput(globals.output);
      let result: unknown;
      let error: unknown;
      try {
        result = await chatSendWs({
          server: globals.server,
          message: opts.message,
        });
      } catch (err) {
        error = err;
      }
      getSharedWuKongIMClient().disconnect();
      if (error) {
        printError(error, format);
      } else {
        printResult(result, format);
      }
    });

  chat
    .command('listen')
    .description('Listen for incoming messages via WuKongIM (JSONL output)')
    .option('--events', 'Also print custom events')
    .action(async (opts, cmd) => {
      const globals = cmd.parent!.parent!.opts();
      try {
        await chatListen({
          server: globals.server,
          includeEvents: opts.events,
        });
      } catch (err) {
        printError(err, resolveOutput(globals.output));
      }
    });

  chat
    .command('history')
    .description('Get message history')
    .option('-l, --limit <n>', 'Max messages', '20')
    .option('--start-seq <n>', 'Start message sequence number')
    .action(async (opts, cmd) => {
      const globals = cmd.parent!.parent!.opts();
      const format = resolveOutput(globals.output);
      try {
        const result = await chatHistory({
          server: globals.server,
          apiKey: globals.apiKey,
          limit: parseInt(opts.limit),
          startSeq: opts.startSeq ? parseInt(opts.startSeq) : undefined,
        });
        printResult(result, format);
      } catch (err) {
        printError(err, format);
      }
    });

  chat
    .command('upload <file>')
    .description('Upload a file')
    .action(async (file, _opts, cmd) => {
      const globals = cmd.parent!.parent!.opts();
      const format = resolveOutput(globals.output);
      try {
        const result = await chatUpload({
          server: globals.server,
          apiKey: globals.apiKey,
          filePath: file,
        });
        printResult(result, format);
      } catch (err) {
        printError(err, format);
      }
    });
}

// -- Action functions (shared by CLI + MCP) --

/**
 * Send a message via /v1/chat/completion.
 * Stream mode (default): SSE streaming to stdout, returns accumulated text.
 * Non-stream mode: returns full JSON response.
 */
export async function chatSend(params: {
  server?: string;
  apiKey?: string;
  message: string;
  stream?: boolean;
}): Promise<unknown> {
  const config = loadConfig();
  const server = params.server || resolveServer();
  const apiKey = params.apiKey || resolveApiKey();
  if (!server) throw new Error('No server configured. Run: tgo-widget init');
  if (!apiKey) throw new Error('No API key configured. Run: tgo-widget init');
  if (!config.platform_open_id) throw new Error('No platform_open_id. Run: tgo-widget init');

  const client = new TgoWidgetClient({ server, apiKey });

  const body: Record<string, unknown> = {
    api_key: apiKey,
    message: params.message,
    from_uid: config.platform_open_id,
    stream: params.stream !== false,
  };
  if (config.channel_id) body.channel_id = config.channel_id;
  if (config.channel_type != null) body.channel_type = config.channel_type;

  if (params.stream === false) {
    // Non-streaming mode
    return client.postPublic('/v1/chat/completion', body);
  }

  // Streaming mode — SSE
  let accumulated = '';
  await client.stream('/v1/chat/completion', body, {
    onMessage: (event, data) => {
      if (!data || typeof data !== 'object') return;
      const d = data as Record<string, unknown>;
      const eventType = (d.event_type as string) || event;

      if (eventType === 'team_run_content') {
        // SSE structure: { event_type, data: { data: { content } } }
        const mid = d.data as Record<string, unknown> | undefined;
        const inner = mid?.data as Record<string, unknown> | undefined;
        const content = (inner?.content ?? mid?.content ?? '') as string;
        if (content) {
          process.stdout.write(content);
          accumulated += content;
        }
      } else if (eventType === 'error') {
        const mid = d.data as Record<string, unknown> | undefined;
        const errMsg = mid?.message || d.message || JSON.stringify(data);
        process.stderr.write(`\nStream error: ${errMsg}\n`);
      }
    },
    onClose: () => {
      // Add newline after stream
      if (accumulated) process.stdout.write('\n');
    },
  });

  return { content: accumulated, stream: true };
}

/**
 * Send a message via WuKongIM WebSocket (raw IM, no AI reply).
 */
export async function chatSendWs(params: {
  server?: string;
  message: string;
}): Promise<unknown> {
  const config = loadConfig();
  if (!config.channel_id) throw new Error('No channel_id. Run: tgo-widget init');
  if (config.channel_type == null) throw new Error('No channel_type. Run: tgo-widget init');

  const wkim = await ensureWuKongIMConnected(params.server);
  const payload = { content: params.message, type: 1 };
  const clientMsgNo = generateClientMsgNo();

  const result = await wkim.send(config.channel_id, config.channel_type, payload, clientMsgNo);

  return {
    messageId: result.messageId,
    messageSeq: result.messageSeq,
    clientMsgNo,
    status: 'sent',
  };
}

/**
 * Listen for incoming messages via WuKongIM WebSocket.
 * Outputs JSONL to stdout. Runs until Ctrl+C.
 */
export async function chatListen(params?: {
  server?: string;
  includeEvents?: boolean;
}): Promise<void> {
  const wkim = await ensureWuKongIMConnected(params?.server);

  console.error(`Connected as ${wkim.uid}. Listening for messages... (Ctrl+C to stop)`);

  wkim.onMessage((msg) => {
    const line = JSON.stringify({
      type: 'message',
      messageId: msg.messageId,
      messageSeq: msg.messageSeq,
      timestamp: msg.timestamp,
      channelId: msg.channelId,
      channelType: msg.channelType,
      fromUid: msg.fromUid,
      payload: msg.payload,
      clientMsgNo: msg.clientMsgNo,
    });
    console.log(line);
  });

  if (params?.includeEvents) {
    wkim.onEvent((evt) => {
      const line = JSON.stringify({
        type: 'event',
        id: evt.id,
        eventType: evt.type,
        timestamp: evt.timestamp,
        data: evt.data,
      });
      console.log(line);
    });
  }

  // Keep alive
  await new Promise<void>(() => {});
}

/**
 * Get message history via POST /v1/visitors/messages/sync.
 */
export async function chatHistory(params: {
  server?: string;
  apiKey?: string;
  limit?: number;
  startSeq?: number;
}): Promise<unknown> {
  const config = loadConfig();
  const apiKey = params.apiKey || resolveApiKey();
  if (!apiKey) throw new Error('No API key configured. Run: tgo-widget init');
  if (!config.channel_id) throw new Error('No channel_id. Run: tgo-widget init');
  if (config.channel_type == null) throw new Error('No channel_type. Run: tgo-widget init');

  const client = new TgoWidgetClient({ server: params.server || resolveServer(), apiKey });
  return client.post('/v1/visitors/messages/sync', {
    platform_api_key: apiKey,
    channel_id: config.channel_id,
    channel_type: config.channel_type,
    start_message_seq: params.startSeq ?? null,
    limit: params.limit ?? 20,
    pull_mode: 0,
  });
}

/**
 * Upload a file via POST /v1/chat/upload.
 */
export async function chatUpload(params: {
  server?: string;
  apiKey?: string;
  filePath: string;
}): Promise<unknown> {
  const config = loadConfig();
  const apiKey = params.apiKey || resolveApiKey();
  if (!apiKey) throw new Error('No API key configured. Run: tgo-widget init');
  if (!config.channel_id) throw new Error('No channel_id. Run: tgo-widget init');
  if (config.channel_type == null) throw new Error('No channel_type. Run: tgo-widget init');

  const client = new TgoWidgetClient({ server: params.server || resolveServer(), apiKey });

  const fileBuffer = readFileSync(params.filePath);
  const fileName = basename(params.filePath);
  const blob = new Blob([fileBuffer]);

  const formData = new FormData();
  formData.append('file', blob, fileName);
  formData.append('channel_id', config.channel_id);
  formData.append('channel_type', String(config.channel_type));

  return client.postFormData('/v1/chat/upload', formData);
}

// -- Helpers --

function generateClientMsgNo(): string {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}
