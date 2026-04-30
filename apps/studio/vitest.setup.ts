import { afterEach, vi } from "vitest";

globalThis.ResizeObserver = class ResizeObserver {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
};

function mockMql(matches: boolean): MediaQueryList {
  return {
    matches,
    media: "",
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(() => false),
  } as unknown as MediaQueryList;
}

const motionOkMql = mockMql(false);

/** Default Studio tests: prefers-reduced-motion off unless a test overrides `matchMedia`. */
globalThis.matchMedia = vi.fn(() => motionOkMql);

afterEach(() => {
  globalThis.matchMedia = vi.fn(() => motionOkMql);
});
