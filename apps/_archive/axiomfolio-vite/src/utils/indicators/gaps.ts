import type { OHLCBar } from './trendLines';

export interface GapZone {
  startTime: number;
  topPrice: number;
  bottomPrice: number;
  direction: 'up' | 'down';
  pct: number;
  filled: boolean;
  filledTime?: number;
}

export function detectGaps(
  bars: OHLCBar[],
  minGapPct = 0.005,
  hideDistancePct = 0.10,
  maxGaps = 20,
): GapZone[] {
  if (bars.length < 2) return [];

  const gaps: GapZone[] = [];
  const currentPrice = bars[bars.length - 1].close;

  for (let i = 1; i < bars.length; i++) {
    const prev = bars[i - 1];
    const cur = bars[i];

    // Gap up: current low > previous high
    if (cur.low > prev.high && (cur.low / prev.high - 1) > minGapPct) {
      const gap: GapZone = {
        startTime: cur.time,
        topPrice: cur.low,
        bottomPrice: prev.high,
        direction: 'up',
        pct: (cur.low / prev.high - 1) * 100,
        filled: false,
      };

      // Check fill forward
      for (let j = i + 1; j < bars.length; j++) {
        if (bars[j].low <= gap.bottomPrice) {
          gap.filled = true;
          gap.filledTime = bars[j].time;
          break;
        }
      }

      // Hide if too far from current price
      if (hideDistancePct > 0 && currentPrice > gap.topPrice * (1 + hideDistancePct)) continue;

      gaps.push(gap);
    }

    // Gap down: current high < previous low
    if (cur.high < prev.low && (1 - cur.high / prev.low) > minGapPct) {
      const gap: GapZone = {
        startTime: cur.time,
        topPrice: prev.low,
        bottomPrice: cur.high,
        direction: 'down',
        pct: (1 - cur.high / prev.low) * 100,
        filled: false,
      };

      for (let j = i + 1; j < bars.length; j++) {
        if (bars[j].high >= gap.topPrice) {
          gap.filled = true;
          gap.filledTime = bars[j].time;
          break;
        }
      }

      if (hideDistancePct > 0 && currentPrice < gap.bottomPrice * (1 - hideDistancePct)) continue;

      gaps.push(gap);
    }
  }

  // Keep most recent gaps up to max
  return gaps.slice(-maxGaps);
}
