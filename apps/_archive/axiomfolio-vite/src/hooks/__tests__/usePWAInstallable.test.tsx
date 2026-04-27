import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { usePWAInstallable } from '../usePWAInstallable'

const DISMISS_KEY = 'pwa_install_dismissed_until'

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed'; platform: string }>
  platforms: string[]
}

type Mutable<T> = { -readonly [K in keyof T]: T[K] }

function createInstallEvent(
  outcome: 'accepted' | 'dismissed' = 'accepted',
): BeforeInstallPromptEvent {
  const event = new Event('beforeinstallprompt') as BeforeInstallPromptEvent
  ;(event as Mutable<BeforeInstallPromptEvent>).platforms = ['web']
  ;(event as Mutable<BeforeInstallPromptEvent>).prompt = vi.fn().mockResolvedValue(undefined)
  ;(event as Mutable<BeforeInstallPromptEvent>).userChoice = Promise.resolve({
    outcome,
    platform: 'web',
  })
  return event
}

describe('usePWAInstallable', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    window.localStorage.clear()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('does not allow prompting during the first 30 seconds of session activity', () => {
    const { result } = renderHook(() => usePWAInstallable())

    act(() => {
      window.dispatchEvent(createInstallEvent())
    })

    expect(result.current.canPrompt).toBe(false)
  })

  it('allows prompting after 30s once a beforeinstallprompt event has fired', () => {
    const { result } = renderHook(() => usePWAInstallable())

    act(() => {
      window.dispatchEvent(createInstallEvent())
    })

    act(() => {
      vi.advanceTimersByTime(30_001)
    })

    expect(result.current.canPrompt).toBe(true)
    expect(result.current.installed).toBe(false)
  })

  it('persists dismissal for 30 days in localStorage', () => {
    const { result } = renderHook(() => usePWAInstallable())

    act(() => {
      window.dispatchEvent(createInstallEvent())
      vi.advanceTimersByTime(30_001)
    })

    const before = Date.now()
    act(() => {
      result.current.dismiss()
    })

    const stored = Number.parseInt(window.localStorage.getItem(DISMISS_KEY) ?? '0', 10)
    expect(stored).toBeGreaterThanOrEqual(before + 30 * 24 * 60 * 60 * 1000 - 1000)
    expect(result.current.canPrompt).toBe(false)
  })

  it('honors a still-active dismissal from a previous session', () => {
    const futureMs = Date.now() + 7 * 24 * 60 * 60 * 1000
    window.localStorage.setItem(DISMISS_KEY, String(futureMs))

    const { result } = renderHook(() => usePWAInstallable())

    act(() => {
      window.dispatchEvent(createInstallEvent())
      vi.advanceTimersByTime(30_001)
    })

    expect(result.current.canPrompt).toBe(false)
  })

  it('treats an expired dismissal as not active', () => {
    window.localStorage.setItem(DISMISS_KEY, String(Date.now() - 1000))

    const { result } = renderHook(() => usePWAInstallable())

    act(() => {
      window.dispatchEvent(createInstallEvent())
      vi.advanceTimersByTime(30_001)
    })

    expect(result.current.canPrompt).toBe(true)
  })
})
