import { useEffect, useMemo, useRef } from 'react'
import styled from '@emotion/styled'
import type { ChatMessage, SystemMessagePayload, RegularMessagePayload } from '../types/chat'
import { isSystemMessageType } from '../types/chat'
import { formatMessageTime } from '../utils/time'
import { useChatStore } from '../store'
import { AlertCircle, RotateCw, Trash2 } from 'lucide-react'
import { ReasonCode } from 'easyjssdk'
import { Bubble, Cursor, AILoadingDots, TextMessage, ImageMessage, FileMessage, MixedMessage, MixedImages, SystemMessage } from './messages'
import { useTranslation } from 'react-i18next'



const Main = styled.main`
  flex:1; min-height:0; overflow:auto; padding: 12px 12px 8px; background: var(--bg-primary, #fff);
  overscroll-behavior: contain;
`
const List = styled.ul`list-style:none; margin:0; padding:0; display:flex; flex-direction:column; gap:12px;`
const Row = styled.div<{self:boolean}>`
  display:flex; ${p => p.self ? 'justify-content:flex-end;' : 'justify-content:flex-start;'}
`

const Meta = styled.div`font-size: 12px; color: var(--text-secondary, #6b7280); margin-top: 6px;`
const Status = styled('div')<{ self: boolean; kind: 'sending' | 'error' }>`
  font-size: 12px; margin-top: 6px; display:flex; align-items:center; gap:6px;
  ${p => p.self ? 'justify-content:flex-end;' : 'justify-content:flex-start;'}
  color: ${p => p.kind==='error' ? 'var(--error-color, #ef4444)' : 'var(--text-muted, #9ca3af)'};
`
const LinkBtn = styled.button`
  border:0; background:transparent; color:inherit; cursor:pointer; padding:0 2px; text-decoration: underline;
`
const TopNotice = styled.li`
  list-style:none; text-align:center; color: var(--text-secondary, #6b7280); font-size:12px; padding: 4px 0 8px;
`



