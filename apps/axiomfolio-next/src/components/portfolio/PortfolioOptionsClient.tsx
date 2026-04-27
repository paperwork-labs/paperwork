"use client";

import React, { useState, useMemo } from 'react';
import {
  ChevronDown,
  ChevronRight,
  LayoutGrid,
  Link2,
  List,
  Loader2,
  Plug,
  RefreshCw,
  Wifi,
  WifiOff,
} from 'lucide-react';
import Link from 'next/link';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import { semanticTextColorClass } from '@/lib/semantic-text-color';
import { useQuery } from '@tanstack/react-query';
import { ChartContext, SymbolLink, ChartSlidePanel } from '@/components/market/SymbolChartUI';
import StatCard from '@/components/shared/StatCard';
import { StatCardSkeleton, TableSkeleton } from '@/components/shared/Skeleton';
import PnlText from '@/components/shared/PnlText';
import PageHeader from '@/components/ui/PageHeader';
import { BrokerBadge } from '@/components/shared/BrokerBadge';
import { useAccountFilter } from '@/hooks/useAccountFilter';
import SortableTable from '@/components/SortableTable';
import type { Column, FilterGroup } from '@/components/SortableTable';
import { useOptions, usePortfolioSync, usePortfolioAccounts } from '@/hooks/usePortfolio';
import { useUserPreferences } from '@/hooks/useUserPreferences';
import { useAccountContext } from '@/context/AccountContext';
import { useAuthOptional } from '@/context/AuthContext';
import { isPlatformAdminRole } from '@/utils/userRole';
import { BarChart, Bar, XAxis, YAxis, Tooltip as RechartsTooltip, ResponsiveContainer, LineChart, Line } from 'recharts';
import { formatMoney, formatDateShort } from '@/utils/format';
import { buildAccountsFromBroker } from '@/utils/portfolio';
import { detectStrategies } from '@/utils/optionStrategies';
import type { OptionPos, StrategyGroup } from '@/utils/optionStrategies';
import type { AccountData, FilterableItem } from '@/hooks/useAccountFilter';
import api from '@/services/api';

/** Shape returned by `/portfolio/options/chain/sources` — broker-agnostic. */
type ChainSource = {
  name: string;
  label: string;
  available: boolean;
  reason?: string;
  kind: 'broker' | 'provider';
};

const EXPIRING_SOON_DAYS = 7;

type TabId = 'positions' | 'chain' | 'pnl' | 'analytics' | 'history';
type PosView = 'card' | 'table';

/* ------------------------------------------------------------------ */
/* Helpers                                                             */
/* ------------------------------------------------------------------ */

function moneyness(pos: OptionPos): 'ITM' | 'OTM' | 'ATM' | null {
  const u = Number(pos.underlying_price ?? 0);
  if (!u || !pos.strike_price) return null;
  const pct = Math.abs(u - pos.strike_price) / pos.strike_price;
  if (pct <= 0.02) return 'ATM';
  const isCall = (pos.option_type || '').toUpperCase() === 'CALL';
  if (isCall) return u > pos.strike_price ? 'ITM' : 'OTM';
  return u < pos.strike_price ? 'ITM' : 'OTM';
}

function moneynessPct(pos: OptionPos): number | null {
  const u = Number(pos.underlying_price ?? 0);
  if (!u || !pos.strike_price) return null;
  return ((u - pos.strike_price) / pos.strike_price) * 100;
}

function moneynessBadgeClass(m: string): string {
  if (m === 'ITM') return 'bg-[rgb(var(--status-success)/0.15)] text-[rgb(var(--status-success)/1)] border-transparent';
  if (m === 'OTM') return 'bg-destructive/10 text-destructive border-transparent';
  return 'bg-amber-500/15 text-amber-800 dark:text-amber-300 border-transparent';
}


/* ------------------------------------------------------------------ */
/* Main Component                                                      */
/* ------------------------------------------------------------------ */

