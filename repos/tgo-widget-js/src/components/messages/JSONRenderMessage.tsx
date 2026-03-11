import { useMemo } from 'react'
import { type DataPart, useJsonRenderMessage } from '@json-render/react'
import type { ChatMessage } from '../../types/chat'
import MarkdownContent from '../MarkdownContent'
import JSONRenderSurface from '../jsonRender/JSONRenderSurface'
import { Cursor } from './messageStyles'

interface JSONRenderMessageProps {
  message: ChatMessage
  onSendMessage?: (message: string) => void
  showCursor?: boolean
}

// ---------------------------------------------------------------------------
// Grouping helpers — split an ordered DataPart[] into runs of the same kind
// so text and spec UI can be rendered in the original interleaved order.
// ---------------------------------------------------------------------------

type PartGroup =
  | { type: 'text'; text: string }
  | { type: 'spec'; parts: DataPart[] }

function groupParts(parts: DataPart[]): PartGroup[] {
  const groups: PartGroup[] = []
  for (const part of parts) {
    if (part.type === 'text') {
      const last = groups[groups.length - 1]
      if (last?.type === 'text') {
        last.text += part.text || ''
      } else {
        groups.push({ type: 'text', text: part.text || '' })
      }
    } else {
      const last = groups[groups.length - 1]
      if (last?.type === 'spec') {
        last.parts.push(part)
      } else {
        groups.push({ type: 'spec', parts: [part] })
      }
    }
  }
  return groups
}

// Sub-component: render a consecutive group of spec DataParts
function JSONRenderGroup({ parts, loading, onSendMessage }: { parts: DataPart[]; loading?: boolean; onSendMessage?: (message: string) => void }) {
  const { spec } = useJsonRenderMessage(parts)
  if (!spec) return null
  return <JSONRenderSurface spec={spec} loading={loading} onSendMessage={onSendMessage} />
}

export default function JSONRenderMessage({ message, onSendMessage, showCursor = false }: JSONRenderMessageProps) {
  const uiParts = useMemo(() => {
    return Array.isArray(message.uiParts) ? (message.uiParts as DataPart[]) : []
  }, [message.uiParts])

  // Suppress "Missing element" warnings while the stream is still delivering patches
  const loading = showCursor

  const groups = useMemo(() => groupParts(uiParts), [uiParts])

  const hasContent = groups.length > 0

  // Fallback text for when there are no groups — strip spec fences to prevent raw JSON leaking
  const payloadText = message.payload.type === 1 ? message.payload.content : ''
  const rawFallback = (message.streamData && message.streamData.trim())
    ? message.streamData
    : payloadText
  const fallbackText = rawFallback.includes('```spec')
    ? rawFallback.replace(/```spec[\s\S]*?```/g, '').replace(/```spec[\s\S]*/g, '').trim()
    : rawFallback

  if (!hasContent && !fallbackText) return null

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4, maxWidth: '100%' }}>
      {hasContent ? (
        groups.map((group, i) => {
          if (group.type === 'text') {
            if (!group.text.trim()) return null
            return (
              <div key={i}>
                <MarkdownContent content={group.text} onSendMessage={onSendMessage} />
                {showCursor && i === groups.length - 1 ? <Cursor /> : null}
              </div>
            )
          }
          return <JSONRenderGroup key={i} parts={group.parts} loading={loading} onSendMessage={onSendMessage} />
        })
      ) : (
        fallbackText ? (
          <div>
            <MarkdownContent content={fallbackText} onSendMessage={onSendMessage} />
            {showCursor ? <Cursor /> : null}
          </div>
        ) : null
      )}
    </div>
  )
}
