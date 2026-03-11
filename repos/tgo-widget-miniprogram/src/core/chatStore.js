/**
 * Chat state management (Observable singleton)
 * Ported from tgo-widget-js chatStore.ts
 */
var IMService = require('../services/wukongim')
var visitorService = require('../services/visitor')
var historyService = require('../services/messageHistory')
var chatService = require('../services/chat')
var uploadService = require('../services/upload')
var systemInfoAdapter = require('../adapters/systemInfo')
var types = require('./types')
var platformStore = require('./platformStore')
var uidUtil = require('../utils/uid')
var jsonRenderUtils = require('../utils/jsonRender')

// Module-level unsub guards
var offMsg = null
var offStatus = null
var offCustom = null

// Stream timeout
var streamTimer = null
var STREAM_TIMEOUT_MS = 60000

// Per-clientMsgNo MixedStreamParser instances
var activeParsers = {}

function ChatStore() {
  this._state = {
    messages: [],
    online: false,
    initializing: false,
    error: null,
    // history
    historyLoading: false,
    historyHasMore: true,
    historyError: null,
    earliestSeq: null,
    // identity
    apiBase: '',
    platformApiKey: '',
    myUid: '',
    channelId: '',
    channelType: 251,
    // streaming
    isStreaming: false,
    streamCanceling: false,
    streamingClientMsgNo: ''
  }
  this._listeners = []
  this._throttleTimer = null
  this._pendingState = null
}

ChatStore.prototype.getState = function () {
  return this._state
}

ChatStore.prototype._setState = function (partial) {
  Object.assign(this._state, partial)
  var state = this._state
  this._listeners.forEach(function (fn) { try { fn(state) } catch (e) {} })
}

/**
 * Throttled setState for streaming updates (50ms batch).
 * Mutates this._state immediately (so subsequent reads see latest data),
 * but defers listener notification to avoid excessive setData calls.
 */
ChatStore.prototype._setStateThrottled = function (partial) {
  var self = this
  // Apply state mutation immediately so next read sees latest data
  Object.assign(this._state, partial)
  // Throttle listener notification
  if (!this._throttleTimer) {
    this._throttleTimer = setTimeout(function () {
      self._throttleTimer = null
      var state = self._state
      self._listeners.forEach(function (fn) { try { fn(state) } catch (e) {} })
    }, 50)
  }
}

ChatStore.prototype.subscribe = function (fn) {
  this._listeners.push(fn)
  var self = this
  return function () {
    var idx = self._listeners.indexOf(fn)
    if (idx >= 0) self._listeners.splice(idx, 1)
  }
}

// ========== Initialization ==========

ChatStore.prototype.initIM = function (cfg) {
  if (!cfg || !cfg.apiBase || !cfg.platformApiKey) return Promise.resolve()
  var self = this
  var st = this._state
  if (st.initializing || IMService.isReady()) return Promise.resolve()

  this._setState({ initializing: true, error: null, apiBase: cfg.apiBase, platformApiKey: cfg.platformApiKey })

  var apiBase = cfg.apiBase
  var platformApiKey = cfg.platformApiKey

  // Load or register visitor
  var cached = visitorService.loadCachedVisitor(apiBase, platformApiKey)
  var visitorPromise
  if (cached) {
    visitorPromise = Promise.resolve(cached)
  } else {
    var sysInfo = systemInfoAdapter.collectSystemInfo()
    visitorPromise = visitorService.registerVisitor({
      apiBase: apiBase,
      platformApiKey: platformApiKey,
      extra: sysInfo ? { system_info: sysInfo } : {}
    }).then(function (res) {
      visitorService.saveCachedVisitor(apiBase, platformApiKey, res)
      return visitorService.loadCachedVisitor(apiBase, platformApiKey)
    })
  }

  return visitorPromise.then(function (visitor) {
    var uid = String(visitor.visitor_id || '')
    var uidForIM = uid.endsWith('-vtr') ? uid : uid + '-vtr'
    var target = visitor.channel_id
    var token = visitor.im_token

    self._setState({
      myUid: uidForIM,
      channelId: target,
      channelType: visitor.channel_type || 251
    })

    if (!token) {
      throw new Error('[Chat] Missing im_token from visitor registration')
    }

    return IMService.init({
      apiBase: apiBase,
      uid: uidForIM,
      token: token,
      target: target,
      channelType: 'group'
    })
  }).then(function () {
    // Subscribe to IM events
    self._bindIMEvents()
    return IMService.connect()
  }).then(function () {
    // Load initial history
    return self.loadInitialHistory(20)
  }).catch(function (e) {
    var errMsg = e && e.message ? e.message : String(e)
    console.error('[Chat] IM initialization failed:', errMsg)
    self._setState({ error: errMsg, online: false })
  }).then(function () {
    self._setState({ initializing: false })
  })
}