const PortfolioOptionsClient: React.FC = () => {
  const [chartSymbol, setChartSymbol] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabId>('positions');
  const [posView, setPosView] = useState<PosView>('card');
  const [chainSymbol, setChainSymbol] = useState('');
  const { selected } = useAccountContext();
  const { currency, timezone } = useUserPreferences();
  const optionsQuery = useOptions(selected === 'all' ? undefined : selected);
  const accountsQuery = usePortfolioAccounts();
  const syncMutation = usePortfolioSync();
  const auth = useAuthOptional();
  const isAdmin = isPlatformAdminRole(auth?.user?.role);

  const gatewayQuery = useQuery({
    queryKey: ['ibGatewayStatus'],
    queryFn: async () => {
      const res = await api.get('/portfolio/options/gateway-status');
      return res.data?.data ?? { connected: false, available: false };
    },
    staleTime: 30000,
    refetchInterval: 60000,
  });
  const gwConnected = gatewayQuery.data?.connected ?? false;

  const stocksQuery = useQuery({
    queryKey: ['portfolioStocks', selected],
    queryFn: async () => {
      const params = selected !== 'all' ? `?account_id=${selected}` : '';
      const res = await api.get(`/portfolio/stocks${params}`);
      return res.data?.data?.positions ?? [];
    },
    staleTime: 60000,
  });
  const stockPositions = useMemo(
    () =>
      (stocksQuery.data ?? []).map((s: any) => ({
        symbol: s.symbol,
        quantity: Number(s.quantity ?? 0),
      })),
    [stocksQuery.data],
  );

  const rawAccounts = accountsQuery.data ?? [];
  const accounts: AccountData[] = useMemo(
    () => buildAccountsFromBroker(rawAccounts ?? []),
    [rawAccounts],
  );

  const data = optionsQuery.data as { positions?: OptionPos[]; underlyings?: Record<string, { calls: OptionPos[]; puts: OptionPos[]; total_value: number; total_pnl: number }> } | undefined;
  const summaryData = optionsQuery.summaryData as { summary?: { total_market_value?: number; total_unrealized_pnl?: number; total_positions?: number; calls_count?: number; puts_count?: number; expiring_this_week?: number; avg_days_to_expiration?: number; net_delta?: number; net_theta?: number } } | undefined;

  const positions = data?.positions ?? [];
  const underlyings = data?.underlyings ?? {};
  const optionsFilterState = useAccountFilter(positions as FilterableItem[], accounts);
  const summary = summaryData?.summary ?? {};
  const totalValue = Number(summary.total_market_value ?? 0);
  const totalPnl = Number(summary.total_unrealized_pnl ?? 0);
  const totalPnlPct = totalValue ? (totalPnl / totalValue) * 100 : 0;
  const callsCount = Number(summary.calls_count ?? 0);
  const putsCount = Number(summary.puts_count ?? 0);
  const expiringSoon = Number(summary.expiring_this_week ?? 0);
  const avgDte = Number(summary.avg_days_to_expiration ?? 0);
  const netDelta = Number(summary.net_delta ?? 0);
  const netTheta = Number(summary.net_theta ?? 0);

  const netGamma = useMemo(() => positions.reduce((s, p) => s + Number(p.gamma ?? 0) * p.quantity, 0), [positions]);
  const netVega = useMemo(() => positions.reduce((s, p) => s + Number(p.vega ?? 0) * p.quantity, 0), [positions]);
  const totalRealizedPnl = useMemo(() => positions.reduce((s, p) => s + Number(p.realized_pnl ?? 0), 0), [positions]);
  const totalCommission = useMemo(() => positions.reduce((s, p) => s + Number(p.commission ?? 0), 0), [positions]);

  const openChart = (symbol: string) => setChartSymbol(symbol);

  const uniqueUnderlyings = useMemo(() => Object.keys(underlyings).sort(), [underlyings]);

  const strategies = useMemo(() => detectStrategies(positions, stockPositions), [positions, stockPositions]);

  return (
    <ChartContext.Provider value={openChart}>
      <div className="p-4">
        <div className="flex flex-col gap-4">
          <PageHeader
            title="Options"
            subtitle="Positions, chains, and P&L analysis"
            rightContent={
              <div className="flex flex-wrap items-center gap-3">
                <GatewayStatusBadge connected={gwConnected} loading={gatewayQuery.isPending} />
                <Button size="sm" variant="outline" onClick={() => syncMutation.mutate()} disabled={syncMutation.isPending}>
                  {syncMutation.isPending ? (
                    <Loader2 className="size-4 animate-spin" aria-hidden />
                  ) : (
                    <RefreshCw className="size-4" aria-hidden />
                  )}
                  Sync
                </Button>
              </div>
            }
          />

          <div className="flex flex-wrap gap-3">
            <StatCard
              label="Total Value"
              value={formatMoney(totalValue, currency, { maximumFractionDigits: 0 })}
            />
            <StatCard label="Calls" value={callsCount} />
            <StatCard label="Puts" value={putsCount} />
            <StatCard
              label="Expiring Soon"
              value={expiringSoon}
              sub={expiringSoon > 0 ? `within ${EXPIRING_SOON_DAYS} days` : undefined}
              color={expiringSoon > 0 ? 'status.warning' : undefined}
            />
            <StatCard label="Avg DTE" value={avgDte} sub="days" />
            <StatCard
              label="Total P&L"
              value={formatMoney(totalPnl, currency)}
              sub={totalPnlPct !== 0 ? `${totalPnlPct >= 0 ? '+' : ''}${totalPnlPct.toFixed(1)}%` : undefined}
              color={totalPnl >= 0 ? 'status.success' : 'status.danger'}
            />
            <StatCard
              label="Realized P&L"
              value={formatMoney(totalRealizedPnl, currency)}
              color={totalRealizedPnl >= 0 ? 'status.success' : 'status.danger'}
            />
            <StatCard
              label="Commission"
              value={formatMoney(Math.abs(totalCommission), currency)}
              color="status.danger"
            />
            <StatCard label="Net Delta" value={netDelta.toFixed(2)} />
            <StatCard
              label="Daily Theta"
              value={formatMoney(netTheta, currency)}
              color={netTheta < 0 ? 'status.danger' : 'status.success'}
            />
            <StatCard label="Net Gamma" value={netGamma.toFixed(3)} />
            <StatCard label="Net Vega" value={netVega.toFixed(2)} />
          </div>

          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border pb-0">
            <div className="flex flex-wrap gap-1">
              {(['positions', 'chain', 'pnl', 'analytics', 'history'] as TabId[]).map((tab) => {
                const isActive = activeTab === tab;
                return (
                  <Button
                    key={tab}
                    size="sm"
                    variant={isActive ? 'default' : 'ghost'}
                    className={cn(
                      'rounded-b-none capitalize',
                      isActive && 'bg-amber-500 font-medium text-white hover:bg-amber-400',
                    )}
                    onClick={() => setActiveTab(tab)}
                  >
                    {tab === 'pnl'
                      ? 'P&L'
                      : tab === 'chain'
                        ? 'Option Chain'
                        : tab === 'analytics'
                          ? 'Analytics'
                          : tab === 'history'
                            ? 'History'
                            : 'Positions'}
                  </Button>
                );
              })}
            </div>
            {activeTab === 'positions' ? (
              <div className="flex gap-1">
                <Button
                  size="xs"
                  variant={posView === 'card' ? 'default' : 'ghost'}
                  onClick={() => setPosView('card')}
                  aria-label="Card view"
                  aria-pressed={posView === 'card'}
                >
                  <LayoutGrid className="size-4" />
                </Button>
                <Button
                  size="xs"
                  variant={posView === 'table' ? 'default' : 'ghost'}
                  onClick={() => setPosView('table')}
                  aria-label="Table view"
                  aria-pressed={posView === 'table'}
                >
                  <List className="size-4" />
                </Button>
              </div>
            ) : null}
          </div>

          {/* Tab content */}
          {activeTab === 'positions' && (optionsQuery.isPending || accountsQuery.isPending ? (
            <TableSkeleton rows={5} cols={4} />
          ) : (optionsQuery.error || accountsQuery.error) ? (
            <OptionsErrorCard
              error={(optionsQuery.error || accountsQuery.error) as unknown}
              isAdmin={isAdmin}
              onRetry={() => {
                optionsQuery.portfolio.refetch();
                optionsQuery.summary.refetch();
                accountsQuery.refetch();
              }}
            />
          ) : (() => {
                const typed = optionsFilterState.filteredData as OptionPos[];
                const filteredSet = new Set(typed.map(p => p.id));
                const filteredUnderlyings: Record<string, { calls: OptionPos[]; puts: OptionPos[]; total_value: number; total_pnl: number }> = {};
                for (const [sym, grp] of Object.entries(underlyings)) {
                  const fc = grp.calls.filter(p => filteredSet.has(p.id));
                  const fp = grp.puts.filter(p => filteredSet.has(p.id));
                  if (fc.length + fp.length > 0) {
                    filteredUnderlyings[sym] = {
                      calls: fc,
                      puts: fp,
                      total_value: [...fc, ...fp].reduce((s, p) => s + Number(p.market_value ?? 0), 0),
                      total_pnl: [...fc, ...fp].reduce((s, p) => s + Number(p.unrealized_pnl ?? 0), 0),
                    };
                  }
                }

                if (posView === 'table') {
                  return (
                    <PositionsTableView
                      positions={typed}
                      currency={currency}
                      gwConnected={gwConnected}
                    />
                  );
                }

                return (
                  <>
                    {/* Strategy groups */}
                    {strategies.length > 0 ? (
                      <div className="mb-3 flex flex-col gap-3">
                        <p className="text-sm font-bold text-muted-foreground">Detected Strategies</p>
                        {strategies.map((sg, idx) => (
                          <Card key={idx} className="gap-0 border-primary/30 py-0">
                            <CardContent className="py-3">
                              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                                <div className="flex flex-wrap items-center gap-2">
                                  <Badge variant="secondary" className="bg-violet-500/15 text-violet-700 dark:text-violet-300">
                                    {sg.label}
                                  </Badge>
                                  <span className="text-xs text-muted-foreground">
                                    {sg.positions[0]?.underlying_symbol} {sg.positions[0]?.expiration_date?.slice(0, 10)}
                                  </span>
                                  {sg.creditDebit ? (
                                    <Badge
                                      variant="outline"
                                      className={cn(
                                        sg.creditDebit === 'credit' && 'border-[rgb(var(--status-success)/1)] text-[rgb(var(--status-success)/1)]',
                                        sg.creditDebit === 'debit' && 'border-destructive text-destructive',
                                        sg.creditDebit !== 'credit' &&
                                          sg.creditDebit !== 'debit' &&
                                          'text-muted-foreground',
                                      )}
                                    >
                                      {sg.creditDebit === 'credit' ? 'Credit' : sg.creditDebit === 'debit' ? 'Debit' : 'Even'}
                                      {sg.netPremium ? ` ${formatMoney(Math.abs(sg.netPremium), currency)}` : ''}
                                    </Badge>
                                  ) : null}
                                </div>
                                <PnlText value={sg.netPnl} format="currency" fontSize="sm" currency={currency} />
                              </div>
                              <div className="mb-2 flex flex-wrap gap-4 text-xs text-muted-foreground">
                                <span>Delta {sg.combinedGreeks.delta.toFixed(2)}</span>
                                <span>Theta {sg.combinedGreeks.theta.toFixed(2)}</span>
                                <span>Gamma {sg.combinedGreeks.gamma.toFixed(3)}</span>
                                <span>Vega {sg.combinedGreeks.vega.toFixed(2)}</span>
                                {sg.maxProfit != null ? (
                                  <span className="text-[rgb(var(--status-success)/1)]">
                                    Max Profit {formatMoney(sg.maxProfit, currency)}
                                  </span>
                                ) : null}
                                {sg.maxLoss != null ? (
                                  <span className="text-[rgb(var(--status-danger)/1)]">
                                    Max Loss {formatMoney(sg.maxLoss, currency)}
                                  </span>
                                ) : null}
                                {sg.breakevens.length > 0 ? (
                                  <span>
                                    B/E: {sg.breakevens.map((b) => b.toFixed(2)).join(', ')}
                                    {sg.positions[0]?.underlying_price
                                      ? ` (${((sg.breakevens[0] / Number(sg.positions[0].underlying_price) - 1) * 100).toFixed(1)}%)`
                                      : ''}
                                  </span>
                                ) : null}
                              </div>
                              {sg.maxProfit != null && sg.maxProfit > 0 && sg.netPnl !== 0 ? (
                                <div className="mb-2">
                                  <div className="mb-1 flex justify-between text-xs text-muted-foreground">
                                    <span>P/L Progress</span>
                                    <span>
                                      {Math.min(100, Math.max(-100, (sg.netPnl / sg.maxProfit) * 100)).toFixed(0)}% of max profit
                                    </span>
                                  </div>
                                  <div className="h-1 w-full overflow-hidden rounded-full bg-muted">
                                    <div
                                      className={cn('h-full rounded-full transition-[width] duration-300', sg.netPnl >= 0 ? 'bg-green-600' : 'bg-red-600')}
                                      style={{ width: `${Math.min(100, Math.abs(sg.netPnl / sg.maxProfit) * 100)}%` }}
                                    />
                                  </div>
                                </div>
                              ) : null}
                              <div className="flex flex-col gap-1">
                                {sg.positions.map((pos) => (
                                  <PositionRow key={pos.id} pos={pos} currency={currency} gwConnected={gwConnected} />
                                ))}
                              </div>
                            </CardContent>
                          </Card>
                        ))}
                      </div>
                    ) : null}

                    {Object.keys(filteredUnderlyings).length === 0 ? (
                      <Card className="gap-0 py-0">
                        <CardContent>
                          <p className="text-muted-foreground">
                            {optionsQuery.isPending ? 'Loading...' : 'No options positions.'}
                          </p>
                        </CardContent>
                      </Card>
                    ) : (
                      <div className="flex flex-col gap-3">
                        {Object.entries(filteredUnderlyings).map(([sym, group]) => (
                          <UnderlyingGroup
                            key={sym}
                            symbol={sym}
                            group={group}
                            currency={currency}
                            openChart={openChart}
                            gwConnected={gwConnected}
                          />
                        ))}
                      </div>
                    )}
                  </>
                );
              })()
          )}

          {activeTab === 'chain' && (
            <OptionChainTab
              chainSymbol={chainSymbol}
              setChainSymbol={setChainSymbol}
              underlyingOptions={uniqueUnderlyings}
              positions={positions}
              isAdmin={isAdmin}
            />
          )}

          {activeTab === 'pnl' && (
            <PnlTab underlyings={underlyings} currency={currency} />
          )}

          {activeTab === 'analytics' && (
            <OptionsAnalyticsTab positions={positions} currency={currency} timezone={timezone} />
          )}

          {activeTab === 'history' && (
            <OptionsHistoryTab accountId={selected === 'all' ? undefined : selected} />
          )}
        </div>
      </div>
      <ChartSlidePanel symbol={chartSymbol} onClose={() => setChartSymbol(null)} />
    </ChartContext.Provider>
  );
};

/* ------------------------------------------------------------------ */
/* Gateway Status Badge                                                */
/* ------------------------------------------------------------------ */
const GatewayStatusBadge: React.FC<{ connected: boolean; loading: boolean }> = ({ connected, loading }) => (
  <Badge
    variant="secondary"
    className={cn(
      'flex items-center gap-1 px-2 py-1',
      !loading && connected && 'bg-[rgb(var(--status-success)/0.12)] text-[rgb(var(--status-success)/1)]',
    )}
  >
    {connected ? <Wifi className="size-3.5" aria-hidden /> : <WifiOff className="size-3.5" aria-hidden />}
    {loading ? 'Checking...' : connected ? 'Gateway Connected' : 'Gateway Offline'}
  </Badge>
);

