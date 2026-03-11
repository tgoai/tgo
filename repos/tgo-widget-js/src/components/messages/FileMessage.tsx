import { Download } from 'lucide-react'
import { getFileIcon } from '../../utils/fileIcon'
import { formatFileSize } from './messageUtils'
import { FileAction, FileCard, FileIconBox, FileInfo, FileName, FileSize } from './messageStyles'

export interface FileMessageProps {
  url: string
  name: string
  size: number
}

export default function FileMessage({ url, name, size }: FileMessageProps){
  const icon = getFileIcon(name, undefined, 40)
  const open = ()=>{ try { window.open(url, '_blank') } catch {} }
  const label = `下载文件：${name}`
  return (
    <FileCard onClick={open} role="button" aria-label={label} title={label}>
      <FileIconBox aria-hidden>{icon}</FileIconBox>
      <FileInfo>
        <FileName title={name}>{name}</FileName>
        <FileSize>{formatFileSize(size)}</FileSize>
      </FileInfo>
      <FileAction href={url} target="_blank" rel="noreferrer" download onClick={e=>e.stopPropagation()} aria-label="下载">
        <Download size={20} />
      </FileAction>
    </FileCard>
  )
}

