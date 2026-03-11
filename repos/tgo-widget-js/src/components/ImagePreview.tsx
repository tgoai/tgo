import React, { useState, useEffect, useCallback, useRef } from 'react'
import styled from '@emotion/styled'

interface ImagePreviewProps {
  images: string[]
  initialIndex?: number
  onClose: () => void
}

const Overlay = styled.div`
  position: fixed;
  inset: 0;
  z-index: 9999;
  background: rgba(0, 0, 0, 0.9);
  display: flex;
  align-items: center;
  justify-content: center;
  animation: fadeIn 0.2s ease;
  
  @keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
  }
`

const CloseButton = styled.button`
  position: absolute;
  top: 16px;
  right: 16px;
  width: 40px;
  height: 40px;
  border: none;
  background: rgba(255, 255, 255, 0.15);
  border-radius: 50%;
  color: #fff;
  font-size: 24px;
  cursor: pointer;
  display: grid;
  place-items: center;
  transition: background 0.2s;
  z-index: 10;
  
  &:hover {
    background: rgba(255, 255, 255, 0.25);
  }
`

const NavButton = styled.button<{ direction: 'left' | 'right' }>`
  position: absolute;
  top: 50%;
  ${p => p.direction}: 16px;
  transform: translateY(-50%);
  width: 48px;
  height: 48px;
  border: none;
  background: rgba(255, 255, 255, 0.15);
  border-radius: 50%;
  color: #fff;
  font-size: 24px;
  cursor: pointer;
  display: grid;
  place-items: center;
  transition: background 0.2s, opacity 0.2s;
  z-index: 10;
  
  &:hover {
    background: rgba(255, 255, 255, 0.25);
  }
  
  &:disabled {
    opacity: 0.3;
    cursor: not-allowed;
  }
`

const ImageContainer = styled.div`
  max-width: 90vw;
  max-height: 85vh;
  display: flex;
  align-items: center;
  justify-content: center;
  user-select: none;
`

const PreviewImage = styled.img<{ scale: number }>`
  max-width: 90vw;
  max-height: 85vh;
  object-fit: contain;
  border-radius: 4px;
  transform: scale(${p => p.scale});
  transition: transform 0.2s ease;
  cursor: ${p => p.scale > 1 ? 'zoom-out' : 'zoom-in'};
`

const Counter = styled.div`
  position: absolute;
  bottom: 20px;
  left: 50%;
  transform: translateX(-50%);
  color: rgba(255, 255, 255, 0.8);
  font-size: 14px;
  padding: 6px 16px;
  background: rgba(0, 0, 0, 0.4);
  border-radius: 16px;
`

const LoadingSpinner = styled.div`
  width: 40px;
  height: 40px;
  border: 3px solid rgba(255, 255, 255, 0.2);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  
  @keyframes spin {
    to { transform: rotate(360deg); }
  }
`

const ErrorMessage = styled.div`
  color: rgba(255, 255, 255, 0.7);
  font-size: 14px;
  text-align: center;
`

export const ImagePreview: React.FC<ImagePreviewProps> = ({ images, initialIndex = 0, onClose }) => {
  const [currentIndex, setCurrentIndex] = useState(initialIndex)
  const [scale, setScale] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const overlayRef = useRef<HTMLDivElement>(null)

  const currentImage = images[currentIndex]
  const hasMultiple = images.length > 1

  const goToPrev = useCallback(() => {
    if (currentIndex > 0) {
      setCurrentIndex(currentIndex - 1)
      setScale(1)
      setLoading(true)
      setError(false)
    }
  }, [currentIndex])

  const goToNext = useCallback(() => {
    if (currentIndex < images.length - 1) {
      setCurrentIndex(currentIndex + 1)
      setScale(1)
      setLoading(true)
      setError(false)
    }
  }, [currentIndex, images.length])

  const toggleZoom = useCallback(() => {
    setScale(s => s === 1 ? 2 : 1)
  }, [])

  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      switch (e.key) {
        case 'Escape':
          onClose()
          break
        case 'ArrowLeft':
          goToPrev()
          break
        case 'ArrowRight':
          goToNext()
          break
        case ' ':
        case 'Enter':
          e.preventDefault()
          toggleZoom()
          break
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    // Prevent body scroll
    document.body.style.overflow = 'hidden'

    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      document.body.style.overflow = ''
    }
  }, [onClose, goToPrev, goToNext, toggleZoom])

  const handleOverlayClick = (e: React.MouseEvent) => {
    if (e.target === overlayRef.current) {
      onClose()
    }
  }

  return (
    <Overlay ref={overlayRef} onClick={handleOverlayClick}>
      <CloseButton onClick={onClose} title="关闭 (Esc)">×</CloseButton>
      
      {hasMultiple && (
        <>
          <NavButton 
            direction="left" 
            onClick={goToPrev} 
            disabled={currentIndex === 0}
            title="上一张 (←)"
          >
            ‹
          </NavButton>
          <NavButton 
            direction="right" 
            onClick={goToNext} 
            disabled={currentIndex === images.length - 1}
            title="下一张 (→)"
          >
            ›
          </NavButton>
        </>
      )}

      <ImageContainer>
        {loading && !error && <LoadingSpinner />}
        {error ? (
          <ErrorMessage>图片加载失败</ErrorMessage>
        ) : (
          <PreviewImage
            src={currentImage}
            alt={`预览图片 ${currentIndex + 1}`}
            scale={scale}
            onClick={toggleZoom}
            onLoad={() => setLoading(false)}
            onError={() => { setLoading(false); setError(true) }}
            style={{ display: loading ? 'none' : 'block' }}
            draggable={false}
          />
        )}
      </ImageContainer>

      {hasMultiple && (
        <Counter>{currentIndex + 1} / {images.length}</Counter>
      )}
    </Overlay>
  )
}

// Global image preview state management
type PreviewState = {
  images: string[]
  initialIndex: number
} | null

let previewState: PreviewState = null
let listeners: Set<(state: PreviewState) => void> = new Set()

export const imagePreviewManager = {
  open: (images: string[], initialIndex = 0) => {
    previewState = { images, initialIndex }
    listeners.forEach(fn => fn(previewState))
  },
  close: () => {
    previewState = null
    listeners.forEach(fn => fn(null))
  },
  subscribe: (fn: (state: PreviewState) => void) => {
    listeners.add(fn)
    return () => { listeners.delete(fn) }
  },
  getState: () => previewState
}

// Hook to use the image preview
export function useImagePreview() {
  const [state, setState] = useState<PreviewState>(imagePreviewManager.getState())

  useEffect(() => {
    return imagePreviewManager.subscribe(setState)
  }, [])

  return state
}

// Wrapper component to be placed at app root
export const ImagePreviewProvider: React.FC = () => {
  const state = useImagePreview()

  if (!state) return null

  return (
    <ImagePreview
      images={state.images}
      initialIndex={state.initialIndex}
      onClose={imagePreviewManager.close}
    />
  )
}

export default ImagePreview

