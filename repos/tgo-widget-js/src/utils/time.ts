export function formatMessageTime(input: number | Date): string {
  const msgDate = normalizeToDate(input)
  if (!msgDate) return ''

  const now = new Date()
  const diff = now.getTime() - msgDate.getTime()

  // 1分钟内
  if (diff < 60 * 1000) return '刚才'

  // 1小时内
  if (diff < 60 * 60 * 1000) {
    const minutes = Math.floor(diff / (60 * 1000))
    return `${minutes}分钟前`
  }

  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 0, 0, 0, 0)
  const startOfYesterday = new Date(startOfToday.getTime() - 24 * 60 * 60 * 1000)

  // 今天
  if (msgDate >= startOfToday) {
    return fmt(msgDate, 'HH:mm')
  }

  // 昨天
  if (msgDate >= startOfYesterday) {
    return `昨天 ${fmt(msgDate, 'HH:mm')}`
  }

  // 7天内（不包含今天/昨天）
  const sevenDaysAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000)
  if (msgDate > sevenDaysAgo) {
    return `${weekdayCN(msgDate)} ${fmt(msgDate, 'HH:mm')}`
  }

  // 本年内
  if (msgDate.getFullYear() === now.getFullYear()) {
    return fmt(msgDate, 'MM-DD HH:mm')
  }

  // 跨年
  return fmt(msgDate, 'YYYY-MM-DD HH:mm')
}

function normalizeToDate(input: number | Date): Date | null {
  if (input instanceof Date) return input
  if (typeof input === 'number' && isFinite(input)) {
    // 支持秒或毫秒
    const ms = input < 1e12 ? input * 1000 : input
    const d = new Date(ms)
    return isNaN(d.getTime()) ? null : d
  }
  return null
}

function pad(n: number): string { return n < 10 ? `0${n}` : String(n) }

function fmt(d: Date, pattern: 'HH:mm' | 'MM-DD HH:mm' | 'YYYY-MM-DD HH:mm'): string {
  const Y = d.getFullYear()
  const M = pad(d.getMonth() + 1)
  const D = pad(d.getDate())
  const h = pad(d.getHours())
  const m = pad(d.getMinutes())
  switch (pattern) {
    case 'HH:mm': return `${h}:${m}`
    case 'MM-DD HH:mm': return `${M}-${D} ${h}:${m}`
    case 'YYYY-MM-DD HH:mm':
    default: return `${Y}-${M}-${D} ${h}:${m}`
  }
}

function weekdayCN(d: Date): string {
  const w = d.getDay() // 0-6 (0: Sunday)
  return ['星期日','星期一','星期二','星期三','星期四','星期五','星期六'][w]
}

