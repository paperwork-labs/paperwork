import React from 'react';
import { Badge, Box, HStack, Heading, Stack, Text } from '@chakra-ui/react';
import useCoverageSnapshot from '../hooks/useCoverageSnapshot';
import {
  CoverageBucketsGrid,
  CoverageKpiGrid,
  CoverageSummaryCard,
  CoverageTrendGrid,
} from '../components/coverage/CoverageSummaryCard';
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

  const dailyFillSeries = (coverage as any)?.daily?.fill_by_date as
    | Array<{ date: string; symbol_count: number; pct_of_universe: number }>
    | undefined;
  const snapshotFillSeries = (coverage as any)?.daily?.snapshot_fill_by_date as
    | Array<{ date: string; symbol_count: number; pct_of_universe: number }>
    | undefined;
  const totalSymbols = Number((coverage as any)?.symbols ?? (coverage as any)?.tracked_count ?? 0);
  const benchmark = (coverage as any)?.meta?.benchmark;
  const benchmarkStale = benchmark && benchmark.ok === false;
  const benchmarkLatest = benchmark?.latest_daily_date;

  const dailyFillDist = React.useMemo(() => {
    const rows = (dailyFillSeries || [])
      .filter((r) => r && r.date)
      .slice()
      .sort((a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : 0)); // newest-first
    const newestDate = rows.length ? rows[0].date : null;
    const newestCount = rows.length ? Number(rows[0].symbol_count || 0) : 0;
    const newestPct = rows.length ? Number(rows[0].pct_of_universe || 0) : 0;
    return { newestDate, newestCount, newestPct, total: totalSymbols || 0, rows };
  }, [dailyFillSeries, totalSymbols]);

  const dailyHistogram = React.useMemo(() => {
    const { rows, newestDate, total } = dailyFillDist;
    if (!rows.length || !newestDate || !total) return null;

    const normDateKey = (d: any) => {
      if (!d) return '';
      const s = String(d);
      return s.length >= 10 ? s.slice(0, 10) : s;
    };

    const pctFor = (row: { pct_of_universe: number }) => Number(row?.pct_of_universe || 0);
    const colorForPct = (pct: number) => {
      const t = Math.max(0, Math.min(1, pct / 100));
      const hue = 0 + 120 * t;
      return `hsl(${hue}, 70%, 45%)`;
    };

    const barMaxH = 36;
    const dotH = 8;
    const snapshotPctByDate = new Map(
      (snapshotFillSeries || []).map((r) => [normDateKey(r.date), Number(r.pct_of_universe || 0)]),
    );
    const windowDays = Math.max(1, Number((coverage as any)?.meta?.fill_trading_days_window ?? 50));
    const bars: Array<{ date: string; symbol_count: number; pct_of_universe: number }> = rows
      .slice()
      .reverse()
      .slice(-windowDays)
      .map((r) => ({
        date: normDateKey(r.date),
        symbol_count: Number(r.symbol_count || 0),
        pct_of_universe: Number(r.pct_of_universe || 0),
      }));

    return (
      <Box mt={2}>
        <Box
          borderRadius="md"
          borderWidth="1px"
          borderColor="border.subtle"
          bg="bg.card"
          px={2}
          py={2}
          overflowX="auto"
          overflowY="hidden"
        >
          <HStack align="end" gap={1} h={`${barMaxH + dotH}px`} w="full">
            {bars.map((r) => {
              const pct = pctFor(r);
              const h = Math.max(2, Math.round((pct / 100) * barMaxH));
              const snapPct = snapshotPctByDate.get(normDateKey(r.date));
              const snapOk = typeof snapPct === 'number' && snapPct >= 95;
              const snapNone = typeof snapPct !== 'number';
              const dotBg =
                snapNone ? 'gray.400' : snapOk ? 'green.500' : (snapPct || 0) >= 50 ? 'orange.500' : 'red.500';
              return (
                <Box
                  key={r.date}
                  flex="1 0 0"
                  minW="6px"
                  title={`${r.date}: ${r.symbol_count}/${total} (${Math.round(pct * 10) / 10}%)`}
                >
                  <Box w="full" h={`${h}px`} borderRadius="sm" bg={colorForPct(pct)} />
                  <Box
                    mt="2px"
                    mx="auto"
                    w="6px"
                    h="6px"
                    borderRadius="full"
                    bg={dotBg}
                    title={
                      snapNone ? `${r.date}: snapshots —` : `${r.date}: snapshots ${Math.round((snapPct || 0) * 10) / 10}%`
                    }
                  />
                </Box>
              );
            })}
          </HStack>
        </Box>
        <Text mt={1} fontSize="xs" color="fg.muted">
          Histogram bars (daily, last {windowDays} trading days): height + color represent % of symbols with a stored 1d OHLCV bar on that date.
          Dot under each bar indicates technical snapshot coverage for that date (green ≥95%, orange ≥50%, red &lt;50%, gray = no snapshot run recorded).
        </Text>
      </Box>
    );
  }, [coverage, dailyFillDist, snapshotFillSeries]);

  return (
    <Box p={4}>
      <Stack gap={6}>
        <Stack gap={2}>
          <Heading size="md">Market Coverage</Heading>
          <Text color="fg.muted">
            Read-only coverage view for tracked market data. Daily should stay green; 5m can be ignored unless you explicitly enable it.
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
                        SPY stale {benchmarkLatest ? `(${benchmarkLatest})` : ''}
                      </Badge>
                    ) : null}
                    <Badge variant="subtle" colorScheme="green">
                      {dailyFillDist.total > 0 ? `${Math.round((dailyFillDist.newestPct || 0) * 10) / 10}% filled on newest` : '—'}
                    </Badge>
                  </HStack>
                </HStack>
                {dailyHistogram}
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

