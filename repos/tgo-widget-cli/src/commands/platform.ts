import { Command } from 'commander';
import { TgoWidgetClient } from '../client.js';
import { resolveOutput, resolveServer, resolveApiKey } from '../config.js';
import { printError, printResult } from '../output.js';

function makeClient(globals: Record<string, string>) {
  return new TgoWidgetClient({ server: resolveServer(globals.server), apiKey: resolveApiKey(globals.apiKey) });
}

export function registerPlatformCommands(parent: Command): void {
  const platform = parent.command('platform').description('Platform information');

  platform
    .command('info')
    .description('Get platform info')
    .action(async (_opts, cmd) => {
      const globals = cmd.parent!.parent!.opts();
      const format = resolveOutput(globals.output);
      try {
        const client = makeClient(globals);
        const result = await platformInfo(client);
        printResult(result, format);
      } catch (err) {
        printError(err, format);
      }
    });
}

export async function platformInfo(client: TgoWidgetClient): Promise<unknown> {
  client.requireApiKey();
  return client.get(`/v1/platforms/info?platform_api_key=${encodeURIComponent(client.apiKey!)}`);
}