/* ------------------------------------------------------------------ */
/* Positions Table View (SortableTable-based)                          */
/* ------------------------------------------------------------------ */
const positionColumns: Column<OptionPos>[] = [
  {
    key: 'underlying',
    header: 'Underlying',
    accessor: (p) => p.underlying_symbol,
    sortable: true,
    sortType: 'string',
    filterable: true,
    filterType: 'text',
    render: (_v, p) => (
      <div className="flex items-center gap-2">
        <SymbolLink symbol={p.underlying_symbol} />
        {(() => {
          const m = moneyness(p);
          return m ? (
            <Badge variant="secondary" className={moneynessBadgeClass(m)}>
              {m}
            </Badge>
          ) : null;
        })()}
      </div>
    ),
  },
  {
    key: 'broker',
    header: 'Broker',
    accessor: (p) => p.broker ?? '',
    sortable: true,
    sortType: 'string',
    filterable: true,
    filterType: 'select',
    filterOptions: [
      { label: 'Schwab', value: 'schwab' },
      { label: 'IBKR', value: 'ibkr' },
      { label: 'Tastytrade', value: 'tastytrade' },
    ],
    render: (_v, p) =>
      p.broker ? (
        <BrokerBadge broker={p.broker} accountNumber={p.account_number ?? null} />
      ) : (
        <span className="text-xs text-muted-foreground">—</span>
      ),
    width: '90px',
  },
  {
    key: 'type',
    header: 'Type',
    accessor: (p) => (p.option_type || '').toUpperCase(),
    sortable: true,
    sortType: 'string',
    filterable: true,
    filterType: 'select',
    filterOptions: [{ label: 'Call', value: 'CALL' }, { label: 'Put', value: 'PUT' }],
    render: (v) => (
      <Badge
        variant="secondary"
        className={
          v === 'CALL'
            ? 'bg-[rgb(var(--status-success)/0.15)] text-[rgb(var(--status-success)/1)]'
            : 'bg-destructive/10 text-destructive'
        }
      >
        {v}
      </Badge>
    ),
    width: '70px',
  },
  {
    key: 'strike',
    header: 'Strike',
    accessor: (p) => p.strike_price,
    sortable: true,
    sortType: 'number',
    isNumeric: true,
    render: (v) => <span className="font-mono">{Number(v).toFixed(2)}</span>,
    width: '80px',
  },
  {
    key: 'expiry',
    header: 'Expiry',
    accessor: (p) => p.expiration_date?.slice(0, 10) ?? '',
    sortable: true,
    sortType: 'date',
    render: (v) => <span className="text-xs">{v || '—'}</span>,
    width: '95px',
  },
  {
    key: 'dte',
    header: 'DTE',
    accessor: (p) => p.days_to_expiration ?? 0,
    sortable: true,
    sortType: 'number',
    isNumeric: true,
    render: (v) => {
      const dte = Number(v);
      const colorClass = cn(
        dte <= 3 && semanticTextColorClass('status.danger'),
        dte > 3 && dte <= 7 && semanticTextColorClass('status.warning'),
        dte > 7 && dte <= 30 && semanticTextColorClass('status.warning'),
        dte > 7 && dte <= 30 && 'opacity-80',
        dte > 30 && 'text-muted-foreground',
      );
      return (
        <div className="flex items-center gap-1">
          {dte <= 3 ? (
            <span
              className="size-1.5 animate-pulse rounded-full bg-[rgb(var(--status-danger)/1)]"
              aria-hidden
            />
          ) : null}
          <span className={cn('font-mono', colorClass, dte <= 7 && 'font-bold')}>{dte}d</span>
        </div>
      );
    },
    width: '70px',
  },
  {
    key: 'qty',
    header: 'Qty',
    accessor: (p) => p.quantity,
    sortable: true,
    sortType: 'number',
    isNumeric: true,
    render: (v) => {
      const q = Number(v);
      return (
        <span className={cn('font-mono', q < 0 ? 'text-[rgb(var(--status-danger)/1)]' : 'text-foreground')}>{q}</span>
      );
    },
    width: '55px',
  },
  {
    key: 'avgPrice',
    header: 'Avg Price',
    accessor: (p) => Number(p.average_open_price ?? 0),
    sortable: true,
    sortType: 'number',
    isNumeric: true,
    render: (v) => <span className="font-mono">{Number(v) ? Number(v).toFixed(2) : '—'}</span>,
    width: '80px',
  },
  {
    key: 'current',
    header: 'Current',
    accessor: (p) => Number(p.current_price ?? 0),
    sortable: true,
    sortType: 'number',
    isNumeric: true,
    render: (v) => <span className="font-mono">{Number(v) ? Number(v).toFixed(2) : '—'}</span>,
    width: '75px',
  },
  {
    key: 'value',
    header: 'Value',
    accessor: (p) => Number(p.market_value ?? 0),
    sortable: true,
    sortType: 'number',
    isNumeric: true,
    width: '90px',
  },
  {
    key: 'pnl',
    header: 'P&L',
    accessor: (p) => Number(p.unrealized_pnl ?? 0),
    sortable: true,
    sortType: 'number',
    isNumeric: true,
    render: (v) => <PnlText value={Number(v)} format="currency" fontSize="xs" />,
    width: '80px',
  },
  {
    key: 'pnlPct',
    header: 'P&L%',
    accessor: (p) => Number(p.unrealized_pnl_pct ?? 0),
    sortable: true,
    sortType: 'number',
    isNumeric: true,
    render: (v) => {
      const pct = Number(v);
      return (
        <span className={cn('text-xs', pct >= 0 ? 'text-[rgb(var(--status-success)/1)]' : 'text-[rgb(var(--status-danger)/1)]')}>
          {pct >= 0 ? '+' : ''}
          {pct.toFixed(1)}%
        </span>
      );
    },
    width: '65px',
  },
  {
    key: 'delta',
    header: 'Delta',
    accessor: (p) => Number(p.delta ?? 0),
    sortable: true,
    sortType: 'number',
    isNumeric: true,
    render: (v) => <span className="font-mono text-xs">{Number(v) ? Number(v).toFixed(2) : '—'}</span>,
    width: '60px',
  },
  {
    key: 'theta',
    header: 'Theta',
    accessor: (p) => Number(p.theta ?? 0),
    sortable: true,
    sortType: 'number',
    isNumeric: true,
    render: (v) => (
      <span
        className={cn(
          'font-mono text-xs',
          Number(v) < 0 ? 'text-[rgb(var(--status-danger)/1)]' : 'text-[rgb(var(--status-success)/1)]',
        )}
      >
        {Number(v) ? Number(v).toFixed(2) : '—'}
      </span>
    ),
    width: '60px',
  },
  {
    key: 'iv',
    header: 'IV',
    // G5: explicit absent vs numeric -- NEVER ?? 0. A missing IV is a
    // data-coverage signal ("provider returned nothing"), not the
    // number zero. Silently coercing to 0 used to hide ~40% of options
    // positions as fake "$0.00 IV" readings (R-IV01).
    accessor: (p) => {
      const v = p.implied_volatility;
      if (v === null || v === undefined) return null;
      const n = Number(v);
      return Number.isFinite(n) ? n : null;
    },
    sortable: true,
    sortType: 'number',
    isNumeric: true,
    render: (v) => {
      if (v === null || v === undefined) {
        return (
          <span
            className="font-mono text-xs text-muted-foreground"
            title="IV unavailable from provider"
            aria-label="Implied volatility unavailable"
          >
            —
          </span>
        );
      }
      const n = Number(v);
      if (!Number.isFinite(n)) {
        return (
          <span
            className="font-mono text-xs text-muted-foreground"
            title="IV unavailable from provider"
            aria-label="Implied volatility unavailable"
          >
            —
          </span>
        );
      }
      return <span className="font-mono text-xs">{`${(n * 100).toFixed(0)}%`}</span>;
    },
    width: '50px',
  },
  {
    key: 'realizedPnl',
    header: 'Realized',
    accessor: (p) => Number(p.realized_pnl ?? 0),
    sortable: true,
    sortType: 'number',
    isNumeric: true,
    render: (v) => {
      const val = Number(v);
      if (!val) return <span className="text-xs text-muted-foreground">—</span>;
      return (
        <span className={cn('text-xs', val >= 0 ? 'text-[rgb(var(--status-success)/1)]' : 'text-[rgb(var(--status-danger)/1)]')}>
          {val >= 0 ? '+' : ''}
          {val.toFixed(0)}
        </span>
      );
    },
    width: '70px',
  },
  {
    key: 'commission',
    header: 'Comm.',
    accessor: (p) => Number(p.commission ?? 0),
    sortable: true,
    sortType: 'number',
    isNumeric: true,
    render: (v) => {
      const val = Number(v);
      if (!val) return <span className="text-xs text-muted-foreground">—</span>;
      return <span className="text-xs text-[rgb(var(--status-danger)/1)]">{Math.abs(val).toFixed(2)}</span>;
    },
    width: '65px',
  },
];

const tableFilterPresets: Array<{ label: string; filters: FilterGroup }> = [
  {
    label: 'Expiring This Week',
    filters: {
      conjunction: 'AND',
      rules: [{ id: 'dte-soon', columnKey: 'dte', operator: 'lte', value: '7' }],
    },
  },
  {
    label: 'ITM Only',
    filters: {
      conjunction: 'AND',
      rules: [{ id: 'itm', columnKey: 'moneyness', operator: 'equals', value: 'ITM' }],
    },
  },
  {
    label: 'High Theta (>$5/day)',
    filters: {
      conjunction: 'AND',
      rules: [{ id: 'theta-high', columnKey: 'theta', operator: 'lt', value: '-5' }],
    },
  },
];

