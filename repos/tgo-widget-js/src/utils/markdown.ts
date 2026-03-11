import { marked } from 'marked'
import { markedHighlight } from 'marked-highlight'
import hljs from 'highlight.js'

// Configure marked with highlight extension
marked.use(markedHighlight({
  langPrefix: 'hljs language-',
  highlight(code, lang) {
    const language = hljs.getLanguage(lang) ? lang : 'plaintext'
    return hljs.highlight(code, { language }).value
  }
}))

marked.setOptions({
  gfm: true,
  breaks: true,
})

/**
 * Preprocess text to prevent indented content from being parsed as code blocks.
 * Markdown treats lines with 4+ leading spaces as code blocks, which is often
 * unintended for chat messages. This function removes up to 4 leading spaces
 * from each line (preserving relative indentation for actual code blocks).
 */
function preprocessText(text: string): string {
  if (!text) return text

  // Split into lines
  const lines = text.split('\n')

  // Check if this looks like intentional code (fenced code block or consistent indentation)
  const hasFencedCode = lines.some(line => line.trim().startsWith('```'))
  if (hasFencedCode) {
    // Don't modify if there's a fenced code block
    return text
  }

  // Remove up to 4 leading spaces from lines that start with spaces
  // but preserve the content structure
  return lines.map(line => {
    // Only process lines that start with spaces (not tabs)
    const match = line.match(/^( {1,4})(\S.*)$/)
    if (match) {
      // Remove leading spaces (1-4) before non-whitespace content
      return match[2]
    }
    return line
  }).join('\n')
}

export function renderMarkdown(text: string): string {
  try {
    const processed = preprocessText(text || '')
    return marked.parse(processed) as string
  } catch {
    // Fallback to escaping on parse error
    const esc = (s: string) => s
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
    return `<pre><code>${esc(text || '')}</code></pre>`
  }
}

