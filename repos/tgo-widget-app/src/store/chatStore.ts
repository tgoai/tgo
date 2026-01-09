import { create } from 'zustand'
import IMService from '../services/wukongim'
import type { ChatMessage, MessagePayload } from '../types/chat'
import { isSystemMessageType } from '../types/chat'
import { loadCachedVisitor, registerVisitor, saveCachedVisitor } from '../services/visitor'
import { resolveApiKey } from '../utils/url'
import { ReasonCode } from 'easyjssdk'
import { syncVisitorMessages, type WuKongIMMessage } from '../services/messageHistory'
import { fetchChannelInfo, type ChannelInfo } from '../services/channel'
import type { StaffInfo } from '../services/channel'
import { uploadChatFile, readImageDimensions } from '../services/upload'
import { collectVisitorSystemInfo } from '../utils/systemInfo'
import { playNotificationSound, showBrowserNotification, requestNotificationPermission } from '../utils/notification'
import usePlatformStore from './platformStore'
import i18n from '../i18n'


// Keep module-level unsubs to avoid duplicate registrations on re-init
let offMsg: null | (()=>void) = null
let offStatus: null | (()=>void) = null
let offCustom: null | (()=>void) = null


// Streaming control timer (auto-revert if no end event)
let streamTimer: any = null
const STREAM_TIMEOUT_MS = 60000

export type ChatConfig = {
  apiBase: string
}

export type ChatState = {
  messages: ChatMessage[]
  online: boolean
  initializing: boolean
  error?: string | null
  // history state
  historyLoading: boolean
  historyHasMore: boolean
  historyError?: string | null
  earliestSeq: number | null
  // channel / identity
  apiBase?: string
  myUid?: string
  channelId?: string
  channelType?: number
  // staff info cache
  staffInfoCache: Record<string, StaffInfo>
  fetchStaffInfo: (uid: string) => Promise<void>
  // actions
  initIM: (cfg: ChatConfig) => Promise<void>
  sendMessage: (text: string) => Promise<void>
  // uploads
  uploadFiles: (files: FileList | File[]) => Promise<void>
  retryUpload: (messageId: string) => Promise<void>
  cancelUpload: (messageId: string) => void
  // retry/remove
  retryMessage: (messageId: string) => Promise<void>
  removeMessage: (messageId: string) => void
  // history
  loadInitialHistory: (limit?: number) => Promise<void>
  loadMoreHistory: (limit?: number) => Promise<void>
  // streaming
  isStreaming: boolean
  streamCanceling: boolean
  streamingClientMsgNo?: string
  markStreamingStart: (clientMsgNo: string) => void
  markStreamingEnd: (clientMsgNo?: string) => void
  cancelStreaming: (reason?: string) => Promise<void>
  appendStreamData: (clientMsgNo: string, data: string) => void
  finalizeStreamMessage: (clientMsgNo: string, errorMessage?: string) => void
  ensureWelcomeMessage: (text: string) => void
  // unread count
  unreadCount: number
  clearUnreadCount: () => void
  incrementUnreadCount: () => void
}

const initialMessages: ChatMessage[] = []

function mapChannelTypeToString(t?: number): 'person' | 'group' {
  if (t === 1) return 'person'
  if (t === 2) return 'group'
  // Fallback: many platforms use group for customer service routing
  return 'group'
}

function toPayloadFromAny(raw: any): MessagePayload {
  const t = raw?.type
  if (t === 1 && typeof raw?.content === 'string') return { type: 1, content: raw.content }
  if (t === 2 && typeof raw?.url === 'string' && typeof raw?.width === 'number' && typeof raw?.height === 'number') {
    return { type: 2, url: raw.url, width: raw.width, height: raw.height }
  }
  if (t === 3 && typeof raw?.url === 'string' && typeof raw?.name === 'string' && typeof raw?.size === 'number') {
    return { type: 3, content: (typeof raw?.content === 'string' && raw.content) ? raw.content : '[文件]', url: raw.url, name: raw.name, size: raw.size }
  }
  if (t === 12 && typeof raw?.content === 'string' && Array.isArray(raw?.images)) {
    const images = raw.images
      .filter((i: any) => i && typeof i.url === 'string' && typeof i.width === 'number' && typeof i.height === 'number')
      .map((i: any) => ({ url: i.url, width: i.width, height: i.height }))
    let file: undefined | { url: string; name: string; size: number } = undefined
    if (raw?.file && typeof raw.file.url === 'string' && typeof raw.file.name === 'string' && typeof raw.file.size === 'number') {
      file = { url: raw.file.url, name: raw.file.name, size: raw.file.size }
    }
    return file ? { type: 12, content: raw.content, images, file } : { type: 12, content: raw.content, images }
  }
  if (t === 99 && typeof raw?.cmd === 'string') return { type: 99, cmd: raw.cmd, param: raw?.param ?? {} }
  if (t === 100) return { type: 100 }
  // System message (type 1000-2000)
  if (typeof t === 'number' && isSystemMessageType(t) && typeof raw?.content === 'string') {
    return { type: t, content: raw.content, extra: Array.isArray(raw?.extra) ? raw.extra : undefined }
  }
  if (typeof raw === 'string') return { type: 1, content: raw }
  return { type: 1, content: typeof raw?.content === 'string' ? raw.content : JSON.stringify(raw ?? {}) }
}

