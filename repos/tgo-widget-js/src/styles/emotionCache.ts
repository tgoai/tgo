import createCache from '@emotion/cache'

// Bind Emotion to this document's <head>. In production, Emotion uses CSSOM insertRule,
// so style tags will look empty but rules exist in sheet.cssRules.
const cache = createCache({ key: 'tgo', container: document.head })
export default cache

