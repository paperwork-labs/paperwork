import React from 'react';
import {
  Box, HStack, Text, Badge, Stack, SimpleGrid,
  TableRoot, TableHeader, TableRow, TableColumnHeader,
  TableBody, TableCell, TableScrollArea,
} from '@chakra-ui/react';
import StageBadge from '../shared/StageBadge';
import { SymbolLink } from './SymbolChartUI';
import { heatColor, SECTOR_PALETTE } from '../../constants/chart';
import { useChartColors } from '../../hooks/useChartColors';
import {
  ScatterChart, Scatter, XAxis, YAxis, ZAxis, Tooltip as RTooltip,
  ResponsiveContainer, ReferenceLine, ReferenceArea, Cell, CartesianGrid,
} from 'recharts';

const DATA_CELL = { fontFamily: 'mono', fontSize: 'xs', letterSpacing: '-0.02em' } as const;

const fmtPct = (v: unknown): string => {
  if (typeof v !== 'number' || !Number.isFinite(v)) return '—';
  return `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`;
};

interface SectorViewProps {
  snapshots: any[];
  dashboardPayload: any;
}

const SectorView: React.FC<SectorViewProps> = ({ snapshots, dashboardPayload }) => {
  const cc = useChartColors();
  const [selectedSector, setSelectedSector] = React.useState<string | null>(null);

  const sectorMap = React.useMemo(() => {
    const m = new Map<string, any[]>();
    snapshots.forEach((s: any) => {
      const sector = s.sector || 'Unknown';
      if (!m.has(sector)) m.set(sector, []);
      m.get(sector)!.push(s);
    });
    return m;
  }, [snapshots]);

  const sectorSummaries = React.useMemo(() =>
    Array.from(sectorMap.entries()).map(([sector, stocks]) => {
      const n = stocks.length;
      const avgPerf1d = stocks.reduce((a: number, s: any) => a + (s.perf_1d || 0), 0) / n;
      const avgPerf20d = stocks.reduce((a: number, s: any) => a + (s.perf_20d || 0), 0) / n;
      const avgRS = stocks.reduce((a: number, s: any) => a + (s.rs_mansfield_pct || 0), 0) / n;
      const stage2count = stocks.filter((s: any) => s.stage_label?.startsWith('2')).length;
      const stage4count = stocks.filter((s: any) => s.stage_label?.startsWith('4')).length;
      return {
        sector, count: n, avgPerf1d, avgPerf20d, avgRS,
        stage2pct: (stage2count / n) * 100,
        stage4pct: (stage4count / n) * 100,
        health: stage2count > stage4count ? 'bullish' : stage4count > stage2count ? 'bearish' : 'neutral',
      };
    }).sort((a, b) => b.avgRS - a.avgRS),
    [sectorMap]);

  const rrgData = React.useMemo(() =>
    (dashboardPayload?.rrg_sectors || []).map((s: any, i: number) => ({
      ...s, z: 200, _idx: i,
    })), [dashboardPayload]);

  const selectedStocks = React.useMemo(() => {
    if (!selectedSector) return [];
    return (sectorMap.get(selectedSector) || [])
      .sort((a: any, b: any) => (b.rs_mansfield_pct || 0) - (a.rs_mansfield_pct || 0));
  }, [selectedSector, sectorMap]);

  const maxAbs = React.useMemo(() => {
    if (!rrgData.length) return 5;
    return Math.max(
      ...rrgData.map((s: any) => Math.abs(s.rs_ratio || 0)),
      ...rrgData.map((s: any) => Math.abs(s.rs_momentum || 0)),
      1,
    );
  }, [rrgData]);
  const pad = Math.ceil(maxAbs * 1.15) || 5;

  return (
    <Stack gap={5}>
      {/* RRG Chart */}
      {rrgData.length > 0 && (
        <Box borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={4} bg="bg.card">
          <Text fontSize="sm" fontWeight="semibold" mb={2}>Relative Rotation Graph</Text>
          <ResponsiveContainer width="100%" height={380}>
            <ScatterChart>
              <CartesianGrid strokeDasharray="3 3" stroke={cc.grid} />
              <XAxis type="number" dataKey="rs_ratio" domain={[-pad, pad]} hide />
              <YAxis type="number" dataKey="rs_momentum" domain={[-pad, pad]} hide />
              <ZAxis type="number" dataKey="z" range={[160, 160]} />
              <ReferenceArea x1={0} x2={pad} y1={0} y2={pad} fill={cc.success} fillOpacity={0.05} label={{ value: 'Leading', position: 'insideTopRight', fontSize: 11, fill: cc.success, fontWeight: 600 }} />
              <ReferenceArea x1={-pad} x2={0} y1={0} y2={pad} fill={cc.area2} fillOpacity={0.05} label={{ value: 'Improving', position: 'insideTopLeft', fontSize: 11, fill: cc.neutral, fontWeight: 600 }} />
              <ReferenceArea x1={-pad} x2={0} y1={-pad} y2={0} fill={cc.danger} fillOpacity={0.05} label={{ value: 'Lagging', position: 'insideBottomLeft', fontSize: 11, fill: cc.danger, fontWeight: 600 }} />
              <ReferenceArea x1={0} x2={pad} y1={-pad} y2={0} fill={cc.warning} fillOpacity={0.05} label={{ value: 'Weakening', position: 'insideBottomRight', fontSize: 11, fill: cc.warning, fontWeight: 600 }} />
              <ReferenceLine x={0} stroke={cc.refLine} strokeWidth={1.5} />
              <ReferenceLine y={0} stroke={cc.refLine} strokeWidth={1.5} />
              <RTooltip
                contentStyle={{ fontSize: 12, borderRadius: 8, border: `1px solid ${cc.tooltipBorder}`, background: cc.tooltipBg, fontFamily: 'JetBrains Mono, monospace' }}
                formatter={(v: any, name: string | undefined) => [Number(v).toFixed(2), name ?? '']}
              />
              <Scatter data={rrgData}>
                {rrgData.map((_: any, i: number) => (
                  <Cell key={i} fill={SECTOR_PALETTE[i % SECTOR_PALETTE.length]} stroke="white" strokeWidth={1.5} />
                ))}
              </Scatter>
            </ScatterChart>
          </ResponsiveContainer>
          <Box display="grid" gridTemplateColumns="repeat(auto-fill, minmax(130px, 1fr))" gap="3px" mt={2}>
            {rrgData.map((s: any, i: number) => (
              <HStack key={s.symbol} gap={1}>
                <Box w="8px" h="8px" borderRadius="full" flexShrink={0} bg={SECTOR_PALETTE[i % SECTOR_PALETTE.length]} />
                <Text fontSize="10px" truncate color="fg.muted">{s.name}</Text>
              </HStack>
            ))}
          </Box>
        </Box>
      )}

      {/* Sector Summary Table */}
      <Box borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={4} bg="bg.card">
        <Text fontSize="sm" fontWeight="semibold" mb={3}>Sector Health Matrix</Text>
        <TableScrollArea borderWidth="1px" borderColor="border.subtle" borderRadius="md">
          <TableRoot size="sm">
            <TableHeader>
              <TableRow>
                <TableColumnHeader>Sector</TableColumnHeader>
                <TableColumnHeader textAlign="right">Count</TableColumnHeader>
                <TableColumnHeader textAlign="right">Avg 1D</TableColumnHeader>
                <TableColumnHeader textAlign="right">Avg 20D</TableColumnHeader>
                <TableColumnHeader textAlign="right">Avg RS</TableColumnHeader>
                <TableColumnHeader textAlign="right">Stage 2 %</TableColumnHeader>
                <TableColumnHeader textAlign="right">Stage 4 %</TableColumnHeader>
                <TableColumnHeader>Health</TableColumnHeader>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sectorSummaries.map(row => (
                <TableRow
                  key={row.sector}
                  cursor="pointer"
                  onClick={() => setSelectedSector(prev => prev === row.sector ? null : row.sector)}
                  bg={selectedSector === row.sector ? 'bg.subtle' : undefined}
                  _hover={{ bg: 'bg.hover' }}
                  transition="background 150ms ease"
                >
                  <TableCell fontWeight="semibold" fontSize="xs">{row.sector}</TableCell>
                  <TableCell textAlign="right" {...DATA_CELL}>{row.count}</TableCell>
                  <TableCell textAlign="right" {...DATA_CELL} color={heatColor(row.avgPerf1d)}>{fmtPct(row.avgPerf1d)}</TableCell>
                  <TableCell textAlign="right" {...DATA_CELL} color={heatColor(row.avgPerf20d)}>{fmtPct(row.avgPerf20d)}</TableCell>
                  <TableCell textAlign="right" {...DATA_CELL} color={heatColor(row.avgRS)}>{fmtPct(row.avgRS)}</TableCell>
                  <TableCell textAlign="right" {...DATA_CELL} color="green.500">{row.stage2pct.toFixed(0)}%</TableCell>
                  <TableCell textAlign="right" {...DATA_CELL} color="red.500">{row.stage4pct.toFixed(0)}%</TableCell>
                  <TableCell>
                    <Badge variant="subtle" size="sm" colorPalette={
                      row.health === 'bullish' ? 'green' : row.health === 'bearish' ? 'red' : 'gray'
                    }>{row.health}</Badge>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </TableRoot>
        </TableScrollArea>
      </Box>

      {/* Selected Sector Drill-Down */}
      {selectedSector && selectedStocks.length > 0 && (
        <Box borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={4} bg="bg.card">
          <HStack justify="space-between" mb={3}>
            <Text fontSize="sm" fontWeight="semibold">{selectedSector} — {selectedStocks.length} stocks</Text>
            <Badge variant="outline" cursor="pointer" onClick={() => setSelectedSector(null)} size="sm">Close</Badge>
          </HStack>
          <TableScrollArea borderWidth="1px" borderColor="border.subtle" borderRadius="md" maxH="400px">
            <TableRoot size="sm">
              <TableHeader position="sticky" top={0} bg="bg.card" zIndex={1}>
                <TableRow>
                  <TableColumnHeader>Ticker</TableColumnHeader>
                  <TableColumnHeader textAlign="right">Price</TableColumnHeader>
                  <TableColumnHeader>Stage</TableColumnHeader>
                  <TableColumnHeader textAlign="right">1D</TableColumnHeader>
                  <TableColumnHeader textAlign="right">20D</TableColumnHeader>
                  <TableColumnHeader textAlign="right">RS</TableColumnHeader>
                  <TableColumnHeader textAlign="right">Ext150%</TableColumnHeader>
                  <TableColumnHeader textAlign="right">ATR%</TableColumnHeader>
                </TableRow>
              </TableHeader>
              <TableBody>
                {selectedStocks.map((s: any) => (
                  <TableRow key={s.symbol} transition="background 150ms ease" _hover={{ bg: 'bg.hover' }}>
                    <TableCell><SymbolLink symbol={s.symbol} /></TableCell>
                    <TableCell textAlign="right" {...DATA_CELL}>{s.current_price?.toFixed(2) ?? '—'}</TableCell>
                    <TableCell><StageBadge stage={s.stage_label || '—'} /></TableCell>
                    <TableCell textAlign="right" {...DATA_CELL} color={heatColor(s.perf_1d)}>{fmtPct(s.perf_1d)}</TableCell>
                    <TableCell textAlign="right" {...DATA_CELL} color={heatColor(s.perf_20d)}>{fmtPct(s.perf_20d)}</TableCell>
                    <TableCell textAlign="right" {...DATA_CELL} color={heatColor(s.rs_mansfield_pct)}>{fmtPct(s.rs_mansfield_pct)}</TableCell>
                    <TableCell textAlign="right" {...DATA_CELL} color={heatColor(s.ext_pct)}>{fmtPct(s.ext_pct)}</TableCell>
                    <TableCell textAlign="right" {...DATA_CELL}>{s.atrp_14?.toFixed(1) ?? '—'}%</TableCell>
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

export default SectorView;
