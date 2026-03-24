import React from 'react';
import {
  Box, HStack, Text, Badge, Stack, Input, SimpleGrid,
  TableRoot, TableHeader, TableRow, TableColumnHeader,
  TableBody, TableCell, TableScrollArea,
} from '@chakra-ui/react';
import { FiSearch } from 'react-icons/fi';
import StageBadge from '../shared/StageBadge';
import StageBar from '../shared/StageBar';
import { SymbolLink } from './SymbolChartUI';
import { heatColor, ACTION_COLORS } from '../../constants/chart';

const DATA_CELL = { fontFamily: 'mono', fontSize: 'xs', letterSpacing: '-0.02em' } as const;

const fmtPct = (v: unknown): string => {
  if (typeof v !== 'number' || !Number.isFinite(v)) return '—';
  return `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`;
};

type SortKey = 'symbol' | 'stage_label' | 'action_label' | 'perf_1d' | 'perf_5d' | 'perf_20d' | 'perf_252d' | 'rsi' | 'ext_pct' | 'atrp_14' | 'rs_mansfield_pct' | 'ema10_dist_n' | 'sma150_slope' | 'scan_tier';

interface BottomUpViewProps {
  snapshots: any[];
}

const BottomUpView: React.FC<BottomUpViewProps> = ({ snapshots }) => {
  const [search, setSearch] = React.useState('');
  const [sortKey, setSortKey] = React.useState<SortKey>('scan_tier');
  const [sortDir, setSortDir] = React.useState<'asc' | 'desc'>('asc');
  const [stageFilter, setStageFilter] = React.useState<string | null>(null);
  const [actionFilter, setActionFilter] = React.useState<string | null>(null);

  const handleSort = React.useCallback((key: SortKey) => {
    if (sortKey === key) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    } else {
      setSortKey(key);
      setSortDir(key === 'symbol' ? 'asc' : 'desc');
    }
  }, [sortKey]);

  const stageCounts = React.useMemo(() => {
    const counts: Record<string, number> = {};
    snapshots.forEach((s: any) => {
      const stage = s.stage_label;
      if (stage) counts[stage] = (counts[stage] || 0) + 1;
    });
    return counts;
  }, [snapshots]);

  const actionCounts = React.useMemo(() => {
    const counts: Record<string, number> = {};
    snapshots.forEach((s: any) => {
      const action = s.action_label || s.scan_action || 'WATCH';
      counts[action] = (counts[action] || 0) + 1;
    });
    return counts;
  }, [snapshots]);

  const filteredRows = React.useMemo(() => {
    let rows = [...snapshots];
    if (search) {
      const q = search.toUpperCase();
      rows = rows.filter((r: any) =>
        r.symbol?.toUpperCase().includes(q) ||
        r.sector?.toUpperCase().includes(q) ||
        r.name?.toUpperCase().includes(q)
      );
    }
    if (stageFilter) {
      rows = rows.filter((r: any) => r.stage_label === stageFilter);
    }
    if (actionFilter) {
      rows = rows.filter((r: any) => (r.action_label || r.scan_action || 'WATCH') === actionFilter);
    }
    rows.sort((a: any, b: any) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      const cmp = typeof av === 'string' ? av.localeCompare(bv) : av - bv;
      return sortDir === 'asc' ? cmp : -cmp;
    });
    return rows;
  }, [snapshots, search, sortKey, sortDir, stageFilter, actionFilter]);

  const SortHeader: React.FC<{ k: SortKey; label: string; align?: string }> = ({ k, label, align }) => (
    <TableColumnHeader
      cursor="pointer"
      onClick={() => handleSort(k)}
      textAlign={align as any}
      _hover={{ bg: 'bg.subtle' }}
      transition="background 150ms ease"
      userSelect="none"
    >
      <HStack gap={1} justify={align === 'right' ? 'flex-end' : 'flex-start'}>
        <Text fontSize="xs" fontWeight="semibold">{label}</Text>
        {sortKey === k && <Text fontSize="xs" color="fg.accent">{sortDir === 'asc' ? '▲' : '▼'}</Text>}
      </HStack>
    </TableColumnHeader>
  );

  return (
    <Stack gap={4}>
      {/* Stage Distribution */}
      <Box borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={4} bg="bg.card">
        <HStack justify="space-between" mb={2}>
          <Text fontSize="sm" fontWeight="semibold">Stage Distribution</Text>
          <Text fontSize="xs" color="fg.muted">{snapshots.length} symbols</Text>
        </HStack>
        <StageBar counts={stageCounts} onClick={(stage: string) => setStageFilter(prev => prev === stage ? null : stage)} activeStage={stageFilter} />
      </Box>

      {/* Action Summary */}
      <HStack gap={2} flexWrap="wrap">
        {Object.entries(actionCounts).sort(([a], [b]) => a.localeCompare(b)).map(([action, count]) => (
          <Badge
            key={action}
            variant={actionFilter === action ? 'solid' : 'subtle'}
            colorPalette={ACTION_COLORS[action] || 'gray'}
            cursor="pointer"
            onClick={() => setActionFilter(prev => prev === action ? null : action)}
            size="sm"
            transition="all 200ms ease"
            _hover={{ opacity: 0.85 }}
          >
            {action}: {count}
          </Badge>
        ))}
        {(stageFilter || actionFilter) && (
          <Badge
            variant="outline"
            cursor="pointer"
            onClick={() => { setStageFilter(null); setActionFilter(null); }}
            size="sm"
            transition="all 200ms ease"
            _hover={{ bg: 'bg.subtle' }}
          >
            Clear Filters
          </Badge>
        )}
      </HStack>

      {/* Search */}
      <HStack gap={2}>
        <Box position="relative" flex={1}>
          <Box position="absolute" left={3} top="50%" transform="translateY(-50%)" zIndex={1}>
            <FiSearch size={14} />
          </Box>
          <Input
            pl={8}
            size="sm"
            placeholder="Search symbol, sector, or name..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </Box>
        <Text fontSize="xs" color="fg.muted">{filteredRows.length} results</Text>
      </HStack>

      {/* Scanner Table */}
      <Box borderWidth="1px" borderColor="border.subtle" borderRadius="lg" bg="bg.card" overflow="hidden">
        <TableScrollArea maxH="70vh">
          <TableRoot size="sm">
            <TableHeader position="sticky" top={0} bg="bg.card" zIndex={1}>
              <TableRow>
                <SortHeader k="symbol" label="Ticker" />
                <TableColumnHeader>Sector</TableColumnHeader>
                <SortHeader k="stage_label" label="Stage" />
                <SortHeader k="action_label" label="Action" />
                <SortHeader k="scan_tier" label="Tier" />
                <SortHeader k="perf_1d" label="1D" align="right" />
                <SortHeader k="perf_5d" label="5D" align="right" />
                <SortHeader k="perf_20d" label="MTD" align="right" />
                <SortHeader k="perf_252d" label="YTD" align="right" />
                <SortHeader k="rsi" label="RSI" align="right" />
                <SortHeader k="ext_pct" label="Ext150%" align="right" />
                <SortHeader k="ema10_dist_n" label="EMA10d" align="right" />
                <SortHeader k="atrp_14" label="ATR%" align="right" />
                <SortHeader k="rs_mansfield_pct" label="RS" align="right" />
                <SortHeader k="sma150_slope" label="Slope" align="right" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredRows.slice(0, 500).map((row: any) => {
                const action = row.action_label || row.scan_action || '';
                return (
                  <TableRow key={row.symbol} transition="background 150ms ease" _hover={{ bg: 'bg.hover' }}>
                    <TableCell>
                      <SymbolLink symbol={row.symbol} />
                    </TableCell>
                    <TableCell fontSize="xs" color="fg.muted" maxW="100px" truncate>{row.sector || '—'}</TableCell>
                    <TableCell><StageBadge stage={row.stage_label || '—'} /></TableCell>
                    <TableCell>
                      {action && (
                        <Badge
                          variant="subtle"
                          size="sm"
                          colorPalette={ACTION_COLORS[action] || 'gray'}
                        >{action}</Badge>
                      )}
                    </TableCell>
                    <TableCell {...DATA_CELL}>{row.scan_tier || '—'}</TableCell>
                    <TableCell textAlign="right" {...DATA_CELL} color={heatColor(row.perf_1d)}>{fmtPct(row.perf_1d)}</TableCell>
                    <TableCell textAlign="right" {...DATA_CELL} color={heatColor(row.perf_5d)}>{fmtPct(row.perf_5d)}</TableCell>
                    <TableCell textAlign="right" {...DATA_CELL} color={heatColor(row.perf_20d)}>{fmtPct(row.perf_20d)}</TableCell>
                    <TableCell textAlign="right" {...DATA_CELL} color={heatColor(row.perf_252d)}>{fmtPct(row.perf_252d)}</TableCell>
                    <TableCell textAlign="right" {...DATA_CELL} color={
                      (row.rsi ?? 50) > 70 ? 'red.500' : (row.rsi ?? 50) < 30 ? 'green.500' : undefined
                    }>{row.rsi?.toFixed(0) ?? '—'}</TableCell>
                    <TableCell textAlign="right" {...DATA_CELL} color={heatColor(row.ext_pct)}>{fmtPct(row.ext_pct)}</TableCell>
                    <TableCell textAlign="right" {...DATA_CELL}>{row.ema10_dist_n?.toFixed(1) ?? '—'}</TableCell>
                    <TableCell textAlign="right" {...DATA_CELL}>{row.atrp_14?.toFixed(1) ?? '—'}%</TableCell>
                    <TableCell textAlign="right" {...DATA_CELL} color={heatColor(row.rs_mansfield_pct)}>{fmtPct(row.rs_mansfield_pct)}</TableCell>
                    <TableCell textAlign="right" {...DATA_CELL} color={heatColor(row.sma150_slope)}>{row.sma150_slope?.toFixed(2) ?? '—'}</TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </TableRoot>
        </TableScrollArea>
      </Box>
    </Stack>
  );
};

export default BottomUpView;
