import React from 'react';
import {
  Box, HStack, Text, Badge, Stack, Heading, SimpleGrid, Skeleton,
  TableRoot, TableHeader, TableRow, TableColumnHeader,
  TableBody, TableCell, TableScrollArea,
} from '@chakra-ui/react';
import { useQuery } from '@tanstack/react-query';
import { marketDataApi } from '../../services/api';
import { REGIME_HEX, heatColor, STAGE_HEX, SECTOR_PALETTE } from '../../constants/chart';
import { useChartColors } from '../../hooks/useChartColors';
import StatCard from '../shared/StatCard';
import {
  ComposedChart, Area, XAxis, YAxis, Tooltip as RTooltip,
  ResponsiveContainer, ReferenceLine, BarChart, Bar, Cell,
} from 'recharts';

const DATA_CELL = { fontFamily: 'mono', fontSize: 'xs', letterSpacing: '-0.02em' } as const;

const REGIME_LABELS: Record<string, string> = {
  R1: 'Bull', R2: 'Bull Extended', R3: 'Chop', R4: 'Bear Rally', R5: 'Bear',
};

const fmtPct = (v: unknown): string => {
  if (typeof v !== 'number' || !Number.isFinite(v)) return '—';
  return `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`;
};

const INDEX_SYMBOLS = ['SPY', 'RSP', 'MDY', 'DIA', 'IWM', 'QQQ'];
const THEMATIC_GROUPS: Record<string, string[]> = {
  'ATOMS': ['XLE', 'XLB', 'GDX', 'URA', 'COPX'],
  'BITS': ['XLK', 'SMH', 'ARKK', 'BOTZ', 'HACK'],
  'Debasement': ['GLD', 'SLV', 'BTC-USD', 'TIP'],
};

interface TopDownViewProps {
  snapshots: any[];
  dashboardPayload: any;
}

