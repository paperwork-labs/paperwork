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

type SetupItem = {
  symbol: string;
  stage_label?: string;
  perf_1d?: number;
  perf_5d?: number;
  perf_20d?: number;
  rs_mansfield_pct?: number;
  current_stage_days?: number;
  momentum_score?: number;
  sector?: string;
};

type StageTransitionItem = {
  symbol: string;
  previous_stage_label?: string;
  stage_label?: string;
  current_stage_days?: number;
  perf_1d?: number;
};

type SectorETFRow = {
  symbol: string;
  sector_name?: string;
  change_1d?: number;
  change_5d?: number;
  change_20d?: number;
  rs_mansfield_pct?: number;
  stage_label?: string;
  days_in_stage?: number;
};

type SectorMomentumItem = {
  sector: string;
  count: number;
  avg_perf_20d?: number;
  avg_rs_mansfield_pct?: number;
};

type DashboardPayload = {
  tracked_count?: number;
  snapshot_count?: number;
  coverage?: { status?: string; daily_pct?: number };
  regime?: {
    stage_counts_normalized?: Record<string, number>;
    up_1d_count?: number;
    down_1d_count?: number;
    flat_1d_count?: number;
    above_sma50_count?: number;
    above_sma200_count?: number;
  };
  leaders?: SetupItem[];
  setups?: {
    breakout_candidates?: SetupItem[];
    pullback_candidates?: SetupItem[];
    rs_leaders?: SetupItem[];
  };
  sector_momentum?: SectorMomentumItem[];
  action_queue?: SetupItem[];
  entry_proximity_top?: Array<any>;
  exit_proximity_top?: Array<any>;
  sector_etf_table?: SectorETFRow[];
  entering_stage_2a?: StageTransitionItem[];
  entering_stage_3?: StageTransitionItem[];
  entering_stage_4?: StageTransitionItem[];
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

const fmtPct = (v: unknown): string => {
  if (typeof v !== 'number' || !Number.isFinite(v)) return '—';
  return `${v.toFixed(1)}%`;
};

const fmtValue = (value: unknown, metricKey: string) => {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '—';
  if (metricKey.startsWith('perf_')) return `${value.toFixed(1)}%`;
  return `${value.toFixed(2)}x`;
};

const normalizeSymbol = (symbol: unknown): string => {
  if (typeof symbol !== 'string') return '';
  return symbol.trim().toUpperCase();
};

const heatColor = (v: unknown): string | undefined => {
  if (typeof v !== 'number' || !Number.isFinite(v)) return undefined;
  if (v > 3) return 'green.600';
  if (v > 1) return 'green.500';
  if (v > 0) return 'green.400';
  if (v < -3) return 'red.600';
  if (v < -1) return 'red.500';
  if (v < 0) return 'red.400';
  return undefined;
};

const STAGE_COLORS: Record<string, string> = {
  '1': 'gray',
  '2A': 'green',
  '2B': 'teal',
  '2C': 'yellow',
  '3': 'orange',
  '4': 'red',
};

const repeatSymbolColor = (symbol: string): string => {
  // Use a broad hue space so repeated symbols are visually distinct.
  let hash = 0;
  for (let i = 0; i < symbol.length; i += 1) {
    hash = (hash * 31 + symbol.charCodeAt(i)) >>> 0;
  }
  const hue = (hash * 137) % 360;
  return `hsl(${hue} 72% 58%)`;
};

/* ===== Sub-components ===== */

const StatCard: React.FC<{ label: string; value: string | number; sub?: string }> = ({ label, value, sub }) => (
  <Box borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={3} bg="bg.card" flex="1" minW="120px">
    <Text fontSize="xs" color="fg.muted">{label}</Text>
    <Text fontSize="lg" fontWeight="bold">{value}</Text>
    {sub && <Text fontSize="xs" color="fg.muted">{sub}</Text>}
  </Box>
);

const StageBar: React.FC<{ counts: Record<string, number>; total: number }> = ({ counts, total }) => {
  const stages = ['1', '2A', '2B', '2C', '3', '4'];
  if (total === 0) return <Text fontSize="xs" color="fg.muted">No data</Text>;
  return (
    <Box>
      <Box display="flex" h="24px" borderRadius="md" overflow="hidden">
        {stages.map((s) => {
          const count = counts[s] || 0;
          const pct = (count / total) * 100;
          if (pct === 0) return null;
          const palette = STAGE_COLORS[s] || 'gray';
          return (
            <Box
              key={s}
              w={`${pct}%`}
              bg={`${palette}.400`}
              display="flex"
              alignItems="center"
              justifyContent="center"
              title={`Stage ${s}: ${count} (${pct.toFixed(0)}%)`}
            >
              {pct > 4 && <Text fontSize="10px" fontWeight="bold" color="white">{s}</Text>}
            </Box>
          );
        })}
      </Box>
      <HStack gap={2} mt={1} flexWrap="wrap">
        {stages.map((s) => {
          const count = counts[s] || 0;
          return (
            <Badge key={s} size="sm" variant="subtle" colorPalette={STAGE_COLORS[s] || 'gray'}>
              {s}: {count} ({total > 0 ? ((count / total) * 100).toFixed(0) : 0}%)
            </Badge>
          );
        })}
      </HStack>
    </Box>
  );
};

const SetupCard: React.FC<{ title: string; items: SetupItem[]; showScore?: boolean }> = ({ title, items, showScore }) => (
  <Box borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={3} bg="bg.card" flex="1" minW="220px">
    <Text fontSize="sm" fontWeight="semibold" mb={2}>{title}</Text>
    {items.length === 0 ? (
      <Text fontSize="xs" color="fg.muted">None found</Text>
    ) : (
      <Box display="flex" flexDirection="column" gap={1}>
        {items.slice(0, 8).map((item) => (
          <HStack key={item.symbol} justify="space-between" fontSize="xs">
            <HStack gap={1}>
              <Text fontWeight="medium">{item.symbol}</Text>
              <Badge size="sm" variant="subtle" colorPalette={STAGE_COLORS[item.stage_label || ''] || 'gray'}>
                {item.stage_label || '?'}
              </Badge>
            </HStack>
            <HStack gap={2}>
              {showScore && item.momentum_score != null && (
                <Text color="fg.muted">{item.momentum_score.toFixed(1)}</Text>
              )}
              <Text color={heatColor(item.perf_20d)}>{fmtPct(item.perf_20d)}</Text>
              <Text color={heatColor(item.rs_mansfield_pct)}>RS {fmtPct(item.rs_mansfield_pct)}</Text>
            </HStack>
          </HStack>
        ))}
      </Box>
    )}
  </Box>
);

const TransitionList: React.FC<{ title: string; items: StageTransitionItem[]; colorPalette: string }> = ({ title, items, colorPalette }) => (
  <Box borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={3} bg="bg.card" flex="1" minW="220px">
    <HStack justify="space-between" align="center" mb={2}>
      <Text fontSize="sm" fontWeight="semibold">{title}</Text>
      <Badge variant="subtle" colorPalette={colorPalette}>{items.length}</Badge>
    </HStack>
    <Box maxH="280px" overflowY="auto" pr={1}>
      <Stack gap={1}>
        {items.length ? items.map((r) => (
          <HStack key={`trans-${r.symbol}`} justify="space-between" fontSize="xs">
            <Text fontWeight="medium">{r.symbol}</Text>
            <HStack gap={1}>
              <Badge variant="subtle" size="sm">
                {r.previous_stage_label || '—'} → {r.stage_label || '?'}
              </Badge>
              {r.current_stage_days != null && (
                <Text color="fg.muted">{r.current_stage_days}d</Text>
              )}
            </HStack>
          </HStack>
        )) : <Text fontSize="xs" color="fg.muted">No recent entries.</Text>}
      </Stack>
    </Box>
  </Box>
);

const RankMatrix: React.FC<{ title: string; data?: Record<string, Array<{ symbol: string; value: number }>> }> = ({ title, data }) => {
  const matrixRows = React.useMemo(() => {
    const maxLen = METRIC_ORDER.reduce(
      (acc, metric) => Math.max(acc, (data?.[metric.key] || []).length),
      0,
    );
    const count = Math.min(maxLen, 10);
    return Array.from({ length: count }, (_, idx) => idx);
  }, [data]);
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
            {matrixRows.map((idx) => (
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

/* ===== Main Component ===== */

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

  const regime = payload?.regime || {};
  const stageCounts = regime.stage_counts_normalized || {};
  const trackedCount = payload?.tracked_count || 0;
  const snapshotCount = payload?.snapshot_count || 0;
  const above50 = regime.above_sma50_count || 0;
  const above200 = regime.above_sma200_count || 0;
  const upCount = regime.up_1d_count || 0;
  const downCount = regime.down_1d_count || 0;
  const pctAbove50 = snapshotCount > 0 ? ((above50 / snapshotCount) * 100).toFixed(0) : '0';
  const pctAbove200 = snapshotCount > 0 ? ((above200 / snapshotCount) * 100).toFixed(0) : '0';
  const advDecRatio = downCount > 0 ? (upCount / downCount).toFixed(2) : upCount > 0 ? '∞' : '0';

  const sectorRows = payload?.sector_etf_table || [];
  const sectorMomentum = payload?.sector_momentum || [];
  const breakoutCandidates = payload?.setups?.breakout_candidates || [];
  const pullbackCandidates = payload?.setups?.pullback_candidates || [];
  const rsLeaders = payload?.setups?.rs_leaders || [];
  const leaders = payload?.leaders || [];
  const enteringStage2a = payload?.entering_stage_2a || [];
  const entering34 = [...(payload?.entering_stage_3 || []), ...(payload?.entering_stage_4 || [])];
  const entryRows = payload?.entry_proximity_top || [];
  const exitRows = payload?.exit_proximity_top || [];

  const regimeLabel = Number(pctAbove50) >= 60 ? 'Bullish' : Number(pctAbove50) <= 40 ? 'Bearish' : 'Neutral';
  const regimePalette = regimeLabel === 'Bullish' ? 'green' : regimeLabel === 'Bearish' ? 'red' : 'yellow';

  return (
    <Box p={4}>
      <Stack gap={4}>
        <HStack justify="space-between" align="end" flexWrap="wrap">
          <Box>
            <HStack gap={2} align="center">
              <Heading size="md">Market Dashboard</Heading>
              <Badge variant="solid" colorPalette={regimePalette} size="sm">{regimeLabel}</Badge>
            </HStack>
            <Text color="fg.muted" fontSize="sm">
              Market breadth, sector rotation, trading setups, and ranked metrics.
            </Text>
          </Box>
          <HStack gap={2}>
            <Badge variant="subtle">Tracked {trackedCount}</Badge>
            <Badge variant="subtle">Snapshots {snapshotCount}</Badge>
          </HStack>
        </HStack>

        {/* Section 1: Market Pulse */}
        <Box>
          <Text fontSize="sm" fontWeight="semibold" mb={2}>Market Pulse</Text>
          <Box display="flex" gap={2} flexWrap="wrap" mb={3}>
            <StatCard label="% Above 50DMA" value={`${pctAbove50}%`} sub={`${above50} / ${snapshotCount}`} />
            <StatCard label="% Above 200DMA" value={`${pctAbove200}%`} sub={`${above200} / ${snapshotCount}`} />
            <StatCard label="Advance / Decline" value={advDecRatio} sub={`${upCount} up · ${downCount} down`} />
            <StatCard label="Total Tracked" value={trackedCount} />
          </Box>
          <StageBar counts={stageCounts} total={snapshotCount} />
        </Box>

        {/* Section 2: Sector Rotation */}
        <Box>
          <Text fontSize="sm" fontWeight="semibold" mb={2}>Sector Rotation</Text>
          <Box display="grid" gridTemplateColumns={{ base: '1fr', xl: '1.6fr 0.4fr' }} gap={3}>
            <Box borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={3} bg="bg.card">
              <TableScrollArea borderWidth="1px" borderColor="border.subtle" borderRadius="md">
                <TableRoot size="sm">
                  <TableHeader>
                    <TableRow>
                      <TableColumnHeader>Sector</TableColumnHeader>
                      <TableColumnHeader>Stage</TableColumnHeader>
                      <TableColumnHeader>Days</TableColumnHeader>
                      <TableColumnHeader>1D%</TableColumnHeader>
                      <TableColumnHeader>5D%</TableColumnHeader>
                      <TableColumnHeader>20D%</TableColumnHeader>
                      <TableColumnHeader>RS</TableColumnHeader>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {sectorRows.map((r) => (
                      <TableRow key={`sector-${r.symbol}`}>
                        <TableCell>{r.sector_name || r.symbol}</TableCell>
                        <TableCell>
                          {r.stage_label ? (
                            <Badge size="sm" variant="subtle" colorPalette={STAGE_COLORS[r.stage_label] || 'gray'}>
                              {r.stage_label}
                            </Badge>
                          ) : '—'}
                        </TableCell>
                        <TableCell>{r.days_in_stage ?? '—'}</TableCell>
                        <TableCell><Text color={heatColor(r.change_1d)}>{fmtPct(r.change_1d)}</Text></TableCell>
                        <TableCell><Text color={heatColor(r.change_5d)}>{fmtPct(r.change_5d)}</Text></TableCell>
                        <TableCell><Text color={heatColor(r.change_20d)}>{fmtPct(r.change_20d)}</Text></TableCell>
                        <TableCell><Text color={heatColor(r.rs_mansfield_pct)}>{fmtPct(r.rs_mansfield_pct)}</Text></TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </TableRoot>
              </TableScrollArea>
            </Box>

            <Box borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={3} bg="bg.card">
              <Text fontSize="xs" fontWeight="semibold" mb={2}>Sector Momentum (by GICS)</Text>
              {sectorMomentum.length === 0 ? (
                <Text fontSize="xs" color="fg.muted">No data</Text>
              ) : (
                <Box display="flex" flexDirection="column" gap={1}>
                  {sectorMomentum.slice(0, 10).map((sm) => (
                    <HStack key={sm.sector} justify="space-between" fontSize="xs">
                      <Text truncate maxW="140px">{sm.sector}</Text>
                      <HStack gap={2}>
                        <Text color={heatColor(sm.avg_perf_20d)}>{fmtPct(sm.avg_perf_20d)}</Text>
                        <Text color="fg.muted">({sm.count})</Text>
                      </HStack>
                    </HStack>
                  ))}
                </Box>
              )}
            </Box>
          </Box>
        </Box>

        {/* Section 3: Trading Setups */}
        <Box>
          <Text fontSize="sm" fontWeight="semibold" mb={2}>Trading Setups</Text>
          <Box display="flex" gap={3} flexWrap="wrap">
            <SetupCard title="Breakout Candidates" items={breakoutCandidates} />
            <SetupCard title="Pullback Buys" items={pullbackCandidates} />
            <SetupCard title="RS Leaders" items={rsLeaders} />
            <SetupCard title="Momentum Leaders" items={leaders} showScore />
          </Box>
        </Box>

        {/* Section 4: Stage Transitions */}
        <Box>
          <Text fontSize="sm" fontWeight="semibold" mb={2}>Stage Transitions</Text>
          <Box display="flex" gap={3} flexWrap="wrap">
            <TransitionList title="Entering Stage 2A (Bullish)" items={enteringStage2a} colorPalette="green" />
            <TransitionList title="Entering Stage 3/4 (Warning)" items={entering34} colorPalette="red" />
          </Box>
        </Box>

        {/* Section 5: Ranked Metrics */}
        <RankMatrix title="Top 10 Matrix" data={payload?.top10_matrix} />
        <RankMatrix title="Bottom 10 Matrix" data={payload?.bottom10_matrix} />

        {/* Section 6: Entry/Exit Proximity */}
        <Box>
          <Text fontSize="sm" fontWeight="semibold" mb={2}>Entry / Exit Proximity</Text>
          <Box display="grid" gridTemplateColumns={{ base: '1fr', xl: '1fr 1fr' }} gap={3}>
            <Box borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={3} bg="bg.card">
              <Text fontSize="xs" fontWeight="semibold" mb={2}>Top 10 Closest to Entry</Text>
              <TableScrollArea borderWidth="1px" borderColor="border.subtle" borderRadius="md">
                <TableRoot size="sm">
                  <TableHeader>
                    <TableRow>
                      <TableColumnHeader>Symbol</TableColumnHeader>
                      <TableColumnHeader>Stage</TableColumnHeader>
                      <TableColumnHeader>Entry</TableColumnHeader>
                      <TableColumnHeader>Dist %</TableColumnHeader>
                      <TableColumnHeader>Dist ATR</TableColumnHeader>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {entryRows.slice(0, 10).length ? (
                      entryRows.slice(0, 10).map((r: any) => (
                        <TableRow key={`entry-${r.symbol}`}>
                          <TableCell>{r.symbol}</TableCell>
                          <TableCell>
                            <Badge size="sm" variant="subtle" colorPalette={STAGE_COLORS[r.stage_label] || 'gray'}>
                              {r.stage_label || '?'}
                            </Badge>
                          </TableCell>
                          <TableCell>{typeof r.entry_price === 'number' ? r.entry_price.toFixed(2) : '—'}</TableCell>
                          <TableCell>{typeof r.distance_pct === 'number' ? `${r.distance_pct.toFixed(2)}%` : '—'}</TableCell>
                          <TableCell>{typeof r.distance_atr === 'number' ? `${r.distance_atr.toFixed(2)}x` : '—'}</TableCell>
                        </TableRow>
                      ))
                    ) : (
                      <TableRow>
                        <TableCell colSpan={5}>
                          <Text fontSize="xs" color="fg.muted">
                            No entry prices set yet. Set Entry prices in Market Tracked.
                          </Text>
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </TableRoot>
              </TableScrollArea>
            </Box>

            <Box borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={3} bg="bg.card">
              <Text fontSize="xs" fontWeight="semibold" mb={2}>Top 10 Closest to Exit</Text>
              <TableScrollArea borderWidth="1px" borderColor="border.subtle" borderRadius="md">
                <TableRoot size="sm">
                  <TableHeader>
                    <TableRow>
                      <TableColumnHeader>Symbol</TableColumnHeader>
                      <TableColumnHeader>Stage</TableColumnHeader>
                      <TableColumnHeader>Exit</TableColumnHeader>
                      <TableColumnHeader>Dist %</TableColumnHeader>
                      <TableColumnHeader>Dist ATR</TableColumnHeader>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {exitRows.slice(0, 10).length ? (
                      exitRows.slice(0, 10).map((r: any) => (
                        <TableRow key={`exit-${r.symbol}`}>
                          <TableCell>{r.symbol}</TableCell>
                          <TableCell>
                            <Badge size="sm" variant="subtle" colorPalette={STAGE_COLORS[r.stage_label] || 'gray'}>
                              {r.stage_label || '?'}
                            </Badge>
                          </TableCell>
                          <TableCell>{typeof r.exit_price === 'number' ? r.exit_price.toFixed(2) : '—'}</TableCell>
                          <TableCell>{typeof r.distance_pct === 'number' ? `${r.distance_pct.toFixed(2)}%` : '—'}</TableCell>
                          <TableCell>{typeof r.distance_atr === 'number' ? `${r.distance_atr.toFixed(2)}x` : '—'}</TableCell>
                        </TableRow>
                      ))
                    ) : (
                      <TableRow>
                        <TableCell colSpan={5}>
                          <Text fontSize="xs" color="fg.muted">
                            No exit prices set yet. Set Exit prices in Market Tracked.
                          </Text>
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </TableRoot>
              </TableScrollArea>
            </Box>
          </Box>
        </Box>
      </Stack>
    </Box>
  );
};

export default MarketDashboard;
