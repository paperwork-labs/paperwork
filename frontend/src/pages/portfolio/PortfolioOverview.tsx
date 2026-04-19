import React, { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Loader2, RefreshCw, TriangleAlert } from 'lucide-react';
import { ChartContext, ChartSlidePanel } from '../../components/market/SymbolChartUI';
import StatCard from '../../components/shared/StatCard';
import StageBar from '../../components/shared/StageBar';
import PnlText from '../../components/shared/PnlText';
import { Page, PageHeader } from '../../components/ui/Page';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { cn } from '@/lib/utils';
import { semanticTextColorClass } from '@/lib/semantic-text-color';
import { useAccountFilter } from '../../hooks/useAccountFilter';
import { DashboardResponse } from '../../services/api';
import {
  usePortfolioOverview,
  usePositions,
  usePortfolioSync,
  usePortfolioPerformanceHistory,
  usePortfolioInsights,
  useAccountBalances,
  useMarginInterest,
  useDividendSummary,
  useLiveSummary,
  useRiskMetrics,
  usePnlSummary,
} from '../../hooks/usePortfolio';
import { useChartColors } from '../../hooks/useChartColors';
import { useUserPreferences } from '../../hooks/useUserPreferences';
import { formatMoney } from '../../utils/format';
import {
  buildAccountsFromPositions,
  stageCountsFromPositions,
  sectorAllocationFromPositions,
  topMoversFromPositions,
  timeAgo,
} from '../../utils/portfolio';
import { StatCardSkeleton } from '../../components/shared/Skeleton';
import { CircuitBreakerBanner } from '../../components/shared/CircuitBreakerBanner';
import { DailyNarrative } from '../../components/portfolio/DailyNarrative';
import type { AccountData } from '../../hooks/useAccountFilter';
import type { EnrichedPosition } from '../../types/portfolio';
import { SECTOR_PALETTE } from '../../constants/chart';
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Legend,
  Tooltip,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Line,
  ComposedChart,
} from 'recharts';
import { marketDataApi } from '../../services/api';

const PERIODS = [
  { key: '30d', label: '30d' },
  { key: '90d', label: '90d' },
  { key: '1y', label: '1Y' },
  { key: 'all', label: 'All' },
] as const;

