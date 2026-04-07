import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { marketDataApi } from '../../services/api';
import { STAGE_HEX } from '../../constants/chart';
import { useColorMode } from '../../theme/colorMode';
import { cn } from '@/lib/utils';
import { Skeleton } from '@/components/ui/skeleton';

const SECTOR_ETFS = [
  'XLK', 'XLF', 'XLV', 'XLY', 'XLI', 'XLE', 'XLU', 'XLP',
  'XLB', 'XLRE', 'XLC', 'SMH', 'XBI', 'ITA', 'GDX', 'TAN', 'URA',
];

const TIME_RANGES = [
  { label: '50d', days: 50 },
  { label: '100d', days: 100 },
  { label: '200d', days: 200 },
  { label: '1Y', days: 365 },
] as const;

const EMPTY_STAGE_COLOR_LIGHT = '#CBD5E1';
const EMPTY_STAGE_COLOR_DARK = '#1E293B';

function stageColor(stage: string | null | undefined, isDark: boolean): string {
  if (!stage) return isDark ? EMPTY_STAGE_COLOR_DARK : EMPTY_STAGE_COLOR_LIGHT;
  const hex = STAGE_HEX[stage];
  return hex ? hex[1] : isDark ? EMPTY_STAGE_COLOR_DARK : EMPTY_STAGE_COLOR_LIGHT;
}

function stageTooltip(stage: string | null | undefined): string {
  if (!stage) return 'No data';
  const labels: Record<string, string> = {
    '1A': 'Base (early)', '1B': 'Base (breakout setup)',
    '2A': 'Advance (early)', '2B': 'Advance (confirmed)', '2C': 'Advance (extended)',
    '3A': 'Top (early)', '3B': 'Top (distribution)',
    '4A': 'Decline (early)', '4B': 'Decline (confirmed)', '4C': 'Decline (capitulation)',
  };
  return labels[stage] || stage;
}

interface HeatmapViewProps {
  snapshots: any[];
}

