// Small localStorage JSON helpers with optional expiry

export type Stored<T> = { v: T; e?: number } // e: expiresAt epoch ms

export function setJSON<T>(key: string, value: T, ttlMs?: number) {
  const rec: Stored<T> = { v: value }
  if (ttlMs && ttlMs > 0) {
    rec.e = Date.now() + ttlMs
  }
  localStorage.setItem(key, JSON.stringify(rec))
}

export function getJSON<T>(key: string): T | null {
  const raw = localStorage.getItem(key)
  if (!raw) return null
  try {
    const rec = JSON.parse(raw) as Stored<T>
    if (rec && typeof rec === 'object') {
      if (rec.e && Date.now() > rec.e) {
        localStorage.removeItem(key)
        return null
      }
      return rec.v as T
    }
  } catch (_) {
    // corrupted; clear
    localStorage.removeItem(key)
  }
  return null
}

export function remove(key: string) {
  localStorage.removeItem(key)
}

