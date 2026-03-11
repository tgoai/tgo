/**
 * json-render-message: groups uiParts into text/spec groups and renders them.
 * Ported from tgo-widget-js JSONRenderMessage.tsx
 */
var jsonRenderUtils = require('../../utils/jsonRender')

Component({
  options: {
    virtualHost: true
  },

  properties: {
    uiParts: {
      type: Array,
      value: null
    },
    payloadContent: {
      type: String,
      value: ''
    },
    showCursor: {
      type: Boolean,
      value: false
    },
    themeColor: {
      type: String,
      value: '#2f80ed'
    }
  },

  data: {
    groups: [],
    hasGroups: false,
    fallbackText: '',
    lastIndex: -1
  },

  observers: {
    'uiParts, payloadContent': function () {
      this._rebuild()
    }
  },

  methods: {
    _rebuild: function () {
      var parts = this.properties.uiParts
      if (!Array.isArray(parts) || parts.length === 0) {
        // Fallback: use payloadContent, strip spec fences
        var raw = this.properties.payloadContent
        var fallback = raw
        if (raw && raw.indexOf('```spec') >= 0) {
          fallback = raw.replace(/```spec[\s\S]*?```/g, '').replace(/```spec[\s\S]*/g, '').trim()
        }
        this.setData({
          groups: [],
          hasGroups: false,
          fallbackText: fallback || '',
          lastIndex: -1
        })
        return
      }

      var partGroups = jsonRenderUtils.groupParts(parts)
      var groups = []
      for (var i = 0; i < partGroups.length; i++) {
        var g = partGroups[i]
        if (g.type === 'text') {
          groups.push({ type: 'text', text: g.text, spec: null })
        } else if (g.type === 'spec') {
          var spec = jsonRenderUtils.buildSpecFromParts(g.parts)
          if (spec) {
            groups.push({ type: 'spec', text: '', spec: spec })
          }
        }
      }

      this.setData({
        groups: groups,
        hasGroups: groups.length > 0,
        fallbackText: '',
        lastIndex: groups.length - 1
      })
    },

    onSendMessage: function (e) {
      this.triggerEvent('sendmessage', e.detail)
    }
  }
})
