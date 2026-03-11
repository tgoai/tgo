import { useState, useEffect } from 'react'
import { ImgBox, ImgEl } from './messageStyles'
import { imagePreviewManager } from '../ImagePreview'

export interface ImageMessageProps {
  url: string
  w: number
  h: number
  /** 所有相关图片列表（用于多图预览导航） */
  allImages?: string[]
  /** 当前图片在列表中的索引 */
  imageIndex?: number
}

// Get max width from CSS variable, defaulting to 280
function getMaxWidth(): number {
  try {
    const val = getComputedStyle(document.documentElement).getPropertyValue('--bubble-max-width').trim()
    // Parse pixel value or percentage
    if (val.endsWith('px')) {
      return parseInt(val, 10) || 280
    }
    // For percentage or min() values, use a reasonable max for expanded state
    if (val.includes('%') || val.includes('min(')) {
      return 500 // larger max for expanded view
    }
  } catch {}
  return 280
}

export default function ImageMessage({ url, w, h, allImages, imageIndex = 0 }: ImageMessageProps){
  const [error, setError] = useState(false)
  const [maxW, setMaxW] = useState(280)

  // Listen for CSS variable changes
  useEffect(() => {
    const updateMaxW = () => setMaxW(getMaxWidth())
    updateMaxW()

    // Use MutationObserver to detect style changes on root
    const observer = new MutationObserver(updateMaxW)
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['style'] })

    return () => observer.disconnect()
  }, [])

  const handleClick = () => {
    const images = allImages && allImages.length > 0 ? allImages : [url]
    imagePreviewManager.open(images, imageIndex)
  }

  const maxH = Math.round(maxW * 0.78) // maintain similar aspect ratio constraint
  const scale = Math.min(maxW / Math.max(1, w), maxH / Math.max(1, h), 1)
  const dw = Math.max(48, Math.round(w * scale))
  const dh = Math.max(48, Math.round(h * scale))
  return (
    <ImgBox
      style={{ width: dw, height: dh }}
      onClick={handleClick}
      title="点击查看大图"
      role="button"
      aria-label="查看大图"
    >
      {!error ? (
        <ImgEl src={url} alt="[图片]" loading="lazy" onError={()=>setError(true)} />
      ) : (
        <div style={{width:'100%',height:'100%',display:'grid',placeItems:'center', color:'#9ca3af', fontSize:12}}>图片加载失败</div>
      )}
    </ImgBox>
  )
}

