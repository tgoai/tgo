import { resolveServer, resolveApiKey } from './config.js';

export interface ApiErrorDetail {
  code?: string;
  message?: string;
  details?: Record<string, unknown>;
  status_code?: number;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public data: ApiErrorDetail,
    public requestId?: string,
  ) {
    super(data.message || `API error ${status}`);
    this.name = 'ApiError';
  }
}

export interface ClientOptions {
  server?: string;
  apiKey?: string;
}

export interface StreamCallbacks {
  onMessage: (event: string, data: unknown) => void;
  onError?: (error: Error) => void;
  onClose?: () => void;
  signal?: AbortSignal;
}

export class TgoWidgetClient {
  private server: string;
  private _apiKey?: string;

  constructor(opts?: ClientOptions) {
    const server = opts?.server || resolveServer();
    if (!server) throw new Error('No server configured. Run: tgo-widget init --api-key <key> --server <url>');
    this.server = server.replace(/\/+$/, '');
    this._apiKey = opts?.apiKey || resolveApiKey();
  }

  private url(endpoint: string): string {
    const path = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
    return `${this.server}${path}`;
  }

  get serverUrl(): string {
    return this.server;
  }

  get apiKey(): string | undefined {
    return this._apiKey;
  }

  private headers(contentType?: string): Record<string, string> {
    const h: Record<string, string> = {
      'X-User-Language': 'en',
    };
    if (contentType) h['Content-Type'] = contentType;
    if (this._apiKey) h['X-Platform-API-Key'] = this._apiKey;
    return h;
  }

  private async handleResponse<T>(res: Response): Promise<T> {
    const requestId = res.headers.get('x-request-id') || undefined;
    if (!res.ok) {
      let data: ApiErrorDetail = {};
      try {
        const body = await res.json();
        data = body.error || body;
      } catch {
        data = { message: await res.text().catch(() => `HTTP ${res.status}`) };
      }
      throw new ApiError(res.status, data, requestId);
    }
    if (res.status === 204) return undefined as T;
    const text = await res.text();
    if (!text) return undefined as T;
    return JSON.parse(text) as T;
  }

  requireApiKey(): void {
    if (!this._apiKey) {
      throw new Error('No API key configured. Run: tgo-widget init --api-key <key>');
    }
  }

  async get<T>(endpoint: string): Promise<T> {
    this.requireApiKey();
    const res = await fetch(this.url(endpoint), {
      method: 'GET',
      headers: this.headers(),
    });
    return this.handleResponse<T>(res);
  }

  async post<T>(endpoint: string, data?: unknown): Promise<T> {
    this.requireApiKey();
    const res = await fetch(this.url(endpoint), {
      method: 'POST',
      headers: this.headers('application/json'),
      body: data !== undefined ? JSON.stringify(data) : undefined,
    });
    return this.handleResponse<T>(res);
  }

  /** POST without auth header (api_key goes in body, e.g. visitor register) */
  async postPublic<T>(endpoint: string, data?: unknown): Promise<T> {
    const res = await fetch(this.url(endpoint), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-User-Language': 'en' },
      body: data !== undefined ? JSON.stringify(data) : undefined,
    });
    return this.handleResponse<T>(res);
  }

  /** POST with multipart/form-data (file uploads) */
  async postFormData<T>(endpoint: string, formData: FormData): Promise<T> {
    this.requireApiKey();
    const h: Record<string, string> = { 'X-User-Language': 'en' };
    if (this._apiKey) h['X-Platform-API-Key'] = this._apiKey;
    const res = await fetch(this.url(endpoint), {
      method: 'POST',
      headers: h,
      body: formData,
    });
    return this.handleResponse<T>(res);
  }

  /** SSE streaming request (no auth header — api_key in body) */
  async stream(endpoint: string, data: unknown, callbacks: StreamCallbacks): Promise<void> {
    const res = await fetch(this.url(endpoint), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-User-Language': 'en' },
      body: JSON.stringify(data),
      signal: callbacks.signal,
    });

    if (!res.ok) {
      let errData: ApiErrorDetail = {};
      try { errData = await res.json(); } catch { /* ignore */ }
      throw new ApiError(res.status, errData);
    }

    const reader = res.body?.getReader();
    if (!reader) throw new Error('No response body');

    const decoder = new TextDecoder();
    let buffer = '';
    let currentEvent = 'message';

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('event:')) {
            currentEvent = line.slice(6).trim();
          } else if (line.startsWith('data:')) {
            const rawData = line.slice(5).trim();
            if (rawData) {
              try {
                callbacks.onMessage(currentEvent, JSON.parse(rawData));
              } catch {
                callbacks.onMessage(currentEvent, rawData);
              }
            }
            currentEvent = 'message';
          }
        }
      }
    } catch (err) {
      if (callbacks.onError && err instanceof Error) callbacks.onError(err);
      else throw err;
    } finally {
      callbacks.onClose?.();
    }
  }
}

/** Create a client from global CLI options */
export function createClient(opts?: ClientOptions): TgoWidgetClient {
  return new TgoWidgetClient(opts);
}
