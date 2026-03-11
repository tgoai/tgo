/* URL/query helpers for retrieving SDK parameters passed via history.replaceState
 * We expect the control iframe URL to contain ?apiKey=... injected by the SDK.
 * To be resilient, we also try parent/top windows when same-origin, and hash fallback.
 */

function tryGetSearchParamFrom(win: Window | null, key: string): string | null {
  try {
    if (!win) return null
    const search = win.location?.search || ''
    if (search) {
      const v = new URLSearchParams(search).get(key)
      if (v) return v
    }
    // fallback: parse from full href (covers cases where search might be empty but href has it)
    const href = win.location?.href || ''
    if (href) {
      const u = new URL(href, win.location.origin)
      const v2 = u.searchParams.get(key)
      if (v2) return v2
    }
    // hash fallback: ?apiKey=... placed after '#'
    const hash = win.location?.hash || ''
    if (hash && hash.includes('?')) {
      const q = hash.substring(hash.indexOf('?'))
      const v3 = new URLSearchParams(q).get(key)
      if (v3) return v3
    }
  } catch (_) {
    // likely cross-origin; ignore
  }
  return null
}

export function resolveApiKey(): string | null {
  // 1) current window (control iframe expected)
  let v = tryGetSearchParamFrom(window, 'apiKey')
  if (v) return v
  // 2) parent window (if accessible and different)
  try {
    if (window.parent && window.parent !== window) {
      v = tryGetSearchParamFrom(window.parent, 'apiKey')
      if (v) return v
    }
  } catch (_) { /* ignore cross-origin */ }
  // 3) top window
  try {
    if (window.top && window.top !== window) {
      v = tryGetSearchParamFrom(window.top, 'apiKey')
      if (v) return v
    }
  } catch (_) { /* ignore cross-origin */ }
  return null
}

export function requireApiKeyOrThrow(): string {
  const v = resolveApiKey()
  if (!v) {
    throw new Error('[Visitor] Missing apiKey in URL (?apiKey=...). Ensure the SDK injects it into the control iframe URL via history.replaceState.')
  }
  return v
}

export type ThemeMode = 'light' | 'dark'

/**
 * Resolve the theme mode from URL query string (?mode=dark or ?mode=light).
 * Returns 'light' as default if not specified or invalid.
 */
export function resolveMode(): ThemeMode {
  // 1) current window
  let v = tryGetSearchParamFrom(window, 'mode')
  if (v === 'dark' || v === 'light') return v
  // 2) parent window
  try {
    if (window.parent && window.parent !== window) {
      v = tryGetSearchParamFrom(window.parent, 'mode')
      if (v === 'dark' || v === 'light') return v
    }
  } catch (_) { /* ignore cross-origin */ }
  // 3) top window
  try {
    if (window.top && window.top !== window) {
      v = tryGetSearchParamFrom(window.top, 'mode')
      if (v === 'dark' || v === 'light') return v
    }
  } catch (_) { /* ignore cross-origin */ }
  return 'light'
}

