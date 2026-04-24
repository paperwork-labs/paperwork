import { useState } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import { Download, Plus, Share, X } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { DURATION, EASE } from '@/lib/motion'
import { usePWAInstallable } from '@/hooks/usePWAInstallable'

interface InstallPromptProps {
  /** Force the prompt visible regardless of session/dismissal gating. Used for tests + Storybook. */
  forceVisible?: boolean
  className?: string
}

/**
 * Bottom-anchored install affordance for AxiomFolio.
 *
 * Visibility rules (encapsulated in `usePWAInstallable`):
 *  - Hidden while running standalone (already installed).
 *  - Hidden during the first 30s of session activity to avoid first-paint nag.
 *  - Hidden for 30 days after the user dismisses or declines.
 *  - On Chromium browsers, only shown after `beforeinstallprompt` fires.
 *  - On iOS Safari, shows a manual "Share → Add to Home Screen" walkthrough.
 *
 * Layout:
 *  - Mobile (<sm): full-width sheet anchored to the bottom safe-area inset.
 *  - Desktop: 360px card pinned to the bottom-right.
 *
 * Motion respects `prefers-reduced-motion` via `useReducedMotion()`.
 */
export function InstallPrompt({ forceVisible, className }: InstallPromptProps) {
  const { canPrompt, isIosSafari, promptInstall, dismiss } = usePWAInstallable()
  const reducedMotion = useReducedMotion()
  const [isPrompting, setIsPrompting] = useState(false)

  const visible = forceVisible ?? canPrompt
  if (!visible) return null

  const handleInstall = async () => {
    if (isPrompting) return
    setIsPrompting(true)
    try {
      const outcome = await promptInstall()
      if (outcome === 'unavailable') {
        // Native prompt isn't available — close gracefully so we don't leave
        // the affordance hanging in a broken state. The 30-day suppression
        // protects from re-render churn.
        dismiss()
      }
    } finally {
      setIsPrompting(false)
    }
  }

  const initial = reducedMotion ? false : { opacity: 0, y: 16 }
  const animate = { opacity: 1, y: 0 }
  const exit = reducedMotion
    ? { opacity: 1, y: 0 }
    : {
        opacity: 0,
        y: 8,
        transition: { duration: DURATION.fast, ease: EASE.standard },
      }
  const transition = reducedMotion
    ? { duration: 0 }
    : { duration: DURATION.medium, ease: EASE.emphasized }

  return (
    <AnimatePresence>
      <motion.aside
        key="pwa-install-prompt"
        role="dialog"
        aria-labelledby="pwa-install-title"
        aria-describedby="pwa-install-body"
        initial={initial}
        animate={animate}
        exit={exit}
        transition={transition}
        className={cn(
          // Mobile: bottom sheet, desktop: bottom-right card.
          'fixed inset-x-0 bottom-0 z-50 mx-auto px-4 pb-[calc(env(safe-area-inset-bottom)+1rem)]',
          'sm:inset-auto sm:right-4 sm:bottom-4 sm:left-auto sm:mx-0 sm:max-w-sm sm:px-0 sm:pb-0',
          'pointer-events-none',
          className,
        )}
      >
        <div className="pointer-events-auto rounded-2xl border border-border bg-popover p-4 text-popover-foreground shadow-lg backdrop-blur-sm sm:rounded-xl sm:p-4">
          <div className="flex items-start gap-3">
            <div
              aria-hidden="true"
              className="grid size-9 shrink-0 place-items-center rounded-lg bg-primary/10 text-primary"
            >
              <Download className="size-4" />
            </div>
            <div className="min-w-0 flex-1">
              <p id="pwa-install-title" className="text-sm font-semibold text-foreground">
                Install AxiomFolio
              </p>
              <p id="pwa-install-body" className="mt-1 text-xs text-muted-foreground">
                {isIosSafari
                  ? 'Get a faster, full-screen experience. Add to your Home Screen for one-tap access.'
                  : 'Get a faster, full-screen experience and quicker access from your dock or home screen.'}
              </p>
              {isIosSafari ? (
                <ol className="mt-3 space-y-1.5 text-xs text-muted-foreground">
                  <li className="flex items-center gap-1.5">
                    <span>1.</span>
                    <span>Tap</span>
                    <Share className="size-3.5" aria-label="Share" />
                    <span>in the Safari toolbar</span>
                  </li>
                  <li className="flex items-center gap-1.5">
                    <span>2.</span>
                    <span>Choose</span>
                    <Plus className="size-3.5" aria-label="Add" />
                    <span>
                      <span className="font-medium text-foreground">Add to Home Screen</span>
                    </span>
                  </li>
                </ol>
              ) : (
                <div className="mt-3 flex items-center gap-2">
                  <Button type="button" size="sm" onClick={handleInstall} disabled={isPrompting}>
                    {isPrompting ? 'Installing…' : 'Install app'}
                  </Button>
                  <Button type="button" size="sm" variant="ghost" onClick={dismiss}>
                    Not now
                  </Button>
                </div>
              )}
            </div>
            <Button
              type="button"
              size="icon-sm"
              variant="ghost"
              aria-label="Dismiss install prompt"
              onClick={dismiss}
              className="-mt-1 -mr-1"
            >
              <X className="size-4" />
            </Button>
          </div>
        </div>
      </motion.aside>
    </AnimatePresence>
  )
}

export default InstallPrompt
