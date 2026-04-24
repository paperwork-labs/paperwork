import type { Time } from 'lightweight-charts';

function isBusinessDay(t: Time): t is { year: number; month: number; day: number } {
  return typeof t === 'object' && t !== null && 'year' in t;
}

function timeToDate(time: Time): Date | null {
  if (isBusinessDay(time)) {
    const ms = Date.UTC(time.year, time.month - 1, time.day);
    const d = new Date(ms);
    return Number.isNaN(d.getTime()) ? null : d;
  }
  if (typeof time === 'number' && Number.isFinite(time)) {
    const d = new Date(time * 1000);
    return Number.isNaN(d.getTime()) ? null : d;
  }
  return null;
}

/** X-axis tick labels: short month+day same year; month+year when range crosses years. */
export function formatLightweightTimeTick(time: Time, multiYear: boolean): string {
  const d = timeToDate(time);
  if (!d) return '';
  if (multiYear) {
    return d.toLocaleDateString(undefined, { month: 'short', year: 'numeric' });
  }
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

/** Right price scale for equity / position charts (dollars). */
export function formatLightweightPriceUsd(price: number): string {
  if (!Number.isFinite(price)) {
    return '—';
  }
  const maxFrac = price >= 100 || price <= -100 ? 0 : 2;
  return new Intl.NumberFormat(undefined, {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: maxFrac,
    minimumFractionDigits: 0,
  }).format(price);
}

/**
 * Portfolio equity chart Y-axis: percent change from first point (already in
 * display percent units, e.g. 5.25 = +5.25%).
 */
export function formatLightweightEquityPercentDisplay(value: number): string {
  if (!Number.isFinite(value)) {
    return '—';
  }
  if (Math.abs(value) < 1e-9) {
    return '0%';
  }
  const sign = value > 0 ? '+' : '';
  return `${sign}${value.toFixed(2)}%`;
}
