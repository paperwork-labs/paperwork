/**
 * Canvas-safe color resolution for chart libraries (lightweight-charts v5,
 * TradingView widget, etc.) that hand colors directly to a canvas 2D context
 * and do NOT accept `oklch(...)` or `color-mix(...)`.
 *
 * Why this exists:
 *   Our design tokens resolve to `oklch(...)` values (e.g. `--foreground` is
 *   `oklch(0.141 0.005 285.823)`). When we pass those straight into
 *   `createChart({ layout: { textColor: ... } })`, lightweight-charts calls
 *   its internal color parser and throws:
 *     "Failed to parse color: oklch(98.5% 0 0)"
 *   which bubbles to an error boundary and bricks the symbol workspace.
 *
 *   DOM probe: setting any valid CSS color on an element and reading it back
 *   via `getComputedStyle(el).color` yields the browser-normalized `rgb(...)`
 *   / `rgba(...)` string regardless of input format (oklch, color-mix, hex,
 *   named). That normalized string is something every canvas parser accepts.
 */

function isAlreadyCanvasSafe(v: string): boolean {
  // Only 3/4/6/8 hex digit forms are valid; e.g. #12345 (5) must not pass through.
  return (
    /^#(?:[0-9a-f]{3,4}|[0-9a-f]{6}|[0-9a-f]{8})$/i.test(v) ||
    /^rgba?\(/i.test(v) ||
    /^hsla?\(/i.test(v) ||
    v === "transparent"
  );
}

/**
 * Normalize `input` to a string lightweight-charts/canvas can parse.
 * Returns `fallback` unchanged if the browser rejects `input` or we're not
 * in a DOM environment (SSR / unit tests without jsdom).
 */
export function canvasSafeColor(input: string, fallback: string): string {
  const src = (input || "").trim();
  if (!src) return fallback;
  if (isAlreadyCanvasSafe(src)) return src;
  if (typeof document === "undefined" || !document.body) return fallback;

  const probe = document.createElement("div");
  probe.style.display = "none";
  document.body.appendChild(probe);
  try {
    probe.style.color = "";
    probe.style.color = src;
    if (probe.style.color === "") {
      return fallback;
    }
    const resolved = getComputedStyle(probe).color;
    return resolved && /^rgba?\(/i.test(resolved) ? resolved : fallback;
  } finally {
    probe.remove();
  }
}

/**
 * Read a CSS custom property off `:root` and return a canvas-safe color.
 *
 * Supports two common token shapes in our stack:
 *   - space-separated RGB triples (`248 250 252`), optionally with `/ alpha`
 *     — wrapped into `rgb(...)` / `rgba(...)`.
 *   - anything else (hex, `oklch(...)`, `color-mix(...)`, named) — resolved
 *     via DOM probe to `rgb(...)`.
 */
export function cssVarToCanvasColor(
  cssVarName: string,
  fallback: string,
): string {
  if (typeof document === 'undefined') return fallback;
  const raw = getComputedStyle(document.documentElement)
    .getPropertyValue(cssVarName)
    .trim();
  if (!raw) return fallback;
  if (/^\d/.test(raw)) {
    // space-separated triples: "248 250 252" or "0 0 0 / 0.5"
    // Normalize to the comma-separated legacy form that every canvas parser
    // (including lightweight-charts v5's) understands.
    const [rgbPart, alphaPart] = raw.split('/').map((s) => s.trim());
    const nums = rgbPart.split(/\s+/).filter(Boolean);
    if (nums.length === 3) {
      return alphaPart
        ? `rgba(${nums.join(', ')}, ${alphaPart})`
        : `rgb(${nums.join(', ')})`;
    }
    return fallback;
  }
  return canvasSafeColor(raw, fallback);
}
