import { Command } from 'commander';
import { registerInitCommand } from './commands/init.js';
import { registerChatCommands } from './commands/chat.js';
import { registerPlatformCommands } from './commands/platform.js';
import { registerChannelCommands } from './commands/channel.js';
import { registerActivityCommands } from './commands/activity.js';
import { loadConfig, resetConfig, resolveOutput } from './config.js';
import { printResult, printError } from './output.js';

const program = new Command();

program
  .name('tgo-widget')
  .description('TGO Widget CLI - Visitor-facing CLI + MCP Server')
  .version('0.1.0')
  .option('-s, --server <url>', 'API server URL')
  .option('-k, --api-key <key>', 'Platform API Key')
  .option('-o, --output <format>', 'Output format: json, table, compact', 'json')
  .option('-v, --verbose', 'Verbose output');

// Register command groups
registerInitCommand(program);
registerChatCommands(program);
registerPlatformCommands(program);
registerChannelCommands(program);
registerActivityCommands(program);

// whoami — show current config
program
  .command('whoami')
  .description('Show current visitor configuration')
  .action((_opts, cmd) => {
    const globals = cmd.parent!.opts();
    const format = resolveOutput(globals.output);
    const config = loadConfig();
    if (!config.visitor_id) {
      printError(new Error('Not initialized. Run: tgo-widget init --api-key <key> --server <url>'), format);
      return;
    }
    printResult({
      visitor_id: config.visitor_id,
      platform_open_id: config.platform_open_id,
      channel_id: config.channel_id,
      channel_type: config.channel_type,
      platform_id: config.platform_id,
      server: config.server,
      has_im_token: !!config.im_token,
    }, format);
  });

// reset — clear config
program
  .command('reset')
  .description('Clear saved configuration')
  .action((_opts, cmd) => {
    const globals = cmd.parent!.opts();
    const format = resolveOutput(globals.output);
    resetConfig();
    printResult({ status: 'reset', message: 'Configuration cleared' }, format);
  });

// MCP serve command
program
  .command('mcp')
  .description('MCP Server commands')
  .command('serve')
  .description('Start MCP Server (stdio transport)')
  .action(async () => {
    const { startMcpServer } = await import('./mcp/server.js');
    await startMcpServer();
  });

program.parse();
