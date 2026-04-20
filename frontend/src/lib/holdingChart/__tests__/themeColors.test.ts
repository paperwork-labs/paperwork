import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { resolveThemeColors, withAlpha } from "../themeColors";

describe("withAlpha", () => {
  it("wraps any CSS color in a color-mix() with the requested percentage", () => {
    expect(withAlpha("#2563EB", 0.18)).toBe(
      "color-mix(in oklch, #2563EB 18%, transparent)",
    );
    expect(withAlpha("rgb(37 99 235)", 0.5)).toBe(
      "color-mix(in oklch, rgb(37 99 235) 50%, transparent)",
    );
    expect(withAlpha("oklch(0.141 0.005 285.823)", 0.85)).toBe(
      "color-mix(in oklch, oklch(0.141 0.005 285.823) 85%, transparent)",
    );
  });

  it("returns the literal `transparent` keyword when alpha is 0", () => {
    expect(withAlpha("#2563EB", 0)).toBe("transparent");
  });

  it("clamps alpha into the [0, 1] range", () => {
    expect(withAlpha("#000000", -0.5)).toBe("transparent");
    expect(withAlpha("#000000", 2)).toBe(
      "color-mix(in oklch, #000000 100%, transparent)",
    );
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

  it("reads --foreground and --border from documentElement and wraps with color-mix", () => {
    window.getComputedStyle = vi.fn().mockImplementation(() => ({
      getPropertyValue: (prop: string) => {
        if (prop === "--foreground") return " oklch(0.141 0.005 285.823) ";
        if (prop === "--border") return " oklch(0.92 0.004 286.32) ";
        return "";
      },
    })) as unknown as typeof window.getComputedStyle;

    const colors = resolveThemeColors();

    expect(colors.text).toBe(
      "color-mix(in oklch, oklch(0.141 0.005 285.823) 85%, transparent)",
    );
    expect(colors.gridLine).toBe(
      "color-mix(in oklch, oklch(0.92 0.004 286.32) 40%, transparent)",
    );
  });

  it("falls back to opinionated defaults when the CSS variables are unset", () => {
    window.getComputedStyle = vi.fn().mockImplementation(() => ({
      getPropertyValue: () => "",
    })) as unknown as typeof window.getComputedStyle;

    const colors = resolveThemeColors();

    expect(colors.text).toContain("color-mix(in oklch,");
    expect(colors.text).toContain("85%");
    expect(colors.gridLine).toContain("color-mix(in oklch,");
    expect(colors.gridLine).toContain("40%");
  });
});
