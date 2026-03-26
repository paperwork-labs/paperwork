import React from 'react';
import toast from 'react-hot-toast';
import { useLocation } from 'react-router-dom';
import { Check, Edit2, X } from 'lucide-react';

import SortableTable, { type Column, type FilterGroup } from '../components/SortableTable';
import { ChartContext, SymbolLink, ChartSlidePanel, PortfolioSymbolsContext } from '../components/market/SymbolChartUI';
import TradeModal from '../components/orders/TradeModal';
import StageBadge from '../components/shared/StageBadge';
import PnlText from '../components/shared/PnlText';
import { useAuth } from '../context/AuthContext';
import { ETF_SYMBOL_SET } from '../constants/etf';
import { usePortfolioSymbols } from '../hooks/usePortfolioSymbols';
import { useUserPreferences } from '../hooks/useUserPreferences';
import api from '../services/api';
import { formatDateTime, formatMoney } from '../utils/format';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Page, PageHeader } from '@/components/ui/Page';
import { cn } from '@/lib/utils';
import { semanticTextColorClass } from '@/lib/semantic-text-color';

type TradeTarget = { symbol: string; currentPrice: number; sharesHeld: number; averageCost?: number } | null;

type EditablePriceCellProps = {
  symbol: string;
  value: number | null | undefined;
  canEdit: boolean;
  onSave: (symbol: string, nextValue: number | null) => Promise<void>;
};

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

