import { afterEach, describe, expect, it, vi } from 'vitest'

import { getDisplayMode, isStandalone } from '../displayMode'

const realMatchMedia = window.matchMedia

afterEach(() => {
  ;(window as unknown as { matchMedia: typeof realMatchMedia }).matchMedia = realMatchMedia
})

function mockMatchMedia(matchedQuery: string) {
  ;(window as unknown as { matchMedia: typeof window.matchMedia }).matchMedia = vi
    .fn()
    .mockImplementation((query: string) => ({
      matches: query === matchedQuery,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }))
}

describe('displayMode', () => {
  it('reports browser when no display-mode media query matches', () => {
    mockMatchMedia('__never__')
    expect(getDisplayMode()).toBe('browser')
    expect(isStandalone()).toBe(false)
  })

  it('reports standalone when display-mode: standalone matches', () => {
    mockMatchMedia('(display-mode: standalone)')
    expect(getDisplayMode()).toBe('standalone')
    expect(isStandalone()).toBe(true)
  })

  it('reports fullscreen when display-mode: fullscreen matches', () => {
    mockMatchMedia('(display-mode: fullscreen)')
    expect(getDisplayMode()).toBe('fullscreen')
    expect(isStandalone()).toBe(true)
  })
})
