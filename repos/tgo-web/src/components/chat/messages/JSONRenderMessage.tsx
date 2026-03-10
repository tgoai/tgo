import React, { useMemo } from 'react';
import { type DataPart, useJsonRenderMessage } from '@json-render/react';

import type { Message } from '@/types';
import MarkdownContent from '../MarkdownContent';
import { JSONRenderSurface } from '../jsonRender/JSONRenderSurface';

/** Strip ```spec fences from text to prevent leaking raw JSON patches in fallback rendering. */
function stripSpecFences(text: string): string {
  return text.replace(/```spec[\s\S]*?```/g, '').replace(/```spec[\s\S]*/g, '').trim();
}

interface JSONRenderMessageProps {
  message: Message;
  isStaff: boolean;
  onSendMessage?: (message: string) => void;
}

// ---------------------------------------------------------------------------
// Grouping helpers — split an ordered DataPart[] into runs of the same kind
// so text and spec UI can be rendered in the original interleaved order.
// ---------------------------------------------------------------------------

type PartGroup =
  | { type: 'text'; text: string }
  | { type: 'spec'; parts: DataPart[] };

function groupParts(parts: DataPart[]): PartGroup[] {
  const groups: PartGroup[] = [];
  for (const part of parts) {
    if (part.type === 'text') {
      const last = groups[groups.length - 1];
      if (last?.type === 'text') {
        last.text += part.text || '';
      } else {
        groups.push({ type: 'text', text: part.text || '' });
      }
    } else {
      const last = groups[groups.length - 1];
      if (last?.type === 'spec') {
        last.parts.push(part);
      } else {
        groups.push({ type: 'spec', parts: [part] });
      }
    }
  }
  return groups;
}

// ---------------------------------------------------------------------------
// Sub-component: render a single group of consecutive spec DataParts
// ---------------------------------------------------------------------------

const JSONRenderGroup: React.FC<{
  parts: DataPart[];
  loading?: boolean;
  onSendMessage?: (message: string) => void;
}> = ({ parts, loading, onSendMessage }) => {
  const { spec } = useJsonRenderMessage(parts);
  if (!spec) return null;
  return <JSONRenderSurface spec={spec} loading={loading} onSendMessage={onSendMessage} />;
};

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

const JSONRenderMessage: React.FC<JSONRenderMessageProps> = ({ message, isStaff, onSendMessage }) => {
  const meta = message.metadata ?? {};
  const uiParts = useMemo(() => {
    return Array.isArray(meta.ui_parts) ? (meta.ui_parts as DataPart[]) : [];
  }, [meta.ui_parts]);

  // Suppress "Missing element" warnings while the stream is still delivering patches
  const loading = meta.stream_end !== 1 && Boolean(meta.has_stream_data);

  const groups = useMemo(() => groupParts(uiParts), [uiParts]);

  // Fallback: if no groups produced (e.g. empty ui_parts), show raw content
  const hasContent = groups.length > 0;

  return (
    <div
      className={`json-render-message inline-block max-w-full p-3 shadow-sm overflow-hidden ${
        isStaff
          ? 'bg-blue-500 dark:bg-blue-600 text-white rounded-lg rounded-tr-none'
          : 'bg-white dark:bg-gray-700 rounded-lg rounded-tl-none border border-gray-100 dark:border-gray-600'
      }`}
    >
      {hasContent ? (
        groups.map((group, i) => {
          if (group.type === 'text') {
            if (!group.text.trim()) return null;
            return (
              <div key={i} className={`text-sm ${isStaff ? 'text-white' : 'text-gray-900 dark:text-gray-100'}`}>
                <MarkdownContent
                  content={group.text}
                  className={isStaff ? 'markdown-white' : ''}
                  onSendMessage={onSendMessage}
                />
              </div>
            );
          }
          return <JSONRenderGroup key={i} parts={group.parts} loading={loading} onSendMessage={onSendMessage} />;
        })
      ) : (
        (() => {
          const fallbackText = stripSpecFences(message.content || '');
          return fallbackText ? (
            <div className={`text-sm ${isStaff ? 'text-white' : 'text-gray-900 dark:text-gray-100'}`}>
              <MarkdownContent
                content={fallbackText}
                className={isStaff ? 'markdown-white' : ''}
                onSendMessage={onSendMessage}
              />
            </div>
          ) : null;
        })()
      )}
      {/* Debug: raw LLM ui_parts for websocket (streaming) messages only */}
      {meta.has_stream_data && (
        <pre className="json-render-debug" style={{ display: 'none' }} data-debug="llm-raw">
          {JSON.stringify(meta.ui_parts, null, 2)}
        </pre>
      )}
    </div>
  );
};

export default JSONRenderMessage;
