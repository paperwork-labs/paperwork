/**
 * Shared chart and indicator color constants — single source of truth.
 *
 * Hex colors use [light, dark] tuples so chart components can pick the
 * right value based on the current color mode.
 */

/* ─── Stage colors ─── */

/** Chakra palette names for StageBadge / StageBar (10 sub-stages). */
export const STAGE_COLORS: Record<string, string> = {
  '1A': 'gray',
  '1B': 'gray',
  '2A': 'green',
  '2B': 'green',
  '2B(RS-)': 'green',
  '2C': 'yellow',
  '3A': 'orange',
  '3B': 'orange',
  '4A': 'red',
  '4B': 'red',
  '4C': 'red',
  // Legacy compat
  '1': 'gray',
  '2': 'green',
  '3': 'orange',
  '4': 'red',
};

/** Hex values for charts / SVGs. Index 0 = light, 1 = dark. */
export const STAGE_HEX: Record<string, [string, string]> = {
  '1A':      ['#A0AEC0', '#CBD5E0'],
  '1B':      ['#718096', '#A0AEC0'],
  '2A':      ['#38A169', '#48BB78'],
  '2B':      ['#2F855A', '#68D391'],
  '2B(RS-)': ['#2F855A', '#68D391'],
  '2C':      ['#D69E2E', '#ECC94B'],
  '3A':      ['#DD6B20', '#ED8936'],
  '3B':      ['#C05621', '#DD6B20'],
  '4A':      ['#E53E3E', '#FC8181'],
  '4B':      ['#C53030', '#F56565'],
  '4C':      ['#9B2C2C', '#E53E3E'],
  // Legacy compat
  '1':       ['#718096', '#A0AEC0'],
  '2':       ['#38A169', '#48BB78'],
  '3':       ['#DD6B20', '#ED8936'],
  '4':       ['#E53E3E', '#FC8181'],
};

/** Valid stage keys for the 10 sub-stages (Stage Analysis). */
export type StageKey = '1A' | '1B' | '2A' | '2B' | '2C' | '3A' | '3B' | '4A' | '4B' | '4C';

/** Regime colors (Market Regime Engine R1–R5). */
export const REGIME_HEX: Record<string, string> = {
  R1: '#22C55E',  // Bull — green
  R2: '#86EFAC',  // Bull Extended — light green
  R3: '#EAB308',  // Chop — yellow
  R4: '#F97316',  // Bear Rally — orange
  R5: '#DC2626',  // Bear — red
};

/** Action label colors. */
export const ACTION_COLORS: Record<string, string> = {
  BUY:    'green',
  HOLD:   'blue',
  WATCH:  'gray',
  REDUCE: 'orange',
  SHORT:  'red',
  AVOID:  'red',
};

/* ─── Signal colors ─── */

export const SIGNAL_HEX = {
  bullish:  ['#16A34A', '#4ADE80'] as [string, string],
  bearish:  ['#DC2626', '#F87171'] as [string, string],
  neutral:  ['#64748B', '#94A3B8'] as [string, string],
  warning:  ['#D97706', '#FBBF24'] as [string, string],
};

/* ─── TD Sequential (chart markers) ─── */

export const TD_HEX = {
  setup:     ['#CA8A04', '#EAB308'] as [string, string],
  perfect:   ['#C026D3', '#D946EF'] as [string, string],
  countdown: ['#DC2626', '#EF4444'] as [string, string],
};

/* ─── RSI reference lines ─── */

export const RSI_HEX = {
  overbought: ['rgba(220,38,38,0.3)', 'rgba(248,113,113,0.3)'] as [string, string],
  oversold:   ['rgba(22,163,74,0.3)',  'rgba(74,222,128,0.3)']  as [string, string],
};

/* ─── MACD histogram ─── */

export const MACD_HEX = {
  positive: ['#16A34A80', '#22c55e80'] as [string, string],
  negative: ['#DC262680', '#ef444480'] as [string, string],
};

/* ─── Bollinger bands ─── */

