export type PlatformConfig = {
  position?: 'bottom-right' | 'bottom-left' | 'top-right' | 'top-left'
  theme_color?: string
  widget_title?: string
  welcome_message?: string
  logo_url?: string
  display_mode?: 'small' | 'big'
}

export type PlatformInfo = {
  id?: string
  name?: string
  config?: PlatformConfig
  [k: string]: any
}

export async function fetchPlatformInfo(params: { apiBase: string; platformApiKey: string; signal?: AbortSignal }): Promise<PlatformInfo> {
  const { apiBase, platformApiKey, signal } = params
  const base = apiBase.replace(/\/$/, '')
  const url = `${base}/v1/platforms/info`
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 10000)
  try {
    const res = await fetch(url + `?platform_api_key=${encodeURIComponent(platformApiKey)}`, {
      method: 'GET',
      headers: { 'X-Platform-API-Key': platformApiKey },
      signal: signal ?? controller.signal,
    })
    if (!res.ok) {
      const text = await res.text().catch(() => '')
      throw new Error(`[Platform] info failed: ${res.status} ${res.statusText} ${text}`)
    }
    const data = (await res.json()) as PlatformInfo
    return data
  } finally {
    clearTimeout(timeout)
  }
}

