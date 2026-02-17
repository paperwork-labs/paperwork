import React from 'react';
import {
  Badge,
  Box,
  Heading,
  HStack,
  Spinner,
  Stack,
  Text,
  TableRoot,
  TableHeader,
  TableRow,
  TableColumnHeader,
  TableBody,
  TableCell,
  TableScrollArea,
} from '@chakra-ui/react';
import { marketDataApi } from '../services/api';

type DashboardPayload = {
  tracked_count?: number;
  snapshot_count?: number;
  entry_proximity_top?: Array<any>;
  exit_proximity_top?: Array<any>;
  sector_etf_table?: Array<any>;
  entering_stage_2a?: Array<any>;
  regime?: { stage_counts_normalized?: Record<string, number> };
  top10_matrix?: Record<string, Array<{ symbol: string; value: number }>>;
  bottom10_matrix?: Record<string, Array<{ symbol: string; value: number }>>;
};

const METRIC_ORDER = [
  { key: 'perf_1d', label: '1D Change' },
  { key: 'perf_5d', label: '5D Change' },
  { key: 'perf_20d', label: '20D Change' },
  { key: 'atrx_sma_21', label: '(Price - 21DMA) / ATR' },
  { key: 'atrx_sma_50', label: '(Price - 50DMA) / ATR' },
  { key: 'atrx_sma_200', label: '(Price - 200DMA) / ATR' },
];

const fmtValue = (value: unknown, metricKey: string) => {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '—';
  if (metricKey.startsWith('perf_')) return `${value.toFixed(1)}%`;
  return `${value.toFixed(2)}x`;
};

const normalizeSymbol = (symbol: unknown): string => {
  if (typeof symbol !== 'string') return '';
  return symbol.trim().toUpperCase();
};

const REPEAT_TEXT_COLORS = [
  'pink.500',
  'purple.500',
  'blue.500',
  'teal.500',
  'orange.500',
  'green.500',
  'cyan.500',
  'yellow.600',
] as const;

const repeatSymbolColor = (symbol: string): string => {
  let hash = 0;
  for (let i = 0; i < symbol.length; i += 1) {
    hash = (hash * 31 + symbol.charCodeAt(i)) >>> 0;
  }
  return REPEAT_TEXT_COLORS[hash % REPEAT_TEXT_COLORS.length];
};

