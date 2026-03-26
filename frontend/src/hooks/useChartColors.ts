import React from 'react';
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
 */
export function useChartColors(): ChartColors {
  const { colorMode } = useColorMode();
  const isDark = colorMode === 'dark';
  
  return React.useMemo(() => {
    const root = typeof document !== 'undefined' ? document.documentElement : null;
    
    const getRgbVar = (varName: string, fallbackKey: string) => {
      const fb = CHART_FALLBACKS[fallbackKey];
      const fallback = fb ? (isDark ? fb[1] : fb[0]) : '#888';
      if (!root) return fallback;
      
      const rgbValue = getComputedStyle(root).getPropertyValue(`--${varName}`).trim();
      if (rgbValue) {
        return `rgb(${rgbValue.replace(/\s*\/.*$/, '')})`;
      }
      return fallback;
    };
    
    return {
      danger: getRgbVar('chart-danger', 'chart-danger'),
      success: getRgbVar('chart-success', 'chart-success'),
      neutral: getRgbVar('chart-neutral', 'chart-neutral'),
      area1: getRgbVar('chart-area1', 'chart-area1'),
      area2: getRgbVar('chart-area2', 'chart-area2'),
      grid: getRgbVar('chart-grid', 'chart-grid'),
      axis: getRgbVar('chart-axis', 'chart-axis'),
      refLine: getRgbVar('chart-refLine', 'chart-refLine'),
      muted: getRgbVar('fg-muted', 'fg-muted'),
      subtle: getRgbVar('fg-subtle', 'fg-subtle'),
      border: getRgbVar('border-subtle', 'border-subtle'),
      brand500: getRgbVar('primary', 'primary'),
      brand400: getRgbVar('primary', 'primary'),
      brand700: getRgbVar('primary', 'primary'),
      warning: getRgbVar('chart-warning', 'chart-warning'),
      tooltipBg: isDark ? '#1E293B' : 'white',
      tooltipBorder: isDark ? 'rgba(255,255,255,0.12)' : 'rgba(15,23,42,0.12)',
    };
  }, [isDark]);
}
