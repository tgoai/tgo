import { resolveApiKey } from '../utils/url'

export type ChatFileUploadResponse = {
  file_id: string
  file_name: string
  file_size: number
  file_type: string
  file_url: string
  channel_id: string
  channel_type: number
  uploaded_at: string
  uploaded_by?: string | null
}

export type UploadParams = {
  apiBase: string
  channelId: string
  channelType: number
  file: File
  onProgress?: (percent: number, loaded: number, total: number) => void
  signal?: AbortSignal
}

export function makeChatFileUrl(apiBase: string, fileId: string, opts?: { includeApiKey?: boolean; apiKeyOverride?: string }): string {
  const base = apiBase.replace(/\/$/, '')
  let url = `${base}/v1/chat/files/${encodeURIComponent(fileId)}`
  const include = opts?.includeApiKey !== false
  const key = opts?.apiKeyOverride ?? resolveApiKey()
  if (include && key) {
    url += (url.includes('?') ? '&' : '?') + 'platform_api_key=' + encodeURIComponent(key)
  }
  return url
}

// Use XMLHttpRequest to support upload progress callbacks
export function uploadChatFile({ apiBase, channelId, channelType, file, onProgress, signal }: UploadParams): Promise<ChatFileUploadResponse> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    const base = apiBase.replace(/\/$/, '')
    const url = `${base}/v1/chat/upload`
    xhr.open('POST', url, true)

    const apiKey = resolveApiKey()
    if (apiKey) xhr.setRequestHeader('X-Platform-API-Key', apiKey)

    xhr.responseType = 'json'

    if (xhr.upload && onProgress) {
      xhr.upload.onprogress = (e: ProgressEvent) => {
        if (!e.lengthComputable) return onProgress(0, 0, 0)
        const p = Math.min(100, Math.round((e.loaded / Math.max(1, e.total)) * 100))
        onProgress(p, e.loaded, e.total)
      }
    }

    const onAbort = () => { try { xhr.abort() } catch {} }
    if (signal) {
      if (signal.aborted) return reject(new DOMException('Aborted', 'AbortError'))
      signal.addEventListener('abort', onAbort, { once: true })
    }

    xhr.onerror = () => {
      cleanup()
      const msg = typeof xhr.statusText === 'string' && xhr.statusText ? xhr.statusText : 'Network error'
      reject(new Error(`[Upload] network error: ${xhr.status} ${msg}`))
    }
    xhr.onload = () => {
      cleanup()
      const status = xhr.status
      if (status >= 200 && status < 300) {
        const data = xhr.response as ChatFileUploadResponse
        if (!data || !data.file_id) {
          return reject(new Error('[Upload] invalid response'))
        }
        resolve(data)
      } else {
        const text = ((): string => {
          try { return typeof xhr.response === 'string' ? xhr.response : JSON.stringify(xhr.response) } catch { return '' }
        })()
        reject(new Error(`[Upload] failed: ${status} ${xhr.statusText} ${text}`))
      }
    }

    const cleanup = () => {
      try { if (signal) signal.removeEventListener('abort', onAbort as any) } catch {}
    }

    const form = new FormData()
    form.append('file', file)
    form.append('channel_id', channelId)
    form.append('channel_type', String(channelType))
    // dual auth supported: we already set X-Platform-API-Key header; body field optional

    xhr.send(form)
  })
}

export async function readImageDimensions(file: File): Promise<{ width: number; height: number } | null> {
  if (!file.type.startsWith('image/')) return null
  // Prefer createImageBitmap if available
  try {
    // @ts-ignore
    if (typeof createImageBitmap === 'function') {
      // @ts-ignore
      const bmp = await createImageBitmap(file)
      const dims = { width: bmp.width, height: bmp.height }
      try { bmp.close?.() } catch {}
      return dims
    }
  } catch {}
  return new Promise(resolve => {
    try {
      const url = URL.createObjectURL(file)
      const img = new Image()
      img.onload = () => {
        const dims = { width: img.naturalWidth || img.width, height: img.naturalHeight || img.height }
        try { URL.revokeObjectURL(url) } catch {}
        resolve(dims)
      }
      img.onerror = () => { try { URL.revokeObjectURL(url) } catch {}; resolve(null) }
      img.src = url
    } catch { resolve(null) }
  })
}

