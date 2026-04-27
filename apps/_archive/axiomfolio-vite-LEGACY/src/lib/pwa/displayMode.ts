// Utilities for detecting PWA display state across browsers.
//
// `display-mode` media queries are the standard way to know we're running as
// an installed PWA. iOS Safari predates the standard and exposes
// navigator.standalone instead, so we check both.

export type PwaDisplayMode = 'standalone' | 'minimal-ui' | 'fullscreen' | 'browser'

interface NavigatorWithStandalone extends Navigator {
  standalone?: boolean
}

function matches(query: string): boolean {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
    return false
  }
  try {
    return window.matchMedia(query).matches
  } catch {
    return false
  }
}

export function getDisplayMode(): PwaDisplayMode {
  if (matches('(display-mode: fullscreen)')) return 'fullscreen'
  if (matches('(display-mode: standalone)')) return 'standalone'
  if (matches('(display-mode: minimal-ui)')) return 'minimal-ui'
  return 'browser'
}

export function isStandalone(): boolean {
  if (typeof window === 'undefined') return false
  if (matches('(display-mode: standalone)') || matches('(display-mode: fullscreen)')) {
    return true
  }
  const nav = window.navigator as NavigatorWithStandalone
  return Boolean(nav.standalone)
}

export function isIos(): boolean {
  if (typeof window === 'undefined') return false
  const ua = window.navigator.userAgent
  // iPadOS 13+ identifies as Macintosh; the touch-points heuristic is the
  // commonly-used disambiguation.
  const iPadOnDesktopUa =
    /Macintosh/.test(ua) &&
    typeof window.navigator.maxTouchPoints === 'number' &&
    window.navigator.maxTouchPoints > 1
  return /iPad|iPhone|iPod/.test(ua) || iPadOnDesktopUa
}
