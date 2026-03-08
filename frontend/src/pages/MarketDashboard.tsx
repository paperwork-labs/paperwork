import React from 'react';
import {
  Badge,
  Box,
  Button,
  Collapsible,
  Heading,
  HStack,
  IconButton,
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
import { FiChevronDown, FiChevronRight, FiRefreshCw } from 'react-icons/fi';
import { marketDataApi } from '../services/api';
import { ChartContext, SymbolLink, ChartSlidePanel, PortfolioSymbolsContext } from '../components/market/SymbolChartUI';
import StatCard from '../components/shared/StatCard';
import { usePortfolioSymbols } from '../hooks/usePortfolioSymbols';
import StageBar from '../components/shared/StageBar';
import StageBadge from '../components/shared/StageBadge';
import { useChartColors } from '../hooks/useChartColors';
import { SECTOR_PALETTE, heatColor } from '../constants/chart';
import { ETF_SYMBOL_SET } from '../constants/etf';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip as RTooltip, ResponsiveContainer, Cell,
  ScatterChart, Scatter, ZAxis, CartesianGrid, ReferenceLine, ReferenceArea, Legend,
  ComposedChart, Area,
} from 'recharts';
import BubbleChart from '../components/charts/BubbleChart';
import api from '../services/api';
import { formatDate } from '../utils/format';
import { useUserPreferences } from '../hooks/useUserPreferences';

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
  latest_snapshot_at?: string;
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
  constituent_symbols?: string[];
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

