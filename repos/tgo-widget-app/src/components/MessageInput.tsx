import React, { useRef, useState } from 'react'
import styled from '@emotion/styled'
import { Paperclip, Smile, Mic, Send as SendIcon, Square as StopIcon } from 'lucide-react'
import { useChatStore } from '../store'
import { useTranslation } from 'react-i18next'


const Bar = styled.footer`
  display:flex; align-items:center; padding:12px; border-top:0; background: var(--bg-primary, #fff);
`
const Card = styled.div`
  position: relative;
  flex:1; display:flex; flex-direction:column; background: var(--bg-input, #fff);
  border:1px solid var(--border-primary, #e5e7eb); border-radius:24px; padding:10px 12px;
  box-shadow: 0 8px 30px rgba(0,0,0,.06);
`
const Top = styled.div`display:flex; align-items:center;`
const Input = styled.input`
  flex:1; height:24px; padding:4px 2px; border:0; outline:none; background:transparent; font-size:14px;
  color: var(--text-primary, #111827);
  &::placeholder{ color: var(--text-muted, #9ca3af); }
`
const Actions = styled.div`display:flex; align-items:center; justify-content:space-between; margin-top:8px;`
const Icons = styled.div`display:flex; align-items:center; gap:8px; color: var(--text-secondary, #6b7280);`
const IconBtn = styled.button<{active?:boolean}>`
  width:32px; height:32px; display:grid; place-items:center; border-radius:8px; border:0;
  background:${p=>p.active?'var(--bg-tertiary, #f3f4f6)':'transparent'}; color: var(--text-secondary, #6b7280); cursor:pointer;
  transition: background-color .15s ease; &:hover{ background: var(--bg-tertiary, #f3f4f6); }
`
const Send = styled.button<{active?:boolean}>`
  width:36px; height:36px; display:grid; place-items:center; border-radius:999px; border:0; cursor:pointer;
  background: ${p=>p.active? 'var(--primary)' : 'var(--bg-tertiary, #f3f4f6)'};
  color: ${p=>p.active? '#fff' : 'var(--text-muted, #9ca3af)'};
`

const Interrupt = styled(Send)`
  background: var(--error-color, #ef4444); color: #fff;
  &:disabled{ opacity:.6; cursor:not-allowed; }
`


// Emoji popover styles
const EmojiPopover = styled.div`
  position: absolute; bottom: calc(100% + 8px); left: 8px; width: 340px; max-height: 320px; overflow: hidden;
  background: var(--bg-primary, #fff); border:1px solid var(--border-primary, #e5e7eb); border-radius:12px;
  box-shadow: 0 8px 24px rgba(0,0,0,.12); z-index:2147483002;
  display:flex; flex-direction:column;
`;
const EmojiTabs = styled.div`display:flex; gap:6px; padding:8px 10px; border-bottom:1px solid var(--bg-tertiary, #f3f4f6);`
const EmojiTab = styled.button<{active?:boolean}>`
  padding:6px 8px; border-radius:8px; border:0; background:${p=>p.active?'var(--bg-tertiary, #f3f4f6)':'transparent'}; cursor:pointer;
`
const EmojiGrid = styled.div`
  padding:10px; display:grid; grid-template-columns: repeat(8, 1fr); gap:6px; overflow:auto;
`;
const EmojiButton = styled.button`
  width: 34px; height: 34px; display:grid; place-items:center; border-radius:8px; border:0; background:transparent; cursor:pointer;
  font-size:22px; line-height:1; &:hover{ background: var(--bg-tertiary, #f3f4f6); }
`;

