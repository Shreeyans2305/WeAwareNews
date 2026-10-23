import { createContext, createElement, useCallback, useContext, useEffect, useState } from 'react'

const ThemeContext = createContext({ theme: 'dark', toggle: () => {} })

export function getInitialTheme() {
  if (typeof window === 'undefined') return 'dark'
  try {
    const saved = window.localStorage.getItem('weaware-theme')
    if (saved === 'dark' || saved === 'light') return saved
  } catch {
    // Storage can be unavailable in private browsing contexts.
  }
  return window.matchMedia?.('(prefers-color-scheme: light)').matches ? 'light' : 'dark'
}

export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState(getInitialTheme)

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    document.body.setAttribute('data-theme', theme)
    try {
      window.localStorage.setItem('weaware-theme', theme)
    } catch {
      // The selected theme remains active for this session when storage is unavailable.
    }
  }, [theme])

  const toggle = useCallback(() => {
    setTheme((t) => (t === 'dark' ? 'light' : 'dark'))
  }, [])

  return createElement(ThemeContext.Provider, { value: { theme, toggle } }, children)
}

export function useTheme() {
  return useContext(ThemeContext)
}

// Kept for backwards compatibility — always resolves to current foreground.
// Do not use for new code; use var(--fg) / var(--bg) instead.
export const ACCENT = 'currentColor'
