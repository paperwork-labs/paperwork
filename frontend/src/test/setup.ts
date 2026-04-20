import '@testing-library/jest-dom/vitest';
import { afterEach } from 'vitest';
import { cleanup } from '@testing-library/react';

// React Testing Library only auto-cleans when Vitest runs with `globals: true`,
// which we intentionally avoid. Register an explicit afterEach so each test
// starts with an empty DOM and tests can share data-testid values without
// colliding across cases.
afterEach(() => {
  cleanup();
});

// happy-dom / jsdom: cmdk measures list height via ResizeObserver.
if (typeof globalThis.ResizeObserver === 'undefined') {
  globalThis.ResizeObserver = class ResizeObserver {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  };
}

// happy-dom: cmdk scrolls selected items into view (may be missing or non-callable).
if (typeof Element !== 'undefined' && typeof Element.prototype.scrollIntoView !== 'function') {
  Element.prototype.scrollIntoView = function scrollIntoViewPolyfill() {
    /* no-op for test env */
  };
}

// jsdom doesn't implement matchMedia; Chakra's useMediaQuery relies on it.
if (typeof window !== 'undefined' && !(window as any).matchMedia) {
  (window as any).matchMedia = (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {}, // deprecated
    removeListener: () => {}, // deprecated
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  });
}




