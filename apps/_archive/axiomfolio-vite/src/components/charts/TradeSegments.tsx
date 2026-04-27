/**
 * Trade segment overlays: FIFO-matched long round-trips as horizontal
 * price lines (entry to exit) colored win / loss.
 */
import * as React from 'react';
import type { IChartApi, UTCTimestamp } from 'lightweight-charts';
import { LineSeries, LineStyle } from 'lightweight-charts';

import { isBuySide, isSellSide } from '@/lib/holdingChart/sideTokens';
import type { ChartColors } from '@/hooks/useChartColors';
import type { ActivityRow } from '@/types/portfolio';

const utcDaySec = (iso: string): UTCTimestamp => {
  const d = new Date(iso);
  return Math.floor(
    Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()) / 1000,
  ) as UTCTimestamp;
};

const asUTC = (t: number) => t as UTCTimestamp;

export interface ChartTradeSegment {
  entryTime: string;
  exitTime: string;
  entryPrice: number;
  win: boolean;
}

/**
 * Long-only FIFO: match sells to open lots; one segment per closed slice.
 */
export function buildTradeSegmentsFromActivity(
  rows: ReadonlyArray<ActivityRow>,
  symbol: string,
): ChartTradeSegment[] {
  const symU = symbol.toUpperCase();
  const sorted = rows
    .filter((r) => (r.symbol || '').toUpperCase() === symU)
    .filter((r) => {
      const c = (r.category || '').toUpperCase();
      if (c.includes('TRADE')) return true;
      if (c.includes('BUY') || c.includes('SELL')) return true;
      return isBuySide(r.side) || isSellSide(r.side);
    })
    .filter((r) => Boolean(r.ts))
    .sort((a, b) => a.ts.localeCompare(b.ts));

  type Lot = { qty: number; price: number; entryIso: string };
  const queue: Lot[] = [];
  const out: ChartTradeSegment[] = [];

  for (const r of sorted) {
    const qty = Math.abs(Number(r.quantity) || 0);
    if (qty <= 0) continue;
    if (isBuySide(r.side)) {
      const price = Number(r.price) || 0;
      queue.push({ qty, price, entryIso: r.ts });
      continue;
    }
    if (isSellSide(r.side)) {
      const sellP = Number(r.price) || 0;
      let rem = qty;
      while (rem > 0 && queue.length > 0) {
        const lot = queue[0]!;
        const take = Math.min(rem, lot.qty);
        const win = sellP > lot.price;
        out.push({
          entryTime: lot.entryIso,
          exitTime: r.ts,
          entryPrice: lot.price,
          win,
        });
        lot.qty -= take;
        rem -= take;
        if (lot.qty <= 0) {
          queue.shift();
        }
      }
    }
  }
  return out;
}

/**
 * Paints one dashed horizontal line per closed segment (entry price level
 * from entry day through exit day).
 */
export function applyTradeSegmentOverlays(
  chart: IChartApi,
  segments: ReadonlyArray<ChartTradeSegment>,
  colors: ChartColors,
): void {
  for (const s of segments) {
    if (!Number.isFinite(s.entryPrice) || s.entryPrice <= 0) continue;
    const t0 = utcDaySec(s.entryTime);
    const t1 = utcDaySec(s.exitTime);
    if (t0 <= 0 || t1 <= 0) continue;
    const line = chart.addSeries(LineSeries, {
      color: s.win ? colors.success : colors.danger,
      lineWidth: 1,
      lineStyle: LineStyle.Dashed,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });
    const lo = Math.min(t0 as number, t1 as number);
    const hi = Math.max(t0 as number, t1 as number);
    line.setData([
      { time: asUTC(lo), value: s.entryPrice },
      { time: asUTC(hi), value: s.entryPrice },
    ]);
  }
}

const TradeSegments: React.FC<Record<string, never>> = () => null;
export default TradeSegments;
