import React from 'react';

import CoverageHealthStrip from '../components/coverage/CoverageHealthStrip';
import {
  CoverageBucketsGrid,
  CoverageKpiGrid,
  CoverageSummaryCard,
  CoverageTrendGrid,
} from '../components/coverage/CoverageSummaryCard';
import useCoverageSnapshot from '../hooks/useCoverageSnapshot';
import { useUserPreferences } from '../hooks/useUserPreferences';
import { Badge } from '@/components/ui/badge';
import { Page } from '@/components/ui/Page';
import { cn } from '@/lib/utils';

/**
 * Market Data Coverage page (read-only).
 * Shows concise status/KPIs only; admin controls and raw tables live on Admin Dashboard.
 */
const MarketCoverage: React.FC = () => {
  const { coverageHistogramWindowDays } = useUserPreferences();
  const { snapshot: coverage, loading, sparkline, kpis, hero } = useCoverageSnapshot({
    fillTradingDaysWindow: coverageHistogramWindowDays ?? undefined,
  });

  const dailyFillSeries = ((coverage as Record<string, Record<string, unknown>>)?.daily?.fill_by_date as
    Array<{ date: string; symbol_count: number; pct_of_universe: number }>) || [];
  const snapshotFillSeries = ((coverage as Record<string, Record<string, unknown>>)?.daily?.snapshot_fill_by_date as
    Array<{ date: string; symbol_count: number; pct_of_universe: number }>) || [];
  const totalSymbols = Number((coverage as Record<string, unknown>)?.symbols ?? (coverage as Record<string, unknown>)?.tracked_count ?? 0);
  const benchmark = (coverage as Record<string, Record<string, unknown>>)?.meta?.benchmark;
  const benchmarkStale = benchmark && (benchmark as Record<string, unknown>).ok === false;
  const benchmarkLatest = (benchmark as Record<string, unknown>)?.latest_daily_date;
  const windowDays = Math.max(1, Number((coverage as Record<string, Record<string, unknown>>)?.meta?.fill_trading_days_window ?? 50));

  const dailyFillDist = React.useMemo(() => {
    const rows = [...dailyFillSeries]
      .filter((r) => r && r.date)
      .sort((a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : 0));
    const newestDate = rows.length ? rows[0].date : null;
    const newestCount = rows.length ? Number(rows[0].symbol_count || 0) : 0;
    const newestPct = rows.length ? Number(rows[0].pct_of_universe || 0) : 0;
    return { newestDate, newestCount, newestPct, total: totalSymbols || 0, rows };
  }, [dailyFillSeries, totalSymbols]);

  return (
    <Page>
      <div className="flex flex-col gap-6">
        <div className="flex flex-col gap-2">
          <h1 className="font-heading text-2xl font-semibold tracking-tight text-foreground md:text-3xl">
            Market Coverage
          </h1>
          <p className="text-sm text-muted-foreground">
            How well the tracked universe is filled with daily OHLCV bars and technical snapshots. Green means all symbols have recent data.
          </p>
        </div>

        {coverage && (
          <CoverageSummaryCard hero={hero} status={coverage.status}>
            <CoverageKpiGrid kpis={kpis} variant="compact" />
            <CoverageTrendGrid sparkline={sparkline} />
            <CoverageBucketsGrid groups={hero?.buckets || []} />
            {dailyFillDist.total > 0 ? (
              <div
                className={cn(
                  'mt-3 rounded-lg border border-border bg-muted/40 p-3',
                )}
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-foreground">
                      Daily fill by date (1d OHLCV)
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {dailyFillDist.newestDate
                        ? `Newest date: ${dailyFillDist.newestDate} • ${dailyFillDist.newestCount}/${dailyFillDist.total} symbols`
                        : 'No daily bars found'}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {benchmarkStale ? (
                      <Badge
                        variant="destructive"
                        className="border-transparent bg-destructive/15 font-normal"
                      >
                        SPY stale {benchmarkLatest ? `(${String(benchmarkLatest)})` : ''}
                      </Badge>
                    ) : null}
                  </div>
                </div>
                <CoverageHealthStrip
                  dailyFillSeries={dailyFillSeries}
                  snapshotFillSeries={snapshotFillSeries}
                  windowDays={windowDays}
                  totalSymbols={totalSymbols}
                />
              </div>
            ) : null}
          </CoverageSummaryCard>
        )}

        {!coverage && !loading ? (
          <p className="text-sm text-muted-foreground">No coverage yet.</p>
        ) : null}
      </div>
    </Page>
  );
};

export default MarketCoverage;