const TopDownView: React.FC<TopDownViewProps> = ({ snapshots, dashboardPayload }) => {
  const cc = useChartColors();

  const { data: regimeData } = useQuery({
    queryKey: ['regime-current'],
    queryFn: async () => {
      const resp = await marketDataApi.getCurrentRegime();
      return resp?.data?.regime ?? resp?.regime ?? null;
    },
    staleTime: 2 * 60_000,
    refetchInterval: 5 * 60_000,
  });

  const { data: regimeHistory } = useQuery({
    queryKey: ['regime-history-90'],
    queryFn: async () => {
      const resp = await marketDataApi.getRegimeHistory(90);
      return resp?.data?.history ?? resp?.history ?? [];
    },
    staleTime: 5 * 60_000,
  });

  const { data: volData } = useQuery({
    queryKey: ['vol-dashboard'],
    queryFn: async () => {
      const resp = await marketDataApi.getVolatilityDashboard();
      return resp?.data ?? resp ?? null;
    },
    staleTime: 2 * 60_000,
  });

  const snapshotMap = React.useMemo(() => {
    const m = new Map<string, any>();
    (snapshots || []).forEach((s: any) => {
      if (s?.symbol) m.set(s.symbol.toUpperCase(), s);
    });
    return m;
  }, [snapshots]);

  const regimeColor = regimeData?.regime_state
    ? REGIME_HEX[regimeData.regime_state] || '#64748B'
    : '#64748B';

  const breadthAbove50 = dashboardPayload?.regime?.above_sma50_count ?? 0;
  const breadthAbove200 = dashboardPayload?.regime?.above_sma200_count ?? 0;
  const total = dashboardPayload?.snapshot_count ?? 1;

  const indexRows = React.useMemo(() =>
    INDEX_SYMBOLS.map(sym => {
      const snap = snapshotMap.get(sym);
      return {
        symbol: sym,
        price: snap?.current_price,
        perf_1d: snap?.perf_1d,
        perf_5d: snap?.perf_5d,
        perf_20d: snap?.perf_20d,
        perf_252d: snap?.perf_252d,
        rsi: snap?.rsi,
      };
    }), [snapshotMap]);

  const sectorRows = React.useMemo(() =>
    (dashboardPayload?.sector_etf_table || []).map((r: any) => ({
      symbol: r.symbol,
      name: r.sector_name,
      change_1d: r.change_1d,
      change_5d: r.change_5d,
      change_20d: r.change_20d,
      rs: r.rs_mansfield_pct,
      stage: r.stage_label,
    })), [dashboardPayload]);

  const regimeChartData = React.useMemo(() =>
    (regimeHistory || []).map((r: any) => ({
      date: r.as_of_date?.slice(5),
      score: r.composite_score,
      state: r.regime_state,
    })), [regimeHistory]);

  return (
    <Stack gap={5}>
      {/* Regime Banner */}
      {regimeData && (
        <Box
          borderWidth="2px"
          borderColor={regimeColor}
          borderRadius="xl"
          p={4}
          bg="bg.card"
          position="relative"
          overflow="hidden"
        >
          <Box
            position="absolute"
            top={0} left={0} right={0} bottom={0}
            bg={regimeColor}
            opacity={0.06}
          />
          <HStack justify="space-between" flexWrap="wrap" gap={3} position="relative">
            <HStack gap={3}>
              <Box
                bg={regimeColor}
                color="white"
                px={3} py={1}
                borderRadius="md"
                fontWeight="bold"
                fontSize="lg"
              >
                {regimeData.regime_state}
              </Box>
              <Box>
                <Text fontWeight="semibold" fontSize="md">
                  {REGIME_LABELS[regimeData.regime_state] || regimeData.regime_state}
                </Text>
                <Text fontSize="xs" color="fg.muted">
                  Composite: {regimeData.composite_score?.toFixed(2)} | As of {regimeData.as_of_date}
                </Text>
              </Box>
            </HStack>
            <HStack gap={4} flexWrap="wrap">
              <StatCard label="Sizing Mult" value={`${regimeData.regime_multiplier?.toFixed(2)}x`} />
              <StatCard label="Max Equity" value={`${regimeData.max_equity_exposure_pct}%`} />
              <StatCard label="Cash Floor" value={`${regimeData.cash_floor_pct}%`} />
            </HStack>
          </HStack>
        </Box>
      )}

      {/* Top Row: Regime Trend + Volatility */}
      <SimpleGrid columns={{ base: 1, lg: 2 }} gap={4}>
        {/* Regime History Chart */}
        <Box borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={4} bg="bg.card">
          <Text fontSize="sm" fontWeight="semibold" mb={3}>Regime Composite (90d)</Text>
          {regimeChartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={180}>
              <ComposedChart data={regimeChartData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="regimeGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={regimeColor} stopOpacity={0.3} />
                    <stop offset="95%" stopColor={regimeColor} stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="date" tick={{ fontSize: 9, fill: cc.muted }} tickLine={false} axisLine={false} interval={Math.floor(regimeChartData.length / 6)} />
                <YAxis domain={[1, 5]} tick={{ fontSize: 9, fill: cc.muted }} tickLine={false} axisLine={false} width={30} />
                <ReferenceLine y={2.5} stroke={cc.refLine} strokeDasharray="4 3" />
                <ReferenceLine y={3.5} stroke={cc.refLine} strokeDasharray="4 3" />
                <RTooltip
                  contentStyle={{ fontSize: 12, borderRadius: 8, border: `1px solid ${cc.border}`, background: cc.tooltipBg, fontFamily: 'JetBrains Mono, monospace' }}
                  formatter={(v: any) => [Number(v).toFixed(2), 'Composite']}
                />
                <Area type="monotone" dataKey="score" fill="url(#regimeGrad)" stroke={regimeColor} strokeWidth={2} />
              </ComposedChart>
            </ResponsiveContainer>
          ) : (
            <Text fontSize="xs" color="fg.muted" textAlign="center" py={8}>No regime history available</Text>
          )}
        </Box>

        {/* Volatility Panel */}
        <Box borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={4} bg="bg.card">
          <Text fontSize="sm" fontWeight="semibold" mb={3}>Volatility</Text>
          <SimpleGrid columns={3} gap={3}>
            <Box textAlign="center">
              <Text fontSize="2xl" fontWeight="bold" fontFamily="mono" letterSpacing="-0.02em">{volData?.vix?.toFixed(1) ?? '—'}</Text>
              <Text fontSize="xs" color="fg.muted">VIX</Text>
            </Box>
            <Box textAlign="center">
              <Text fontSize="2xl" fontWeight="bold" fontFamily="mono" letterSpacing="-0.02em">{volData?.vix3m?.toFixed(1) ?? '—'}</Text>
              <Text fontSize="xs" color="fg.muted">VIX3M</Text>
            </Box>
            <Box textAlign="center">
              <Text fontSize="2xl" fontWeight="bold" fontFamily="mono" letterSpacing="-0.02em">{volData?.vvix?.toFixed(1) ?? '—'}</Text>
              <Text fontSize="xs" color="fg.muted">VVIX</Text>
            </Box>
          </SimpleGrid>
          <SimpleGrid columns={2} gap={3} mt={3}>
            <Box p={2} borderRadius="md" bg="bg.subtle" textAlign="center" transition="background 200ms ease">
              <Text fontSize="sm" fontWeight="semibold" fontFamily="mono">
                {volData?.term_structure_ratio?.toFixed(3) ?? '—'}
              </Text>
              <Text fontSize="xs" color="fg.muted">VIX3M/VIX</Text>
              <Text fontSize="10px" color={
                (volData?.term_structure_ratio ?? 1) < 1 ? 'red.500' :
                (volData?.term_structure_ratio ?? 1) > 1.15 ? 'orange.500' : 'green.500'
              }>
                {(volData?.term_structure_ratio ?? 1) < 1 ? 'Backwardation' :
                 (volData?.term_structure_ratio ?? 1) > 1.15 ? 'Mkt Overbought' : 'Normal Contango'}
              </Text>
            </Box>
            <Box p={2} borderRadius="md" bg="bg.subtle" textAlign="center" transition="background 200ms ease">
              <Text fontSize="sm" fontWeight="semibold" fontFamily="mono">
                {volData?.vol_of_vol_ratio?.toFixed(2) ?? '—'}
              </Text>
              <Text fontSize="xs" color="fg.muted">VVIX/VIX</Text>
              <Text fontSize="10px" color={
                (volData?.vol_of_vol_ratio ?? 5) < 3.5 ? 'green.500' :
                (volData?.vol_of_vol_ratio ?? 5) > 6 ? 'red.500' : 'fg.muted'
              }>
                {(volData?.vol_of_vol_ratio ?? 5) < 3.5 ? 'Buy Protection' :
                 (volData?.vol_of_vol_ratio ?? 5) > 6 ? 'Sell Protection' : 'Neutral'}
              </Text>
            </Box>
          </SimpleGrid>
        </Box>
      </SimpleGrid>

      {/* Breadth Stats */}
      <SimpleGrid columns={{ base: 2, md: 4 }} gap={3}>
        <StatCard label="% Above 50 DMA" value={total > 0 ? `${((breadthAbove50 / total) * 100).toFixed(0)}%` : '—'} />
        <StatCard label="% Above 200 DMA" value={total > 0 ? `${((breadthAbove200 / total) * 100).toFixed(0)}%` : '—'} />
        <StatCard label="Advancing" value={String(dashboardPayload?.regime?.up_1d_count ?? '—')} />
        <StatCard label="Declining" value={String(dashboardPayload?.regime?.down_1d_count ?? '—')} />
      </SimpleGrid>

      {/* Index Performance Grid */}
      <Box borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={4} bg="bg.card">
        <Text fontSize="sm" fontWeight="semibold" mb={3}>Index Performance</Text>
        <TableScrollArea borderWidth="1px" borderColor="border.subtle" borderRadius="md">
          <TableRoot size="sm">
            <TableHeader>
              <TableRow>
                <TableColumnHeader>Index</TableColumnHeader>
                <TableColumnHeader textAlign="right">Price</TableColumnHeader>
                <TableColumnHeader textAlign="right">1D</TableColumnHeader>
                <TableColumnHeader textAlign="right">5D</TableColumnHeader>
                <TableColumnHeader textAlign="right">MTD</TableColumnHeader>
                <TableColumnHeader textAlign="right">YTD</TableColumnHeader>
                <TableColumnHeader textAlign="right">RSI</TableColumnHeader>
              </TableRow>
            </TableHeader>
            <TableBody>
              {indexRows.map(row => (
                <TableRow key={row.symbol} transition="background 150ms ease" _hover={{ bg: 'bg.hover' }}>
                  <TableCell fontWeight="semibold">{row.symbol}</TableCell>
                  <TableCell textAlign="right" {...DATA_CELL}>{row.price?.toFixed(2) ?? '—'}</TableCell>
                  <TableCell textAlign="right" {...DATA_CELL} color={heatColor(row.perf_1d)}>{fmtPct(row.perf_1d)}</TableCell>
                  <TableCell textAlign="right" {...DATA_CELL} color={heatColor(row.perf_5d)}>{fmtPct(row.perf_5d)}</TableCell>
                  <TableCell textAlign="right" {...DATA_CELL} color={heatColor(row.perf_20d)}>{fmtPct(row.perf_20d)}</TableCell>
                  <TableCell textAlign="right" {...DATA_CELL} color={heatColor(row.perf_252d)}>{fmtPct(row.perf_252d)}</TableCell>
                  <TableCell textAlign="right" {...DATA_CELL} color={
                    (row.rsi ?? 50) > 70 ? 'red.500' : (row.rsi ?? 50) < 30 ? 'green.500' : undefined
                  }>{row.rsi?.toFixed(0) ?? '—'}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </TableRoot>
        </TableScrollArea>
      </Box>

      {/* Sector Rotation Table */}
      {sectorRows.length > 0 && (
        <Box borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={4} bg="bg.card">
          <Text fontSize="sm" fontWeight="semibold" mb={3}>Sector ETFs</Text>
          <TableScrollArea borderWidth="1px" borderColor="border.subtle" borderRadius="md">
            <TableRoot size="sm">
              <TableHeader>
                <TableRow>
                  <TableColumnHeader>ETF</TableColumnHeader>
                  <TableColumnHeader>Sector</TableColumnHeader>
                  <TableColumnHeader textAlign="right">1D</TableColumnHeader>
                  <TableColumnHeader textAlign="right">5D</TableColumnHeader>
                  <TableColumnHeader textAlign="right">20D</TableColumnHeader>
                  <TableColumnHeader textAlign="right">RS</TableColumnHeader>
                  <TableColumnHeader>Stage</TableColumnHeader>
                </TableRow>
              </TableHeader>
              <TableBody>
                {sectorRows.map((row: any) => (
                  <TableRow key={row.symbol} transition="background 150ms ease" _hover={{ bg: 'bg.hover' }}>
                    <TableCell fontWeight="semibold">{row.symbol}</TableCell>
                    <TableCell fontSize="xs" color="fg.muted">{row.name || '—'}</TableCell>
                    <TableCell textAlign="right" {...DATA_CELL} color={heatColor(row.change_1d)}>{fmtPct(row.change_1d)}</TableCell>
                    <TableCell textAlign="right" {...DATA_CELL} color={heatColor(row.change_5d)}>{fmtPct(row.change_5d)}</TableCell>
                    <TableCell textAlign="right" {...DATA_CELL} color={heatColor(row.change_20d)}>{fmtPct(row.change_20d)}</TableCell>
                    <TableCell textAlign="right" {...DATA_CELL} color={heatColor(row.rs)}>{fmtPct(row.rs)}</TableCell>
                    <TableCell>
                      <Badge variant="subtle" size="sm" colorPalette={
                        row.stage?.startsWith('2') ? 'green' :
                        row.stage?.startsWith('4') ? 'red' :
                        row.stage?.startsWith('3') ? 'orange' : 'gray'
                      }>{row.stage || '—'}</Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </TableRoot>
          </TableScrollArea>
        </Box>
      )}
    </Stack>
  );
};

export default TopDownView;
