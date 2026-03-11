export type OutputFormat = 'json' | 'table' | 'compact';

/** Print result in the requested format */
export function printResult(data: unknown, format: OutputFormat): void {
  switch (format) {
    case 'json':
      printJson(data);
      break;
    case 'table':
      printTable(data);
      break;
    case 'compact':
      printCompact(data);
      break;
  }
}

function printJson(data: unknown): void {
  console.log(JSON.stringify(data, null, 2));
}

function printTable(data: unknown): void {
  if (Array.isArray(data)) {
    if (data.length === 0) {
      console.log('(empty)');
      return;
    }
    const keys = [...new Set(data.flatMap(item => Object.keys(item)))];
    const widths = keys.map(k =>
      Math.max(k.length, ...data.map(item => String(item[k] ?? '').length))
    );
    const cappedWidths = widths.map(w => Math.min(w, 40));
    const header = keys.map((k, i) => k.padEnd(cappedWidths[i])).join('  ');
    const separator = cappedWidths.map(w => '-'.repeat(w)).join('  ');
    console.log(header);
    console.log(separator);
    for (const item of data) {
      const row = keys.map((k, i) => {
        const val = String(item[k] ?? '');
        return val.slice(0, cappedWidths[i]).padEnd(cappedWidths[i]);
      }).join('  ');
      console.log(row);
    }
  } else if (data && typeof data === 'object') {
    const entries = Object.entries(data as Record<string, unknown>);
    const maxKeyLen = Math.max(...entries.map(([k]) => k.length), 0);
    for (const [key, value] of entries) {
      const val = typeof value === 'object' ? JSON.stringify(value) : String(value ?? '');
      console.log(`${key.padEnd(maxKeyLen)}  ${val}`);
    }
  } else {
    console.log(String(data));
  }
}

function printCompact(data: unknown): void {
  if (Array.isArray(data)) {
    for (const item of data) {
      if (item && typeof item === 'object') {
        const vals = Object.values(item as Record<string, unknown>);
        console.log(vals.map(v => (typeof v === 'object' ? JSON.stringify(v) : String(v ?? ''))).join(' | '));
      } else {
        console.log(String(item));
      }
    }
  } else if (data && typeof data === 'object') {
    const vals = Object.values(data as Record<string, unknown>);
    console.log(vals.map(v => (typeof v === 'object' ? JSON.stringify(v) : String(v ?? ''))).join(' | '));
  } else {
    console.log(String(data));
  }
}

/** Print an error in structured format */
export function printError(err: unknown, format: OutputFormat): void {
  if (err && typeof err === 'object' && 'status' in err && 'data' in err) {
    const apiErr = err as { status: number; data: unknown; requestId?: string };
    const output = {
      error: true,
      status: apiErr.status,
      ...(typeof apiErr.data === 'object' ? apiErr.data as Record<string, unknown> : { message: String(apiErr.data) }),
      ...(apiErr.requestId ? { request_id: apiErr.requestId } : {}),
    };
    if (format === 'json') {
      console.error(JSON.stringify(output, null, 2));
    } else {
      console.error(`Error ${apiErr.status}: ${(output as Record<string, unknown>).message || JSON.stringify(apiErr.data)}`);
    }
  } else if (err instanceof Error) {
    if (format === 'json') {
      console.error(JSON.stringify({ error: true, message: err.message }, null, 2));
    } else {
      console.error(`Error: ${err.message}`);
    }
  } else {
    console.error(String(err));
  }
  process.exitCode = 1;
}
