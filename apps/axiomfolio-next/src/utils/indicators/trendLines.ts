export interface OHLCBar {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
}

export interface TrendLine {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  direction: 'up' | 'down';
  channelX1?: number;
  channelY1?: number;
  channelX2?: number;
  channelY2?: number;
}

function computeATR(bars: OHLCBar[], period = 14): number[] {
  const atr: number[] = new Array(bars.length).fill(0);
  if (bars.length < 2) return atr;
  for (let i = 1; i < bars.length; i++) {
    const tr = Math.max(
      bars[i].high - bars[i].low,
      Math.abs(bars[i].high - bars[i - 1].close),
      Math.abs(bars[i].low - bars[i - 1].close),
    );
    if (i < period) {
      atr[i] = (atr[i - 1] * (i - 1) + tr) / i;
    } else {
      atr[i] = (atr[i - 1] * (period - 1) + tr) / period;
    }
  }
  return atr;
}

function findPivots(
  bars: OHLCBar[],
  period: number,
): { highs: { idx: number; val: number }[]; lows: { idx: number; val: number }[] } {
  const highs: { idx: number; val: number }[] = [];
  const lows: { idx: number; val: number }[] = [];

  for (let i = period; i < bars.length - period; i++) {
    let isHigh = true;
    let isLow = true;
    for (let j = 1; j <= period; j++) {
      if (bars[i].high <= bars[i - j].high || bars[i].high <= bars[i + j].high) isHigh = false;
      if (bars[i].low >= bars[i - j].low || bars[i].low >= bars[i + j].low) isLow = false;
      if (!isHigh && !isLow) break;
    }
    if (isHigh) highs.push({ idx: i, val: bars[i].high });
    if (isLow) lows.push({ idx: i, val: bars[i].low });
  }
  return { highs, lows };
}

/**
 * Compute the parallel channel offset for a trend line. For uptrend lines
 * (connecting lows), the channel is the max high deviation above the line.
 * For downtrend lines (connecting highs), it's the max low deviation below.
 */
function computeChannelOffset(
  bars: OHLCBar[],
  p2Idx: number,
  p2Val: number,
  slope: number,
  direction: 'up' | 'down',
  endIdx: number,
): number {
  let maxDeviation = 0;
  for (let k = p2Idx; k <= endIdx; k++) {
    const expected = p2Val + slope * (k - p2Idx);
    const deviation = direction === 'up'
      ? bars[k].high - expected
      : expected - bars[k].low;
    if (deviation > maxDeviation) maxDeviation = deviation;
  }
  return maxDeviation;
}

