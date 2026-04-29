"use client";

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import dynamic from 'next/dynamic';
import Link from 'next/link';
import { AlertTriangle, Lock, MinusCircle, Pencil, Plus, RefreshCw, Search, Trash2, Unlock } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { semanticTextColorClass } from '@/lib/semantic-text-color';
import axios from 'axios';
import toast from 'react-hot-toast';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { PageHeader } from "@paperwork-labs/ui";
import type { IndicatorToggles, ChartEvent, ChartEventType } from '@/components/charts/SymbolChartWithMarkers';
import { getStoredIndicators, storeIndicators } from '@/components/charts/SymbolChartWithMarkers';
import { buildTradeSegmentsFromActivity } from '@/components/charts/TradeSegments';
import { OliverKellLegend } from '@/components/charts/OliverKellBadges';
import TierGate from '@/components/billing/TierGate';
import api, { marketDataApi, portfolioApi, unwrapResponse } from '@/services/api';
import { usePositions, useActivity, useClosedPositions } from '@/hooks/usePortfolio';
import useEntitlement from '@/hooks/useEntitlement';
import { useRSMansfield } from '@/hooks/useRSMansfield';
import {
  FEATURE_CHART_RS_RIBBON,
  FEATURE_CHART_TRADE_ANNOTATIONS,
  FEATURE_CHART_TRADE_RATIONALE,
} from '@/constants/features';
import type { KellPatternItem, VolumeEventItem } from '@/types/indicators';
import { useAccountContext } from '@/context/AccountContext';
import { useUserPreferences } from '@/hooks/useUserPreferences';
import { useChartColors } from '@/hooks/useChartColors';
import { formatMoney, formatDateFriendly } from '@/utils/format';
import { TableSkeleton } from '@/components/shared/Skeleton';
import { useColorMode } from '@/theme/colorMode';
import type { EnrichedPosition, ActivityRow, LotRow } from '@/types/portfolio';
import type { Order, OrderStatus } from '@/types/orders';
import {
  type WorkspaceSnapshot,
  parseWorkspaceSnapshotFromMarketDataResponse,
} from '@/types/workspaceSnapshot';
import TradeModal from '@/components/orders/TradeModal';

const ORDER_STATUSES_FOR_POLL: OrderStatus[] = ['submitted', 'pending_submit', 'partially_filled'];

function toastAxiosDetail(e: unknown, fallback: string) {
  if (axios.isAxiosError(e) && e.response?.data && typeof e.response.data === 'object' && e.response.data !== null) {
    const raw = (e.response.data as { detail?: unknown }).detail;
    const msg = Array.isArray(raw) ? raw.map(String).join(', ') : typeof raw === 'string' ? raw : undefined;
    if (msg) {
      toast.error(msg);
      return;
    }
  }
  toast.error(fallback);
}

async function fetchWorkspaceOrdersList(symbol: string): Promise<Order[]> {
  const res = await api.get('/portfolio/orders', { params: { symbol, limit: 50 } });
  const body: unknown = res.data;
  if (body == null || typeof body !== 'object') return [];
  if ('data' in body && Array.isArray((body as { data: unknown }).data)) {
    return (body as { data: Order[] }).data;
  }
  if (Array.isArray(body)) return body as Order[];
  return [];
}

const SymbolChartWithMarkers = dynamic(
  () => import('@/components/charts/SymbolChartWithMarkers'),
  { ssr: false },
);
const TradingViewChart = dynamic(
  () => import('@/components/charts/TradingViewChart'),
  { ssr: false },
);
const RSMansfieldRibbon = dynamic(
  () =>
    import('@/components/charts/RSMansfieldRibbon').then((m) => ({
      default: m.RSMansfieldRibbon,
    })),
  { ssr: false },
);

type TradeTarget = { symbol: string; currentPrice: number; sharesHeld: number; averageCost?: number; positionId?: number } | null;

interface LotTotals {
  shares: number;
  cost: number;
  value: number;
}

function useMediaQueryMin768(): boolean {
  const [matches, setMatches] = useState(() =>
    typeof window !== 'undefined' ? window.matchMedia('(min-width: 768px)').matches : true,
  );
  useEffect(() => {
    const mql = window.matchMedia('(min-width: 768px)');
    const handler = () => setMatches(mql.matches);
    mql.addEventListener('change', handler);
    handler();
    return () => mql.removeEventListener('change', handler);
  }, []);
  return matches;
}

function classifyActivity(r: ActivityRow): ChartEventType {
  const cat = (r.category || '').toUpperCase();
  const side = (r.side || '').toUpperCase();
  const src = (r.src || '').toUpperCase();

  if (cat === 'TRADE' && (side.includes('BUY') || side.includes('BOT'))) return 'BUY';
  if (cat === 'TRADE' && (side.includes('SELL') || side.includes('SLD'))) return 'SELL';
  if (cat.includes('BUY') || side.includes('BUY') || side.includes('BOT')) return 'BUY';
  if (cat.includes('SELL') || side.includes('SELL') || side.includes('SLD')) return 'SELL';
  if (cat.includes('DIV') || cat.includes('PAYMENT_IN_LIEU') || src.includes('DIV')) return 'DIVIDEND';
  if (cat.includes('TRANSFER') || cat.includes('DEPOSIT') || cat.includes('WITHDRAWAL')) return 'TRANSFER';
  if (cat.includes('COMMISSION') || cat.includes('FEE')) return 'FEE';
  if (cat.includes('INTEREST')) return 'INTEREST';
  return 'OTHER';
}

function shortLabel(r: ActivityRow, evType: ChartEventType, currency: string): string {
  const qty = Number(r.quantity || 0);
  const price = Number(r.price || 0);
  const amt = Number(r.amount || r.net_amount || 0);

  switch (evType) {
    case 'BUY':
      return `B ${qty ? qty : ''} @${price ? price.toFixed(0) : '?'}`.trim();
    case 'SELL':
      return `S ${qty ? qty : ''} @${price ? price.toFixed(0) : '?'}`.trim();
    case 'DIVIDEND':
      return amt ? formatMoney(amt, currency) : 'Div';
    case 'TRANSFER':
      return amt >= 0 ? `+${formatMoney(Math.abs(amt), currency, { maximumFractionDigits: 0 })}` : `-${formatMoney(Math.abs(amt), currency, { maximumFractionDigits: 0 })}`;
    case 'FEE':
      return `-${formatMoney(Math.abs(amt || Number(r.commission || 0)), currency)}`;
    case 'INTEREST':
      return amt >= 0 ? `+${formatMoney(Math.abs(amt), currency)}` : `-${formatMoney(Math.abs(amt), currency)}`;
    default:
      return (r.category || 'Event').slice(0, 12);
  }
}

const EVENT_TOGGLE_CONFIG: { type: ChartEventType; label: string; activeClass: string }[] = [
  { type: 'BUY', label: 'Buys', activeClass: 'border-emerald-600/40 bg-emerald-600/15 text-emerald-900 dark:text-emerald-200' },
  { type: 'SELL', label: 'Sells', activeClass: 'border-red-600/40 bg-red-600/15 text-red-900 dark:text-red-200' },
  { type: 'DIVIDEND', label: 'Divs', activeClass: 'border-teal-600/40 bg-teal-600/15 text-teal-900 dark:text-teal-200' },
  { type: 'ORDER_PENDING', label: 'Orders', activeClass: 'border-amber-500/40 bg-amber-500/15 text-amber-950 dark:text-amber-200' },
];

