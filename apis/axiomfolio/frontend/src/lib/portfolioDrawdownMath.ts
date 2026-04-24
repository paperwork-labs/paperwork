/**
 * Drawdown math for portfolio equity series (total value over time).
 * DD% = (equity - running_max) / running_max (negative when underwater).
 */

export interface DrawdownPoint {
  timeUtc: number;
  /** Fractional drawdown (e.g. -0.136 for -13.6%). */
  drawdown: number;
}

export interface DrawdownStats {
  /** Most negative drawdown in the window (≤ 0). */
  maxDrawdown: number;
  /** Drawdown at the last point vs running max of the full series. */
  currentDrawdown: number;
  points: DrawdownPoint[];
}

/**
 * @param totalValues — strictly positive portfolio values in chronological order.
 */
export function computeDrawdownUnderwaterSeries(
  timesUtc: readonly number[],
  totalValues: readonly number[],
): DrawdownStats {
  if (timesUtc.length !== totalValues.length || timesUtc.length === 0) {
    return { maxDrawdown: 0, currentDrawdown: 0, points: [] };
  }

  let runningMax = 0;
  let maxDd = 0;
  const points: DrawdownPoint[] = [];

  for (let i = 0; i < totalValues.length; i++) {
    const v = totalValues[i];
    const t = timesUtc[i];
    if (!Number.isFinite(v) || !Number.isFinite(t) || v <= 0) {
      points.push({ timeUtc: t, drawdown: 0 });
      continue;
    }
    if (v > runningMax) runningMax = v;
    const peak = runningMax;
    const dd = peak > 0 ? (v - peak) / peak : 0;
    if (dd < maxDd) maxDd = dd;
    points.push({ timeUtc: t, drawdown: dd });
  }

  const currentDd = points.length > 0 ? points[points.length - 1].drawdown : 0;
  return { maxDrawdown: maxDd, currentDrawdown: currentDd, points };
}

/** For unit tests: max drawdown over a value path (percent change from running peak). */
export function maxDrawdownFromPath(values: readonly number[]): number {
  const stats = computeDrawdownUnderwaterSeries(
    values.map((_, i) => i),
    values,
  );
  return stats.maxDrawdown;
}
