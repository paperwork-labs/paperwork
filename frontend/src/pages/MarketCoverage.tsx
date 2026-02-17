import React from 'react';
import { Badge, Box, HStack, Heading, Stack, Text } from '@chakra-ui/react';
import useCoverageSnapshot from '../hooks/useCoverageSnapshot';
import {
  CoverageBucketsGrid,
  CoverageKpiGrid,
  CoverageSummaryCard,
  CoverageTrendGrid,
} from '../components/coverage/CoverageSummaryCard';
import CoverageHealthStrip from '../components/coverage/CoverageHealthStrip';
import { useUserPreferences } from '../hooks/useUserPreferences';

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
    <Box p={4}>
      <Stack gap={6}>
        <Stack gap={2}>
          <Heading size="md">Market Coverage</Heading>
          <Text color="fg.muted">
            How well the tracked universe is filled with daily OHLCV bars and technical snapshots. Green means all symbols have recent data.
          </Text>
        </Stack>

        {coverage && (
          <CoverageSummaryCard hero={hero} status={coverage.status}>
            <CoverageKpiGrid kpis={kpis} variant="compact" />
            <CoverageTrendGrid sparkline={sparkline} />
            <CoverageBucketsGrid groups={hero?.buckets || []} />
            {dailyFillDist.total > 0 ? (
              <Box mt={3} borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={3} bg="bg.muted">
                <HStack justify="space-between" align="start" flexWrap="wrap" gap={3}>
                  <Box>
                    <Text fontSize="sm" fontWeight="semibold" color="fg.default">
                      Daily fill by date (1d OHLCV)
                    </Text>
                    <Text fontSize="xs" color="fg.muted">
                      {dailyFillDist.newestDate
                        ? `Newest date: ${dailyFillDist.newestDate} • ${dailyFillDist.newestCount}/${dailyFillDist.total} symbols`
                        : 'No daily bars found'}
                    </Text>
                  </Box>
                  <HStack gap={2} flexWrap="wrap">
                    {benchmarkStale ? (
                      <Badge variant="subtle" colorScheme="red">
                        SPY stale {benchmarkLatest ? `(${String(benchmarkLatest)})` : ''}
                      </Badge>
                    ) : null}
                  </HStack>
                </HStack>
                <CoverageHealthStrip
                  dailyFillSeries={dailyFillSeries}
                  snapshotFillSeries={snapshotFillSeries}
                  windowDays={windowDays}
                  totalSymbols={totalSymbols}
                />
              </Box>
            ) : null}
          </CoverageSummaryCard>
        )}

        {!coverage && !loading && <Text color="fg.muted">No coverage yet.</Text>}
      </Stack>
    </Box>
  );
};

export default MarketCoverage;

