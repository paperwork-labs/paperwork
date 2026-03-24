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

export const HEAT_SCALE: { min: number; chakra: string }[] = [
  { min:  3,         chakra: 'green.600' },
  { min:  1,         chakra: 'green.500' },
  { min:  0,         chakra: 'green.400' },
  { min: -1,         chakra: 'red.400' },
  { min: -3,         chakra: 'red.500' },
  { min: -Infinity,  chakra: 'red.600' },
];

export function heatColor(v: unknown): string | undefined {
  if (typeof v !== 'number' || !Number.isFinite(v)) return undefined;
  for (const tier of HEAT_SCALE) {
    if (v >= tier.min) return tier.chakra;
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
  'var(--chakra-colors-brand-600)',
  'var(--chakra-colors-red-500)',
  'var(--chakra-colors-green-500)',
  'var(--chakra-colors-orange-500)',
  'var(--chakra-colors-purple-500)',
  'var(--chakra-colors-teal-500)',
  'var(--chakra-colors-pink-500)',
  'var(--chakra-colors-cyan-600)',
  'var(--chakra-colors-yellow-600)',
  'var(--chakra-colors-brand-400)',
  'var(--chakra-colors-red-400)',
  'var(--chakra-colors-green-600)',
  'var(--chakra-colors-orange-600)',
  'var(--chakra-colors-purple-400)',
] as const;

export { SECTOR_PALETTE };