export default function MessageInput({ onSend }: { onSend(text: string): void }){
  const { t } = useTranslation()
  const ref = useRef<HTMLInputElement>(null)
  const [hasText, setHasText] = useState(false)
  const [emojiOpen, setEmojiOpen] = useState(false)
  const [tab, setTab] = useState<'smileys'|'hearts'|'party'>('smileys')
  const popRef = useRef<HTMLDivElement>(null)
  const emojiBtnRef = useRef<HTMLButtonElement>(null)
  const caretStart = useRef<number | null>(null)
  const caretEnd = useRef<number | null>(null)
  // IME composing flag (for Chinese/Japanese/Korean etc.)
  const [isComposing, setIsComposing] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)
  const uploadFiles = useChatStore(s => s.uploadFiles)
  const isStreaming = useChatStore(s => s.isStreaming)
  const streamCanceling = useChatStore(s => s.streamCanceling)
  const cancelStreaming = useChatStore(s => s.cancelStreaming)

  const updateHasText = ()=> setHasText(!!ref.current?.value?.trim())
  const updateCaret = ()=>{
    if(!ref.current) return; caretStart.current = ref.current.selectionStart; caretEnd.current = ref.current.selectionEnd;
  }
  const insertAtCursor = (text: string)=>{
    const el = ref.current; if(!el) return;
    const start = el.selectionStart ?? el.value.length;
    const end = el.selectionEnd ?? el.value.length;
    const before = el.value.slice(0, start);
    const after = el.value.slice(end);
    el.value = before + text + after;
    const newPos = start + text.length;
    el.focus();
    requestAnimationFrame(()=>{ el.setSelectionRange(newPos, newPos); updateCaret(); updateHasText(); })
  }

  const onEmojiClick = (e: string)=>{ insertAtCursor(e); }

  // IME: composition handlers
  const handleCompositionStart = () => { setIsComposing(true) }
  const handleCompositionEnd = (e: React.CompositionEvent<HTMLInputElement>) => {
    setIsComposing(false)
    // Update state after composition commits final text
    try { updateHasText() } catch {}
  }
  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      const composingNow = isComposing || !!(e.nativeEvent as any)?.isComposing
      if (composingNow) return
      // When streaming, ignore Enter (do not send)
      if (isStreaming) { e.preventDefault(); return }
      e.preventDefault()
      fire()
    }
  }

  // outside click to close
  React.useEffect(()=>{
    if(!emojiOpen) return;
    const handler = (ev: MouseEvent | TouchEvent)=>{
      const t = ev.target as Node;
      if(popRef.current?.contains(t)) return;
      if(emojiBtnRef.current?.contains(t as Node)) return;
      setEmojiOpen(false);
    };
    document.addEventListener('mousedown', handler);
    document.addEventListener('touchstart', handler, { passive: true } as any);
    return ()=>{
      document.removeEventListener('mousedown', handler);
      document.removeEventListener('touchstart', handler as any);
    }
  }, [emojiOpen])

  const fire = async ()=>{
    const v = ref.current?.value?.trim(); if(!v) return;
    // If a previous AI stream is ongoing, auto-cancel before sending a new message
    if (isStreaming && !streamCanceling) { try { await cancelStreaming('auto_cancel_on_new_send') } catch {} }
    onSend(v)
    if(ref.current) ref.current.value=''; setHasText(false);
  }

  const handlePickFiles = () => { fileRef.current?.click() }
  const handleFilesSelected = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files || files.length === 0) return
    // Optional: basic size limit (25MB)
    const MAX = 25 * 1024 * 1024
    const tooLarge = Array.from(files).find(f => f.size > MAX)
    if (tooLarge) {
      alert(t('messageInput.fileTooLarge', { size: (MAX/1024/1024)|0, name: tooLarge.name }))
      e.target.value = ''
      return
    }
    // Delegate to store
    void uploadFiles(files)
    // Allow re-selecting the same file
    e.target.value = ''
  }

  const SMILEYS = ['😀','😃','😄','😁','😆','😅','😂','🙂','🙃','😉','😊','😇','🥰','😍','🤩','😘','😗','☺️','😚','😙','😋','😛','😜','🤪','😝','🫠','🤗','🥲','🫡','🤔']
  const HEARTS = ['❤️','🩵','💛','💚','💙','💜','🧡','🖤','🤍','🤎','💘','💖','💗','💓','💕','💞']
  const PARTY  = ['🎉','🎊','✨','⭐️','🌟','💫','🔥','⚡️','🎈','🎁','🥳','👏','👍','🙌','🤝']
  const LIST = tab==='smileys'? SMILEYS : tab==='hearts'? HEARTS : PARTY

  return (
    <Bar>
      <Card>
        <Top>
          <Input ref={ref} placeholder={t('messageInput.placeholder')} onFocus={updateCaret} onClick={updateCaret} onKeyUp={updateCaret}
                 onChange={()=>{ updateHasText(); updateCaret(); }}
                 onCompositionStart={handleCompositionStart}
                 onCompositionEnd={handleCompositionEnd}
                 onKeyDown={handleKeyDown}
          />
        </Top>
        <Actions>
          <Icons>
            <input ref={fileRef} type="file" multiple style={{ display: 'none' }} onChange={handleFilesSelected}
                    accept={['image/*','application/pdf','application/msword','application/vnd.openxmlformats-officedocument.wordprocessingml.document','application/vnd.ms-excel','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','application/zip','application/x-zip-compressed','application/vnd.ms-powerpoint','application/vnd.openxmlformats-officedocument.presentationml.presentation','text/plain','text/markdown'].join(',')}
            />
            <IconBtn aria-label={t('messageInput.attach')} onClick={handlePickFiles}><Paperclip size={18} /></IconBtn>
            <IconBtn ref={emojiBtnRef} active={emojiOpen} aria-label={t('messageInput.emoji')} onClick={()=>setEmojiOpen(v=>!v)}><Smile size={18} /></IconBtn>
            {/* <IconBtn aria-label="Voice"><Mic size={18} /></IconBtn> */}
          </Icons>
          {isStreaming ? (
            <Interrupt onClick={()=>{ if(!streamCanceling) void cancelStreaming('user_click') }} aria-label={t('messageInput.interrupt')} disabled={streamCanceling}><StopIcon size={18} /></Interrupt>
          ) : (
            <Send onClick={fire} aria-label={t('messageInput.send')} active={hasText}><SendIcon size={18} /></Send>
          )}
        </Actions>
        {emojiOpen && (
          <EmojiPopover ref={popRef} role="dialog" aria-label="Emoji picker">
            <EmojiTabs>
              <EmojiTab active={tab==='smileys'} onClick={()=>setTab('smileys')}>😀</EmojiTab>
              <EmojiTab active={tab==='hearts'} onClick={()=>setTab('hearts')}>❤️</EmojiTab>
              <EmojiTab active={tab==='party'} onClick={()=>setTab('party')}>🎉</EmojiTab>
            </EmojiTabs>
            <EmojiGrid>
              {LIST.map(ch => (
                <EmojiButton key={ch} onClick={()=>onEmojiClick(ch)}>{ch}</EmojiButton>
              ))}
            </EmojiGrid>
          </EmojiPopover>
        )}
      </Card>
    </Bar>
  )
}

