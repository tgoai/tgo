export function formatFileSize(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return '未知大小'
  const KB = 1024, MB = KB*1024, GB = MB*1024
  if (bytes < KB) return `${bytes} B`
  if (bytes < MB) return `${(bytes/KB).toFixed(1)} KB`
  if (bytes < GB) return `${(bytes/MB).toFixed(1)} MB`
  return `${(bytes/GB).toFixed(1)} GB`
}

export function getGridLayout(count: number){
  if (count === 1) return { cols: 1, rows: 1, size: 'large' as const }
  if (count === 2) return { cols: 2, rows: 1, size: 'medium' as const }
  if (count === 3) return { cols: 3, rows: 1, size: 'small' as const }
  if (count === 4) return { cols: 2, rows: 2, size: 'medium' as const }
  if (count <= 6) return { cols: 3, rows: 2, size: 'small' as const }
  return { cols: 3, rows: 3, size: 'small' as const }
}

