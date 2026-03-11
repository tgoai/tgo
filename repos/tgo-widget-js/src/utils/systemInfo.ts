import type { VisitorSystemInfo } from '../types/api'

function parseBrowser(ua: string): string | null {
  try {
    // iOS Chrome
    const mCriOS = ua.match(/CriOS\/(\d+(?:\.\d+)?)/)
    if (mCriOS) return `Chrome iOS ${mCriOS[1]}`

    // iOS Firefox
    const mFxiOS = ua.match(/FxiOS\/(\d+(?:\.\d+)?)/)
    if (mFxiOS) return `Firefox iOS ${mFxiOS[1]}`

    // Edge (Chromium)
    const mEdg = ua.match(/Edg\/(\d+(?:\.\d+)?)/)
    if (mEdg) return `Edge ${mEdg[1]}`

    // Chrome (exclude Edge/Opera)
    const mChrome = /Chrome\/(\d+(?:\.\d+)?)/.exec(ua)
    if (mChrome && !/Edg\//.test(ua) && !/OPR\//.test(ua)) return `Chrome ${mChrome[1]}`

    // Firefox
    const mFx = ua.match(/Firefox\/(\d+(?:\.\d+)?)/)
    if (mFx) return `Firefox ${mFx[1]}`

    // Safari (Version/x.y)
    if (/Safari\//.test(ua) && /Version\//.test(ua) && !/Chrome\//.test(ua)) {
      const mVer = ua.match(/Version\/(\d+(?:\.\d+)?)/)
      if (mVer) return `Safari ${mVer[1]}`
      return 'Safari'
    }
  } catch {}
  return null
}

function parseOS(ua: string): string | null {
  try {
    // iOS
    const mIOS = ua.match(/(iPhone|iPad|iPod).*?OS (\d+[\._\d]*)/)
    if (mIOS) return `iOS ${mIOS[2].replace(/_/g, '.')}`

    // Android
    const mAndroid = ua.match(/Android (\d+(?:\.\d+)?)/)
    if (mAndroid) return `Android ${mAndroid[1]}`

    // Windows
    const mWin = ua.match(/Windows NT (\d+\.\d+)/)
    if (mWin) {
      const v = mWin[1]
      const map: Record<string, string> = {
        '10.0': 'Windows 10+',
        '6.3': 'Windows 8.1',
        '6.2': 'Windows 8',
        '6.1': 'Windows 7',
      }
      return map[v] || `Windows NT ${v}`
    }

    // macOS
    const mMac = ua.match(/Mac OS X (\d+[\._]\d+(?:[\._]\d+)?)/)
    if (mMac) return `macOS ${mMac[1].replace(/_/g, '.')}`

    // Linux
    if (/Linux/.test(ua) && !/Android/.test(ua)) return 'Linux'
  } catch {}
  return null
}

function getSourceDetail(): string | null {
  try {
    const ref = (typeof document !== 'undefined' && document.referrer) ? document.referrer : ''
    const hasWindow = typeof window !== 'undefined' && typeof window.location !== 'undefined'
    let utm: string | null = null
    if (hasWindow) {
      try {
        const url = new URL(window.location.href)
        const keys = ['utm_source','utm_medium','utm_campaign','utm_term','utm_content','gclid','msclkid','fbclid']
        const parts: string[] = []
        for (const k of keys) {
          const v = url.searchParams.get(k)
          if (v) parts.push(`${k}=${v}`)
        }
        utm = parts.length ? parts.join('&') : null
      } catch {}
    }
    if (ref && utm) return `referrer=${ref}; utm=${utm}`
    if (ref) return ref
    if (utm) return `utm=${utm}`
  } catch {}
  return null
}

export function collectVisitorSystemInfo(): VisitorSystemInfo | null {
  try {
    const ua = (typeof navigator !== 'undefined' && navigator.userAgent) ? navigator.userAgent : ''
    const browser = ua ? parseBrowser(ua) : null
    const os = ua ? parseOS(ua) : null
    const source = getSourceDetail()

    const hasAny = !!(browser || os || source)
    if (!hasAny) return null

    const info: VisitorSystemInfo = {}
    if (source) info.source_detail = source
    if (browser) info.browser = browser
    if (os) info.operating_system = os
    return info
  } catch {
    return null
  }
}