const PositionsTableView: React.FC<{ positions: OptionPos[]; currency: string; gwConnected: boolean }> = ({ positions, currency }) => {
  const fmtCols = useMemo(() => {
    return positionColumns.map(col => {
      if (col.key === 'value' && !col.render) {
        return {
          ...col,
          render: (v: any) => (
            <span className="font-mono text-xs">{formatMoney(Number(v), currency, { maximumFractionDigits: 0 })}</span>
          ),
        };
      }
      if (col.key === 'pnl' && col.render) {
        return {
          ...col,
          render: (v: any) => <PnlText value={Number(v)} format="currency" fontSize="xs" currency={currency} />,
        };
      }
      return col;
    });
  }, [currency]);

  return (
    <SortableTable
      data={positions}
      columns={fmtCols}
      defaultSortBy="dte"
      defaultSortOrder="asc"
      size="sm"
      maxHeight="70vh"
      filtersEnabled
      filterPresets={tableFilterPresets}
      emptyMessage="No options positions."
    />
  );
};

/* ------------------------------------------------------------------ */
/* Underlying Group (Card View)                                        */
/* ------------------------------------------------------------------ */
const UnderlyingGroup: React.FC<{
  symbol: string;
  group: { calls: OptionPos[]; puts: OptionPos[]; total_value: number; total_pnl: number };
  currency: string;
  openChart: (s: string) => void;
  gwConnected: boolean;
}> = ({ symbol, group, currency, gwConnected }) => {
  const [open, setOpen] = useState(true);
  const allPositions = [...group.calls, ...group.puts];
  const totalPnl = group.total_pnl ?? 0;

  const grpDelta = allPositions.reduce((s, p) => s + Number(p.delta ?? 0) * p.quantity, 0);
  const grpRealizedPnl = allPositions.reduce((s, p) => s + Number(p.realized_pnl ?? 0), 0);

  return (
    <Card className="gap-0 py-0">
      <CardContent>
        <button
          type="button"
          className="flex w-full cursor-pointer items-center justify-between gap-2 rounded-md p-1 text-left hover:bg-muted/60"
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
        >
          <div className="flex flex-wrap items-center gap-2">
            {open ? <ChevronDown className="size-4 shrink-0" aria-hidden /> : <ChevronRight className="size-4 shrink-0" aria-hidden />}
            <SymbolLink symbol={symbol} />
            <Badge variant="secondary">{allPositions.length} pos</Badge>
            {grpRealizedPnl !== 0 ? (
              <Badge
                variant="outline"
                className={
                  grpRealizedPnl >= 0
                    ? 'border-[rgb(var(--status-success)/1)] text-[rgb(var(--status-success)/1)]'
                    : 'border-destructive text-destructive'
                }
              >
                Realized {grpRealizedPnl >= 0 ? '+' : ''}
                {grpRealizedPnl.toFixed(0)}
              </Badge>
            ) : null}
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-xs text-muted-foreground">D {grpDelta.toFixed(2)}</span>
            <span className="text-sm text-muted-foreground">{formatMoney(group.total_value, currency)}</span>
            <PnlText value={totalPnl} format="currency" currency={currency} />
          </div>
        </button>
        {open ? (
          <div className="mt-3 flex flex-col gap-1">
            {allPositions.map((pos) => (
              <PositionRow key={pos.id} pos={pos} currency={currency} gwConnected={gwConnected} />
            ))}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
};

/* ------------------------------------------------------------------ */
/* Position Row (enhanced)                                             */
/* ------------------------------------------------------------------ */
const PositionRow: React.FC<{ pos: OptionPos; currency: string; gwConnected: boolean }> = ({ pos, currency, gwConnected }) => {
  const isShort = pos.quantity < 0;
  const qty = Math.abs(pos.quantity);
  const hasGreeks = pos.delta != null || pos.theta != null;
  const dte = pos.days_to_expiration ?? 0;
  const dtePct = Math.min(100, Math.max(0, (dte / 90) * 100));
  const dteBarClass =
    dte <= 3
      ? 'bg-[rgb(var(--status-danger)/1)]'
      : dte <= 7
        ? 'bg-[rgb(var(--status-warning)/1)]'
        : dte > 30
          ? 'bg-[rgb(var(--status-success)/1)]'
          : 'bg-[rgb(var(--status-warning)/0.5)]';
  const m = moneyness(pos);
  const mPct = moneynessPct(pos);

  return (
    <div className="border-b border-border px-2 py-2 last:border-b-0 hover:bg-muted/50">
      <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
        <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2">
          <Badge
            variant="secondary"
            className={cn(
              'shrink-0',
              isShort ? 'bg-destructive/10 text-destructive' : 'bg-[rgb(var(--status-success)/0.15)] text-[rgb(var(--status-success)/1)]',
            )}
          >
            {isShort ? 'SHORT' : 'LONG'}
          </Badge>
          {m ? (
            <Badge variant="outline" className={cn('shrink-0', moneynessBadgeClass(m))}>
              {m}
            </Badge>
          ) : null}
          <span className="truncate font-mono font-medium">
            {qty} x {pos.strike_price}
            {(pos.option_type || '').toUpperCase() === 'CALL' ? 'C' : 'P'} {pos.expiration_date?.slice(0, 10) ?? '—'}
          </span>
          {mPct !== null ? (
            <span className="shrink-0 text-xs text-muted-foreground">
              {mPct >= 0 ? '+' : ''}
              {mPct.toFixed(1)}%
            </span>
          ) : null}
          {pos.broker ? (
            <BrokerBadge
              broker={pos.broker}
              accountNumber={pos.account_number ?? null}
              className="shrink-0"
            />
          ) : null}
        </div>

        <div className="flex shrink-0 items-center gap-2">
          <div className="h-1.5 w-[60px] overflow-hidden rounded-full bg-muted">
            <div className={cn('h-full rounded-full transition-[width] duration-300', dteBarClass)} style={{ width: `${dtePct}%` }} />
          </div>
          <div className="flex items-center gap-1">
            {dte <= 3 ? (
              <span
                className="size-1.5 rounded-full bg-[rgb(var(--status-danger)/1)]"
                aria-hidden
              />
            ) : null}
            <span
              className={cn(
                'w-[35px] text-right text-xs',
                dte <= 3 && 'font-bold',
                dte > 3 && dte <= 7 && 'font-bold',
                dte <= 3 && semanticTextColorClass('status.danger'),
                dte > 3 && dte <= 7 && semanticTextColorClass('status.warning'),
                dte > 7 && dte <= 30 && semanticTextColorClass('status.warning'),
                dte > 7 && dte <= 30 && 'opacity-80',
                dte > 30 && 'text-muted-foreground',
              )}
            >
              {dte}d
            </span>
          </div>
        </div>

        {hasGreeks ? (
          <div className="flex shrink-0 flex-wrap gap-2 text-xs text-muted-foreground">
            {pos.delta != null ? (
              <span>
                D<span className="ml-0.5 font-mono">{pos.delta.toFixed(2)}</span>
              </span>
            ) : null}
            {pos.gamma != null ? (
              <span>
                G<span className="ml-0.5 font-mono">{pos.gamma.toFixed(3)}</span>
              </span>
            ) : null}
            {pos.theta != null ? (
              <span>
                T
                <span
                  className={cn(
                    'ml-0.5 font-mono',
                    pos.theta < 0 ? 'text-[rgb(var(--status-danger)/1)]' : 'text-[rgb(var(--status-success)/1)]',
                  )}
                >
                  {pos.theta.toFixed(2)}
                </span>
              </span>
            ) : null}
            {pos.vega != null ? (
              <span>
                V<span className="ml-0.5 font-mono">{pos.vega.toFixed(2)}</span>
              </span>
            ) : null}
          </div>
        ) : (
          <Badge variant="outline" className={cn('shrink-0', gwConnected && 'border-amber-500/50 text-amber-700 dark:text-amber-400')}>
            {gwConnected ? 'Syncing...' : 'No Greeks'}
          </Badge>
        )}

        <PnlText value={Number(pos.unrealized_pnl ?? 0)} format="currency" fontSize="sm" currency={currency} />
      </div>

      <div className="mt-1 flex flex-wrap gap-4 pl-1 text-xs text-muted-foreground">
        <span>Price {formatMoney(Number(pos.current_price ?? 0), currency)}</span>
        {pos.cost_basis != null && Number(pos.cost_basis) !== 0 ? (
          <span>Cost {formatMoney(Math.abs(Number(pos.cost_basis)), currency)}</span>
        ) : null}
        {pos.realized_pnl != null && Number(pos.realized_pnl) !== 0 ? (
          <span
            className={
              Number(pos.realized_pnl) >= 0 ? 'text-[rgb(var(--status-success)/1)]' : 'text-[rgb(var(--status-danger)/1)]'
            }
          >
            Realized {Number(pos.realized_pnl) >= 0 ? '+' : ''}
            {formatMoney(Number(pos.realized_pnl), currency)}
          </span>
        ) : null}
        {pos.commission != null && Number(pos.commission) !== 0 ? (
          <span className="text-[rgb(var(--status-danger)/1)]">
            Comm. {formatMoney(Math.abs(Number(pos.commission)), currency)}
          </span>
        ) : null}
        {pos.implied_volatility != null && pos.implied_volatility > 0 ? (
          <span>IV {(pos.implied_volatility * 100).toFixed(1)}%</span>
        ) : null}
        {pos.underlying_price != null && Number(pos.underlying_price) > 0 ? (
          <span>Underlying {formatMoney(Number(pos.underlying_price), currency)}</span>
        ) : null}
      </div>
    </div>
  );
};

/* ------------------------------------------------------------------ */
/* Option Chain Tab (broker-agnostic; any available source renders)    */
/* ------------------------------------------------------------------ */

type ChainEntry = {
  strike: number;
  last?: number;
  bid?: number;
  ask?: number;
  iv?: number;
  delta?: number;
  gamma?: number;
  theta?: number;
  vega?: number;
  volume?: number;
  open_interest?: number;
};

const OptionChainTab: React.FC<{
  chainSymbol: string;
  setChainSymbol: (s: string) => void;
  underlyingOptions: string[];
  positions: OptionPos[];
  isAdmin: boolean;
}> = ({ chainSymbol, setChainSymbol, underlyingOptions, positions, isAdmin }) => {
  const [selectedExp, setSelectedExp] = useState<string | null>(null);

  // Probe which chain sources are wired for the current user. The UI uses
  // this to decide between "render data", "empty state with CTA", and
  // (admin-only) dev-mode hints — never hardcoding a single broker.
  const sourcesQuery = useQuery<{ sources: ChainSource[]; any_available: boolean }>({
    queryKey: ['optionChainSources'],
    queryFn: async () => {
      const res = await api.get('/portfolio/options/chain/sources');
      return (
        res.data?.data ?? { sources: [] as ChainSource[], any_available: false }
      );
    },
    staleTime: 30000,
    refetchInterval: 60000,
  });
  const anyAvailable = sourcesQuery.data?.any_available ?? false;

  const chainQuery = useQuery({
    queryKey: ['optionChain', chainSymbol],
    queryFn: async () => {
      const res = await api.get(`/portfolio/options/chain/${encodeURIComponent(chainSymbol)}`);
      return (
        res.data?.data ?? { source: 'none', expirations: [], chains: {}, attempts: [] }
      );
    },
    enabled: !!chainSymbol && anyAvailable,
    staleTime: 30000,
  });

  const chainData = chainQuery.data as
    | {
        source: string;
        expirations: string[];
        chains: Record<string, { calls: ChainEntry[]; puts: ChainEntry[] }>;
        attempts?: Array<{ name: string; available: boolean; succeeded: boolean; error?: string }>;
      }
    | undefined;

  const expirations = chainData?.expirations ?? [];
  const activeExp = selectedExp ?? expirations[0] ?? null;
  const activeChain = activeExp ? chainData?.chains?.[activeExp] : null;
  const chainSource = chainData?.source ?? null;

  const heldStrikes = useMemo(() => {
    const set = new Set<string>();
    for (const p of positions) {
      if (p.underlying_symbol === chainSymbol) {
        set.add(`${p.strike_price}-${(p.option_type || '').toUpperCase()}`);
      }
    }
    return set;
  }, [positions, chainSymbol]);

  const underlyingPrice = useMemo(() => {
    const match = positions.find(p => p.underlying_symbol === chainSymbol && p.underlying_price);
    return Number(match?.underlying_price ?? 0);
  }, [positions, chainSymbol]);

  if (sourcesQuery.isPending) {
    return (
      <Card className="gap-0 py-0">
        <CardContent className="py-8">
          <div className="flex flex-col items-center gap-3 text-center text-muted-foreground">
            <Loader2 className="size-6 animate-spin" aria-hidden />
            <p className="text-sm">Checking option chain sources…</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  // Honest, broker-agnostic empty state. We never mention a single broker
  // by name here — the user may be on Schwab/Tastytrade and have no IBKR
  // at all. The admin-only footer keeps the `make ib-up` dev instruction
  // accessible without leaking it into the non-admin UI.
  if (!anyAvailable) {
    return <ChainEmptyState sources={sourcesQuery.data?.sources ?? []} isAdmin={isAdmin} />;
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <Input
          placeholder="Enter symbol..."
          value={chainSymbol}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) => setChainSymbol(e.target.value.toUpperCase())}
          className="max-w-[200px] h-8 text-sm"
        />
        {underlyingOptions.slice(0, 8).map((sym) => (
          <Button key={sym} size="xs" variant={chainSymbol === sym ? 'default' : 'outline'} onClick={() => setChainSymbol(sym)}>
            {sym}
          </Button>
        ))}
        {chainSource ? <ChainSourceBadge source={chainSource} /> : null}
      </div>

      {chainQuery.isPending && chainSymbol ? (
        <p className="text-sm text-muted-foreground">Loading chain...</p>
      ) : null}

      {chainSymbol && chainData && chainSource === 'none' ? (
        <Card className="gap-0 border-amber-500/40 py-0">
          <CardContent className="py-4">
            <p className="text-sm font-bold text-foreground">
              No chain data available for {chainSymbol}.
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              Every configured source declined (most common: symbol not listed,
              provider rate-limited, or market closed with no cached quotes).
            </p>
            {isAdmin && chainData.attempts && chainData.attempts.length > 0 ? (
              <pre className="mt-2 overflow-x-auto rounded bg-muted/60 p-2 text-[11px] leading-4 text-muted-foreground">
                {JSON.stringify(chainData.attempts, null, 2)}
              </pre>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      {activeChain ? (
        <>
          <div className="flex flex-wrap gap-1">
            {expirations.map((exp) => (
              <Button key={exp} size="xs" variant={activeExp === exp ? 'default' : 'outline'} onClick={() => setSelectedExp(exp)}>
                {exp}
              </Button>
            ))}
          </div>

          <div className="overflow-x-auto">
            <div className="grid grid-cols-[1fr_auto_1fr] gap-0 text-xs">
              <div className="flex items-center justify-between bg-muted/60 px-2 py-1">
                <span className="font-bold">CALLS</span>
                <div className="flex gap-3">
                  <span className="inline-block w-10 text-right">Vol</span>
                  <span className="inline-block w-10 text-right">OI</span>
                  <span className="inline-block w-[50px] text-right">Bid</span>
                  <span className="inline-block w-[50px] text-right">Ask</span>
                  <span className="inline-block w-[45px] text-right">Delta</span>
                  <span className="inline-block w-10 text-right">IV</span>
                </div>
              </div>
              <div className="bg-primary px-2 py-1 text-center">
                <span className="font-bold text-primary-foreground">Strike</span>
              </div>
              <div className="flex items-center justify-between bg-muted/60 px-2 py-1">
                <div className="flex gap-3">
                  <span className="inline-block w-10">IV</span>
                  <span className="inline-block w-[45px]">Delta</span>
                  <span className="inline-block w-[50px]">Bid</span>
                  <span className="inline-block w-[50px]">Ask</span>
                  <span className="inline-block w-10">OI</span>
                  <span className="inline-block w-10">Vol</span>
                </div>
                <span className="font-bold">PUTS</span>
              </div>

              {/* Build merged strike list */}
              {(() => {
                const allStrikes = new Set<number>();
                activeChain.calls.forEach(c => allStrikes.add(c.strike));
                activeChain.puts.forEach(p => allStrikes.add(p.strike));
                const strikes = [...allStrikes].sort((a, b) => a - b);
                const callMap = new Map(activeChain.calls.map(c => [c.strike, c]));
                const putMap = new Map(activeChain.puts.map(p => [p.strike, p]));

                let closestAtmStrike = strikes[0] ?? 0;
                if (underlyingPrice > 0) {
                  let minDist = Infinity;
                  for (const s of strikes) {
                    const dist = Math.abs(s - underlyingPrice);
                    if (dist < minDist) { minDist = dist; closestAtmStrike = s; }
                  }
                }

                return strikes.map(strike => {
                  const call = callMap.get(strike);
                  const put = putMap.get(strike);
                  const isAtm = strike === closestAtmStrike && underlyingPrice > 0;
                  const hasCallPos = heldStrikes.has(`${strike}-CALL`);
                  const hasPutPos = heldStrikes.has(`${strike}-PUT`);

                  return (
                    <React.Fragment key={strike}>
                      <div
                        className={cn(
                          'flex items-center justify-between border-b border-border px-2 py-1',
                          isAtm && 'bg-amber-950/30 dark:bg-amber-950/40',
                        )}
                      >
                        <div className="flex items-center gap-1">
                          {hasCallPos ? <span className="size-1.5 rounded-full bg-blue-500" aria-hidden /> : null}
                          <span className="font-mono">{call?.last?.toFixed(2) ?? '—'}</span>
                        </div>
                        <div className="flex gap-3">
                          <span className="inline-block w-10 text-right font-mono text-muted-foreground">{call?.volume ?? '—'}</span>
                          <span className="inline-block w-10 text-right font-mono text-muted-foreground">{call?.open_interest ?? '—'}</span>
                          <span className="inline-block w-[50px] text-right font-mono">{call?.bid?.toFixed(2) ?? '—'}</span>
                          <span className="inline-block w-[50px] text-right font-mono">{call?.ask?.toFixed(2) ?? '—'}</span>
                          <span className="inline-block w-[45px] text-right font-mono">{call?.delta?.toFixed(2) ?? '—'}</span>
                          <span className="inline-block w-10 text-right font-mono">
                            {call?.iv ? `${(call.iv * 100).toFixed(0)}%` : '—'}
                          </span>
                        </div>
                      </div>
                      <div
                        className={cn(
                          'border-b border-border px-2 py-1 text-center',
                          isAtm ? 'bg-amber-600 text-amber-50' : 'bg-primary text-primary-foreground',
                        )}
                      >
                        <span className="font-mono font-bold">
                          {strike}
                          {isAtm ? <span className="ml-1 text-[0.65rem]">ATM</span> : null}
                        </span>
                      </div>
                      <div
                        className={cn(
                          'flex items-center justify-between border-b border-border px-2 py-1',
                          isAtm && 'bg-amber-950/30 dark:bg-amber-950/40',
                        )}
                      >
                        <div className="flex gap-3">
                          <span className="inline-block w-10 font-mono">{put?.iv ? `${(put.iv * 100).toFixed(0)}%` : '—'}</span>
                          <span className="inline-block w-[45px] font-mono">{put?.delta?.toFixed(2) ?? '—'}</span>
                          <span className="inline-block w-[50px] font-mono">{put?.bid?.toFixed(2) ?? '—'}</span>
                          <span className="inline-block w-[50px] font-mono">{put?.ask?.toFixed(2) ?? '—'}</span>
                          <span className="inline-block w-10 font-mono text-muted-foreground">{put?.open_interest ?? '—'}</span>
                          <span className="inline-block w-10 font-mono text-muted-foreground">{put?.volume ?? '—'}</span>
                        </div>
                        <div className="flex items-center gap-1">
                          <span className="font-mono">{put?.last?.toFixed(2) ?? '—'}</span>
                          {hasPutPos ? <span className="size-1.5 rounded-full bg-blue-500" aria-hidden /> : null}
                        </div>
                      </div>
                    </React.Fragment>
                  );
                });
              })()}
            </div>
          </div>
        </>
      ) : null}

    </div>
  );
};

/* ------------------------------------------------------------------ */
/* Option-chain empty state (broker-honest, CTA to Connections)        */
/* ------------------------------------------------------------------ */
const ChainEmptyState: React.FC<{ sources: ChainSource[]; isAdmin: boolean }> = ({
  sources,
  isAdmin,
}) => {
  const brokerSources = sources.filter((s) => s.kind === 'broker');
  const providerSources = sources.filter((s) => s.kind === 'provider');
  return (
    <Card className="gap-0 py-0">
      <CardContent className="py-10">
        <div className="mx-auto flex max-w-xl flex-col items-center gap-3 text-center">
          <Plug className="size-8 text-muted-foreground" aria-hidden />
          <p className="text-base font-bold text-foreground">
            Option chain data isn't available right now.
          </p>
          <p className="text-sm text-muted-foreground">
            To enable option chains, either connect a broker with options access
            (Schwab, Tastytrade, IBKR) <span className="whitespace-nowrap">or</span>{' '}
            add a market-data provider key (Polygon, Tradier, or Alpha Vantage)
            in{' '}
            <span className="font-medium text-foreground">
              Settings &rarr; Connections &rarr; Market Data
            </span>
            .
          </p>
          <div className="mt-1 flex flex-wrap items-center justify-center gap-2">
            <Button asChild size="sm">
              <Link href="/settings/connections">
                <Link2 className="size-4" aria-hidden />
                Open Connections
              </Link>
            </Button>
          </div>
          {sources.length > 0 ? (
            <div className="mt-3 w-full rounded-md border border-border bg-muted/30 p-3 text-left text-xs text-muted-foreground">
              <p className="mb-1 font-medium text-foreground">Available sources</p>
              <ul className="flex flex-col gap-0.5">
                {[...brokerSources, ...providerSources].map((s) => (
                  <li key={s.name} className="flex items-center gap-2">
                    <span
                      className={cn(
                        'inline-block size-1.5 rounded-full',
                        s.available
                          ? 'bg-[rgb(var(--status-success)/1)]'
                          : 'bg-muted-foreground/50',
                      )}
                      aria-hidden
                    />
                    <span className="font-medium">{s.label}</span>
                    <span className="text-muted-foreground">
                      {s.available ? 'ready' : s.reason ?? 'not configured'}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {isAdmin ? (
            <p className="mt-2 text-[11px] text-muted-foreground">
              Dev tip: run{' '}
              <code className="rounded bg-muted px-1 py-0.5 font-mono text-[11px]">
                make ib-up
              </code>{' '}
              to connect to an IB Gateway on localhost (admins only).
            </p>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
};

const ChainSourceBadge: React.FC<{ source: string }> = ({ source }) => {
  if (!source || source === 'none') return null;
  const label =
    source === 'ibkr_gateway'
      ? 'IB Gateway'
      : source === 'yfinance'
        ? 'Yahoo Finance'
        : source;
  return (
    <Badge
      variant="outline"
      className="border-muted-foreground/30 text-[10px] uppercase tracking-wide text-muted-foreground"
      title={`Chain data served from ${label}`}
    >
      <Wifi className="size-3" aria-hidden />
      {label}
    </Badge>
  );
};

/* ------------------------------------------------------------------ */
/* Positions error card (admin sees HTTP status + request path)        */
/* ------------------------------------------------------------------ */
const OptionsErrorCard: React.FC<{
  error: unknown;
  isAdmin: boolean;
  onRetry: () => void;
}> = ({ error, isAdmin, onRetry }) => {
  const status = (error as { response?: { status?: number } } | null)?.response?.status ?? null;
  const detail =
    (error as { response?: { data?: { detail?: string } } } | null)?.response?.data?.detail ??
    (error as { message?: string } | null)?.message ??
    null;
  const cfg = (error as { config?: { url?: string; method?: string } } | null)?.config ?? null;
  const reqPath = cfg?.url ?? null;
  const reqMethod = (cfg?.method ?? 'get').toUpperCase();
  return (
    <Card className="gap-0 border-destructive/40 py-0">
      <CardContent className="py-6">
        <div className="flex flex-col gap-2">
          <p className="text-sm font-bold text-[rgb(var(--status-danger)/1)]">
            Failed to load options.
          </p>
          <p className="text-xs text-muted-foreground">
            We couldn't fetch your options positions. This is usually a transient
            backend issue — retry below. If it keeps happening, check{' '}
            <Link href="/settings/connections" className="underline">
              Connections
            </Link>{' '}
            and make sure at least one broker is synced.
          </p>
          {isAdmin && (status || detail || reqPath) ? (
            <pre className="overflow-x-auto rounded bg-muted/60 p-2 text-[11px] leading-4 text-muted-foreground">
              {[
                reqPath ? `${reqMethod} ${reqPath}` : null,
                status != null ? `status: ${status}` : null,
                detail ? `detail: ${detail}` : null,
              ]
                .filter(Boolean)
                .join('\n')}
            </pre>
          ) : null}
          <div>
            <Button size="sm" variant="outline" onClick={onRetry}>
              <RefreshCw className="size-4" aria-hidden /> Retry
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

/* ------------------------------------------------------------------ */
/* P&L Tab (SortableTable)                                             */
/* ------------------------------------------------------------------ */

type PnlRow = {
  sym: string;
  posCount: number;
  totalValue: number;
  callsPnl: number;
  putsPnl: number;
  totalPnl: number;
  pnlPct: number;
  realizedPnl: number;
  deltaExposure: number;
};

const pnlColumns: Column<PnlRow>[] = [
  {
    key: 'sym',
    header: 'Underlying',
    accessor: (r) => r.sym,
    sortable: true,
    sortType: 'string',
    filterable: true,
    filterType: 'text',
    render: (_v, r) => <SymbolLink symbol={r.sym} />,
  },
  {
    key: 'posCount',
    header: 'Pos',
    accessor: (r) => r.posCount,
    sortable: true,
    sortType: 'number',
    isNumeric: true,
    width: '55px',
  },
  {
    key: 'totalValue',
    header: 'Value',
    accessor: (r) => r.totalValue,
    sortable: true,
    sortType: 'number',
    isNumeric: true,
    width: '90px',
  },
  {
    key: 'callsPnl',
    header: 'Calls P&L',
    accessor: (r) => r.callsPnl,
    sortable: true,
    sortType: 'number',
    isNumeric: true,
    render: (v) => <PnlText value={Number(v)} format="currency" fontSize="xs" />,
    width: '90px',
  },
  {
    key: 'putsPnl',
    header: 'Puts P&L',
    accessor: (r) => r.putsPnl,
    sortable: true,
    sortType: 'number',
    isNumeric: true,
    render: (v) => <PnlText value={Number(v)} format="currency" fontSize="xs" />,
    width: '90px',
  },
  {
    key: 'totalPnl',
    header: 'Total P&L',
    accessor: (r) => r.totalPnl,
    sortable: true,
    sortType: 'number',
    isNumeric: true,
    render: (v) => <PnlText value={Number(v)} format="currency" fontSize="xs" />,
    width: '100px',
  },
  {
    key: 'pnlPct',
    header: 'P&L%',
    accessor: (r) => r.pnlPct,
    sortable: true,
    sortType: 'number',
    isNumeric: true,
    render: (v) => {
      const pct = Number(v);
      return (
        <span className={cn('text-xs', pct >= 0 ? 'text-[rgb(var(--status-success)/1)]' : 'text-[rgb(var(--status-danger)/1)]')}>
          {pct >= 0 ? '+' : ''}
          {pct.toFixed(1)}%
        </span>
      );
    },
    width: '65px',
  },
  {
    key: 'realizedPnl',
    header: 'Realized',
    accessor: (r) => r.realizedPnl,
    sortable: true,
    sortType: 'number',
    isNumeric: true,
    render: (v) => {
      const val = Number(v);
      if (!val) return <span className="text-xs text-muted-foreground">—</span>;
      return <PnlText value={val} format="currency" fontSize="xs" />;
    },
    width: '80px',
  },
  {
    key: 'deltaExposure',
    header: 'Delta Exp.',
    accessor: (r) => r.deltaExposure,
    sortable: true,
    sortType: 'number',
    isNumeric: true,
    render: (v) => <span className="font-mono text-xs">{Number(v).toFixed(2)}</span>,
    width: '80px',
  },
];

const pnlFilterPresets: Array<{ label: string; filters: FilterGroup }> = [
  {
    label: 'Winners',
    filters: {
      conjunction: 'AND',
      rules: [{ id: 'pnl-pos', columnKey: 'totalPnl', operator: 'gt', value: '0' }],
    },
  },
  {
    label: 'Losers',
    filters: {
      conjunction: 'AND',
      rules: [{ id: 'pnl-neg', columnKey: 'totalPnl', operator: 'lt', value: '0' }],
    },
  },
  {
    label: 'High Delta',
    filters: {
      conjunction: 'AND',
      rules: [{ id: 'delta-high', columnKey: 'deltaExposure', operator: 'gt', value: '5' }],
    },
  },
];

const PnlTab: React.FC<{
  underlyings: Record<string, { calls: OptionPos[]; puts: OptionPos[]; total_value: number; total_pnl: number }>;
  currency: string;
}> = ({ underlyings, currency }) => {
  const rows: PnlRow[] = useMemo(() => {
    return Object.entries(underlyings).map(([sym, grp]) => {
      const callsPnl = grp.calls.reduce((s, p) => s + Number(p.unrealized_pnl ?? 0), 0);
      const putsPnl = grp.puts.reduce((s, p) => s + Number(p.unrealized_pnl ?? 0), 0);
      const totalPnl = callsPnl + putsPnl;
      const realizedPnl = [...grp.calls, ...grp.puts].reduce((s, p) => s + Number(p.realized_pnl ?? 0), 0);
      const deltaExposure = [...grp.calls, ...grp.puts].reduce((s, p) => s + Number(p.delta ?? 0) * p.quantity, 0);
      const totalValue = grp.total_value;
      const totalCost = [...grp.calls, ...grp.puts].reduce((s, p) => s + Math.abs(Number(p.cost_basis ?? 0)), 0);
      const pnlPct = totalCost > 0 ? (totalPnl / totalCost) * 100 : 0;
      return { sym, callsPnl, putsPnl, totalPnl, realizedPnl, deltaExposure, totalValue, pnlPct, posCount: grp.calls.length + grp.puts.length };
    });
  }, [underlyings]);

  const totals = useMemo(() => rows.reduce(
    (acc, r) => ({
      callsPnl: acc.callsPnl + r.callsPnl,
      putsPnl: acc.putsPnl + r.putsPnl,
      totalPnl: acc.totalPnl + r.totalPnl,
      realizedPnl: acc.realizedPnl + r.realizedPnl,
      deltaExposure: acc.deltaExposure + r.deltaExposure,
    }),
    { callsPnl: 0, putsPnl: 0, totalPnl: 0, realizedPnl: 0, deltaExposure: 0 },
  ), [rows]);

  const fmtCols = useMemo(() => {
    return pnlColumns.map(col => {
      if (col.key === 'totalValue') {
        return {
          ...col,
          render: (v: any) => (
            <span className="font-mono text-xs">{formatMoney(Number(v), currency, { maximumFractionDigits: 0 })}</span>
          ),
        };
      }
      if (['callsPnl', 'putsPnl', 'totalPnl', 'realizedPnl'].includes(col.key)) {
        return {
          ...col,
          render: (v: any) => {
            const val = Number(v);
            if (col.key === 'realizedPnl' && !val) return <span className="text-xs text-muted-foreground">—</span>;
            return <PnlText value={val} format="currency" fontSize="xs" currency={currency} />;
          },
        };
      }
      return col;
    });
  }, [currency]);

  if (rows.length === 0) {
    return (
      <Card className="gap-0 py-0">
        <CardContent>
          <p className="text-muted-foreground">No positions to analyze.</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap gap-3">
        <StatCard label="Calls P&L" value={formatMoney(totals.callsPnl, currency)} color={totals.callsPnl >= 0 ? 'status.success' : 'status.danger'} />
        <StatCard label="Puts P&L" value={formatMoney(totals.putsPnl, currency)} color={totals.putsPnl >= 0 ? 'status.success' : 'status.danger'} />
        <StatCard label="Total P&L" value={formatMoney(totals.totalPnl, currency)} color={totals.totalPnl >= 0 ? 'status.success' : 'status.danger'} />
        <StatCard label="Realized" value={formatMoney(totals.realizedPnl, currency)} color={totals.realizedPnl >= 0 ? 'status.success' : 'status.danger'} />
        <StatCard label="Net Delta" value={totals.deltaExposure.toFixed(2)} />
      </div>
      <SortableTable
        data={rows}
        columns={fmtCols}
        defaultSortBy="totalPnl"
        defaultSortOrder="desc"
        size="sm"
        maxHeight="60vh"
        filtersEnabled
        filterPresets={pnlFilterPresets}
        emptyMessage="No positions to analyze."
      />
    </div>
  );
};

/* ------------------------------------------------------------------ */
/* Analytics Tab                                                       */
/* ------------------------------------------------------------------ */

/** Semantic token strokes for Recharts (no raw hex). */
const GREEKS_STROKE = {
  delta: 'rgb(var(--chart-neutral) / 1)',
  gamma: 'rgb(var(--chart-success) / 1)',
  theta: 'rgb(var(--chart-danger) / 1)',
  vega: 'rgb(var(--status-info) / 1)',
} as const;

const GreeksDashboard: React.FC<{ positions: OptionPos[]; currency: string }> = ({ positions, currency }) => {
  const byUnderlying = useMemo(() => {
    const map = new Map<string, { symbol: string; delta: number; gamma: number; theta: number; vega: number; value: number }>();
    for (const p of positions) {
      const sym = p.underlying_symbol;
      const existing = map.get(sym) ?? { symbol: sym, delta: 0, gamma: 0, theta: 0, vega: 0, value: 0 };
      existing.delta += Number(p.delta ?? 0) * p.quantity;
      existing.gamma += Number(p.gamma ?? 0) * p.quantity;
      existing.theta += Number(p.theta ?? 0) * p.quantity;
      existing.vega += Number(p.vega ?? 0) * p.quantity;
      existing.value += Number(p.market_value ?? 0);
      map.set(sym, existing);
    }
    return [...map.values()].sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta));
  }, [positions]);

  const totals = useMemo(() => ({
    delta: positions.reduce((s, p) => s + Number(p.delta ?? 0) * p.quantity, 0),
    gamma: positions.reduce((s, p) => s + Number(p.gamma ?? 0) * p.quantity, 0),
    theta: positions.reduce((s, p) => s + Number(p.theta ?? 0) * p.quantity, 0),
    vega: positions.reduce((s, p) => s + Number(p.vega ?? 0) * p.quantity, 0),
  }), [positions]);

  return (
    <Card className="gap-0 py-0">
      <CardContent>
        <p className="mb-3 font-bold text-foreground">Greeks Exposure</p>
        <div className="mb-4 flex flex-wrap gap-3">
          <StatCard label="Net Delta" value={totals.delta.toFixed(2)} color={totals.delta >= 0 ? 'status.success' : 'status.danger'} />
          <StatCard label="Net Gamma" value={totals.gamma.toFixed(3)} />
          <StatCard label="Daily Theta" value={formatMoney(totals.theta, currency)} color={totals.theta < 0 ? 'status.danger' : 'status.success'} />
          <StatCard label="Net Vega" value={totals.vega.toFixed(2)} />
        </div>
        {byUnderlying.length > 0 ? (
          <div className="h-[250px]">
            <ResponsiveContainer>
              <BarChart data={byUnderlying} layout="vertical" margin={{ left: 40, right: 20, top: 8, bottom: 28 }}>
                <XAxis
                  type="number"
                  tick={{ fontSize: 10 }}
                  label={{ value: 'Delta exposure', position: 'bottom', fontSize: 10, className: 'fill-muted-foreground' }}
                />
                <YAxis
                  type="category"
                  dataKey="symbol"
                  tick={{ fontSize: 11, fontFamily: 'mono' }}
                  width={50}
                  label={{ value: 'Symbol', angle: -90, position: 'insideLeft', fontSize: 10, className: 'fill-muted-foreground' }}
                />
                <RechartsTooltip
                  formatter={(value: any, name: any) => [
                    name === 'theta' ? formatMoney(Number(value), currency) : (Number(value) ?? 0).toFixed(3),
                    String(name ?? '').charAt(0).toUpperCase() + String(name ?? '').slice(1),
                  ] as React.ReactNode}
                />
                <Bar dataKey="delta" fill={GREEKS_STROKE.delta} barSize={8} radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
};

const ThetaCalendar: React.FC<{ positions: OptionPos[]; currency: string; timezone?: string }> = ({ positions, currency, timezone }) => {
  const projections = useMemo(() => {
    const days: Array<{ day: number; label: string; dailyTheta: number; cumTheta: number }> = [];
    const dailyTheta = positions.reduce((s, p) => s + Number(p.theta ?? 0) * p.quantity, 0);
    let cumulative = 0;

    for (let i = 0; i < 30; i++) {
      const date = new Date();
      date.setDate(date.getDate() + i);

      cumulative += dailyTheta;
      days.push({
        day: i,
        label: formatDateShort(date, timezone),
        dailyTheta,
        cumTheta: cumulative,
      });
    }
    return days;
  }, [positions, timezone]);

  return (
    <Card className="gap-0 py-0">
      <CardContent>
        <p className="mb-3 font-bold text-foreground">Theta Decay Projection (30 days)</p>
        <div className="h-[200px]">
          <ResponsiveContainer>
            <LineChart data={projections} margin={{ left: 8, right: 10, top: 5, bottom: 5 }}>
              <XAxis dataKey="label" tick={{ fontSize: 9 }} interval={4} />
              <YAxis
                tick={{ fontSize: 10 }}
                width={68}
                label={{ value: 'Cumulative theta ($)', angle: -90, position: 'insideLeft', fontSize: 10, className: 'fill-muted-foreground' }}
              />
              <RechartsTooltip
                formatter={(value: any) => [formatMoney(Number(value), currency), 'Cumulative Theta'] as React.ReactNode}
              />
              <Line
                type="monotone"
                dataKey="cumTheta"
                stroke="rgb(var(--chart-danger) / 1)"
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
};

const IVSkewChart: React.FC<{ positions: OptionPos[] }> = ({ positions }) => {
  const skewData = useMemo(() => {
    const data: Array<{ strike: number; iv: number; type: string; symbol: string }> = [];
    for (const p of positions) {
      if (p.implied_volatility && p.implied_volatility > 0) {
        data.push({
          strike: p.strike_price,
          iv: p.implied_volatility * 100,
          type: (p.option_type || '').toUpperCase(),
          symbol: p.underlying_symbol,
        });
      }
    }
    return data.sort((a, b) => a.strike - b.strike);
  }, [positions]);

  if (skewData.length < 2) {
    return (
      <Card className="gap-0 py-0">
        <CardContent>
          <p className="mb-3 font-bold text-foreground">IV Skew</p>
          <p className="text-sm text-muted-foreground">Need at least 2 positions with IV data to show skew.</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="gap-0 py-0">
      <CardContent>
        <p className="mb-3 font-bold text-foreground">IV Skew</p>
        <div className="h-[200px]">
          <ResponsiveContainer>
            <LineChart data={skewData} margin={{ left: 8, right: 10, top: 5, bottom: 5 }}>
              <XAxis
                dataKey="strike"
                tick={{ fontSize: 10 }}
                label={{ value: 'Strike', position: 'bottom', fontSize: 10, className: 'fill-muted-foreground' }}
              />
              <YAxis
                tick={{ fontSize: 10 }}
                unit="%"
                width={48}
                label={{ value: 'Implied vol.', angle: -90, position: 'insideLeft', fontSize: 10, className: 'fill-muted-foreground' }}
              />
              <RechartsTooltip
                formatter={(value: any) => [`${(Number(value) ?? 0).toFixed(1)}%`, 'IV'] as React.ReactNode}
                labelFormatter={(label) => `Strike: ${label}`}
              />
              <Line
                type="monotone"
                dataKey="iv"
                stroke="rgb(var(--status-info) / 1)"
                strokeWidth={2}
                dot={{ r: 3 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
};

const PayoffDiagram: React.FC<{ positions: OptionPos[]; currency: string }> = ({ positions, currency }) => {
  const payoffData = useMemo(() => {
    if (positions.length === 0) return [];

    const underlyingPrices = positions.map(p => Number(p.underlying_price ?? 0)).filter(Boolean);
    if (underlyingPrices.length === 0) return [];

    const avgUnderlying = underlyingPrices.reduce((a, b) => a + b, 0) / underlyingPrices.length;
    const strikes = positions.map(p => p.strike_price);
    const minPrice = Math.min(avgUnderlying * 0.8, ...strikes) * 0.95;
    const maxPrice = Math.max(avgUnderlying * 1.2, ...strikes) * 1.05;
    const step = (maxPrice - minPrice) / 50;

    const data: Array<{ price: number; pnl: number }> = [];
    for (let price = minPrice; price <= maxPrice; price += step) {
      let totalPnl = 0;
      for (const p of positions) {
        const isCall = (p.option_type || '').toUpperCase() === 'CALL';
        const intrinsic = isCall
          ? Math.max(0, price - p.strike_price)
          : Math.max(0, p.strike_price - price);
        const costPerContract = Math.abs(Number(p.average_open_price ?? 0));
        const pnlPerContract = p.quantity > 0
          ? (intrinsic - costPerContract) * 100
          : (costPerContract - intrinsic) * 100;
        totalPnl += pnlPerContract * Math.abs(p.quantity);
      }
      data.push({ price: Math.round(price * 100) / 100, pnl: Math.round(totalPnl) });
    }
    return data;
  }, [positions]);

  if (payoffData.length === 0) {
    return null;
  }

  return (
    <Card className="gap-0 py-0">
      <CardContent>
        <p className="mb-3 font-bold text-foreground">Payoff at Expiration</p>
        <div className="h-[250px]">
          <ResponsiveContainer>
            <LineChart data={payoffData} margin={{ left: 20, right: 20, top: 5, bottom: 5 }}>
              <XAxis dataKey="price" tick={{ fontSize: 10 }} label={{ value: 'Underlying Price', position: 'bottom', fontSize: 11 }} />
              <YAxis tick={{ fontSize: 10 }} label={{ value: 'P/L ($)', angle: -90, position: 'insideLeft', fontSize: 11 }} />
              <RechartsTooltip
                formatter={(value: any) => [formatMoney(Number(value), currency), 'P/L at Expiration'] as React.ReactNode}
                labelFormatter={(label) => `Price: $${label}`}
              />
              <Line
                type="monotone"
                dataKey="pnl"
                stroke="rgb(var(--chart-neutral) / 1)"
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
};

const OptionsAnalyticsTab: React.FC<{ positions: OptionPos[]; currency: string; timezone?: string }> = ({ positions, currency, timezone }) => {
  return (
    <div className="flex flex-col gap-4">
      <GreeksDashboard positions={positions} currency={currency} />
      <div className="flex flex-wrap items-start gap-4">
        <div className="min-w-[300px] flex-1">
          <ThetaCalendar positions={positions} currency={currency} timezone={timezone} />
        </div>
        <div className="min-w-[300px] flex-1">
          <IVSkewChart positions={positions} />
        </div>
      </div>
      <PayoffDiagram positions={positions} currency={currency} />
    </div>
  );
};

/* ------------------------------------------------------------------ */
/* History Tab                                                         */
/* ------------------------------------------------------------------ */
type HistoryItem = {
  id: number;
  symbol: string;
  underlying_symbol: string;
  option_type: string;
  strike_price: number | null;
  expiry_date: string | null;
  event_type: string;
  exercised_quantity: number;
  assigned_quantity: number;
  original_quantity: number;
  cost_basis: number;
  realized_pnl: number;
  commission: number;
};

const historyColumns: Column<HistoryItem>[] = [
  {
    key: 'underlying_symbol',
    header: 'Underlying',
    accessor: (r) => r.underlying_symbol,
    sortable: true,
    sortType: 'string',
    filterable: true,
    filterType: 'text',
    render: (_v, r) => <SymbolLink symbol={r.underlying_symbol} />,
  },
  {
    key: 'option_type',
    header: 'Type',
    accessor: (r) => (r.option_type || '').toUpperCase(),
    sortable: true,
    sortType: 'string',
    render: (v) => (
      <Badge
        variant="secondary"
        className={
          v === 'CALL'
            ? 'bg-[rgb(var(--status-success)/0.15)] text-[rgb(var(--status-success)/1)]'
            : 'bg-destructive/10 text-destructive'
        }
      >
        {v}
      </Badge>
    ),
    width: '70px',
  },
  {
    key: 'strike',
    header: 'Strike',
    accessor: (r) => r.strike_price ?? 0,
    sortable: true,
    sortType: 'number',
    isNumeric: true,
    render: (v) => <span className="font-mono">{Number(v) ? Number(v).toFixed(2) : '—'}</span>,
    width: '80px',
  },
  {
    key: 'expiry',
    header: 'Expiry',
    accessor: (r) => r.expiry_date ?? '',
    sortable: true,
    sortType: 'date',
    render: (v) => <span className="text-xs">{v || '—'}</span>,
    width: '95px',
  },
  {
    key: 'event',
    header: 'Event',
    accessor: (r) => r.event_type,
    sortable: true,
    sortType: 'string',
    filterable: true,
    filterType: 'select',
    filterOptions: [
      { label: 'Exercised', value: 'exercised' },
      { label: 'Assigned', value: 'assigned' },
      { label: 'Expired', value: 'expired' },
    ],
    render: (v) => (
      <Badge
        variant="secondary"
        className={cn(
          'capitalize',
          v === 'exercised' && 'bg-blue-500/15 text-blue-700 dark:text-blue-300',
          v === 'assigned' && 'bg-amber-500/15 text-amber-800 dark:text-amber-300',
          v !== 'exercised' && v !== 'assigned' && 'text-muted-foreground',
        )}
      >
        {v}
      </Badge>
    ),
    width: '90px',
  },
  {
    key: 'qty',
    header: 'Qty',
    accessor: (r) => r.original_quantity,
    sortable: true,
    sortType: 'number',
    isNumeric: true,
    width: '55px',
  },
  {
    key: 'costBasis',
    header: 'Cost Basis',
    accessor: (r) => r.cost_basis,
    sortable: true,
    sortType: 'number',
    isNumeric: true,
    width: '90px',
  },
  {
    key: 'realizedPnl',
    header: 'Realized P&L',
    accessor: (r) => r.realized_pnl,
    sortable: true,
    sortType: 'number',
    isNumeric: true,
    render: (v) => <PnlText value={Number(v)} format="currency" fontSize="xs" />,
    width: '100px',
  },
  {
    key: 'commission',
    header: 'Commission',
    accessor: (r) => r.commission,
    sortable: true,
    sortType: 'number',
    isNumeric: true,
    render: (v) => {
      const val = Number(v);
      if (!val) return <span className="text-xs text-muted-foreground">—</span>;
      return <span className="text-xs text-[rgb(var(--status-danger)/1)]">{Math.abs(val).toFixed(2)}</span>;
    },
    width: '85px',
  },
];

const OptionsHistoryTab: React.FC<{ accountId?: string }> = ({ accountId }) => {
  const historyQuery = useQuery({
    queryKey: ['optionsHistory', accountId],
    queryFn: async () => {
      const params = accountId ? `?account_id=${accountId}` : '';
      const res = await api.get(`/portfolio/options/history${params}`);
      return res.data?.data ?? { history: [], total: 0 };
    },
    staleTime: 60000,
  });

  const items: HistoryItem[] = historyQuery.data?.history ?? [];

  if (historyQuery.isPending) {
    return <TableSkeleton rows={5} cols={4} />;
  }

  if (historyQuery.error) {
    return <p className="text-sm text-[rgb(var(--status-danger)/1)]">Failed to load options history.</p>;
  }

  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-muted-foreground">
        Exercised, assigned, and expired options from your account history.
      </p>
      <SortableTable
        data={items}
        columns={historyColumns}
        defaultSortBy="expiry"
        defaultSortOrder="desc"
        size="sm"
        maxHeight="70vh"
        filtersEnabled
        emptyMessage="No historical options events found."
      />
    </div>
  );
};

export default PortfolioOptionsClient;
