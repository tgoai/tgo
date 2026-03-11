/**
 * json-render-surface: manages state store and renders root element.
 * Handles action dispatch and state change events.
 * Ported from tgo-widget-js JSONRenderSurface.tsx
 */
var jsonRenderUtils = require('../../utils/jsonRender')

Component({
  options: {
    virtualHost: true
  },

  properties: {
    spec: {
      type: Object,
      value: null
    },
    loading: {
      type: Boolean,
      value: false
    },
    themeColor: {
      type: String,
      value: '#2f80ed'
    }
  },

  data: {
    stateSnapshot: {},
    hasRoot: false
  },

  observers: {
    'spec': function (spec) {
      this._initStore(spec)
    }
  },

  lifetimes: {
    detached: function () {
      if (this._unsub) {
        this._unsub()
        this._unsub = null
      }
    }
  },

  methods: {
    _initStore: function (spec) {
      var self = this
      // Clean up previous subscription
      if (this._unsub) {
        this._unsub()
        this._unsub = null
      }

      if (!spec || !spec.root) {
        this.setData({ hasRoot: false, stateSnapshot: {} })
        return
      }

      var store = jsonRenderUtils.createStateStore(spec.state || {})
      this._store = store
      this._actionNames = jsonRenderUtils.collectActionNames(spec)

      this.setData({
        hasRoot: true,
        stateSnapshot: store.getSnapshot()
      })

      this._unsub = store.subscribe(function () {
        self.setData({ stateSnapshot: store.getSnapshot() })
      })
    },

    onAction: function (e) {
      var detail = e.detail || {}
      var actionName = detail.actionName
      var params = detail.params || {}

      if (!actionName) return

      // Built-in state actions
      if (actionName === 'setState' && this._store) {
        if (params.statePath && typeof params.statePath === 'string') {
          this._store.set(params.statePath, params.value)
        }
        return
      }
      if (actionName === 'pushState' && this._store) {
        return
      }
      if (actionName === 'removeState' && this._store) {
        return
      }

      // Contains statePath → treat as state update
      if (params.statePath && typeof params.statePath === 'string' && this._store) {
        this._store.set(params.statePath, params.value)
        return
      }

      // External action → format as text message
      var snapshot = this._store ? this._store.getSnapshot() : {}
      var text = jsonRenderUtils.formatActionMessage(actionName, params, snapshot)
      this.triggerEvent('sendmessage', { text: text })
    },

    onStateChange: function (e) {
      var detail = e.detail || {}
      if (detail.path && this._store) {
        this._store.set(detail.path, detail.value)
      }
    }
  }
})
