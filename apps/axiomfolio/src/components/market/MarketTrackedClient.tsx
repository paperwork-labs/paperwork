"use client";

import React from 'react';
import toast from 'react-hot-toast';
import { useSearchParams } from 'next/navigation';
import { Check, ChevronDown, Edit2, X } from 'lucide-react';

import SortableTable, { type Column } from '@/components/SortableTable';
import { ChartContext, SymbolLink, ChartSlidePanel, PortfolioSymbolsContext } from '@/components/market/SymbolChartUI';
import TradeModal from '@/components/orders/TradeModal';
import StageBadge from '@/components/shared/StageBadge';
import PnlText from '@/components/shared/PnlText';
import { useBackendUser } from '@/hooks/use-backend-user';
import { isPlatformAdminRole } from '@/utils/userRole';
import { ETF_SYMBOL_SET } from '@/constants/etf';
import { STAGE_COLORS, ACTION_COLORS } from '@/constants/chart';
import { STAGE_SUBTLE_BADGE, STAGE_SOLID_BADGE } from '@/lib/stageTailwind';
import { usePortfolioSymbols } from '@/hooks/usePortfolioSymbols';
import { useUserPreferences } from '@/hooks/useUserPreferences';
import { useSnapshotTable } from '@/hooks/useSnapshotTable';
import { useSnapshotAggregates, formatAggregateCount } from '@/hooks/useSnapshotAggregates';
import { useIvCoverageBatch, type IvCoverage } from '@/hooks/useIvCoverage';
import api from '@/services/api';
import { formatDateTime, formatMoney } from '@/utils/format';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Page, PageHeader } from '@paperwork-labs/ui';
import Pagination from '@/components/ui/Pagination';
import { cn } from '@/lib/utils';
import { semanticTextColorClass } from '@/lib/semantic-text-color';
import type { SnapshotTableParams, SnapshotAggregateParams } from '@/types/market';

/* ─── Types ─── */

type TradeTarget = { symbol: string; currentPrice: number; sharesHeld: number; averageCost?: number } | null;

type EditablePriceCellProps = {
  symbol: string;
  value: number | null | undefined;
  canEdit: boolean;
  onSave: (symbol: string, nextValue: number | null) => Promise<void>;
};

type PresetConfig = {
  type: 'action_labels' | 'scan_tiers' | 'preset';
  key: string;
  paramValue: string;
};

type ColumnProfile = 'overview' | 'technical' | 'fundamental' | 'plan' | 'full';

/* ─── Constants ─── */

const ACTION_PRESETS: Array<{ key: string; label: string; paramValue: string }> = [
  { key: 'buy', label: 'Buy Candidates', paramValue: 'BUY' },
  { key: 'watch', label: 'Watch List', paramValue: 'WATCH' },
  { key: 'hold', label: 'Hold and Monitor', paramValue: 'HOLD' },
  { key: 'short', label: 'Short Candidates', paramValue: 'SHORT' },
  { key: 'reduce', label: 'Reduce or Exit', paramValue: 'REDUCE,AVOID' },
];

const SCAN_TIER_PRESETS: Array<{ key: string; label: string; paramValue: string }> = [
  { key: 'breakout_elite', label: 'Breakout Elite', paramValue: 'Breakout Elite' },
  { key: 'early_base', label: 'Early Base', paramValue: 'Early Base' },
];

const TRADING_LENS_PRESETS: Array<{ key: string; label: string; paramValue: string }> = [
  { key: 'pullback_buy_zone', label: 'Pullback Buy Zone', paramValue: 'pullback_buy_zone' },
  { key: 'ma_alignment', label: 'Clean Trend (MA Stack)', paramValue: 'ma_alignment' },
  { key: 'large_cap_leaders', label: 'Large Cap Leaders', paramValue: 'large_cap_leaders' },
  { key: 'squeeze_setup', label: 'Squeeze Setup', paramValue: 'squeeze_setup' },
];

const COLUMN_PROFILE_SETS: Record<ColumnProfile, Set<string> | null> = {
  overview: new Set([
    'symbol', 'name', 'current_price', 'stage_label', 'current_stage_days',
    'perf_1d', 'rs_mansfield_pct', 'sector', 'scan_tier', 'action_label',
  ]),
  technical: new Set([
    'symbol', 'current_price', 'stage_label', 'rs_mansfield_pct',
    'ema_10_dist_pct', 'ext_pct', 'vol_ratio', 'atrp_14',
    'range_pos_20d', 'range_pos_52w', 'scan_tier', 'action_label',
  ]),
  fundamental: new Set([
    'symbol', 'current_price', 'pe_ttm', 'roe', 'eps_growth_yoy',
    'revenue_growth_yoy', 'dividend_yield', 'beta', 'market_cap',
  ]),
  plan: new Set([
    'symbol', 'current_price', 'entry_price', 'exit_price', 'stage_label',
    'rs_mansfield_pct', 'perf_1d', 'portfolio_qty', 'portfolio_pnl',
  ]),
  full: null,
};

const COLUMN_PROFILE_OPTIONS: Array<{ key: ColumnProfile; label: string }> = [
  { key: 'overview', label: 'Overview' },
  { key: 'technical', label: 'Technical' },
  { key: 'fundamental', label: 'Fundamental' },
  { key: 'plan', label: 'Plan' },
  { key: 'full', label: 'Full' },
];

const INDEX_SCOPE_OPTIONS: Array<{ key: string; label: string; paramValue?: string }> = [
  { key: 'all', label: 'All' },
  { key: 'SP500', label: 'S&P 500', paramValue: 'SP500' },
  { key: 'NASDAQ100', label: 'NASDAQ 100', paramValue: 'NASDAQ100' },
  { key: 'DOW30', label: 'DOW 30', paramValue: 'DOW30' },
  { key: 'RUSSELL2000', label: 'Russell 2000', paramValue: 'RUSSELL2000' },
  { key: 'holdings', label: 'My Holdings' },
  { key: 'etf', label: 'ETFs' },
];

const ALL_STAGES = ['1A', '1B', '2A', '2B', '2C', '3A', '3B', '4A', '4B', '4C'] as const;
const ALL_ACTIONS = ['BUY', 'WATCH', 'HOLD', 'SHORT', 'REDUCE', 'AVOID'] as const;
const LS_METRIC_STRIP_KEY = 'tracked-metric-strip-collapsed';
const DEFAULT_SCAN_TIERS = 'Breakout Elite,Breakout Standard';

