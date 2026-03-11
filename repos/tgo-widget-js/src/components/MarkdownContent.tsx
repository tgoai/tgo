import React, { useMemo, useRef, useEffect } from 'react';
import { Marked, RendererObject, RendererThis, Tokens } from 'marked';
import { markedHighlight } from "marked-highlight";
import hljs from 'highlight.js/lib/core';
// Import only commonly used languages
import javascript from 'highlight.js/lib/languages/javascript';
import typescript from 'highlight.js/lib/languages/typescript';
import python from 'highlight.js/lib/languages/python';
import java from 'highlight.js/lib/languages/java';
import cpp from 'highlight.js/lib/languages/cpp';
import csharp from 'highlight.js/lib/languages/csharp';
import go from 'highlight.js/lib/languages/go';
import rust from 'highlight.js/lib/languages/rust';
import php from 'highlight.js/lib/languages/php';
import ruby from 'highlight.js/lib/languages/ruby';
import sql from 'highlight.js/lib/languages/sql';
import bash from 'highlight.js/lib/languages/bash';
import shell from 'highlight.js/lib/languages/shell';
import json from 'highlight.js/lib/languages/json';
import xml from 'highlight.js/lib/languages/xml';
import yaml from 'highlight.js/lib/languages/yaml';
import markdown from 'highlight.js/lib/languages/markdown';
import css from 'highlight.js/lib/languages/css';
import scss from 'highlight.js/lib/languages/scss';
import plaintext from 'highlight.js/lib/languages/plaintext';
import DOMPurify from 'dompurify';
import { imagePreviewManager } from './ImagePreview';

// Register languages
hljs.registerLanguage('javascript', javascript);
hljs.registerLanguage('typescript', typescript);
hljs.registerLanguage('python', python);
hljs.registerLanguage('java', java);
hljs.registerLanguage('cpp', cpp);
hljs.registerLanguage('c++', cpp);
hljs.registerLanguage('csharp', csharp);
hljs.registerLanguage('c#', csharp);
hljs.registerLanguage('go', go);
hljs.registerLanguage('rust', rust);
hljs.registerLanguage('php', php);
hljs.registerLanguage('ruby', ruby);
hljs.registerLanguage('sql', sql);
hljs.registerLanguage('bash', bash);
hljs.registerLanguage('sh', bash);
hljs.registerLanguage('shell', shell);
hljs.registerLanguage('json', json);
hljs.registerLanguage('xml', xml);
hljs.registerLanguage('html', xml);
hljs.registerLanguage('yaml', yaml);
hljs.registerLanguage('yml', yaml);
hljs.registerLanguage('markdown', markdown);
hljs.registerLanguage('md', markdown);
hljs.registerLanguage('css', css);
hljs.registerLanguage('scss', scss);
hljs.registerLanguage('plaintext', plaintext);

interface MarkdownContentProps {
  content: string;
  className?: string;
  /** 发送消息回调（用于 msg:// 协议） */
  onSendMessage?: (message: string) => void;
  /** 复制成功回调 */
  onCopySuccess?: (text: string) => void;
}

const headingClassMap: Record<number, string> = {
  1: 'text-lg font-semibold mb-2 mt-3 first:mt-0 last:mb-0 text-gray-900 dark:text-gray-100',
  2: 'text-base font-semibold mb-1.5 mt-2.5 first:mt-0 last:mb-0 text-gray-900 dark:text-gray-100',
  3: 'text-sm font-semibold mb-1 mt-2 first:mt-0 last:mb-0 text-gray-900 dark:text-gray-100',
  4: 'text-sm font-medium mb-1 mt-1.5 first:mt-0 last:mb-0 text-gray-900 dark:text-gray-100',
  5: 'text-xs font-medium mb-0.5 mt-1 first:mt-0 last:mb-0 text-gray-900 dark:text-gray-100',
  6: 'text-xs font-medium mb-0.5 mt-1 first:mt-0 last:mb-0 text-gray-700 dark:text-gray-300'
};

const escapeHtml = (value: string): string =>
  value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');

const sanitizeHref = (href?: string | null): string => {
  if (!href) return '';
  const trimmed = href.trim();

  if (trimmed.startsWith('#')) {
    return trimmed;
  }

  try {
    const url = new URL(trimmed, 'http://localhost');
    if (['http:', 'https:', 'mailto:', 'tel:'].includes(url.protocol)) {
      return trimmed;
    }
  } catch {
    if (trimmed.startsWith('mailto:') || trimmed.startsWith('tel:') || trimmed.startsWith('/')) {
      return trimmed;
    }
  }

  return '#';
};

