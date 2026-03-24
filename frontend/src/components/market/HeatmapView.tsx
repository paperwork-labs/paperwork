import React from 'react';
import {
  Box, HStack, Text, Stack, SimpleGrid, Badge, Skeleton,
} from '@chakra-ui/react';
import { useQuery } from 'react-query';
import { marketDataApi } from '../../services/api';
import { STAGE_HEX } from '../../constants/chart';
import { useColorMode } from '../../theme/colorMode';

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
    const available = new Set(snapshots.map((s: any) => s.symbol?.toUpperCase()));
    return SECTOR_ETFS.filter(s => available.has(s));
  }, [snapshots]);

  const queries = useQuery(
    ['heatmap-history', etfSymbols.join(','), timeRange],
    async () => {
      const results: Record<string, any[]> = {};
      await Promise.all(
        etfSymbols.map(async (sym) => {
          try {
            const resp = await marketDataApi.getSnapshotHistory(sym, timeRange);
            const rows = resp?.data?.rows ?? resp?.rows ?? [];
            results[sym] = rows;
          } catch {
            results[sym] = [];
          }
        })
      );
      return results;
    },
    { staleTime: 10 * 60_000, enabled: etfSymbols.length > 0 },
  );

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
    <Stack gap={4}>
      <Box borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={4} bg="bg.card">
        <HStack justify="space-between" mb={4}>
          <Box>
            <Text fontSize="sm" fontWeight="semibold">Stage Heatmap — Sector ETFs Over Time</Text>
            <Text fontSize="xs" color="fg.muted">
              Each cell shows the Weinstein stage for that ETF on that date. Green = advancing, Red = declining.
            </Text>
          </Box>
          <HStack gap={1}>
            {TIME_RANGES.map(tr => (
              <Badge
                key={tr.days}
                variant={timeRange === tr.days ? 'solid' : 'subtle'}
                cursor="pointer"
                onClick={() => setTimeRange(tr.days)}
                size="sm"
                transition="all 200ms ease"
                _hover={{ opacity: 0.85 }}
              >
                {tr.label}
              </Badge>
            ))}
          </HStack>
        </HStack>

        {queries.isLoading ? (
          <Stack gap={2} py={4}>
            {Array.from({ length: 8 }).map((_, i) => (
              <Skeleton key={i} height="18px" borderRadius="sm" />
            ))}
          </Stack>
        ) : displayDates.length === 0 ? (
          <Text fontSize="sm" color="fg.muted" textAlign="center" py={8}>No historical data available</Text>
        ) : (
          <Box overflowX="auto">
            <Box display="inline-block" minW="100%">
              {/* Header Row */}
              <HStack gap={0} mb={1}>
                <Box w="60px" flexShrink={0} />
                {displayDates.map(date => (
                  <Box
                    key={date}
                    w="14px"
                    flexShrink={0}
                    textAlign="center"
                    title={date}
                  >
                    {displayDates.indexOf(date) % 10 === 0 && (
                      <Text fontSize="8px" color="fg.muted" transform="rotate(-45deg)" transformOrigin="left" whiteSpace="nowrap">
                        {date.slice(5)}
                      </Text>
                    )}
                  </Box>
                ))}
              </HStack>

              {/* Data Rows */}
              {etfSymbols.map(sym => (
                <HStack key={sym} gap={0} mb="1px">
                  <Box w="60px" flexShrink={0}>
                    <Text fontSize="xs" fontWeight="semibold" truncate>{sym}</Text>
                  </Box>
                  {displayDates.map(date => {
                    const stage = gridData[sym]?.[date];
                    return (
                      <Box
                        key={`${sym}-${date}`}
                        w="14px"
                        h="18px"
                        flexShrink={0}
                        bg={stageColor(stage, isDark)}
                        borderRadius="1px"
                        title={`${sym} ${date}: ${stageTooltip(stage)}`}
                        aria-label={`${sym} ${date}: ${stageTooltip(stage)}`}
                        transition="opacity 150ms ease, outline 150ms ease"
                        _hover={{ opacity: 0.8, outline: '1px solid white' }}
                      />
                    );
                  })}
                </HStack>
              ))}
            </Box>
          </Box>
        )}

        {/* Legend */}
        <HStack gap={2} mt={4} flexWrap="wrap" justify="center">
          {legendStages.map(stage => (
            <HStack key={stage} gap={1}>
              <Box w="12px" h="12px" borderRadius="sm" bg={stageColor(stage, isDark)} />
              <Text fontSize="10px" color="fg.muted">{stage}</Text>
            </HStack>
          ))}
          <HStack gap={1}>
            <Box w="12px" h="12px" borderRadius="sm" bg={isDark ? EMPTY_STAGE_COLOR_DARK : EMPTY_STAGE_COLOR_LIGHT} />
            <Text fontSize="10px" color="fg.muted">No data</Text>
          </HStack>
        </HStack>
      </Box>
    </Stack>
  );
};

export default HeatmapView;
