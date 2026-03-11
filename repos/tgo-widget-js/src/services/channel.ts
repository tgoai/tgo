export type ChannelInfo = {
  name?: string
  avatar?: string
  channel_id?: string
  channel_type?: number
  entity_type?: 'visitor' | 'staff' | string
  extra?: any
  [k: string]: any
}

export type StaffInfo = { name?: string; avatar?: string }

export async function fetchChannelInfo(params: {
  apiBase: string
  platformApiKey: string
  channelId: string
  channelType: number
  signal?: AbortSignal
}): Promise<ChannelInfo> {
  const { apiBase, platformApiKey, channelId, channelType, signal } = params
  const base = apiBase.replace(/\/$/, '')
  const url = `${base}/v1/channels/info` +
    `?channel_id=${encodeURIComponent(channelId)}` +
    `&channel_type=${encodeURIComponent(String(channelType))}` +
    `&platform_api_key=${encodeURIComponent(platformApiKey)}`

  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 10000)
  try {
    const res = await fetch(url, {
      method: 'GET',
      headers: { 'X-Platform-API-Key': platformApiKey },
      signal: signal ?? controller.signal,
    })
    if (!res.ok) {
      const text = await res.text().catch(() => '')
      throw new Error(`[Channel] info failed: ${res.status} ${res.statusText} ${text}`)
    }
    const data = (await res.json()) as ChannelInfo
    return data
  } finally {
    clearTimeout(timeout)
  }
}

