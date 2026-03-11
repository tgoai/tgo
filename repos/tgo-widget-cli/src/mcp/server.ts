import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { z } from 'zod';
import { TgoWidgetClient } from '../client.js';
import { loadConfig, resetConfig, resolveServer, resolveApiKey } from '../config.js';

// Commands
import { initVisitor } from '../commands/init.js';
import { chatSend, chatSendWs, chatHistory, chatUpload } from '../commands/chat.js';
import { platformInfo } from '../commands/platform.js';
import { channelInfo } from '../commands/channel.js';
import { activityRecord } from '../commands/activity.js';

function text(data: unknown): { content: { type: 'text'; text: string }[] } {
  return { content: [{ type: 'text', text: JSON.stringify(data, null, 2) }] };
}

function getClient(): TgoWidgetClient {
  return new TgoWidgetClient({ server: resolveServer(), apiKey: resolveApiKey() });
}

export async function startMcpServer(): Promise<void> {
  const server = new McpServer({
    name: 'tgo-widget',
    version: '0.1.0',
  });

  // ─── Init ──────────────────────────────────────────────

  server.tool(
    'tgo_widget_init',
    'Register as visitor and save configuration',
    {
      api_key: z.string().describe('Platform API Key'),
      server: z.string().optional().describe('API server URL'),
      name: z.string().optional().describe('Visitor name'),
      email: z.string().optional().describe('Visitor email'),
      phone: z.string().optional().describe('Visitor phone'),
    },
    async (params) => text(await initVisitor({
      server: params.server,
      apiKey: params.api_key,
      name: params.name,
      email: params.email,
      phone: params.phone,
    })),
  );

  // ─── Chat ─────────────────────────────────────────────

  server.tool(
    'tgo_widget_chat_send',
    'Send a message to customer service and get AI response (waits for full response)',
    {
      message: z.string().describe('Message text'),
      stream: z.boolean().optional().default(false).describe('Use SSE streaming (default: false for MCP)'),
    },
    async (params) => text(await chatSend({
      message: params.message,
      stream: params.stream,
    })),
  );

  server.tool(
    'tgo_widget_chat_send_ws',
    'Send a message via WuKongIM WebSocket (raw IM, no AI reply)',
    {
      message: z.string().describe('Message text'),
    },
    async (params) => text(await chatSendWs({ message: params.message })),
  );

  server.tool(
    'tgo_widget_chat_history',
    'Get message history',
    {
      limit: z.number().optional().default(20).describe('Max messages'),
      start_seq: z.number().optional().describe('Start message sequence number'),
    },
    async (params) => text(await chatHistory({
      limit: params.limit,
      startSeq: params.start_seq,
    })),
  );

  server.tool(
    'tgo_widget_chat_upload',
    'Upload a file to the chat',
    {
      file_path: z.string().describe('Local file path to upload'),
    },
    async (params) => text(await chatUpload({ filePath: params.file_path })),
  );

  // ─── Platform ─────────────────────────────────────────

  server.tool(
    'tgo_widget_platform_info',
    'Get platform information',
    {},
    async () => text(await platformInfo(getClient())),
  );

  // ─── Channel ──────────────────────────────────────────

  server.tool(
    'tgo_widget_channel_info',
    'Get channel information',
    {
      channel_id: z.string().optional().describe('Channel ID (default: from config)'),
      channel_type: z.number().optional().describe('Channel type (default: from config)'),
    },
    async (params) => text(await channelInfo(getClient(), {
      channelId: params.channel_id,
      channelType: params.channel_type,
    })),
  );

  // ─── Activity ─────────────────────────────────────────

  server.tool(
    'tgo_widget_activity_record',
    'Record a visitor activity',
    {
      activity_type: z.string().describe('Activity type (page_view, message_sent, form_submitted, file_uploaded, custom_event, session_start, session_end)'),
      title: z.string().describe('Activity title'),
      description: z.string().optional().describe('Activity description'),
      duration_seconds: z.number().optional().describe('Duration in seconds'),
    },
    async (params) => text(await activityRecord(getClient(), {
      activityType: params.activity_type,
      title: params.title,
      description: params.description,
      durationSeconds: params.duration_seconds,
    })),
  );

  // ─── Whoami / Reset ───────────────────────────────────

  server.tool(
    'tgo_widget_whoami',
    'Show current visitor configuration',
    {},
    async () => {
      const config = loadConfig();
      if (!config.visitor_id) {
        return text({ error: 'Not initialized. Run tgo_widget_init first.' });
      }
      return text({
        visitor_id: config.visitor_id,
        platform_open_id: config.platform_open_id,
        channel_id: config.channel_id,
        channel_type: config.channel_type,
        platform_id: config.platform_id,
        server: config.server,
        has_im_token: !!config.im_token,
      });
    },
  );

  server.tool(
    'tgo_widget_reset',
    'Clear saved visitor configuration',
    {},
    async () => {
      resetConfig();
      return text({ status: 'reset', message: 'Configuration cleared' });
    },
  );

  // ─── Connect ──────────────────────────────────────────

  const transport = new StdioServerTransport();
  await server.connect(transport);
}