export function detectTrendLines(
  bars: OHLCBar[],
  pivotPeriod = 20,
  maxLines = 3,
): TrendLine[] {
  if (bars.length < pivotPeriod * 2 + 1) return [];

  const { highs, lows } = findPivots(bars, pivotPeriod);
  const atr = computeATR(bars);
  const lines: TrendLine[] = [];
  const validationLimit = Math.min(bars.length - 1, 100);

  // Uptrend lines from ascending pivot lows (most recent first)
  const sortedLows = [...lows].reverse().slice(0, 10);
  let upCount = 0;
  for (let i = 0; i < sortedLows.length - 1 && upCount < maxLines; i++) {
    const p1 = sortedLows[i];
    for (let j = i + 1; j < Math.min(sortedLows.length, i + 6); j++) {
      const p2 = sortedLows[j];
      if (p1.val <= p2.val) continue;
      const slope = (p1.val - p2.val) / (p1.idx - p2.idx);
      let valid = true;
      const tolerance = (atr[p1.idx] || atr[bars.length - 1] || 0) * 0.1;
      const checkEnd = Math.min(p1.idx + validationLimit, bars.length - 1);
      for (let k = p2.idx; k <= checkEnd; k++) {
        const expected = p2.val + slope * (k - p2.idx);
        if (bars[k].low < expected - tolerance) { valid = false; break; }
      }
      if (valid) {
        const endIdx = bars.length - 1;
        const endY = p2.val + slope * (endIdx - p2.idx);
        const offset = computeChannelOffset(bars, p2.idx, p2.val, slope, 'up', endIdx);
        lines.push({
          x1: bars[p2.idx].time,
          y1: p2.val,
          x2: bars[endIdx].time,
          y2: endY,
          direction: 'up',
          channelX1: bars[p2.idx].time,
          channelY1: p2.val + offset,
          channelX2: bars[endIdx].time,
          channelY2: endY + offset,
        });
        upCount++;
        break;
      }
    }
  }

  // Downtrend lines from descending pivot highs
  const sortedHighs = [...highs].reverse().slice(0, 10);
  let downCount = 0;
  for (let i = 0; i < sortedHighs.length - 1 && downCount < maxLines; i++) {
    const p1 = sortedHighs[i];
    for (let j = i + 1; j < Math.min(sortedHighs.length, i + 6); j++) {
      const p2 = sortedHighs[j];
      if (p1.val >= p2.val) continue;
      const slope = (p1.val - p2.val) / (p1.idx - p2.idx);
      let valid = true;
      const tolerance = (atr[p1.idx] || atr[bars.length - 1] || 0) * 0.1;
      const checkEnd = Math.min(p1.idx + validationLimit, bars.length - 1);
      for (let k = p2.idx; k <= checkEnd; k++) {
        const expected = p2.val + slope * (k - p2.idx);
        if (bars[k].high > expected + tolerance) { valid = false; break; }
      }
      if (valid) {
        const endIdx = bars.length - 1;
        const endY = p2.val + slope * (endIdx - p2.idx);
        const offset = computeChannelOffset(bars, p2.idx, p2.val, slope, 'down', endIdx);
        lines.push({
          x1: bars[p2.idx].time,
          y1: p2.val,
          x2: bars[endIdx].time,
          y2: endY,
          direction: 'down',
          channelX1: bars[p2.idx].time,
          channelY1: p2.val - offset,
          channelX2: bars[endIdx].time,
          channelY2: endY - offset,
        });
        downCount++;
        break;
      }
    }
  }

  return lines;
}

export interface SRLevel {
  price: number;
  strength: number;
  type: 'support' | 'resistance';
}

export function detectSupportResistance(
  bars: OHLCBar[],
  pivotPeriod = 10,
  maxLevels = 4,
  clusterATRMultiplier = 0.75,
): SRLevel[] {
  if (bars.length < pivotPeriod * 2 + 1) return [];

  const { highs, lows } = findPivots(bars, pivotPeriod);
  const atr = computeATR(bars);
  const lastATR = atr[bars.length - 1] || 1;
  const clusterDist = lastATR * clusterATRMultiplier;
  const currentPrice = bars[bars.length - 1].close;

  const allPivots = [
    ...highs.map(p => ({ val: p.val, kind: 'high' as const })),
    ...lows.map(p => ({ val: p.val, kind: 'low' as const })),
  ].sort((a, b) => a.val - b.val);

  const zones: { price: number; touches: number; kind: 'support' | 'resistance' }[] = [];

  for (const pivot of allPivots) {
    const existing = zones.find(z => Math.abs(z.price - pivot.val) <= clusterDist);
    if (existing) {
      existing.price = (existing.price * existing.touches + pivot.val) / (existing.touches + 1);
      existing.touches++;
    } else {
      zones.push({
        price: pivot.val,
        touches: 1,
        kind: pivot.val < currentPrice ? 'support' : 'resistance',
      });
    }
  }

  return zones
    .filter(z => z.touches >= 2)
    .sort((a, b) => b.touches - a.touches)
    .slice(0, maxLevels)
    .map(z => ({
      price: z.price,
      strength: z.touches,
      type: z.price < currentPrice ? 'support' : 'resistance',
    }));
}
