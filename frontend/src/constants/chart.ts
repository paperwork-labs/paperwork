/**
 * Shared chart and indicator color constants — single source of truth.
 *
 * Hex colors use [light, dark] tuples so chart components can pick the
 * right value based on the current color mode.
 */

/* ─── Stage colors ─── */

/** Chakra palette names for StageBadge / StageBar. */
export const STAGE_COLORS: Record<string, string> = {
  '1': 'gray',
  '2A': 'green',
  '2B': 'green',
  '2C': 'yellow',
  '3': 'orange',
  '4': 'red',
};

/** Hex values for charts / SVGs. Index 0 = light, 1 = dark. */
export const STAGE_HEX: Record<string, [string, string]> = {
  '1':  ['#718096', '#A0AEC0'],
  '2A': ['#38A169', '#48BB78'],
  '2B': ['#2F855A', '#68D391'],
  '2C': ['#D69E2E', '#ECC94B'],
  '3':  ['#DD6B20', '#ED8936'],
  '4':  ['#E53E3E', '#FC8181'],
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

export const HEAT_MAP_COLORS = {
  strong_positive: '#16A34A',
  positive:        '#4ADE80',
  neutral:         '#94A3B8',
  negative:        '#F87171',
  strong_negative: '#DC2626',
};

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
