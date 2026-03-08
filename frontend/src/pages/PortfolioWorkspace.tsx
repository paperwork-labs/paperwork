import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Box,
  Flex,
  VStack,
  Input,
  InputGroup,
  Text,
  Badge,
  CardRoot,
  CardBody,
  CardHeader,
  Button,
  IconButton,
  TableScrollArea,
  TableRoot,
  TableHeader,
  TableBody,
  TableRow,
  TableColumnHeader,
  TableCell,
  useMediaQuery,
} from '@chakra-ui/react';
import { FiRefreshCw, FiSearch, FiMinusCircle, FiLock, FiUnlock, FiEdit2, FiTrash2 } from 'react-icons/fi';
import toast from 'react-hot-toast';
import { useQuery, useQueryClient } from 'react-query';
import PageHeader from '../components/ui/PageHeader';
import SymbolChartWithMarkers, { getStoredIndicators, storeIndicators } from '../components/charts/SymbolChartWithMarkers';
import type { IndicatorToggles, ChartEvent, ChartEventType } from '../components/charts/SymbolChartWithMarkers';
import TradingViewChart from '../components/charts/TradingViewChart';
import api, { marketDataApi, portfolioApi, unwrapResponse } from '../services/api';
import { usePositions, useActivity, useClosedPositions } from '../hooks/usePortfolio';
import { useAccountContext } from '../context/AccountContext';
import { useUserPreferences } from '../hooks/useUserPreferences';
import { useChartColors } from '../hooks/useChartColors';
import { formatMoney } from '../utils/format';
import { TableSkeleton } from '../components/shared/Skeleton';
import { useColorMode } from '../theme/colorMode';
import type { EnrichedPosition, ActivityRow, LotRow } from '../types/portfolio';
import TradeModal from '../components/orders/TradeModal';

type TradeTarget = { symbol: string; currentPrice: number; sharesHeld: number; averageCost?: number; positionId?: number } | null;

interface LotTotals {
  shares: number;
  cost: number;
  value: number;
}

const fmtDate = (iso: string | undefined | null) => {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return String(iso).slice(0, 10);
  return d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: '2-digit' });
};

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

const EVENT_TOGGLE_CONFIG: { type: ChartEventType; label: string; colorPalette: string }[] = [
  { type: 'BUY', label: 'Buys', colorPalette: 'green' },
  { type: 'SELL', label: 'Sells', colorPalette: 'red' },
  { type: 'DIVIDEND', label: 'Divs', colorPalette: 'teal' },
  { type: 'ORDER_PENDING', label: 'Orders', colorPalette: 'yellow' },
];