const HeatmapView: React.FC<HeatmapViewProps> = ({ snapshots }) => {
  const { colorMode } = useColorMode();
  const isDark = colorMode === 'dark';
  const [timeRange, setTimeRange] = React.useState<number>(100);

  const etfSymbols = React.useMemo(() => {
    if (snapshots.length === 0) return SECTOR_ETFS;
    const available = new Set(snapshots.map((s: any) => s.symbol?.toUpperCase()));
    return SECTOR_ETFS.filter(s => available.has(s));
  }, [snapshots]);

  const queries = useQuery({
    queryKey: ['heatmap-history-batch', etfSymbols.join(','), timeRange],
    queryFn: async () => {
      const results: Record<string, any[]> = {};
      try {
        const resp = await marketDataApi.getSnapshotHistoryBatch(etfSymbols.join(','), timeRange);
        const raw = resp as Record<string, any> | undefined;
        const bySym = raw?.data?.histories ?? raw?.histories ?? {};
        for (const sym of etfSymbols) {
          const rows = bySym[sym] ?? [];
          results[sym] = Array.isArray(rows) ? rows : [];
        }
      } catch {
        for (const sym of etfSymbols) {
          results[sym] = [];
        }
      }
      return results;
    },
    staleTime: 10 * 60_000,
    enabled: etfSymbols.length > 0,
  });

  const historyData = queries.data || {};

  const allDates = React.useMemo(() => {
    const dateSet = new Set<string>();
    Object.values(historyData).forEach((rows: any[]) => {
      rows.forEach((r: any) => {
        if (r.as_of_date) dateSet.add(r.as_of_date);
      });
    });
    return Array.from(dateSet).sort();
  }, [historyData]);

  const displayDates = React.useMemo(() => {
    const maxCols = 60;
    if (allDates.length <= maxCols) return allDates;
    const step = Math.ceil(allDates.length / maxCols);
    return allDates.filter((_, i) => i % step === 0);
  }, [allDates]);

  const gridData = React.useMemo(() => {
    const grid: Record<string, Record<string, string | null>> = {};
    Object.entries(historyData).forEach(([sym, rows]: [string, any[]]) => {
      grid[sym] = {};
      rows.forEach((r: any) => {
        const snap = r.snapshot || r;
        grid[sym][r.as_of_date] = snap.stage_label || null;
      });
    });
    return grid;
  }, [historyData]);

  const legendStages = ['1A', '1B', '2A', '2B', '2C', '3A', '3B', '4A', '4B', '4C'];

  return (
    <div className="flex flex-col gap-4">
      <div className="rounded-lg border border-border bg-card p-4">
        <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-sm font-semibold">Stage Heatmap — Sector ETFs Over Time</p>
            <p className="text-xs text-muted-foreground">
              Each cell shows the Weinstein stage for that ETF on that date. Green = advancing, Red = declining.
            </p>
          </div>
          <div className="flex flex-wrap gap-1">
            {TIME_RANGES.map(tr => (
              <button
                key={tr.days}
                type="button"
                className={cn(
                  'inline-flex h-5 items-center rounded-full border px-2 text-xs font-medium transition-opacity hover:opacity-85',
                  timeRange === tr.days
                    ? 'border-primary bg-primary text-primary-foreground'
                    : 'border-transparent bg-muted/80 text-muted-foreground'
                )}
                onClick={() => setTimeRange(tr.days)}
              >
                {tr.label}
              </button>
            ))}
          </div>
        </div>

        {queries.isPending ? (
          <div className="flex flex-col gap-2 py-4">
            {Array.from({ length: 8 }).map((_, i) => (
              <Skeleton key={i} className="h-[18px] rounded-sm" />
            ))}
          </div>
        ) : displayDates.length === 0 ? (
          <p className="py-8 text-center text-sm text-muted-foreground">No historical data available</p>
        ) : (
          <div className="overflow-x-auto">
            <div className="inline-block min-w-full">
              <div className="mb-1 flex gap-0">
                <div className="w-[60px] shrink-0" />
                {displayDates.map((date, dateIdx) => (
                  <div
                    key={date}
                    className="w-[14px] shrink-0 text-center"
                    title={date}
                  >
                    {dateIdx % 10 === 0 && (
                      <span
                        className="inline-block origin-left whitespace-nowrap text-[8px] text-muted-foreground"
                        style={{ transform: 'rotate(-45deg)' }}
                      >
                        {date.slice(5)}
                      </span>
                    )}
                  </div>
                ))}
              </div>

              {etfSymbols.map(sym => (
                <div key={sym} className="mb-px flex gap-0">
                  <div className="w-[60px] shrink-0">
                    <p className="truncate text-xs font-semibold">{sym}</p>
                  </div>
                  {displayDates.map(date => {
                    const stage = gridData[sym]?.[date];
                    const tip = `${sym} ${date}: ${stageTooltip(stage)}`;
                    return (
                      <div
                        key={`${sym}-${date}`}
                        className="h-[18px] w-[14px] shrink-0 rounded-[1px] transition-[opacity,outline] outline-offset-0 hover:opacity-80 hover:outline hover:outline-1 hover:outline-white"
                        style={{ backgroundColor: stageColor(stage, isDark) }}
                        title={tip}
                        aria-label={tip}
                      />
                    );
                  })}
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
          {legendStages.map(stage => (
            <div key={stage} className="flex items-center gap-1">
              <div
                className="size-3 rounded-sm"
                style={{ backgroundColor: stageColor(stage, isDark) }}
                aria-hidden
              />
              <span className="text-[10px] text-muted-foreground">{stage}</span>
            </div>
          ))}
          <div className="flex items-center gap-1">
            <div
              className="size-3 rounded-sm"
              style={{ backgroundColor: isDark ? EMPTY_STAGE_COLOR_DARK : EMPTY_STAGE_COLOR_LIGHT }}
              aria-hidden
            />
            <span className="text-[10px] text-muted-foreground">No data</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default HeatmapView;
