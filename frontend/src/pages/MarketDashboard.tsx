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
import { Link as RouterLink } from 'react-router-dom';
import { useColorMode } from '../theme/colorMode';
import { marketDataApi } from '../services/api';
import { ChartContext, SymbolLink, ChartSlidePanel } from '../components/market/SymbolChartUI';
import StatCard from '../components/shared/StatCard';
import { usePortfolioSymbols, type PortfolioSymbolData } from '../hooks/usePortfolioSymbols';
import StageBar from '../components/shared/StageBar';
import StageBadge from '../components/shared/StageBadge';
import { useChartColors } from '../hooks/useChartColors';
import { SECTOR_PALETTE } from '../constants/chart';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip as RTooltip, ResponsiveContainer, Cell,
  ScatterChart, Scatter, ZAxis, CartesianGrid, ReferenceLine, ReferenceArea, Legend,
  ComposedChart, Area,
} from 'recharts';

type SetupItem = {
  symbol: string;
  stage_label?: string;
  previous_stage_label?: string;
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

type RangeHistogramBin = { bin: string; count: number };
type BreadthPoint = { date: string; above_sma50_pct: number; above_sma200_pct: number; total: number };
type RRGSector = { symbol: string; name: string; rs_ratio: number; rs_momentum: number };
type EarningsItem = { symbol: string; next_earnings: string; stage_label?: string; rs_mansfield_pct?: number; sector?: string };
type FundamentalLeader = { symbol: string; eps_growth_yoy: number; rs_mansfield_pct: number; pe_ttm?: number | null; stage_label?: string; sector?: string; composite_score: number };
type RSIDivergenceItem = { symbol: string; perf_20d: number; rsi: number; stage_label?: string; sector?: string };
type TDSignalItem = { symbol: string; signals: string[]; stage_label?: string; perf_1d?: number; sector?: string };
type GapLeader = { symbol: string; gaps_up: number; gaps_down: number; total_gaps: number; stage_label?: string; sector?: string };

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
  range_histogram?: RangeHistogramBin[];
  breadth_series?: BreadthPoint[];
  rrg_sectors?: RRGSector[];
  upcoming_earnings?: EarningsItem[];
  fundamental_leaders?: FundamentalLeader[];
  rsi_divergences?: { bearish?: RSIDivergenceItem[]; bullish?: RSIDivergenceItem[] };
  td_signals?: TDSignalItem[];
  gap_leaders?: GapLeader[];
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

const repeatSymbolColor = (symbol: string): string => {
  // Use a broad hue space so repeated symbols are visually distinct.
  let hash = 0;
  for (let i = 0; i < symbol.length; i += 1) {
    hash = (hash * 31 + symbol.charCodeAt(i)) >>> 0;
  }
  const hue = (hash * 137) % 360;
  return `hsl(${hue} 72% 58%)`;
};

/* ===== Sub-components (StatCard, StageBar from shared) ===== */

const SetupCard: React.FC<{ title: string; items: SetupItem[]; showScore?: boolean; linkPreset?: string; portfolioSymbols?: Record<string, PortfolioSymbolData> }> = ({ title, items, showScore, linkPreset, portfolioSymbols }) => (
  <Box borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={3} bg="bg.card" flex="1" minW="220px">
    <HStack justify="space-between" align="center" mb={2}>
      {linkPreset ? (
        <RouterLink to={`/market/tracked?preset=${linkPreset}`} style={{ textDecoration: 'none' }}>
          <Text fontSize="sm" fontWeight="semibold" _hover={{ textDecoration: 'underline' }} cursor="pointer">{title}</Text>
        </RouterLink>
      ) : (
        <Text fontSize="sm" fontWeight="semibold">{title}</Text>
      )}
      {items.length > 0 && <Badge variant="subtle" size="sm">{items.length}</Badge>}
    </HStack>
    {items.length === 0 ? (
      <Text fontSize="xs" color="fg.muted">None found</Text>
    ) : (
      <Box maxH="260px" overflowY="auto" pr={1}>
        <Box display="flex" flexDirection="column" gap={1}>
          {items.map((item) => (
            <HStack key={item.symbol} justify="space-between" fontSize="xs">
              <HStack gap={1}>
                <SymbolLink symbol={item.symbol} />
                {portfolioSymbols?.[item.symbol] && (
                  <Badge size="xs" colorPalette="blue" variant="subtle">Held</Badge>
                )}
                <StageBadge stage={item.stage_label || '?'} />
              </HStack>
              <HStack gap={2} flexShrink={0}>
                {showScore && item.momentum_score != null && (
                  <Text color="fg.muted">{item.momentum_score.toFixed(1)}</Text>
                )}
                <Text color={heatColor(item.perf_20d)}>{fmtPct(item.perf_20d)}</Text>
                <Text color={heatColor(item.rs_mansfield_pct)}>RS {fmtPct(item.rs_mansfield_pct)}</Text>
              </HStack>
            </HStack>
          ))}
        </Box>
      </Box>
    )}
  </Box>
);

const TransitionList: React.FC<{ title: string; items: StageTransitionItem[]; colorPalette: string; portfolioSymbols?: Record<string, PortfolioSymbolData> }> = ({ title, items, colorPalette, portfolioSymbols }) => {
  const symbolsParam = items.map((r) => r.symbol).join(',');
  const titleLink = symbolsParam ? `/market/tracked?symbols=${encodeURIComponent(symbolsParam)}` : undefined;
  return (
    <Box borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={3} bg="bg.card" flex="1" minW="220px">
      <HStack justify="space-between" align="center" mb={2}>
        {titleLink ? (
          <RouterLink to={titleLink} style={{ textDecoration: 'none' }}>
            <Text fontSize="sm" fontWeight="semibold" _hover={{ textDecoration: 'underline' }} cursor="pointer">{title}</Text>
          </RouterLink>
        ) : (
          <Text fontSize="sm" fontWeight="semibold">{title}</Text>
        )}
        <Badge variant="subtle" colorPalette={colorPalette}>{items.length}</Badge>
      </HStack>
      <Box maxH="280px" overflowY="auto" pr={1}>
        <Stack gap={1}>
          {items.length ? items.map((r) => (
            <HStack key={`trans-${r.symbol}`} justify="space-between" fontSize="xs">
              <HStack gap={1}>
                <SymbolLink symbol={r.symbol} />
                {portfolioSymbols?.[r.symbol] && (
                  <Badge size="xs" colorPalette="blue" variant="subtle">Held</Badge>
                )}
              </HStack>
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
};

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
                        as="span"
                        fontWeight={hasRepeat ? 'bold' : undefined}
                        color={hasRepeat ? repeatSymbolColor(symbol) : undefined}
                        data-testid={
                          hasRepeat
                            ? `repeat-text-${title.replace(/\s+/g, '-').toLowerCase()}`
                            : undefined
                        }
                      >
                        <SymbolLink symbol={item.symbol} /> <Text as="span" fontSize="xs" color="fg.muted">({fmtValue(item.value, m.key)})</Text>
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

const RangeHistogram: React.FC<{ bins: RangeHistogramBin[] }> = ({ bins }) => {
  const cc = useChartColors();
  const data = bins.map((b) => {
    const isLow = b.bin.startsWith('0-') || b.bin.startsWith('10-');
    const isHigh = b.bin.startsWith('80-') || b.bin.startsWith('90-');
    return {
      name: b.bin.replace('%', ''),
      count: b.count,
      fill: isLow ? cc.danger : isHigh ? cc.success : cc.neutral,
    };
  });
  return (
    <Box borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={4} bg="bg.card">
      <Text fontSize="sm" fontWeight="semibold" mb={2}>52-Week Range Distribution</Text>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 4 }}>
          <XAxis
            dataKey="name"
            tick={{ fontSize: 9, fill: cc.muted }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v) => `${v}%`}
          />
          <YAxis hide />
          <RTooltip
            contentStyle={{ fontSize: 12, borderRadius: 8, border: `1px solid ${cc.border}` }}
            formatter={(value) => [`${value} symbols`, 'Count']}
          />
          <Bar dataKey="count" radius={[4, 4, 0, 0]} maxBarSize={36}>
            {data.map((entry, i) => (
              <Cell key={i} fill={entry.fill} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <Text fontSize="xs" color="fg.muted" textAlign="center" mt={1}>Left-skew = capitulation · Right-skew = euphoria</Text>
    </Box>
  );
};

const BreadthChart: React.FC<{ series: BreadthPoint[] }> = ({ series }) => {
  const cc = useChartColors();
  if (!series.length) return null;
  const fmtDate = (raw: string) => {
    const d = new Date(raw);
    if (isNaN(d.getTime())) return raw.slice(5, 10);
    return `${String(d.getMonth() + 1).padStart(2, '0')}/${String(d.getDate()).padStart(2, '0')}`;
  };
  const data = series.map((pt) => ({
    date: fmtDate(pt.date),
    sma50: pt.above_sma50_pct,
    sma200: pt.above_sma200_pct,
  }));

  const latest50 = data.length ? data[data.length - 1].sma50 : null;
  const latest200 = data.length ? data[data.length - 1].sma200 : null;

  return (
    <Box borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={4} bg="bg.card">
      <HStack justify="space-between" align="baseline" mb={2}>
        <Text fontSize="sm" fontWeight="semibold">Breadth Over Time</Text>
        <HStack gap={3}>
          {latest50 != null && (
            <HStack gap={1}>
              <Box w="8px" h="3px" borderRadius="full" bg={cc.area1} />
              <Text fontSize="10px" color="fg.muted">&gt;50DMA <Text as="span" fontWeight="semibold" color="fg.default">{latest50.toFixed(0)}%</Text></Text>
            </HStack>
          )}
          {latest200 != null && (
            <HStack gap={1}>
              <Box w="8px" h="3px" borderRadius="full" bg={cc.area2} />
              <Text fontSize="10px" color="fg.muted">&gt;200DMA <Text as="span" fontWeight="semibold" color="fg.default">{latest200.toFixed(0)}%</Text></Text>
            </HStack>
          )}
        </HStack>
      </HStack>
      <ResponsiveContainer width="100%" height={200}>
        <ComposedChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="grad50" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={cc.area1} stopOpacity={0.25} />
              <stop offset="95%" stopColor={cc.area1} stopOpacity={0.02} />
            </linearGradient>
            <linearGradient id="grad200" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={cc.area2} stopOpacity={0.2} />
              <stop offset="95%" stopColor={cc.area2} stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <XAxis
            dataKey="date"
            tick={{ fontSize: 9, fill: cc.muted }}
            tickLine={false}
            axisLine={false}
            interval={Math.max(0, Math.floor(data.length / 5))}
          />
          <YAxis hide domain={[0, 100]} />
          <ReferenceLine y={50} stroke={cc.refLine} strokeDasharray="4 3" label={{ value: '50%', position: 'insideTopLeft', fontSize: 9, fill: cc.muted }} />
          <RTooltip
            contentStyle={{ fontSize: 12, borderRadius: 8, border: `1px solid ${cc.border}` }}
            formatter={(value, name) => [`${Number(value).toFixed(1)}%`, String(name) === 'sma50' ? '% > 50DMA' : '% > 200DMA']}
          />
          <Area type="monotone" dataKey="sma200" fill="url(#grad200)" stroke={cc.area2} strokeWidth={1.5} />
          <Area type="monotone" dataKey="sma50" fill="url(#grad50)" stroke={cc.area1} strokeWidth={2} />
        </ComposedChart>
      </ResponsiveContainer>
    </Box>
  );
};

const RRGCustomTooltip: React.FC<any> = ({ active, payload }) => {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  const quad = d.rs_ratio >= 0
    ? d.rs_momentum >= 0 ? 'Leading' : 'Weakening'
    : d.rs_momentum >= 0 ? 'Improving' : 'Lagging';
  return (
    <Box bg="bg.panel" borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={3} shadow="md" minW="160px">
      <HStack gap={2} mb={1}>
        <Box w="10px" h="10px" borderRadius="full" bg={SECTOR_PALETTE[d._idx % SECTOR_PALETTE.length]} />
        <Text fontSize="sm" fontWeight="bold">{d.name}</Text>
      </HStack>
      <Text fontSize="xs" color="fg.muted">{d.symbol}</Text>
      <Box mt={2} display="flex" flexDirection="column" gap={1}>
        <HStack justify="space-between" fontSize="xs">
          <Text color="fg.muted">RS-Ratio</Text>
          <Text fontWeight="medium">{d.rs_ratio.toFixed(2)}</Text>
        </HStack>
        <HStack justify="space-between" fontSize="xs">
          <Text color="fg.muted">RS-Momentum</Text>
          <Text fontWeight="medium">{d.rs_momentum.toFixed(2)}</Text>
        </HStack>
        <HStack justify="space-between" fontSize="xs">
          <Text color="fg.muted">Quadrant</Text>
          <Text fontWeight="medium">{quad}</Text>
        </HStack>
      </Box>
    </Box>
  );
};

const RRGChart: React.FC<{ sectors: RRGSector[] }> = ({ sectors }) => {
  const cc = useChartColors();
  if (!sectors.length) return null;
  const data = sectors.map((s, i) => ({
    ...s,
    z: 200,
    _idx: i,
  }));

  const maxAbs = Math.max(
    ...sectors.map((s) => Math.abs(s.rs_ratio)),
    ...sectors.map((s) => Math.abs(s.rs_momentum)),
    1,
  );
  const pad = Math.ceil(maxAbs * 1.15) || 5;

  return (
    <Box borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={4} bg="bg.card" h="100%" display="flex" flexDirection="column" minH="520px">
      <Text fontSize="sm" fontWeight="semibold" mb={1}>Relative Rotation Graph (Sectors)</Text>
      <Text fontSize="xs" color="fg.muted" mb={2}>Hover each dot to see sector details</Text>
      <Box flex={1} minH="380px" w="100%">
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart>
          <CartesianGrid strokeDasharray="3 3" stroke={cc.grid} />
          <XAxis
            type="number"
            dataKey="rs_ratio"
            name="RS-Ratio"
            domain={[-pad, pad]}
            hide
          />
          <YAxis
            type="number"
            dataKey="rs_momentum"
            name="RS-Momentum"
            domain={[-pad, pad]}
            hide
          />
          <ZAxis type="number" dataKey="z" range={[160, 160]} />
          <ReferenceArea x1={0} x2={pad} y1={0} y2={pad} fill={cc.success} fillOpacity={0.05} label={{ value: 'Leading ↗', position: 'insideTopRight', fontSize: 11, fill: cc.success, fontWeight: 600 }} />
          <ReferenceArea x1={-pad} x2={0} y1={0} y2={pad} fill={cc.area2} fillOpacity={0.05} label={{ value: '↖ Improving', position: 'insideTopLeft', fontSize: 11, fill: cc.neutral, fontWeight: 600 }} />
          <ReferenceArea x1={-pad} x2={0} y1={-pad} y2={0} fill={cc.danger} fillOpacity={0.05} label={{ value: '↙ Lagging', position: 'insideBottomLeft', fontSize: 11, fill: cc.danger, fontWeight: 600 }} />
          <ReferenceArea x1={0} x2={pad} y1={-pad} y2={0} fill={cc.warning} fillOpacity={0.05} label={{ value: 'Weakening ↘', position: 'insideBottomRight', fontSize: 11, fill: cc.warning, fontWeight: 600 }} />
          <ReferenceLine x={0} stroke={cc.refLine} strokeWidth={1.5} />
          <ReferenceLine y={0} stroke={cc.refLine} strokeWidth={1.5} />
          <RTooltip content={<RRGCustomTooltip />} cursor={false} />
          <Scatter data={data}>
            {data.map((entry, i) => (
              <Cell key={i} fill={SECTOR_PALETTE[i % SECTOR_PALETTE.length]} stroke="white" strokeWidth={1.5} />
            ))}
          </Scatter>
          </ScatterChart>
        </ResponsiveContainer>
      </Box>
      <Box display="grid" gridTemplateColumns="repeat(auto-fill, minmax(130px, 1fr))" gap="3px" mt={2} px={1} flexShrink={0}>
        {data.map((s, i) => (
          <HStack key={s.symbol} gap={1}>
            <Box w="8px" h="8px" borderRadius="full" flexShrink={0} bg={SECTOR_PALETTE[i % SECTOR_PALETTE.length]} />
            <Text fontSize="10px" truncate color="fg.muted">{s.name}</Text>
          </HStack>
        ))}
      </Box>
    </Box>
  );
};

/* ===== Main Component ===== */

const MarketDashboard: React.FC = () => {
  const [payload, setPayload] = React.useState<DashboardPayload | null>(null);
  const [loading, setLoading] = React.useState<boolean>(true);
  const [error, setError] = React.useState<string | null>(null);
  const [chartSymbol, setChartSymbol] = React.useState<string | null>(null);
  const openChart = React.useCallback((sym: string) => setChartSymbol(sym), []);
  const portfolioQuery = usePortfolioSymbols();
  const portfolioSymbols = portfolioQuery.data ?? {};

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

  const actionQueue = payload?.action_queue || [];

  const regimeLabel = Number(pctAbove50) >= 60 ? 'Bullish' : Number(pctAbove50) <= 40 ? 'Bearish' : 'Neutral';
  const regimePalette = regimeLabel === 'Bullish' ? 'green' : regimeLabel === 'Bearish' ? 'red' : 'yellow';

  return (
    <ChartContext.Provider value={openChart}>
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

        {/* Action Queue */}
        {actionQueue.length > 0 && (
          <Box>
            <HStack mb={2} gap={2} align="center">
              <Text fontSize="sm" fontWeight="semibold">Action Queue</Text>
              <Badge variant="subtle" size="sm">{actionQueue.length}</Badge>
            </HStack>
            <Box borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={3} bg="bg.card" maxH="340px" overflowY="auto">
              <Box display="grid" gridTemplateColumns={{ base: '1fr', xl: '1fr 1fr' }} gap={1} columnGap={4}>
                {actionQueue.map((item) => {
                  const reasons: string[] = [];
                  if (item.previous_stage_label && item.previous_stage_label !== item.stage_label) {
                    reasons.push(`${item.previous_stage_label} → ${item.stage_label}`);
                  }
                  if (typeof item.perf_1d === 'number' && Math.abs(item.perf_1d) >= 3) {
                    reasons.push(`1D ${item.perf_1d > 0 ? '+' : ''}${item.perf_1d.toFixed(1)}%`);
                  }
                  if (typeof item.rs_mansfield_pct === 'number' && Math.abs(item.rs_mansfield_pct) >= 6) {
                    reasons.push(`RS ${item.rs_mansfield_pct > 0 ? '+' : ''}${item.rs_mansfield_pct.toFixed(1)}%`);
                  }
                  return (
                      <HStack key={`aq-${item.symbol}`} justify="space-between" fontSize="xs" py="2px" borderBottomWidth="1px" borderColor="border.subtle">
                      <HStack gap={1} minW="80px">
                        <SymbolLink symbol={item.symbol} />
                        {portfolioSymbols[item.symbol] && (
                          <Badge size="xs" colorPalette="blue" variant="subtle">Held</Badge>
                        )}
                        <StageBadge stage={item.stage_label || '?'} />
                      </HStack>
                      <HStack gap={1} flexShrink={0}>
                        {reasons.map((r, i) => (
                          <Text key={i} fontSize="xs" color="fg.muted">{r}</Text>
                        ))}
                        {item.sector && <Text color="fg.subtle" fontSize="xs" truncate maxW="100px">{item.sector}</Text>}
                      </HStack>
                    </HStack>
                  );
                })}
              </Box>
            </Box>
          </Box>
        )}

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
                            <StageBadge stage={r.stage_label} />
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
          <Box display="grid" gridTemplateColumns={{ base: '1fr', md: '1fr 1fr', xl: '1fr 1fr 1fr 1fr' }} gap={3}>
            <SetupCard title="Breakout Candidates" items={breakoutCandidates} linkPreset="breakout" portfolioSymbols={portfolioSymbols} />
            <SetupCard title="Pullback Buys" items={pullbackCandidates} linkPreset="pullback" portfolioSymbols={portfolioSymbols} />
            <SetupCard title="RS Leaders" items={rsLeaders} linkPreset="rs_leaders" portfolioSymbols={portfolioSymbols} />
            <SetupCard title="Momentum Leaders" items={leaders} showScore linkPreset="momentum" portfolioSymbols={portfolioSymbols} />
          </Box>
        </Box>

        {/* Section 4: Stage Transitions */}
        <Box>
          <Text fontSize="sm" fontWeight="semibold" mb={2}>Stage Transitions</Text>
          <Box display="grid" gridTemplateColumns={{ base: '1fr', md: '1fr 1fr' }} gap={3}>
            <TransitionList title="Entering Stage 2A (Bullish)" items={enteringStage2a} colorPalette="green" portfolioSymbols={portfolioSymbols} />
            <TransitionList title="Entering Stage 3/4 (Warning)" items={entering34} colorPalette="red" portfolioSymbols={portfolioSymbols} />
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
                            <StageBadge stage={r.stage_label || '?'} />
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
                            <StageBadge stage={r.stage_label || '?'} />
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
        {/* Market Insights */}
        <Box>
          <Text fontSize="sm" fontWeight="semibold" mb={2}>Market Insights</Text>
          <Box display="grid" gridTemplateColumns={{ base: '1fr', lg: '1fr 1fr' }} gap={3}>
            <Box display="flex" flexDirection="column" gap={3}>
              {(payload?.range_histogram || []).length > 0 && (
                <RangeHistogram bins={payload!.range_histogram!} />
              )}
              {(payload?.breadth_series || []).length > 0 && (
                <BreadthChart series={payload!.breadth_series!} />
              )}
            </Box>
            {(payload?.rrg_sectors || []).length > 0 && (
              <RRGChart sectors={payload!.rrg_sectors!} />
            )}
          </Box>
        </Box>

        {/* Signals & Divergences */}
        <Box>
          <Text fontSize="sm" fontWeight="semibold" mb={2}>Signals & Divergences</Text>
          <Box display="grid" gridTemplateColumns={{ base: '1fr', lg: '1fr 1fr 1fr' }} gap={3}>
            <Box borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={3} bg="bg.card">
              <Text fontSize="xs" fontWeight="semibold" mb={2}>Divergence Watch</Text>
              {((payload?.rsi_divergences?.bearish || []).length + (payload?.rsi_divergences?.bullish || []).length) === 0 ? (
                <Text fontSize="xs" color="fg.muted">No divergences detected</Text>
              ) : (
                <Box maxH="300px" overflowY="auto" pr={1}>
                  <Box display="flex" flexDirection="column" gap={2}>
                    {(payload?.rsi_divergences?.bearish || []).length > 0 && (
                      <Box>
                        <Badge size="sm" variant="subtle" colorPalette="red" mb={1}>Bearish ({payload!.rsi_divergences!.bearish!.length})</Badge>
                        {payload!.rsi_divergences!.bearish!.map((d) => (
                          <HStack key={`div-b-${d.symbol}`} justify="space-between" fontSize="xs" py="1px">
                            <SymbolLink symbol={d.symbol} />
                            <HStack gap={2}>
                              <Text color="green.400">+{d.perf_20d}%</Text>
                              <Text color="red.400">RSI {d.rsi}</Text>
                            </HStack>
                          </HStack>
                        ))}
                      </Box>
                    )}
                    {(payload?.rsi_divergences?.bullish || []).length > 0 && (
                      <Box>
                        <Badge size="sm" variant="subtle" colorPalette="green" mb={1}>Bullish ({payload!.rsi_divergences!.bullish!.length})</Badge>
                        {payload!.rsi_divergences!.bullish!.map((d) => (
                          <HStack key={`div-l-${d.symbol}`} justify="space-between" fontSize="xs" py="1px">
                            <SymbolLink symbol={d.symbol} />
                            <HStack gap={2}>
                              <Text color="red.400">{d.perf_20d}%</Text>
                              <Text color="green.400">RSI {d.rsi}</Text>
                            </HStack>
                          </HStack>
                        ))}
                      </Box>
                    )}
                  </Box>
                </Box>
              )}
            </Box>

            <Box borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={3} bg="bg.card">
              <HStack justify="space-between" mb={1}>
                <Text fontSize="xs" fontWeight="semibold">TD Sequential Signals</Text>
                {(payload?.td_signals || []).length > 0 && <Badge variant="subtle" size="sm">{payload!.td_signals!.length}</Badge>}
              </HStack>
              <Text fontSize="xs" color="fg.muted" mb={2}>Setup 9 = potential reversal. Countdown 13 = exhaustion confirmed.</Text>
              {(payload?.td_signals || []).length === 0 ? (
                <Text fontSize="xs" color="fg.muted">No active signals</Text>
              ) : (
                <Box maxH="300px" overflowY="auto">
                  <Box display="grid" gridTemplateColumns={{ base: '1fr', xl: '1fr 1fr' }} gap={1} columnGap={3}>
                    {payload!.td_signals!.map((s) => (
                      <HStack key={`td-${s.symbol}`} justify="space-between" fontSize="xs" py="1px" borderBottomWidth="1px" borderColor="border.subtle">
                        <HStack gap={1}>
                          <SymbolLink symbol={s.symbol} />
                          <StageBadge stage={s.stage_label || '?'} />
                        </HStack>
                        <HStack gap={1} flexShrink={0}>
                          {s.signals.map((sig, i) => (
                            <Badge key={i} size="sm" variant="outline" colorPalette={sig.includes('Buy') ? 'green' : 'red'}>{sig}</Badge>
                          ))}
                        </HStack>
                      </HStack>
                    ))}
                  </Box>
                </Box>
              )}
            </Box>

            <Box borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={3} bg="bg.card">
              <HStack justify="space-between" mb={2}>
                <Text fontSize="xs" fontWeight="semibold">Open Gaps</Text>
                {(payload?.gap_leaders || []).length > 0 && <Badge variant="subtle" size="sm">{payload!.gap_leaders!.length}</Badge>}
              </HStack>
              <Text fontSize="xs" color="fg.muted" mb={2}>Symbols with unfilled price gaps (potential support/resistance).</Text>
              {(payload?.gap_leaders || []).length === 0 ? (
                <Text fontSize="xs" color="fg.subtle">No unfilled gaps detected. Gap data populates after indicator computation runs.</Text>
              ) : (
                <Box maxH="300px" overflowY="auto">
                  <Box display="flex" flexDirection="column" gap={1}>
                    {payload!.gap_leaders!.map((g) => (
                      <HStack key={`gap-${g.symbol}`} justify="space-between" fontSize="xs" py="1px" borderBottomWidth="1px" borderColor="border.subtle">
                        <HStack gap={1}>
                          <SymbolLink symbol={g.symbol} />
                          <StageBadge stage={g.stage_label || '?'} />
                        </HStack>
                        <HStack gap={2} flexShrink={0}>
                          <Text color="green.400">{g.gaps_up}↑</Text>
                          <Text color="red.400">{g.gaps_down}↓</Text>
                        </HStack>
                      </HStack>
                    ))}
                  </Box>
                </Box>
              )}
            </Box>
          </Box>
        </Box>

        {/* Earnings & Fundamentals */}
        <Box>
          <Text fontSize="sm" fontWeight="semibold" mb={2}>Earnings & Fundamentals</Text>
          <Box display="grid" gridTemplateColumns={{ base: '1fr', lg: '1fr 1fr' }} gap={3}>
            <Box borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={3} bg="bg.card">
              <Text fontSize="xs" fontWeight="semibold" mb={2}>Upcoming Earnings (7d)</Text>
              {(payload?.upcoming_earnings || []).length === 0 ? (
                <Text fontSize="xs" color="fg.muted">No upcoming earnings</Text>
              ) : (
                <Box maxH="260px" overflowY="auto" pr={1}>
                  <Box display="flex" flexDirection="column" gap={1}>
                    {payload!.upcoming_earnings!.map((e) => (
                      <HStack key={`earn-${e.symbol}`} justify="space-between" fontSize="xs">
                        <HStack gap={1}>
                          <SymbolLink symbol={e.symbol} />
                          <StageBadge stage={e.stage_label || '?'} />
                        </HStack>
                        <Text color="fg.muted">{new Date(e.next_earnings).toLocaleDateString()}</Text>
                      </HStack>
                    ))}
                  </Box>
                </Box>
              )}
            </Box>

            <Box borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={3} bg="bg.card">
              <Text fontSize="xs" fontWeight="semibold" mb={2}>Fundamental Leaders</Text>
              {(payload?.fundamental_leaders || []).length === 0 ? (
                <Text fontSize="xs" color="fg.muted">Insufficient data</Text>
              ) : (
                <Box maxH="260px" overflowY="auto" pr={1}>
                  <Box display="flex" flexDirection="column" gap={1}>
                    {payload!.fundamental_leaders!.map((f) => (
                      <HStack key={`fund-${f.symbol}`} justify="space-between" fontSize="xs">
                        <HStack gap={1}>
                          <SymbolLink symbol={f.symbol} />
                          <StageBadge stage={f.stage_label || '?'} />
                        </HStack>
                        <HStack gap={2} flexShrink={0}>
                          <Text>EPS {f.eps_growth_yoy > 0 ? '+' : ''}{f.eps_growth_yoy}%</Text>
                          <Text color={heatColor(f.rs_mansfield_pct)}>RS {fmtPct(f.rs_mansfield_pct)}</Text>
                          {f.pe_ttm != null && <Text color="fg.muted">PE {f.pe_ttm}</Text>}
                        </HStack>
                      </HStack>
                    ))}
                  </Box>
                </Box>
              )}
            </Box>
          </Box>
        </Box>
      </Stack>
      <ChartSlidePanel symbol={chartSymbol} onClose={() => setChartSymbol(null)} />
    </Box>
    </ChartContext.Provider>
  );
};

export default MarketDashboard;
