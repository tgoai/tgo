/**
 * json-render utilities for miniprogram
 * Ported from @json-render/react (buildSpecFromParts, groupParts)
 * and tgo-widget-js JSONRenderSurface (formatActionMessage, collectActionNames)
 */
var core = require('@json-render/core')

// Re-export core functions
var createMixedStreamParser = core.createMixedStreamParser
var createStateStore = core.createStateStore
var applySpecPatch = core.applySpecPatch
var nestedToFlat = core.nestedToFlat

var SPEC_DATA_PART_TYPE = 'data-' + (core.SPEC_DATA_PART || 'spec')

// ---- buildSpecFromParts ----
// Ported from @json-render/react buildSpecFromParts
function isSpecDataPart(data) {
  if (typeof data !== 'object' || data === null) return false
  switch (data.type) {
    case 'patch':
      return typeof data.patch === 'object' && data.patch !== null
    case 'flat':
    case 'nested':
      return typeof data.spec === 'object' && data.spec !== null
    default:
      return false
  }
}

function buildSpecFromParts(parts) {
  var spec = { root: '', elements: {} }
  var hasSpec = false
  for (var i = 0; i < parts.length; i++) {
    var part = parts[i]
    if (part.type === SPEC_DATA_PART_TYPE) {
      if (!isSpecDataPart(part.data)) continue
      var payload = part.data
      if (payload.type === 'patch') {
        hasSpec = true
        applySpecPatch(spec, payload.patch)
      } else if (payload.type === 'flat') {
        hasSpec = true
        Object.assign(spec, payload.spec)
      } else if (payload.type === 'nested') {
        hasSpec = true
        var flat = nestedToFlat(payload.spec)
        Object.assign(spec, flat)
      }
    }
  }
  return hasSpec ? spec : null
}

// ---- groupParts ----
// Ported from JSONRenderMessage.tsx groupParts
function groupParts(parts) {
  var groups = []
  for (var i = 0; i < parts.length; i++) {
    var part = parts[i]
    if (part.type === 'text') {
      var last = groups.length > 0 ? groups[groups.length - 1] : null
      if (last && last.type === 'text') {
        last.text += part.text || ''
      } else {
        groups.push({ type: 'text', text: part.text || '' })
      }
    } else {
      var lastG = groups.length > 0 ? groups[groups.length - 1] : null
      if (lastG && lastG.type === 'spec') {
        lastG.parts.push(part)
      } else {
        groups.push({ type: 'spec', parts: [part] })
      }
    }
  }
  return groups
}

// ---- collectActionNames ----
// Ported from JSONRenderSurface.tsx
var BUILTIN_ACTIONS = { setState: 1, pushState: 1, removeState: 1, validateForm: 1 }

function collectActionNames(spec) {
  if (!spec) return []
  var names = {}
  var elements = spec.elements || {}
  var keys = Object.keys(elements)
  for (var i = 0; i < keys.length; i++) {
    var element = elements[keys[i]]
    if (!element) continue
    var events = element.on
    if (!events || typeof events !== 'object') continue
    var evKeys = Object.keys(events)
    for (var j = 0; j < evKeys.length; j++) {
      var binding = events[evKeys[j]]
      if (Array.isArray(binding)) {
        for (var k = 0; k < binding.length; k++) {
          if (binding[k] && typeof binding[k].action === 'string') {
            names[binding[k].action] = true
          }
        }
        continue
      }
      if (binding && typeof binding.action === 'string') {
        names[binding.action] = true
      }
    }
  }
  var result = []
  var nameKeys = Object.keys(names)
  for (var n = 0; n < nameKeys.length; n++) {
    if (!BUILTIN_ACTIONS[nameKeys[n]]) {
      result.push(nameKeys[n])
    }
  }
  return result
}

// ---- formatActionMessage ----
// Ported from JSONRenderSurface.tsx
function formatActionMessage(actionName, params, state) {
  var parts = ['[' + actionName + ']']
  if (params) {
    var pKeys = Object.keys(params)
    for (var i = 0; i < pKeys.length; i++) {
      var v = params[pKeys[i]]
      if (v != null && v !== '') parts.push(pKeys[i] + ': ' + v)
    }
  }
  if (state) {
    var sKeys = Object.keys(state)
    for (var j = 0; j < sKeys.length; j++) {
      var sv = state[sKeys[j]]
      if (typeof sv === 'object' && sv !== null) {
        var fKeys = Object.keys(sv)
        for (var k = 0; k < fKeys.length; k++) {
          var fv = sv[fKeys[k]]
          if (fv != null && fv !== '') parts.push(fKeys[k] + ': ' + fv)
        }
      } else if (sv != null && sv !== '') {
        parts.push(sKeys[j] + ': ' + sv)
      }
    }
  }
  return parts.join('\n')
}

module.exports = {
  createMixedStreamParser: createMixedStreamParser,
  createStateStore: createStateStore,
  applySpecPatch: applySpecPatch,
  nestedToFlat: nestedToFlat,
  buildSpecFromParts: buildSpecFromParts,
  groupParts: groupParts,
  collectActionNames: collectActionNames,
  formatActionMessage: formatActionMessage
}
