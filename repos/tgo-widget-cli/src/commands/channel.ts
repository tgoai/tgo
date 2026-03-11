import { Command } from 'commander';
import { TgoWidgetClient } from '../client.js';
import { loadConfig, resolveOutput, resolveServer, resolveApiKey } from '../config.js';
import { printError, printResult } from '../output.js';

function makeClient(globals: Record<string, string>) {
  return new TgoWidgetClient({ server: resolveServer(globals.server), apiKey: resolveApiKey(globals.apiKey) });
}

export function registerChannelCommands(parent: Command): void {
  const channel = parent.command('channel').description('Channel information');

  channel
    .command('info')
    .description('Get channel info')
    .option('--channel-id <id>', 'Channel ID (default: from config)')
    .option('--channel-type <n>', 'Channel type (default: from config)')
    .action(async (opts, cmd) => {
      const globals = cmd.parent!.parent!.opts();
      const format = resolveOutput(globals.output);
      try {
        const client = makeClient(globals);
        const result = await channelInfo(client, {
          channelId: opts.channelId,
          channelType: opts.channelType ? parseInt(opts.channelType) : undefined,
        });
        printResult(result, format);
      } catch (err) {
        printError(err, format);
      }
    });
}

export async function channelInfo(
  client: TgoWidgetClient,
  params?: { channelId?: string; channelType?: number },
): Promise<unknown> {
  client.requireApiKey();
  const config = loadConfig();
  const channelId = params?.channelId || config.channel_id;
  const channelType = params?.channelType ?? config.channel_type;
  if (!channelId) throw new Error('No channel_id. Run: tgo-widget init');
  if (channelType == null) throw new Error('No channel_type. Run: tgo-widget init');

  const qs = new URLSearchParams({
    channel_id: channelId,
    channel_type: String(channelType),
    platform_api_key: client.apiKey!,
  });
  return client.get(`/v1/channels/info?${qs.toString()}`);
}
