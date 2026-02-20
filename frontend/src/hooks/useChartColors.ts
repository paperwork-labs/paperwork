import React from 'react';
import { useColorMode } from '../theme/colorMode';

const CHART_FALLBACKS: Record<string, [string, string]> = {
  'chart.danger': ['#DC2626', '#F87171'],
  'chart.success': ['#16A34A', '#4ADE80'],
  'chart.neutral': ['#3B82F6', '#60A5FA'],
  'chart.area1': ['#16A34A', '#34D399'],
  'chart.area2': ['#2563EB', '#60A5FA'],
  'chart.grid': ['rgba(15,23,42,0.08)', 'rgba(255,255,255,0.08)'],
  'chart.axis': ['rgba(15,23,42,0.4)', 'rgba(255,255,255,0.45)'],
  'chart.refLine': ['rgba(15,23,42,0.2)', 'rgba(255,255,255,0.2)'],
  'chart.warning': ['#D97706', '#FBBF24'],
  'fg.muted': ['#64748B', '#94A3B8'],
  'fg.subtle': ['#94A3B8', '#64748B'],
  'border.subtle': ['#E2E8F0', '#334155'],
  'brand.500': ['#6366F1', '#818CF8'],
  'brand.400': ['#818CF8', '#A5B4FC'],
  'brand.700': ['#4338CA', '#4F46E5'],
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
}

/** Resolves chart semantic tokens for Recharts/D3 (theme-aware). */
export function useChartColors(): ChartColors {
  const { colorMode } = useColorMode();
  const isDark = colorMode === 'dark';
  return React.useMemo(() => {
    const root = typeof document !== 'undefined' ? document.documentElement : null;
    const get = (token: string) => {
      const fb = CHART_FALLBACKS[token];
      const fallback = fb ? (isDark ? fb[1] : fb[0]) : token;
      if (!root) return fallback;
      const v = getComputedStyle(root)
        .getPropertyValue(`--chakra-colors-${token.replace(/\./g, '-')}`)
        .trim();
      return v || fallback;
    };
    return {
      danger: get('chart.danger'),
      success: get('chart.success'),
      neutral: get('chart.neutral'),
      area1: get('chart.area1'),
      area2: get('chart.area2'),
      grid: get('chart.grid'),
      axis: get('chart.axis'),
      refLine: get('chart.refLine'),
      muted: get('fg.muted'),
      subtle: get('fg.subtle'),
      border: get('border.subtle'),
      brand500: get('brand.500'),
      brand400: get('brand.400'),
      brand700: get('brand.700'),
      warning: get('chart.warning'),
    };
  }, [isDark]);
}