const SetupCard: React.FC<{ title: string; items: SetupItem[]; showScore?: boolean; linkPreset?: string; showHeldBadge?: boolean }> = ({ title, items, showScore, linkPreset, showHeldBadge = true }) => (
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
          {items.map((item, i) => (
            <HStack key={`setup-${item.symbol}-${i}`} justify="space-between" fontSize="xs">
              <HStack gap={1}>
                <SymbolLink symbol={item.symbol} showHeldBadge={showHeldBadge} />
                <StageBadge stage={item.stage_label || '?'} />
              </HStack>
              <HStack gap={2} flexShrink={0}>
                {showScore && item.momentum_score != null && (
                  <Text color={heatColor(item.momentum_score)}>{item.momentum_score.toFixed(1)}</Text>
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

const TransitionList: React.FC<{ title: string; items: StageTransitionItem[]; colorPalette: string; showHeldBadge?: boolean }> = ({ title, items, colorPalette, showHeldBadge = true }) => {
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
          {items.length ? items.map((r, i) => (
            <HStack key={`trans-${r.symbol}-${i}`} justify="space-between" fontSize="xs">
              <SymbolLink symbol={r.symbol} showHeldBadge={showHeldBadge} />
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
        <ResponsiveContainer width="100%" height={400}>
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
          <HStack key={`rrg-${s.symbol}-${i}`} gap={1}>
            <Box w="8px" h="8px" borderRadius="full" flexShrink={0} bg={SECTOR_PALETTE[i % SECTOR_PALETTE.length]} />
            <Text fontSize="10px" truncate color="fg.muted">{s.name}</Text>
          </HStack>
        ))}
      </Box>
    </Box>
  );
};

/* ===== Volatility Regime ===== */

type VolData = {
  vix: number | null;
  vvix: number | null;
  vix3m: number | null;
  term_structure_ratio: number | null;
  vol_of_vol_ratio: number | null;
  regime: string;
  signal: string;
};

const REGIME_COLORS: Record<string, { palette: string; label: string }> = {
  calm:     { palette: 'green',  label: 'Calm' },
  elevated: { palette: 'yellow', label: 'Elevated' },
  fear:     { palette: 'orange', label: 'Fear' },
  extreme:  { palette: 'red',    label: 'Extreme' },
  unknown:  { palette: 'gray',   label: 'Unknown' },
};

const GaugeBar: React.FC<{
  label: string;
  value: number | null;
  min: number;
  max: number;
  zones: { end: number; color: string; label: string }[];
}> = ({ label, value, min, max, zones }) => {
  const range = max - min;
  const pct = value != null ? Math.max(0, Math.min(100, ((value - min) / range) * 100)) : null;

  return (
    <Box>
      <HStack justify="space-between" mb="2px">
        <Text fontSize="xs" fontWeight="medium">{label}</Text>
        <Text fontSize="xs" color="fg.muted">{value != null ? value.toFixed(2) : '—'}</Text>
      </HStack>
      <Box position="relative" h="14px" borderRadius="md" overflow="hidden" display="flex">
        {zones.map((zone, i) => {
          const start = i === 0 ? min : zones[i - 1].end;
          const width = ((zone.end - start) / range) * 100;
          return (
            <Box
              key={i}
              h="100%"
              w={`${width}%`}
              bg={zone.color}
              opacity={0.25}
              position="relative"
            />
          );
        })}
        {pct != null && (
          <Box
            position="absolute"
            left={`${pct}%`}
            top="0"
            bottom="0"
            w="3px"
            bg="fg"
            borderRadius="sm"
            transform="translateX(-50%)"
            zIndex={1}
          />
        )}
      </Box>
      <HStack justify="space-between" mt="1px">
        {zones.map((zone, i) => (
          <Text key={i} fontSize="9px" color="fg.subtle">{zone.label}</Text>
        ))}
      </HStack>
    </Box>
  );
};

const VolatilityRegime: React.FC<{ data: VolData | null }> = ({ data }) => {
  if (!data || data.regime === 'unknown') return null;
  const rc = REGIME_COLORS[data.regime] || REGIME_COLORS.unknown;

  return (
    <Box borderWidth="1px" borderColor="border.subtle" borderRadius="lg" bg="bg.card" p={3}>
      <HStack justify="space-between" mb={2}>
        <Text fontSize="sm" fontWeight="semibold">Volatility Regime</Text>
        <HStack gap={2}>
          {data.vix != null && <Text fontSize="xs" color="fg.muted">VIX {data.vix.toFixed(1)}</Text>}
          <Badge variant="subtle" colorPalette={rc.palette} size="sm">{rc.label}</Badge>
        </HStack>
      </HStack>
      <Stack gap={2}>
        <GaugeBar
          label="Term Structure (VIX3M / VIX)"
          value={data.term_structure_ratio}
          min={0.8}
          max={1.4}
          zones={[
            { end: 1.0,  color: 'red',    label: 'Backwardation' },
            { end: 1.15, color: 'green',  label: 'Normal' },
            { end: 1.4,  color: 'orange', label: 'Overbought' },
          ]}
        />
        <GaugeBar
          label="Vol-of-Vol (VVIX / VIX)"
          value={data.vol_of_vol_ratio}
          min={2.0}
          max={8.0}
          zones={[
            { end: 3.5, color: 'green',  label: 'Buy Protection' },
            { end: 6.0, color: 'gray',   label: 'Neutral' },
            { end: 8.0, color: 'red',    label: 'Sell Protection' },
          ]}
        />
      </Stack>
      {data.signal && (
        <Text fontSize="xs" color="fg.muted" mt={2} fontStyle="italic">{data.signal}</Text>
      )}
    </Box>
  );
};

/* ===== Section visibility & collapse ===== */

type UniverseFilter = 'all' | 'etf' | 'holdings';

const SECTION_VIS = {
  all:      { pulse: true,  actionQueue: true,  sectorRotation: true,  scatter: true,  setups: true,  transitions: true,  ranked: true,  proximity: true,  insights: true,  signals: true,  earnings: true  },
  etf:      { pulse: true,  actionQueue: false, sectorRotation: true,  scatter: true,  setups: false, transitions: false, ranked: false, proximity: true,  insights: true,  signals: false, earnings: false },
  holdings: { pulse: false, actionQueue: true,  sectorRotation: false, scatter: false, setups: true,  transitions: true,  ranked: false, proximity: true,  insights: false, signals: true,  earnings: true  },
} as const;

const MODE_DESCRIPTIONS: Record<UniverseFilter, string> = {
  all: 'S&P 500, NASDAQ 100, and DOW 30 -- broad market scanning for entries and exits',
  etf: 'Sector and thematic ETFs -- rotation and relative strength analysis',
  holdings: 'Your portfolio positions -- signals, setups, and earnings alerts',
};

const COLLAPSE_KEY = 'axiomfolio:dashboard:collapsed';

function useSectionCollapse() {
  const [collapsed, setCollapsed] = React.useState<Set<string>>(() => {
    try {
      const stored = localStorage.getItem(COLLAPSE_KEY);
      return stored ? new Set(JSON.parse(stored) as string[]) : new Set<string>();
    } catch { return new Set<string>(); }
  });

  const toggle = React.useCallback((key: string) => {
    setCollapsed(prev => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      try { localStorage.setItem(COLLAPSE_KEY, JSON.stringify([...next])); } catch {}
      return next;
    });
  }, []);

  return { collapsed, toggle };
}

const SectionHeading: React.FC<{
  title: string;
  sectionKey: string;
  isCollapsed: boolean;
  onToggle: () => void;
  count?: number;
}> = ({ title, sectionKey, isCollapsed, onToggle, count }) => (
  <HStack
    cursor="pointer"
    onClick={onToggle}
    tabIndex={0}
    onKeyDown={(e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        onToggle();
      }
    }}
    gap={2}
    mb={isCollapsed ? 0 : 2}
    role="button"
    aria-expanded={!isCollapsed}
    aria-controls={`section-${sectionKey}`}
    _hover={{ opacity: 0.8 }}
    userSelect="none"
  >
    {isCollapsed ? <FiChevronRight size={14} /> : <FiChevronDown size={14} />}
    <Text fontSize="sm" fontWeight="semibold">{title}</Text>
    {count != null && count > 0 && <Badge variant="subtle" size="sm">{count}</Badge>}
  </HStack>
);

const EmptyState: React.FC<{ mode: UniverseFilter; noun?: string }> = ({ mode, noun = 'items' }) => (
  <Text fontSize="sm" color="fg.muted" py={4} textAlign="center">
    No {noun} for {MODE_DESCRIPTIONS[mode].toLowerCase()}
  </Text>
);

/* ===== Main Component ===== */

const UNIVERSE_FILTER_KEY = 'axiomfolio:market-dashboard:universe-filter';

const MarketDashboard: React.FC = () => {
  const { timezone } = useUserPreferences();
  const [payload, setPayload] = React.useState<DashboardPayload | null>(null);
  const [loading, setLoading] = React.useState<boolean>(true);
  const [error, setError] = React.useState<string | null>(null);
  const [chartSymbol, setChartSymbol] = React.useState<string | null>(null);
  const openChart = React.useCallback((sym: string) => setChartSymbol(sym), []);
  const portfolioQuery = usePortfolioSymbols();
  const portfolioSymbols = portfolioQuery.data ?? {};
  const { collapsed, toggle } = useSectionCollapse();

  const [universeFilter, setUniverseFilter] = React.useState<UniverseFilter>(() => {
    try {
      const stored = localStorage.getItem(UNIVERSE_FILTER_KEY);
      if (stored === 'etf' || stored === 'holdings') return stored;
    } catch {}
    return 'all';
  });

  const handleFilterChange = React.useCallback((f: UniverseFilter) => {
    setUniverseFilter(f);
    try { localStorage.setItem(UNIVERSE_FILTER_KEY, f); } catch {}
  }, []);

  const vis = SECTION_VIS[universeFilter];
  const showHeld = universeFilter !== 'holdings';

  const constituentSet = React.useMemo(
    () => new Set((payload?.constituent_symbols ?? []).map((s: string) => s.toUpperCase())),
    [payload?.constituent_symbols],
  );

  const symbolFilter = React.useCallback((symbol: string): boolean => {
    const sym = symbol?.toUpperCase?.() || '';
    if (universeFilter === 'all') return constituentSet.size === 0 || constituentSet.has(sym);
    if (universeFilter === 'etf') return ETF_SYMBOL_SET.has(sym);
    if (universeFilter === 'holdings') return sym in portfolioSymbols;
    return true;
  }, [universeFilter, portfolioSymbols, constituentSet]);

  const [volData, setVolData] = React.useState<VolData | null>(null);
  const [trackedRows, setTrackedRows] = React.useState<any[]>([]);

  const fetchDashboard = React.useCallback(async () => {
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
  }, []);

  React.useEffect(() => { void fetchDashboard(); }, [fetchDashboard]);

  React.useEffect(() => {
    marketDataApi.getVolatilityDashboard().then((d: any) => setVolData(d)).catch(() => {});
  }, []);

  React.useEffect(() => {
    api.get('/market-data/snapshots?limit=5000')
      .then((r: any) => {
        const rows = r?.data?.rows;
        if (Array.isArray(rows)) setTrackedRows(rows);
      })
      .catch(() => {});
  }, []);

  const filteredTrackedRows = React.useMemo(
    () => trackedRows.filter((r) => symbolFilter(r?.symbol)),
    [trackedRows, symbolFilter],
  );

  /* --- ZONE 1b: effectiveStats (must be before early returns) --- */
  const effectiveStats = React.useMemo(() => {
    const regime = payload?.regime || {};
    if (universeFilter === 'all' && constituentSet.size === 0) {
      const sc = payload?.snapshot_count || 0;
      const a50 = regime.above_sma50_count || 0;
      const a200 = regime.above_sma200_count || 0;
      const up = regime.up_1d_count || 0;
      const dn = regime.down_1d_count || 0;
      const flat = (regime.flat_1d_count as number) || 0;
      return { count: sc, above50: a50, above200: a200, upCount: up, downCount: dn, flatCount: flat, stageCounts: regime.stage_counts_normalized || {} };
    }
    const rows = filteredTrackedRows;
    const n = rows.length;
    return {
      count: n,
      above50: rows.filter((r: any) => r.sma_50 && r.current_price > r.sma_50).length,
      above200: rows.filter((r: any) => r.sma_200 && r.current_price > r.sma_200).length,
      upCount: rows.filter((r: any) => (r.change_1d ?? r.perf_1d ?? 0) > 0).length,
      downCount: rows.filter((r: any) => (r.change_1d ?? r.perf_1d ?? 0) < 0).length,
      flatCount: rows.filter((r: any) => (r.change_1d ?? r.perf_1d ?? 0) === 0).length,
      stageCounts: rows.reduce((acc: Record<string, number>, r: any) => {
        const s = r.stage_label; if (s) acc[s] = (acc[s] || 0) + 1; return acc;
      }, {} as Record<string, number>),
    };
  }, [universeFilter, constituentSet.size, filteredTrackedRows, payload]);

  /* --- ZONE 1c: filteredSections (consolidate all sf() calls) --- */
  const filteredSections = React.useMemo(() => {
    const sf = <T extends { symbol?: string }>(arr: T[]) =>
      arr.filter((r) => symbolFilter(r.symbol || ''));
    const sfMatrix = (m: Record<string, any[]> | undefined | null) =>
      m ? Object.fromEntries(Object.entries(m).map(([k, arr]) => [k, sf(arr)])) : undefined;

    return {
      sectorRows: sf(payload?.sector_etf_table || []),
      sectorMomentum: payload?.sector_momentum || [],
      breakoutCandidates: sf(payload?.setups?.breakout_candidates || []),
      pullbackCandidates: sf(payload?.setups?.pullback_candidates || []),
      rsLeaders: sf(payload?.setups?.rs_leaders || []),
      leaders: sf(payload?.leaders || []),
      enteringStage2a: sf(payload?.entering_stage_2a || []),
      entering34: sf([...(payload?.entering_stage_3 || []), ...(payload?.entering_stage_4 || [])]),
      entryRows: sf(payload?.entry_proximity_top || []),
      exitRows: sf(payload?.exit_proximity_top || []),
      actionQueue: sf(payload?.action_queue || []),
      top10Matrix: sfMatrix(payload?.top10_matrix),
      bottom10Matrix: sfMatrix(payload?.bottom10_matrix),
      rrgSectors: sf(payload?.rrg_sectors || []),
      rsiBearish: sf(payload?.rsi_divergences?.bearish || []),
      rsiBullish: sf(payload?.rsi_divergences?.bullish || []),
      tdSignals: sf(payload?.td_signals || []),
      gapLeaders: sf(payload?.gap_leaders || []),
      upcomingEarnings: sf(payload?.upcoming_earnings || []),
      fundamentalLeaders: sf(payload?.fundamental_leaders || []),
    };
  }, [payload, symbolFilter]);

  /* --- ZONE 2: Early returns (all hooks are above this line) --- */

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

  /* --- ZONE 3: Derived plain values + JSX --- */

  const {
    sectorRows, sectorMomentum, breakoutCandidates, pullbackCandidates,
    rsLeaders, leaders, enteringStage2a, entering34, entryRows, exitRows,
    actionQueue, top10Matrix, bottom10Matrix, rrgSectors, rsiBearish,
    rsiBullish, tdSignals, gapLeaders, upcomingEarnings, fundamentalLeaders,
  } = filteredSections;

  const trackedCount = payload?.tracked_count || 0;

  const { count: snapshotCount, above50, above200, upCount, downCount, stageCounts } = effectiveStats;
  const pctAbove50 = snapshotCount > 0 ? ((above50 / snapshotCount) * 100).toFixed(0) : '0';
  const pctAbove200 = snapshotCount > 0 ? ((above200 / snapshotCount) * 100).toFixed(0) : '0';
  const advDecRatio = downCount > 0 ? (upCount / downCount).toFixed(2) : upCount > 0 ? '∞' : '0';
  const advDecColor = (() => {
    const r = downCount > 0 ? upCount / downCount : upCount > 0 ? 2 : 1;
    if (r > 1.2) return 'green.500';
    if (r > 1) return 'green.400';
    if (r < 0.8) return 'red.500';
    if (r < 1) return 'red.400';
    return undefined;
  })();

  const snapshotAge = payload?.latest_snapshot_at
    ? Math.round((Date.now() - new Date(payload.latest_snapshot_at).getTime()) / 60000)
    : null;

  const filterLabels: Record<UniverseFilter, string> = {
    all: `All (${constituentSet.size || trackedCount})`,
    etf: `ETFs (${ETF_SYMBOL_SET.size})`,
    holdings: `Holdings (${Object.keys(portfolioSymbols).length})`,
  };

  return (
    <PortfolioSymbolsContext.Provider value={portfolioSymbols}>
    <ChartContext.Provider value={openChart}>
    <Box p={4}>
      <Stack gap={4}>
        <Box>
          <HStack justify="space-between" align="end" flexWrap="wrap" mb={1}>
            <HStack gap={3} align="baseline">
              <Heading size="md">Market Dashboard</Heading>
              <HStack gap={1}>
                {(['all', 'etf', 'holdings'] as UniverseFilter[]).map((f) => (
                  <Button
                    key={f}
                    size="xs"
                    variant={universeFilter === f ? 'solid' : 'outline'}
                    colorPalette={universeFilter === f ? (f === 'holdings' ? 'blue' : 'gray') : 'gray'}
                    onClick={() => handleFilterChange(f)}
                  >
                    {filterLabels[f]}
                  </Button>
                ))}
              </HStack>
            </HStack>
            <HStack gap={2}>
              <HStack gap={1}>
                <Text fontSize="xs" color={snapshotAge != null && snapshotAge > 30 ? 'status.warning' : 'fg.muted'}>
                  {snapshotAge != null ? `${snapshotAge}m ago` : ''}
                </Text>
                <IconButton size="xs" variant="ghost" onClick={() => { void fetchDashboard(); }} aria-label="Refresh dashboard">
                  <FiRefreshCw />
                </IconButton>
              </HStack>
            </HStack>
          </HStack>
          <Text fontSize="xs" color="fg.muted">{MODE_DESCRIPTIONS[universeFilter]}</Text>
        </Box>

        {/* Section 1: Market Pulse */}
        {vis.pulse && (
        <Box>
          <SectionHeading title="Market Pulse" sectionKey="pulse" isCollapsed={collapsed.has('pulse')} onToggle={() => toggle('pulse')} />
          <Collapsible.Root open={!collapsed.has('pulse')}>
            <Collapsible.Content>
              <Box display="flex" gap={2} flexWrap="wrap" mb={3}>
                <StatCard label="% Above 50DMA" value={`${pctAbove50}%`} sub={`${above50} / ${snapshotCount}`} />
                <StatCard label="% Above 200DMA" value={`${pctAbove200}%`} sub={`${above200} / ${snapshotCount}`} />
                <StatCard label="Advance / Decline" value={advDecRatio} sub={`${upCount} up · ${downCount} down`} color={advDecColor} />
              </Box>
              <StageBar counts={stageCounts} total={snapshotCount} />
              <VolatilityRegime data={volData} />
            </Collapsible.Content>
          </Collapsible.Root>
        </Box>
        )}

        {/* Action Queue — organized by Weinstein Stage */}
        {vis.actionQueue && (() => {
          if (actionQueue.length === 0) return (
            <Box>
              <SectionHeading title="Action Queue" sectionKey="actionQueue" isCollapsed={collapsed.has('actionQueue')} onToggle={() => toggle('actionQueue')} count={0} />
              <Collapsible.Root open={!collapsed.has('actionQueue')}><Collapsible.Content><EmptyState mode={universeFilter} noun="action items" /></Collapsible.Content></Collapsible.Root>
            </Box>
          );
          const stageGroups: Record<string, typeof actionQueue> = { '1': [], '2': [], '3': [], '4': [] };
          for (const item of actionQueue) {
            const s = (item.stage_label || '').charAt(0);
            if (s in stageGroups) stageGroups[s].push(item);
            else stageGroups['1'].push(item);
          }
          const stageConfig = [
            { key: '1', label: 'Stage 1 — Base', palette: 'gray' },
            { key: '2', label: 'Stage 2 — Uptrend', palette: 'green' },
            { key: '3', label: 'Stage 3 — Distribution', palette: 'yellow' },
            { key: '4', label: 'Stage 4 — Downtrend', palette: 'red' },
          ];
          return (
            <Box>
              <SectionHeading title="Action Queue" sectionKey="actionQueue" isCollapsed={collapsed.has('actionQueue')} onToggle={() => toggle('actionQueue')} count={actionQueue.length} />
              <Collapsible.Root open={!collapsed.has('actionQueue')}>
                <Collapsible.Content>
              <Box display="grid" gridTemplateColumns={{ base: '1fr', md: 'repeat(2, 1fr)', xl: 'repeat(4, 1fr)' }} gap={3}>
                {stageConfig.map(({ key, label, palette }) => (
                  <Box key={key} borderWidth="1px" borderColor="border.subtle" borderRadius="lg" bg="bg.card" overflow="hidden">
                    <Box px={3} py={1.5} borderBottomWidth="1px" borderColor="border.subtle">
                      <HStack justify="space-between">
                        <Text fontSize="xs" fontWeight="semibold" color={`${palette}.fg`}>{label}</Text>
                        <Badge size="xs" variant="subtle" colorPalette={palette}>{stageGroups[key].length}</Badge>
                      </HStack>
                    </Box>
                    <Box px={3} py={2} maxH="260px" overflowY="auto">
                      {stageGroups[key].length === 0 ? (
                        <Text fontSize="xs" color="fg.subtle">No signals</Text>
                      ) : (
                        stageGroups[key].map((item, idx) => {
                          const reasons: string[] = [];
                          if (item.previous_stage_label && item.previous_stage_label !== item.stage_label) {
                            reasons.push(`${item.previous_stage_label} → ${item.stage_label}`);
                          }
                          if (typeof item.perf_1d === 'number' && Math.abs(item.perf_1d) >= 3) {
                            reasons.push(`1D ${item.perf_1d > 0 ? '+' : ''}${item.perf_1d.toFixed(1)}%`);
                          }
                          if (typeof item.rs_mansfield_pct === 'number' && Math.abs(item.rs_mansfield_pct) >= 6) {
                            reasons.push(`RS ${item.rs_mansfield_pct > 0 ? '+' : ''}${item.rs_mansfield_pct.toFixed(1)}`);
                          }
                          return (
                            <HStack key={`aq-${item.symbol}-${idx}`} justify="space-between" fontSize="xs" py="2px" borderBottomWidth="1px" borderColor="border.subtle">
                              <SymbolLink symbol={item.symbol} showHeldBadge={showHeld} />
                              <HStack gap={1} flexShrink={0}>
                                {reasons.map((r, i) => (
                                  <Text key={i} fontSize="xs" color="fg.muted">{r}</Text>
                                ))}
                              </HStack>
                            </HStack>
                          );
                        })
                      )}
                    </Box>
                  </Box>
                ))}
              </Box>
                </Collapsible.Content>
              </Collapsible.Root>
            </Box>
          );
        })()}

        {/* Section 2: Sector Rotation */}
        {vis.sectorRotation && (
        <Box>
          <SectionHeading title="Sector Rotation" sectionKey="sectorRotation" isCollapsed={collapsed.has('sectorRotation')} onToggle={() => toggle('sectorRotation')} />
          <Collapsible.Root open={!collapsed.has('sectorRotation')}>
            <Collapsible.Content>
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
                    {sectorRows.map((r, i) => (
                      <TableRow key={`sector-${r.symbol}-${i}`}>
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
                  {sectorMomentum.slice(0, 10).map((sm, i) => (
                    <HStack key={`sector-mom-${sm.sector}-${i}`} justify="space-between" fontSize="xs">
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
            </Collapsible.Content>
          </Collapsible.Root>
        </Box>
        )}

        {/* Scatter/Bubble Chart */}
        {vis.scatter && filteredTrackedRows.length > 0 && (
          <Box>
            <SectionHeading title="Universe Scatter" sectionKey="scatter" isCollapsed={collapsed.has('scatter')} onToggle={() => toggle('scatter')} count={filteredTrackedRows.length} />
            <Collapsible.Root open={!collapsed.has('scatter')}>
              {/* @ts-expect-error unmountOnExit is supported at runtime but not typed */}
              <Collapsible.Content unmountOnExit>
            <Box borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={4} bg="bg.card">
              <BubbleChart
                data={filteredTrackedRows}
                defaultX="perf_1d"
                defaultY="rs_mansfield_pct"
                defaultColor="stage_label"
                defaultSize="market_cap"
                onSymbolClick={openChart}
              />
            </Box>
              </Collapsible.Content>
            </Collapsible.Root>
          </Box>
        )}

        {/* Section 3: Trading Setups */}
        {vis.setups && (
        <Box>
          <SectionHeading title="Trading Setups" sectionKey="setups" isCollapsed={collapsed.has('setups')} onToggle={() => toggle('setups')} count={breakoutCandidates.length + pullbackCandidates.length + rsLeaders.length + leaders.length} />
          <Collapsible.Root open={!collapsed.has('setups')}>
            <Collapsible.Content>
              {(breakoutCandidates.length + pullbackCandidates.length + rsLeaders.length + leaders.length) === 0 ? (
                <EmptyState mode={universeFilter} noun="trading setups" />
              ) : (
                <Box display="grid" gridTemplateColumns={{ base: '1fr', md: '1fr 1fr', xl: '1fr 1fr 1fr 1fr' }} gap={3}>
                  <SetupCard title="Breakout Candidates" items={breakoutCandidates} linkPreset="breakout" showHeldBadge={showHeld} />
                  <SetupCard title="Pullback Buys" items={pullbackCandidates} linkPreset="pullback" showHeldBadge={showHeld} />
                  <SetupCard title="RS Leaders" items={rsLeaders} linkPreset="rs_leaders" showHeldBadge={showHeld} />
                  <SetupCard title="Momentum Leaders" items={leaders} showScore linkPreset="momentum" showHeldBadge={showHeld} />
                </Box>
              )}
            </Collapsible.Content>
          </Collapsible.Root>
        </Box>
        )}

        {/* Section 4: Stage Transitions */}
        {vis.transitions && (
        <Box>
          <SectionHeading title="Stage Transitions" sectionKey="transitions" isCollapsed={collapsed.has('transitions')} onToggle={() => toggle('transitions')} count={enteringStage2a.length + entering34.length} />
          <Collapsible.Root open={!collapsed.has('transitions')}>
            <Collapsible.Content>
              {(enteringStage2a.length + entering34.length) === 0 ? (
                <EmptyState mode={universeFilter} noun="stage transitions" />
              ) : (
                <Box display="grid" gridTemplateColumns={{ base: '1fr', md: '1fr 1fr' }} gap={3}>
                  <TransitionList title="Entering Stage 2A (Bullish)" items={enteringStage2a} colorPalette="green" showHeldBadge={showHeld} />
                  <TransitionList title="Entering Stage 3/4 (Warning)" items={entering34} colorPalette="red" showHeldBadge={showHeld} />
                </Box>
              )}
            </Collapsible.Content>
          </Collapsible.Root>
        </Box>
        )}

        {/* Section 5: Ranked Metrics */}
        {vis.ranked && (
        <Box>
          <SectionHeading title="Top / Bottom 10 Matrix" sectionKey="ranked" isCollapsed={collapsed.has('ranked')} onToggle={() => toggle('ranked')} />
          <Collapsible.Root open={!collapsed.has('ranked')}>
            <Collapsible.Content>
              <Stack gap={3}>
                <RankMatrix title="Top 10 Matrix" data={top10Matrix} />
                <RankMatrix title="Bottom 10 Matrix" data={bottom10Matrix} />
              </Stack>
            </Collapsible.Content>
          </Collapsible.Root>
        </Box>
        )}

        {/* Section 6: Entry/Exit Proximity */}
        {vis.proximity && (
        <Box>
          <SectionHeading title="Entry / Exit Proximity" sectionKey="proximity" isCollapsed={collapsed.has('proximity')} onToggle={() => toggle('proximity')} />
          <Collapsible.Root open={!collapsed.has('proximity')}>
            <Collapsible.Content>
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
                      entryRows.slice(0, 10).map((r: any, i: number) => {
                        const distColor = typeof r.distance_pct === 'number' && Math.abs(r.distance_pct) <= 3 ? 'green.400' : undefined;
                        return (
                        <TableRow key={`entry-${r.symbol}-${i}`}>
                          <TableCell><SymbolLink symbol={r.symbol} showHeldBadge={showHeld} /></TableCell>
                          <TableCell>
                            <StageBadge stage={r.stage_label || '?'} />
                          </TableCell>
                          <TableCell>{typeof r.entry_price === 'number' ? r.entry_price.toFixed(2) : '—'}</TableCell>
                          <TableCell><Text color={distColor}>{typeof r.distance_pct === 'number' ? `${r.distance_pct.toFixed(2)}%` : '—'}</Text></TableCell>
                          <TableCell>{typeof r.distance_atr === 'number' ? `${r.distance_atr.toFixed(2)}x` : '—'}</TableCell>
                        </TableRow>
                        );
                      })
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
                      exitRows.slice(0, 10).map((r: any, i: number) => {
                        const distColor = typeof r.distance_pct === 'number' && Math.abs(r.distance_pct) <= 3 ? 'red.400' : undefined;
                        return (
                        <TableRow key={`exit-${r.symbol}-${i}`}>
                          <TableCell><SymbolLink symbol={r.symbol} showHeldBadge={showHeld} /></TableCell>
                          <TableCell>
                            <StageBadge stage={r.stage_label || '?'} />
                          </TableCell>
                          <TableCell>{typeof r.exit_price === 'number' ? r.exit_price.toFixed(2) : '—'}</TableCell>
                          <TableCell><Text color={distColor}>{typeof r.distance_pct === 'number' ? `${r.distance_pct.toFixed(2)}%` : '—'}</Text></TableCell>
                          <TableCell>{typeof r.distance_atr === 'number' ? `${r.distance_atr.toFixed(2)}x` : '—'}</TableCell>
                        </TableRow>
                        );
                      })
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
            </Collapsible.Content>
          </Collapsible.Root>
        </Box>
        )}

        {/* Market Insights */}
        {vis.insights && (
        <Box>
          <SectionHeading title="Market Insights" sectionKey="insights" isCollapsed={collapsed.has('insights')} onToggle={() => toggle('insights')} />
          <Collapsible.Root open={!collapsed.has('insights')}>
            {/* @ts-expect-error unmountOnExit is supported at runtime but not typed */}
            <Collapsible.Content unmountOnExit>
          <Box display="grid" gridTemplateColumns={{ base: '1fr', lg: '1fr 1fr' }} gap={3}>
            <Box display="flex" flexDirection="column" gap={3}>
              {(payload?.range_histogram || []).length > 0 && (
                <RangeHistogram bins={payload!.range_histogram!} />
              )}
              {(payload?.breadth_series || []).length > 0 && (
                <BreadthChart series={payload!.breadth_series!} />
              )}
            </Box>
            {rrgSectors.length > 0 && (
              <RRGChart sectors={rrgSectors} />
            )}
          </Box>
            </Collapsible.Content>
          </Collapsible.Root>
        </Box>
        )}

        {/* Signals & Divergences */}
        {vis.signals && (
        <Box>
          <SectionHeading title="Signals & Divergences" sectionKey="signals" isCollapsed={collapsed.has('signals')} onToggle={() => toggle('signals')} count={rsiBearish.length + rsiBullish.length + tdSignals.length + gapLeaders.length} />
          <Collapsible.Root open={!collapsed.has('signals')}>
            <Collapsible.Content>
          <Box display="grid" gridTemplateColumns={{ base: '1fr', lg: '1fr 1fr 1fr' }} gap={3}>
            <Box borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={3} bg="bg.card">
              <Text fontSize="xs" fontWeight="semibold" mb={2}>Divergence Watch</Text>
              {(rsiBearish.length + rsiBullish.length) === 0 ? (
                <Text fontSize="xs" color="fg.muted">No divergences detected</Text>
              ) : (
                <Box maxH="300px" overflowY="auto" pr={1}>
                  <Box display="flex" flexDirection="column" gap={2}>
                    {rsiBearish.length > 0 && (
                      <Box>
                        <Badge size="sm" variant="subtle" colorPalette="red" mb={1}>Bearish ({rsiBearish.length})</Badge>
                        {rsiBearish.map((d, i) => (
                          <HStack key={`div-b-${d.symbol}-${i}`} justify="space-between" fontSize="xs" py="1px">
                            <SymbolLink symbol={d.symbol} />
                            <HStack gap={2}>
                              <Text color="green.400">+{d.perf_20d}%</Text>
                              <Text color="red.400">RSI {d.rsi}</Text>
                            </HStack>
                          </HStack>
                        ))}
                      </Box>
                    )}
                    {rsiBullish.length > 0 && (
                      <Box>
                        <Badge size="sm" variant="subtle" colorPalette="green" mb={1}>Bullish ({rsiBullish.length})</Badge>
                        {rsiBullish.map((d, i) => (
                          <HStack key={`div-l-${d.symbol}-${i}`} justify="space-between" fontSize="xs" py="1px">
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
                {tdSignals.length > 0 && <Badge variant="subtle" size="sm">{tdSignals.length}</Badge>}
              </HStack>
              <Text fontSize="xs" color="fg.muted" mb={2}>Setup 9 = potential reversal. Countdown 13 = exhaustion confirmed.</Text>
              {tdSignals.length === 0 ? (
                <Text fontSize="xs" color="fg.muted">No active signals</Text>
              ) : (
                <Box maxH="300px" overflowY="auto">
                  <Box display="grid" gridTemplateColumns={{ base: '1fr', xl: '1fr 1fr' }} gap={1} columnGap={3}>
                    {tdSignals.map((s, i) => (
                      <HStack key={`td-${s.symbol}-${i}`} justify="space-between" fontSize="xs" py="1px" borderBottomWidth="1px" borderColor="border.subtle">
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
                {gapLeaders.length > 0 && <Badge variant="subtle" size="sm">{gapLeaders.length}</Badge>}
              </HStack>
              <Text fontSize="xs" color="fg.muted" mb={2}>Symbols with unfilled price gaps (potential support/resistance).</Text>
              {gapLeaders.length === 0 ? (
                <Text fontSize="xs" color="fg.subtle">No unfilled gaps detected. Gap data populates after indicator computation runs.</Text>
              ) : (
                <Box maxH="300px" overflowY="auto">
                  <Box display="flex" flexDirection="column" gap={1}>
                    {gapLeaders.map((g, i) => (
                      <HStack key={`gap-${g.symbol}-${i}`} justify="space-between" fontSize="xs" py="1px" borderBottomWidth="1px" borderColor="border.subtle">
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
            </Collapsible.Content>
          </Collapsible.Root>
        </Box>
        )}

        {/* Earnings & Fundamentals */}
        {vis.earnings && (
        <Box>
          <SectionHeading title="Earnings & Fundamentals" sectionKey="earnings" isCollapsed={collapsed.has('earnings')} onToggle={() => toggle('earnings')} count={upcomingEarnings.length + fundamentalLeaders.length} />
          <Collapsible.Root open={!collapsed.has('earnings')}>
            <Collapsible.Content>
          <Box display="grid" gridTemplateColumns={{ base: '1fr', lg: '1fr 1fr' }} gap={3}>
            <Box borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={3} bg="bg.card">
              <Text fontSize="xs" fontWeight="semibold" mb={2}>Upcoming Earnings (7d)</Text>
              {upcomingEarnings.length === 0 ? (
                <Text fontSize="xs" color="fg.muted">No upcoming earnings</Text>
              ) : (
                <Box maxH="260px" overflowY="auto" pr={1}>
                  <Box display="flex" flexDirection="column" gap={1}>
                    {upcomingEarnings.map((e, i) => (
                      <HStack key={`earn-${e.symbol}-${i}`} justify="space-between" fontSize="xs">
                        <HStack gap={1}>
                          <SymbolLink symbol={e.symbol} />
                          <StageBadge stage={e.stage_label || '?'} />
                        </HStack>
                        <Text color="fg.muted">{formatDate(e.next_earnings, timezone)}</Text>
                      </HStack>
                    ))}
                  </Box>
                </Box>
              )}
            </Box>

            <Box borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={3} bg="bg.card">
              <Text fontSize="xs" fontWeight="semibold" mb={2}>Fundamental Leaders</Text>
              {fundamentalLeaders.length === 0 ? (
                <Text fontSize="xs" color="fg.muted">Insufficient data</Text>
              ) : (
                <Box maxH="260px" overflowY="auto" pr={1}>
                  <Box display="flex" flexDirection="column" gap={1}>
                    {fundamentalLeaders.map((f, i) => (
                      <HStack key={`fund-${f.symbol}-${i}`} justify="space-between" fontSize="xs">
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
            </Collapsible.Content>
          </Collapsible.Root>
        </Box>
        )}

      </Stack>
      <ChartSlidePanel symbol={chartSymbol} onClose={() => setChartSymbol(null)} />
    </Box>
    </ChartContext.Provider>
    </PortfolioSymbolsContext.Provider>
  );
};

export default MarketDashboard;