const pendingFiles = new Map<string, File>()
const uploadControllers = new Map<string, AbortController>()

function mapHistoryToChatMessage(m: WuKongIMMessage, myUid?: string): ChatMessage {
  const isStreamEnded = m?.setting_flags?.stream === true && m?.end === 1 && typeof m?.stream_data === 'string' && m.stream_data.length > 0
  const payload: MessagePayload = isStreamEnded ? { type: 1, content: m.stream_data as string } : toPayloadFromAny(m?.payload)
  // 检查消息的 error 字段（与 payload 平级）
  const errorMessage = m?.error ? String(m.error) : undefined
  return {
    id: m.message_id_str ?? m.client_msg_no ?? `h-${m.message_seq}`,
    role: m.from_uid && myUid && m.from_uid === myUid ? 'user' : 'agent',
    payload,
    time: new Date((m.timestamp || 0) * 1000),
    messageSeq: typeof m.message_seq === 'number' ? m.message_seq : undefined,
    clientMsgNo: m.client_msg_no ? String(m.client_msg_no) : undefined,
    fromUid: m.from_uid ? String(m.from_uid) : undefined,
    channelId: m.channel_id ? String(m.channel_id) : undefined,
    channelType: typeof m.channel_type === 'number' ? m.channel_type : undefined,
    errorMessage,
  }
}

const inflightStaff = new Set<string>()

