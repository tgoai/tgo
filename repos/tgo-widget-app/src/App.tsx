import React, { useMemo, useEffect } from 'react'
import styled from '@emotion/styled'
import { css } from '@emotion/react'
import Header from './components/Header'
import MessageList from './components/MessageList'
import MessageInput from './components/MessageInput'
import { useChatStore, usePlatformStore } from './store'
import { resolveApiKey, resolveMode } from './utils/url'
import { recordVisitorActivity } from './services/visitorActivity'
import { ThemeProvider } from './contexts/ThemeContext'


const WidgetWrap = styled.div`
  position: absolute; inset: 0; width: 100%; height: 100%;
  display: flex; flex-direction: column; background: var(--bg-primary, #fff); border-radius: 16px; overflow: hidden;
  overscroll-behavior: contain;
  @media (max-width: 480px){ border-radius: 0; }
`

const Grow = styled.div`flex: 1; min-height: 0; display: flex; flex-direction: column;`

export default function App(){
  const messages = useChatStore(s => s.messages)
  const initIM = useChatStore(s => s.initIM)
  const sendMessage = useChatStore(s => s.sendMessage)
  const ensureWelcomeMessage = useChatStore(s => s.ensureWelcomeMessage)
  const myUid = useChatStore(s => s.myUid)

  const pConfig = usePlatformStore(s => s.config)
  const isExpanded = usePlatformStore(s => s.isExpanded)
  const initPlatform = usePlatformStore(s => s.init)
  const welcomeInjected = usePlatformStore(s => s.welcomeInjected)
  const markWelcomeInjected = usePlatformStore(s => s.markWelcomeInjected)

  // Resolve theme mode from URL (?mode=dark or ?mode=light)
  const themeMode = useMemo(() => resolveMode(), [])

  // API base via env
  // Priority: window.ENV (runtime) > import.meta.env (build-time) > undefined
  // If relative path, prepend current origin
  const cfg = useMemo(() => {
    let apiBase = (
      (typeof window !== 'undefined' && (window as any).ENV?.VITE_API_BASE_URL) ||
      (import.meta as any).env?.VITE_API_BASE_URL ||
      undefined
    ) as string | undefined

    // Handle relative URL: starts with "/" but not "//"
    if (apiBase && apiBase.startsWith('/') && !apiBase.startsWith('//')) {
      apiBase = window.location.origin + apiBase
    }

    return { apiBase }
  }, [])

  useEffect(()=>{
    if (cfg.apiBase) {
      const platformApiKey = resolveApiKey() || ''
      if (platformApiKey) void initPlatform(cfg.apiBase, platformApiKey)
    }
  }, [])

  useEffect(()=>{
    if(!cfg.apiBase){
      console.warn('[Widget] Missing env VITE_API_BASE_URL. Also ensure URL has ?apiKey=... for visitor register')
      return
    }
    void initIM({ apiBase: cfg.apiBase! })
  }, [])

  // Insert welcome message once after platform config available
  useEffect(()=>{
    const welcome = pConfig?.welcome_message
    if (welcome && !welcomeInjected) {
      ensureWelcomeMessage(welcome)
      markWelcomeInjected()
    }
  }, [pConfig?.welcome_message, welcomeInjected])

  const onSend = (text: string)=>{ void sendMessage(text) }

  const title = useMemo(()=> pConfig?.widget_title || 'Tgo', [pConfig?.widget_title])

  const theme = useMemo(()=>{
    const c = pConfig?.theme_color || '#2f80ed'
    const el = document?.createElement?.('div') as HTMLDivElement | undefined
    if (el) {
      el.style.color = ''
      el.style.color = c as any
      if (el.style.color) return c
    }
    return '#2f80ed'
  }, [pConfig?.theme_color])

  const pos = useMemo(()=>{
    const p = pConfig?.position
    return (p==='bottom-right'||p==='bottom-left'||p==='top-right'||p==='top-left') ? p : 'bottom-right'
  }, [pConfig?.position])

  // Apply theme color to CSS variable --primary inside the iframe + notify host
  useEffect(()=>{
    try { document.documentElement?.style?.setProperty('--primary', theme) } catch {}
    try { window.parent?.postMessage?.({ type: 'TGO_WIDGET_CONFIG', payload: { theme_color: theme } }, '*') } catch {}
  }, [theme])

  // Notify host page to position the UI iframe
  useEffect(()=>{
    try { window.parent?.postMessage?.({ type: 'TGO_WIDGET_CONFIG', payload: { position: pos } }, '*') } catch {}
  }, [pos])

  // Notify host page about expanded state
  useEffect(()=>{
    try { window.parent?.postMessage?.({ type: 'TGO_WIDGET_CONFIG', payload: { expanded: !!isExpanded } }, '*') } catch {}
  }, [isExpanded])

  // Host page activity tracking: dwell time and custom events
  useEffect(()=>{
    let debounceTimer: any = null
    let currentUrl: string | null = null
    let currentTitle = ''
    let currentReferrer = ''
    let startAt = 0
    let lastFlushAt = 0

    let currentActivityId: string | null = null
    let currentCreatePromise: Promise<any> | null = null


    // Session tracking (per-tab via sessionStorage)
    let sessionStarted = false
    let sessionStartAt = 0
    let pagesVisited = 0
    let sessionEndSent = false

    const SS_STARTED_AT = 'tgo_session_started_at'
    const SS_PAGES = 'tgo_session_pages'
    try {
      const s = sessionStorage.getItem(SS_STARTED_AT)
      if (s) {
        sessionStarted = true
        sessionStartAt = parseInt(s, 10) || 0
        const pv = parseInt(sessionStorage.getItem(SS_PAGES) || '0', 10)
        pagesVisited = isNaN(pv) ? 0 : pv
      }
    } catch {}

    const markSessionStarted = () => {
      sessionStarted = true
      sessionStartAt = Date.now()
      pagesVisited = 0
      sessionEndSent = false
      try {
        sessionStorage.setItem(SS_STARTED_AT, String(sessionStartAt))
        sessionStorage.setItem(SS_PAGES, '0')
      } catch {}
    }

    const incPagesVisited = () => {
      pagesVisited += 1
      try { sessionStorage.setItem(SS_PAGES, String(pagesVisited)) } catch {}
    }

    const sendSessionStart = () => {
      const uid = useChatStore.getState().myUid || myUid
      const apiKey = resolveApiKey()
      if (!cfg.apiBase || !uid || !apiKey) return
      let visitorId = ""
      if(uid && uid.endsWith('-vtr')){
        visitorId = uid.substring(0, uid.length - 4)
      }else{
        visitorId = uid
      }

      void recordVisitorActivity({
        apiBase: cfg.apiBase,
        visitorId: visitorId,
        activityType: 'session_start',
        title: 'Session started',
        context: { page_url: currentUrl, referrer: currentReferrer || '' }
      }).catch(err => console.warn('[Activity] Failed to record session_start', err))
    }

    const sendSessionEnd = (source?: string) => {
      // Guard: only once per session
      if (sessionEndSent || !sessionStarted) {
        console.warn('[Activity] sendSessionEnd skipped: already sent or session not started', { sessionEndSent, sessionStarted, source })
        return
      }
      sessionEndSent = true
      const uid = useChatStore.getState().myUid || myUid
      const apiKey = resolveApiKey()
      if (!cfg.apiBase || !uid || !apiKey) return
      const now = Date.now()
      const total = sessionStartAt ? Math.max(0, Math.round((now - sessionStartAt) / 1000)) : null
      console.warn('[Activity] sendSessionEnd invoked', { source, now, total, pagesVisited, currentUrl, currentTitle })
      try { console.trace('[Activity] sendSessionEnd stack trace') } catch {}

      let visitorId = ""
      if(uid && uid.endsWith('-vtr')){
        visitorId = uid.substring(0, uid.length - 4)
      }else{
        visitorId = uid
      }
      void recordVisitorActivity({
        apiBase: cfg.apiBase,
        visitorId: visitorId,
        activityType: 'session_end',
        title: 'Session ended',
        durationSeconds: total ?? undefined,
        context: { page_url: currentUrl, referrer: currentReferrer || '', metadata: { pages_visited: pagesVisited } },
        keepalive: true
      }).catch(err => console.warn('[Activity] Failed to record session_end', err))
    }

    const flush = (reason: 'nav' | 'exit') => {
      if (!cfg.apiBase) return
      const uid = useChatStore.getState().myUid || myUid
      const apiKey = resolveApiKey()
      if (!uid || !apiKey) return
      if (!currentUrl || !startAt) return
      const now = Date.now()
      if (now - lastFlushAt < 200) return
      lastFlushAt = now
      const dur = Math.max(0, Math.round((now - startAt) / 1000))
      const title = currentTitle && currentTitle.trim() ? `Visited ${currentTitle}` : 'Visited page'

      const doUpdate = (): Promise<any> => {
        if (!currentActivityId) {
          console.warn('[Activity] Missing activity id on flush; skip update')
          return Promise.resolve()
        }
        const usedId = currentActivityId
        let visitorId = ""
        if(uid && uid.endsWith('-vtr')){
          visitorId = uid.substring(0, uid.length - 4)
        }else{
          visitorId = uid
        }
        return recordVisitorActivity({
          apiBase: cfg.apiBase,
          visitorId: visitorId,
          activityType: 'page_view',
          title,
          id: usedId,
          durationSeconds: dur,
          context: { page_url: currentUrl, referrer: currentReferrer || '' },
          keepalive: reason === 'exit',
        })
          .then(() => { if (currentActivityId === usedId) currentActivityId = null })
          .catch(err => console.warn('[Activity] Failed to update page_view duration', err))
      }

      let chain: Promise<any> = Promise.resolve()
      if (currentActivityId) {
        chain = doUpdate()
      } else if (currentCreatePromise) {
        chain = currentCreatePromise.then(() => doUpdate()).catch(() => Promise.resolve())
      }

      if (reason === 'exit') {
        chain.finally(() => { sendSessionEnd('flush_exit') })
      }
    }

    const begin = (info: { page_url: string; title?: string; referrer?: string }) => {
      currentUrl = info.page_url
      currentTitle = info.title || ''
      currentReferrer = info.referrer || ''
      startAt = Date.now()
      const uid = useChatStore.getState().myUid || myUid
      const apiKey = resolveApiKey()

      // Session start (once per tab)
      if (!sessionStarted && cfg.apiBase && uid && apiKey) {
        markSessionStarted()
        sendSessionStart()
      }

      // Enter event: create page_view immediately (no duration); save returned activity id
      if (cfg.apiBase && uid && apiKey) {
        let visitorId = ""
        if(uid && uid.endsWith('-vtr')){
          visitorId = uid.substring(0, uid.length - 4)
        }else{
          visitorId = uid
        }
        const p = recordVisitorActivity({
          apiBase: cfg.apiBase,
          visitorId: visitorId,
          activityType: 'page_view',
          title: currentTitle && currentTitle.trim() ? `Visited ${currentTitle}` : 'Visited page',
          context: { page_url: currentUrl, referrer: currentReferrer || '' }
        })
        currentCreatePromise = p
        void p.then(res => { currentActivityId = res?.id || null })
             .catch(err => { console.warn('[Activity] Failed to create page_view', err); currentCreatePromise = null })
      }

      // Increment session page count
      incPagesVisited()
    }

    const onMsg = (e: MessageEvent) => {
      const d: any = (e && (e as any).data) || null
      if (d?.type === 'TGO_HOST_PAGE_INFO' && d.payload?.page_url) {
        if (debounceTimer) clearTimeout(debounceTimer)
        const info = d.payload
        debounceTimer = setTimeout(() => {
          if (!currentUrl) {
            begin(info)
          } else if (currentUrl !== info.page_url) {
            flush('nav')
            begin(info)
          } else {
            currentTitle = info.title || currentTitle
            currentReferrer = info.referrer || currentReferrer
          }
        }, 300)
      } else if (d?.type === 'TGO_HOST_PAGE_EXIT') {
        flush('exit')
      } else if (d?.type === 'CONFIG_UPDATE' && d.payload) {
        const p = d.payload || {}
        const patch: any = {}
        if (typeof p.title === 'string') patch.widget_title = p.title
        if (typeof p.themeColor === 'string') patch.theme_color = p.themeColor
        if (typeof p.welcomeMessage === 'string') {
          patch.welcome_message = p.welcomeMessage
          try { useChatStore.getState().ensureWelcomeMessage(p.welcomeMessage) } catch {}
        }
        if (typeof p.position === 'string') patch.position = p.position
        if (typeof p.logoUrl === 'string') patch.logo_url = p.logoUrl
        try { usePlatformStore.getState().setConfig(patch as any) } catch {}
      } else if (d?.type === 'TGO_TRACK_EVENT' && d.payload) {
        const uid = useChatStore.getState().myUid || myUid
        const apiKey = resolveApiKey()
        if (!cfg.apiBase || !uid || !apiKey) return
        const p = d.payload || {}
        const t = String(p.activity_type || '')
        const title = String(p.title || '')
        if (!title) return
        const allowed = t === 'custom_event' || t === 'form_submitted'
        if (!allowed) return
        let visitorId = ""
        if(uid && uid.endsWith('-vtr')){
          visitorId = uid.substring(0, uid.length - 4)
        }else{
          visitorId = uid
        }
        void recordVisitorActivity({
          apiBase: cfg.apiBase,
          visitorId: visitorId,
          activityType: t,
          title,
          description: typeof p.description === 'string' ? p.description : null,
          context: (p.context && typeof p.context === 'object') ? p.context : null
        }).catch(err => console.warn('[Activity] Failed to record custom event', err))
      }
    }

    window.addEventListener('message', onMsg)

    if (useChatStore.getState().myUid || myUid) {
      try { window.parent?.postMessage?.({ type: 'TGO_REQUEST_PAGE_INFO' }, '*') } catch {}
    }

    // We rely on host SDK to send TGO_HOST_PAGE_EXIT; avoid double triggering here.

    return () => {
      window.removeEventListener('message', onMsg)
      if (debounceTimer) clearTimeout(debounceTimer)
    }
  }, [myUid, cfg.apiBase])



  const requestClose = () => {
    try { (window.parent as any)?.TGOWidget?.hide?.(); } catch {}
  };

  return (
    <ThemeProvider initialMode={themeMode}>
      <WidgetWrap role="dialog" aria-label="Customer Support">
        <Header title={title} onClose={requestClose} />
        <Grow>
          <MessageList messages={messages} />
          <MessageInput onSend={onSend} />
        </Grow>
        <a
          href="https://tgo.ai"
          target="_blank"
          rel="noopener noreferrer"
          css={css`
            display:block;
            text-align:center;
            font-size:12px;
            color: var(--text-muted, #9ca3af);
            padding: 6px 0;
            text-decoration: none;
            &:hover { color: var(--text-secondary, #6b7280); }
          `}
        >Powered by tgo.ai</a>
      </WidgetWrap>
    </ThemeProvider>
  )
}

