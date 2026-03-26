import React from 'react';
import { cn } from '@/lib/utils';

export interface FillRow {
  date: string;
  symbol_count: number;
  pct_of_universe: number;
}

interface Props {
  dailyFillSeries: FillRow[];
  snapshotFillSeries?: FillRow[];
  windowDays: number;
  totalSymbols: number;
}

const normDateKey = (d: unknown) => {
  if (!d) return '';
  const s = String(d);
  return s.length >= 10 ? s.slice(0, 10) : s;
};

const colorForPct = (pct: number) => {
  const t = Math.max(0, Math.min(1, pct / 100));
  const hue = 120 * t;
  return `hsl(${hue}, 70%, 45%)`;
};

const CoverageHealthStrip: React.FC<Props> = ({
  dailyFillSeries,
  snapshotFillSeries,
  windowDays,
  totalSymbols,
}) => {
  const bars = React.useMemo(() => {
    return [...dailyFillSeries]
      .filter((r) => r && r.date)
      .sort((a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : 0))
      .reverse()
      .slice(-windowDays)
      .map((r) => ({
        date: normDateKey(r.date),
        symbol_count: Number(r.symbol_count || 0),
        pct_of_universe: Number(r.pct_of_universe || 0),
      }));
  }, [dailyFillSeries, windowDays]);

  const snapshotPctByDate = React.useMemo(
    () =>
      new Map(
        (snapshotFillSeries || []).map((r) => [
          normDateKey(r.date),
          Number(r.pct_of_universe || 0),
        ]),
      ),
    [snapshotFillSeries],
  );

  if (!bars.length || !totalSymbols) return null;

  const latest = bars[bars.length - 1];
  const latestPct = latest ? Number(latest.pct_of_universe || 0) : 0;

  const sparkWidth = 80;
  const sparkHeight = 20;
  const sparkPath = bars
    .map((p, i) => {
      const x = (i / Math.max(bars.length - 1, 1)) * sparkWidth;
      const y = sparkHeight - (Math.min(Number(p.pct_of_universe || 0), 100) / 100) * sparkHeight;
      return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(' ');

  return (
    <div className="mt-2">
      <div className="flex flex-wrap items-center gap-3">
        <div className="min-w-0 flex-1">
          <div className="overflow-x-auto overflow-y-hidden rounded-md border border-border bg-card px-1 py-1">
            <div className="flex h-[22px] w-full items-end gap-px">
              {bars.map((r) => {
                const pct = Number(r.pct_of_universe || 0);
                const h = Math.max(2, Math.round((pct / 100) * 14));
                const snapPct = snapshotPctByDate.get(r.date);
                const snapOk = typeof snapPct === 'number' && snapPct >= 95;
                const snapNone = typeof snapPct !== 'number';
                const dotClass = snapNone
                  ? 'bg-muted-foreground/60 opacity-50'
                  : snapOk
                    ? 'bg-emerald-500'
                    : (snapPct || 0) >= 50
                      ? 'bg-amber-500'
                      : 'bg-destructive';
                return (
                  <div
                    key={r.date}
                    className="flex min-w-[4px] flex-1 flex-col items-center justify-end"
                    title={`${r.date}: ${r.symbol_count}/${totalSymbols} (${Math.round(pct * 10) / 10}%) | snap: ${snapNone ? '—' : `${Math.round((snapPct || 0) * 10) / 10}%`}`}
                  >
                    <div className="w-full rounded-sm" style={{ height: `${h}px`, backgroundColor: colorForPct(pct) }} />
                    <div className={cn('mt-px size-1 rounded-full', dotClass)} />
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          <svg
            width={sparkWidth}
            height={sparkHeight}
            viewBox={`0 0 ${sparkWidth} ${sparkHeight}`}
            className="text-muted-foreground"
            aria-hidden
          >
            <path d={sparkPath} fill="none" stroke="currentColor" strokeWidth="1.2" />
          </svg>
          <span className="whitespace-nowrap text-xs font-semibold text-foreground">
            {Math.round(latestPct * 10) / 10}%
          </span>
        </div>
      </div>
      <p className="mt-1 text-xs text-muted-foreground">
        Coverage strip (last {windowDays} trading days). Cell color = daily fill %. Dot = snapshot coverage (green {'\u2265'}
        95%, orange {'\u2265'}50%, red {'<'}50%, gray = none). Hover for detail.
      </p>
    </div>
  );
};

export default CoverageHealthStrip;