const PortfolioWorkspace: React.FC = () => {
  const { selected } = useAccountContext();
  const { currency } = useUserPreferences();
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

  const [isMdOrLarger] = useMediaQuery(['(min-width: 768px)']);
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

  const barsQuery = useQuery(
    ['workspaceBars', selectedSymbol, period],
    async () => {
      if (!selectedSymbol) return [];
      const res = await marketDataApi.getHistory(selectedSymbol, period, '1d');
      return unwrapResponse<{ time: string; open: number; high: number; low: number; close: number; volume?: number }>(res, 'bars');
    },
    { enabled: !!selectedSymbol, staleTime: 300000 }
  );
  const bars = barsQuery.data ?? [];
  const barsError = barsQuery.isError || (barsQuery.isSuccess && bars.length === 0);

  const snapshotQuery = useQuery(
    ['workspaceSnapshot', selectedSymbol],
    async () => {
      if (!selectedSymbol) return null;
      const res = await marketDataApi.getSnapshot(selectedSymbol);
      const d = (res as any)?.data;
      return d?.data?.snapshot ?? d?.snapshot ?? d ?? null;
    },
    { enabled: !!selectedSymbol, staleTime: 600000 }
  );
  const snapshot = snapshotQuery.data as Record<string, any> | null;

  const selectedHolding = holdings.find(h => h.symbol === selectedSymbol);
  const lotsQuery = useQuery(
    ['workspaceTaxLots', selectedHolding?.id],
    async () => {
      if (!selectedHolding?.id) return [];
      const res = await portfolioApi.getHoldingTaxLots(selectedHolding.id);
      return unwrapResponse<LotRow>(res, 'tax_lots');
    },
    { enabled: !!selectedHolding?.id, staleTime: 60000 }
  );
  const lots = lotsQuery.data ?? [];

  const ordersQuery = useQuery(
    ['workspaceOrders', selectedSymbol],
    async () => {
      if (!selectedSymbol) return [];
      const res = await api.get('/portfolio/orders', { params: { symbol: selectedSymbol, limit: 50 } });
      return res.data?.data ?? res.data ?? [];
    },
    {
      enabled: !!selectedSymbol,
      staleTime: 15000,
      refetchInterval: (data: any) => {
        const active = (data ?? []).some((o: any) => ['submitted', 'pending_submit', 'partially_filled'].includes(o.status));
        return active ? 5000 : false;
      },
    }
  );
  const orders: any[] = ordersQuery.data ?? [];

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
      .filter((o: any) => o.created_at || o.filled_at || o.submitted_at)
      .map((o: any) => {
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
    const ACTIVE = new Set(['submitted', 'pending_submit', 'partially_filled']);
    return orders
      .filter((o: any) => ACTIVE.has(o.status))
      .flatMap((o: any) => {
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
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'Failed to save lot');
    } finally {
      setLotSaving(false);
    }
  }, [selectedSymbol, lotForm, editingLotId, emptyLotForm, invalidateLotQueries]);

  const handleLotDelete = useCallback(async (id: number) => {
    try {
      await portfolioApi.deleteManualTaxLot(id);
      toast.success('Tax lot deleted');
      invalidateLotQueries();
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'Failed to delete lot');
    }
  }, [invalidateLotQueries]);

  const isLoading = positionsQuery.isLoading;

  if (isLoading) {
    return (
      <VStack p={{ base: 3, md: 6 }} gap={6} align="stretch">
        <PageHeader title="Workspace" subtitle="Holdings list + Trades and dividends by symbol" />
        <TableSkeleton rows={8} cols={4} />
      </VStack>
    );
  }

  return (
    <VStack p={{ base: 3, md: 6 }} gap={4} align="stretch">
      <Flex gap={4} align="stretch" flexDirection={{ base: 'column', lg: 'row' }}>
        {/* Left: holdings list */}
        <VStack bg="bg.card" borderWidth="1px" borderColor="border.subtle" borderRadius="xl" p={3} gap={3} align="stretch" w={{ base: '100%', lg: '340px' }} h={{ base: '40vh', lg: 'calc(100vh - 2rem)' }}>
          <Box display="flex" gap={2} alignItems="center">
            <InputGroup
              startElement={
                <Box color="fg.muted" display="flex" alignItems="center">
                  <FiSearch />
                </Box>
              }
            >
              <Input placeholder="Search holdings..." value={search} onChange={(e: React.ChangeEvent<HTMLInputElement>) => setSearch(e.target.value)} />
            </InputGroup>
            <Button size="sm" variant="outline" onClick={handleRefresh}>
              <FiRefreshCw />
              Refresh
            </Button>
          </Box>
          <Box display="flex" gap={1}>
            <Button size="xs" flex={1} variant={holdingsTab === 'open' ? 'solid' : 'outline'} onClick={() => setHoldingsTab('open')}>
              Open
            </Button>
            <Button size="xs" flex={1} variant={holdingsTab === 'closed' ? 'solid' : 'outline'} onClick={() => setHoldingsTab('closed')}>
              Closed
            </Button>
          </Box>
          <VStack gap={2} align="stretch" overflowY="auto">
            {holdingsTab === 'open' && filteredHoldings.map((h: EnrichedPosition) => {
              const active = selectedSymbol?.toUpperCase() === h.symbol.toUpperCase();
              const pnl = Number(h.unrealized_pnl ?? 0);
              const pnlPct = Number(h.unrealized_pnl_pct ?? 0);
              const color = pnl >= 0 ? 'fg.success' : 'fg.error';
              return (
                <Box
                  key={h.id}
                  id={`ticker-${h.symbol}`}
                  onClick={() => setSelectedSymbol(h.symbol)}
                  cursor="pointer"
                  p={2}
                  borderRadius="lg"
                  borderWidth="1px"
                  borderColor={active ? 'border.emphasis' : 'border.subtle'}
                  bg={active ? 'bg.muted' : undefined}
                  _hover={{ bg: 'bg.muted' }}
                  display="flex"
                  gap={2}
                  alignItems="center"
                >
                  <Box w="8px" h="8px" borderRadius="full" bg="border.emphasis" />
                  <VStack gap={0} align="start" flex={1}>
                    <Box display="flex" justifyContent="space-between" width="full">
                      <Text fontWeight="bold">{h.symbol}</Text>
                      <Badge colorPalette={pnl >= 0 ? 'green' : 'red'}>
                        {pnlPct.toFixed(2)}%
                      </Badge>
                    </Box>
                    <Box display="flex" justifyContent="space-between" width="full">
                      <Text fontSize="xs" color="fg.muted">{(h.shares ?? 0).toLocaleString()} sh</Text>
                      <Text fontSize="xs" color={color}>{formatMoney(Math.abs(pnl), currency, { maximumFractionDigits: 0 })}</Text>
                    </Box>
                    {(h.average_cost != null || h.cost_basis != null) && (
                      <Text fontSize="xs" color="fg.muted" mt={-0.5}>
                        Cost {h.cost_basis != null ? formatMoney(Number(h.cost_basis), currency, { maximumFractionDigits: 0 }) : h.average_cost != null ? `${formatMoney(Number(h.average_cost), currency)}/sh` : ''}
                      </Text>
                    )}
                  </VStack>
                </Box>
              );
            })}
            {holdingsTab === 'closed' && closedPositions.map((cp) => {
              const active = selectedSymbol?.toUpperCase() === cp.symbol.toUpperCase();
              const pnl = cp.total_realized_pnl ?? 0;
              return (
                <Box
                  key={cp.symbol}
                  id={`ticker-${cp.symbol}`}
                  onClick={() => setSelectedSymbol(cp.symbol)}
                  cursor="pointer"
                  p={2}
                  borderRadius="lg"
                  borderWidth="1px"
                  borderColor={active ? 'border.emphasis' : 'border.subtle'}
                  bg={active ? 'bg.muted' : undefined}
                  _hover={{ bg: 'bg.muted' }}
                  display="flex"
                  gap={2}
                  alignItems="center"
                >
                  <Box w="8px" h="8px" borderRadius="full" bg="fg.muted" opacity={0.5} />
                  <VStack gap={0} align="start" flex={1}>
                    <Box display="flex" justifyContent="space-between" width="full">
                      <Text fontWeight="bold">{cp.symbol}</Text>
                      <Badge colorPalette="gray" variant="outline">Closed</Badge>
                    </Box>
                    <Box display="flex" justifyContent="space-between" width="full">
                      <Text fontSize="xs" color="fg.muted">{cp.trade_count} trades</Text>
                      <Text fontSize="xs" color={pnl >= 0 ? 'fg.success' : 'fg.error'}>
                        {formatMoney(pnl, currency, { maximumFractionDigits: 0 })}
                      </Text>
                    </Box>
                  </VStack>
                </Box>
              );
            })}
            {holdingsTab === 'closed' && closedPositions.length === 0 && (
              <Text fontSize="sm" color="fg.muted" textAlign="center" py={4}>No closed positions</Text>
            )}
          </VStack>
        </VStack>

        {/* Right: detail pane */}
        <VStack flex={1} gap={4} align="stretch">
          {/* Symbol summary bar */}
          {selectedHolding && (
            <Box display="flex" gap={4} flexWrap="wrap" px={1} alignItems="center">
              <Box>
                <Text fontSize="xs" color="fg.muted">Value</Text>
                <Text fontSize="sm" fontWeight="bold">{formatMoney(Number(selectedHolding.market_value ?? 0), currency, { maximumFractionDigits: 0 })}</Text>
              </Box>
              <Box>
                <Text fontSize="xs" color="fg.muted">Cost Basis</Text>
                <Text fontSize="sm" fontWeight="bold">{formatMoney(Number(selectedHolding.cost_basis ?? (Number(selectedHolding.average_cost ?? 0) * Number(selectedHolding.shares ?? 0))), currency, { maximumFractionDigits: 0 })}</Text>
              </Box>
              <Box>
                <Text fontSize="xs" color="fg.muted">Unrealized P&L</Text>
                <Text fontSize="sm" fontWeight="bold" color={Number(selectedHolding.unrealized_pnl ?? 0) >= 0 ? 'fg.success' : 'fg.error'}>
                  {formatMoney(Number(selectedHolding.unrealized_pnl ?? 0), currency, { maximumFractionDigits: 0 })}
                  {selectedHolding.unrealized_pnl_pct != null && ` (${Number(selectedHolding.unrealized_pnl_pct).toFixed(2)}%)`}
                </Text>
              </Box>
              <Box>
                <Text fontSize="xs" color="fg.muted">Shares</Text>
                <Text fontSize="sm" fontWeight="bold">{Number(selectedHolding.shares ?? 0).toLocaleString()}</Text>
              </Box>
              <Box>
                <Text fontSize="xs" color="fg.muted">Avg Cost</Text>
                <Text fontSize="sm" fontWeight="bold">{selectedHolding.average_cost != null ? formatMoney(Number(selectedHolding.average_cost), currency) : '—'}</Text>
              </Box>
              <Box ml="auto">
                <Button
                  size="xs"
                  variant="outline"
                  colorPalette="red"
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
              </Box>
            </Box>
          )}

          {/* Market context from snapshot */}
          {snapshot && selectedSymbol && (
            <Box display="flex" gap={3} flexWrap="wrap" px={1} py={1} borderRadius="md" bg="bg.subtle">
              {snapshot.stage_label && (
                <Badge
                  colorPalette={String(snapshot.stage_label).startsWith('2') ? 'green' : snapshot.stage_label === '4' ? 'red' : 'gray'}
                  variant="subtle" size="sm"
                >
                  Stage {snapshot.stage_label}
                </Badge>
              )}
              {snapshot.current_stage_days != null && (
                <Badge variant="outline" size="sm">{snapshot.current_stage_days}d in stage</Badge>
              )}
              {snapshot.rsi != null && (
                <Badge colorPalette={snapshot.rsi > 70 ? 'red' : snapshot.rsi < 30 ? 'green' : 'gray'} variant="outline" size="sm">
                  RSI {Number(snapshot.rsi).toFixed(0)}
                </Badge>
              )}
              {snapshot.atrp_14 != null && (
                <Badge variant="outline" size="sm">ATR {Number(snapshot.atrp_14).toFixed(1)}%</Badge>
              )}
              {snapshot.pe_ttm != null && Number(snapshot.pe_ttm) > 0 && (
                <Badge variant="outline" size="sm">P/E {Number(snapshot.pe_ttm).toFixed(1)}</Badge>
              )}
              {snapshot.dividend_yield != null && Number(snapshot.dividend_yield) > 0 && (
                <Badge colorPalette="blue" variant="outline" size="sm">Yield {Number(snapshot.dividend_yield).toFixed(2)}%</Badge>
              )}
              {snapshot.beta != null && (
                <Badge variant="outline" size="sm">Beta {Number(snapshot.beta).toFixed(2)}</Badge>
              )}
              {snapshot.rs_mansfield_pct != null && (
                <Badge colorPalette={Number(snapshot.rs_mansfield_pct) > 0 ? 'green' : 'red'} variant="outline" size="sm">
                  RS {Number(snapshot.rs_mansfield_pct) > 0 ? '+' : ''}{Number(snapshot.rs_mansfield_pct).toFixed(1)}%
                </Badge>
              )}
              {(() => {
                const tdParts: string[] = [];
                if (snapshot.td_buy_complete) tdParts.push('Buy 9');
                else if (snapshot.td_buy_setup >= 7) tdParts.push(`B${snapshot.td_buy_setup}`);
                if (snapshot.td_sell_complete) tdParts.push('Sell 9');
                else if (snapshot.td_sell_setup >= 7) tdParts.push(`S${snapshot.td_sell_setup}`);
                if (snapshot.td_buy_countdown >= 12) tdParts.push(`BC${snapshot.td_buy_countdown}`);
                if (snapshot.td_sell_countdown >= 12) tdParts.push(`SC${snapshot.td_sell_countdown}`);
                return tdParts.length > 0 ? (
                  <Badge colorPalette={tdParts[0].startsWith('B') ? 'green' : 'red'} variant="outline" size="sm">
                    TD {tdParts.join(' ')}
                  </Badge>
                ) : null;
              })()}
              {((snapshot.gaps_unfilled_up ?? 0) > 0 || (snapshot.gaps_unfilled_down ?? 0) > 0) && (
                <Badge variant="outline" size="sm">
                  Gaps {snapshot.gaps_unfilled_up ?? 0}↑ {snapshot.gaps_unfilled_down ?? 0}↓
                </Badge>
              )}
              {snapshot.next_earnings && (
                <Badge colorPalette="purple" variant="outline" size="sm">
                  Earnings {new Date(snapshot.next_earnings).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                </Badge>
              )}
            </Box>
          )}

          {/* Chart */}
          <CardRoot borderWidth="1px" borderColor="border.subtle" bg="bg.card">
            <CardHeader pb={2}>
              <Box display="flex" justifyContent="space-between" alignItems="center" flexWrap="wrap" gap={3}>
                <Text fontWeight="bold">{selectedSymbol || '—'}</Text>
                <Box display="flex" gap={3} alignItems="center" flexWrap="wrap">
                  <Badge>Live</Badge>
                  <Box display="flex" gap={2} alignItems="center">
                    <Text fontSize="xs" color="fg.muted">Advanced</Text>
                    <Button size="xs" variant={showAdvanced ? 'solid' : 'outline'} onClick={() => setShowAdvanced((v: boolean) => !v)}>
                      {showAdvanced ? 'On' : 'Off'}
                    </Button>
                  </Box>
                  <Box display="flex" gap={2} alignItems="center" opacity={showAdvanced ? 0.4 : 1}>
                    <Text fontSize="xs" color="fg.muted">Range</Text>
                    <Button size="xs" disabled={showAdvanced} variant={period === '6mo' ? 'solid' : 'outline'} onClick={() => { setPeriod('6mo'); setZoomYears(0.5); }}>6m</Button>
                    <Button size="xs" disabled={showAdvanced} variant={period === '1y' ? 'solid' : 'outline'} onClick={() => { setPeriod('1y'); setZoomYears(1); }}>1y</Button>
                    <Button size="xs" disabled={showAdvanced} variant={period === '3y' ? 'solid' : 'outline'} onClick={() => { setPeriod('3y'); setZoomYears(3); }}>3y</Button>
                    <Button size="xs" disabled={showAdvanced} variant={period === '5y' ? 'solid' : 'outline'} onClick={() => { setPeriod('5y'); setZoomYears(5); }}>5y</Button>
                    <Button size="xs" disabled={showAdvanced} variant={period === 'max' ? 'solid' : 'outline'} onClick={() => { setPeriod('max'); setZoomYears('all'); }}>All</Button>
                  </Box>
                  <Box display="flex" gap={2} alignItems="center">
                    <Text fontSize="xs" color="fg.muted">Line</Text>
                    <Button size="xs" variant={showLine ? 'solid' : 'outline'} onClick={() => setShowLine((v: boolean) => !v)}>
                      {showLine ? 'On' : 'Off'}
                    </Button>
                  </Box>
                </Box>
              </Box>
              {/* Event type toggles */}
              {!showAdvanced && (
                <Box display="flex" gap={2} alignItems="center" flexWrap="wrap" mt={1}>
                  <Text fontSize="xs" color="fg.muted">Events</Text>
                  {EVENT_TOGGLE_CONFIG.map(({ type, label, colorPalette }) => (
                    <Button
                      key={type}
                      size="xs"
                      colorPalette={enabledEvents.has(type) ? colorPalette : undefined}
                      variant={enabledEvents.has(type) ? 'solid' : 'outline'}
                      onClick={() => toggleEventType(type)}
                    >
                      {label}
                    </Button>
                  ))}
                </Box>
              )}
              {!showAdvanced && (
                <Box display="flex" gap={2} alignItems="center" flexWrap="wrap" mt={1}>
                  <Text fontSize="xs" color="fg.muted">Indicators</Text>
                  <Button size="xs" variant={indicators.trendLines ? 'solid' : 'outline'} onClick={() => toggleIndicator('trendLines')}>Trend Lines</Button>
                  <Button size="xs" variant={indicators.gaps ? 'solid' : 'outline'} onClick={() => toggleIndicator('gaps')}>Gaps</Button>
                  <Button size="xs" variant={indicators.tdSequential ? 'solid' : 'outline'} onClick={() => toggleIndicator('tdSequential')}>TD Seq</Button>
                  <Button size="xs" variant={indicators.emas ? 'solid' : 'outline'} onClick={() => toggleIndicator('emas')}>EMAs</Button>
                  <Button size="xs" variant={indicators.stage ? 'solid' : 'outline'} onClick={() => toggleIndicator('stage')}>Stage</Button>
                  <Button size="xs" variant={indicators.supportResistance ? 'solid' : 'outline'} onClick={() => toggleIndicator('supportResistance')}>S/R</Button>
                </Box>
              )}
              {lockedDaySec && (
                <Box mt={2} display="flex" gap={3} alignItems="center" flexWrap="wrap">
                  <Badge colorPalette="purple">Pinned</Badge>
                  <Text fontSize="sm">{new Date(lockedDaySec * 1000).toISOString().slice(0, 10)}</Text>
                  <Button size="xs" variant="outline" onClick={() => setLockedDaySec(null)}>
                    Clear
                  </Button>
                </Box>
              )}
            </CardHeader>
            <CardBody>
              {selectedSymbol ? (
                showAdvanced ? (
                  <TradingViewChart
                    symbol={selectedSymbol}
                    height={chartHeight}
                    showHeader={false}
                    theme="dark"
                  />
                ) : barsError && !barsQuery.isLoading ? (
                  <Box h={`${chartHeight}px`} display="flex" flexDirection="column" alignItems="center" justifyContent="center" gap={3}>
                    <Text color="fg.muted">No price data available for {selectedSymbol}</Text>
                    <Button size="sm" colorPalette="brand" variant="outline" onClick={() => setShowAdvanced(true)}>
                      Open TradingView Chart
                    </Button>
                  </Box>
                ) : (
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
                  />
                )
              ) : <Box h={`${chartHeight}px`} />}
            </CardBody>
          </CardRoot>

          <Box display="grid" gridTemplateColumns={{ base: '1fr', lg: '2fr 1fr' }} gap={4}>
            {/* Tax Lots panel */}
            <CardRoot borderWidth="1px" borderColor="border.subtle" maxH={lotEditMode ? { base: '70vh', md: '520px' } : { base: '50vh', md: '400px' }} overflow="hidden" bg="bg.card">
              <CardHeader pb={2}>
                <Box display="flex" justifyContent="space-between" alignItems="center">
                  <Box display="flex" gap={2} alignItems="center">
                    <Text fontWeight="bold">Tax Lots</Text>
                    <Badge variant="outline">{lots.length}</Badge>
                  </Box>
                  <IconButton
                    size="2xs"
                    variant={lotEditMode ? 'solid' : 'ghost'}
                    colorPalette={lotEditMode ? 'purple' : 'gray'}
                    aria-label={lotEditMode ? 'Lock tax lots' : 'Unlock to add/edit lots'}
                    onClick={() => { setLotEditMode(v => !v); setEditingLotId(null); setLotForm(emptyLotForm); }}
                  >
                    {lotEditMode ? <FiUnlock /> : <FiLock />}
                  </IconButton>
                </Box>
              </CardHeader>
              <CardBody p={0}>
                <TableScrollArea maxH={{ base: '250px', md: '340px' }}>
                  <TableRoot size="sm">
                    <TableHeader>
                      <TableRow>
                        <TableColumnHeader>Date</TableColumnHeader>
                        <TableColumnHeader>Type</TableColumnHeader>
                        <TableColumnHeader textAlign="end">Days</TableColumnHeader>
                        <TableColumnHeader textAlign="end">Shares</TableColumnHeader>
                        <TableColumnHeader textAlign="end">Cost/Share</TableColumnHeader>
                        <TableColumnHeader textAlign="end">Value</TableColumnHeader>
                        <TableColumnHeader textAlign="end">P/L</TableColumnHeader>
                        <TableColumnHeader w="28px" />
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {lots.length === 0 && (
                        <TableRow>
                          <TableCell colSpan={8}>
                            <Text fontSize="xs" color="fg.muted" textAlign="center" py={4}>
                              {lotsQuery.isLoading ? 'Loading tax lots…' : `No tax lots synced for ${selectedSymbol ?? 'this symbol'}. Sync your brokerage to populate.`}
                            </Text>
                          </TableCell>
                        </TableRow>
                      )}
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
                          return (
                            <TableRow
                              id={`lot-${lotDay}-${idx}`}
                              key={`lot-${l.id || idx}`}
                              bg={focused ? 'bg.muted' : approachingLT ? (isDark ? 'yellow.950' : 'yellow.50') : undefined}
                              css={{ '& .sell-icon': { opacity: 0, transition: 'opacity 0.15s' }, '&:hover .sell-icon': { opacity: 1 } }}
                            >
                              <TableCell>{fmtDate(l.purchase_date)}</TableCell>
                              <TableCell>
                                <Box display="flex" gap={1}>
                                  <Badge size="sm" colorPalette={isLT ? 'green' : approachingLT ? 'yellow' : 'gray'}>
                                    {isLT ? 'LT' : 'ST'}
                                  </Badge>
                                  {l.source && (
                                    <Badge size="sm" variant="outline" colorPalette={l.source === 'OFFICIAL_STATEMENT' || l.source === 'official_statement' ? 'blue' : l.source === 'MANUAL_ENTRY' || l.source === 'manual_entry' ? 'purple' : 'gray'}>
                                      {l.source === 'OFFICIAL_STATEMENT' || l.source === 'official_statement' ? 'Official' : l.source === 'MANUAL_ENTRY' || l.source === 'manual_entry' ? 'Manual' : 'Est'}
                                    </Badge>
                                  )}
                                </Box>
                              </TableCell>
                              <TableCell textAlign="end">
                                <Text fontSize="xs" color={approachingLT ? (isDark ? 'yellow.400' : 'yellow.700') : 'fg.muted'}>
                                  {daysHeld}d
                                </Text>
                              </TableCell>
                              <TableCell textAlign="end">{sh.toLocaleString()}</TableCell>
                              <TableCell textAlign="end">{cps ? formatMoney(cps, currency) : '-'}</TableCell>
                              <TableCell textAlign="end">{val ? formatMoney(val, currency, { maximumFractionDigits: 0 }) : '-'}</TableCell>
                              <TableCell textAlign="end" color={pnl >= 0 ? 'fg.success' : 'fg.error'}>
                                {pnl ? formatMoney(pnl, currency, { maximumFractionDigits: 0 }) : '-'}
                              </TableCell>
                              <TableCell w={lotEditMode ? '56px' : '28px'} p={0}>
                                {lotEditMode && (l.source === 'MANUAL_ENTRY' || l.source === 'manual_entry') ? (
                                  <Box display="flex" gap={0}>
                                    <IconButton
                                      size="2xs"
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
                                      <FiEdit2 />
                                    </IconButton>
                                    <IconButton
                                      size="2xs"
                                      variant="ghost"
                                      colorPalette="red"
                                      aria-label="Delete lot"
                                      onClick={() => l.id && handleLotDelete(l.id)}
                                    >
                                      <FiTrash2 />
                                    </IconButton>
                                  </Box>
                                ) : (
                                  <IconButton
                                    className="sell-icon"
                                    size="2xs"
                                    variant="ghost"
                                    colorPalette="red"
                                    aria-label={`Sell ${sh} shares from lot`}
                                    onClick={() => setTradeTarget({
                                      symbol: selectedSymbol!,
                                      currentPrice: lastClose,
                                      sharesHeld: sh,
                                      averageCost: cps || undefined,
                                      positionId: selectedHolding?.id,
                                    })}
                                  >
                                    <FiMinusCircle />
                                  </IconButton>
                                )}
                              </TableCell>
                            </TableRow>
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
                          <TableRow bg="bg.subtle">
                            <TableCell colSpan={3}>
                              <Text fontSize="xs" fontWeight="semibold">Total</Text>
                            </TableCell>
                            <TableCell textAlign="end">
                              <Text fontSize="xs" fontWeight="semibold">{totals.shares.toLocaleString()}</Text>
                            </TableCell>
                            <TableCell textAlign="end">
                              <Text fontSize="xs" fontWeight="semibold">{formatMoney(totals.cost / (totals.shares || 1), currency)}</Text>
                            </TableCell>
                            <TableCell textAlign="end">
                              <Text fontSize="xs" fontWeight="semibold">{formatMoney(totals.value, currency, { maximumFractionDigits: 0 })}</Text>
                            </TableCell>
                            <TableCell textAlign="end">
                              <Text fontSize="xs" fontWeight="semibold" color={totalPnl >= 0 ? 'fg.success' : 'fg.error'}>
                                {formatMoney(totalPnl, currency, { maximumFractionDigits: 0 })}
                              </Text>
                            </TableCell>
                            <TableCell w="28px" />
                          </TableRow>
                        );
                      })()}
                    </TableBody>
                  </TableRoot>
                </TableScrollArea>
                {lotEditMode && (
                  <Box px={3} py={2} borderTopWidth="1px" borderColor="border.subtle" bg="bg.subtle">
                    <Text fontSize="xs" fontWeight="semibold" mb={1} color="fg.muted">
                      {editingLotId ? 'Edit Lot' : 'Add Manual Lot'}
                    </Text>
                    <Box display="flex" gap={2} alignItems="end" flexWrap="wrap">
                      <Box>
                        <Text fontSize="2xs" color="fg.muted">Date</Text>
                        <Input
                          size="xs"
                          type="date"
                          value={lotForm.date}
                          onChange={(e: React.ChangeEvent<HTMLInputElement>) => setLotForm(f => ({ ...f, date: e.target.value }))}
                          max={new Date().toISOString().slice(0, 10)}
                          w="130px"
                        />
                      </Box>
                      <Box>
                        <Text fontSize="2xs" color="fg.muted">Shares</Text>
                        <Input
                          size="xs"
                          type="number"
                          placeholder="Qty"
                          value={lotForm.qty}
                          onChange={(e: React.ChangeEvent<HTMLInputElement>) => setLotForm(f => ({ ...f, qty: e.target.value }))}
                          min={0}
                          step="any"
                          w="80px"
                        />
                      </Box>
                      <Box>
                        <Text fontSize="2xs" color="fg.muted">Cost/Share</Text>
                        <Input
                          size="xs"
                          type="number"
                          placeholder="Price"
                          value={lotForm.costPerShare}
                          onChange={(e: React.ChangeEvent<HTMLInputElement>) => setLotForm(f => ({ ...f, costPerShare: e.target.value }))}
                          min={0}
                          step="any"
                          w="90px"
                        />
                      </Box>
                      <Button
                        size="xs"
                        colorPalette="purple"
                        disabled={lotSaving || !lotForm.date || !lotForm.qty || !lotForm.costPerShare}
                        onClick={handleLotSave}
                      >
                        {lotSaving ? '...' : editingLotId ? 'Update' : 'Save'}
                      </Button>
                      {editingLotId && (
                        <Button
                          size="xs"
                          variant="ghost"
                          onClick={() => { setEditingLotId(null); setLotForm(emptyLotForm); }}
                        >
                          Cancel
                        </Button>
                      )}
                    </Box>
                  </Box>
                )}
              </CardBody>
            </CardRoot>

            {/* Dividends */}
            <CardRoot borderWidth="1px" borderColor="border.subtle" maxH={{ base: '50vh', md: '400px' }} overflow="hidden" bg="bg.card">
              <CardHeader pb={2}>
                <Box display="flex" justifyContent="space-between" alignItems="center">
                  <Text fontWeight="bold">Dividends</Text>
                  <Box display="flex" gap={2} alignItems="center">
                    {symbolDividends.length > 0 && (
                      <Text fontSize="xs" color="fg.muted">
                        Total {formatMoney(symbolDividends.reduce((s, r: ActivityRow) => s + Number(r.amount || r.net_amount || 0), 0), currency)}
                      </Text>
                    )}
                    <Badge variant="outline">{symbolDividends.length}</Badge>
                  </Box>
                </Box>
              </CardHeader>
              <CardBody p={0}>
                <TableScrollArea maxH={{ base: '250px', md: '340px' }}>
                  <TableRoot size="sm">
                    <TableHeader>
                      <TableRow>
                        <TableColumnHeader>Date</TableColumnHeader>
                        <TableColumnHeader textAlign="end">Amount</TableColumnHeader>
                        <TableColumnHeader textAlign="end">Per Share</TableColumnHeader>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {symbolDividends.length === 0 && (
                        <TableRow>
                          <TableCell colSpan={3}>
                            <Text fontSize="xs" color="fg.muted" textAlign="center" py={4}>
                              No dividend history for {selectedSymbol ?? 'this symbol'}.
                            </Text>
                          </TableCell>
                        </TableRow>
                      )}
                      {symbolDividends.map((r: ActivityRow, idx: number) => {
                        const day = (r.ts || '').slice(0, 10);
                        const hoverDay = focusedDaySec ? new Date(focusedDaySec * 1000).toISOString().slice(0, 10) : '';
                        const focused = hoverDay && day === hoverDay;
                        const amt = Number(r.amount || r.net_amount || 0);
                        const qty = Number(r.quantity || 0);
                        const perShare = qty > 0 ? amt / qty : null;
                        return (
                          <TableRow id={`div-${day}-${idx}`} key={`div-${r.external_id || idx}`} bg={focused ? 'bg.muted' : undefined}>
                            <TableCell>{fmtDate(r.ts)}</TableCell>
                            <TableCell textAlign="end">{amt ? formatMoney(amt, currency) : '-'}</TableCell>
                            <TableCell textAlign="end" color="fg.muted">{perShare != null ? formatMoney(perShare, currency, { minimumFractionDigits: 2, maximumFractionDigits: 4 }) : '-'}</TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </TableRoot>
                </TableScrollArea>
              </CardBody>
            </CardRoot>
          </Box>
        </VStack>
      </Flex>

      {tradeTarget && (
        <TradeModal
          isOpen={!!tradeTarget}
          symbol={tradeTarget.symbol}
          currentPrice={tradeTarget.currentPrice}
          sharesHeld={tradeTarget.sharesHeld}
          averageCost={tradeTarget.averageCost}
          positionId={tradeTarget.positionId}
          onClose={() => setTradeTarget(null)}
        />
      )}
    </VStack>
  );
};

export default PortfolioWorkspace;
