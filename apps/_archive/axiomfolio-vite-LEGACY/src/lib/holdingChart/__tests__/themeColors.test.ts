import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { resolveThemeColors, withAlpha } from "../themeColors";

describe("withAlpha", () => {
  it("returns canvas-parseable rgb/rgba (never raw color-mix) for all inputs", () => {
    expect(withAlpha("#2563EB", 0.18)).toMatch(/^rgba?\(/);
    expect(withAlpha("#2563EB", 0.18)).not.toMatch(/oklch|color-mix/);
    expect(withAlpha("rgb(37 99 235)", 0.5)).toMatch(/^rgba?\(/);
    expect(withAlpha("rgb(37 99 235)", 0.5)).not.toMatch(/oklch|color-mix/);
    expect(withAlpha("oklch(0.141 0.005 285.823)", 0.85)).toMatch(/^rgba?\(/);
    expect(withAlpha("oklch(0.141 0.005 285.823)", 0.85)).not.toMatch(
      /oklch|color-mix/,
    );
  });

  it("returns the literal `transparent` keyword when alpha is 0", () => {
    expect(withAlpha("#2563EB", 0)).toBe("transparent");
  });

  it("clamps alpha into the [0, 1] range", () => {
    expect(withAlpha("#000000", -0.5)).toBe("transparent");
    expect(withAlpha("#000000", 2)).toMatch(/^rgba?\(/);
    expect(withAlpha("#000000", 2)).not.toMatch(/oklch|color-mix/);
  });
});

describe("resolveThemeColors", () => {
  let originalGetComputedStyle: typeof window.getComputedStyle;

  beforeEach(() => {
    originalGetComputedStyle = window.getComputedStyle;
  });

  afterEach(() => {
    window.getComputedStyle = originalGetComputedStyle;
  });

  it("returns canvas-parseable colors (rgb/rgba) so lightweight-charts can paint", () => {
    // jsdom can't resolve oklch/color-mix via the DOM probe, so the helper
    // falls back to its opinionated rgba(...) defaults. The important
    // invariant is that callers never receive raw `oklch(...)` or
    // `color-mix(...)` strings — lightweight-charts v5 rejects both.
    window.getComputedStyle = vi.fn().mockImplementation(() => ({
      getPropertyValue: (prop: string) => {
        if (prop === "--foreground") return " oklch(0.141 0.005 285.823) ";
        if (prop === "--border") return " oklch(0.92 0.004 286.32) ";
        return "";
      },
    })) as unknown as typeof window.getComputedStyle;

    const colors = resolveThemeColors();

    expect(colors.text).toMatch(/^rgba?\(/);
    expect(colors.gridLine).toMatch(/^rgba?\(/);
    expect(colors.text).not.toMatch(/oklch|color-mix/);
    expect(colors.gridLine).not.toMatch(/oklch|color-mix/);
  });

  it("falls back to opinionated defaults when the CSS variables are unset", () => {
    window.getComputedStyle = vi.fn().mockImplementation(() => ({
      getPropertyValue: () => "",
    })) as unknown as typeof window.getComputedStyle;

    const colors = resolveThemeColors();

    expect(colors.text).toMatch(/^rgba?\(/);
    expect(colors.gridLine).toMatch(/^rgba?\(/);
  });
});