const ACTION_PILL_SUBTLE: Record<string, string> = {
  green:  'border-green-600/30 bg-green-600/10 text-green-700 dark:text-green-400',
  blue:   'border-blue-600/30 bg-blue-600/10 text-blue-700 dark:text-blue-400',
  gray:   'border-gray-500/30 bg-gray-500/10 text-gray-600 dark:text-gray-400',
  orange: 'border-orange-600/30 bg-orange-600/10 text-orange-700 dark:text-orange-400',
  red:    'border-red-600/30 bg-red-600/10 text-red-700 dark:text-red-400',
};

const ACTION_PILL_SOLID: Record<string, string> = {
  green:  'border-transparent bg-green-600 text-white',
  blue:   'border-transparent bg-blue-600 text-white',
  gray:   'border-transparent bg-gray-600 text-white',
  orange: 'border-transparent bg-orange-600 text-white',
  red:    'border-transparent bg-red-600 text-white',
};

/* ─── URL State Parser ─── */

interface UrlDerivedState {
  preset: PresetConfig | null;
  filterStage: string | null;
  metricAction: string | null;
  indexScope: string;
  symbolsFilter: string[];
  sectors: string | undefined;
}

function parseUrlState(search: string): UrlDerivedState {
  const p = new URLSearchParams(search);

  let preset: PresetConfig | null = null;
  let metricAction: string | null = null;

  const actionLabels = p.get('action_labels');
  if (actionLabels) {
    const match = ACTION_PRESETS.find((pr) => pr.paramValue === actionLabels);
    if (match) {
      preset = { type: 'action_labels', key: match.key, paramValue: match.paramValue };
    } else {
      metricAction = actionLabels;
    }
  }

  if (!preset) {
    const presetParam = p.get('preset');
    if (presetParam) {
      const match = TRADING_LENS_PRESETS.find((pr) => pr.paramValue === presetParam);
      if (match) preset = { type: 'preset', key: match.key, paramValue: match.paramValue };
    }
  }

  if (!preset) {
    const scanTiers = p.get('scan_tiers');
    if (scanTiers) {
      const match = SCAN_TIER_PRESETS.find((pr) => pr.paramValue === scanTiers);
      if (match) preset = { type: 'scan_tiers', key: match.key, paramValue: match.paramValue };
    }
  }

  let indexScope = 'all';
  const indexName = p.get('index_name');
  if (indexName) {
    const match = INDEX_SCOPE_OPTIONS.find((s) => s.paramValue === indexName);
    if (match) indexScope = match.key;
  }

  const symbols = (p.get('symbols') || '')
    .split(',')
    .map((s) => s.trim().toUpperCase())
    .filter(Boolean);

  const sectors = p.get('sectors') || p.get('sector') || undefined;
  const filterStage = p.get('filter_stage') || null;

  return { preset, filterStage, metricAction, indexScope, symbolsFilter: symbols, sectors };
}

/* ─── EditablePriceCell ─── */