export default function MessageList({ messages }: { messages: ChatMessage[] }){
  const { t } = useTranslation()
  const ref = useRef<HTMLDivElement>(null)
  const items = useMemo(()=> messages.map(m => ({...m, key: m.id})), [messages])

  const historyLoading = useChatStore(s => s.historyLoading)
  const historyHasMore = useChatStore(s => s.historyHasMore)
  const historyError = useChatStore(s => s.historyError)
  const loadMore = useChatStore(s => s.loadMoreHistory)

  const reasonText = (code: ReasonCode) => {
    switch(code){
      case ReasonCode.AuthFail: return t('errors.authFail')
      case ReasonCode.SubscriberNotExist: return t('errors.subscriberNotExist')
      case ReasonCode.NotAllowSend: return t('errors.notAllowSend')
      case ReasonCode.NotInWhitelist: return t('errors.notInWhitelist')
      case ReasonCode.RateLimit: return t('errors.rateLimit')
      case ReasonCode.Ban:
      case ReasonCode.SendBan: return t('errors.banned')
      case ReasonCode.ChannelNotExist:
      case ReasonCode.ChannelIDError: return t('errors.channelNotExist')
      case ReasonCode.Disband: return t('errors.disbanded')
      case ReasonCode.SystemError: return t('errors.systemError')
      case ReasonCode.Unknown:
      default: return t('errors.networkError')
    }
  }
  const canRetry = (code: ReasonCode) => ![
    ReasonCode.AuthFail,
    ReasonCode.NotAllowSend,
    ReasonCode.NotInWhitelist,
    ReasonCode.Ban,
    ReasonCode.SendBan,
    ReasonCode.Disband,
  ].includes(code)

  const isAtBottomRef = useRef(true)
  const preHeightRef = useRef<number | null>(null)

  useEffect(()=>{
    const el = ref.current
    if(!el) return
    const onScroll = () => {
      if (!el) return
      const nearTop = el.scrollTop <= 16
      isAtBottomRef.current = (el.scrollTop + el.clientHeight) >= (el.scrollHeight - 16)
      if (nearTop && !historyLoading && historyHasMore) {
        preHeightRef.current = el.scrollHeight
        void loadMore()
      }
    }
    el.addEventListener('scroll', onScroll)
    return () => el.removeEventListener('scroll', onScroll)
  }, [historyLoading, historyHasMore, loadMore])

  useEffect(()=>{
    const el = ref.current
    if(!el) return
    if (preHeightRef.current != null) {
      const delta = el.scrollHeight - preHeightRef.current
      el.scrollTop = delta
      preHeightRef.current = null
    } else if (isAtBottomRef.current) {
      el.scrollTop = el.scrollHeight
    }
  }, [items])

  const retry = useChatStore(s => s.retryMessage)
  const retryUpload = useChatStore(s => s.retryUpload)
  const cancelUpload = useChatStore(s => s.cancelUpload)
  const remove = useChatStore(s => s.removeMessage)
  const staffCache = useChatStore(s => s.staffInfoCache)


  return (
    <Main ref={ref} role="log" aria-live="polite">
      <List>
        {/* top status row */}
        {historyLoading && <TopNotice>{t('messageList.loadingHistory')}</TopNotice>}
        {!historyLoading && historyError && (
          <TopNotice style={{color:'#ef4444'}}>
            {t('messageList.loadHistoryFailed')}
            <button onClick={()=>loadMore()} style={{marginLeft:8, border:0, background:'transparent', color:'#ef4444', textDecoration:'underline', cursor:'pointer'}}>{t('common.retry')}</button>
          </TopNotice>
        )}
        {!historyLoading && !historyError && !historyHasMore && <TopNotice>{t('messageList.noMoreMessages')}</TopNotice>}
        {items.map(m => {
          // Check if this is a system message (type 1000-2000)
          const isSystemMsg = isSystemMessageType(m.payload.type)
          
          if (isSystemMsg) {
            const sysPayload = m.payload as SystemMessagePayload
            return (
              <li key={m.key}>
                <SystemMessage content={sysPayload.content} extra={sysPayload.extra} />
              </li>
            )
          }
          
          // After filtering out system messages, we can safely cast to RegularMessagePayload
          const payload = m.payload as RegularMessagePayload
          
          return (
          <li key={m.key}>
            <Row self={m.role==='user'}>
              {payload.type === 3 ? (
                <FileMessage url={payload.url} name={payload.name} size={payload.size} />
              ) : payload.type === 12 ? (
                <div style={{ display:'flex', flexDirection:'column', gap: 8, alignItems: 'flex-start' }}>
                  {(payload.content && payload.content.length>0) && (
                    <Bubble self={m.role==='user'}>
                      <MixedMessage content={payload.content} />
                    </Bubble>
                  )}
                  {(Array.isArray(payload.images) && payload.images.length>0) && (
                    <MixedImages images={payload.images} />
                  )}
                  {payload.file && (
                    <FileMessage url={payload.file.url} name={payload.file.name} size={payload.file.size} />
                  )}
                </div>
              ) : payload.type === 2 ? (
                <ImageMessage url={payload.url} w={payload.width} h={payload.height} />
              ) : m.errorMessage ? (
                /* 有错误信息 - 在气泡内显示错误 */
                <Bubble self={false}>
                  <div style={{ color: 'var(--error-color, #ef4444)', display: 'flex', alignItems: 'center', gap: 6 }}>
                    <AlertCircle size={14} /> {m.errorMessage}
                  </div>
                </Bubble>
              ) : m.streamData && m.streamData.length ? (
                /* Streaming content - show with blinking cursor */
                <Bubble self={false}>
                  <TextMessage content={m.streamData} />
                  <Cursor />
                </Bubble>
              ) : payload.type === 100 ? (
                /* AI Loading - show only when no streamData yet */
                <Bubble self={false}>
                  <AILoadingDots><span /><span /><span /></AILoadingDots>
                </Bubble>
              ) : (
                <Bubble self={m.role==='user'}>
                  {payload.type === 1 ? (
                    <TextMessage content={payload.content} />
                  ) : (
                    <div>[消息]</div>
                  )}
                </Bubble>
              )}
            </Row>
            {m.role==='agent' && (
              <Meta>{formatMessageTime(m.time)}</Meta>
            )}
            {m.role==='user' && (
              <Meta style={{ textAlign: 'right' }}>{formatMessageTime(m.time)}</Meta>
            )}
            {m.role==='user' && m.status === 'sending' && (
              <Status self kind="sending">{t('messageList.sending')}</Status>
            )}
            {m.role==='user' && m.status === 'uploading' && (
              <Status self kind="sending">
                {t('messageList.uploading')} {typeof m.uploadProgress === 'number' ? `${m.uploadProgress}%` : ''}
                <span>·</span>
                <LinkBtn onClick={()=>cancelUpload(m.id)} aria-label={t('common.cancel')}>{t('common.cancel')}</LinkBtn>
              </Status>
            )}
            {m.role==='user' && typeof m.reasonCode === 'number' && m.reasonCode !== ReasonCode.Success && (
              <Status self kind="error">
                <AlertCircle size={14} /> {reasonText(m.reasonCode as ReasonCode)}
                {canRetry(m.reasonCode as ReasonCode) && (
                  <>
                    <LinkBtn onClick={()=>retry(m.id)} aria-label={t('common.retry')}><RotateCw size={14} /> {t('common.retry')}</LinkBtn>
                    <span>·</span>
                  </>
                )}
                <LinkBtn onClick={()=>remove(m.id)} aria-label={t('common.delete')}><Trash2 size={14} /> {t('common.delete')}</LinkBtn>
              </Status>
            )}
            {m.role==='user' && m.uploadError && (
              <Status self kind="error">
                <AlertCircle size={14} /> {m.uploadError}
                <LinkBtn onClick={()=>retryUpload(m.id)} aria-label={t('common.retry')}><RotateCw size={14} /> {t('common.retry')}</LinkBtn>
                <span>·</span>
                <LinkBtn onClick={()=>remove(m.id)} aria-label={t('common.delete')}><Trash2 size={14} /> {t('common.delete')}</LinkBtn>
              </Status>
            )}

          </li>
        )})}
      </List>
    </Main>
  )
}