const renderer: RendererObject = {
  heading(this: RendererThis, { tokens, depth }: Tokens.Heading) {
    const html = this.parser.parseInline(tokens);
    const clz = headingClassMap[depth] || 'font-bold mt-4 mb-2 first:mt-0 last:mb-0 text-gray-900 dark:text-gray-100';
    return `<h${depth} class="${clz}">${html}</h${depth}>`;
  },
  paragraph(this: RendererThis, { tokens }: Tokens.Paragraph) {
    const html = this.parser.parseInline(tokens);
    return `<p class="mb-1.5 last:mb-0 leading-normal text-gray-800 dark:text-gray-200">${html}</p>`;
  },
  link(this: RendererThis, { href, title, tokens }: Tokens.Link) {
    const html = this.parser.parseInline(tokens);
    const safeHref = sanitizeHref(href);
    const titleAttr = title ? ` title="${escapeHtml(title)}"` : '';
    return `<a href="${escapeHtml(safeHref)}"${titleAttr} target="_blank" rel="noopener noreferrer" class="text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300 underline break-words">${html}</a>`;
  },
  list(this: RendererThis, token: Tokens.List) {
    const itemsHtml = token.items
      .map(item => {
        const rawContent = this.parser.parse(item.tokens);
        const trimmed = rawContent.trim();
        const singleParagraphMatch = trimmed.match(/^<p>([\s\S]*)<\/p>$/);
        const content = singleParagraphMatch ? singleParagraphMatch[1].trim() : trimmed;

        const checkbox = item.task
          ? `<input type="checkbox" class="mr-2 h-3.5 w-3.5 align-middle rounded border border-gray-300 dark:border-gray-600 text-blue-500 dark:text-blue-400" disabled ${item.checked ? 'checked' : ''} />`
          : '';

        return `<li class="text-gray-800 dark:text-gray-200 leading-normal">${checkbox}${content}</li>`;
      })
      .join('');
    const startAttr = token.ordered && token.start && token.start !== 1 ? ` start="${token.start}"` : '';
    if (token.ordered) {
      return `<ol${startAttr} class="list-decimal list-outside mb-1.5 first:mt-0 last:mb-0 space-y-0.5 pl-4">${itemsHtml}</ol>`;
    }
    return `<ul class="list-disc list-outside mb-1.5 first:mt-0 last:mb-0 space-y-0.5 pl-4">${itemsHtml}</ul>`;
  },
  blockquote(this: RendererThis, { tokens }: Tokens.Blockquote) {
    const html = this.parser.parse(tokens);
    return `<blockquote class="border-l-4 border-gray-300 dark:border-gray-600 pl-4 py-2 my-3 italic text-gray-700 dark:text-gray-300 bg-gray-50 dark:bg-gray-800">${html}</blockquote>`;
  },
  hr() {
    return '<hr class="my-4 border-t border-gray-300 dark:border-gray-600" />';
  },
  table(this: RendererThis, token: Tokens.Table) {
    const headerRow = token.header
      .map((cell, index) => {
        const align = token.align[index];
        const alignAttr = align ? ` style="text-align:${align}"` : '';
        const content = this.parser.parseInline(cell.tokens);
        return `<th class="px-4 py-2 text-left text-sm font-semibold text-gray-900 dark:text-gray-100 border border-gray-300 dark:border-gray-600"${alignAttr}>${content}</th>`;
      })
      .join('');

    const headerSection = headerRow
      ? `<thead class="bg-gray-100 dark:bg-gray-800"><tr class="border-b border-gray-300 dark:border-gray-600">${headerRow}</tr></thead>`
      : '';

    const bodyRows = token.rows
      .map(row => {
        const cells = row
          .map((cell, index) => {
            const align = token.align[index];
            const alignAttr = align ? ` style="text-align:${align}"` : '';
            const content = this.parser.parseInline(cell.tokens);
            return `<td class="px-4 py-2 text-sm text-gray-800 dark:text-gray-200 border border-gray-300 dark:border-gray-600"${alignAttr}>${content}</td>`;
          })
          .join('');
        return `<tr class="border-b border-gray-300 dark:border-gray-600">${cells}</tr>`;
      })
      .join('');

    return `
      <div class="my-3 overflow-x-auto">
        <table class="min-w-full border-collapse border border-gray-300 dark:border-gray-600">
          ${headerSection}
          <tbody>${bodyRows}</tbody>
        </table>
      </div>
    `;
  },
  strong(this: RendererThis, { tokens }: Tokens.Strong) {
    const html = this.parser.parseInline(tokens);
    return `<strong class="font-bold text-gray-900 dark:text-gray-100">${html}</strong>`;
  },
  em(this: RendererThis, { tokens }: Tokens.Em) {
    const html = this.parser.parseInline(tokens);
    return `<em class="italic text-gray-800 dark:text-gray-200">${html}</em>`;
  },
  del(this: RendererThis, { tokens }: Tokens.Del) {
    const html = this.parser.parseInline(tokens);
    return `<del class="line-through text-gray-600 dark:text-gray-400">${html}</del>`;
  },
  image(this: RendererThis, { href, title, text }: Tokens.Image) {
    const safeSrc = sanitizeHref(href);
    const titleAttr = title ? ` title="${escapeHtml(title)}"` : '';
    return `<img src="${escapeHtml(safeSrc)}" alt="${escapeHtml(text || '')}"${titleAttr} class="max-w-full h-auto rounded-lg my-2 cursor-pointer hover:opacity-90 transition-opacity markdown-image" data-preview-src="${escapeHtml(safeSrc)}" loading="lazy" />`;
  }
};