export const BOLLINGER_HEX: [string, string] = ['#4F46E580', '#818CF880'];

/* ─── Heat scale (momentum, RS, performance %) ─── */

export const HEAT_SCALE: { min: number; class: string; hex: string }[] = [
  { min:  3,         class: 'text-green-600', hex: '#16A34A' },
  { min:  1,         class: 'text-green-500', hex: '#22C55E' },
  { min:  0,         class: 'text-green-400', hex: '#4ADE80' },
  { min: -1,         class: 'text-red-400',   hex: '#F87171' },
  { min: -3,         class: 'text-red-500',   hex: '#EF4444' },
  { min: -Infinity,  class: 'text-red-600',   hex: '#DC2626' },
];

export function heatColor(v: unknown): string | undefined {
  if (typeof v !== 'number' || !Number.isFinite(v)) return undefined;
  for (const tier of HEAT_SCALE) {
    if (v >= tier.min) return tier.class;
  }
  return undefined;
}

export function heatColorHex(v: unknown): string | undefined {
  if (typeof v !== 'number' || !Number.isFinite(v)) return undefined;
  for (const tier of HEAT_SCALE) {
    if (v >= tier.min) return tier.hex;
  }
  return undefined;
}

/* ─── Heat map (FinvizHeatMap treemap) ─── */

export const HEAT_MAP_STOPS: { pct: number; hex: string }[] = [
  { pct: -4, hex: '#7F1D1D' },
  { pct: -3, hex: '#991B1B' },
  { pct: -2, hex: '#DC2626' },
  { pct: -1, hex: '#EF4444' },
  { pct:  0, hex: '#475569' },
  { pct:  1, hex: '#4ADE80' },
  { pct:  2, hex: '#22C55E' },
  { pct:  3, hex: '#16A34A' },
  { pct:  4, hex: '#15803D' },
];

function lerpHex(a: string, b: string, t: number): string {
  const parse = (h: string) => [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16)];
  const [r1, g1, b1] = parse(a);
  const [r2, g2, b2] = parse(b);
  const c = (v1: number, v2: number) => Math.round(v1 + (v2 - v1) * t).toString(16).padStart(2, '0');
  return `#${c(r1, r2)}${c(g1, g2)}${c(b1, b2)}`;
}

export function heatMapColor(pct: number): string {
  if (pct <= HEAT_MAP_STOPS[0].pct) return HEAT_MAP_STOPS[0].hex;
  for (let i = 1; i < HEAT_MAP_STOPS.length; i++) {
    if (pct <= HEAT_MAP_STOPS[i].pct) {
      const lo = HEAT_MAP_STOPS[i - 1];
      const hi = HEAT_MAP_STOPS[i];
      const t = (pct - lo.pct) / (hi.pct - lo.pct);
      return lerpHex(lo.hex, hi.hex, t);
    }
  }
  return HEAT_MAP_STOPS[HEAT_MAP_STOPS.length - 1].hex;
}

export const HEAT_MAP_LEGEND = [
  { label: '<-3%', hex: '#991B1B' },
  { label: '-2%',  hex: '#DC2626' },
  { label: '-1%',  hex: '#EF4444' },
  { label: '0%',   hex: '#475569' },
  { label: '+1%',  hex: '#4ADE80' },
  { label: '+2%',  hex: '#22C55E' },
  { label: '>+3%', hex: '#16A34A' },
];

/* ─── Sector / allocation palette ─── */

const SECTOR_PALETTE = [
  '#2563EB', // blue-600 (primary/brand)
  '#EF4444', // red-500
  '#22C55E', // green-500
  '#F97316', // orange-500
  '#A855F7', // purple-500
  '#14B8A6', // teal-500
  '#EC4899', // pink-500
  '#0891B2', // cyan-600
  '#CA8A04', // yellow-600
  '#60A5FA', // blue-400
  '#F87171', // red-400
  '#16A34A', // green-600
  '#EA580C', // orange-600
  '#C084FC', // purple-400
] as const;

export { SECTOR_PALETTE };

