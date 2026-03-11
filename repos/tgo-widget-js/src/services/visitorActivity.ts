import { requireApiKeyOrThrow } from '../utils/url'

export type VisitorActivityType = 'page_view' | 'message_sent' | 'form_submitted' | 'file_uploaded' | 'custom_event' | 'session_start' | 'session_end'

export type VisitorActivityContext = {
  page_url?: string | null
  referrer?: string | null
  metadata?: Record<string, any> | null
} | null

export type VisitorActivityCreateRequest = {
  id?: string | null
  platform_api_key?: string | null
  visitor_id: string
  activity_type: VisitorActivityType
  title: string
  description?: string | null
  duration_seconds?: number | null
  context?: VisitorActivityContext
}

export type VisitorActivityCreateResponse = {
  id: string
  activity_type: string
  title: string
  occurred_at: string
  context?: Record<string, any> | null
}

export async function recordVisitorActivity(params: {
  apiBase: string
  visitorId: string
  activityType: VisitorActivityType
  title: string
  description?: string | null
  id?: string | null
  durationSeconds?: number | null
  context?: VisitorActivityContext
  signal?: AbortSignal
  keepalive?: boolean
}): Promise<VisitorActivityCreateResponse> {
  const {
    apiBase,
    visitorId,
    activityType,
    title,
    description = null,
    id = null,
    durationSeconds = null,
    context = null,
    signal,
    keepalive = false,
  } = params
  if (!apiBase) throw new Error('[Activity] Missing apiBase')
  if (!visitorId) throw new Error('[Activity] Missing visitorId')
  const apiKey = requireApiKeyOrThrow()
  const url = `${apiBase.replace(/\/$/, '')}/v1/visitors/activities`

  const body: VisitorActivityCreateRequest = {
    platform_api_key: apiKey,
    visitor_id: visitorId,
    activity_type: activityType,
    title,
    description,
    context,
  }
  if (id) (body as any).id = id
  if (durationSeconds != null) (body as any).duration_seconds = durationSeconds

  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 10000)
  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Platform-API-Key': apiKey,
      },
      body: JSON.stringify(body),
      signal: signal ?? controller.signal,
      // keepalive allows the request to outlive the page lifecycle (used on unload)
      keepalive,
    })
    if (!res.ok) {
      const text = await res.text().catch(() => '')
      throw new Error(`[Activity] record failed: ${res.status} ${res.statusText} ${text}`)
    }
    const data = (await res.json()) as VisitorActivityCreateResponse
    return data
  } finally {
    clearTimeout(timer)
  }
}
