import React from 'react';
import {
  Box,
  Heading,
  Text,
  HStack,
  Badge,
} from '@chakra-ui/react';
import toast from 'react-hot-toast';
import api from '../services/api';
import { useUserPreferences } from '../hooks/useUserPreferences';
import SortableTable, { type Column, type FilterGroup } from '../components/SortableTable';
import { formatMoney, formatDateTime } from '../utils/format';
import { useLocation } from 'react-router-dom';

const MarketTracked: React.FC = () => {
  const location = useLocation();
  const { timezone, currency } = useUserPreferences();
  const [rows, setRows] = React.useState<any[]>([]);
  const [loading, setLoading] = React.useState<boolean>(false);

  const load = async () => {
    if (loading) return;
    setLoading(true);
    try {
      const r = await api.get('/market-data/snapshots?limit=5000');
      const out = (r as any)?.data?.rows;
      setRows(Array.isArray(out) ? out : []);
    } catch (err: any) {
      toast.error(err?.message || 'Failed to load tracked snapshot table');
      setRows([]);
    } finally {
      setLoading(false);
    }
  };
  React.useEffect(() => { load(); }, []);

  const columns = React.useMemo<Column<any>[]>(() => {
    const fmtNum = (v: any, digits = 2) =>
      typeof v === 'number' && Number.isFinite(v) ? v.toFixed(digits) : '—';
    const fmtPct = (v: any) =>
      typeof v === 'number' && Number.isFinite(v) ? `${Math.round(v * 10) / 10}%` : '—';
    const fmtX = (v: any) =>
      typeof v === 'number' && Number.isFinite(v) ? `${Math.round(v * 10) / 10}x` : '—';
    const fmtTs = (v: any) => (v ? formatDateTime(String(v), timezone) : '—');
    const ema10DistPct = (r: any) => {
      const price = r?.current_price;
      const ema10 = r?.ema_10;
      if (typeof price !== 'number' || typeof ema10 !== 'number' || !Number.isFinite(price) || !Number.isFinite(ema10) || ema10 === 0) {
        return null;
      }
      return (price / ema10 - 1) * 100;
    };
    const stageScore = (v: any) => {
      const label = String(v || '').toUpperCase();
      // Stage desirability: 2A < 2B < 2C (green when it improves), then 1, then 3, then 4.
      const map: Record<string, number> = {
        '2A': 2.6,
        '2B': 2.8,
        '2C': 3.0,
        '2': 2.5,
        '1': 2.0,
        '3': 1.0,
        '4': 0.0,
      };
      return map[label] ?? null;
    };
    const stageBadge = (current: any, prev: any) => {
      const cur = stageScore(current);
      const prior = stageScore(prev);
      const label = String(current || 'UNKNOWN');
      if (cur == null || prior == null) {
        return <Badge variant="subtle" colorPalette="gray">{label}</Badge>;
      }
      if (cur > prior) {
        return <Badge variant="subtle" colorPalette="green">{label}</Badge>;
      }
      if (cur < prior) {
        return <Badge variant="subtle" colorPalette="red">{label}</Badge>;
      }
      return <Badge variant="subtle" colorPalette="yellow">{label}</Badge>;
    };

    // Keep default view compact. Level 1–4 fields are still sortable and visible via horizontal scroll.
    const fmtDays = (v: any) =>
      typeof v === 'number' && Number.isFinite(v) ? `${Math.max(0, Math.round(v))}d` : '—';

    return [
      { key: 'symbol', header: 'Symbol', accessor: (r) => r.symbol, sortable: true, sortType: 'string' },
      { key: 'as_of_timestamp', header: 'As of', accessor: (r) => r.as_of_timestamp || r.analysis_timestamp, sortable: true, sortType: 'date', render: (v) => fmtTs(v) },
      { key: 'current_price', header: 'Price', accessor: (r) => r.current_price, sortable: true, sortType: 'number', isNumeric: true, render: (v) => (typeof v === 'number' ? formatMoney(v, currency, { maximumFractionDigits: 2 }) : '—') },
      { key: 'market_cap', header: 'Mkt Cap', accessor: (r) => r.market_cap, sortable: true, sortType: 'number', isNumeric: true, render: (v) => (typeof v === 'number' ? Intl.NumberFormat('en', { notation: 'compact' }).format(v) : '—') },
      { key: 'perf_1d', header: 'Change %', accessor: (r) => r.perf_1d, sortable: true, sortType: 'number', isNumeric: true, render: (v) => fmtPct(v) },
      { key: 'perf_5d', header: 'Perf 1W', accessor: (r) => r.perf_5d, sortable: true, sortType: 'number', isNumeric: true, render: (v) => fmtPct(v) },
      { key: 'perf_20d', header: 'Perf 1M', accessor: (r) => r.perf_20d, sortable: true, sortType: 'number', isNumeric: true, render: (v) => fmtPct(v) },
      { key: 'pe_ttm', header: 'P/E', accessor: (r) => r.pe_ttm, sortable: true, sortType: 'number', isNumeric: true, render: (v) => fmtNum(v) },
      // PEG hidden (provider coverage is inconsistent)
      { key: 'roe', header: 'ROE %', accessor: (r) => r.roe, sortable: true, sortType: 'number', isNumeric: true, render: (v) => fmtPct(v) },
      // EPS QoQ hidden (provider coverage is inconsistent)
      { key: 'eps_growth_yoy', header: 'EPS YoY %', accessor: (r) => r.eps_growth_yoy, sortable: true, sortType: 'number', isNumeric: true, render: (v) => fmtPct(v) },
      // Rev QoQ hidden (provider coverage is inconsistent)
      { key: 'revenue_growth_yoy', header: 'Rev YoY %', accessor: (r) => r.revenue_growth_yoy, sortable: true, sortType: 'number', isNumeric: true, render: (v) => fmtPct(v) },
      { key: 'dividend_yield', header: 'Div Yield %', accessor: (r) => r.dividend_yield, sortable: true, sortType: 'number', isNumeric: true, render: (v) => fmtPct(v) },
      { key: 'beta', header: 'Beta', accessor: (r) => r.beta, sortable: true, sortType: 'number', isNumeric: true, render: (v) => fmtNum(v) },
      // Analyst rating hidden (coverage is inconsistent)
      // Earnings hidden (provider coverage is inconsistent)

      // Level 4
      {
        key: 'stage_label',
        header: 'Stage',
        accessor: (r) => r.stage_label,
        sortable: true,
        sortType: 'string',
        filterType: 'select',
        filterOptions: [
          { label: '1', value: '1' },
          { label: '2', value: '2' },
          { label: '2A', value: '2A' },
          { label: '2B', value: '2B' },
          { label: '2C', value: '2C' },
          { label: '3', value: '3' },
          { label: '4', value: '4' },
          { label: 'UNKNOWN', value: 'UNKNOWN' },
        ],
        render: (v, r) => stageBadge(v, r.previous_stage_label),
      },
      {
        key: 'current_stage_days',
        header: 'Time in Stage',
        accessor: (r) => r.current_stage_days,
        sortable: true,
        sortType: 'number',
        isNumeric: true,
        render: (v) => fmtDays(v),
      },
      {
        key: 'previous_stage_label',
        header: 'Previous Stage',
        accessor: (r) => r.previous_stage_label,
        sortable: true,
        sortType: 'string',
        filterType: 'select',
        filterOptions: [
          { label: '1', value: '1' },
          { label: '2', value: '2' },
          { label: '2A', value: '2A' },
          { label: '2B', value: '2B' },
          { label: '2C', value: '2C' },
          { label: '3', value: '3' },
          { label: '4', value: '4' },
          { label: 'UNKNOWN', value: 'UNKNOWN' },
        ],
        render: (v) => <Badge variant="subtle" colorPalette="gray">{String(v || 'UNKNOWN')}</Badge>,
      },
      {
        key: 'previous_stage_days',
        header: 'Time in Previous Stage',
        accessor: (r) => r.previous_stage_days,
        sortable: true,
        sortType: 'number',
        isNumeric: true,
        render: (v) => fmtDays(v),
      },

      // Level 3
      { key: 'rs_mansfield_pct', header: 'RS (Mansfield)', accessor: (r) => r.rs_mansfield_pct, sortable: true, sortType: 'number', isNumeric: true, render: (v) => fmtPct(v) },

      // Level 1 ranges
      { key: 'range_pos_20d', header: 'Range 20d%', accessor: (r) => r.range_pos_20d, sortable: true, sortType: 'number', isNumeric: true, render: (v) => fmtPct(v) },
      { key: 'range_pos_50d', header: 'Range 50d%', accessor: (r) => r.range_pos_50d, sortable: true, sortType: 'number', isNumeric: true, render: (v) => fmtPct(v) },
      { key: 'range_pos_52w', header: 'Range 52w%', accessor: (r) => r.range_pos_52w, sortable: true, sortType: 'number', isNumeric: true, render: (v) => fmtPct(v) },

      // Level 1 SMAs
      { key: 'sma_5', header: 'SMA 5', accessor: (r) => r.sma_5, sortable: true, sortType: 'number', isNumeric: true, render: (v) => fmtNum(v) },
      { key: 'sma_10', header: 'SMA 10', accessor: (r) => r.sma_10, sortable: true, sortType: 'number', isNumeric: true, render: (v) => fmtNum(v) },
      { key: 'sma_14', header: 'SMA 14', accessor: (r) => r.sma_14, sortable: true, sortType: 'number', isNumeric: true, render: (v) => fmtNum(v) },
      { key: 'sma_21', header: 'SMA 21', accessor: (r) => r.sma_21, sortable: true, sortType: 'number', isNumeric: true, render: (v) => fmtNum(v) },
      { key: 'sma_50', header: 'SMA 50', accessor: (r) => r.sma_50, sortable: true, sortType: 'number', isNumeric: true, render: (v) => fmtNum(v) },
      { key: 'sma_100', header: 'SMA 100', accessor: (r) => r.sma_100, sortable: true, sortType: 'number', isNumeric: true, render: (v) => fmtNum(v) },
      { key: 'sma_150', header: 'SMA 150', accessor: (r) => r.sma_150, sortable: true, sortType: 'number', isNumeric: true, render: (v) => fmtNum(v) },
      { key: 'sma_200', header: 'SMA 200', accessor: (r) => r.sma_200, sortable: true, sortType: 'number', isNumeric: true, render: (v) => fmtNum(v) },

      // Level 1 EMAs
      { key: 'ema_10', header: 'EMA 10', accessor: (r) => r.ema_10, sortable: true, sortType: 'number', isNumeric: true, render: (v) => fmtNum(v) },
      { key: 'ema_8', header: 'EMA 8', accessor: (r) => r.ema_8, sortable: true, sortType: 'number', isNumeric: true, render: (v) => fmtNum(v) },
      { key: 'ema_21', header: 'EMA 21', accessor: (r) => r.ema_21, sortable: true, sortType: 'number', isNumeric: true, render: (v) => fmtNum(v) },
      { key: 'ema_10_dist_pct', header: 'EMA10 Dist %', accessor: (r) => ema10DistPct(r), sortable: true, sortType: 'number', isNumeric: true, render: (v) => fmtPct(v) },

      // Level 1 ATRs + Level 2 ATR%
      { key: 'atr_14', header: 'ATR 14', accessor: (r) => r.atr_14, sortable: true, sortType: 'number', isNumeric: true, render: (v) => fmtNum(v) },
      { key: 'atr_30', header: 'ATR 30', accessor: (r) => r.atr_30, sortable: true, sortType: 'number', isNumeric: true, render: (v) => fmtNum(v) },
      { key: 'atrp_14', header: 'ATR% 14', accessor: (r) => r.atrp_14, sortable: true, sortType: 'number', isNumeric: true, render: (v) => fmtPct(v) },
      { key: 'atrp_30', header: 'ATR% 30', accessor: (r) => r.atrp_30, sortable: true, sortType: 'number', isNumeric: true, render: (v) => fmtPct(v) },

      // Level 2 ATR multiples
      { key: 'atrx_sma_21', header: '(P−SMA21)/ATR', accessor: (r) => r.atrx_sma_21, sortable: true, sortType: 'number', isNumeric: true, render: (v) => fmtX(v) },
      { key: 'atrx_sma_50', header: '(P−SMA50)/ATR', accessor: (r) => r.atrx_sma_50, sortable: true, sortType: 'number', isNumeric: true, render: (v) => fmtX(v) },
      { key: 'atrx_sma_100', header: '(P−SMA100)/ATR', accessor: (r) => r.atrx_sma_100, sortable: true, sortType: 'number', isNumeric: true, render: (v) => fmtX(v) },
      { key: 'atrx_sma_150', header: '(P−SMA150)/ATR', accessor: (r) => r.atrx_sma_150, sortable: true, sortType: 'number', isNumeric: true, render: (v) => fmtX(v) },

      // Context
      { key: 'sector', header: 'Sector', accessor: (r) => r.sector, sortable: true, sortType: 'string' },
      { key: 'industry', header: 'Industry', accessor: (r) => r.industry, sortable: true, sortType: 'string' },
    ];
  }, [currency, timezone]);

  const filterPresets = React.useMemo<Array<{ label: string; filters: FilterGroup }>>(() => [
    {
      label: 'Momentum Trend (Clean)',
      filters: {
        conjunction: 'AND' as const,
        rules: [
          {
            id: 'momentum_price_gt_sma50',
            columnKey: 'current_price',
            operator: 'gt' as const,
            valueSource: 'column' as const,
            valueColumnKey: 'sma_50',
          },
          {
            id: 'momentum_price_gt_sma200',
            columnKey: 'current_price',
            operator: 'gt' as const,
            valueSource: 'column' as const,
            valueColumnKey: 'sma_200',
          },
          {
            id: 'momentum_price_gt_ema21',
            columnKey: 'current_price',
            operator: 'gt' as const,
            valueSource: 'column' as const,
            valueColumnKey: 'ema_21',
          },
          {
            id: 'momentum_ema8_gt_ema21',
            columnKey: 'ema_8',
            operator: 'gt' as const,
            valueSource: 'column' as const,
            valueColumnKey: 'ema_21',
          },
          {
            id: 'momentum_sma21_gt_sma50',
            columnKey: 'sma_21',
            operator: 'gt' as const,
            valueSource: 'column' as const,
            valueColumnKey: 'sma_50',
          },
          {
            id: 'momentum_sma50_gt_sma200',
            columnKey: 'sma_50',
            operator: 'gt' as const,
            valueSource: 'column' as const,
            valueColumnKey: 'sma_200',
          },
        ],
      },
    },
    {
      label: 'Giants Waking Up (Large Cap Trend)',
      filters: {
        conjunction: 'AND' as const,
        rules: [
          {
            id: 'giant_mcap_gt_50b',
            columnKey: 'market_cap',
            operator: 'gt' as const,
            valueSource: 'literal' as const,
            value: '50000000000',
          },
          {
            id: 'giant_stage_2',
            columnKey: 'stage_label',
            operator: 'equals' as const,
            valueSource: 'literal' as const,
            value: '2',
          },
          {
            id: 'giant_price_gt_sma200',
            columnKey: 'current_price',
            operator: 'gt' as const,
            valueSource: 'column' as const,
            valueColumnKey: 'sma_200',
          },
          {
            id: 'giant_ema21_gt_sma50',
            columnKey: 'ema_21',
            operator: 'gt' as const,
            valueSource: 'column' as const,
            valueColumnKey: 'sma_50',
          },
          {
            id: 'giant_rs_positive',
            columnKey: 'rs_mansfield_pct',
            operator: 'gt' as const,
            valueSource: 'literal' as const,
            value: '0',
          },
        ],
      },
    },
    {
      label: 'Short-Term Squeeze (Range + ATR)',
      filters: {
        conjunction: 'AND' as const,
        rules: [
          {
            id: 'squeeze_range_20d_gt_80',
            columnKey: 'range_pos_20d',
            operator: 'gt' as const,
            valueSource: 'literal' as const,
            value: '80',
          },
          {
            id: 'squeeze_atrp14_gt_3',
            columnKey: 'atrp_14',
            operator: 'gt' as const,
            valueSource: 'literal' as const,
            value: '3',
          },
          {
            id: 'squeeze_price_gt_ema8',
            columnKey: 'current_price',
            operator: 'gt' as const,
            valueSource: 'column' as const,
            valueColumnKey: 'ema_8',
          },
          {
            id: 'squeeze_ema8_gt_ema21',
            columnKey: 'ema_8',
            operator: 'gt' as const,
            valueSource: 'column' as const,
            valueColumnKey: 'ema_21',
          },
        ],
      },
    },
    {
      label: 'Bullish Trend Day',
      filters: {
        conjunction: 'AND' as const,
        rules: [
          {
            id: 'bull_price_gt_sma50',
            columnKey: 'current_price',
            operator: 'gt' as const,
            valueSource: 'column' as const,
            valueColumnKey: 'sma_50',
          },
          {
            id: 'bull_sma50_gt_sma200',
            columnKey: 'sma_50',
            operator: 'gt' as const,
            valueSource: 'column' as const,
            valueColumnKey: 'sma_200',
          },
          {
            id: 'bull_rs_positive',
            columnKey: 'rs_mansfield_pct',
            operator: 'gt' as const,
            valueSource: 'literal' as const,
            value: '0',
          },
        ],
      },
    },
  ],
    []);

  const deepLinkFilters = React.useMemo<FilterGroup | undefined>(() => {
    const params = new URLSearchParams(location.search || '');
    const symbols = (params.get('symbols') || '')
      .split(',')
      .map((s) => s.trim().toUpperCase())
      .filter(Boolean);
    if (symbols.length > 0) {
      return {
        conjunction: 'OR',
        rules: symbols.map((sym, i) => ({
          id: `deep_symbol_${i}_${sym}`,
          columnKey: 'symbol',
          operator: 'equals',
          valueSource: 'literal',
          value: sym,
        })),
      };
    }

    const sector = (params.get('sector') || '').trim();
    if (sector) {
      return {
        conjunction: 'AND',
        rules: [
          {
            id: 'deep_sector',
            columnKey: 'sector',
            operator: 'equals',
            valueSource: 'literal',
            value: sector,
          },
        ],
      };
    }

    const preset = (params.get('preset') || '').trim();
    if (preset) {
      const map: Record<string, string> = {
        momentum: 'Momentum Trend (Clean)',
        giants: 'Giants Waking Up (Large Cap Trend)',
        squeeze: 'Short-Term Squeeze (Range + ATR)',
        bullish: 'Bullish Trend Day',
      };
      const label = map[preset];
      if (label) {
        const selected = filterPresets.find((p) => p.label === label);
        if (selected) return selected.filters;
      }
    }
    return undefined;
  }, [location.search, filterPresets]);

  return (
    <Box p={4}>
      <HStack justify="space-between" align="end" mb={3} flexWrap="wrap" gap={2}>
        <Box>
          <Heading size="md">Market Tracked</Heading>
          <Text color="fg.muted" fontSize="sm">
            Tracked symbols with technical indicators. Use presets or custom filters to find setups.
          </Text>
          <Text color="fg.muted" fontSize="xs">
            Indicators are computed from daily OHLCV and the SPY benchmark. Sector/industry come from fundamentals.
          </Text>
        </Box>
        <Badge variant="subtle">{rows.length} rows</Badge>
      </HStack>

      <Box w="full" borderWidth="1px" borderColor="border.subtle" borderRadius="xl" bg="bg.card">
        <SortableTable
          key={location.search || 'tracked-default'}
          data={rows}
          columns={columns}
          defaultSortBy="symbol"
          defaultSortOrder="asc"
          maxHeight="70vh"
          filtersEnabled
          filterPresets={filterPresets}
          initialFilters={deepLinkFilters}
          emptyMessage={loading ? 'Loading…' : 'No tracked symbols yet.'}
        />
      </Box>
    </Box>
  );
};

export default MarketTracked;