/* ─── Series palette (HSL-derived, theme- and CB-aware) ─────────────────────
 *
 * The 8 series colors are defined in `index.css` as `--series-1` through
 * `--series-8`. Components should resolve them at runtime via this helper so
 * that:
 *   - Light / dark mode swaps automatically (different luminance per theme).
 *   - Color-blind users opting in via `[data-palette="cb"]` see the
 *     Okabe-Ito 2008 palette (provably distinguishable for protan/deutan).
 *   - Hex fallbacks render correctly during SSR or the brief moment before
 *     CSS variables resolve (Recharts in particular reads colors eagerly).
 *
 * Use:
 *   const colors = getSeriesPalette();              // theme-aware, 8 entries
 *   const oneColor = seriesColor(idx);              // safe modulo, single color
 */

const SERIES_FALLBACK_LIGHT = [
  '#2563EB', '#16A34A', '#D97706', '#A855F7',
  '#0EA5E9', '#EC4899', '#14B8A6', '#EA580C',
] as const;

const SERIES_FALLBACK_DARK = [
  '#60A5FA', '#4ADE80', '#FBBF24', '#C084FC',
  '#38BDF8', '#F472B6', '#2DD4BF', '#FB923C',
] as const;

const SERIES_CB_LIGHT = [
  '#0072B2', '#D55E00', '#009E73', '#F0E442',
  '#56B4E9', '#E69F00', '#CC79A7', '#000000',
] as const;

const SERIES_CB_DARK = [
  '#4F9CD7', '#F58231', '#40BC9E', '#F5E95F',
  '#86C5EB', '#F0AE26', '#DC90B8', '#E0E0E0',
] as const;

export const SERIES_FALLBACK = SERIES_FALLBACK_LIGHT;

export type PaletteVariant = 'default' | 'cb';

interface PaletteContext {
  isDark: boolean;
  variant: PaletteVariant;
}

function detectPaletteContext(): PaletteContext {
  if (typeof document === 'undefined') {
    return { isDark: false, variant: 'default' };
  }
  const root = document.documentElement;
  const isDark = root.classList.contains('dark');
  const variant: PaletteVariant = root.getAttribute('data-palette') === 'cb' ? 'cb' : 'default';
  return { isDark, variant };
}

function fallbackPalette({ isDark, variant }: PaletteContext): readonly string[] {
  if (variant === 'cb') return isDark ? SERIES_CB_DARK : SERIES_CB_LIGHT;
  return isDark ? SERIES_FALLBACK_DARK : SERIES_FALLBACK_LIGHT;
}

/**
 * Returns the 8-entry series palette, theme- and CB-aware. Resolves the
 * `--series-N` CSS variables when running in a browser; falls back to the
 * matching hex constants during SSR or if the variable is unset (e.g., before
 * the stylesheet has loaded).
 */
export function getSeriesPalette(): string[] {
  const ctx = detectPaletteContext();
  const fallbacks = fallbackPalette(ctx);

  if (typeof document === 'undefined') {
    return [...fallbacks];
  }
  const styles = getComputedStyle(document.documentElement);
  return Array.from({ length: 8 }, (_, i) => {
    const raw = styles.getPropertyValue(`--series-${i + 1}`).trim();
    return raw ? `rgb(${raw.replace(/\s*\/.*$/, '')})` : fallbacks[i];
  });
}

/**
 * Returns a single series color for a given index (modulo 8). Useful when
 * iterating over an unknown number of series and you want stable color
 * assignment.
 */
export function seriesColor(index: number): string {
  const palette = getSeriesPalette();
  if (palette.length === 0) return SERIES_FALLBACK_LIGHT[0];
  const i = ((index % palette.length) + palette.length) % palette.length;
  return palette[i];
}

/**
 * For SSR or pre-mount usage (e.g., Recharts default fills), use these static
 * fallbacks. They match the light-theme default-palette CSS variables.
 */
export const SERIES_STATIC_FALLBACKS = SERIES_FALLBACK_LIGHT;
