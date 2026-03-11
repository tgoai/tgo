import { useState, useMemo } from 'react'
import ImageMessage from './ImageMessage'
import { Grid, GridImg, GridItem } from './messageStyles'
import { getGridLayout } from './messageUtils'
import { imagePreviewManager } from '../ImagePreview'

export interface MixedImagesProps {
  images: Array<{ url: string; width: number; height: number }>
}

interface SquareItemProps {
  url: string
  moreCount?: number
  onClick: () => void
}

function SquareItem({ url, moreCount = 0, onClick }: SquareItemProps){
  const [error, setError] = useState(false)
  return (
    <GridItem onClick={onClick} title={moreCount>0?`+${moreCount}`:'点击查看大图'}>
      {!error ? (
        <GridImg src={url} alt="[图片]" loading="lazy" onError={()=>setError(true)} />
      ) : (
        <div style={{width:'100%',height:'100%',display:'grid',placeItems:'center', color:'#9ca3af', fontSize:12}}>图片加载失败</div>
      )}
      {moreCount > 0 && (
        <div style={{position:'absolute',inset:0,background:'rgba(0,0,0,0.45)',color:'#fff',display:'grid',placeItems:'center',fontSize:18,fontWeight:600}}>
          +{moreCount}
        </div>
      )}
    </GridItem>
  )
}

export default function MixedImages({ images }: MixedImagesProps){
  const imgs = Array.isArray(images) ? images : []
  const visible = imgs.slice(0, 9)
  const more = imgs.length - visible.length
  const layout = getGridLayout(visible.length)
  const isSingle = visible.length === 1

  // 所有图片的 URL 列表
  const allImageUrls = useMemo(() => imgs.map(img => img.url), [imgs])

  const handleImageClick = (index: number) => {
    imagePreviewManager.open(allImageUrls, index)
  }

  if (visible.length === 0) return null
  return (
    <div style={{ width: 'auto', maxWidth: 'var(--bubble-max-width, 280px)' }}>
      {isSingle ? (
        <ImageMessage 
          url={visible[0].url} 
          w={visible[0].width} 
          h={visible[0].height}
          allImages={allImageUrls}
          imageIndex={0}
        />
      ) : (
        <Grid style={{ gridTemplateColumns: `repeat(${layout.cols}, 1fr)` }}>
          {visible.map((img, idx) => (
            <SquareItem 
              key={idx} 
              url={img.url} 
              moreCount={idx === visible.length - 1 ? Math.max(0, more) : 0}
              onClick={() => handleImageClick(idx)}
            />
          ))}
        </Grid>
      )}
    </div>
  )
}