export const useChatStore = create<ChatState>((set, get) => ({
  messages: initialMessages,
  online: false,
  initializing: false,
  error: null,
  historyLoading: false,
  historyHasMore: true,
  historyError: null,
  earliestSeq: null,
  // streaming state
  isStreaming: false,
  streamCanceling: false,
  streamingClientMsgNo: undefined,
  unreadCount: 0,
  staffInfoCache: {},
  fetchStaffInfo: async (uid: string) => {
    const st = get()
    if (!uid) return
    if (st.staffInfoCache[uid]) return
    if (inflightStaff.has(uid)) return
    // require apiBase and platformApiKey
    const apiBase = st.apiBase
    const platformApiKey = resolveApiKey() || ''
    if (!apiBase || !platformApiKey) return
    inflightStaff.add(uid)
    try {
      const info: ChannelInfo = await fetchChannelInfo({
        apiBase,
        platformApiKey,
        channelId: uid,
        channelType: 1,
      })
      const name = info?.name || (info?.extra?.name ?? info?.extra?.nickname) || uid
      const avatar = info?.avatar || info?.extra?.avatar_url
      set(s => ({ staffInfoCache: { ...s.staffInfoCache, [uid]: { name, avatar } } }))
    } catch (e) {
      // swallow errors; keep cache empty to allow retry in future if desired
    } finally {
      inflightStaff.delete(uid)
    }
  },

  initIM: async (cfg: ChatConfig) => {
    if (!cfg?.apiBase) return
    const st = get()
    if (st.initializing || IMService.isReady) return
    set({ initializing: true, error: null })
    try {
      // remember apiBase for history API
      set({ apiBase: cfg.apiBase })
      // Resolve platform API key from URL (?apiKey=...) on the control iframe URL
      const platformApiKey = resolveApiKey() || ''
      if (!platformApiKey) throw new Error('[Visitor] Missing apiKey in URL (?apiKey=...). Ensure the SDK injects it into the control iframe URL via history.replaceState.')

      // Request notification permission
      requestNotificationPermission()

      // Load cached visitor/channel or register
      let cached = loadCachedVisitor(cfg.apiBase, platformApiKey)
      if (!cached) {
        const sys = collectVisitorSystemInfo()
        // 获取访客时区
        const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || null
        const res = await registerVisitor({
          apiBase: cfg.apiBase,
          platformApiKey,
          extra: {
            ...(sys ? { system_info: sys } : {}),
            timezone,
          },
        })
        saveCachedVisitor(cfg.apiBase, platformApiKey, res)
        cached = loadCachedVisitor(cfg.apiBase, platformApiKey)!
      }

      // WuKongIM 连接要求：使用 visitor_id + "-vtr" 作为 uid
      const uid = String(cached.visitor_id || '')
      const uidForIM = uid.endsWith('-vtr') ? uid : `${uid}-vtr`
      const target = cached.channel_id
      const channelType = mapChannelTypeToString(cached.channel_type)
      const token = cached.im_token

      console.log('[Chat] Initializing IM with:', { uid: uidForIM, target, channelType, hasToken: !!token, token: token ? `${token.substring(0, 10)}...` : 'undefined' })

      // persist identity/channel info into store for history sync
      set({ myUid: uidForIM, channelId: target, channelType: cached.channel_type ?? 251 })

      if (!token) {
        throw new Error('[Chat] Missing im_token from visitor registration. Please check that the /v1/visitors/register API returns im_token field.')
      }

      await IMService.init({ apiBase: cfg.apiBase, uid: uidForIM, token, target, channelType })
      // status events (de-duped)
      if (offStatus) { try { offStatus() } catch {} ; offStatus = null }
      offStatus = IMService.onStatus((s) => {
        set({ online: s === 'connected' })
      })
      // message events (de-duped)
      if (offMsg) { try { offMsg() } catch {} ; offMsg = null }
      offMsg = IMService.onMessage((m) => {
        // skip self echoes
        if (!m.fromUid || m.fromUid === uidForIM) return
        // prefetch staff info by sender uid (personal channel)
        try { void get().fetchStaffInfo(m.fromUid) } catch {}
        const chat: ChatMessage = {
          id: String(m.messageId),
          role: 'agent',
          payload: toPayloadFromAny(m?.payload),
          time: new Date(m.timestamp * 1000),
          messageSeq: typeof m.messageSeq === 'number' ? m.messageSeq : undefined,
          clientMsgNo: m?.clientMsgNo,
          fromUid: m.fromUid,
          channelId: m.channelId,
          channelType: m.channelType,
        }
        // Check if message already exists (de-duplicate)
        const currentState = get()
        if (currentState.messages.some(x => x.id === chat.id)) return

        // New message received: play sound and show notification
        playNotificationSound()
        const pConfig = usePlatformStore.getState().config
        const title = pConfig.widget_title || 'Tgo'
        let content = ''
        if (chat.payload.type === 1) content = chat.payload.content
        else if (chat.payload.type === 2) content = '[图片]'
        else if (chat.payload.type === 3) content = '[文件]'
        
        if (content) {
          void showBrowserNotification(title, {
            body: content,
            icon: pConfig.logo_url || undefined,
          })
        }

        // Increment unread count (outside of set to avoid nested updates)
        get().incrementUnreadCount()

        set(state => {
          // If there is a streaming placeholder with the same clientMsgNo, merge into it
          if (chat.clientMsgNo) {
            const idx = state.messages.findIndex(x => x.clientMsgNo && x.clientMsgNo === chat.clientMsgNo)
            if (idx >= 0) {
              const next = state.messages.slice()
              next[idx] = { ...state.messages[idx], ...chat, streamData: undefined }
              return { messages: next }
            }
          }
          return { messages: [...state.messages, chat] }
        })
      })
      // custom stream events (de-duped)
      if (offCustom) { try { offCustom() } catch {} ; offCustom = null }
      offCustom = IMService.onCustom((ev:any) => {
        try {
          if (!ev) return

          // Handle stream start event
          if (ev.type === '___TextMessageStart') {
            const id = ev?.id ? String(ev.id) : ''
            if (!id) return
            console.log('[Chat] Stream started for message:', id)

            // Stream started: play sound
            playNotificationSound()
            const pConfig = usePlatformStore.getState().config
            void showBrowserNotification(pConfig.widget_title || 'Tgo', {
              body: i18n.t('messageInput.typing'),
              icon: pConfig.logo_url || undefined,
            })

            // Increment unread count for AI start
            get().incrementUnreadCount()

            try { get().markStreamingStart(id) } catch {}
            return
          }

          // Handle streaming content chunks
          if (ev.type === '___TextMessageContent') {
            const id = ev?.id ? String(ev.id) : ''
            if (!id) return
            const chunk = typeof ev.data === 'string' ? ev.data : (ev.data!=null ? String(ev.data) : '')
            if (!chunk) return
            get().appendStreamData(id, chunk)
            return
          }

          // Handle stream end event
          if (ev.type === '___TextMessageEnd') {
            const id = ev?.id ? String(ev.id) : ''
            if (!id) return
            // 如果 data 字段有值，则认为是错误信息
            const errorMessage = ev?.data ? String(ev.data) : undefined
            console.log('[Chat] Stream ended for message:', id, errorMessage ? `error: ${errorMessage}` : '')
            get().finalizeStreamMessage(id, errorMessage)
            try { get().markStreamingEnd() } catch {}
            return
          }
        } catch (err) {
          console.error('[Chat] Custom event handler error:', err)
        }
      })
      await IMService.connect()
      // initial history load (latest N)
      await get().loadInitialHistory(20)
    } catch (e: any) {
      const errMsg = e?.message || String(e)
      console.error('[Chat] IM initialization failed:', errMsg, e)
      set({ error: errMsg, online: false })
    } finally {
      set({ initializing: false })
    }
  },

  sendMessage: async (text: string) => {
    const v = (text || '').trim(); if (!v) return
    const clientMsgNo = (typeof crypto !== 'undefined' && (crypto as any)?.randomUUID) ? (crypto as any).randomUUID() : `cmn-${Date.now()}-${Math.random().toString(36).slice(2,8)}`
    const id = 'u-' + Date.now()
    const you: ChatMessage = { id, role: 'user', payload: { type: 1, content: v }, time: new Date(), status: 'sending', clientMsgNo }

    // 1. 先渲染消息到消息列表（发送中状态）
    set(state => ({ messages: [...state.messages, you] }))

    try {
      const st = get()
      const apiBase = st.apiBase
      const platformApiKey = resolveApiKey() || ''
      const myUid = st.myUid
      const channelId = st.channelId
      const channelType = st.channelType

      if (!apiBase || !platformApiKey || !myUid) {
        throw new Error('Cannot send message: missing apiBase, apiKey, or myUid')
      }

      // If a previous stream is ongoing, auto-cancel it before sending a new one
      if (st.isStreaming) { try { await get().cancelStreaming('auto_cancel_on_new_send') } catch {} }

      // 2. 先通过 websocket 发送
      // 确保 IM 已就绪
      if (!IMService.isReady) {
        if (!st.initializing && st.apiBase) {
          console.log('[Chat] IM not ready, attempting to initialize...')
          try { void get().initIM({ apiBase: st.apiBase }) } catch {}
        }
        const start = Date.now()
        const timeout = 10000
        while (!IMService.isReady && (Date.now() - start) < timeout) {
          await new Promise(r => setTimeout(r, 120))
        }
        if (!IMService.isReady) {
          throw new Error('Cannot send message: IM service is not ready after waiting.')
        }
      }

      console.log('[Chat] WebSocket sending...')
      const result = await IMService.sendText(v, { clientMsgNo })
      console.log('[Chat] WebSocket send result:', result)

      // 只有 WebSocket 发送成功（reasonCode 为 Success）才继续调用 completion 接口
      if (result.reasonCode !== ReasonCode.Success) {
        console.warn('[Chat] WebSocket send did not return Success, skipping completion API.', result.reasonCode)
        set(state => ({
          messages: state.messages.map(m => m.id === id ? { ...m, status: undefined, reasonCode: result.reasonCode } : m)
        }))
        return
      }

      // 3. WebSocket 发送成功后，再调用 /v1/chat/completion 接口（stream=false）
      const url = `${apiBase.replace(/\/$/, '')}/v1/chat/completion`
      const payload: Record<string, any> = {
        api_key: platformApiKey,
        message: v,
        from_uid: myUid,
        wukongim_only: true,
        forward_user_message_to_wukongim: false,
        stream: false,
      }
      if (channelId) payload.channel_id = channelId
      if (channelType != null) payload.channel_type = channelType

      console.log('[Chat] Calling /v1/chat/completion:', { url, payload: { ...payload, api_key: '***' } })

      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })

      // 解析响应 JSON
      const resJson = await res.json().catch(() => ({}))
      console.log('[Chat] /v1/chat/completion response:', resJson)

      // 检查 event_type 是否为 error
      if (resJson.event_type === 'error') {
        const errMsg = resJson.message || resJson.detail || 'Unknown error'
        throw new Error(errMsg)
      }

      if (!res.ok) {
        const errMsg = resJson.message || resJson.detail || `${res.status} ${res.statusText}`
        throw new Error(`/v1/chat/completion failed: ${errMsg}`)
      }

      console.log('[Chat] /v1/chat/completion success')

      set(state => ({
        messages: state.messages.map(m => m.id === id ? { ...m, status: undefined, reasonCode: result.reasonCode } : m)
      }))
    } catch (e) {
      console.error('[Chat] Send failed:', e)
      try { get().markStreamingEnd() } catch {}
      set(state => ({
        messages: state.messages.map(m => m.id === id ? { ...m, status: undefined, reasonCode: ReasonCode.Unknown } : m),
        error: (e as any)?.message || String(e)
      }))
    }
  },

  uploadFiles: async (files: FileList | File[]) => {
    const arr: File[] = Array.isArray(files as any) ? (files as any as File[]) : Array.from(files as FileList)
    for (const file of arr) {
      ;(async () => {
        try {
          const st = get()
          if (!st.apiBase || !st.channelId || !st.channelType) {
            set({ error: '[Upload] Not initialized' })
            return
          }
          const isImage = (file?.type || '').startsWith('image/')
          const dimsPromise = isImage ? readImageDimensions(file) : Promise.resolve(null)
          const clientMsgNo = (typeof crypto !== 'undefined' && (crypto as any)?.randomUUID) ? (crypto as any).randomUUID() : `um-${Date.now()}-${Math.random().toString(36).slice(2,8)}`
          const id = `u-up-${Date.now()}-${Math.random().toString(36).slice(2,8)}`
          const placeholder: ChatMessage = {
            id,
            role: 'user',
            payload: { type: 1, content: isImage ? '图片上传中…' : '文件上传中…' } as any,
            time: new Date(),
            status: 'uploading',
            uploadProgress: 0,
            clientMsgNo,
          }
          set(s => ({ messages: [...s.messages, placeholder] }))
          pendingFiles.set(id, file)
          const controller = new AbortController()
          uploadControllers.set(id, controller)

          try {
            const res = await uploadChatFile({
              apiBase: st.apiBase,
              channelId: st.channelId,
              channelType: st.channelType,
              file,
              signal: controller.signal,
              onProgress: (p) => {
                set(s => ({ messages: s.messages.map(m => m.id === id ? { ...m, uploadProgress: p } : m) }))
              },
            })

            const dims = await dimsPromise
            if (isImage) {
              const w = Math.max(1, dims?.width ?? 1)
              const h = Math.max(1, dims?.height ?? 1)
              const fileUrl = res.file_url
              const payload: MessagePayload = { type: 2, url: fileUrl, width: w, height: h }
              set(s => ({ messages: s.messages.map(m => m.id === id ? { ...m, payload, status: 'sending', uploadProgress: undefined, uploadError: undefined } : m) }))
              const result = await IMService.sendPayload(payload, { clientMsgNo })
              set(s => ({ messages: s.messages.map(m => m.id === id ? { ...m, status: undefined, reasonCode: (result?.reasonCode ?? ReasonCode.Unknown) as ReasonCode } : m) }))
            } else {
              const fileUrl = res.file_url
              const payload: MessagePayload = { type: 3, content: file.name || '[文件]', url: fileUrl, name: res.file_name || file.name, size: res.file_size ?? file.size }
              set(s => ({ messages: s.messages.map(m => m.id === id ? { ...m, payload, status: 'sending', uploadProgress: undefined, uploadError: undefined } : m) }))
              const result = await IMService.sendPayload(payload, { clientMsgNo })
              set(s => ({ messages: s.messages.map(m => m.id === id ? { ...m, status: undefined, reasonCode: (result?.reasonCode ?? ReasonCode.Unknown) as ReasonCode } : m) }))
            }
            // success: cleanup retained file/controller
            uploadControllers.delete(id)
            pendingFiles.delete(id)
          } catch (err: any) {
            // error
            uploadControllers.delete(id)
            const aborted = err?.name === 'AbortError'
            set(s => ({
              messages: s.messages.map(m => m.id === id ? { ...m, status: undefined, uploadError: aborted ? '已取消' : (err?.message || '上传失败') } : m),
              error: aborted ? s.error : (err?.message || String(err))
            }))
            // keep pendingFiles for retry on failure
          }
        } catch (e) {
          set({ error: (e as any)?.message || String(e) })
        }
      })()
    }
  },

  retryUpload: async (messageId: string) => {
    const file = pendingFiles.get(messageId)
    if (!file) return
    const st = get()
    if (!st.apiBase || !st.channelId || !st.channelType) return
    const isImage = (file?.type || '').startsWith('image/')
    const dimsPromise = isImage ? readImageDimensions(file) : Promise.resolve(null)
    const clientMsgNo = (typeof crypto !== 'undefined' && (crypto as any)?.randomUUID) ? (crypto as any).randomUUID() : `um-${Date.now()}-${Math.random().toString(36).slice(2,8)}`
    // reset state
    set(s => ({ messages: s.messages.map(m => m.id === messageId ? { ...m, payload: { type: 1, content: isImage ? '图片上传中…' : '文件上传中…' } as any, status: 'uploading', uploadProgress: 0, uploadError: undefined, clientMsgNo } : m) }))
    const controller = new AbortController()
    uploadControllers.set(messageId, controller)
    try {
      const res = await uploadChatFile({
        apiBase: st.apiBase,
        channelId: st.channelId,
        channelType: st.channelType,
        file,
        signal: controller.signal,
        onProgress: (p) => set(s => ({ messages: s.messages.map(m => m.id === messageId ? { ...m, uploadProgress: p } : m) })),
      })
      const dims = await dimsPromise
      if (isImage) {
        const w = Math.max(1, dims?.width ?? 1)
        const h = Math.max(1, dims?.height ?? 1)
        const fileUrl = res.file_url
        const payload: MessagePayload = { type: 2, url: fileUrl, width: w, height: h }
        set(s => ({ messages: s.messages.map(m => m.id === messageId ? { ...m, payload, status: 'sending', uploadProgress: undefined, uploadError: undefined } : m) }))
        const result = await IMService.sendPayload(payload, { clientMsgNo })
        set(s => ({ messages: s.messages.map(m => m.id === messageId ? { ...m, status: undefined, reasonCode: (result?.reasonCode ?? ReasonCode.Unknown) as ReasonCode } : m) }))
      } else {
        const fileUrl = res.file_url
        const payload: MessagePayload = { type: 3, content: file.name || '[文件]', url: fileUrl, name: res.file_name || file.name, size: res.file_size ?? file.size }
        set(s => ({ messages: s.messages.map(m => m.id === messageId ? { ...m, payload, status: 'sending', uploadProgress: undefined, uploadError: undefined } : m) }))
        const result = await IMService.sendPayload(payload, { clientMsgNo })
        set(s => ({ messages: s.messages.map(m => m.id === messageId ? { ...m, status: undefined, reasonCode: (result?.reasonCode ?? ReasonCode.Unknown) as ReasonCode } : m) }))
      }
      uploadControllers.delete(messageId)
      pendingFiles.delete(messageId)
    } catch (err: any) {
      uploadControllers.delete(messageId)
      const aborted = err?.name === 'AbortError'
      set(s => ({
        messages: s.messages.map(m => m.id === messageId ? { ...m, status: undefined, uploadError: aborted ? '已取消' : (err?.message || '上传失败') } : m),
        error: aborted ? s.error : (err?.message || String(err))
      }))
    }
  },

  cancelUpload: (messageId: string) => {
    const ctl = uploadControllers.get(messageId)
    if (ctl) {
      try { ctl.abort() } catch {}
      uploadControllers.delete(messageId)
    } else {
      // if no inflight controller, mark as cancelled locally
      set(s => ({ messages: s.messages.map(m => m.id === messageId ? { ...m, status: undefined, uploadError: '已取消' } : m) }))
    }
  },

  retryMessage: async (messageId: string) => {
    const state = get()
    const msg = state.messages.find(m => m.id === messageId)
    if (!msg || msg.role !== 'user') return
    // set to sending
    set(s => ({ messages: s.messages.map(m => m.id === messageId ? { ...m, status: 'sending', reasonCode: undefined } : m) }))
    try {
      const result = await IMService.sendPayload(msg.payload)
      const code: ReasonCode = (result?.reasonCode ?? ReasonCode.Unknown) as ReasonCode
      set(s => ({ messages: s.messages.map(m => m.id === messageId ? { ...m, status: undefined, reasonCode: code } : m) }))
    } catch (e) {
      set(s => ({
        messages: s.messages.map(m => m.id === messageId ? { ...m, status: undefined, reasonCode: ReasonCode.Unknown } : m),
        error: (e as any)?.message || String(e)
      }))
    }
  },

  removeMessage: (messageId: string) => {
    set(s => ({ messages: s.messages.filter(m => m.id !== messageId) }))
  },

  loadInitialHistory: async (limit = 20) => {
    const st = get()
    if (!st.channelId || !st.channelType) return
    if (st.historyLoading) return
    set({ historyLoading: true, historyError: null })
    try {
      const res = await syncVisitorMessages({
        apiBase: st.apiBase || '', // not in state; use last cfg via closure if needed
        channelId: st.channelId,
        channelType: st.channelType,
        startSeq: 0,
        endSeq: 0,
        limit,
        pullMode: 1,
      })
      // Sort ascending by seq
      const myUid = st.myUid
      const list = [...res.messages].sort((a,b)=> (a.message_seq||0)-(b.message_seq||0))
        .map(m => mapHistoryToChatMessage(m, myUid))

      // prefetch staff names for agent messages
      try {
        const uids = Array.from(new Set(list.filter(x => x.role==='agent' && x.fromUid).map(x => String(x.fromUid))))
        uids.forEach(u => { try { void get().fetchStaffInfo(u) } catch {} })
      } catch {}

      // dedup by seq or id, then prepend
      set(s => {
        const existingSeqs = new Set<number>()
        s.messages.forEach(m => { if (typeof m.messageSeq === 'number') existingSeqs.add(m.messageSeq) })
        const existingIds = new Set(s.messages.map(m => m.id))
        const mergedHead = list.filter(m => (m.messageSeq!=null ? !existingSeqs.has(m.messageSeq) : !existingIds.has(m.id)))
        const earliest = mergedHead.length ? Math.min(...mergedHead.map(m => m.messageSeq ?? Number.MAX_SAFE_INTEGER), s.earliestSeq ?? Number.MAX_SAFE_INTEGER) : s.earliestSeq
        return {
          messages: [...mergedHead, ...s.messages],
          earliestSeq: earliest ?? null,
          historyHasMore: res.more === 1,
        }
      })
    } catch (e:any) {
      set({ historyError: e?.message || String(e) })
    } finally {
      set({ historyLoading: false })
    }
  },

  loadMoreHistory: async (limit = 20) => {
    const st = get()
    if (!st.channelId || !st.channelType) return
    if (st.historyLoading) return
    const start = st.earliestSeq ?? 0
    set({ historyLoading: true, historyError: null })
    try {
      const res = await syncVisitorMessages({
        apiBase: st.apiBase || '',
        channelId: st.channelId,
        channelType: st.channelType,
        startSeq: start,
        endSeq: 0,
        limit,
        pullMode: 0,
      })
      const myUid = st.myUid
      // sort descending (down pull returns <= start), then reverse to maintain ascending order when prepending
      const listAsc = [...res.messages]
        .sort((a,b)=> (a.message_seq||0)-(b.message_seq||0))
        .map(m => mapHistoryToChatMessage(m, myUid))

      // prefetch staff names for agent messages
      try {
        const uids = Array.from(new Set(listAsc.filter(x => x.role==='agent' && x.fromUid).map(x => String(x.fromUid))))
        uids.forEach(u => { try { void get().fetchStaffInfo(u) } catch {} })
      } catch {}

      set(s => {
        const existingSeqs = new Set<number>()
        s.messages.forEach(m => { if (typeof m.messageSeq === 'number') existingSeqs.add(m.messageSeq) })
        const existingIds = new Set(s.messages.map(m => m.id))
        const prepend = listAsc.filter(m => (m.messageSeq!=null ? !existingSeqs.has(m.messageSeq) : !existingIds.has(m.id)))
        const earliest = prepend.length ? Math.min(...prepend.map(m => m.messageSeq ?? Number.MAX_SAFE_INTEGER), s.earliestSeq ?? Number.MAX_SAFE_INTEGER) : s.earliestSeq
        return {
          messages: [...prepend, ...s.messages],
          earliestSeq: earliest ?? null,
          historyHasMore: res.more === 1,
        }
      })
    } catch (e:any) {
      set({ historyError: e?.message || String(e) })
    } finally {
      set({ historyLoading: false })
    }
  },
  // mark streaming start and auto-timeout
  markStreamingStart: (clientMsgNo: string) => {
    if (!clientMsgNo) return
    // clear previous timer
    if (streamTimer) { try { clearTimeout(streamTimer) } catch {} ; streamTimer = null }
    set({ isStreaming: true, streamCanceling: false, streamingClientMsgNo: clientMsgNo })
    // auto timeout to revert button if no end event
    streamTimer = setTimeout(() => {
      const st = get()
      if (st.isStreaming && st.streamingClientMsgNo === clientMsgNo) {
        set({ isStreaming: false, streamingClientMsgNo: undefined, streamCanceling: false })
      }
    }, STREAM_TIMEOUT_MS)
  },

  // explicitly end streaming and clear state
  markStreamingEnd: (_clientMsgNo?: string) => {
    if (streamTimer) { try { clearTimeout(streamTimer) } catch {} ; streamTimer = null }
    set({ isStreaming: false, streamCanceling: false, streamingClientMsgNo: undefined })
  },

  // interrupt API integration
  cancelStreaming: async (reason?: string) => {
    const st = get()
    if (st.streamCanceling) return
    const apiBase = st.apiBase
    const clientMsgNo = st.streamingClientMsgNo
    const platformApiKey = resolveApiKey() || ''
    set({ streamCanceling: true })
    try {
      if (!apiBase || !clientMsgNo || !platformApiKey) return
      const url = `${apiBase.replace(/\/$/, '')}/v1/ai/runs/cancel-by-client`
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ platform_api_key: platformApiKey, client_msg_no: clientMsgNo, reason: reason || 'user_cancel' })
      })
      if (!res.ok) {
        const text = await res.text().catch(()=>'')
        console.warn('[Chat] Cancel streaming failed:', res.status, res.statusText, text)
      }
    } catch (e) {
      console.warn('[Chat] Cancel streaming error:', e)
    } finally {
      // Regardless of API result, revert UI state to allow new messages
      if (streamTimer) { try { clearTimeout(streamTimer) } catch {} ; streamTimer = null }
      set({ isStreaming: false, streamingClientMsgNo: undefined, streamCanceling: false })
    }
  },


  appendStreamData: (clientMsgNo: string, data: string) => {
    if (!clientMsgNo || !data) return
    set(state => {
      let found = false
      const messages = state.messages.map(m => {
        if (m.clientMsgNo && m.clientMsgNo === clientMsgNo) {
          found = true
          return { ...m, streamData: (m.streamData || '') + data }
        }
        return m
      })
      if (found) return { messages }
      // Not found: create a placeholder agent message to display streaming content immediately
      const placeholder: ChatMessage = {
        id: `stream-${clientMsgNo}`,
        role: 'agent',
        payload: { type: 1, content: '' },
        time: new Date(),
        clientMsgNo,
        streamData: data,
      }
      return { messages: [...state.messages, placeholder] }
    })
    // If streaming state isn't set yet, set it based on incoming stream
    const st = get()
    if (!st.isStreaming) { try { get().markStreamingStart(clientMsgNo) } catch {} }
  },

  finalizeStreamMessage: (clientMsgNo: string, errorMessage?: string) => {
    if (!clientMsgNo) return
    set(state => {
      const messages = state.messages.map(m => {
        if (m.clientMsgNo && m.clientMsgNo === clientMsgNo) {
          // Move streamData into payload.content and clear streamData to stop blinking cursor
          // 如果有错误信息，设置 errorMessage 字段
          return {
            ...m,
            payload: m.streamData ? { type: 1, content: m.streamData } as MessagePayload : m.payload,
            streamData: undefined,
            errorMessage: errorMessage || undefined,
          }
        }
        return m
      })
      return { messages }
    })
    // If this was the active streaming message, clear streaming state
    const st = get()
    if (st.streamingClientMsgNo === clientMsgNo) {
      if (streamTimer) { try { clearTimeout(streamTimer) } catch {} ; streamTimer = null }
      set({ isStreaming: false, streamingClientMsgNo: undefined, streamCanceling: false })
    }
  },

  ensureWelcomeMessage: (text: string) => {
    const t = (text || '').trim(); if (!t) return
    set(state => {
      const idx = state.messages.findIndex(m => m.id === 'welcome')
      if (idx >= 0) {
        const next = state.messages.slice()
        const m = next[idx]
        next[idx] = { ...m, payload: { type: 1, content: t } as any }
        return { messages: next }
      }
      const welcome: ChatMessage = { id: 'welcome', role: 'agent', payload: { type: 1, content: t }, time: new Date() }
      return { messages: [welcome, ...state.messages] }
    })
  },

  clearUnreadCount: () => {
    set({ unreadCount: 0 })
  },

  incrementUnreadCount: () => {
    // Only increment if window is not visible (hidden/closed)
    const { isVisible } = usePlatformStore.getState()
    console.log('[Chat] incrementUnreadCount called, isVisible:', isVisible)
    if (!isVisible) {
      set(s => {
        const newCount = s.unreadCount + 1
        console.log('[Chat] Incrementing unread count to:', newCount)
        return { unreadCount: newCount }
      })
    }
  }
}))

export default useChatStore

