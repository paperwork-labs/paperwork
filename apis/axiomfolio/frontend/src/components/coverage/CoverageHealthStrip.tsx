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

const dailyColor = (pct: number) => {
  const t = Math.max(0, Math.min(1, pct / 100));
  const hue = 120 * t;
  return `hsl(${hue}, 70%, 45%)`;
};

const snapshotColor = (pct: number) => {
  if (pct >= 95) return 'hsl(160, 60%, 40%)';
  if (pct >= 50) return 'hsl(35, 80%, 50%)';
  return 'hsl(0, 70%, 50%)';
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
          {
            pct: Number(r.pct_of_universe || 0),
            count: Number(r.symbol_count || 0),
          },
        ]),
      ),
    [snapshotFillSeries],
  );

  const [hoverIdx, setHoverIdx] = React.useState<number | null>(null);
  const containerRef = React.useRef<HTMLDivElement>(null);

  if (!bars.length || !totalSymbols) return null;

  const latestDailyPct = bars[bars.length - 1]
    ? Number(bars[bars.length - 1].pct_of_universe || 0)
    : 0;
  const latestSnapEntry = bars[bars.length - 1]
    ? snapshotPctByDate.get(bars[bars.length - 1].date)
    : undefined;
  const latestSnapPct = latestSnapEntry?.pct ?? 0;

  const hoverBar = hoverIdx != null ? bars[hoverIdx] : null;
  const hoverSnap = hoverBar ? snapshotPctByDate.get(hoverBar.date) : null;

  return (
    <div className="space-y-1">
      {/* Dual-row strip */}
      <div
        ref={containerRef}
        className="overflow-x-auto overflow-y-hidden rounded-md border border-border bg-card"
        onMouseLeave={() => setHoverIdx(null)}
      >
        {/* Daily row */}
        <div className="flex items-center gap-0 px-1 pt-1">
          <span className="mr-1.5 w-[52px] shrink-0 text-right text-[9px] text-muted-foreground">
            Daily
          </span>
          <div className="flex flex-1 gap-px">
            {bars.map((r, i) => {
              const pct = Number(r.pct_of_universe || 0);
              return (
                <div
                  key={r.date}
                  className={cn(
                    'h-3 min-w-[6px] flex-1 rounded-[2px] transition-opacity',
                    hoverIdx != null && hoverIdx !== i && 'opacity-40',
                  )}
                  style={{ backgroundColor: dailyColor(pct) }}
                  onMouseEnter={() => setHoverIdx(i)}
                />
              );
            })}
          </div>
          <span className="ml-1.5 w-[38px] shrink-0 text-right text-[10px] font-medium tabular-nums text-foreground">
            {Math.round(latestDailyPct * 10) / 10}%
          </span>
        </div>
        {/* Snapshot row */}
        <div className="flex items-center gap-0 px-1 pb-1">
          <span className="mr-1.5 w-[52px] shrink-0 text-right text-[9px] text-muted-foreground">
            Snapshot
          </span>
          <div className="flex flex-1 gap-px">
            {bars.map((r, i) => {
              const snap = snapshotPctByDate.get(r.date);
              const hasSn = snap != null;
              const snapPct = snap?.pct ?? 0;
              return (
                <div
                  key={r.date}
                  className={cn(
                    'h-3 min-w-[6px] flex-1 rounded-[2px] transition-opacity',
                    !hasSn && 'bg-muted/40',
                    hoverIdx != null && hoverIdx !== i && 'opacity-40',
                  )}
                  style={hasSn ? { backgroundColor: snapshotColor(snapPct) } : undefined}
                  onMouseEnter={() => setHoverIdx(i)}
                />
              );
            })}
          </div>
          <span className="ml-1.5 w-[38px] shrink-0 text-right text-[10px] font-medium tabular-nums text-foreground">
            {Math.round(latestSnapPct * 10) / 10}%
          </span>
        </div>
      </div>

      {/* Hover detail line */}
      {hoverBar && (
        <div className="flex items-center gap-3 px-1 text-[10px] text-muted-foreground">
          <span className="font-medium text-foreground">{hoverBar.date}</span>
          <span>
            Daily: {hoverBar.symbol_count.toLocaleString()}/{totalSymbols.toLocaleString()} ({Math.round(hoverBar.pct_of_universe * 10) / 10}%)
          </span>
          {hoverSnap ? (
            <span>
              Snapshot: {hoverSnap.count.toLocaleString()}/{totalSymbols.toLocaleString()} ({Math.round(hoverSnap.pct * 10) / 10}%)
            </span>
          ) : (
            <span className="italic">No snapshot data</span>
          )}
        </div>
      )}
    </div>
  );
};

export default CoverageHealthStrip;