// marked.use({gfm: true, breaks: false });

const marked = new Marked(markedHighlight({
  emptyLangClass: 'hljs',
  langPrefix: 'hljs language-',
  highlight(code, lang) {
    const language = hljs.getLanguage(lang) ? lang : 'plaintext';
    return hljs.highlight(code, { language }).value;
  }
}));

marked.use({
    renderer,
    gfm: true,
});


const MARKDOWN_CACHE_LIMIT = 200;
const markdownCache = new Map<string, string>();

/**
 * Pre-process markdown to handle incomplete/streaming content
 * This helps prevent rendering issues with unterminated code blocks, etc.
 */
const preprocessStreamingMarkdown = (markdown: string): string => {
  if (!markdown) return '';

  let processed = markdown;

  // Remove leading whitespace from the start of content to prevent
  // it being interpreted as an indented code block (4+ spaces = code block in Markdown)
  // But preserve intentional code blocks (those starting with ```)
  processed = processed.replace(/^[ \t]+/gm, (match, offset) => {
    // Check if this line is inside a fenced code block
    const before = processed.substring(0, offset);
    const fenceMatches = before.match(/^(`{3,}|~{3,})/gm) || [];
    // If odd number of fences before this line, we're inside a code block - preserve spaces
    if (fenceMatches.length % 2 !== 0) {
      return match;
    }
    // Otherwise, trim leading spaces to prevent indented code block interpretation
    // Keep up to 3 spaces (Markdown allows up to 3 for normal content)
    return match.length > 3 ? '   ' : match;
  });

  // Count code fence occurrences (``` or ~~~)
  const codeBlockMatches = processed.match(/^(`{3,}|~{3,})/gm) || [];
  const codeBlockCount = codeBlockMatches.length;

  // If odd number of code fences, the last code block is unclosed - close it
  if (codeBlockCount % 2 !== 0) {
    // Find the last code fence to determine which type to use for closing
    const lastFenceMatch = processed.match(/(`{3,}|~{3,})(?!.*(`{3,}|~{3,}))/s);
    const closingFence = lastFenceMatch ? lastFenceMatch[1].charAt(0).repeat(3) : '```';
    processed = processed + '\n' + closingFence;
  }

  // Handle unclosed inline code (backticks)
  // Count single backticks not part of code fences
  const inlineCodePattern = /(?<!`)`(?!`)/g;
  const inlineMatches = processed.match(inlineCodePattern) || [];
  if (inlineMatches.length % 2 !== 0) {
    processed = processed + '`';
  }

  return processed;
};

const renderMarkdownToHtml = (markdown: string): string => {
  if (!markdown) return '';

  // Pre-process for streaming content
  const processedMarkdown = preprocessStreamingMarkdown(markdown);

  const cacheKey = processedMarkdown;
  const cached = markdownCache.get(cacheKey);
  if (cached) {
    return cached;
  }

  const parsed = marked.parse(processedMarkdown) as string;
  const sanitizeConfig = {
    USE_PROFILES: { html: true },
    ADD_ATTR: ['target', 'rel', 'data-preview-src'],
  };

  const sanitized = typeof window !== 'undefined'
    ? String(DOMPurify.sanitize(parsed, sanitizeConfig))
    : parsed;

  markdownCache.set(cacheKey, sanitized);
  if (markdownCache.size > MARKDOWN_CACHE_LIMIT) {
    const firstKey = markdownCache.keys().next().value;
    if (firstKey) {
      markdownCache.delete(firstKey);
    }
  }

  return sanitized;
};

/**
 * Markdown Content Renderer Component
 * Renders markdown content using Marked with caching and sanitization for performance & safety
 */
const MarkdownContent: React.FC<MarkdownContentProps> = ({ 
  content, 
  className = '',
}) => {
  const containerRef = useRef<HTMLDivElement>(null);

  const html = useMemo(() => {
    return renderMarkdownToHtml(content || '');
  }, [content]);

  // 处理 Markdown 中图片的点击事件
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const handleClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (target.tagName === 'IMG' && target.hasAttribute('data-preview-src')) {
        const src = target.getAttribute('data-preview-src');
        if (src) {
          e.preventDefault();
          e.stopPropagation();
          // 收集所有可预览的图片
          const allImages = Array.from(container.querySelectorAll('img[data-preview-src]'))
            .map(img => img.getAttribute('data-preview-src'))
            .filter((s): s is string => !!s);
          const index = allImages.indexOf(src);
          imagePreviewManager.open(allImages, index >= 0 ? index : 0);
        }
      }
    };

    container.addEventListener('click', handleClick);
    return () => container.removeEventListener('click', handleClick);
  }, [html]);

  const combinedClassName = className
    ? `markdown-content ${className}`.trim()
    : 'markdown-content';

  return (
    <div
      ref={containerRef}
      className={combinedClassName}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
};

export default MarkdownContent;
