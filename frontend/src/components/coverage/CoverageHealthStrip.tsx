import React from 'react';
import { Box, HStack, Text } from '@chakra-ui/react';

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
    <Box mt={2}>
      <HStack gap={3} align="center">
        {/* Heatmap strip + snapshot dots */}
        <Box flex="1" minW="0">
          <Box
            borderRadius="md"
            borderWidth="1px"
            borderColor="border.subtle"
            bg="bg.card"
            px={1}
            py={1}
            overflowX="auto"
            overflowY="hidden"
          >
            <HStack align="end" gap="1px" h="22px" w="full">
              {bars.map((r) => {
                const pct = Number(r.pct_of_universe || 0);
                const h = Math.max(2, Math.round((pct / 100) * 14));
                const snapPct = snapshotPctByDate.get(r.date);
                const snapOk = typeof snapPct === 'number' && snapPct >= 95;
                const snapNone = typeof snapPct !== 'number';
                const dotBg = snapNone
                  ? 'fg.subtle'
                  : snapOk
                    ? 'status.success'
                    : (snapPct || 0) >= 50
                      ? 'status.warning'
                      : 'status.danger';
                return (
                  <Box
                    key={r.date}
                    flex="1 0 0"
                    minW="4px"
                    display="flex"
                    flexDirection="column"
                    alignItems="center"
                    justifyContent="flex-end"
                    title={`${r.date}: ${r.symbol_count}/${totalSymbols} (${Math.round(pct * 10) / 10}%) | snap: ${snapNone ? '—' : `${Math.round((snapPct || 0) * 10) / 10}%`}`}
                  >
                    <Box w="full" h={`${h}px`} borderRadius="sm" bg={colorForPct(pct)} />
                    <Box
                      mt="1px"
                      w="4px"
                      h="4px"
                      borderRadius="full"
                      bg={dotBg}
                      opacity={snapNone ? 0.5 : 1}
                    />
                  </Box>
                );
              })}
            </HStack>
          </Box>
        </Box>

        {/* Inline sparkline + latest value */}
        <HStack gap={2} flexShrink={0} align="center">
          <svg width={sparkWidth} height={sparkHeight} viewBox={`0 0 ${sparkWidth} ${sparkHeight}`}>
            <path d={sparkPath} fill="none" stroke="var(--chakra-colors-fg-muted)" strokeWidth="1.2" />
          </svg>
          <Text fontSize="xs" fontWeight="semibold" color="fg.default" whiteSpace="nowrap">
            {Math.round(latestPct * 10) / 10}%
          </Text>
        </HStack>
      </HStack>
      <Text mt={1} fontSize="xs" color="fg.muted">
        Coverage strip (last {windowDays} trading days). Cell color = daily fill %. Dot = snapshot coverage (green {'\u2265'}95%, orange {'\u2265'}50%, red {'<'}50%, gray = none). Hover for detail.
      </Text>
    </Box>
  );
};

export default CoverageHealthStrip;