const PortfolioOverview: React.FC = () => {
  const [chartSymbol, setChartSymbol] = useState<string | null>(null);
  const [historyPeriod, setHistoryPeriod] = useState<string>('1y');
  const [showBenchmark, setShowBenchmark] = useState<boolean>(true);
  const { currency } = useUserPreferences();
  const colors = useChartColors();
  const overview = usePortfolioOverview();
  const positionsQuery = usePositions();
  const syncMutation = usePortfolioSync();
  const historyQuery = usePortfolioPerformanceHistory({ period: historyPeriod });
  const insightsQuery = usePortfolioInsights();
  const insights = insightsQuery.data;
  const balancesQuery = useAccountBalances();
  const marginQuery = useMarginInterest();
  const balances = (balancesQuery.data ?? []) as Array<Record<string, unknown>>;
  const marginItems = (marginQuery.data ?? []) as Array<Record<string, unknown>>;
  const dividendQuery = useDividendSummary();
  const dividendData = dividendQuery.data ?? {};
  const liveQuery = useLiveSummary();
  const liveData = liveQuery.data ?? {};
  const riskQuery = useRiskMetrics();
  const riskData = riskQuery.data ?? {};
  const positions = (positionsQuery.data ?? []) as EnrichedPosition[];
  const dashboard = overview.summary.data as DashboardResponse | undefined;
  const rawAccounts = overview.accountsData ?? [];
  const historySeries = (historyQuery.data ?? []) as Array<{ date: string; total_value: number }>;

  const [spyBars, setSpyBars] = React.useState<Array<{ time: string; close: number }>>([]);
  React.useEffect(() => {
    marketDataApi
      .getHistory('SPY', historyPeriod === 'all' ? '5y' : historyPeriod, '1d')
      .then((res: { bars?: unknown; data?: unknown }) => {
        const bars = (res?.bars || res?.data || []) as Array<{ time?: string; date?: string; close: number }>;
        setSpyBars(bars.map((b) => ({ time: (b.time || b.date || '').slice(0, 10), close: b.close })));
      })
      .catch(() => setSpyBars([]));
  }, [historyPeriod]);

  const equityCurveData = useMemo(() => {
    if (!historySeries.length) return [];
    const spyMap = new Map(spyBars.map((b) => [b.time, b.close]));
    const firstPortfolioValue = historySeries[0].total_value || 1;
    let firstSpyClose: number | null = null;
    return historySeries.map((pt) => {
      const dateKey = pt.date.slice(0, 10);
      const spyClose = spyMap.get(dateKey);
      if (spyClose && firstSpyClose === null) firstSpyClose = spyClose;
      const portfolioPct = (pt.total_value / firstPortfolioValue - 1) * 100;
      const spyPct =
        spyClose && firstSpyClose ? (spyClose / firstSpyClose - 1) * 100 : undefined;
      return { date: dateKey, total_value: pt.total_value, portfolio_pct: portfolioPct, spy_pct: spyPct };
    });
  }, [historySeries, spyBars]);

  const accounts: AccountData[] = useMemo(
    () =>
      buildAccountsFromPositions(
        rawAccounts.map(
          (a: {
            id?: number;
            account_number?: string;
            broker?: string;
            account_name?: string;
            account_type?: string;
            last_successful_sync?: string | null;
          }) => ({
            id: a.id,
            account_number: a.account_number ?? String(a.id),
            broker: a.broker ?? 'Unknown',
            account_name: a.account_name,
            account_type: a.account_type,
            last_successful_sync: a.last_successful_sync,
          }),
        ),
        positions,
      ),
    [rawAccounts, positions],
  );

  const filterState = useAccountFilter(positions as import('../../hooks/useAccountFilter').FilterableItem[], accounts);
  const filteredPositions = filterState.filteredData as EnrichedPosition[];

  const pnlSummaryQuery = usePnlSummary(
    filterState.selectedAccount === 'all' ? undefined : filterState.selectedAccount,
  );
  const pnlSummary = pnlSummaryQuery.data;

  const summary = (dashboard?.data?.summary ?? dashboard?.summary ?? dashboard) as
    | import('../../services/api').DashboardSummary
    | undefined;
  const dayChange = Number(summary?.day_change ?? 0);
  const dayChangePct = Number(summary?.day_change_pct ?? 0);

  const openChart = (symbol: string) => setChartSymbol(symbol);

  return (
    <ChartContext.Provider value={openChart}>
      <Page>
        <div className="flex flex-col gap-4">
          <PageHeader
            title="Portfolio Overview"
            subtitle="KPIs, allocation, stage distribution, and account summary"
            rightContent={
              <Button
                size="sm"
                variant="outline"
                onClick={() => syncMutation.mutate()}
                disabled={syncMutation.isPending}
                className="gap-2"
              >
                {syncMutation.isPending ? (
                  <Loader2 className="size-4 animate-spin" aria-hidden />
                ) : (
                  <RefreshCw className="size-4" aria-hidden />
                )}
                Sync
              </Button>
            }
          />

          <DailyNarrative />

          {!liveQuery.isPending && !liveData.is_live && (
            <Alert className="border-amber-500/40 bg-amber-500/10 text-amber-950 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-100">
              <TriangleAlert className="size-4" aria-hidden />
              <AlertTitle className="text-sm">Live data disconnected</AlertTitle>
              <AlertDescription className="text-sm">
                Portfolio values may be stale.{' '}
                <Link to="/settings/connections" className="font-semibold underline underline-offset-2">
                  Reconnect in Settings
                </Link>
              </AlertDescription>
            </Alert>
          )}

          <CircuitBreakerBanner />

          {(overview.isPending || positionsQuery.isPending) && (
            <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
              {[1, 2, 3, 4].map((i) => (
                <StatCardSkeleton key={i} />
              ))}
            </div>
          )}
          {!(overview.isPending || positionsQuery.isPending) && (overview.error || positionsQuery.error) ? (
            <p className={cn('text-sm', semanticTextColorClass('status.danger'))}>Failed to load portfolio data</p>
          ) : null}
          {(() => {
            if (overview.isPending || positionsQuery.isPending) return null;
            if (overview.error || positionsQuery.error) return null;
            const pos = filteredPositions;
            const filteredStage = stageCountsFromPositions(pos);
            const filteredSector = sectorAllocationFromPositions(pos);
            const filteredMovers = topMoversFromPositions(pos);
            const filteredTotal = pos.reduce((s, p) => s + Number(p.market_value ?? 0), 0);
            const filteredCost = pos.reduce((s, p) => {
              const avg = (p as { average_cost?: number }).average_cost;
              const sh = (p as { shares?: number }).shares ?? 0;
              return s + Number(p.cost_basis ?? (avg != null ? avg * sh : 0));
            }, 0);
            const filteredPnl = pos.reduce((s, p) => s + Number(p.unrealized_pnl ?? 0), 0);
            const filteredPnlPct = filteredTotal ? (filteredPnl / filteredTotal) * 100 : 0;
            const filteredBalances =
              filterState.selectedAccount === 'all'
                ? balances
                : balances.filter((b) => {
                    const raw = rawAccounts.find((a: { id?: number }) => a.id === b.account_id);
                    return (
                      raw &&
                      ((raw as { account_number?: string }).account_number === filterState.selectedAccount ||
                        String((raw as { id?: unknown }).id) === filterState.selectedAccount)
                    );
                  });
            const nlvTotal = filteredBalances.reduce((s, b) => s + Number(b.net_liquidation ?? 0), 0);
            const kpiValue = nlvTotal > 0 ? nlvTotal : filteredTotal;
            return (
              <>
                <div className="flex flex-wrap gap-3">
                  <StatCard
                    label="Total Value"
                    value={formatMoney(kpiValue, currency, { maximumFractionDigits: 0 })}
                    sub={
                      nlvTotal > 0
                        ? `NLV (incl. cash)`
                        : filteredCost
                          ? `Cost basis ${formatMoney(filteredCost, currency, { maximumFractionDigits: 0 })}`
                          : undefined
                    }
                  />
                  <StatCard
                    label="Day P&L"
                    value={formatMoney(dayChange, currency)}
                    sub={dayChangePct !== 0 ? `${dayChangePct >= 0 ? '+' : ''}${dayChangePct.toFixed(2)}%` : undefined}
                    trend={dayChange >= 0 ? 'up' : 'down'}
                    color={dayChange >= 0 ? 'status.success' : 'status.danger'}
                  />
                  <StatCard
                    label="Unrealized P&L"
                    value={formatMoney(filteredPnl, currency)}
                    sub={
                      filteredPnlPct !== 0 ? `${filteredPnlPct >= 0 ? '+' : ''}${filteredPnlPct.toFixed(2)}%` : undefined
                    }
                    color={filteredPnl >= 0 ? 'status.success' : 'status.danger'}
                  />
                  {pnlSummary && (
                    <StatCard
                      label="Realized P&L"
                      value={formatMoney(pnlSummary.realized_pnl, currency)}
                      sub={
                        pnlSummary.total_dividends > 0
                          ? `+${formatMoney(pnlSummary.total_dividends, currency, { maximumFractionDigits: 0 })} dividends`
                          : undefined
                      }
                      color={pnlSummary.realized_pnl >= 0 ? 'status.success' : 'status.danger'}
                    />
                  )}
                  <StatCard label="Positions" value={pos.length} />
                </div>

                {insights &&
                  (insights.harvest_candidates?.length > 0 ||
                    insights.approaching_lt?.length > 0 ||
                    insights.concentration_warnings?.length > 0) && (
                    <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
                      <Card className="gap-0 border border-border py-3 shadow-none ring-0">
                        <CardContent className="px-4 py-0">
                          <div className="mb-2 flex items-center gap-2">
                            <span className="text-sm font-semibold text-muted-foreground">Tax Loss Harvest</span>
                            <Badge variant="destructive" className="h-5 text-[10px]">
                              {insights.harvest_candidates?.length ?? 0}
                            </Badge>
                          </div>
                          {(insights.harvest_candidates?.length ?? 0) === 0 ? (
                            <p className="text-xs text-muted-foreground">No candidates</p>
                          ) : (
                            <div className="flex flex-col gap-1">
                              {insights.harvest_candidates.slice(0, 5).map((c) => (
                                <div key={c.symbol} className="flex justify-between gap-2">
                                  <span className="font-mono text-xs">{c.symbol}</span>
                                  <span className={cn('text-xs', semanticTextColorClass('status.danger'))}>
                                    {formatMoney(c.unrealized_pnl, currency, { maximumFractionDigits: 0 })}
                                  </span>
                                </div>
                              ))}
                            </div>
                          )}
                        </CardContent>
                      </Card>

                      <Card className="gap-0 border border-border py-3 shadow-none ring-0">
                        <CardContent className="px-4 py-0">
                          <div className="mb-2 flex items-center gap-2">
                            <span className="text-sm font-semibold text-muted-foreground">Approaching Long-Term</span>
                            <Badge
                              variant="outline"
                              className="h-5 border-amber-500/40 bg-amber-500/10 text-[10px] text-amber-800 dark:text-amber-200"
                            >
                              {insights.approaching_lt?.length ?? 0}
                            </Badge>
                          </div>
                          {(insights.approaching_lt?.length ?? 0) === 0 ? (
                            <p className="text-xs text-muted-foreground">None near 365-day threshold</p>
                          ) : (
                            <div className="flex flex-col gap-1">
                              {insights.approaching_lt.slice(0, 5).map((p) => (
                                <div key={p.symbol} className="flex justify-between gap-2">
                                  <span className="font-mono text-xs">{p.symbol}</span>
                                  <span className={cn('text-xs', semanticTextColorClass('yellow.400'))}>
                                    {p.days_to_lt}d to LT
                                  </span>
                                </div>
                              ))}
                            </div>
                          )}
                        </CardContent>
                      </Card>

                      <Card className="gap-0 border border-border py-3 shadow-none ring-0">
                        <CardContent className="px-4 py-0">
                          <div className="mb-2 flex items-center gap-2">
                            <span className="text-sm font-semibold text-muted-foreground">Concentration Risk</span>
                            <Badge
                              variant="outline"
                              className="h-5 border-orange-500/40 bg-orange-500/10 text-[10px] text-orange-800 dark:text-orange-200"
                            >
                              {insights.concentration_warnings?.length ?? 0}
                            </Badge>
                          </div>
                          {(insights.concentration_warnings?.length ?? 0) === 0 ? (
                            <p className="text-xs text-muted-foreground">Well-diversified</p>
                          ) : (
                            <div className="flex flex-col gap-1">
                              {insights.concentration_warnings.slice(0, 5).map((w) => (
                                <div key={w.symbol} className="flex justify-between gap-2">
                                  <span className="font-mono text-xs">{w.symbol}</span>
                                  <span className={cn('text-xs', semanticTextColorClass('orange.500'))}>
                                    {w.pct_of_portfolio}%
                                  </span>
                                </div>
                              ))}
                            </div>
                          )}
                        </CardContent>
                      </Card>
                    </div>
                  )}

                {rawAccounts.length > 0 && (
                  <div className="flex flex-wrap items-center gap-4 rounded-md bg-muted/50 px-3 py-2">
                    {rawAccounts.map(
                      (a: {
                        id?: number;
                        account_number?: string;
                        broker?: string;
                        last_successful_sync?: string | null;
                      }) => {
                        const syncTime = a.last_successful_sync ? new Date(a.last_successful_sync) : null;
                        const ageMs = syncTime ? Date.now() - syncTime.getTime() : Infinity;
                        const ageHours = ageMs / (1000 * 60 * 60);
                        const dotClass =
                          ageHours < 1
                            ? 'bg-green-500'
                            : ageHours < 24
                              ? 'bg-amber-400'
                              : 'bg-red-400';
                        return (
                          <div key={a.id} className="flex items-center gap-1">
                            <span className={cn('size-1.5 shrink-0 rounded-full', dotClass)} aria-hidden />
                            <span className="text-xs text-muted-foreground">
                              {(a.broker || '').toUpperCase()} ···{(a.account_number || '').slice(-4)} ·{' '}
                              {syncTime ? timeAgo(a.last_successful_sync) : 'Never'}
                            </span>
                          </div>
                        );
                      },
                    )}
                    <Button
                      size="xs"
                      variant="outline"
                      className="ml-auto gap-1"
                      onClick={() => syncMutation.mutate()}
                      disabled={syncMutation.isPending}
                    >
                      {syncMutation.isPending ? (
                        <Loader2 className="size-2.5 animate-spin" aria-hidden />
                      ) : (
                        <RefreshCw className="size-2.5" aria-hidden />
                      )}
                      Sync
                    </Button>
                  </div>
                )}

                <Card className="gap-0 border border-border shadow-none ring-0">
                  <CardContent className="py-4">
                    <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                      <div className="flex flex-wrap items-center gap-3">
                        <span className="text-sm font-semibold text-muted-foreground">
                          {showBenchmark ? 'Performance vs SPY' : 'Value over time'}
                        </span>
                        <Button
                          size="xs"
                          variant={showBenchmark ? 'default' : 'outline'}
                          onClick={() => setShowBenchmark((v) => !v)}
                        >
                          vs SPY
                        </Button>
                      </div>
                      <div className="flex flex-wrap gap-1">
                        {PERIODS.map((p) => (
                          <Button
                            key={p.key}
                            size="xs"
                            variant={historyPeriod === p.key ? 'default' : 'outline'}
                            onClick={() => setHistoryPeriod(p.key)}
                          >
                            {p.label}
                          </Button>
                        ))}
                      </div>
                    </div>
                    {historyQuery.isPending ? (
                      <p className="text-sm text-muted-foreground">Loading…</p>
                    ) : equityCurveData.length > 0 ? (
                      showBenchmark ? (
                        <ResponsiveContainer width="100%" height={300}>
                          <ComposedChart data={equityCurveData} margin={{ top: 8, right: 8, left: 8, bottom: 8 }}>
                            <defs>
                              <linearGradient id="portfolioPctGradient" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="0%" stopColor={colors.area1} stopOpacity={0.2} />
                                <stop offset="100%" stopColor={colors.area1} stopOpacity={0.02} />
                              </linearGradient>
                            </defs>
                            <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                            <YAxis tick={{ fontSize: 10 }} tickFormatter={(v) => `${v.toFixed(0)}%`} />
                              <Tooltip
                                formatter={(v, name) =>
                                  [
                                    `${Number(v ?? 0).toFixed(2)}%`,
                                    name === 'portfolio_pct' ? 'Portfolio' : 'SPY',
                                  ] as [React.ReactNode, string]
                                }
                                labelFormatter={(d) => String(d)}
                              />
                            <Area
                              type="monotone"
                              dataKey="portfolio_pct"
                              stroke={colors.area1}
                              fill="url(#portfolioPctGradient)"
                              strokeWidth={2}
                              name="portfolio_pct"
                            />
                            <Line
                              type="monotone"
                              dataKey="spy_pct"
                              stroke={colors.area2}
                              strokeWidth={1.5}
                              strokeDasharray="4 3"
                              dot={false}
                              name="spy_pct"
                            />
                          </ComposedChart>
                        </ResponsiveContainer>
                      ) : (
                        <ResponsiveContainer width="100%" height={300}>
                          <AreaChart data={equityCurveData} margin={{ top: 8, right: 8, left: 8, bottom: 8 }}>
                            <defs>
                              <linearGradient id="portfolioValueGradient" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="0%" stopColor={colors.area1} stopOpacity={0.25} />
                                <stop offset="100%" stopColor={colors.area1} stopOpacity={0.02} />
                              </linearGradient>
                            </defs>
                            <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                            <YAxis
                              tick={{ fontSize: 10 }}
                              tickFormatter={(v) => formatMoney(v, currency, { maximumFractionDigits: 0 })}
                            />
                              <Tooltip
                                formatter={(v) => formatMoney(Number(v ?? 0), currency) as React.ReactNode}
                                labelFormatter={(d) => String(d)}
                              />
                            <Area
                              type="monotone"
                              dataKey="total_value"
                              stroke={colors.area1}
                              fill="url(#portfolioValueGradient)"
                              strokeWidth={1.5}
                            />
                          </AreaChart>
                        </ResponsiveContainer>
                      )
                    ) : (
                      <p className="text-sm text-muted-foreground">
                        No performance history yet. Snapshots are recorded after sync.
                      </p>
                    )}
                  </CardContent>
                </Card>

                <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                  <Card className="gap-0 border border-border shadow-none ring-0">
                    <CardContent className="py-4">
                      <p className="mb-3 text-sm font-semibold text-muted-foreground">Allocation (by sector)</p>
                      {filteredSector.length > 0 ? (
                        <ResponsiveContainer width="100%" height={240}>
                          <PieChart>
                            <Pie
                              data={filteredSector}
                              dataKey="value"
                              nameKey="name"
                              cx="40%"
                              cy="50%"
                              innerRadius={55}
                              outerRadius={85}
                              paddingAngle={2}
                            >
                              {filteredSector.map((_, i) => (
                                <Cell key={i} fill={SECTOR_PALETTE[i % SECTOR_PALETTE.length]} />
                              ))}
                            </Pie>
                            <Tooltip formatter={(v) => formatMoney(Number(v ?? 0), currency) as React.ReactNode} />
                            <Legend
                              layout="vertical"
                              align="right"
                              verticalAlign="middle"
                              iconType="circle"
                              iconSize={8}
                              formatter={(value: string) => {
                                const total = filteredSector.reduce((s, x) => s + x.value, 0);
                                const item = filteredSector.find((s) => s.name === value);
                                const pct = item && total > 0 ? ((item.value / total) * 100).toFixed(0) : '0';
                                return (
                                  <span className="text-[11px] text-muted-foreground">
                                    {value} {pct}%
                                  </span>
                                );
                              }}
                            />
                          </PieChart>
                        </ResponsiveContainer>
                      ) : (
                        <p className="text-sm text-muted-foreground">No sector data</p>
                      )}
                    </CardContent>
                  </Card>

                  {accounts.length > 0 ? (
                    <Card className="gap-0 border border-border shadow-none ring-0">
                      <CardContent className="py-4">
                        <p className="mb-3 text-sm font-semibold text-muted-foreground">Accounts</p>
                        <div
                          className={cn(
                            'grid gap-2',
                            accounts.length > 2 ? 'grid-cols-1 md:grid-cols-2' : 'grid-cols-1',
                          )}
                        >
                          {accounts.map((acc) => {
                            const raw = rawAccounts.find(
                              (a: { account_number?: string; id?: unknown }) =>
                                (a.account_number ?? String(a.id)) === acc.account_id,
                            );
                            const bal = balances.find((b: { account_id?: number }) => b.account_id === raw?.id);
                            const nlv = Number(bal?.net_liquidation ?? 0);
                            const displayValue = nlv > 0 ? nlv : acc.total_value;
                            const isSelected = filterState.selectedAccount === acc.account_id;
                            return (
                              <button
                                type="button"
                                key={acc.account_id}
                                className={cn(
                                  'cursor-pointer rounded-lg border p-3 text-left transition-colors',
                                  isSelected
                                    ? 'border-primary ring-1 ring-primary/20'
                                    : 'border-border hover:border-primary/40 hover:bg-muted/50',
                                )}
                                onClick={() => filterState.setSelectedAccount(isSelected ? 'all' : acc.account_id)}
                              >
                                <div className="mb-1 flex justify-between gap-2">
                                  <div className="flex items-center gap-2">
                                    <span className="text-sm font-semibold">{acc.broker}</span>
                                    <Badge variant="secondary" className="h-5 text-[10px]">
                                      {(raw as { account_type?: string })?.account_type ?? 'TAXABLE'}
                                    </Badge>
                                  </div>
                                  <span className="font-mono text-xs text-muted-foreground">
                                    ···{(acc.account_id || '').slice(-4)}
                                  </span>
                                </div>
                                <p className="text-lg font-bold">
                                  {formatMoney(displayValue, currency, { maximumFractionDigits: 0 })}
                                </p>
                                <p className="text-xs text-muted-foreground">
                                  {acc.positions_count} positions · {timeAgo(raw?.last_successful_sync)}
                                </p>
                              </button>
                            );
                          })}
                        </div>
                      </CardContent>
                    </Card>
                  ) : null}
                </div>

                <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                  <Card className="gap-0 border border-border shadow-none ring-0">
                    <CardContent className="py-4">
                      <p className="mb-3 text-sm font-semibold text-muted-foreground">
                        Stage distribution (portfolio)
                      </p>
                      <StageBar counts={filteredStage.counts} total={filteredStage.total} />
                    </CardContent>
                  </Card>

                  <Card className="gap-0 border border-border shadow-none ring-0">
                    <CardContent className="py-4">
                      <p className="mb-3 text-sm font-semibold text-muted-foreground">Top movers</p>
                      <div className="flex flex-wrap items-start gap-6">
                        <div className="flex flex-col gap-1">
                          <span className={cn('text-xs', semanticTextColorClass('status.success'))}>
                            Top contributors
                          </span>
                          {filteredMovers.contributors.length === 0 ? (
                            <span className="text-xs text-muted-foreground">—</span>
                          ) : (
                            filteredMovers.contributors.map((p) => (
                              <div key={p.symbol} className="flex gap-2">
                                <span className="font-mono text-xs">{p.symbol}</span>
                                <PnlText
                                  value={Number(p.unrealized_pnl ?? 0)}
                                  format="currency"
                                  fontSize="xs"
                                  currency={currency}
                                />
                              </div>
                            ))
                          )}
                        </div>
                        <div className="flex flex-col gap-1">
                          <span className={cn('text-xs', semanticTextColorClass('status.danger'))}>Top detractors</span>
                          {filteredMovers.detractors.length === 0 ? (
                            <span className="text-xs text-muted-foreground">—</span>
                          ) : (
                            filteredMovers.detractors.map((p) => (
                              <div key={p.symbol} className="flex gap-2">
                                <span className="font-mono text-xs">{p.symbol}</span>
                                <PnlText
                                  value={Number(p.unrealized_pnl ?? 0)}
                                  format="currency"
                                  fontSize="xs"
                                  currency={currency}
                                />
                              </div>
                            ))
                          )}
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </div>

                {pos.length > 0 && (
                  <Card className="gap-0 border border-border py-3 shadow-none ring-0">
                    <CardContent className="py-2">
                      <div className="mb-2 flex justify-between gap-2">
                        <span className="text-sm font-semibold text-muted-foreground">Top Holdings</span>
                        <Link
                          to="/portfolio/holdings"
                          className="text-xs text-primary hover:underline"
                        >
                          View all
                        </Link>
                      </div>
                      <div className="flex flex-wrap gap-3">
                        {[...pos]
                          .sort((a, b) => Number(b.market_value ?? 0) - Number(a.market_value ?? 0))
                          .slice(0, 6)
                          .map((p) => {
                            const pnl = Number(p.unrealized_pnl ?? 0);
                            const mv = Number(p.market_value ?? 0);
                            const weight = filteredTotal > 0 ? ((mv / filteredTotal) * 100).toFixed(1) : '0';
                            return (
                              <div
                                key={p.symbol}
                                className="min-w-[120px] flex-1 rounded-md border border-border p-2"
                              >
                                <div className="mb-1 flex justify-between gap-1">
                                  <span className="font-mono text-xs font-semibold">{p.symbol}</span>
                                  <span className="text-xs text-muted-foreground">{weight}%</span>
                                </div>
                                <p className="text-sm font-bold">
                                  {formatMoney(mv, currency, { maximumFractionDigits: 0 })}
                                </p>
                                <PnlText value={pnl} format="currency" fontSize="xs" currency={currency} />
                              </div>
                            );
                          })}
                      </div>
                    </CardContent>
                  </Card>
                )}

                {(dividendData.trailing_12m_income != null ||
                  riskData.beta != null ||
                  marginItems.length > 0) && (
                  <details className="group">
                    <summary className="cursor-pointer py-2 text-sm font-semibold text-muted-foreground">
                      Dividends, Risk & Margin
                    </summary>
                    <div className="mt-2 flex flex-col gap-4">
                      <p className="text-sm font-semibold text-muted-foreground">Dividend Income</p>
                      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-4">
                        <StatCard
                          label="Trailing 12M Income"
                          value={formatMoney(dividendData.trailing_12m_income ?? 0, currency, {
                            maximumFractionDigits: 0,
                          })}
                          color="status.success"
                        />
                        <StatCard
                          label="Forward Yield"
                          value={`${dividendData.estimated_forward_yield_pct ?? 0}%`}
                        />
                        <StatCard
                          label="Top Payer"
                          value={dividendData.top_payers?.[0]?.symbol ?? '-'}
                          sub={
                            dividendData.top_payers?.[0]
                              ? formatMoney(dividendData.top_payers[0].annual_income, currency, {
                                  maximumFractionDigits: 0,
                                })
                              : ''
                          }
                        />
                        <StatCard
                          label="Upcoming Ex-Date"
                          value={dividendData.upcoming_ex_dates?.[0]?.symbol ?? 'None'}
                          sub={dividendData.upcoming_ex_dates?.[0]?.est_ex_date ?? ''}
                        />
                      </div>

                      <p className="text-sm font-semibold text-muted-foreground">Risk Profile</p>
                      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-5">
                        <StatCard label="Beta" value={riskData.beta ?? 1.0} />
                        <StatCard
                          label="Volatility (Ann.)"
                          value={`${riskData.volatility ?? 0}%`}
                          color={Number(riskData.volatility) > 30 ? 'status.danger' : undefined}
                        />
                        <StatCard label="Sharpe Ratio" value={riskData.sharpe_ratio ?? 0} />
                        <StatCard
                          label="Top 5 Weight"
                          value={`${riskData.top5_weight ?? 0}%`}
                          sub={riskData.concentration_label ?? ''}
                        />
                        <StatCard label="HHI" value={riskData.hhi ?? 0} sub={riskData.concentration_label ?? ''} />
                      </div>

                      {marginItems.length > 0 && (
                        <Card className="gap-0 border border-border shadow-none ring-0">
                          <CardContent className="py-4">
                            <p className="mb-3 text-sm font-semibold text-muted-foreground">Margin & Interest</p>
                            <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-4">
                              {marginItems.slice(0, 4).map((m) => (
                                <div key={String(m.id)} className="rounded-md border border-border p-2">
                                  <p className="text-xs text-muted-foreground">
                                    {String(m.from_date)} – {String(m.to_date)}
                                  </p>
                                  <p className="text-sm font-bold">
                                    {formatMoney(Number(m.interest_accrued ?? 0), currency)}
                                  </p>
                                  {m.interest_rate != null && (
                                    <p className="text-xs text-muted-foreground">
                                      Rate: {(Number(m.interest_rate) * 100).toFixed(2)}%
                                    </p>
                                  )}
                                  {m.ending_balance != null && (
                                    <p className="text-xs text-muted-foreground">
                                      Balance:{' '}
                                      {formatMoney(Number(m.ending_balance), currency, { maximumFractionDigits: 0 })}
                                    </p>
                                  )}
                                </div>
                              ))}
                            </div>
                          </CardContent>
                        </Card>
                      )}
                    </div>
                  </details>
                )}

                {balances.some((b) => b.initial_margin_req != null) && (
                  <div>
                    <div className="mb-3 flex items-center gap-2">
                      <span className="text-sm font-semibold text-muted-foreground">Account Health</span>
                      {liveData.is_live && (
                        <Badge className="h-5 bg-emerald-500/15 text-[10px] text-emerald-700 dark:text-emerald-300">
                          Live
                        </Badge>
                      )}
                    </div>
                    <div className="flex flex-wrap gap-3">
                      {balances.map((b) => {
                        const marginUtil = Number(b.margin_utilization_pct ?? 0);
                        const marginColor =
                          marginUtil > 60
                            ? 'status.danger'
                            : marginUtil > 30
                              ? 'yellow.400'
                              : 'status.success';
                        const netLiq =
                          liveData.is_live && liveData.net_liquidation != null && balances.length === 1
                            ? Number(liveData.net_liquidation)
                            : Number(b.net_liquidation ?? 0);
                        return (
                          <React.Fragment key={String(b.account_id)}>
                            <StatCard
                              label={`Cash (${String(b.broker ?? '')})`}
                              value={formatMoney(
                                Number(b.cash_balance ?? b.total_cash_value ?? 0),
                                currency,
                                { maximumFractionDigits: 0 },
                              )}
                              sub={
                                b.available_funds != null
                                  ? `Avail ${formatMoney(b.available_funds as number, currency, { maximumFractionDigits: 0 })}`
                                  : undefined
                              }
                            />
                            <StatCard
                              label="Net Liquidation"
                              value={formatMoney(netLiq, currency, { maximumFractionDigits: 0 })}
                            />
                            <StatCard
                              label="Buying Power"
                              value={formatMoney(Number(b.buying_power ?? 0), currency, { maximumFractionDigits: 0 })}
                            />
                            {b.initial_margin_req != null && (
                              <StatCard
                                label="Margin Used"
                                value={`${marginUtil.toFixed(1)}%`}
                                color={marginColor}
                                sub={`Init ${formatMoney(Number(b.initial_margin_req), currency, { maximumFractionDigits: 0 })}`}
                              />
                            )}
                            {b.leverage != null && (
                              <StatCard label="Leverage" value={`${Number(b.leverage).toFixed(2)}x`} />
                            )}
                            {b.cushion != null && (
                              <StatCard label="Cushion" value={`${(Number(b.cushion) * 100).toFixed(1)}%`} />
                            )}
                          </React.Fragment>
                        );
                      })}
                    </div>
                  </div>
                )}
              </>
            );
          })()}
        </div>
      </Page>
      <ChartSlidePanel symbol={chartSymbol} onClose={() => setChartSymbol(null)} />
    </ChartContext.Provider>
  );
};

export default PortfolioOverview;
