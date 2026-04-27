/**
 * `themeColors` — runtime helpers that turn our CSS design tokens into
 * concrete color strings safe to hand to lightweight-charts (or any other
 * canvas-based renderer that won't itself resolve `var(--…)`).
 *
 * Why this exists:
 *   - Our design tokens (`--foreground`, `--border`) are stored as
 *     `oklch(...)` values, NOT space-separated RGB triples. Wrapping them
 *     with `rgb(var(--foreground) / 0.85)` produces invalid CSS like
 *     `rgb(oklch(0.141 0.005 285.823) / 0.85)`. Browsers tolerate the bad
 *     string by dropping the property; lightweight-charts then silently
 *     falls back to its default colors and the chart looks broken on
 *     dark mode.
 *   - The series palette (`seriesColor(0)`) returns either a hex string
 *     OR an `rgb(...)` string depending on which CSS vars are wired up.
 *     The previous "concat hex alpha" trick (`${color}2E`) is a no-op for
 *     `rgb(...)` strings; `color-mix` works for both, in any color space.
 *
 * Both helpers are SSR-safe (return sensible fallbacks when `document`
 * is undefined) and avoid touching the chart library directly so they
 * stay trivially unit-testable without a JSDOM crutch.
 */

import { canvasSafeColor } from "@/lib/chartColors";

/** Hard fallbacks used when running outside a browser (SSR / unit tests). */
const FALLBACK_TEXT = "rgba(15, 23, 42, 0.85)";
const FALLBACK_GRID = "rgba(15, 23, 42, 0.08)";
const FALLBACK_FOREGROUND = "oklch(0.141 0.005 285.823)";
const FALLBACK_BORDER = "oklch(0.92 0.004 286.32)";

export interface ChartThemeColors {
  /** Resolved color for chart axis / value labels. */
  text: string;
  /** Resolved color for vertical & horizontal grid lines. */
  gridLine: string;
}

/**
 * Apply a 0–1 alpha to an arbitrary CSS color by composing with
 * `color-mix(in oklch, …)`, then normalizing to a canvas-parseable
 * `rgb` / `rgba` string (lightweight-charts v5 rejects raw `color-mix`).
 * Works uniformly for `#rrggbb`, `rgb(r g b)`, `oklch(…)`, and named
 * colors in modern browsers; when the mix cannot be resolved, returns a
 * neutral grey with the requested alpha.
 */
export function withAlpha(color: string, alpha: number): string {
  const clamped = Math.min(1, Math.max(0, alpha));
  if (clamped === 0) return "transparent";
  const pct = Math.round(clamped * 100);
  const mix = `color-mix(in oklch, ${color} ${pct}%, transparent)`;
  return canvasSafeColor(
    mix,
    `rgba(128, 128, 128, ${clamped})`,
  );
}

/**
 * Read the current theme's `--foreground` and `--border` values and wrap
 * them in `color-mix(...)` to apply the chart-axis / grid-line alphas.
 *
 * Returning the resolved strings (not the raw `var(...)` references) is
 * deliberate: lightweight-charts paints to a canvas and never re-resolves
 * CSS variables, so we MUST hand it concrete colors.
 *
 * Caller is responsible for re-invoking this function when the theme or
 * color palette changes (subscribe to the `axiomfolio:color-palette-change`
 * event and a MutationObserver on `<html>` `class` / `data-palette`).
 */
export function resolveThemeColors(): ChartThemeColors {
  if (typeof document === "undefined") {
    return { text: FALLBACK_TEXT, gridLine: FALLBACK_GRID };
  }
  const cs = getComputedStyle(document.documentElement);
  const fg = cs.getPropertyValue("--foreground").trim() || FALLBACK_FOREGROUND;
  const border = cs.getPropertyValue("--border").trim() || FALLBACK_BORDER;
  // NOTE: must return canvas-parseable strings (rgb/rgba) — lightweight-charts
  // v5 rejects both `oklch(...)` AND `color-mix(...)`. We compose with
  // `color-mix` for correctness, then normalize via DOM probe.
  return {
    text: canvasSafeColor(
      `color-mix(in oklch, ${fg} 85%, transparent)`,
      FALLBACK_TEXT,
    ),
    gridLine: canvasSafeColor(
      `color-mix(in oklch, ${border} 40%, transparent)`,
      FALLBACK_GRID,
    ),
  };
}