const PortfolioWorkspaceClient: React.FC = () => {
  const { selected } = useAccountContext();
  const { currency, timezone } = useUserPreferences();
  const queryClient = useQueryClient();
  const chartColors = useChartColors();
  const { colorMode } = useColorMode();
  const isDark = colorMode === 'dark';
  const accountId = selected === 'all' || selected === 'taxable' || selected === 'ira' ? undefined : selected;

  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [tradeTarget, setTradeTarget] = useState<TradeTarget>(null);
  const [enabledEvents, setEnabledEvents] = useState<Set<ChartEventType>>(new Set(['BUY', 'SELL', 'DIVIDEND']));
  const [hoverDaySec, setHoverDaySec] = useState<number | null>(null);
  const [lockedDaySec, setLockedDaySec] = useState<number | null>(null);
  const focusedDaySec = lockedDaySec ?? hoverDaySec;
  const [showLine, setShowLine] = useState(true);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [period, setPeriod] = useState<'6mo' | '1y' | '3y' | '5y' | 'max'>('1y');
  const [zoomYears, setZoomYears] = useState<number | 'all'>(1);
  const [indicators, setIndicators] = useState<IndicatorToggles>(getStoredIndicators);
  const toggleIndicator = (key: keyof IndicatorToggles) => {
    setIndicators(prev => {
      const next = { ...prev, [key]: !prev[key] };
      storeIndicators(next);
      return next;
    });
  };
  const toggleEventType = useCallback((type: ChartEventType) => {
    setEnabledEvents(prev => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type); else next.add(type);
      return next;
    });
  }, []);

  const handleHoverDay = useCallback((v: number | null) => setHoverDaySec(v), []);
  const handleClickDay = useCallback((t: number | null) => setLockedDaySec((prev: number | null) => (prev === t ? null : t || null)), []);

  const isMdOrLarger = useMediaQueryMin768();
  const chartHeight = isMdOrLarger ? 520 : 300;
  const [holdingsTab, setHoldingsTab] = useState<'open' | 'closed'>('open');
  const [lotEditMode, setLotEditMode] = useState(false);
  const [editingLotId, setEditingLotId] = useState<number | null>(null);
  const emptyLotForm = { date: '', qty: '', costPerShare: '' };
  const [lotForm, setLotForm] = useState(emptyLotForm);
  const [lotSaving, setLotSaving] = useState(false);

  const positionsQuery = usePositions(accountId);
  const holdings = (positionsQuery.data ?? []) as EnrichedPosition[];

  const closedQuery = useClosedPositions(accountId);
  const closedPositions = (closedQuery.data ?? []) as { symbol: string; total_realized_pnl: number; total_shares_sold: number; last_trade_date: string | null; trade_count: number }[];

  useEffect(() => {
    if (!selectedSymbol && holdings.length > 0) {
      setSelectedSymbol(holdings[0].symbol);
    }
  }, [holdings, selectedSymbol]);

  const activityQuery = useActivity({ accountId, symbol: selectedSymbol ?? undefined, limit: 500 });
  const activityRows = useMemo(() => {
    const raw = activityQuery.data as { data?: { activity?: unknown[] }; activity?: unknown[] } | undefined;
    return (raw?.data?.activity ?? raw?.activity ?? []) as ActivityRow[];
  }, [activityQuery.data]);

  const barsQuery = useQuery({
    queryKey: ['workspaceBars', selectedSymbol, period],
    queryFn: async () => {
      if (!selectedSymbol) return [];
      const res = await marketDataApi.getHistory(selectedSymbol, period, '1d');
      return unwrapResponse<{ time: string; open: number; high: number; low: number; close: number; volume?: number }>(res, 'bars');
    },
    enabled: !!selectedSymbol,
    staleTime: 300000,
  });
  const bars = barsQuery.data ?? [];
  const barsError = barsQuery.isError || (barsQuery.isSuccess && bars.length === 0);

  const snapshotQuery = useQuery<WorkspaceSnapshot | null>({
    queryKey: ['workspaceSnapshot', selectedSymbol],
    queryFn: async (): Promise<WorkspaceSnapshot | null> => {
      if (!selectedSymbol) return null;
      const res: unknown = await marketDataApi.getSnapshot(selectedSymbol);
      return parseWorkspaceSnapshotFromMarketDataResponse(res);
    },
    enabled: !!selectedSymbol,
    staleTime: 600000,
  });
  const snapshot: WorkspaceSnapshot | null = snapshotQuery.data ?? null;

  const selectedHolding = holdings.find(h => h.symbol === selectedSymbol);
  const lotsQuery = useQuery({
    queryKey: ['workspaceTaxLots', selectedHolding?.id],
    queryFn: async () => {
      if (!selectedHolding?.id) return [];
      const res = await portfolioApi.getHoldingTaxLots(selectedHolding.id);
      return unwrapResponse<LotRow>(res, 'tax_lots');
    },
    enabled: !!selectedHolding?.id,
    staleTime: 60000,
  });
  const lots = lotsQuery.data ?? [];

  const ordersQuery = useQuery<Order[]>({
    queryKey: ['workspaceOrders', selectedSymbol],
    queryFn: async (): Promise<Order[]> => {
      if (!selectedSymbol) return [];
      return fetchWorkspaceOrdersList(selectedSymbol);
    },
    enabled: !!selectedSymbol,
    staleTime: 15000,
    refetchInterval: (query) => {
      const data = query.state.data;
      const active =
        (data ?? []).some((o) => ORDER_STATUSES_FOR_POLL.includes(o.status));
      return active ? 5000 : false;
    },
  });
  const orders: Order[] = ordersQuery.data ?? [];

  const filteredHoldings = useMemo(() => {
    const q = search.trim().toLowerCase();
    const list = holdings.slice().sort((a: EnrichedPosition, b: EnrichedPosition) => (b.market_value ?? 0) - (a.market_value ?? 0));
    if (!q) return list;
    return list.filter((h: EnrichedPosition) => h.symbol.toLowerCase().includes(q));
  }, [holdings, search]);

  useEffect(() => {
    if (!lockedDaySec) return;
    const day = new Date(lockedDaySec * 1000).toISOString().slice(0, 10);
    let el = document.querySelector<HTMLElement>(`[id^="lot-${day}"]`);
    if (!el) el = document.querySelector<HTMLElement>(`[id^="div-${day}"]`);
    if (el) el.scrollIntoView({ block: 'center', behavior: 'smooth' });
  }, [lockedDaySec]);

  useEffect(() => {
    if (!selectedSymbol) return;
    const el = document.getElementById(`ticker-${selectedSymbol}`);
    if (el) el.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }, [selectedSymbol]);

  // All activity for the selected symbol -- no truncation
  const symbolActivity = useMemo((): ActivityRow[] => {
    if (!selectedSymbol) return [];
    return activityRows
      .filter((r: ActivityRow) => (r.symbol || '').toUpperCase() === selectedSymbol.toUpperCase())
      .sort((a: ActivityRow, b: ActivityRow) => (b.ts || '').localeCompare(a.ts || ''));
  }, [activityRows, selectedSymbol]);

  // Dividends subset for the panel
  const symbolDividends = useMemo((): ActivityRow[] => {
    return symbolActivity.filter((r: ActivityRow) => classifyActivity(r) === 'DIVIDEND');
  }, [symbolActivity]);

  // Build unified events array from activity + tax lots
  const chartEvents = useMemo((): ChartEvent[] => {
    const findClosest = (iso: string) => {
      if (!bars?.length) return 0;
      const target = new Date(iso).getTime();
      let best = bars[0];
      let diff = Math.abs(new Date(bars[0].time).getTime() - target);
      for (const b of bars) {
        const d = Math.abs(new Date(b.time).getTime() - target);
        if (d < diff) { best = b; diff = d; }
      }
      return Number(best?.close || 0);
    };

    const eventsFromActivity: ChartEvent[] = symbolActivity.map((r: ActivityRow) => {
      const evType = classifyActivity(r);
      const price = Number(r.price || 0) || findClosest(r.ts || '');
      return {
        time: r.ts || '',
        price,
        type: evType,
        label: shortLabel(r, evType, currency),
        amount: Number(r.amount || r.net_amount || 0),
      };
    });

    const activityBuyDates = new Set(
      eventsFromActivity
        .filter(e => e.type === 'BUY')
        .map(e => (e.time || '').slice(0, 10)),
    );
    const eventsFromLots: ChartEvent[] = lots
      .filter((l: LotRow) => !activityBuyDates.has((l.purchase_date || '').slice(0, 10)))
      .map((l: LotRow) => {
        const iso = `${(l.purchase_date || '').slice(0, 10)}T13:30:00Z`;
        const price = Number(l.cost_per_share || 0);
        const qty = Number((l.shares_remaining ?? l.shares) || 0);
        return {
          time: iso,
          price,
          type: 'BUY' as const,
          label: `B ${qty} @${price.toFixed(0)}`,
        };
      });

    const eventsFromOrders: ChartEvent[] = orders
      .filter((o) => o.created_at || o.filled_at || o.submitted_at)
      .map((o) => {
        const status = (o.status || '').toLowerCase();
        let evType: ChartEventType = 'ORDER_PENDING';
        if (status === 'filled') evType = 'ORDER_FILLED';
        else if (status === 'cancelled') evType = 'ORDER_CANCELLED';

        const ts = o.filled_at || o.submitted_at || o.created_at || '';
        const price = Number(o.filled_avg_price || o.limit_price || o.stop_price || 0) || findClosest(ts);
        const side = (o.side || 'sell').charAt(0).toUpperCase();
        const qty = Number(o.quantity || 0);
        const label = `${side}${qty} ${status}`;
        return { time: ts, price, type: evType, label, amount: qty };
      });

    return [...eventsFromActivity, ...eventsFromLots, ...eventsFromOrders];
  }, [symbolActivity, lots, bars, currency, orders]);

  const filteredEvents = useMemo(() => {
    const ORDER_EVENT_TYPES: Set<ChartEventType> = new Set(['ORDER_PENDING', 'ORDER_FILLED', 'ORDER_CANCELLED']);
    const showOrders = enabledEvents.has('ORDER_PENDING');
    return chartEvents.filter(e =>
      enabledEvents.has(e.type) || (showOrders && ORDER_EVENT_TYPES.has(e.type))
    );
  }, [chartEvents, enabledEvents]);

  const priceLinesExtra = useMemo(() => {
    const activeStatuses = new Set<OrderStatus>(ORDER_STATUSES_FOR_POLL);
    return orders
      .filter((o) => activeStatuses.has(o.status))
      .flatMap((o) => {
        const lines: { price: number; color: string; title: string; lineStyle?: number }[] = [];
        if (o.limit_price) {
          lines.push({ price: Number(o.limit_price), color: '#D97706', title: `LIMIT $${Number(o.limit_price).toFixed(2)}`, lineStyle: 2 });
        }
        if (o.stop_price) {
          lines.push({ price: Number(o.stop_price), color: '#DC2626', title: `STOP $${Number(o.stop_price).toFixed(2)}`, lineStyle: 3 });
        }
        return lines;
      });
  }, [orders]);

  const avgPrice = useMemo(() => {
    if (!lots?.length) return undefined;
    const entries = lots
      .map((l: LotRow) => ({ cost: Number(l.cost_per_share || 0), sh: Number((l.shares_remaining ?? l.shares) || 0) }))
      .filter((e: { cost: number; sh: number }) => e.sh > 0 && e.cost > 0);
    const totSh = entries.reduce((s: number, e: { sh: number }) => s + e.sh, 0);
    if (!totSh) return undefined;
    const wavg = entries.reduce((s: number, e: { cost: number; sh: number }) => s + e.cost * e.sh, 0) / totSh;
    return Number.isFinite(wavg) ? wavg : undefined;
  }, [lots]);

  const ent = useEntitlement();
  const canChartAnn = ent.can(FEATURE_CHART_TRADE_ANNOTATIONS);
  const canKellRationale = ent.can(FEATURE_CHART_TRADE_RATIONALE);
  const canRsRibbon = ent.can(FEATURE_CHART_RS_RIBBON);

  const rsMansfieldQuery = useRSMansfield(selectedSymbol, {
    period,
    benchmark: 'SPY',
    enabled:
      Boolean(selectedSymbol) &&
      !showAdvanced &&
      canRsRibbon &&
      !ent.isLoading &&
      indicators.rsMansfieldRibbon,
  });

  const tradeSegmentsForSymbol = useMemo(
    () => (selectedSymbol ? buildTradeSegmentsFromActivity(symbolActivity, selectedSymbol) : []),
    [symbolActivity, selectedSymbol],
  );

  const chartAnnQuery = useQuery({
    queryKey: ['workspaceChartAnn', selectedSymbol, period],
    queryFn: async (): Promise<{
      volume_events: VolumeEventItem[];
      kell_patterns: KellPatternItem[];
    }> => {
      if (!selectedSymbol) {
        return { volume_events: [], kell_patterns: [] };
      }
      const res = await marketDataApi.getIndicatorSeries(selectedSymbol, { period });
      const top = (res as { data?: unknown } | null)?.data ?? res;
      const raw = (top && typeof top === 'object' ? top : {}) as Record<string, unknown>;
      const volume_events = Array.isArray(raw.volume_events) ? (raw.volume_events as VolumeEventItem[]) : [];
      const kell_patterns = Array.isArray(raw.kell_patterns) ? (raw.kell_patterns as KellPatternItem[]) : [];
      return { volume_events, kell_patterns };
    },
    enabled: Boolean(selectedSymbol) && canChartAnn && !ent.isLoading,
    staleTime: 60_000,
  });

  const handleRefresh = () => {
    queryClient.invalidateQueries({ queryKey: ['portfolioStocks'] });
    queryClient.invalidateQueries({ queryKey: ['portfolioActivity'] });
  };

  const invalidateLotQueries = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['workspaceTaxLots'] });
    queryClient.invalidateQueries({ queryKey: ['portfolioTaxLots'] });
    queryClient.invalidateQueries({ queryKey: ['portfolioStocks'] });
  }, [queryClient]);

  const handleLotSave = useCallback(async () => {
    if (!selectedSymbol || !lotForm.date || !lotForm.qty || !lotForm.costPerShare) return;
    setLotSaving(true);
    try {
      if (editingLotId) {
        await portfolioApi.updateManualTaxLot(editingLotId, {
          quantity: parseFloat(lotForm.qty),
          cost_per_share: parseFloat(lotForm.costPerShare),
          acquisition_date: lotForm.date,
        });
        toast.success('Tax lot updated');
      } else {
        await portfolioApi.createManualTaxLot({
          symbol: selectedSymbol,
          quantity: parseFloat(lotForm.qty),
          cost_per_share: parseFloat(lotForm.costPerShare),
          acquisition_date: lotForm.date,
        });
        toast.success('Tax lot added');
      }
      setLotForm(emptyLotForm);
      setEditingLotId(null);
      invalidateLotQueries();
    } catch (e: unknown) {
      toastAxiosDetail(e, 'Failed to save lot');
    } finally {
      setLotSaving(false);
    }
  }, [selectedSymbol, lotForm, editingLotId, emptyLotForm, invalidateLotQueries]);

  const handleLotDelete = useCallback(async (id: number) => {
    try {
      await portfolioApi.deleteManualTaxLot(id);
      toast.success('Tax lot deleted');
      invalidateLotQueries();
    } catch (e: unknown) {
      toastAxiosDetail(e, 'Failed to delete lot');
    }
  }, [invalidateLotQueries]);

  const isLoading = positionsQuery.isPending;

  if (isLoading) {
    return (
      <div className="flex flex-col gap-6 p-3 md:p-6">
        <PageHeader title="Workspace" subtitle="Holdings list + Trades and dividends by symbol" />
        <TableSkeleton rows={8} cols={4} />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4 p-3 md:p-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-stretch">
        {/* Left: holdings list */}
        <div className="flex h-[40vh] w-full flex-col gap-3 rounded-xl border border-border bg-card p-3 lg:h-[calc(100vh-2rem)] lg:w-[340px]">
          <div className="flex items-center gap-2">
            <div className="relative min-w-0 flex-1">
              <span className="pointer-events-none absolute top-1/2 left-2.5 -translate-y-1/2 text-muted-foreground">
                <Search className="size-4" aria-hidden />
              </span>
              <Input
                className="h-8 pl-8 text-sm"
                placeholder="Search holdings..."
                value={search}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setSearch(e.target.value)}
              />
            </div>
            <Button type="button" size="sm" variant="outline" className="shrink-0 gap-1.5" onClick={handleRefresh}>
              <RefreshCw className="size-3.5" aria-hidden />
              Refresh
            </Button>
          </div>
          <div className="flex gap-1">
            <Button
              type="button"
              size="xs"
              className="flex-1"
              variant={holdingsTab === 'open' ? 'default' : 'outline'}
              onClick={() => setHoldingsTab('open')}
            >
              Open
            </Button>
            <Button
              type="button"
              size="xs"
              className="flex-1"
              variant={holdingsTab === 'closed' ? 'default' : 'outline'}
              onClick={() => setHoldingsTab('closed')}
            >
              Closed
            </Button>
          </div>
          <div className="flex min-h-0 flex-col gap-2 overflow-y-auto">
            {holdingsTab === 'open' && filteredHoldings.map((h: EnrichedPosition) => {
              const active = selectedSymbol?.toUpperCase() === h.symbol.toUpperCase();
              const pnl = Number(h.unrealized_pnl ?? 0);
              const pnlPct = Number(h.unrealized_pnl_pct ?? 0);
              return (
                <button
                  type="button"
                  key={h.id}
                  id={`ticker-${h.symbol}`}
                  onClick={() => setSelectedSymbol(h.symbol)}
                  className={cn(
                    'flex cursor-pointer items-center gap-2 rounded-lg border p-2 text-left transition-colors',
                    active ? 'border-ring bg-muted' : 'border-border hover:bg-muted/80',
                  )}
                >
                  <span className="size-2 shrink-0 rounded-full bg-ring" />
                  <div className="min-w-0 flex-1">
                    <div className="flex w-full items-center justify-between gap-2">
                      <span className="font-bold">{h.symbol}</span>
                      <Badge
                        variant="outline"
                        className={cn(
                          'shrink-0 font-normal',
                          pnl >= 0
                            ? 'border-emerald-500/40 text-emerald-800 dark:text-emerald-200'
                            : 'border-destructive/40 text-destructive',
                        )}
                      >
                        {pnlPct.toFixed(2)}%
                      </Badge>
                    </div>
                    <div className="flex w-full items-center justify-between gap-2">
                      <span className="text-xs text-muted-foreground">{(h.shares ?? 0).toLocaleString()} sh</span>
                      <span className={cn('text-xs', semanticTextColorClass(pnl >= 0 ? 'fg.success' : 'fg.error'))}>
                        {formatMoney(Math.abs(pnl), currency, { maximumFractionDigits: 0 })}
                      </span>
                    </div>
                    {(h.average_cost != null || h.cost_basis != null) && (
                      <p className="-mt-0.5 text-xs text-muted-foreground">
                        Cost {h.cost_basis != null ? formatMoney(Number(h.cost_basis), currency, { maximumFractionDigits: 0 }) : h.average_cost != null ? `${formatMoney(Number(h.average_cost), currency)}/sh` : ''}
                      </p>
                    )}
                  </div>
                </button>
              );
            })}
            {holdingsTab === 'closed' && closedPositions.map((cp) => {
              const active = selectedSymbol?.toUpperCase() === cp.symbol.toUpperCase();
              const pnl = cp.total_realized_pnl ?? 0;
              return (
                <button
                  type="button"
                  key={cp.symbol}
                  id={`ticker-${cp.symbol}`}
                  onClick={() => setSelectedSymbol(cp.symbol)}
                  className={cn(
                    'flex cursor-pointer items-center gap-2 rounded-lg border p-2 text-left transition-colors',
                    active ? 'border-ring bg-muted' : 'border-border hover:bg-muted/80',
                  )}
                >
                  <span className="size-2 shrink-0 rounded-full bg-muted-foreground/50" />
                  <div className="min-w-0 flex-1">
                    <div className="flex w-full items-center justify-between gap-2">
                      <span className="font-bold">{cp.symbol}</span>
                      <Badge variant="outline" className="shrink-0 font-normal text-muted-foreground">
                        Closed
                      </Badge>
                    </div>
                    <div className="flex w-full items-center justify-between gap-2">
                      <span className="text-xs text-muted-foreground">{cp.trade_count} trades</span>
                      <span className={cn('text-xs', semanticTextColorClass(pnl >= 0 ? 'fg.success' : 'fg.error'))}>
                        {formatMoney(pnl, currency, { maximumFractionDigits: 0 })}
                      </span>
                    </div>
                  </div>
                </button>
              );
            })}
            {holdingsTab === 'closed' && closedPositions.length === 0 && (
              <p className="py-4 text-center text-sm text-muted-foreground">No closed positions</p>
            )}
          </div>
        </div>

        {/* Right: detail pane */}
        <div className="flex min-w-0 flex-1 flex-col gap-4">
          {/* Symbol summary bar */}
          {selectedHolding && (
            <div className="flex flex-wrap items-center gap-4 px-1">
              <div>
                <p className="text-xs text-muted-foreground">Value</p>
                <p className="text-sm font-bold">{formatMoney(Number(selectedHolding.market_value ?? 0), currency, { maximumFractionDigits: 0 })}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Cost Basis</p>
                <p className="text-sm font-bold">{formatMoney(Number(selectedHolding.cost_basis ?? (Number(selectedHolding.average_cost ?? 0) * Number(selectedHolding.shares ?? 0))), currency, { maximumFractionDigits: 0 })}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Unrealized P&L</p>
                <p
                  className={cn(
                    'text-sm font-bold',
                    semanticTextColorClass(Number(selectedHolding.unrealized_pnl ?? 0) >= 0 ? 'fg.success' : 'fg.error'),
                  )}
                >
                  {formatMoney(Number(selectedHolding.unrealized_pnl ?? 0), currency, { maximumFractionDigits: 0 })}
                  {selectedHolding.unrealized_pnl_pct != null && ` (${Number(selectedHolding.unrealized_pnl_pct).toFixed(2)}%)`}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Shares</p>
                <p className="text-sm font-bold">{Number(selectedHolding.shares ?? 0).toLocaleString()}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Avg Cost</p>
                <p className="text-sm font-bold">{selectedHolding.average_cost != null ? formatMoney(Number(selectedHolding.average_cost), currency) : '—'}</p>
              </div>
              <div className="ml-auto">
                <Button
                  type="button"
                  size="xs"
                  variant="outline"
                  className="border-destructive/40 text-destructive hover:bg-destructive/10"
                  onClick={() => setTradeTarget({
                    symbol: selectedHolding.symbol,
                    currentPrice: Number(selectedHolding.current_price ?? 0),
                    sharesHeld: Number(selectedHolding.shares ?? 0),
                    averageCost: selectedHolding.average_cost != null ? Number(selectedHolding.average_cost) : undefined,
                    positionId: selectedHolding.id,
                  })}
                >
                  Trade
                </Button>
              </div>
            </div>
          )}

          {/* Market context from snapshot */}
          {snapshot && selectedSymbol && (
            <div className="flex flex-wrap gap-2 rounded-md bg-muted/50 px-1 py-1">
              {snapshot.stage_label && (
                <Badge
                  variant="outline"
                  className={cn(
                    'h-5 font-normal',
                    String(snapshot.stage_label).startsWith('2')
                      ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-900 dark:text-emerald-200'
                      : snapshot.stage_label === '4'
                        ? 'border-destructive/40 bg-destructive/10 text-destructive'
                        : 'text-muted-foreground',
                  )}
                >
                  Stage {snapshot.stage_label}
                </Badge>
              )}
              {snapshot.current_stage_days != null && (
                <Badge variant="outline" className="h-5 font-normal">{snapshot.current_stage_days}d in stage</Badge>
              )}
              {snapshot.rsi != null && (
                <Badge
                  variant="outline"
                  className={cn(
                    'h-5 font-normal',
                    snapshot.rsi > 70
                      ? 'border-destructive/40 text-destructive'
                      : snapshot.rsi < 30
                        ? 'border-emerald-500/40 text-emerald-800 dark:text-emerald-200'
                        : 'text-muted-foreground',
                  )}
                >
                  RSI {Number(snapshot.rsi).toFixed(0)}
                </Badge>
              )}
              {snapshot.atrp_14 != null && (
                <Badge variant="outline" className="h-5 font-normal">ATR {Number(snapshot.atrp_14).toFixed(1)}%</Badge>
              )}
              {snapshot.pe_ttm != null && Number(snapshot.pe_ttm) > 0 && (
                <Badge variant="outline" className="h-5 font-normal">P/E {Number(snapshot.pe_ttm).toFixed(1)}</Badge>
              )}
              {snapshot.dividend_yield != null && Number(snapshot.dividend_yield) > 0 && (
                <Badge variant="outline" className="h-5 border-blue-500/40 font-normal text-blue-800 dark:text-blue-200">
                  Yield {Number(snapshot.dividend_yield).toFixed(2)}%
                </Badge>
              )}
              {snapshot.beta != null && (
                <Badge variant="outline" className="h-5 font-normal">Beta {Number(snapshot.beta).toFixed(2)}</Badge>
              )}
              {snapshot.rs_mansfield_pct != null && (
                <Badge
                  variant="outline"
                  className={cn(
                    'h-5 font-normal',
                    Number(snapshot.rs_mansfield_pct) > 0
                      ? 'border-emerald-500/40 text-emerald-800 dark:text-emerald-200'
                      : 'border-destructive/40 text-destructive',
                  )}
                >
                  RS {Number(snapshot.rs_mansfield_pct) > 0 ? '+' : ''}{Number(snapshot.rs_mansfield_pct).toFixed(1)}%
                </Badge>
              )}
              {(() => {
                const tdParts: string[] = [];
                if (snapshot.td_buy_complete) tdParts.push('Buy 9');
                else if ((snapshot.td_buy_setup ?? 0) >= 7) tdParts.push(`B${snapshot.td_buy_setup ?? 0}`);
                if (snapshot.td_sell_complete) tdParts.push('Sell 9');
                else if ((snapshot.td_sell_setup ?? 0) >= 7) tdParts.push(`S${snapshot.td_sell_setup ?? 0}`);
                if ((snapshot.td_buy_countdown ?? 0) >= 12) tdParts.push(`BC${snapshot.td_buy_countdown ?? 0}`);
                if ((snapshot.td_sell_countdown ?? 0) >= 12) tdParts.push(`SC${snapshot.td_sell_countdown ?? 0}`);
                return tdParts.length > 0 ? (
                  <Badge
                    variant="outline"
                    className={cn(
                      'h-5 font-normal',
                      tdParts[0].startsWith('B')
                        ? 'border-emerald-500/40 text-emerald-800 dark:text-emerald-200'
                        : 'border-destructive/40 text-destructive',
                    )}
                  >
                    TD {tdParts.join(' ')}
                  </Badge>
                ) : null;
              })()}
              {((snapshot.gaps_unfilled_up ?? 0) > 0 || (snapshot.gaps_unfilled_down ?? 0) > 0) && (
                <Badge variant="outline" className="h-5 font-normal">
                  Gaps {snapshot.gaps_unfilled_up ?? 0}↑ {snapshot.gaps_unfilled_down ?? 0}↓
                </Badge>
              )}
              {snapshot.next_earnings && (
                <Badge variant="outline" className="h-5 border-violet-500/40 font-normal text-violet-800 dark:text-violet-200">
                  Earnings {new Date(snapshot.next_earnings).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                </Badge>
              )}
            </div>
          )}

          {/* Chart */}
          <Card className="gap-0 border border-border py-0">
            <CardHeader className="gap-2 px-4 pb-2">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="font-bold">{selectedSymbol || '—'}</p>
                <div className="flex flex-wrap items-center gap-2 md:gap-3">
                  <Badge className="h-5">Live</Badge>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground">Advanced</span>
                    <Button type="button" size="xs" variant={showAdvanced ? 'default' : 'outline'} onClick={() => setShowAdvanced((v: boolean) => !v)}>
                      {showAdvanced ? 'On' : 'Off'}
                    </Button>
                  </div>
                  <div className={cn('flex flex-wrap items-center gap-2', showAdvanced && 'pointer-events-none opacity-40')}>
                    <span className="text-xs text-muted-foreground">Range</span>
                    <Button type="button" size="xs" disabled={showAdvanced} variant={period === '6mo' ? 'default' : 'outline'} onClick={() => { setPeriod('6mo'); setZoomYears(0.5); }}>6m</Button>
                    <Button type="button" size="xs" disabled={showAdvanced} variant={period === '1y' ? 'default' : 'outline'} onClick={() => { setPeriod('1y'); setZoomYears(1); }}>1y</Button>
                    <Button type="button" size="xs" disabled={showAdvanced} variant={period === '3y' ? 'default' : 'outline'} onClick={() => { setPeriod('3y'); setZoomYears(3); }}>3y</Button>
                    <Button type="button" size="xs" disabled={showAdvanced} variant={period === '5y' ? 'default' : 'outline'} onClick={() => { setPeriod('5y'); setZoomYears(5); }}>5y</Button>
                    <Button type="button" size="xs" disabled={showAdvanced} variant={period === 'max' ? 'default' : 'outline'} onClick={() => { setPeriod('max'); setZoomYears('all'); }}>All</Button>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground">Line</span>
                    <Button type="button" size="xs" variant={showLine ? 'default' : 'outline'} onClick={() => setShowLine((v: boolean) => !v)}>
                      {showLine ? 'On' : 'Off'}
                    </Button>
                  </div>
                </div>
              </div>
              {!showAdvanced && (
                <div className="mt-1 flex flex-wrap items-center gap-2">
                  <span className="text-xs text-muted-foreground">Events</span>
                  {EVENT_TOGGLE_CONFIG.map(({ type, label, activeClass }) => (
                    <Button
                      key={type}
                      type="button"
                      size="xs"
                      variant="outline"
                      className={enabledEvents.has(type) ? activeClass : ''}
                      onClick={() => toggleEventType(type)}
                    >
                      {label}
                    </Button>
                  ))}
                </div>
              )}
              {!showAdvanced && (
                <div className="mt-1 flex flex-wrap items-center gap-2">
                  <span className="text-xs text-muted-foreground">Indicators</span>
                  <Button type="button" size="xs" variant={indicators.trendLines ? 'default' : 'outline'} onClick={() => toggleIndicator('trendLines')}>Trend Lines</Button>
                  <Button type="button" size="xs" variant={indicators.gaps ? 'default' : 'outline'} onClick={() => toggleIndicator('gaps')}>Gaps</Button>
                  <Button type="button" size="xs" variant={indicators.tdSequential ? 'default' : 'outline'} onClick={() => toggleIndicator('tdSequential')}>TD Seq</Button>
                  <Button type="button" size="xs" variant={indicators.emas ? 'default' : 'outline'} onClick={() => toggleIndicator('emas')}>EMAs</Button>
                  <Button type="button" size="xs" variant={indicators.stage ? 'default' : 'outline'} onClick={() => toggleIndicator('stage')}>Stage</Button>
                  <Button type="button" size="xs" variant={indicators.supportResistance ? 'default' : 'outline'} onClick={() => toggleIndicator('supportResistance')}>S/R</Button>
                  <TierGate feature={FEATURE_CHART_RS_RIBBON} fallback={null}>
                    <Button
                      type="button"
                      size="xs"
                      variant={indicators.rsMansfieldRibbon ? 'default' : 'outline'}
                      onClick={() => toggleIndicator('rsMansfieldRibbon')}
                    >
                      Show RS Mansfield (52w)
                    </Button>
                  </TierGate>
                </div>
              )}
              {lockedDaySec ? (
                <div className="mt-2 flex flex-wrap items-center gap-3">
                  <Badge variant="outline" className="h-5 border-violet-500/40 text-violet-800 dark:text-violet-200">Pinned</Badge>
                  <span className="text-sm">{new Date(lockedDaySec * 1000).toISOString().slice(0, 10)}</span>
                  <Button type="button" size="xs" variant="outline" onClick={() => setLockedDaySec(null)}>
                    Clear
                  </Button>
                </div>
              ) : null}
            </CardHeader>
            <CardContent className="px-0 pb-4">
              {selectedSymbol ? (
                showAdvanced ? (
                  <TradingViewChart
                    symbol={selectedSymbol}
                    height={chartHeight}
                    showHeader={false}
                    theme="dark"
                  />
                ) : barsQuery.isPending ? (
                  <div className="flex items-center justify-center" style={{ height: chartHeight }}>
                    <div className="flex flex-col items-center gap-2">
                      <div className="h-8 w-8 animate-spin rounded-full border-2 border-muted-foreground border-t-transparent" />
                      <p className="text-sm text-muted-foreground">Loading chart...</p>
                    </div>
                  </div>
                ) : barsError ? (
                  <div className="flex flex-col items-center justify-center gap-3" style={{ height: chartHeight }}>
                    <p className="text-muted-foreground">No price data available for {selectedSymbol}</p>
                    <Button type="button" size="sm" variant="outline" onClick={() => setShowAdvanced(true)}>
                      Open TradingView Chart
                    </Button>
                  </div>
                ) : (
                  <>
                    {!ent.isLoading && !ent.isError && !canChartAnn && (
                      <p className="px-4 pb-2 text-xs text-muted-foreground">
                        Upgrade to Pro to see your trades annotated.
                      </p>
                    )}
                    {canChartAnn && !showAdvanced && (
                      <div className="flex flex-wrap items-center gap-2 px-4 pb-2">
                        <span className="text-xs text-muted-foreground">Kell</span>
                        <OliverKellLegend />
                        {chartAnnQuery.isError && (
                          <span className="text-xs text-destructive">Pattern data unavailable</span>
                        )}
                        {chartAnnQuery.isLoading && (
                          <span className="text-xs text-muted-foreground">Loading pattern markers…</span>
                        )}
                      </div>
                    )}
                    <SymbolChartWithMarkers
                    height={chartHeight}
                    bars={bars}
                    symbol={selectedSymbol ?? undefined}
                    events={filteredEvents}
                    showEvents={enabledEvents.size > 0}
                    onHoverDaySec={handleHoverDay}
                    onClickDaySec={handleClickDay}
                    showLine={showLine}
                    zoomYears={zoomYears}
                    avgPrice={avgPrice}
                    pinnedDaySec={lockedDaySec}
                    indicators={indicators}
                    colors={chartColors}
                    priceLinesExtra={enabledEvents.has('ORDER_PENDING') ? priceLinesExtra : undefined}
                    volumeEvents={canChartAnn ? (chartAnnQuery.isLoading ? null : (chartAnnQuery.data?.volume_events ?? [])) : null}
                    kellPatterns={canChartAnn ? (chartAnnQuery.isLoading ? null : (chartAnnQuery.data?.kell_patterns ?? [])) : null}
                    tradeSegments={canChartAnn ? tradeSegmentsForSymbol : []}
                    proPlusRationale={canKellRationale}
                    stageLabel={typeof snapshot?.stage_label === 'string' ? snapshot.stage_label : null}
                    currentStageDays={
                      typeof snapshot?.current_stage_days === 'number' ? snapshot.current_stage_days : null
                    }
                    snapshotLoading={snapshotQuery.isLoading}
                  />
                    <TierGate
                      feature={FEATURE_CHART_RS_RIBBON}
                      fallback={
                        <div className="border-t border-border px-4 py-3">
                          <p className="text-sm text-muted-foreground">
                            Upgrade to Pro to see relative-strength structure
                          </p>
                          <Button asChild className="mt-2" size="sm" variant="outline">
                            <Link href="/pricing">View plans</Link>
                          </Button>
                        </div>
                      }
                    >
                      {indicators.rsMansfieldRibbon ? (
                        <div className="border-t border-border pt-2">
                          <RSMansfieldRibbon
                            isPending={rsMansfieldQuery.isPending}
                            isError={rsMansfieldQuery.isError}
                            error={rsMansfieldQuery.error instanceof Error ? rsMansfieldQuery.error : null}
                            onRetry={() => void rsMansfieldQuery.refetch()}
                            points={rsMansfieldQuery.points}
                            benchmark="SPY"
                          />
                        </div>
                      ) : null}
                    </TierGate>
                  </>
                )
              ) : <div style={{ height: chartHeight }} />}
            </CardContent>
          </Card>

          {/* Tax Lots for {SYMBOL} — full-width below the chart.
              Root cause of the founder's "we dont see that" report: this
              card previously lived in a 2/3-width grid cell beside
              Dividends, which pushed it below the fold on a 1080p screen
              (chart ~520px + summary + badges + indicator controls). The
              old empty-state also silently swallowed query errors — a lot
              that failed to load looked identical to "nothing synced yet".
              Now: promoted to full width, titled with the selected symbol,
              and a strict loading / error / empty / data split so no
              ambiguity is possible. */}
          <Card
            className={cn(
              'gap-0 overflow-hidden border border-border py-0',
              lotEditMode ? 'max-h-[75vh] md:max-h-[560px]' : 'max-h-[60vh] md:max-h-[440px]',
            )}
            data-testid="workspace-tax-lots"
          >
            <CardHeader className="flex-row items-center justify-between gap-2 px-4 pb-2">
              <div className="flex items-center gap-2">
                <p className="font-bold">
                  {selectedSymbol ? `Tax Lots for ${selectedSymbol}` : 'Tax Lots'}
                </p>
                {lotsQuery.isSuccess && lots.length > 0 ? (
                  <Badge variant="outline" className="font-normal">{lots.length}</Badge>
                ) : null}
              </div>
              <Button
                type="button"
                size="icon-xs"
                variant={lotEditMode ? 'default' : 'ghost'}
                className={lotEditMode ? 'bg-violet-600/15 text-violet-900 hover:bg-violet-600/25 dark:text-violet-200' : ''}
                aria-label={lotEditMode ? 'Lock tax lots' : 'Unlock to add/edit lots'}
                onClick={() => { setLotEditMode(v => !v); setEditingLotId(null); setLotForm(emptyLotForm); }}
              >
                {lotEditMode ? <Unlock className="size-3.5" /> : <Lock className="size-3.5" />}
              </Button>
            </CardHeader>
            <CardContent className="px-0 pb-0">
              {!selectedSymbol ? (
                <div className="flex flex-col items-center gap-2 px-4 py-8 text-center">
                  <p className="text-sm text-muted-foreground">
                    Select a holding from the list to view its tax lots.
                  </p>
                </div>
              ) : !selectedHolding?.id ? (
                <div className="flex flex-col items-center gap-3 px-4 py-8 text-center">
                  <p className="text-sm text-muted-foreground">
                    No open position for {selectedSymbol}. Add a manual lot to start
                    tracking one.
                  </p>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => { setLotEditMode(true); setEditingLotId(null); setLotForm(emptyLotForm); }}
                  >
                    <Plus className="size-3.5" aria-hidden />
                    Add a lot
                  </Button>
                </div>
              ) : lotsQuery.isPending ? (
                <div
                  className="flex flex-col gap-2 px-4 py-4"
                  aria-busy="true"
                  aria-label={`Loading tax lots for ${selectedSymbol}`}
                  data-testid="workspace-tax-lots-loading"
                >
                  <Skeleton className="h-4 w-48" />
                  <Skeleton className="h-8 w-full" />
                  <Skeleton className="h-8 w-full" />
                  <Skeleton className="h-8 w-full" />
                </div>
              ) : lotsQuery.isError ? (
                <div
                  className="flex flex-col items-center gap-3 px-4 py-8 text-center"
                  role="alert"
                  data-testid="workspace-tax-lots-error"
                >
                  <AlertTriangle className="size-5 text-destructive" aria-hidden />
                  <p className="text-sm text-destructive">
                    Couldn't load lots for {selectedSymbol}.
                  </p>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => void lotsQuery.refetch()}
                  >
                    Retry
                  </Button>
                </div>
              ) : lots.length === 0 ? (
                <div
                  className="flex flex-col items-center gap-3 px-4 py-8 text-center"
                  data-testid="workspace-tax-lots-empty"
                >
                  <p className="text-sm text-muted-foreground">
                    No lots tracked for {selectedSymbol}. Sync your brokerage or add
                    a manual lot below.
                  </p>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => { setLotEditMode(true); setEditingLotId(null); setLotForm(emptyLotForm); }}
                  >
                    <Plus className="size-3.5" aria-hidden />
                    Add a lot
                  </Button>
                </div>
              ) : (
                <div className="max-h-[250px] overflow-auto md:max-h-[340px]" data-testid="workspace-tax-lots-table">
                  <table className="w-full min-w-[640px] border-collapse text-left text-xs">
                    <thead>
                      <tr className="border-b border-border bg-muted/50">
                        <th className="px-2 py-1.5 font-medium">Date</th>
                        <th className="px-2 py-1.5 font-medium">Type</th>
                        <th className="px-2 py-1.5 text-right font-medium">Days</th>
                        <th className="px-2 py-1.5 text-right font-medium">Shares</th>
                        <th className="px-2 py-1.5 text-right font-medium">Cost/Share</th>
                        <th className="px-2 py-1.5 text-right font-medium">Value</th>
                        <th className="px-2 py-1.5 text-right font-medium">P/L</th>
                        <th className="w-7 px-0 py-1.5" />
                      </tr>
                    </thead>
                    <tbody>
                      {lots
                        .slice()
                        .sort((a: LotRow, b: LotRow) => new Date(b.purchase_date || '').getTime() - new Date(a.purchase_date || '').getTime())
                        .map((l: LotRow, idx: number) => {
                          const lotDay = (l.purchase_date || '').slice(0, 10);
                          const hoverDay = focusedDaySec ? new Date(focusedDaySec * 1000).toISOString().slice(0, 10) : '';
                          const focused = hoverDay && lotDay === hoverDay;
                          const sh = Number((l.shares_remaining ?? l.shares) || 0);
                          const cps = Number(l.cost_per_share || 0);
                          const cost = sh * cps;
                          const lastClose = bars?.length ? Number(bars[bars.length - 1].close || 0) : 0;
                          const val = sh * lastClose;
                          const pnl = val - cost;
                          const daysHeld = l.days_held ?? 0;
                          const isLT = l.is_long_term ?? daysHeld >= 365;
                          const approachingLT = !isLT && daysHeld >= 300;
                          const srcOfficial = l.source === 'OFFICIAL_STATEMENT' || l.source === 'official_statement';
                          const srcManual = l.source === 'MANUAL_ENTRY' || l.source === 'manual_entry';
                          return (
                            <tr
                              id={`lot-${lotDay}-${idx}`}
                              key={`lot-${l.id || idx}`}
                              className={cn(
                                'group border-b border-border',
                                focused && 'bg-muted',
                                approachingLT && (isDark ? 'bg-yellow-950/40' : 'bg-yellow-50'),
                              )}
                            >
                              <td className="px-2 py-1.5">{formatDateFriendly(l.purchase_date, timezone)}</td>
                              <td className="px-2 py-1.5">
                                <div className="flex flex-wrap gap-1">
                                  <Badge
                                    variant="outline"
                                    className={cn(
                                      'h-5 font-normal',
                                      isLT
                                        ? 'border-emerald-500/40 text-emerald-800 dark:text-emerald-200'
                                        : approachingLT
                                          ? 'border-amber-500/40 text-amber-900 dark:text-amber-200'
                                          : 'text-muted-foreground',
                                    )}
                                  >
                                    {isLT ? 'LT' : 'ST'}
                                  </Badge>
                                  {l.source ? (
                                    <Badge
                                      variant="outline"
                                      className={cn(
                                        'h-5 font-normal',
                                        srcOfficial
                                          ? 'border-blue-500/40 text-blue-800 dark:text-blue-200'
                                          : srcManual
                                            ? 'border-violet-500/40 text-violet-800 dark:text-violet-200'
                                            : 'text-muted-foreground',
                                      )}
                                    >
                                      {srcOfficial ? 'Official' : srcManual ? 'Manual' : 'Est'}
                                    </Badge>
                                  ) : null}
                                </div>
                              </td>
                              <td className={cn(
                                'px-2 py-1.5 text-right',
                                approachingLT
                                  ? isDark
                                    ? 'text-amber-400'
                                    : 'text-amber-800'
                                  : 'text-muted-foreground',
                              )}
                              >
                                {daysHeld}d
                              </td>
                              <td className="px-2 py-1.5 text-right tabular-nums">{sh.toLocaleString()}</td>
                              <td className="px-2 py-1.5 text-right tabular-nums">{cps ? formatMoney(cps, currency) : '-'}</td>
                              <td className="px-2 py-1.5 text-right tabular-nums">{val ? formatMoney(val, currency, { maximumFractionDigits: 0 }) : '-'}</td>
                              <td className={cn('px-2 py-1.5 text-right tabular-nums', semanticTextColorClass(pnl >= 0 ? 'fg.success' : 'fg.error'))}>
                                {pnl ? formatMoney(pnl, currency, { maximumFractionDigits: 0 }) : '-'}
                              </td>
                              <td className="p-0">
                                {lotEditMode && srcManual ? (
                                  <div className="flex justify-end gap-0">
                                    <Button
                                      type="button"
                                      size="icon-xs"
                                      variant="ghost"
                                      aria-label="Edit lot"
                                      onClick={() => {
                                        setEditingLotId(l.id ?? null);
                                        setLotForm({
                                          date: (l.purchase_date || '').slice(0, 10),
                                          qty: String(sh),
                                          costPerShare: String(cps),
                                        });
                                      }}
                                    >
                                      <Pencil className="size-3.5" />
                                    </Button>
                                    <Button
                                      type="button"
                                      size="icon-xs"
                                      variant="ghost"
                                      className="text-destructive hover:text-destructive"
                                      aria-label="Delete lot"
                                      onClick={() => l.id && handleLotDelete(l.id)}
                                    >
                                      <Trash2 className="size-3.5" />
                                    </Button>
                                  </div>
                                ) : (
                                  <div className="flex justify-end pr-1">
                                    <Button
                                      type="button"
                                      size="icon-xs"
                                      variant="ghost"
                                      className="text-destructive opacity-0 transition-opacity group-hover:opacity-100 hover:text-destructive"
                                      aria-label={`Sell ${sh} shares from lot`}
                                      onClick={() => setTradeTarget({
                                        symbol: selectedSymbol!,
                                        currentPrice: lastClose,
                                        sharesHeld: sh,
                                        averageCost: cps || undefined,
                                        positionId: selectedHolding?.id,
                                      })}
                                    >
                                      <MinusCircle className="size-3.5" />
                                    </Button>
                                  </div>
                                )}
                              </td>
                            </tr>
                          );
                        })}
                      {lots.length > 0 && (() => {
                        const lastClose = bars?.length ? Number(bars[bars.length - 1].close || 0) : 0;
                        const totals = lots.reduce<LotTotals>(
                          (acc, l: LotRow) => {
                            const sh = Number((l.shares_remaining ?? l.shares) || 0);
                            const cps = Number(l.cost_per_share || 0);
                            acc.shares += sh;
                            acc.cost += sh * cps;
                            acc.value += sh * lastClose;
                            return acc;
                          },
                          { shares: 0, cost: 0, value: 0 },
                        );
                        const totalPnl = totals.value - totals.cost;
                        return (
                          <tr className="border-b border-border bg-muted/40">
                            <td colSpan={3} className="px-2 py-1.5 font-semibold">Total</td>
                            <td className="px-2 py-1.5 text-right font-semibold tabular-nums">{totals.shares.toLocaleString()}</td>
                            <td className="px-2 py-1.5 text-right font-semibold tabular-nums">{formatMoney(totals.cost / (totals.shares || 1), currency)}</td>
                            <td className="px-2 py-1.5 text-right font-semibold tabular-nums">{formatMoney(totals.value, currency, { maximumFractionDigits: 0 })}</td>
                            <td className={cn('px-2 py-1.5 text-right font-semibold tabular-nums', semanticTextColorClass(totalPnl >= 0 ? 'fg.success' : 'fg.error'))}>
                              {formatMoney(totalPnl, currency, { maximumFractionDigits: 0 })}
                            </td>
                            <td className="w-7" />
                          </tr>
                        );
                      })()}
                    </tbody>
                  </table>
                </div>
              )}
              {lotEditMode && selectedSymbol && (
                <div className="border-t border-border bg-muted/40 px-3 py-2">
                  <p className="mb-1 text-xs font-semibold text-muted-foreground">
                    {editingLotId ? 'Edit Lot' : 'Add Manual Lot'}
                  </p>
                    <div className="flex flex-wrap items-end gap-2">
                      <div>
                        <p className="text-[10px] text-muted-foreground">Date</p>
                        <Input
                          className="h-8 w-[130px] text-xs"
                          type="date"
                          value={lotForm.date}
                          onChange={(e: React.ChangeEvent<HTMLInputElement>) => setLotForm(f => ({ ...f, date: e.target.value }))}
                          max={new Date().toISOString().slice(0, 10)}
                        />
                      </div>
                      <div>
                        <p className="text-[10px] text-muted-foreground">Shares</p>
                        <Input
                          className="h-8 w-20 text-xs"
                          type="number"
                          placeholder="Qty"
                          value={lotForm.qty}
                          onChange={(e: React.ChangeEvent<HTMLInputElement>) => setLotForm(f => ({ ...f, qty: e.target.value }))}
                          min={0}
                          step="any"
                        />
                      </div>
                      <div>
                        <p className="text-[10px] text-muted-foreground">Cost/Share</p>
                        <Input
                          className="h-8 w-[90px] text-xs"
                          type="number"
                          placeholder="Price"
                          value={lotForm.costPerShare}
                          onChange={(e: React.ChangeEvent<HTMLInputElement>) => setLotForm(f => ({ ...f, costPerShare: e.target.value }))}
                          min={0}
                          step="any"
                        />
                      </div>
                      <Button
                        type="button"
                        size="xs"
                        className="bg-violet-600/15 text-violet-900 hover:bg-violet-600/25 dark:text-violet-200"
                        disabled={lotSaving || !lotForm.date || !lotForm.qty || !lotForm.costPerShare}
                        onClick={() => void handleLotSave()}
                      >
                        {lotSaving ? '...' : editingLotId ? 'Update' : 'Save'}
                      </Button>
                      {editingLotId ? (
                        <Button
                          type="button"
                          size="xs"
                          variant="ghost"
                          onClick={() => { setEditingLotId(null); setLotForm(emptyLotForm); }}
                        >
                          Cancel
                        </Button>
                      ) : null}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Dividends */}
            <Card className="max-h-[50vh] gap-0 overflow-hidden border border-border py-0 md:max-h-[400px]">
              <CardHeader className="flex-row items-center justify-between gap-2 px-4 pb-2">
                <p className="font-bold">Dividends</p>
                <div className="flex items-center gap-2">
                  {symbolDividends.length > 0 ? (
                    <span className="text-xs text-muted-foreground">
                      Total {formatMoney(symbolDividends.reduce((s, r: ActivityRow) => s + Number(r.amount || r.net_amount || 0), 0), currency)}
                    </span>
                  ) : null}
                  <Badge variant="outline" className="font-normal">{symbolDividends.length}</Badge>
                </div>
              </CardHeader>
              <CardContent className="px-0 pb-0">
                <div className="max-h-[250px] overflow-auto md:max-h-[340px]">
                  <table className="w-full border-collapse text-left text-xs">
                    <thead>
                      <tr className="border-b border-border bg-muted/50">
                        <th className="px-2 py-1.5 font-medium">Date</th>
                        <th className="px-2 py-1.5 text-right font-medium">Amount</th>
                        <th className="px-2 py-1.5 text-right font-medium">Per Share</th>
                      </tr>
                    </thead>
                    <tbody>
                      {symbolDividends.length === 0 && (
                        <tr>
                          <td colSpan={3} className="px-2 py-4 text-center text-muted-foreground">
                            No dividend history for {selectedSymbol ?? 'this symbol'}.
                          </td>
                        </tr>
                      )}
                      {symbolDividends.map((r: ActivityRow, idx: number) => {
                        const day = (r.ts || '').slice(0, 10);
                        const hoverDay = focusedDaySec ? new Date(focusedDaySec * 1000).toISOString().slice(0, 10) : '';
                        const focused = hoverDay && day === hoverDay;
                        const amt = Number(r.amount || r.net_amount || 0);
                        const qty = Number(r.quantity || 0);
                        const perShare = qty > 0 ? amt / qty : null;
                        return (
                          <tr
                            id={`div-${day}-${idx}`}
                            key={`div-${r.external_id || idx}`}
                            className={cn('border-b border-border', focused && 'bg-muted')}
                          >
                            <td className="px-2 py-1.5">{formatDateFriendly(r.ts, timezone)}</td>
                            <td className="px-2 py-1.5 text-right tabular-nums">{amt ? formatMoney(amt, currency) : '-'}</td>
                            <td className="px-2 py-1.5 text-right tabular-nums text-muted-foreground">
                              {perShare != null ? formatMoney(perShare, currency, { minimumFractionDigits: 2, maximumFractionDigits: 4 }) : '-'}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
        </div>
      </div>

      {tradeTarget ? (
        <TradeModal
          isOpen={!!tradeTarget}
          symbol={tradeTarget.symbol}
          currentPrice={tradeTarget.currentPrice}
          sharesHeld={tradeTarget.sharesHeld}
          averageCost={tradeTarget.averageCost}
          positionId={tradeTarget.positionId}
          onClose={() => setTradeTarget(null)}
        />
      ) : null}
    </div>
  );
};

export default PortfolioWorkspaceClient;
