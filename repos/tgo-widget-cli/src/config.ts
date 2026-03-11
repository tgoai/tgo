import { existsSync, mkdirSync, readFileSync, writeFileSync, unlinkSync } from 'node:fs';
import { homedir } from 'node:os';
import { dirname, join } from 'node:path';

export interface TgoWidgetConfig {
  server?: string;
  api_key?: string;
  visitor_id?: string;
  platform_open_id?: string;
  channel_id?: string;
  channel_type?: number;
  im_token?: string;
  platform_id?: string;
  output?: 'json' | 'table' | 'compact';
}

const CONFIG_DIR = join(homedir(), '.tgo-widget');
const CONFIG_PATH = join(CONFIG_DIR, 'config.json');

export function loadConfig(): TgoWidgetConfig {
  if (!existsSync(CONFIG_PATH)) return {};
  try {
    return JSON.parse(readFileSync(CONFIG_PATH, 'utf-8'));
  } catch {
    return {};
  }
}

export function saveConfig(config: TgoWidgetConfig): void {
  mkdirSync(dirname(CONFIG_PATH), { recursive: true });
  writeFileSync(CONFIG_PATH, JSON.stringify(config, null, 2) + '\n');
}

export function updateConfig(patch: Partial<TgoWidgetConfig>): void {
  const config = loadConfig();
  Object.assign(config, patch);
  for (const key of Object.keys(config) as (keyof TgoWidgetConfig)[]) {
    if (config[key] == null) delete config[key];
  }
  saveConfig(config);
}

export function resetConfig(): void {
  if (existsSync(CONFIG_PATH)) {
    unlinkSync(CONFIG_PATH);
  }
}

/** Resolve a setting with priority: CLI flag > env var > config file */
export function resolveServer(flag?: string): string | undefined {
  return flag || process.env.TGO_WIDGET_SERVER || loadConfig().server;
}

export function resolveApiKey(flag?: string): string | undefined {
  return flag || process.env.TGO_WIDGET_API_KEY || loadConfig().api_key;
}

export function resolveOutput(flag?: string): 'json' | 'table' | 'compact' {
  const v = flag || process.env.TGO_WIDGET_OUTPUT || loadConfig().output;
  if (v === 'table' || v === 'compact') return v;
  return 'json';
}
