import React, { createContext, useContext, useMemo, useState, useCallback, useEffect } from 'react'
import type { ThemeMode } from '../utils/url'

// Get the target document (UI iframe's document when running in controller iframe)
function getTargetDocument(): Document {
  try {
    const isController = window.name === 'tgo-controller-frame'
    if (isController && window.parent && 'frames' in window.parent) {
      const uiFrame = (window.parent as any).frames['tgo-ui-frame'] as Window | undefined
      if (uiFrame && uiFrame.document) return uiFrame.document
    }
  } catch (e) {
    // cross-origin: fall back to current document
  }
  return document
}

// Apply bubble max-width based on expanded state
// Collapsed: 280px, Expanded: 70% of container width (capped at 800px for readability)
export function applyExpandedLayout(expanded: boolean) {
  const targetDoc = getTargetDocument()
  const root = targetDoc.documentElement
  if (!root) return
  try {
    const maxWidth = expanded ? 'min(80%, 800px)' : '360px'
    root.style.setProperty('--bubble-max-width', maxWidth)
  } catch {}
}

// Dark mode color palette
export const darkTheme = {
  // Backgrounds
  bgPrimary: '#1a1a1a',
  bgSecondary: '#2d2d2d',
  bgTertiary: '#3d3d3d',
  bgInput: '#2d2d2d',
  bgBubbleAgent: '#3d3d3d',
  bgBubbleUser: 'var(--primary)',
  bgHover: '#404040',
  bgCode: '#2d2d2d',
  bgCodeInline: 'rgba(255,255,255,0.1)',

  // Text colors
  textPrimary: '#f3f4f6',
  textSecondary: '#9ca3af',
  textMuted: '#6b7280',
  textOnPrimary: '#ffffff',

  // Borders
  borderPrimary: '#404040',
  borderSecondary: '#4a4a4a',

  // Accents
  linkColor: '#60a5fa',
  errorColor: '#f87171',
}

// Light mode color palette
export const lightTheme = {
  // Backgrounds
  bgPrimary: '#ffffff',
  bgSecondary: '#f5f6f7',
  bgTertiary: '#f3f4f6',
  bgInput: '#ffffff',
  bgBubbleAgent: '#f5f6f7',
  bgBubbleUser: 'var(--primary)',
  bgHover: '#f3f4f6',
  bgCode: '#f6f8fa',
  bgCodeInline: 'rgba(0,0,0,0.05)',

  // Text colors
  textPrimary: '#111827',
  textSecondary: '#6b7280',
  textMuted: '#9ca3af',
  textOnPrimary: '#ffffff',

  // Borders
  borderPrimary: '#e5e7eb',
  borderSecondary: '#eef2f4',

  // Accents
  linkColor: '#2563eb',
  errorColor: '#ef4444',
}

export type Theme = typeof lightTheme

interface ThemeContextValue {
  mode: ThemeMode
  theme: Theme
  isDark: boolean
  toggleMode: () => void
}

const ThemeContext = createContext<ThemeContextValue>({
  mode: 'light',
  theme: lightTheme,
  isDark: false,
  toggleMode: () => {},
})

// Helper to apply CSS variables to document root
function applyThemeToRoot(theme: Theme, isDark: boolean) {
  const targetDoc = getTargetDocument()
  const root = targetDoc.documentElement
  if (!root) return
  try {
    root.style.setProperty('--bg-primary', theme.bgPrimary)
    root.style.setProperty('--bg-secondary', theme.bgSecondary)
    root.style.setProperty('--bg-tertiary', theme.bgTertiary)
    root.style.setProperty('--bg-input', theme.bgInput)
    root.style.setProperty('--bg-bubble-agent', theme.bgBubbleAgent)
    root.style.setProperty('--bg-hover', theme.bgHover)
    root.style.setProperty('--bg-code', theme.bgCode)
    root.style.setProperty('--bg-code-inline', theme.bgCodeInline)
    root.style.setProperty('--text-primary', theme.textPrimary)
    root.style.setProperty('--text-secondary', theme.textSecondary)
    root.style.setProperty('--text-muted', theme.textMuted)
    root.style.setProperty('--border-primary', theme.borderPrimary)
    root.style.setProperty('--border-secondary', theme.borderSecondary)
    root.style.setProperty('--link-color', theme.linkColor)
    root.style.setProperty('--error-color', theme.errorColor)
    // Also update body background
    targetDoc.body.style.background = theme.bgPrimary

    // Toggle .dark class on root element for Emotion styled components
    if (isDark) {
      root.classList.add('dark')
      targetDoc.body.classList.add('dark')
    } else {
      root.classList.remove('dark')
      targetDoc.body.classList.remove('dark')
    }
  } catch {}
}

export function ThemeProvider({ initialMode, children }: { initialMode: ThemeMode; children: React.ReactNode }) {
  const [mode, setMode] = useState<ThemeMode>(initialMode)

  const toggleMode = useCallback(() => {
    setMode(prev => prev === 'dark' ? 'light' : 'dark')
  }, [])

  const theme = mode === 'dark' ? darkTheme : lightTheme
  const isDark = mode === 'dark'

  // Apply CSS variables whenever mode changes
  useEffect(() => {
    applyThemeToRoot(theme, isDark)
    // Notify SDK (parent window) about theme change for launcher styling
    try {
      window.parent?.postMessage({ type: 'tgo:theme-change', isDark: mode === 'dark' }, '*')
    } catch {}
  }, [theme, mode, isDark])

  const value = useMemo(() => ({
    mode,
    theme,
    isDark,
    toggleMode,
  }), [mode, theme, isDark, toggleMode])

  return (
    <ThemeContext.Provider value={value}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme() {
  return useContext(ThemeContext)
}

export default ThemeContext

