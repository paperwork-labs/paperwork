import type { OHLCBar } from './trendLines';

export interface EMAResult {
  time: number;
  value: number;
}

export function computeEMA(bars: OHLCBar[], period: number): EMAResult[] {
  if (bars.length === 0) return [];
  const k = 2 / (period + 1);
  const result: EMAResult[] = [];

  let sum = 0;
  for (let i = 0; i < Math.min(period, bars.length); i++) {
    sum += bars[i].close;
  }
  let prev = sum / Math.min(period, bars.length);
  if (bars.length >= period) {
    result.push({ time: bars[period - 1].time, value: prev });
  }

  for (let i = period; i < bars.length; i++) {
    prev = bars[i].close * k + prev * (1 - k);
    result.push({ time: bars[i].time, value: prev });
  }

  return result;
}