ChatStore.prototype._bindIMEvents = function () {
  var self = this
  var uidForIM = this._state.myUid

  // Status events
  if (offStatus) { try { offStatus() } catch (e) {} ; offStatus = null }
  offStatus = IMService.onStatus(function (s) {
    self._setState({ online: s === 'connected' })
  })

  // Message events
  if (offMsg) { try { offMsg() } catch (e) {} ; offMsg = null }
  offMsg = IMService.onMessage(function (m) {
    if (!m.fromUid || m.fromUid === uidForIM) return

    var chat = {
      id: String(m.messageId),
      role: 'agent',
      payload: types.toPayloadFromAny(m && m.payload),
      time: new Date(m.timestamp * 1000),
      messageSeq: typeof m.messageSeq === 'number' ? m.messageSeq : undefined,
      clientMsgNo: m.clientMsgNo,
      fromUid: m.fromUid,
      channelId: m.channelId,
      channelType: m.channelType
    }

    var currentMessages = self._state.messages
    for (var i = 0; i < currentMessages.length; i++) {
      if (currentMessages[i].id === chat.id) return
    }

    // Merge into streaming placeholder if exists
    if (chat.clientMsgNo) {
      var idx = -1
      for (var j = 0; j < currentMessages.length; j++) {
        if (currentMessages[j].clientMsgNo && currentMessages[j].clientMsgNo === chat.clientMsgNo) {
          idx = j
          break
        }
      }
      if (idx >= 0) {
        var next = currentMessages.slice()
        next[idx] = Object.assign({}, currentMessages[idx], chat, { streamData: undefined })
        self._setState({ messages: next })
        return
      }
    }

    self._setState({ messages: currentMessages.concat([chat]) })
  })

  // Custom stream events
  if (offCustom) { try { offCustom() } catch (e) {} ; offCustom = null }
  offCustom = IMService.onCustom(function (ev) {
    try {
      if (!ev) return
      var customEvent = ev

      // Parse event data
      var eventData = null
      if (customEvent.dataJson && typeof customEvent.dataJson === 'object') {
        eventData = customEvent.dataJson
      } else if (typeof customEvent.data === 'string') {
        try { eventData = JSON.parse(customEvent.data) } catch (e) {}
      } else if (customEvent.data && typeof customEvent.data === 'object') {
        eventData = customEvent.data
      }

      var newEventType = (eventData && eventData.event_type) || customEvent.type || ''
      var clientMsgNo = (eventData && eventData.client_msg_no) ? String(eventData.client_msg_no) : (customEvent.id ? String(customEvent.id) : '')

      // --- Stream API v2 ---
      if (newEventType === 'stream.delta') {
        if (!clientMsgNo) return
        var payload = eventData && eventData.payload
        var delta = payload && payload.delta
        if (delta) {
          var parser = activeParsers[clientMsgNo]
          if (!parser) {
            parser = jsonRenderUtils.createMixedStreamParser({
              onText: function (t) { self.appendMixedPart(clientMsgNo, { type: 'text', text: t + '\n' }) },
              onPatch: function (p) { self.appendMixedPart(clientMsgNo, { type: 'data-spec', data: { type: 'patch', patch: p } }) }
            })
            activeParsers[clientMsgNo] = parser
          }
          parser.push(String(delta).replace(/([^\n])```spec/g, '$1\n```spec'))
        }
        return
      }

      if (newEventType === 'stream.close') {
        if (!clientMsgNo) return
        var closeParser = activeParsers[clientMsgNo]
        if (closeParser) { closeParser.flush(); delete activeParsers[clientMsgNo] }
        var errMsg = (eventData && eventData.payload && eventData.payload.end_reason > 0) ? '流异常结束' : undefined
        self.finalizeStreamMessage(clientMsgNo, errMsg)
        self.markStreamingEnd()
        return
      }

      if (newEventType === 'stream.error') {
        if (!clientMsgNo) return
        var errParser = activeParsers[clientMsgNo]
        if (errParser) { errParser.flush(); delete activeParsers[clientMsgNo] }
        var errMessage = (eventData && eventData.payload && eventData.payload.error) || '未知错误'
        self.finalizeStreamMessage(clientMsgNo, errMessage)
        self.markStreamingEnd()
        return
      }

      if (newEventType === 'stream.cancel') {
        if (!clientMsgNo) return
        var cancelParser = activeParsers[clientMsgNo]
        if (cancelParser) { cancelParser.flush(); delete activeParsers[clientMsgNo] }
        self.finalizeStreamMessage(clientMsgNo)
        self.markStreamingEnd()
        return
      }

      if (newEventType === 'stream.finish') {
        return
      }

      // --- Legacy event format ---
      if (customEvent.type === '___TextMessageStart') {
        var startId = customEvent.id ? String(customEvent.id) : ''
        if (startId) self.markStreamingStart(startId)
        return
      }

      if (customEvent.type === '___TextMessageContent') {
        var contentId = customEvent.id ? String(customEvent.id) : ''
        if (!contentId) return
        var chunk = typeof customEvent.data === 'string' ? customEvent.data : (customEvent.data != null ? String(customEvent.data) : '')
        if (chunk) self.appendStreamData(contentId, chunk)
        return
      }

      if (customEvent.type === '___TextMessageEnd') {
        var endId = customEvent.id ? String(customEvent.id) : ''
        if (!endId) return
        var endError = customEvent.data ? String(customEvent.data) : undefined
        self.finalizeStreamMessage(endId, endError)
        self.markStreamingEnd()
        return
      }
    } catch (err) {
      console.error('[Chat] Custom event handler error:', err)
    }
  })
}

// ========== Send Message ==========

ChatStore.prototype.sendMessage = function (text) {
  var v = (text || '').trim()
  if (!v) return Promise.resolve()

  var self = this
  var clientMsgNo = uidUtil.generateClientMsgNo('cmn')
  var id = 'u-' + Date.now()
  var msg = {
    id: id,
    role: 'user',
    payload: { type: 1, content: v },
    time: new Date(),
    status: 'sending',
    clientMsgNo: clientMsgNo
  }

  // Add to messages immediately
  this._setState({ messages: this._state.messages.concat([msg]) })

  var st = this._state
  if (!st.apiBase || !st.platformApiKey || !st.myUid) {
    this._updateMessage(id, { status: undefined, errorMessage: 'Not initialized' })
    return Promise.resolve()
  }

  // Auto-cancel previous streaming
  var cancelPromise = st.isStreaming ? this.cancelStreaming('auto_cancel_on_new_send') : Promise.resolve()

  return cancelPromise.then(function () {
    // Wait for IM ready
    if (!IMService.isReady()) {
      return self._waitForIMReady(10000)
    }
  }).then(function () {
    if (!IMService.isReady()) {
      throw new Error('IM service is not ready')
    }
    return IMService.sendText(v, { clientMsgNo: clientMsgNo })
  }).then(function (result) {
    var ReasonCode = require('easyjssdk').ReasonCode
    if (result.reasonCode !== ReasonCode.Success) {
      self._updateMessage(id, { status: undefined, reasonCode: result.reasonCode })
      return
    }

    // Call chat completion API
    return chatService.sendChatCompletion({
      apiBase: self._state.apiBase,
      platformApiKey: self._state.platformApiKey,
      message: v,
      fromUid: self._state.myUid,
      channelId: self._state.channelId,
      channelType: self._state.channelType
    }).then(function () {
      self._updateMessage(id, { status: undefined, reasonCode: result.reasonCode })
    })
  }).catch(function (e) {
    console.error('[Chat] Send failed:', e)
    self.markStreamingEnd()
    var ReasonCode = require('easyjssdk').ReasonCode
    self._updateMessage(id, { status: undefined, reasonCode: ReasonCode.Unknown })
    self._setState({ error: e && e.message ? e.message : String(e) })
  })
}

ChatStore.prototype._waitForIMReady = function (timeoutMs) {
  var start = Date.now()
  return new Promise(function (resolve) {
    var check = function () {
      if (IMService.isReady() || (Date.now() - start) >= timeoutMs) {
        resolve()
      } else {
        setTimeout(check, 120)
      }
    }
    check()
  })
}

ChatStore.prototype._updateMessage = function (id, partial) {
  var messages = this._state.messages.map(function (m) {
    if (m.id === id) return Object.assign({}, m, partial)
    return m
  })
  this._setState({ messages: messages })
}

// ========== Upload ==========

ChatStore.prototype.uploadImage = function (tempFilePath) {
  var self = this
  var st = this._state
  if (!st.apiBase || !st.channelId) {
    this._setState({ error: '[Upload] Not initialized' })
    return Promise.resolve()
  }

  var clientMsgNo = uidUtil.generateClientMsgNo('um')
  var id = 'u-up-' + Date.now() + '-' + Math.random().toString(36).slice(2, 6)
  var placeholder = {
    id: id,
    role: 'user',
    payload: { type: 1, content: '图片上传中…' },
    time: new Date(),
    status: 'uploading',
    uploadProgress: 0,
    clientMsgNo: clientMsgNo
  }
  this._setState({ messages: this._state.messages.concat([placeholder]) })

  return uploadService.getImageInfo(tempFilePath).then(function (dims) {
    return uploadService.uploadChatFile({
      apiBase: st.apiBase,
      apiKey: st.platformApiKey,
      channelId: st.channelId,
      channelType: st.channelType,
      filePath: tempFilePath,
      onProgress: function (p) {
        self._updateMessage(id, { uploadProgress: p })
      }
    }).then(function (res) {
      var w = dims ? Math.max(1, dims.width) : 1
      var h = dims ? Math.max(1, dims.height) : 1
      var payload = { type: 2, url: res.file_url, width: w, height: h }
      self._updateMessage(id, { payload: payload, status: 'sending', uploadProgress: undefined })
      return IMService.sendPayload(payload, { clientMsgNo: clientMsgNo })
    }).then(function (result) {
      self._updateMessage(id, { status: undefined, reasonCode: result && result.reasonCode })
    })
  }).catch(function (err) {
    console.error('[Chat] Upload failed:', err)
    self._updateMessage(id, { status: undefined, uploadError: err && err.message ? err.message : '上传失败' })
  })
}

// ========== History ==========

ChatStore.prototype.loadInitialHistory = function (limit) {
  limit = limit || 20
  var self = this
  var st = this._state
  if (!st.channelId || !st.channelType) return Promise.resolve()
  if (st.historyLoading) return Promise.resolve()

  this._setState({ historyLoading: true, historyError: null })

  return historyService.syncVisitorMessages({
    apiBase: st.apiBase,
    platformApiKey: st.platformApiKey,
    channelId: st.channelId,
    channelType: st.channelType,
    startSeq: 0,
    endSeq: 0,
    limit: limit,
    pullMode: 1
  }).then(function (res) {
    var myUid = self._state.myUid
    var list = res.messages.slice().sort(function (a, b) {
      return (a.message_seq || 0) - (b.message_seq || 0)
    }).map(function (m) {
      return types.mapHistoryToChatMessage(m, myUid)
    })

    // Dedup and prepend
    var existingSeqs = {}
    var existingIds = {}
    self._state.messages.forEach(function (m) {
      if (typeof m.messageSeq === 'number') existingSeqs[m.messageSeq] = true
      existingIds[m.id] = true
    })

    var mergedHead = list.filter(function (m) {
      if (m.messageSeq != null) return !existingSeqs[m.messageSeq]
      return !existingIds[m.id]
    })

    var earliest = self._state.earliestSeq
    mergedHead.forEach(function (m) {
      if (m.messageSeq != null) {
        if (earliest === null || m.messageSeq < earliest) earliest = m.messageSeq
      }
    })

    self._setState({
      messages: mergedHead.concat(self._state.messages),
      earliestSeq: earliest,
      historyHasMore: res.more === 1
    })
  }).catch(function (e) {
    self._setState({ historyError: e && e.message ? e.message : String(e) })
  }).then(function () {
    self._setState({ historyLoading: false })
  })
}

ChatStore.prototype.loadMoreHistory = function (limit) {
  limit = limit || 20
  var self = this
  var st = this._state
  if (!st.channelId || !st.channelType) return Promise.resolve()
  if (st.historyLoading) return Promise.resolve()

  var start = st.earliestSeq || 0
  this._setState({ historyLoading: true, historyError: null })

  return historyService.syncVisitorMessages({
    apiBase: st.apiBase,
    platformApiKey: st.platformApiKey,
    channelId: st.channelId,
    channelType: st.channelType,
    startSeq: start,
    endSeq: 0,
    limit: limit,
    pullMode: 0
  }).then(function (res) {
    var myUid = self._state.myUid
    var listAsc = res.messages.slice().sort(function (a, b) {
      return (a.message_seq || 0) - (b.message_seq || 0)
    }).map(function (m) {
      return types.mapHistoryToChatMessage(m, myUid)
    })

    var existingSeqs = {}
    var existingIds = {}
    self._state.messages.forEach(function (m) {
      if (typeof m.messageSeq === 'number') existingSeqs[m.messageSeq] = true
      existingIds[m.id] = true
    })

    var prepend = listAsc.filter(function (m) {
      if (m.messageSeq != null) return !existingSeqs[m.messageSeq]
      return !existingIds[m.id]
    })

    var earliest = self._state.earliestSeq
    prepend.forEach(function (m) {
      if (m.messageSeq != null) {
        if (earliest === null || m.messageSeq < earliest) earliest = m.messageSeq
      }
    })

    self._setState({
      messages: prepend.concat(self._state.messages),
      earliestSeq: earliest,
      historyHasMore: res.more === 1
    })
  }).catch(function (e) {
    self._setState({ historyError: e && e.message ? e.message : String(e) })
  }).then(function () {
    self._setState({ historyLoading: false })
  })
}

// ========== Streaming ==========

ChatStore.prototype.markStreamingStart = function (clientMsgNo) {
  if (!clientMsgNo) return
  if (streamTimer) { try { clearTimeout(streamTimer) } catch (e) {} ; streamTimer = null }
  var self = this
  this._setState({ isStreaming: true, streamCanceling: false, streamingClientMsgNo: clientMsgNo })
  streamTimer = setTimeout(function () {
    var s = self._state
    if (s.isStreaming && s.streamingClientMsgNo === clientMsgNo) {
      self._setState({ isStreaming: false, streamingClientMsgNo: '', streamCanceling: false })
    }
  }, STREAM_TIMEOUT_MS)
}

ChatStore.prototype.markStreamingEnd = function () {
  if (streamTimer) { try { clearTimeout(streamTimer) } catch (e) {} ; streamTimer = null }
  this._setState({ isStreaming: false, streamCanceling: false, streamingClientMsgNo: '' })
}

ChatStore.prototype.cancelStreaming = function (reason) {
  var self = this
  var st = this._state
  if (st.streamCanceling) return Promise.resolve()

  this._setState({ streamCanceling: true })

  if (!st.apiBase || !st.streamingClientMsgNo || !st.platformApiKey) {
    this.markStreamingEnd()
    return Promise.resolve()
  }

  return chatService.cancelStreaming({
    apiBase: st.apiBase,
    platformApiKey: st.platformApiKey,
    clientMsgNo: st.streamingClientMsgNo,
    reason: reason || 'user_cancel'
  }).catch(function (e) {
    console.warn('[Chat] Cancel streaming error:', e)
  }).then(function () {
    self.markStreamingEnd()
  })
}

ChatStore.prototype.appendStreamData = function (clientMsgNo, data) {
  if (!clientMsgNo || !data) return

  var messages = this._state.messages
  var found = false
  var updated = messages.map(function (m) {
    if (m.clientMsgNo && m.clientMsgNo === clientMsgNo) {
      found = true
      return Object.assign({}, m, { streamData: (m.streamData || '') + data })
    }
    return m
  })

  if (!found) {
    var placeholder = {
      id: 'stream-' + clientMsgNo,
      role: 'agent',
      payload: { type: 1, content: '' },
      time: new Date(),
      clientMsgNo: clientMsgNo,
      streamData: data
    }
    updated = messages.concat([placeholder])
  }

  this._setStateThrottled({ messages: updated })

  if (!this._state.isStreaming) {
    this.markStreamingStart(clientMsgNo)
  }
}

ChatStore.prototype.appendMixedPart = function (clientMsgNo, part) {
  if (!clientMsgNo) return

  var messages = this._state.messages
  var found = false
  var updated = messages.map(function (m) {
    if (m.clientMsgNo && m.clientMsgNo === clientMsgNo) {
      found = true
      var parts = (m.uiParts || []).slice()
      // Merge consecutive text parts
      if (part.type === 'text' && parts.length > 0) {
        var last = parts[parts.length - 1]
        if (last.type === 'text') {
          parts[parts.length - 1] = { type: 'text', text: (last.text || '') + (part.text || '') }
          var textContent = ''
          for (var i = 0; i < parts.length; i++) {
            if (parts[i].type === 'text') textContent += parts[i].text || ''
          }
          return Object.assign({}, m, { uiParts: parts, streamData: textContent })
        }
      }
      parts.push(part)
      var tc = ''
      for (var j = 0; j < parts.length; j++) {
        if (parts[j].type === 'text') tc += parts[j].text || ''
      }
      return Object.assign({}, m, { uiParts: parts, streamData: tc })
    }
    return m
  })

  if (!found) {
    var initParts = [part]
    var placeholder = {
      id: 'stream-' + clientMsgNo,
      role: 'agent',
      payload: { type: 1, content: '' },
      time: new Date(),
      clientMsgNo: clientMsgNo,
      uiParts: initParts,
      streamData: part.type === 'text' ? (part.text || '') : ''
    }
    updated = messages.concat([placeholder])
  }

  this._setStateThrottled({ messages: updated })

  if (!this._state.isStreaming) {
    this.markStreamingStart(clientMsgNo)
  }
}

ChatStore.prototype.finalizeStreamMessage = function (clientMsgNo, errorMessage) {
  if (!clientMsgNo) return

  var messages = this._state.messages.map(function (m) {
    if (m.clientMsgNo && m.clientMsgNo === clientMsgNo) {
      var finalPayload = m.streamData
        ? { type: 1, content: m.streamData }
        : m.payload
      var result = Object.assign({}, m, {
        payload: finalPayload,
        streamData: undefined,
        errorMessage: errorMessage || undefined
      })
      // Preserve uiParts for json-render
      if (m.uiParts) result.uiParts = m.uiParts
      return result
    }
    return m
  })

  this._setState({ messages: messages })

  if (this._state.streamingClientMsgNo === clientMsgNo) {
    this.markStreamingEnd()
  }
}

ChatStore.prototype.ensureWelcomeMessage = function (text) {
  var t = (text || '').trim()
  if (!t) return

  var messages = this._state.messages
  var idx = -1
  for (var i = 0; i < messages.length; i++) {
    if (messages[i].id === 'welcome') { idx = i; break }
  }

  if (idx >= 0) {
    var next = messages.slice()
    next[idx] = Object.assign({}, messages[idx], { payload: { type: 1, content: t } })
    this._setState({ messages: next })
  } else {
    var welcome = {
      id: 'welcome',
      role: 'agent',
      payload: { type: 1, content: t },
      time: new Date()
    }
    this._setState({ messages: [welcome].concat(messages) })
  }
}

ChatStore.prototype.disconnect = function () {
  if (offMsg) { try { offMsg() } catch (e) {} ; offMsg = null }
  if (offStatus) { try { offStatus() } catch (e) {} ; offStatus = null }
  if (offCustom) { try { offCustom() } catch (e) {} ; offCustom = null }
  this.markStreamingEnd()
  IMService.disconnect()
}

module.exports = new ChatStore()