const MarketTracked: React.FC = () => {
  const location = useLocation();
  const { timezone, currency } = useUserPreferences();
  const { user } = useAuth();
  const canEditPlan = user?.role === 'admin' || user?.role === 'analyst';
  const [rows, setRows] = React.useState<any[]>([]);
  const [trackedCount, setTrackedCount] = React.useState<number>(0);
  const [loading, setLoading] = React.useState<boolean>(false);
  const [chartSymbol, setChartSymbol] = React.useState<string | null>(null);
  const openChart = React.useCallback((sym: string) => setChartSymbol(sym), []);
  const [showHoldings, setShowHoldings] = React.useState(false);
  const [tradeTarget, setTradeTarget] = React.useState<TradeTarget>(null);
  const portfolioQuery = usePortfolioSymbols();
  const portfolioSymbols = portfolioQuery.data ?? {};

  const load = async () => {
    if (loading) return;
    setLoading(true);
    try {
      const r = await api.get('/market-data/snapshots?limit=5000');
      const data = (r as any)?.data;
      const out = data?.rows;
      setRows(Array.isArray(out) ? out : []);
      setTrackedCount(typeof data?.tracked_count === 'number' ? data.tracked_count : 0);
    } catch (err: any) {
      toast.error(err?.message || 'Failed to load tracked snapshot table');
      setRows([]);
    } finally {
      setLoading(false);
    }
  };
  React.useEffect(() => { void load(); }, []);

  const updateTrackedPlan = React.useCallback(async (
    symbol: string,
    patch: { entry_price?: number | null; exit_price?: number | null }
  ) => {
    try {
      await api.patch(`/market-data/tracked-plan/${encodeURIComponent(symbol)}`, patch);
      setRows((prev) =>
        prev.map((row) => {
          if (String(row?.symbol || '').toUpperCase() !== symbol.toUpperCase()) return row;
          return { ...row, ...patch };
        })
      );
    } catch (err: any) {
      toast.error(err?.message || 'Failed to update tracked plan');
      throw err;
    }
  }, []);

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
    const fmtDays = (v: any) =>
      typeof v === 'number' && Number.isFinite(v) ? `${Math.max(0, Math.round(v))}d` : '—';

    return [
      { key: 'symbol', header: 'Symbol', accessor: (r) => r.symbol, sortable: true, sortType: 'string', render: (_v, r) => (
        <div className="flex items-center gap-1">
          <SymbolLink symbol={String(r?.symbol || '')} />
          {String(r?.symbol || '') in portfolioSymbols && (
            <Badge variant="secondary" className="h-4 px-1.5 text-[10px] font-medium">
              Held
            </Badge>
          )}
        </div>
      ) },
      { key: 'name', header: 'Name', accessor: (r) => r.name, sortable: true, sortType: 'string', render: (v) => String(v || '—') },
      { key: 'current_price', header: 'Price', accessor: (r) => r.current_price, sortable: true, sortType: 'number', isNumeric: true, render: (v) => (typeof v === 'number' ? formatMoney(v, currency, { maximumFractionDigits: 2 }) : '—') },
      {
        key: 'entry_price',
        header: 'Entry',
        accessor: (r) => r.entry_price,
        sortable: true,
        sortType: 'number',
        isNumeric: true,
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
        key: 'exit_price',
        header: 'Exit',
        accessor: (r) => r.exit_price,
        sortable: true,
        sortType: 'number',
        isNumeric: true,
        render: (v, r) => (
          <EditablePriceCell
            symbol={String(r?.symbol || '')}
            value={typeof v === 'number' ? v : null}
            canEdit={canEditPlan}
            onSave={(symbol, nextValue) => updateTrackedPlan(symbol, { exit_price: nextValue })}
          />
        ),
      },
      { key: 'market_cap', header: 'Mkt Cap', accessor: (r) => r.market_cap, sortable: true, sortType: 'number', isNumeric: true, render: (v) => (typeof v === 'number' ? Intl.NumberFormat('en', { notation: 'compact' }).format(v) : '—') },
      { key: 'perf_1d', header: 'Change %', accessor: (r) => r.perf_1d, sortable: true, sortType: 'number', isNumeric: true, render: (v) => fmtPct(v) },
      { key: 'perf_5d', header: 'Perf 1W', accessor: (r) => r.perf_5d, sortable: true, sortType: 'number', isNumeric: true, render: (v) => fmtPct(v) },
      { key: 'perf_20d', header: 'Perf 1M', accessor: (r) => r.perf_20d, sortable: true, sortType: 'number', isNumeric: true, render: (v) => fmtPct(v) },
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
        render: (v, r) => {
          const cur = stageScore(v);
          const prev = stageScore(r.previous_stage_label);
          const changed = prev != null && cur != null && cur !== prev;
          return (
            <div className="flex items-center gap-1">
              <StageBadge stage={v || '?'} />
              {changed && (
                <span className={cn('text-xs', semanticTextColorClass(cur! > prev! ? 'green.400' : 'red.400'))}>
                  {cur! > prev! ? '▲' : '▼'}
                </span>
              )}
            </div>
          );
        },
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
        render: (v) => (
          <Badge variant="secondary" className="font-normal">
            {String(v || 'UNKNOWN')}
          </Badge>
        ),
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
      { key: 'pe_ttm', header: 'P/E', accessor: (r) => r.pe_ttm, sortable: true, sortType: 'number', isNumeric: true, render: (v) => fmtNum(v) },
      { key: 'roe', header: 'ROE %', accessor: (r) => r.roe, sortable: true, sortType: 'number', isNumeric: true, render: (v) => fmtPct(v) },
      { key: 'eps_growth_yoy', header: 'EPS YoY %', accessor: (r) => r.eps_growth_yoy, sortable: true, sortType: 'number', isNumeric: true, render: (v) => fmtPct(v) },
      { key: 'revenue_growth_yoy', header: 'Rev YoY %', accessor: (r) => r.revenue_growth_yoy, sortable: true, sortType: 'number', isNumeric: true, render: (v) => fmtPct(v) },
      { key: 'dividend_yield', header: 'Div Yield %', accessor: (r) => r.dividend_yield, sortable: true, sortType: 'number', isNumeric: true, render: (v) => fmtPct(v) },
      { key: 'beta', header: 'Beta', accessor: (r) => r.beta, sortable: true, sortType: 'number', isNumeric: true, render: (v) => fmtNum(v) },
      { key: 'rs_mansfield_pct', header: 'RS (Mansfield)', accessor: (r) => r.rs_mansfield_pct, sortable: true, sortType: 'number', isNumeric: true, render: (v) => typeof v === 'number' && Number.isFinite(v) ? (v > 0 ? `+${v.toFixed(1)}` : v.toFixed(1)) : '—' },
      { key: 'range_pos_20d', header: 'Range 20d%', accessor: (r) => r.range_pos_20d, sortable: true, sortType: 'number', isNumeric: true, render: (v) => fmtPct(v) },
      { key: 'range_pos_50d', header: 'Range 50d%', accessor: (r) => r.range_pos_50d, sortable: true, sortType: 'number', isNumeric: true, render: (v) => fmtPct(v) },
      { key: 'range_pos_52w', header: 'Range 52w%', accessor: (r) => r.range_pos_52w, sortable: true, sortType: 'number', isNumeric: true, render: (v) => fmtPct(v) },
      { key: 'sma_5', header: 'SMA 5', accessor: (r) => r.sma_5, sortable: true, sortType: 'number', isNumeric: true, render: (v) => fmtNum(v) },
      { key: 'sma_10', header: 'SMA 10', accessor: (r) => r.sma_10, sortable: true, sortType: 'number', isNumeric: true, render: (v) => fmtNum(v) },
      { key: 'sma_14', header: 'SMA 14', accessor: (r) => r.sma_14, sortable: true, sortType: 'number', isNumeric: true, render: (v) => fmtNum(v) },
      { key: 'sma_21', header: 'SMA 21', accessor: (r) => r.sma_21, sortable: true, sortType: 'number', isNumeric: true, render: (v) => fmtNum(v) },
      { key: 'sma_50', header: 'SMA 50', accessor: (r) => r.sma_50, sortable: true, sortType: 'number', isNumeric: true, render: (v) => fmtNum(v) },
      { key: 'sma_100', header: 'SMA 100', accessor: (r) => r.sma_100, sortable: true, sortType: 'number', isNumeric: true, render: (v) => fmtNum(v) },
      { key: 'sma_150', header: 'SMA 150', accessor: (r) => r.sma_150, sortable: true, sortType: 'number', isNumeric: true, render: (v) => fmtNum(v) },
      { key: 'sma_200', header: 'SMA 200', accessor: (r) => r.sma_200, sortable: true, sortType: 'number', isNumeric: true, render: (v) => fmtNum(v) },
      { key: 'ema_10', header: 'EMA 10', accessor: (r) => r.ema_10, sortable: true, sortType: 'number', isNumeric: true, render: (v) => fmtNum(v) },
      { key: 'ema_8', header: 'EMA 8', accessor: (r) => r.ema_8, sortable: true, sortType: 'number', isNumeric: true, render: (v) => fmtNum(v) },
      { key: 'ema_21', header: 'EMA 21', accessor: (r) => r.ema_21, sortable: true, sortType: 'number', isNumeric: true, render: (v) => fmtNum(v) },
      { key: 'ema_10_dist_pct', header: 'EMA10 Dist %', accessor: (r) => ema10DistPct(r), sortable: true, sortType: 'number', isNumeric: true, render: (v) => fmtPct(v) },
      { key: 'atr_14', header: 'ATR 14', accessor: (r) => r.atr_14, sortable: true, sortType: 'number', isNumeric: true, render: (v) => fmtNum(v) },
      { key: 'atr_30', header: 'ATR 30', accessor: (r) => r.atr_30, sortable: true, sortType: 'number', isNumeric: true, render: (v) => fmtNum(v) },
      { key: 'atrp_14', header: 'ATR% 14', accessor: (r) => r.atrp_14, sortable: true, sortType: 'number', isNumeric: true, render: (v) => fmtPct(v) },
      { key: 'atrp_30', header: 'ATR% 30', accessor: (r) => r.atrp_30, sortable: true, sortType: 'number', isNumeric: true, render: (v) => fmtPct(v) },
      { key: 'atrx_sma_21', header: '(P−SMA21)/ATR', accessor: (r) => r.atrx_sma_21, sortable: true, sortType: 'number', isNumeric: true, render: (v) => fmtX(v) },
      { key: 'atrx_sma_50', header: '(P−SMA50)/ATR', accessor: (r) => r.atrx_sma_50, sortable: true, sortType: 'number', isNumeric: true, render: (v) => fmtX(v) },
      { key: 'atrx_sma_100', header: '(P−SMA100)/ATR', accessor: (r) => r.atrx_sma_100, sortable: true, sortType: 'number', isNumeric: true, render: (v) => fmtX(v) },
      { key: 'atrx_sma_150', header: '(P−SMA150)/ATR', accessor: (r) => r.atrx_sma_150, sortable: true, sortType: 'number', isNumeric: true, render: (v) => fmtX(v) },
      { key: 'sector', header: 'Sector', accessor: (r) => r.sector, sortable: true, sortType: 'string' },
      { key: 'industry', header: 'Industry', accessor: (r) => r.industry, sortable: true, sortType: 'string' },
      { key: 'as_of_timestamp', header: 'As of', accessor: (r) => r.as_of_timestamp || r.analysis_timestamp, sortable: true, sortType: 'date', render: (v) => fmtTs(v) },
      {
        key: 'portfolio_qty',
        header: 'Qty',
        accessor: (r) => portfolioSymbols[r.symbol]?.quantity ?? 0,
        sortable: true,
        sortType: 'number',
        isNumeric: true,
        render: (v) => {
          const qty = Number(v);
          return qty > 0 ? <span className="font-mono text-xs">{qty}</span> : <span className="text-xs text-muted-foreground">—</span>;
        },
        width: '60px',
        hidden: !showHoldings,
      },
      {
        key: 'portfolio_pnl',
        header: 'Unrealized',
        accessor: (r) => portfolioSymbols[r.symbol]?.unrealized_pnl ?? 0,
        sortable: true,
        sortType: 'number',
        isNumeric: true,
        render: (v) => {
          const val = Number(v);
          if (!val) return <span className="text-xs text-muted-foreground">—</span>;
          return <PnlText value={val} format="currency" />;
        },
        width: '80px',
        hidden: !showHoldings,
      },
      {
        key: 'actions',
        header: '',
        accessor: () => '',
        sortable: false,
        width: '70px',
        render: (_v: any, r: any) => {
          const sym = String(r?.symbol || '');
          const price = typeof r?.current_price === 'number' ? r.current_price : 0;
          const posData = portfolioSymbols[sym];
          const sharesHeld = posData?.quantity ?? 0;
          const avgCost = posData && posData.quantity > 0 ? posData.cost_basis / posData.quantity : undefined;
          return (
            <Button
              type="button"
              size="xs"
              variant="outline"
              className="h-6 text-xs"
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
  }, [currency, timezone, canEditPlan, updateTrackedPlan, portfolioSymbols, showHoldings]);

  const filterPresets = React.useMemo<Array<{ label: string; filters: FilterGroup }>>(() => [
    {
      label: 'Momentum Trend (Clean)',
      filters: {
        conjunction: 'AND' as const,
        rules: [
          { id: 'momentum_price_gt_sma50', columnKey: 'current_price', operator: 'gt' as const, valueSource: 'column' as const, valueColumnKey: 'sma_50' },
          { id: 'momentum_price_gt_sma200', columnKey: 'current_price', operator: 'gt' as const, valueSource: 'column' as const, valueColumnKey: 'sma_200' },
          { id: 'momentum_price_gt_ema21', columnKey: 'current_price', operator: 'gt' as const, valueSource: 'column' as const, valueColumnKey: 'ema_21' },
          { id: 'momentum_ema8_gt_ema21', columnKey: 'ema_8', operator: 'gt' as const, valueSource: 'column' as const, valueColumnKey: 'ema_21' },
          { id: 'momentum_sma21_gt_sma50', columnKey: 'sma_21', operator: 'gt' as const, valueSource: 'column' as const, valueColumnKey: 'sma_50' },
          { id: 'momentum_sma50_gt_sma200', columnKey: 'sma_50', operator: 'gt' as const, valueSource: 'column' as const, valueColumnKey: 'sma_200' },
        ],
      },
    },
    {
      label: 'Giants Waking Up (Large Cap Trend)',
      filters: {
        conjunction: 'AND' as const,
        rules: [
          { id: 'giant_mcap_gt_50b', columnKey: 'market_cap', operator: 'gt' as const, valueSource: 'literal' as const, value: '50000000000' },
          { id: 'giant_stage_2x', columnKey: 'stage_label', operator: 'starts_with' as const, valueSource: 'literal' as const, value: '2' },
          { id: 'giant_price_gt_sma200', columnKey: 'current_price', operator: 'gt' as const, valueSource: 'column' as const, valueColumnKey: 'sma_200' },
          { id: 'giant_ema21_gt_sma50', columnKey: 'ema_21', operator: 'gt' as const, valueSource: 'column' as const, valueColumnKey: 'sma_50' },
          { id: 'giant_rs_positive', columnKey: 'rs_mansfield_pct', operator: 'gt' as const, valueSource: 'literal' as const, value: '0' },
        ],
      },
    },
    {
      label: 'Short-Term Squeeze (Range + ATR)',
      filters: {
        conjunction: 'AND' as const,
        rules: [
          { id: 'squeeze_range_20d_gt_80', columnKey: 'range_pos_20d', operator: 'gt' as const, valueSource: 'literal' as const, value: '80' },
          { id: 'squeeze_atrp14_gt_3', columnKey: 'atrp_14', operator: 'gt' as const, valueSource: 'literal' as const, value: '3' },
          { id: 'squeeze_price_gt_ema8', columnKey: 'current_price', operator: 'gt' as const, valueSource: 'column' as const, valueColumnKey: 'ema_8' },
          { id: 'squeeze_ema8_gt_ema21', columnKey: 'ema_8', operator: 'gt' as const, valueSource: 'column' as const, valueColumnKey: 'ema_21' },
        ],
      },
    },
    {
      label: 'Breakout Watch',
      filters: {
        conjunction: 'AND' as const,
        rules: [
          { id: 'bkout_stage_2x', columnKey: 'stage_label', operator: 'starts_with' as const, valueSource: 'literal' as const, value: '2' },
          { id: 'bkout_perf5d_pos', columnKey: 'perf_5d', operator: 'gt' as const, valueSource: 'literal' as const, value: '0' },
          { id: 'bkout_rs_pos', columnKey: 'rs_mansfield_pct', operator: 'gt' as const, valueSource: 'literal' as const, value: '0' },
          { id: 'bkout_price_gt_sma50', columnKey: 'current_price', operator: 'gt' as const, valueSource: 'column' as const, valueColumnKey: 'sma_50' },
        ],
      },
    },
    {
      label: 'Pullback Buy Zone',
      filters: {
        conjunction: 'AND' as const,
        rules: [
          { id: 'pull_stage_2x', columnKey: 'stage_label', operator: 'starts_with' as const, valueSource: 'literal' as const, value: '2' },
          { id: 'pull_perf5d_range', columnKey: 'perf_5d', operator: 'between' as const, valueSource: 'literal' as const, value: '-4', valueTo: '2' },
          { id: 'pull_rs_pos', columnKey: 'rs_mansfield_pct', operator: 'gt' as const, valueSource: 'literal' as const, value: '0' },
          { id: 'pull_price_gt_sma50', columnKey: 'current_price', operator: 'gt' as const, valueSource: 'column' as const, valueColumnKey: 'sma_50' },
        ],
      },
    },
    {
      label: 'RS Leaders',
      filters: {
        conjunction: 'AND' as const,
        rules: [
          { id: 'rsl_rs_gt_3', columnKey: 'rs_mansfield_pct', operator: 'gt' as const, valueSource: 'literal' as const, value: '3' },
          { id: 'rsl_price_gt_sma200', columnKey: 'current_price', operator: 'gt' as const, valueSource: 'column' as const, valueColumnKey: 'sma_200' },
        ],
      },
    },
    {
      label: 'Stage 1 Base Building',
      filters: {
        conjunction: 'AND' as const,
        rules: [
          { id: 'base_stage_1', columnKey: 'stage_label', operator: 'equals' as const, valueSource: 'literal' as const, value: '1' },
          { id: 'base_range52w_lt_30', columnKey: 'range_pos_52w', operator: 'lt' as const, valueSource: 'literal' as const, value: '30' },
        ],
      },
    },
    {
      label: 'Distribution Warning',
      filters: {
        conjunction: 'AND' as const,
        rules: [
          { id: 'dist_stage_3', columnKey: 'stage_label', operator: 'equals' as const, valueSource: 'literal' as const, value: '3' },
          { id: 'dist_rs_neg', columnKey: 'rs_mansfield_pct', operator: 'lt' as const, valueSource: 'literal' as const, value: '0' },
        ],
      },
    },
    {
      label: 'Stage 4 Decline',
      filters: {
        conjunction: 'AND' as const,
        rules: [
          { id: 'decl_stage_4', columnKey: 'stage_label', operator: 'equals' as const, valueSource: 'literal' as const, value: '4' },
          { id: 'decl_price_lt_sma50', columnKey: 'current_price', operator: 'lt' as const, valueSource: 'column' as const, valueColumnKey: 'sma_50' },
          { id: 'decl_price_lt_sma200', columnKey: 'current_price', operator: 'lt' as const, valueSource: 'column' as const, valueColumnKey: 'sma_200' },
        ],
      },
    },
  ], []);

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
    const asset = (params.get('asset') || '').trim();
    if (asset.toLowerCase() === 'etf') return undefined;
    if (preset) {
      const map: Record<string, string> = {
        momentum: 'Momentum Trend (Clean)',
        giants: 'Giants Waking Up (Large Cap Trend)',
        squeeze: 'Short-Term Squeeze (Range + ATR)',
        breakout: 'Breakout Watch',
        pullback: 'Pullback Buy Zone',
        rs_leaders: 'RS Leaders',
        base: 'Stage 1 Base Building',
        distribution: 'Distribution Warning',
        decline: 'Stage 4 Decline',
      };
      const label = map[preset];
      if (label) {
        const selected = filterPresets.find((p) => p.label === label);
        if (selected) return selected.filters;
      }
    }
    return undefined;
  }, [location.search, filterPresets]);

  const etfOnlyDeepLink = React.useMemo(() => {
    const params = new URLSearchParams(location.search || '');
    const asset = (params.get('asset') || '').trim().toLowerCase();
    const preset = (params.get('preset') || '').trim().toLowerCase();
    return asset === 'etf' || preset === 'etf';
  }, [location.search]);

  const [etfOnly, setEtfOnly] = React.useState<boolean>(etfOnlyDeepLink);
  React.useEffect(() => {
    setEtfOnly(etfOnlyDeepLink);
  }, [etfOnlyDeepLink]);

  const tableRows = React.useMemo(() => {
    let d = rows;
    if (etfOnly) {
      d = d.filter((row) => ETF_SYMBOL_SET.has(String(row?.symbol || '').toUpperCase()));
    }
    if (showHoldings) {
      d = d.filter((row) => String(row?.symbol || '') in portfolioSymbols);
    }
    return d;
  }, [rows, etfOnly, showHoldings, portfolioSymbols]);

  return (
    <ChartContext.Provider value={openChart}>
      <PortfolioSymbolsContext.Provider value={portfolioSymbols}>
        <Page>
          <PageHeader
            title="Market Tracked"
            subtitle="Tracked symbols with technical indicators. Use presets or custom filters to find setups."
            rightContent={
              <div className="flex flex-wrap items-end justify-end gap-2">
                <Button
                  type="button"
                  size="xs"
                  variant={showHoldings ? 'default' : 'outline'}
                  onClick={() => setShowHoldings((v) => !v)}
                >
                  My Holdings
                </Button>
                <Button
                  type="button"
                  size="xs"
                  variant={etfOnly ? 'default' : 'outline'}
                  onClick={() => setEtfOnly((prev) => !prev)}
                >
                  ETFs Only
                </Button>
                <Badge variant="secondary" className="h-6 shrink-0">
                  {tableRows.length} rows
                </Badge>
              </div>
            }
            actions={
              <p className="text-xs text-muted-foreground">
                Indicators are computed from daily OHLCV and the SPY benchmark. Sector/industry come from fundamentals.
              </p>
            }
          />

          {!loading && trackedCount > 0 && rows.length < trackedCount ? (
            <div className="mb-2 rounded-md border border-border bg-muted/50 px-3 py-2">
              <p className="text-xs text-muted-foreground">
                Showing {rows.length} of {trackedCount} tracked symbols with computed indicators.
                {rows.length < trackedCount * 0.9 ? ' Run "Recompute Indicators (Market Snapshot)" from Operator Actions to update all tracked symbols.' : ''}
              </p>
            </div>
          ) : null}

          <div className="w-full overflow-hidden rounded-xl border border-border bg-card shadow-xs ring-1 ring-foreground/10">
            <SortableTable
              key={`${location.search || 'tracked-default'}-${etfOnly ? 'etf' : 'all'}`}
              data={tableRows}
              columns={columns}
              defaultSortBy="symbol"
              defaultSortOrder="asc"
              maxHeight="70vh"
              filtersEnabled
              filterPresets={filterPresets}
              initialFilters={deepLinkFilters}
              initialFiltersOpen={!etfOnlyDeepLink}
              emptyMessage={loading ? 'Loading…' : 'No tracked symbols yet.'}
            />
          </div>
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

export default MarketTracked;
