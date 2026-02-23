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

export function computeSMA(closes: number[], period: number): number[] {
  const result: number[] = [];
  let sum = 0;
  for (let i = 0; i < closes.length; i++) {
    sum += closes[i];
    if (i >= period) sum -= closes[i - period];
    if (i >= period - 1) result.push(sum / period);
    else result.push(NaN);
  }
  return result;
}

interface WeeklyBar {
  close: number;
  high: number;
  low: number;
  volume: number;
}

function resampleWeekly(bars: OHLCBar[]): WeeklyBar[] {
  if (bars.length === 0) return [];
  const weeks: WeeklyBar[] = [];
  let wk: WeeklyBar | null = null;
  let prevWeekNum = -1;

  for (const b of bars) {
    const d = new Date(b.time * 1000);
    const dayOfYear = Math.floor((d.getTime() - new Date(d.getFullYear(), 0, 1).getTime()) / 86400000);
    const weekNum = d.getFullYear() * 100 + Math.floor(dayOfYear / 7);

    if (weekNum !== prevWeekNum) {
      if (wk) weeks.push(wk);
      wk = { close: b.close, high: b.high, low: b.low, volume: 0 };
      prevWeekNum = weekNum;
    } else if (wk) {
      wk.close = b.close;
      wk.high = Math.max(wk.high, b.high);
      wk.low = Math.min(wk.low, b.low);
    }
  }
  if (wk) weeks.push(wk);
  return weeks;
}

export interface StageInfo {
  stage: string;
  distFromMA30Pct: number;
  sataScore: number;
}

export function computeWeinsteinStage(bars: OHLCBar[]): StageInfo {
  const weekly = resampleWeekly(bars);
  if (weekly.length < 30) return { stage: '?', distFromMA30Pct: 0, sataScore: 0 };

  const closes = weekly.map(w => w.close);
  const ma30 = computeSMA(closes, 30);

  const lastIdx = weekly.length - 1;
  const currentMA30 = ma30[lastIdx - 30 + 30]; // aligned
  const prevMA30 = lastIdx >= 1 ? ma30[lastIdx - 1] : currentMA30;
  const wClose = weekly[lastIdx].close;

  if (isNaN(currentMA30) || isNaN(prevMA30)) return { stage: '?', distFromMA30Pct: 0, sataScore: 0 };

  const slopePct = (currentMA30 / prevMA30 - 1) * 100;
  const distPct = (wClose / currentMA30 - 1) * 100;

  let stage = '?';
  if (slopePct > 0.05 && distPct > 0) {
    stage = distPct <= 5 ? '2A' : distPct <= 15 ? '2B' : '2C';
  } else if (slopePct < -0.05 && distPct < 0) {
    stage = '4';
  } else if (Math.abs(slopePct) <= 0.05 && Math.abs(distPct) <= 5) {
    stage = '1';
  } else {
    stage = '3';
  }

  // SATA Score (simplified -- 10 components)
  let sata = 0;
  const ma10 = computeSMA(closes, 10);
  const currentMA10 = ma10[lastIdx];

  const highs52 = weekly.slice(Math.max(0, lastIdx - 52), lastIdx).map(w => w.high);
  const lows52 = weekly.slice(Math.max(0, lastIdx - 52), lastIdx + 1).map(w => w.low);
  const prevHigh52 = highs52.length ? Math.max(...highs52) : 0;
  const low52 = lows52.length ? Math.min(...lows52) : 0;
  const range = prevHigh52 - low52;

  // 1. Breakout above 52w high
  if (wClose > prevHigh52) sata++;
  // 2. Price > MA30
  if (wClose > currentMA30) sata++;
  // 3. MA30 rising
  if (currentMA30 > prevMA30) sata++;
  // 4. MA10 > MA30
  if (!isNaN(currentMA10) && currentMA10 > currentMA30) sata++;
  // 5. Price > MA10
  if (!isNaN(currentMA10) && wClose > currentMA10) sata++;
  // 6. Skip RS (needs benchmark data)
  // 7. RSI > 50 (simplified from closes)
  const rsi = computeRSI(closes, 14);
  if (rsi > 50) sata++;
  // 8-9. Skip MACD/OBV (complex)
  // 10. Top quintile of 52w range
  if (range > 0 && (wClose - low52) / range > 0.8) sata++;

  return { stage, distFromMA30Pct: distPct, sataScore: sata };
}

function computeRSI(closes: number[], period: number): number {
  if (closes.length < period + 1) return 50;
  let gains = 0;
  let losses = 0;
  for (let i = closes.length - period; i < closes.length; i++) {
    const diff = closes[i] - closes[i - 1];
    if (diff > 0) gains += diff;
    else losses -= diff;
  }
  if (losses === 0) return 100;
  const rs = gains / losses;
  return 100 - 100 / (1 + rs);
}
