import { afterEach, beforeEach, describe, expect, it } from "vitest";

import {
  SERIES_FALLBACK,
  SERIES_STATIC_FALLBACKS,
  getSeriesPalette,
  seriesColor,
} from "../chart";

const setVar = (name: string, value: string) => {
  document.documentElement.style.setProperty(name, value);
};

const clearVar = (name: string) => {
  document.documentElement.style.removeProperty(name);
};

describe("series palette helpers", () => {
  beforeEach(() => {
    document.documentElement.classList.remove("dark");
    document.documentElement.removeAttribute("data-palette");
  });

  afterEach(() => {
    for (let i = 1; i <= 8; i++) clearVar(`--series-${i}`);
    document.documentElement.classList.remove("dark");
    document.documentElement.removeAttribute("data-palette");
  });

  it("returns 8 colors that fall back to the static light palette when CSS vars are unset", () => {
    const palette = getSeriesPalette();
    expect(palette).toHaveLength(8);
    expect(palette[0]).toBe(SERIES_FALLBACK[0]);
  });

  it("resolves CSS variables when present and converts them to rgb()", () => {
    setVar("--series-1", "10 20 30");
    setVar("--series-2", "40 50 60");
    const palette = getSeriesPalette();
    expect(palette[0]).toBe("rgb(10 20 30)");
    expect(palette[1]).toBe("rgb(40 50 60)");
  });

  it("uses dark fallbacks when the .dark class is present and CSS vars are absent", () => {
    document.documentElement.classList.add("dark");
    const palette = getSeriesPalette();
    // Dark fallback for slot 0 is #60A5FA (blue-400). It should NOT match the
    // light fallback (#2563EB).
    expect(palette[0]).not.toBe(SERIES_FALLBACK[0]);
    expect(palette[0]).toBe("#60A5FA");
  });

  it("uses Okabe-Ito CB fallbacks when [data-palette='cb'] is set", () => {
    document.documentElement.setAttribute("data-palette", "cb");
    const palette = getSeriesPalette();
    expect(palette[0]).toBe("#0072B2"); // CB blue
    expect(palette[2]).toBe("#009E73"); // CB bluish-green
  });

  it("seriesColor() wraps modulo 8 and never returns undefined", () => {
    expect(seriesColor(0)).toBeTruthy();
    expect(seriesColor(8)).toBe(seriesColor(0));
    expect(seriesColor(-1)).toBe(seriesColor(7));
    expect(seriesColor(17)).toBe(seriesColor(1));
  });

  it("exports a static fallback array for SSR / pre-mount usage", () => {
    expect(SERIES_STATIC_FALLBACKS).toHaveLength(8);
    expect(SERIES_STATIC_FALLBACKS[0]).toMatch(/^#[0-9A-F]{6}$/i);
  });
});
