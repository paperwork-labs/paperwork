/**
 * Align SPY daily closes to portfolio performance dates and normalize
 * for charting vs portfolio equity.
 */

export interface PortfolioPerformancePoint {
  date: string;
  total_value: number;
}

export interface AlignedChartPoint {
  timeUtc: number;
  /** Primary series: dollars or percent from first point (see mode). */
  equity: number;
  /** Optional benchmark, same scale as equity (scaled in $ mode). */
  benchmark: number | null;
}

function dateKey(iso: string): string {
  return String(iso).slice(0, 10);
}

function toUtcMs(iso: string): number | null {
  const ms = Date.parse(iso);
  return Number.isFinite(ms) ? ms : null;
}

export function pickHistoryPeriodKey(firstMs: number, lastMs: number): string {
  const span = lastMs - firstMs;
  const days = span / 86400000;
  if (!Number.isFinite(days) || days <= 0) return '1y';
  if (days > 365 * 4) return '5y';
  if (days > 365 * 1.5) return '2y';
  if (days > 365) return '1y';
  if (days > 180) return '6mo';
  if (days > 90) return '3mo';
  if (days > 30) return '3mo';
  return '1mo';
}

export type EquityValueMode = 'usd' | 'pct';

/**
 * Build SPY close map keyed by YYYY-MM-DD, forward-filled on sorted trade days.
 */
export function buildSpyCloseMap(
  bars: ReadonlyArray<{ time?: string; date?: string; close: number }>,
): Map<string, number> {
  const sorted = [...bars]
    .map((b) => {
      const k = dateKey(String(b.time ?? b.date ?? ''));
      const c = Number(b.close);
      return { k, c };
    })
    .filter((r) => r.k.length >= 10 && Number.isFinite(r.c) && r.c > 0)
    .sort((a, b) => a.k.localeCompare(b.k));

  const m = new Map<string, number>();
  for (const r of sorted) m.set(r.k, r.c);
  return m;
}

/**
 * @param portfolio — ascending by date, length ≥ 1
 * @param spyByDate — from `buildSpyCloseMap` on SPY /market-data history
 */
export function buildAlignedEquityPoints(
  portfolio: ReadonlyArray<PortfolioPerformancePoint>,
  spyByDate: Map<string, number>,
  mode: EquityValueMode,
): { points: AlignedChartPoint[]; hasBenchmark: boolean } {
  if (portfolio.length === 0) {
    return { points: [], hasBenchmark: false };
  }

  const sorted = [...portfolio]
    .map((p) => ({ d: dateKey(p.date), v: Number(p.total_value) }))
    .filter((r) => r.d.length >= 10 && Number.isFinite(r.v) && r.v > 0)
    .sort((a, b) => a.d.localeCompare(b.d));

  if (sorted.length === 0) {
    return { points: [], hasBenchmark: false };
  }

  const p0 = sorted[0].v;
  let spyCarry: number | null = null;
  const rows: Array<{
    d: string;
    v: number;
    spy: number | null;
  }> = [];
  for (const row of sorted) {
    const sClose = spyByDate.get(row.d);
    if (sClose != null && Number.isFinite(sClose) && sClose > 0) {
      spyCarry = sClose;
    }
    rows.push({ d: row.d, v: row.v, spy: spyCarry });
  }
  const spy0 = rows.find((r) => r.spy != null)?.spy ?? null;
  const hasBenchmark = spy0 != null && p0 > 0;

  const points: AlignedChartPoint[] = [];
  for (const row of rows) {
    const ms = toUtcMs(row.d) ?? toUtcMs(`${row.d}T00:00:00Z`) ?? 0;
    if (!ms) continue;
    const sv = row.spy;

    let equity: number;
    let bench: number | null = null;
    if (mode === 'pct') {
      equity = p0 > 0 ? (row.v / p0 - 1) * 100 : 0;
      if (hasBenchmark && sv != null && spy0 != null) {
        bench = (sv / spy0 - 1) * 100;
      }
    } else {
      equity = row.v;
      if (hasBenchmark && sv != null && spy0 != null) {
        const scale = p0 / spy0;
        bench = sv * scale;
      }
    }

    points.push({ timeUtc: Math.floor(ms / 1000), equity, benchmark: bench });
  }

  return { points, hasBenchmark };
}
