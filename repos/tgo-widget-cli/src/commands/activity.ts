import { Command } from 'commander';
import { TgoWidgetClient } from '../client.js';
import { loadConfig, resolveOutput, resolveServer, resolveApiKey } from '../config.js';
import { printError, printResult } from '../output.js';

function makeClient(globals: Record<string, string>) {
  return new TgoWidgetClient({ server: resolveServer(globals.server), apiKey: resolveApiKey(globals.apiKey) });
}

export function registerActivityCommands(parent: Command): void {
  const activity = parent.command('activity').description('Visitor activity tracking');

  activity
    .command('record')
    .description('Record a visitor activity')
    .requiredOption('--type <type>', 'Activity type (page_view, message_sent, form_submitted, file_uploaded, custom_event, session_start, session_end)')
    .requiredOption('--title <text>', 'Activity title')
    .option('--description <text>', 'Activity description')
    .option('--duration <seconds>', 'Duration in seconds')
    .action(async (opts, cmd) => {
      const globals = cmd.parent!.parent!.opts();
      const format = resolveOutput(globals.output);
      try {
        const client = makeClient(globals);
        const result = await activityRecord(client, {
          activityType: opts.type,
          title: opts.title,
          description: opts.description,
          durationSeconds: opts.duration ? parseInt(opts.duration) : undefined,
        });
        printResult(result, format);
      } catch (err) {
        printError(err, format);
      }
    });
}

export async function activityRecord(
  client: TgoWidgetClient,
  params: {
    activityType: string;
    title: string;
    description?: string;
    durationSeconds?: number;
    context?: Record<string, unknown>;
  },
): Promise<unknown> {
  client.requireApiKey();
  const config = loadConfig();
  if (!config.visitor_id) throw new Error('No visitor_id. Run: tgo-widget init');

  const body: Record<string, unknown> = {
    platform_api_key: client.apiKey,
    visitor_id: config.visitor_id,
    activity_type: params.activityType,
    title: params.title,
  };
  if (params.description) body.description = params.description;
  if (params.durationSeconds != null) body.duration_seconds = params.durationSeconds;
  if (params.context) body.context = params.context;

  return client.post('/v1/visitors/activities', body);
}
