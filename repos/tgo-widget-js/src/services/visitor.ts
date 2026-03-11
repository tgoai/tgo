import { getJSON, setJSON } from '../utils/storage'
import type { VisitorRegisterRequest, VisitorRegisterResponse, CachedVisitor } from '../types/api'

const VISITOR_CACHE_KEY = (apiBase: string, platformApiKey: string) => `tgo:visitor:${apiBase}:${platformApiKey}`

export function loadCachedVisitor(apiBase: string, platformApiKey: string): CachedVisitor | null {
  return getJSON<CachedVisitor>(VISITOR_CACHE_KEY(apiBase, platformApiKey))
}

export function saveCachedVisitor(apiBase: string, platformApiKey: string, v: VisitorRegisterResponse, expiresAtMs?: number) {
  const cached: CachedVisitor = {
    apiBase,
    platform_api_key: platformApiKey,
    visitor_id: v.id,
    platform_open_id: v.platform_open_id,
    channel_id: v.channel_id,
    channel_type: v.channel_type,
    im_token: v.im_token,
    project_id: v.project_id,
    platform_id: v.platform_id,
    created_at: v.created_at,
    updated_at: v.updated_at,
    expires_at: expiresAtMs,
  }
  setJSON(VISITOR_CACHE_KEY(apiBase, platformApiKey), cached)
}

export async function registerVisitor(params: {
  apiBase: string
  platformApiKey: string
  signal?: AbortSignal
  extra?: Omit<VisitorRegisterRequest, 'platform_api_key'>
}): Promise<VisitorRegisterResponse> {
  const { apiBase, platformApiKey, signal, extra } = params
  const url = `${apiBase.replace(/\/$/, '')}/v1/visitors/register`
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 10000)
  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        platform_api_key: platformApiKey,
        ...extra,
      } satisfies VisitorRegisterRequest),
      signal: signal ?? controller.signal,
    })
    if (!res.ok) {
      const text = await res.text().catch(() => '')
      throw new Error(`[Visitor] register failed: ${res.status} ${res.statusText} ${text}`)
    }
    const data = (await res.json()) as VisitorRegisterResponse
    console.log('[Visitor] Registration response:', {
      id: data?.id,
      channel_id: data?.channel_id,
      hasImToken: !!data?.im_token,
      im_token: data?.im_token ? `${data.im_token.substring(0, 10)}...` : 'undefined'
    })
    if (!data?.id || !data?.channel_id) {
      throw new Error('[Visitor] invalid register response: missing id/channel_id')
    }
    if (!data?.im_token) {
      console.warn('[Visitor] Warning: im_token not found in registration response. This may cause IM initialization to fail.')
    }
    return data
  } finally {
    clearTimeout(timeout)
  }
}