const EditablePriceCell: React.FC<EditablePriceCellProps> = ({ symbol, value, canEdit, onSave }) => {
  const [editing, setEditing] = React.useState(false);
  const [draft, setDraft] = React.useState<string>(value == null ? '' : String(value));
  const [saving, setSaving] = React.useState(false);

  React.useEffect(() => {
    setDraft(value == null ? '' : String(value));
  }, [value]);

  const startEdit = () => {
    setDraft(value == null ? '' : String(value));
    setEditing(true);
  };

  const cancelEdit = () => {
    setDraft(value == null ? '' : String(value));
    setEditing(false);
  };

  const submit = async () => {
    const trimmed = draft.trim();
    if (!trimmed) {
      setSaving(true);
      try {
        await onSave(symbol, null);
        setEditing(false);
      } catch (err: any) {
        toast.error(err?.message || 'Failed to update price');
      } finally {
        setSaving(false);
      }
      return;
    }
    const parsed = Number(trimmed);
    if (!Number.isFinite(parsed) || parsed <= 0) {
      toast.error('Price must be a positive number');
      return;
    }
    setSaving(true);
    try {
      await onSave(symbol, parsed);
      setEditing(false);
    } catch (err: any) {
      toast.error(err?.message || 'Failed to update price');
    } finally {
      setSaving(false);
    }
  };

  if (!canEdit && value == null) return <>—</>;
  if (!canEdit) return <>{value?.toFixed(2)}</>;

  if (editing) {
    return (
      <div className="flex items-center gap-1">
        <Input
          className="h-6 w-[88px] px-2 text-xs"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="—"
        />
        <Button type="button" aria-label="Save" size="icon-xs" variant="ghost" onClick={submit} disabled={saving}>
          <Check className="size-3" />
        </Button>
        <Button type="button" aria-label="Cancel" size="icon-xs" variant="ghost" onClick={cancelEdit} disabled={saving}>
          <X className="size-3" />
        </Button>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-1">
      <span className="text-xs">{value == null ? '—' : value.toFixed(2)}</span>
      <Button type="button" aria-label="Edit" size="icon-xs" variant="ghost" onClick={startEdit}>
        <Edit2 className="size-3" />
      </Button>
      {value == null ? (
        <Button type="button" size="xs" variant="ghost" className="h-6 px-2 text-xs" onClick={startEdit}>
          Set
        </Button>
      ) : null}
    </div>
  );
};

/* ─── MarketTracked ─── */

const MarketTrackedClient: React.FC = () => {
  const searchParams = useSearchParams();
  const locationSearch = React.useMemo(() => {
    const s = searchParams.toString();
    return s ? `?${s}` : '';
  }, [searchParams]);
  const { timezone, currency } = useUserPreferences();
  const { user } = useBackendUser();
  const portfolioQuery = usePortfolioSymbols();
  const portfolioSymbols = portfolioQuery.data ?? {};

  /* URL-derived mode (not state — re-derives on every URL change) */
  const urlParams = React.useMemo(() => new URLSearchParams(locationSearch), [locationSearch]);
  const mode = urlParams.get('mode') === 'scan' ? ('scan' as const) : ('track' as const);
  const canEditPlan = mode === 'track' && (isPlatformAdminRole(user?.role) || user?.role === 'analyst');

  /* Chart / trade panel state */
  const [chartSymbol, setChartSymbol] = React.useState<string | null>(null);
  const openChart = React.useCallback((sym: string) => setChartSymbol(sym), []);
  const [tradeTarget, setTradeTarget] = React.useState<TradeTarget>(null);

  /* Sorting and pagination */
  const [sortBy, setSortBy] = React.useState(() => (mode === 'scan' ? 'rs_mansfield_pct' : 'symbol'));
  const [sortDir, setSortDir] = React.useState<'asc' | 'desc'>(() => (mode === 'scan' ? 'desc' : 'asc'));
  const [page, setPage] = React.useState(1);
  const [pageSize, setPageSize] = React.useState(100);
  const [compact, setCompact] = React.useState(false);

  /* Filter / preset / profile state — initialized from URL */
  const [initUrl] = React.useState(() =>
    parseUrlState(typeof window !== 'undefined' ? window.location.search : ''),
  );
  const [activePreset, setActivePreset] = React.useState<PresetConfig | null>(initUrl.preset);
  const [filterStage, setFilterStage] = React.useState<string | null>(initUrl.filterStage);
  const [metricActionFilter, setMetricActionFilter] = React.useState<string | null>(initUrl.metricAction);
  const [indexScope, setIndexScope] = React.useState(initUrl.indexScope);
  const [symbolsFilter, setSymbolsFilter] = React.useState(initUrl.symbolsFilter);
  const [deepLinkSectors, setDeepLinkSectors] = React.useState(initUrl.sectors);
  const [columnProfile, setColumnProfile] = React.useState<ColumnProfile>('overview');

  /* Metric strip collapse — persisted in localStorage */
  const [metricStripCollapsed, setMetricStripCollapsed] = React.useState(() => {
    try { return localStorage.getItem(LS_METRIC_STRIP_KEY) === 'true'; } catch { return false; }
  });

  /* Derived booleans from index scope */
  const showHoldings = indexScope === 'holdings';
  const showEtfOnly = indexScope === 'etf';

  /* Reset sort defaults when mode changes */
  React.useEffect(() => {
    setSortBy(mode === 'scan' ? 'rs_mansfield_pct' : 'symbol');
    setSortDir(mode === 'scan' ? 'desc' : 'asc');
    setPage(1);
  }, [mode]);

  /* Sync filter state on URL navigation (subsequent navigations) */
  React.useEffect(() => {
    const state = parseUrlState(locationSearch);
    setActivePreset(state.preset);
    setFilterStage(state.filterStage);
    setMetricActionFilter(state.metricAction);
    setIndexScope(state.indexScope);
    setSymbolsFilter(state.symbolsFilter);
    setDeepLinkSectors(state.sectors);
  }, [locationSearch]);

  /* ─── Event handlers ─── */

  const handleSortChange = React.useCallback((key: string, dir: 'asc' | 'desc') => {
    setSortBy(key);
    setSortDir(dir);
    setPage(1);
  }, []);

  const handlePageSizeChange = React.useCallback((size: number) => {
    setPageSize(size);
    setPage(1);
  }, []);

  const handlePresetClick = React.useCallback((cfg: PresetConfig) => {
    setActivePreset((prev) => {
      if (prev?.key === cfg.key) return null;
      return cfg;
    });
    if (cfg.type === 'action_labels') setMetricActionFilter(null);
    setPage(1);
  }, []);

  const handleStageClick = React.useCallback((stage: string) => {
    setFilterStage((prev) => (prev === stage ? null : stage));
    setPage(1);
  }, []);

  const handleActionClick = React.useCallback(
    (action: string) => {
      if (activePreset?.type === 'action_labels') setActivePreset(null);
      setMetricActionFilter((prev) => (prev === action ? null : action));
      setPage(1);
    },
    [activePreset],
  );

  const clearMetricFilters = React.useCallback(() => {
    setFilterStage(null);
    setMetricActionFilter(null);
    setPage(1);
  }, []);

  const toggleMetricStrip = React.useCallback(() => {
    setMetricStripCollapsed((prev) => {
      const next = !prev;
      try { localStorage.setItem(LS_METRIC_STRIP_KEY, String(next)); } catch { /* noop */ }
      return next;
    });
  }, []);

  const updateTrackedPlan = React.useCallback(async (
    symbol: string,
    patch: { entry_price?: number | null; exit_price?: number | null },
  ) => {
    try {
      await api.patch(`/market-data/tracked-plan/${encodeURIComponent(symbol)}`, patch);
    } catch (err: any) {
      toast.error(err?.message || 'Failed to update tracked plan');
      throw err;
    }
  }, []);

  /* ─── Table params ─── */

  const offset = (page - 1) * pageSize;

  const tableParams = React.useMemo<SnapshotTableParams>(() => {
    const params: SnapshotTableParams = {
      sort_by: sortBy,
      sort_dir: sortDir,
      offset,
      limit: pageSize,
      include_plan: true,
    };

    if (activePreset?.type === 'action_labels') {
      params.action_labels = activePreset.paramValue;
    } else if (metricActionFilter) {
      params.action_labels = metricActionFilter;
    }

    if (activePreset?.type === 'scan_tiers') {
      params.scan_tiers = activePreset.paramValue;
    } else if (mode === 'scan' && !activePreset) {
      params.scan_tiers = DEFAULT_SCAN_TIERS;
    }

    if (activePreset?.type === 'preset') {
      params.preset = activePreset.paramValue;
    }

    if (filterStage) params.filter_stage = filterStage;

    const scope = INDEX_SCOPE_OPTIONS.find((s) => s.key === indexScope);
    if (scope?.paramValue) params.index_name = scope.paramValue;

    if (deepLinkSectors) params.sectors = deepLinkSectors;

    if (symbolsFilter.length > 0) {
      params.symbols = symbolsFilter.join(',');
    }

    return params;
  }, [sortBy, sortDir, offset, pageSize, activePreset, metricActionFilter, filterStage, indexScope, deepLinkSectors, mode, symbolsFilter]);

  /* ─── Data fetching ─── */

  const { data: tableData, isPending: loading } = useSnapshotTable(tableParams);
  const rows = tableData?.rows ?? [];
  const total = tableData?.total ?? 0;

  // G5: fetch IV-rank coverage for every visible symbol. The hook
  // dedupes + sorts symbols internally so we can hand it ``rows`` as-is.
  const ivSymbols = React.useMemo(
    () => rows.map((r: any) => String(r?.symbol || '')).filter(Boolean),
    [rows],
  );
  const ivCoverageQuery = useIvCoverageBatch(ivSymbols);
  const ivCoverageMap: Record<string, IvCoverage> = ivCoverageQuery.data ?? {};

  const aggregateParams = React.useMemo<SnapshotAggregateParams>(() => {
    const p: SnapshotAggregateParams = {};
    if (tableParams.filter_stage) p.filter_stage = tableParams.filter_stage;
    if (tableParams.sectors) p.sectors = tableParams.sectors;
    if (tableParams.scan_tiers) p.scan_tiers = tableParams.scan_tiers;
    if (tableParams.regime_state) p.regime_state = tableParams.regime_state;
    if (tableParams.action_labels) p.action_labels = tableParams.action_labels;
    if (tableParams.preset) p.preset = tableParams.preset;
    if (tableParams.index_name) p.index_name = tableParams.index_name;
    if (tableParams.symbols) p.symbols = tableParams.symbols;
    return p;
  }, [tableParams]);

  const aggregatesQuery = useSnapshotAggregates(aggregateParams);
  const aggregates = aggregatesQuery.data;
  const aggregatesCountLabel = formatAggregateCount(aggregatesQuery);

  /* ─── Column visibility helper ─── */

  const isColHidden = React.useCallback(
    (key: string): boolean => {
      if (key === 'actions') return false;
      if (columnProfile === 'full') {
        if (key === 'portfolio_qty' || key === 'portfolio_pnl') return !showHoldings;
        return false;
      }
      const profileSet = COLUMN_PROFILE_SETS[columnProfile];
      if (!profileSet) return false;
      return !profileSet.has(key);
    },
    [columnProfile, showHoldings],
  );

  /* ─── Column definitions ─── */

  const columns = React.useMemo<Column<any>[]>(() => {
    const fmtNum = (v: any, digits = 2) =>
      typeof v === 'number' && Number.isFinite(v) ? v.toFixed(digits) : '—';
    const fmtPct = (v: any) =>
      typeof v === 'number' && Number.isFinite(v) ? `${Math.round(v * 10) / 10}%` : '—';
    const fmtX = (v: any) =>
      typeof v === 'number' && Number.isFinite(v) ? `${Math.round(v * 10) / 10}x` : '—';
    const fmtTs = (v: any) => (v ? formatDateTime(String(v), timezone) : '—');
    const fmtDays = (v: any) =>
      typeof v === 'number' && Number.isFinite(v) ? `${Math.max(0, Math.round(v))}d` : '—';
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
      const map: Record<string, number> = { '2A': 2.6, '2B': 2.8, '2C': 3.0, '2': 2.5, '1': 2.0, '3': 1.0, '4': 0.0 };
      return map[label] ?? null;
    };

    return [
      {
        key: 'symbol', header: 'Symbol', accessor: (r) => r.symbol, sortable: true, sortType: 'string',
        hidden: isColHidden('symbol'),
        render: (_v, r) => (
          <div className="flex items-center gap-1">
            <SymbolLink symbol={String(r?.symbol || '')} />
            {mode === 'track' && String(r?.symbol || '') in portfolioSymbols && (
              <Badge variant="secondary" className="h-4 px-1.5 text-[10px] font-medium">Held</Badge>
            )}
          </div>
        ),
      },
      { key: 'name', header: 'Name', accessor: (r) => r.name, sortable: true, sortType: 'string', hidden: isColHidden('name'), render: (v) => String(v || '—') },
      { key: 'current_price', header: 'Price', accessor: (r) => r.current_price, sortable: true, sortType: 'number', isNumeric: true, hidden: isColHidden('current_price'), render: (v) => (typeof v === 'number' ? formatMoney(v, currency, { maximumFractionDigits: 2 }) : '—') },
      {
        key: 'entry_price', header: 'Entry', accessor: (r) => r.entry_price, sortable: true, sortType: 'number', isNumeric: true,
        hidden: isColHidden('entry_price'),
        render: (v, r) => (
          <EditablePriceCell
            symbol={String(r?.symbol || '')}
            value={typeof v === 'number' ? v : null}
            canEdit={canEditPlan}
            onSave={(symbol, nextValue) => updateTrackedPlan(symbol, { entry_price: nextValue })}
          />
        ),
      },
      {
        key: 'exit_price', header: 'Exit', accessor: (r) => r.exit_price, sortable: true, sortType: 'number', isNumeric: true,
        hidden: isColHidden('exit_price'),
        render: (v, r) => (
          <EditablePriceCell
            symbol={String(r?.symbol || '')}
            value={typeof v === 'number' ? v : null}
            canEdit={canEditPlan}
            onSave={(symbol, nextValue) => updateTrackedPlan(symbol, { exit_price: nextValue })}
          />
        ),
      },
      { key: 'market_cap', header: 'Mkt Cap', accessor: (r) => r.market_cap, sortable: true, sortType: 'number', isNumeric: true, hidden: isColHidden('market_cap'), render: (v) => (typeof v === 'number' ? Intl.NumberFormat('en', { notation: 'compact' }).format(v) : '—') },
      { key: 'perf_1d', header: 'Change %', accessor: (r) => r.perf_1d, sortable: true, sortType: 'number', isNumeric: true, hidden: isColHidden('perf_1d'), render: (v) => fmtPct(v) },
      { key: 'perf_5d', header: 'Perf 1W', accessor: (r) => r.perf_5d, sortable: true, sortType: 'number', isNumeric: true, hidden: isColHidden('perf_5d'), render: (v) => fmtPct(v) },
      { key: 'perf_20d', header: 'Perf 1M', accessor: (r) => r.perf_20d, sortable: true, sortType: 'number', isNumeric: true, hidden: isColHidden('perf_20d'), render: (v) => fmtPct(v) },
      {
        key: 'stage_label', header: 'Stage', accessor: (r) => r.stage_label, sortable: true, sortType: 'string',
        hidden: isColHidden('stage_label'),
        filterType: 'select',
        filterOptions: [
          { label: '1', value: '1' }, { label: '2', value: '2' },
          { label: '2A', value: '2A' }, { label: '2B', value: '2B' }, { label: '2C', value: '2C' },
          { label: '3', value: '3' }, { label: '4', value: '4' }, { label: 'New', value: 'UNKNOWN' },
        ],
        render: (v, r) => {
          const cur = stageScore(v);
          const prev = stageScore(r.previous_stage_label);
          const changed = prev != null && cur != null && cur !== prev;
          const displayStage = v === 'UNKNOWN' ? 'New' : v;
          return (
            <div className="flex items-center gap-1">
              <StageBadge stage={displayStage || '?'} />
              {changed && (
                <span className={cn('text-xs', semanticTextColorClass(cur! > prev! ? 'green.400' : 'red.400'))}>
                  {cur! > prev! ? '▲' : '▼'}
                </span>
              )}
            </div>
          );
        },
      },
      { key: 'current_stage_days', header: 'Time in Stage', accessor: (r) => r.current_stage_days, sortable: true, sortType: 'number', isNumeric: true, hidden: isColHidden('current_stage_days'), render: (v) => fmtDays(v) },
      {
        key: 'previous_stage_label', header: 'Previous Stage', accessor: (r) => r.previous_stage_label, sortable: true, sortType: 'string',
        hidden: isColHidden('previous_stage_label'),
        filterType: 'select',
        filterOptions: [
          { label: '1', value: '1' }, { label: '2', value: '2' },
          { label: '2A', value: '2A' }, { label: '2B', value: '2B' }, { label: '2C', value: '2C' },
          { label: '3', value: '3' }, { label: '4', value: '4' }, { label: 'New', value: 'UNKNOWN' },
        ],
        render: (v) => {
          const display = v === 'UNKNOWN' ? 'New' : v ? String(v) : '—';
          return <Badge variant="secondary" className="font-normal">{display}</Badge>;
        },
      },
      { key: 'previous_stage_days', header: 'Time in Previous Stage', accessor: (r) => r.previous_stage_days, sortable: true, sortType: 'number', isNumeric: true, hidden: isColHidden('previous_stage_days'), render: (v) => fmtDays(v) },
      { key: 'pe_ttm', header: 'P/E', accessor: (r) => r.pe_ttm, sortable: true, sortType: 'number', isNumeric: true, hidden: isColHidden('pe_ttm'), render: (v) => fmtNum(v) },
      { key: 'roe', header: 'ROE %', accessor: (r) => r.roe, sortable: true, sortType: 'number', isNumeric: true, hidden: isColHidden('roe'), render: (v) => fmtPct(v) },
      { key: 'eps_growth_yoy', header: 'EPS YoY %', accessor: (r) => r.eps_growth_yoy, sortable: true, sortType: 'number', isNumeric: true, hidden: isColHidden('eps_growth_yoy'), render: (v) => fmtPct(v) },
      { key: 'revenue_growth_yoy', header: 'Rev YoY %', accessor: (r) => r.revenue_growth_yoy, sortable: true, sortType: 'number', isNumeric: true, hidden: isColHidden('revenue_growth_yoy'), render: (v) => fmtPct(v) },
      { key: 'dividend_yield', header: 'Div Yield %', accessor: (r) => r.dividend_yield, sortable: true, sortType: 'number', isNumeric: true, hidden: isColHidden('dividend_yield'), render: (v) => fmtPct(v) },
      { key: 'beta', header: 'Beta', accessor: (r) => r.beta, sortable: true, sortType: 'number', isNumeric: true, hidden: isColHidden('beta'), render: (v) => fmtNum(v) },
      { key: 'rs_mansfield_pct', header: 'RS (Mansfield)', accessor: (r) => r.rs_mansfield_pct, sortable: true, sortType: 'number', isNumeric: true, hidden: isColHidden('rs_mansfield_pct'), render: (v) => typeof v === 'number' && Number.isFinite(v) ? (v > 0 ? `+${v.toFixed(1)}` : v.toFixed(1)) : '—' },
      {
        key: 'iv_rank_252',
        header: 'IV Rank',
        // G5: source-of-truth is ``HistoricalIV.iv_rank_252`` via the
        // batch hook above. We distinguish four states: numeric (rank
        // present), ramping (<252 samples), absent (no history), and
        // loading (query still in flight). NEVER render 0 for a missing
        // value -- that would hide a coverage gap.
        accessor: (r) => {
          const cov = ivCoverageMap[String(r?.symbol || '')];
          return cov?.hasRank && typeof cov.ivRank === 'number' ? cov.ivRank : null;
        },
        sortable: true,
        sortType: 'number',
        isNumeric: true,
        hidden: isColHidden('iv_rank_252'),
        render: (_v, r) => {
          const sym = String(r?.symbol || '');
          const cov = ivCoverageMap[sym];
          if (ivCoverageQuery.isPending && !cov) {
            return <span className="text-xs text-muted-foreground" aria-label="Loading IV rank">…</span>;
          }
          if (!cov) {
            return <span className="text-xs text-muted-foreground">—</span>;
          }
          if (cov.isRamping) {
            return (
              <span
                className="text-xs text-muted-foreground"
                title="IV rank requires 1 year of history; ramping."
              >
                N/A
              </span>
            );
          }
          if (cov.hasRank && typeof cov.ivRank === 'number') {
            return <span className="font-mono text-xs">{Math.round(cov.ivRank)}</span>;
          }
          return <span className="text-xs text-muted-foreground">—</span>;
        },
      },
      { key: 'ext_pct', header: 'Ext %', accessor: (r) => r.ext_pct, sortable: true, sortType: 'number', isNumeric: true, hidden: isColHidden('ext_pct'), render: (v) => fmtPct(v) },
      { key: 'vol_ratio', header: 'Vol Ratio', accessor: (r) => r.vol_ratio, sortable: true, sortType: 'number', isNumeric: true, hidden: isColHidden('vol_ratio'), render: (v) => fmtX(v) },
      { key: 'range_pos_20d', header: 'Range 20d%', accessor: (r) => r.range_pos_20d, sortable: true, sortType: 'number', isNumeric: true, hidden: isColHidden('range_pos_20d'), render: (v) => fmtPct(v) },
      { key: 'range_pos_50d', header: 'Range 50d%', accessor: (r) => r.range_pos_50d, sortable: true, sortType: 'number', isNumeric: true, hidden: isColHidden('range_pos_50d'), render: (v) => fmtPct(v) },
      { key: 'range_pos_52w', header: 'Range 52w%', accessor: (r) => r.range_pos_52w, sortable: true, sortType: 'number', isNumeric: true, hidden: isColHidden('range_pos_52w'), render: (v) => fmtPct(v) },
      { key: 'sma_5', header: 'SMA 5', accessor: (r) => r.sma_5, sortable: true, sortType: 'number', isNumeric: true, hidden: isColHidden('sma_5'), render: (v) => fmtNum(v) },
      { key: 'sma_10', header: 'SMA 10', accessor: (r) => r.sma_10, sortable: true, sortType: 'number', isNumeric: true, hidden: isColHidden('sma_10'), render: (v) => fmtNum(v) },
      { key: 'sma_14', header: 'SMA 14', accessor: (r) => r.sma_14, sortable: true, sortType: 'number', isNumeric: true, hidden: isColHidden('sma_14'), render: (v) => fmtNum(v) },
      { key: 'sma_21', header: 'SMA 21', accessor: (r) => r.sma_21, sortable: true, sortType: 'number', isNumeric: true, hidden: isColHidden('sma_21'), render: (v) => fmtNum(v) },
      { key: 'sma_50', header: 'SMA 50', accessor: (r) => r.sma_50, sortable: true, sortType: 'number', isNumeric: true, hidden: isColHidden('sma_50'), render: (v) => fmtNum(v) },
      { key: 'sma_100', header: 'SMA 100', accessor: (r) => r.sma_100, sortable: true, sortType: 'number', isNumeric: true, hidden: isColHidden('sma_100'), render: (v) => fmtNum(v) },
      { key: 'sma_150', header: 'SMA 150', accessor: (r) => r.sma_150, sortable: true, sortType: 'number', isNumeric: true, hidden: isColHidden('sma_150'), render: (v) => fmtNum(v) },
      { key: 'sma_200', header: 'SMA 200', accessor: (r) => r.sma_200, sortable: true, sortType: 'number', isNumeric: true, hidden: isColHidden('sma_200'), render: (v) => fmtNum(v) },
      { key: 'ema_10', header: 'EMA 10', accessor: (r) => r.ema_10, sortable: true, sortType: 'number', isNumeric: true, hidden: isColHidden('ema_10'), render: (v) => fmtNum(v) },
      { key: 'ema_8', header: 'EMA 8', accessor: (r) => r.ema_8, sortable: true, sortType: 'number', isNumeric: true, hidden: isColHidden('ema_8'), render: (v) => fmtNum(v) },
      { key: 'ema_21', header: 'EMA 21', accessor: (r) => r.ema_21, sortable: true, sortType: 'number', isNumeric: true, hidden: isColHidden('ema_21'), render: (v) => fmtNum(v) },
      { key: 'ema_10_dist_pct', header: 'EMA10 Dist %', accessor: (r) => ema10DistPct(r), sortable: true, sortType: 'number', isNumeric: true, hidden: isColHidden('ema_10_dist_pct'), render: (v) => fmtPct(v) },
      { key: 'atr_14', header: 'ATR 14', accessor: (r) => r.atr_14, sortable: true, sortType: 'number', isNumeric: true, hidden: isColHidden('atr_14'), render: (v) => fmtNum(v) },
      { key: 'atr_30', header: 'ATR 30', accessor: (r) => r.atr_30, sortable: true, sortType: 'number', isNumeric: true, hidden: isColHidden('atr_30'), render: (v) => fmtNum(v) },
      { key: 'atrp_14', header: 'ATR% 14', accessor: (r) => r.atrp_14, sortable: true, sortType: 'number', isNumeric: true, hidden: isColHidden('atrp_14'), render: (v) => fmtPct(v) },
      { key: 'atrp_30', header: 'ATR% 30', accessor: (r) => r.atrp_30, sortable: true, sortType: 'number', isNumeric: true, hidden: isColHidden('atrp_30'), render: (v) => fmtPct(v) },
      { key: 'atrx_sma_21', header: '(P−SMA21)/ATR', accessor: (r) => r.atrx_sma_21, sortable: true, sortType: 'number', isNumeric: true, hidden: isColHidden('atrx_sma_21'), render: (v) => fmtX(v) },
      { key: 'atrx_sma_50', header: '(P−SMA50)/ATR', accessor: (r) => r.atrx_sma_50, sortable: true, sortType: 'number', isNumeric: true, hidden: isColHidden('atrx_sma_50'), render: (v) => fmtX(v) },
      { key: 'atrx_sma_100', header: '(P−SMA100)/ATR', accessor: (r) => r.atrx_sma_100, sortable: true, sortType: 'number', isNumeric: true, hidden: isColHidden('atrx_sma_100'), render: (v) => fmtX(v) },
      { key: 'atrx_sma_150', header: '(P−SMA150)/ATR', accessor: (r) => r.atrx_sma_150, sortable: true, sortType: 'number', isNumeric: true, hidden: isColHidden('atrx_sma_150'), render: (v) => fmtX(v) },
      { key: 'sector', header: 'Sector', accessor: (r) => r.sector, sortable: true, sortType: 'string', hidden: isColHidden('sector') },
      { key: 'industry', header: 'Industry', accessor: (r) => r.industry, sortable: true, sortType: 'string', hidden: isColHidden('industry') },
      {
        key: 'scan_tier', header: 'Scan Tier', accessor: (r) => r.scan_tier, sortable: true, sortType: 'string',
        hidden: isColHidden('scan_tier'),
        render: (v) => v ? <Badge variant="secondary" className="font-normal">{String(v)}</Badge> : <span className="text-muted-foreground">—</span>,
      },
      {
        key: 'action_label', header: 'Action', accessor: (r) => r.action_label, sortable: true, sortType: 'string',
        hidden: isColHidden('action_label'),
        filterType: 'select',
        filterOptions: ALL_ACTIONS.map((a) => ({ label: a, value: a })),
        render: (v) => {
          if (!v) return <span className="text-muted-foreground">—</span>;
          const palette = ACTION_COLORS[String(v)] ?? 'gray';
          const cls = ACTION_PILL_SUBTLE[palette] ?? ACTION_PILL_SUBTLE.gray;
          return <Badge variant="outline" className={cn('font-normal', cls)}>{String(v)}</Badge>;
        },
      },
      { key: 'as_of_timestamp', header: 'As of', accessor: (r) => r.as_of_timestamp || r.analysis_timestamp, sortable: true, sortType: 'date', hidden: isColHidden('as_of_timestamp'), render: (v) => fmtTs(v) },
      {
        key: 'portfolio_qty', header: 'Qty',
        accessor: (r) => portfolioSymbols[r.symbol]?.quantity ?? 0,
        sortable: true, sortType: 'number', isNumeric: true, width: '60px',
        hidden: isColHidden('portfolio_qty'),
        render: (v) => {
          const qty = Number(v);
          return qty > 0 ? <span className="font-mono text-xs">{qty}</span> : <span className="text-xs text-muted-foreground">—</span>;
        },
      },
      {
        key: 'portfolio_pnl', header: 'Unrealized',
        accessor: (r) => portfolioSymbols[r.symbol]?.unrealized_pnl ?? 0,
        sortable: true, sortType: 'number', isNumeric: true, width: '80px',
        hidden: isColHidden('portfolio_pnl'),
        render: (v) => {
          const val = Number(v);
          if (!val) return <span className="text-xs text-muted-foreground">—</span>;
          return <PnlText value={val} format="currency" />;
        },
      },
      {
        key: 'actions', header: '', accessor: () => '', sortable: false, width: '70px',
        hidden: false,
        render: (_v: any, r: any) => {
          const sym = String(r?.symbol || '');
          const price = typeof r?.current_price === 'number' ? r.current_price : 0;
          const posData = portfolioSymbols[sym];
          const sharesHeld = posData?.quantity ?? 0;
          const avgCost = posData && posData.quantity > 0 ? posData.cost_basis / posData.quantity : undefined;
          return (
            <Button
              type="button" size="xs" variant="outline" className="h-6 text-xs"
              onClick={(e: React.MouseEvent) => {
                e.stopPropagation();
                setTradeTarget({ symbol: sym, currentPrice: price, sharesHeld, averageCost: avgCost });
              }}
            >
              Trade
            </Button>
          );
        },
      },
    ];
  }, [currency, timezone, canEditPlan, updateTrackedPlan, portfolioSymbols, isColHidden, mode, ivCoverageMap, ivCoverageQuery.isPending]);

  /* ─── Client-side row filtering ─── */

  const tableRows = React.useMemo(() => {
    let d = rows;
    if (showEtfOnly) {
      d = d.filter((row) => ETF_SYMBOL_SET.has(String(row?.symbol || '').toUpperCase()));
    }
    if (showHoldings) {
      d = d.filter((row) => String(row?.symbol || '') in portfolioSymbols);
    }
    return d;
  }, [rows, showEtfOnly, showHoldings, portfolioSymbols]);

  /* ─── Aggregate lookups for metric strip ─── */

  const stageCountMap = React.useMemo(() => {
    const map = new Map<string, number>();
    for (const entry of aggregates?.stage_distribution ?? []) {
      map.set(entry.stage, entry.count);
    }
    return map;
  }, [aggregates]);

  const actionCountMap = React.useMemo(() => {
    const map = new Map<string, number>();
    for (const entry of aggregates?.action_distribution ?? []) {
      map.set(entry.action, entry.count);
    }
    return map;
  }, [aggregates]);

  const hasMetricFilters = !!filterStage || !!metricActionFilter;

  /* ─── Render ─── */

  return (
    <ChartContext.Provider value={openChart}>
      <PortfolioSymbolsContext.Provider value={portfolioSymbols}>
        <Page fullWidth>
          <PageHeader
            title="Market Tracked"
            subtitle="Tracked symbols with technical indicators. Use presets or filters to find setups."
            actions={
              <p className="text-xs text-muted-foreground">
                Indicators are computed from daily OHLCV and the SPY benchmark. Sector/industry come from fundamentals.
              </p>
            }
          />

          {/* ── Preset pill bar ── */}
          <div className="flex flex-wrap items-center gap-x-5 gap-y-2 px-1 pb-3">
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="mr-0.5 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Action</span>
              {ACTION_PRESETS.map((p) => (
                <Badge
                  key={p.key}
                  variant={activePreset?.key === p.key ? 'default' : 'outline'}
                  className="cursor-pointer select-none transition-colors"
                  role="button"
                  aria-pressed={activePreset?.key === p.key}
                  onClick={() => handlePresetClick({ type: 'action_labels', key: p.key, paramValue: p.paramValue })}
                >
                  {p.label}
                </Badge>
              ))}
            </div>

            <div className="flex flex-wrap items-center gap-1.5">
              <span className="mr-0.5 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Tier</span>
              {SCAN_TIER_PRESETS.map((p) => (
                <Badge
                  key={p.key}
                  variant={activePreset?.key === p.key ? 'default' : 'outline'}
                  className="cursor-pointer select-none transition-colors"
                  role="button"
                  aria-pressed={activePreset?.key === p.key}
                  onClick={() => handlePresetClick({ type: 'scan_tiers', key: p.key, paramValue: p.paramValue })}
                >
                  {p.label}
                </Badge>
              ))}
            </div>

            {mode === 'track' && (
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="mr-0.5 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Lens</span>
                {TRADING_LENS_PRESETS.map((p) => (
                  <Badge
                    key={p.key}
                    variant={activePreset?.key === p.key ? 'default' : 'outline'}
                    className="cursor-pointer select-none transition-colors"
                    role="button"
                    aria-pressed={activePreset?.key === p.key}
                    onClick={() => handlePresetClick({ type: 'preset', key: p.key, paramValue: p.paramValue })}
                  >
                    {p.label}
                  </Badge>
                ))}
              </div>
            )}
          </div>

          {/* ── Index scope + Column profile ── */}
          <div className="flex flex-wrap items-center gap-x-6 gap-y-2 px-1 pb-3">
            <div className="flex flex-wrap items-center gap-1">
              {INDEX_SCOPE_OPTIONS.map((s) => (
                <Badge
                  key={s.key}
                  variant={indexScope === s.key ? 'default' : 'outline'}
                  className="cursor-pointer select-none transition-colors"
                  role="button"
                  aria-pressed={indexScope === s.key}
                  onClick={() => { setIndexScope(s.key); setPage(1); }}
                >
                  {s.label}
                </Badge>
              ))}
            </div>

            <div className="h-5 w-px bg-border" aria-hidden />

            <div className="flex flex-wrap items-center gap-1">
              {COLUMN_PROFILE_OPTIONS.map((p) => (
                <Badge
                  key={p.key}
                  variant={columnProfile === p.key ? 'default' : 'outline'}
                  className="cursor-pointer select-none transition-colors"
                  role="button"
                  aria-pressed={columnProfile === p.key}
                  onClick={() => setColumnProfile(p.key)}
                >
                  {p.label}
                </Badge>
              ))}
            </div>
          </div>

          {/* ── Metric strip ── */}
          <div className="mb-3 rounded-lg border border-border bg-card/60 px-3 py-2">
            <div className="flex w-full items-center gap-2 text-left">
              <button
                type="button"
                className="flex min-w-0 flex-1 items-center gap-2 text-left"
                onClick={toggleMetricStrip}
                aria-expanded={!metricStripCollapsed}
                aria-controls="metric-strip-content"
              >
                <ChevronDown
                  className={cn('size-4 text-muted-foreground transition-transform', metricStripCollapsed && '-rotate-90')}
                  aria-hidden
                />
                <span
                  className="text-xs font-medium text-muted-foreground"
                  aria-live="polite"
                  aria-busy={aggregatesQuery.isLoading}
                >
                  {aggregatesCountLabel} symbols
                </span>
              </button>
              {aggregatesQuery.isError && (
                <button
                  type="button"
                  onClick={() => aggregatesQuery.refetch()}
                  className="shrink-0 text-[10px] text-muted-foreground underline underline-offset-2 hover:text-foreground"
                  aria-label="Retry aggregate count"
                >
                  retry
                </button>
              )}
              {hasMetricFilters && (
                <Button
                  type="button" size="xs" variant="ghost"
                  className="ml-auto h-5 shrink-0 px-2 text-[11px]"
                  onClick={() => clearMetricFilters()}
                >
                  Clear
                </Button>
              )}
            </div>

            {!metricStripCollapsed && (
              <div id="metric-strip-content" className="mt-2 space-y-2">
                {/* Stage row */}
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="mr-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">Stage</span>
                  {ALL_STAGES.map((stage) => {
                    const count = stageCountMap.get(stage) ?? 0;
                    const isActive = filterStage === stage;
                    const palette = STAGE_COLORS[stage] ?? 'gray';
                    const cls = isActive
                      ? (STAGE_SOLID_BADGE[palette] ?? STAGE_SOLID_BADGE.gray)
                      : (STAGE_SUBTLE_BADGE[palette] ?? STAGE_SUBTLE_BADGE.gray);
                    return (
                      <Badge
                        key={stage}
                        variant="outline"
                        className={cn('cursor-pointer select-none tabular-nums transition-colors', cls)}
                        role="button"
                        aria-pressed={isActive}
                        onClick={() => handleStageClick(stage)}
                      >
                        {stage} <span className="ml-0.5 opacity-70">{count}</span>
                      </Badge>
                    );
                  })}
                </div>

                {/* Action row */}
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="mr-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">Action</span>
                  {ALL_ACTIONS.map((action) => {
                    const count = actionCountMap.get(action) ?? 0;
                    const isActive = metricActionFilter === action;
                    const palette = ACTION_COLORS[action] ?? 'gray';
                    const cls = isActive
                      ? (ACTION_PILL_SOLID[palette] ?? ACTION_PILL_SOLID.gray)
                      : (ACTION_PILL_SUBTLE[palette] ?? ACTION_PILL_SUBTLE.gray);
                    return (
                      <Badge
                        key={action}
                        variant="outline"
                        className={cn('cursor-pointer select-none tabular-nums transition-colors', cls)}
                        role="button"
                        aria-pressed={isActive}
                        onClick={() => handleActionClick(action)}
                      >
                        {action} <span className="ml-0.5 opacity-70">{count}</span>
                      </Badge>
                    );
                  })}
                </div>
              </div>
            )}
          </div>

          {/* ── Table ── */}
          <div className="w-full overflow-hidden rounded-xl border border-border bg-card shadow-xs ring-1 ring-foreground/10">
            <SortableTable
              key={locationSearch || 'tracked-default'}
              data={tableRows}
              columns={columns}
              defaultSortBy={sortBy}
              defaultSortOrder={sortDir}
              size={compact ? 'sm' : 'md'}
              rowClassName={cn('even:bg-muted/30', compact ? 'py-1 text-xs' : 'py-2 text-sm')}
              maxHeight="70vh"
              filtersEnabled
              emptyMessage={
                loading
                  ? 'Loading…'
                  : 'Your watchlist is a clean slate — add a symbol when something deserves a seat.'
              }
              serverSorted
              onSortChange={handleSortChange}
              serverTotal={total}
              endToolbar={
                <Button
                  type="button" size="xs"
                  variant={compact ? 'default' : 'outline'}
                  aria-pressed={compact}
                  aria-label={compact ? 'Switch to comfortable table density' : 'Switch to compact table density'}
                  onClick={() => setCompact((v) => !v)}
                >
                  Compact
                </Button>
              }
            />
          </div>

          {total > 0 && (
            <div className="mt-3">
              <Pagination
                page={page}
                pageSize={pageSize}
                total={total}
                pageSizeOptions={[50, 100, 200]}
                onPageChange={setPage}
                onPageSizeChange={handlePageSizeChange}
              />
            </div>
          )}
        </Page>
        <ChartSlidePanel symbol={chartSymbol} onClose={() => setChartSymbol(null)} />
        {tradeTarget && (
          <TradeModal
            isOpen={!!tradeTarget}
            symbol={tradeTarget.symbol}
            currentPrice={tradeTarget.currentPrice}
            sharesHeld={tradeTarget.sharesHeld}
            averageCost={tradeTarget.averageCost}
            onClose={() => setTradeTarget(null)}
          />
        )}
      </PortfolioSymbolsContext.Provider>
    </ChartContext.Provider>
  );
};

export default MarketTrackedClient;
