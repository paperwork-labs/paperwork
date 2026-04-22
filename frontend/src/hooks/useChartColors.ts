import React from 'react';
import { cssVarToCanvasColor } from '../lib/chartColors';
import { useColorMode } from '../theme/colorMode';

/**
 * Fallback hex values [light, dark] for chart colors.
 * These match the --chart-* tokens in index.css.
 */
const CHART_FALLBACKS: Record<string, [string, string]> = {
  'chart-danger': ['#DC2626', '#F87171'],
  'chart-success': ['#16A34A', '#4ADE80'],
  'chart-neutral': ['#3B82F6', '#60A5FA'],
  'chart-area1': ['#16A34A', '#34D399'],
  'chart-area2': ['#2563EB', '#60A5FA'],
  'chart-grid': ['rgba(15,23,42,0.06)', 'rgba(255,255,255,0.05)'],
  'chart-axis': ['rgba(15,23,42,0.35)', 'rgba(255,255,255,0.4)'],
  'chart-refLine': ['rgba(15,23,42,0.15)', 'rgba(255,255,255,0.15)'],
  'chart-warning': ['#D97706', '#FBBF24'],
  'fg-muted': ['#64748B', '#94A3B8'],
  'fg-subtle': ['#94A3B8', '#64748B'],
  'border-subtle': ['#E2E8F0', '#334155'],
  'primary': ['#F59E0B', '#FBBF24'], // amber
};

export interface ChartColors {
  danger: string;
  success: string;
  neutral: string;
  area1: string;
  area2: string;
  grid: string;
  axis: string;
  refLine: string;
  muted: string;
  subtle: string;
  border: string;
  brand500: string;
  brand400: string;
  brand700: string;
  warning: string;
  tooltipBg: string;
  tooltipBorder: string;
}

/**
 * Resolves chart semantic tokens for Recharts/D3 (theme-aware).
 * Uses --chart-* CSS variables from index.css with hex fallbacks.
 *
 * All values are normalized via cssVarToCanvasColor so lightweight-charts
 * (canvas 2D) receives comma-separated rgb/rgba — space-separated rgb()
 * from raw tokens is not reliably parsed by the library.
 */
export function useChartColors(): ChartColors {
  const { colorMode } = useColorMode();
  const isDark = colorMode === 'dark';
  
  return React.useMemo(() => {
    const root = typeof document !== 'undefined' ? document.documentElement : null;

    const token = (cssVarSuffix: string, fallbackKey: string) => {
      const fb = CHART_FALLBACKS[fallbackKey];
      const fallback = fb ? (isDark ? fb[1] : fb[0]) : '#888888';
      if (!root) return fallback;
      return cssVarToCanvasColor(`--${cssVarSuffix}`, fallback);
    };

    return {
      danger: token('chart-danger', 'chart-danger'),
      success: token('chart-success', 'chart-success'),
      neutral: token('chart-neutral', 'chart-neutral'),
      area1: token('chart-area1', 'chart-area1'),
      area2: token('chart-area2', 'chart-area2'),
      grid: token('chart-grid', 'chart-grid'),
      axis: token('chart-axis', 'chart-axis'),
      refLine: token('chart-refLine', 'chart-refLine'),
      muted: token('fg-muted', 'fg-muted'),
      subtle: token('fg-subtle', 'fg-subtle'),
      border: token('border-subtle', 'border-subtle'),
      brand500: token('primary', 'primary'),
      brand400: token('primary', 'primary'),
      brand700: token('primary', 'primary'),
      warning: token('chart-warning', 'chart-warning'),
      tooltipBg: isDark ? '#1E293B' : 'white',
      tooltipBorder: isDark ? 'rgba(255,255,255,0.12)' : 'rgba(15,23,42,0.12)',
    };
  }, [isDark]);
}
