import { useCallback, useEffect, useRef, useState } from 'react'

import { isIos, isStandalone } from '../lib/pwa/displayMode'

// Spec: https://developer.mozilla.org/en-US/docs/Web/API/BeforeInstallPromptEvent
// Not in lib.dom.d.ts because it's still a non-standard / Chromium event.
interface BeforeInstallPromptEvent extends Event {
  readonly platforms: string[]
  readonly userChoice: Promise<{ outcome: 'accepted' | 'dismissed'; platform: string }>
  prompt: () => Promise<void>
}

const DISMISS_KEY = 'pwa_install_dismissed_until'
// Persist a dismissal for 30 days so we don't nag users after they've said no.
const DISMISS_DURATION_MS = 30 * 24 * 60 * 60 * 1000
// Don't surface the prompt during the first 30 seconds — it would land on
// first paint and feels spammy. We want some signal that the user is engaged.
const MIN_SESSION_MS = 30 * 1000

function readDismissedUntil(): number {
  if (typeof window === 'undefined') return 0
  try {
    const raw = window.localStorage.getItem(DISMISS_KEY)
    if (!raw) return 0
    const parsed = Number.parseInt(raw, 10)
    return Number.isFinite(parsed) ? parsed : 0
  } catch {
    return 0
  }
}

function writeDismissedUntil(epochMs: number): void {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(DISMISS_KEY, String(epochMs))
  } catch {
    // localStorage may be unavailable (private mode, quota). The cost is just
    // that the prompt may reappear on next session — non-critical.
  }
}

export interface UsePWAInstallableResult {
  /** True when we should show the install affordance now. */
  canPrompt: boolean
  /** True when the app is already running as a PWA. */
  installed: boolean
  /** True when this is iOS Safari (no programmatic install — show instructions). */
  isIosSafari: boolean
  /** Trigger the native install prompt (no-op on iOS). */
  promptInstall: () => Promise<'accepted' | 'dismissed' | 'unavailable'>
  /** Dismiss for the next 30 days. */
  dismiss: () => void
}

export function usePWAInstallable(): UsePWAInstallableResult {
  const deferredPromptRef = useRef<BeforeInstallPromptEvent | null>(null)
  const [hasDeferredPrompt, setHasDeferredPrompt] = useState(false)
  const [installed, setInstalled] = useState<boolean>(() => isStandalone())
  const [sessionElapsed, setSessionElapsed] = useState(false)
  const [dismissedUntil, setDismissedUntil] = useState<number>(() => readDismissedUntil())

  // iOS Safari never fires beforeinstallprompt — surface a manual instructions
  // block instead. We don't show this in standalone mode (already installed).
  const isIosSafari =
    typeof window !== 'undefined' && isIos() && !installed

  useEffect(() => {
    if (typeof window === 'undefined') return

    const onBeforeInstall = (event: Event) => {
      // Per the spec, calling preventDefault stops the browser's own mini
      // infobar so we can show our own UI on our schedule.
      event.preventDefault()
      deferredPromptRef.current = event as BeforeInstallPromptEvent
      setHasDeferredPrompt(true)
    }

    const onAppInstalled = () => {
      deferredPromptRef.current = null
      setHasDeferredPrompt(false)
      setInstalled(true)
    }

    window.addEventListener('beforeinstallprompt', onBeforeInstall as EventListener)
    window.addEventListener('appinstalled', onAppInstalled)
    return () => {
      window.removeEventListener('beforeinstallprompt', onBeforeInstall as EventListener)
      window.removeEventListener('appinstalled', onAppInstalled)
    }
  }, [])

  useEffect(() => {
    if (sessionElapsed) return
    const handle = window.setTimeout(() => setSessionElapsed(true), MIN_SESSION_MS)
    return () => window.clearTimeout(handle)
  }, [sessionElapsed])

  // Re-check display mode when the page becomes visible again — e.g. user
  // installed the app from the address-bar UI in another tab.
  useEffect(() => {
    if (typeof document === 'undefined') return
    const onVisibility = () => {
      if (document.visibilityState === 'visible' && isStandalone()) {
        setInstalled(true)
      }
    }
    document.addEventListener('visibilitychange', onVisibility)
    return () => document.removeEventListener('visibilitychange', onVisibility)
  }, [])

  const promptInstall = useCallback(async (): Promise<
    'accepted' | 'dismissed' | 'unavailable'
  > => {
    const evt = deferredPromptRef.current
    if (!evt) return 'unavailable'
    try {
      await evt.prompt()
      const choice = await evt.userChoice
      deferredPromptRef.current = null
      setHasDeferredPrompt(false)
      if (choice.outcome === 'dismissed') {
        const until = Date.now() + DISMISS_DURATION_MS
        writeDismissedUntil(until)
        setDismissedUntil(until)
      }
      return choice.outcome
    } catch {
      // The user-gesture requirement may have lapsed; fail closed and let the
      // caller surface a "try again" affordance.
      return 'unavailable'
    }
  }, [])

  const dismiss = useCallback(() => {
    const until = Date.now() + DISMISS_DURATION_MS
    writeDismissedUntil(until)
    setDismissedUntil(until)
    deferredPromptRef.current = null
    setHasDeferredPrompt(false)
  }, [])

  const dismissedActive = dismissedUntil > Date.now()
  const canPrompt =
    !installed && sessionElapsed && !dismissedActive && (hasDeferredPrompt || isIosSafari)

  return { canPrompt, installed, isIosSafari, promptInstall, dismiss }
}