const RankMatrix: React.FC<{ title: string; data?: Record<string, Array<{ symbol: string; value: number }>> }> = ({ title, data }) => {
  const rows = Array.from({ length: 10 }).map((_, idx) => idx);
  const repeatedSymbols = React.useMemo(() => {
    const counts = new Map<string, number>();
    METRIC_ORDER.forEach((metric) => {
      (data?.[metric.key] || []).forEach((item) => {
        const symbol = normalizeSymbol(item?.symbol);
        if (!symbol) return;
        counts.set(symbol, (counts.get(symbol) || 0) + 1);
      });
    });
    return new Set(
      Array.from(counts.entries())
        .filter(([, count]) => count > 1)
        .map(([symbol]) => symbol),
    );
  }, [data]);

  return (
    <Box borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={3} bg="bg.card">
      <Text fontSize="sm" fontWeight="semibold" mb={2}>{title}</Text>
      <TableScrollArea borderWidth="1px" borderColor="border.subtle" borderRadius="md">
        <TableRoot size="sm">
          <TableHeader>
            <TableRow>
              {METRIC_ORDER.map((m) => (
                <TableColumnHeader key={m.key}>{m.label}</TableColumnHeader>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((idx) => (
              <TableRow key={idx}>
                {METRIC_ORDER.map((m) => {
                  const item = (data?.[m.key] || [])[idx];
                  const symbol = normalizeSymbol(item?.symbol);
                  const hasRepeat = !!symbol && repeatedSymbols.has(symbol);
                  if (!item) {
                    return <TableCell key={`${m.key}-${idx}`}>—</TableCell>;
                  }
                  return (
                    <TableCell key={`${m.key}-${idx}`}>
                      <Text
                        fontWeight={hasRepeat ? 'bold' : undefined}
                        color={hasRepeat ? repeatSymbolColor(symbol) : undefined}
                        data-testid={
                          hasRepeat
                            ? `repeat-text-${title.replace(/\s+/g, '-').toLowerCase()}`
                            : undefined
                        }
                      >
                        {`${item.symbol} (${fmtValue(item.value, m.key)})`}
                      </Text>
                    </TableCell>
                  );
                })}
              </TableRow>
            ))}
          </TableBody>
        </TableRoot>
      </TableScrollArea>
    </Box>
  );
};

const MarketDashboard: React.FC = () => {
  const [payload, setPayload] = React.useState<DashboardPayload | null>(null);
  const [loading, setLoading] = React.useState<boolean>(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const res = await marketDataApi.getDashboard();
        setPayload((res as DashboardPayload) || null);
        setError(null);
      } catch (e: any) {
        setPayload(null);
        setError(e?.message || 'Failed to load market dashboard');
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, []);

  if (loading) {
    return (
      <Box p={4}>
        <HStack><Spinner size="sm" /><Text>Loading market dashboard…</Text></HStack>
      </Box>
    );
  }

  if (error) {
    return (
      <Box p={4}>
        <Heading size="md" mb={2}>Market Dashboard</Heading>
        <Text color="status.danger">{error}</Text>
      </Box>
    );
  }

  const stageCounts = payload?.regime?.stage_counts_normalized || {};
  const entryRows = payload?.entry_proximity_top || [];
  const exitRows = payload?.exit_proximity_top || [];
  const sectorRows = payload?.sector_etf_table || [];
  const enteringStage2a = payload?.entering_stage_2a || [];

  return (
    <Box p={4}>
      <Stack gap={4}>
        <HStack justify="space-between" align="end" flexWrap="wrap">
          <Box>
            <Heading size="md">Market Dashboard</Heading>
            <Text color="fg.muted" fontSize="sm">
              Entry/exit proximity, sector ETFs, stage transitions, and ranked momentum metrics.
            </Text>
          </Box>
          <HStack gap={2}>
            <Badge variant="subtle">Tracked {payload?.tracked_count || 0}</Badge>
            <Badge variant="subtle">Snapshots {payload?.snapshot_count || 0}</Badge>
          </HStack>
        </HStack>

        <Box display="grid" gridTemplateColumns={{ base: '1fr', md: 'repeat(6, 1fr)' }} gap={2}>
          <Badge variant="subtle">Stage 1: {stageCounts['1'] || 0}</Badge>
          <Badge variant="subtle">Stage 2A: {stageCounts['2A'] || 0}</Badge>
          <Badge variant="subtle">Stage 2B: {stageCounts['2B'] || 0}</Badge>
          <Badge variant="subtle">Stage 2C: {stageCounts['2C'] || 0}</Badge>
          <Badge variant="subtle">Stage 3: {stageCounts['3'] || 0}</Badge>
          <Badge variant="subtle">Stage 4: {stageCounts['4'] || 0}</Badge>
        </Box>

        <Box display="grid" gridTemplateColumns={{ base: '1fr', xl: '1fr 1fr' }} gap={3}>
          <Box borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={3} bg="bg.card">
            <Text fontSize="sm" fontWeight="semibold" mb={2}>Top 10 Closest to Entry</Text>
            <TableScrollArea borderWidth="1px" borderColor="border.subtle" borderRadius="md">
              <TableRoot size="sm">
                <TableHeader>
                  <TableRow>
                    <TableColumnHeader>Symbol</TableColumnHeader>
                    <TableColumnHeader>Entry</TableColumnHeader>
                    <TableColumnHeader>Dist %</TableColumnHeader>
                    <TableColumnHeader>Dist ATR</TableColumnHeader>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {entryRows.slice(0, 10).length ? (
                    entryRows.slice(0, 10).map((r) => (
                      <TableRow key={`entry-${r.symbol}`}>
                        <TableCell>{r.symbol}</TableCell>
                        <TableCell>{typeof r.entry_price === 'number' ? r.entry_price.toFixed(2) : '—'}</TableCell>
                        <TableCell>{typeof r.distance_pct === 'number' ? `${r.distance_pct.toFixed(2)}%` : '—'}</TableCell>
                        <TableCell>{typeof r.distance_atr === 'number' ? `${r.distance_atr.toFixed(2)}x` : '—'}</TableCell>
                      </TableRow>
                    ))
                  ) : (
                    <TableRow>
                      <TableCell colSpan={4}>
                        <Text fontSize="xs" color="fg.muted">
                          No entry prices set yet. Analysts/Admins can set Entry in Market Tracked.
                        </Text>
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </TableRoot>
            </TableScrollArea>
          </Box>

          <Box borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={3} bg="bg.card">
            <Text fontSize="sm" fontWeight="semibold" mb={2}>Top 10 Closest to Exit</Text>
            <TableScrollArea borderWidth="1px" borderColor="border.subtle" borderRadius="md">
              <TableRoot size="sm">
                <TableHeader>
                  <TableRow>
                    <TableColumnHeader>Symbol</TableColumnHeader>
                    <TableColumnHeader>Exit</TableColumnHeader>
                    <TableColumnHeader>Dist %</TableColumnHeader>
                    <TableColumnHeader>Dist ATR</TableColumnHeader>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {exitRows.slice(0, 10).length ? (
                    exitRows.slice(0, 10).map((r) => (
                      <TableRow key={`exit-${r.symbol}`}>
                        <TableCell>{r.symbol}</TableCell>
                        <TableCell>{typeof r.exit_price === 'number' ? r.exit_price.toFixed(2) : '—'}</TableCell>
                        <TableCell>{typeof r.distance_pct === 'number' ? `${r.distance_pct.toFixed(2)}%` : '—'}</TableCell>
                        <TableCell>{typeof r.distance_atr === 'number' ? `${r.distance_atr.toFixed(2)}x` : '—'}</TableCell>
                      </TableRow>
                    ))
                  ) : (
                    <TableRow>
                      <TableCell colSpan={4}>
                        <Text fontSize="xs" color="fg.muted">
                          No exit prices set yet. Analysts/Admins can set Exit in Market Tracked.
                        </Text>
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </TableRoot>
            </TableScrollArea>
          </Box>

          <Box borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={3} bg="bg.card">
            <Text fontSize="sm" fontWeight="semibold" mb={2}>Sector ETFs</Text>
            <TableScrollArea borderWidth="1px" borderColor="border.subtle" borderRadius="md">
              <TableRoot size="sm">
                <TableHeader>
                  <TableRow>
                    <TableColumnHeader>Sector Name</TableColumnHeader>
                    <TableColumnHeader>1D Change</TableColumnHeader>
                    <TableColumnHeader>Stage</TableColumnHeader>
                    <TableColumnHeader>Days in Stage</TableColumnHeader>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {sectorRows.slice(0, 20).map((r) => (
                    <TableRow key={`sector-${r.symbol}`}>
                      <TableCell>{r.sector_name || r.symbol}</TableCell>
                      <TableCell>{typeof r.change_1d === 'number' ? `${r.change_1d.toFixed(1)}%` : '—'}</TableCell>
                      <TableCell>{r.stage_label || '—'}</TableCell>
                      <TableCell>{typeof r.days_in_stage === 'number' ? r.days_in_stage : '—'}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </TableRoot>
            </TableScrollArea>
          </Box>

          <Box borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={3} bg="bg.card">
            <HStack justify="space-between" align="center" mb={2}>
              <Text fontSize="sm" fontWeight="semibold">Stocks Entering Stage 2A</Text>
              <Badge variant="subtle">{enteringStage2a.length}</Badge>
            </HStack>
            <Box maxH="320px" overflowY="auto" pr={1}>
              <Stack gap={1}>
                {enteringStage2a.length ? enteringStage2a.map((r) => (
                  <HStack key={`stage2a-${r.symbol}`} justify="space-between">
                    <Text fontSize="xs">{r.symbol}</Text>
                    <Badge variant="subtle">{`Prev ${r.previous_stage_label || '—'} -> 2A`}</Badge>
                  </HStack>
                )) : <Text fontSize="xs" color="fg.muted">No recent entries.</Text>}
              </Stack>
            </Box>
          </Box>
        </Box>

        <RankMatrix title="Top 10 Matrix" data={payload?.top10_matrix} />
        <RankMatrix title="Bottom 10 Matrix" data={payload?.bottom10_matrix} />
      </Stack>
    </Box>
  );
};

export default MarketDashboard;
