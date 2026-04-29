"use client";

import React, { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import type { UTCTimestamp } from 'lightweight-charts';
import Link from 'next/link';
import { TriangleAlert } from 'lucide-react';
import { ChartContext, ChartSlidePanel } from '@/components/market/SymbolChartUI';
import StatCard from '@/components/shared/StatCard';
import StageBar from '@/components/shared/StageBar';
import PnlText from '@/components/shared/PnlText';
import { PageHeader } from '@paperwork-labs/ui';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { cn } from '@/lib/utils';
import { semanticTextColorClass } from '@/lib/semantic-text-color';
import { useAccountFilter } from '@/hooks/useAccountFilter';
import { DashboardResponse, marketDataApi } from '@/services/api';
import {
  usePortfolioOverview,
  usePositions,
  usePortfolioInsights,
  useAccountBalances,
  useLiveSummary,
  usePnlSummary,
  usePortfolioPerformanceHistory,
} from '@/hooks/usePortfolio';
import { useAccountContext } from '@/context/AccountContext';
import { useUserPreferences } from '@/hooks/useUserPreferences';
import { formatMoney } from '@/utils/format';
import {
  buildAccountsFromPositions,
  brokerAccountRowKey,
  normalizeBrokerAccountsForPositions,
  stageCountsFromPositions,
  sectorAllocationFromPositions,
  topMoversFromPositions,
  timeAgo,
} from '@/utils/portfolio';
import type { RawBrokerAccountInput } from '@/utils/portfolio';
import { StatCardSkeleton } from '@/components/shared/Skeleton';
import { DailyNarrative } from '@/components/portfolio/DailyNarrative';
import { SyncStatusStrip } from '@/components/portfolio/SyncStatusStrip';
import DisciplineTrajectoryTile from '@/components/portfolio/DisciplineTrajectoryTile';
import DisciplineTrajectoryMultiAccount from '@/components/portfolio/DisciplineTrajectoryMultiAccount';
import TierGate from '@/components/billing/TierGate';
import type { AccountData } from '@/hooks/useAccountFilter';
import type { EnrichedPosition } from '@/types/portfolio';
import { SECTOR_PALETTE } from '@/constants/chart';
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Legend,
  Tooltip,
} from 'recharts';
import {
  PortfolioEquityChart,
  type PortfolioEquityChartPoint,
} from '@/components/charts/PortfolioEquityChart';
import { DrawdownUnderwater } from '@/components/charts/DrawdownUnderwater';
import {
  buildAlignedEquityPoints,
  buildSpyCloseMap,
  pickHistoryPeriodKey,
} from '@/lib/portfolioEquitySeries';

const OverviewTab: React.FC = () => {
  const [chartSymbol, setChartSymbol] = useState<string | null>(null);
  const { currency } = useUserPreferences();
  const { selected: globalSelected } = useAccountContext();
  // Thread the global account selector into the dashboard summary so the
  // top KPIs (value, day P&L) scope to the selected account. When "all" or
  // a bucket category ('taxable'/'ira'/'hsa') is chosen, leave summary
  // portfolio-wide — bucket scoping happens client-side via useAccountFilter.
  const overviewAccountId =
    globalSelected === 'all' ||
    globalSelected === 'taxable' ||
    globalSelected === 'ira' ||
    globalSelected === 'hsa'
      ? undefined
      : globalSelected;
  const overview = usePortfolioOverview(overviewAccountId);
  const positionsQuery = usePositions();
  const insightsQuery = usePortfolioInsights();
  const insights = insightsQuery.data;
  const balancesQuery = useAccountBalances();
  const balances = balancesQuery.data;
  const liveQuery = useLiveSummary(overviewAccountId);
  const liveData = liveQuery.data;
  const positionRows = (positionsQuery.data as EnrichedPosition[] | undefined) ?? [];
  const dashboard = overview.summary.data as DashboardResponse | undefined;
  const rawAccounts = Array.isArray(overview.accountsData) ? overview.accountsData : [];
  // Only tracked/enabled broker accounts render on the overview. The backend
  // returns both enabled and disabled rows from GET /accounts; untracked ones
  // previously leaked into the Accounts card as $0 tiles and skewed the
  // positions count. (Audit 2026-04-22 — founder pain #1.)
  const sanitizedBrokerRows = useMemo(
    () => {
      const enabledOnly = (rawAccounts as Array<RawBrokerAccountInput & { is_enabled?: boolean }>).filter(
        (a) => a.is_enabled !== false,
      );
      return normalizeBrokerAccountsForPositions(enabledOnly as RawBrokerAccountInput[]);
    },
    [rawAccounts],
  );

  const accounts: AccountData[] = useMemo(
    () => buildAccountsFromPositions(sanitizedBrokerRows, positionRows),
    [sanitizedBrokerRows, positionRows],
  );

  const filterState = useAccountFilter(positionRows as import('../../../hooks/useAccountFilter').FilterableItem[], accounts);
  const filteredPositions = filterState.filteredData as EnrichedPosition[];

  const trajectoryDbAccountId = useMemo((): number | undefined => {
    if (filterState.selectedAccount === 'all') return undefined;
    const raw = sanitizedBrokerRows.find(
      (a) =>
        a.account_number === filterState.selectedAccount ||
        String(a.id) === filterState.selectedAccount,
    );
    return typeof raw?.id === 'number' ? raw.id : undefined;
  }, [filterState.selectedAccount, sanitizedBrokerRows]);

  const pnlSummaryQuery = usePnlSummary(
    filterState.selectedAccount === 'all' ? undefined : filterState.selectedAccount,
  );
  const pnlSummary = pnlSummaryQuery.data;

  const [equityValueMode, setEquityValueMode] = useState<'usd' | 'pct'>('usd');
  const performanceAccountId =
    filterState.selectedAccount === 'all' ? undefined : filterState.selectedAccount;
  const performanceHistoryQuery = usePortfolioPerformanceHistory({ accountId: performanceAccountId });

  const historyRange = useMemo(() => {
    const d = performanceHistoryQuery.data;
    if (!d?.length) return null;
    const sorted = [...d]
      .map((p) => ({ t: String(p.date).slice(0, 10) }))
      .filter((x) => x.t.length >= 10)
      .sort((a, b) => a.t.localeCompare(b.t));
    if (!sorted.length) return null;
    const f = Date.parse(sorted[0].t);
    const l = Date.parse(sorted[sorted.length - 1].t);
    if (!Number.isFinite(f) || !Number.isFinite(l)) return null;
    return { firstMs: f, lastMs: l, period: pickHistoryPeriodKey(f, l) };
  }, [performanceHistoryQuery.data]);

  const spyHistoryQuery = useQuery({
    queryKey: ['spyHistoryPortfolioHero', historyRange?.period],
    queryFn: async () => marketDataApi.getHistory('SPY', historyRange?.period ?? '1y', '1d'),
    enabled: Boolean(
      historyRange &&
        !performanceHistoryQuery.isPending &&
        !performanceHistoryQuery.isError &&
        (performanceHistoryQuery.data?.length ?? 0) > 0,
    ),
    staleTime: 60_000,
  });

  const spyBars = useMemo(() => {
    const r = spyHistoryQuery.data;
    if (r == null) return [] as Array<{ time?: string; date?: string; close: number }>;
    const raw = (r as { bars?: unknown; data?: unknown }).bars ?? (r as { data?: unknown }).data;
    if (!Array.isArray(raw)) return [];
    return raw as Array<{ time?: string; date?: string; close: number }>;
  }, [spyHistoryQuery.data]);

  const spyMap = useMemo(() => buildSpyCloseMap(spyBars), [spyBars]);

  const equityChartPack = useMemo(() => {
    const d = performanceHistoryQuery.data;
    if (!d?.length) {
      return {
        points: [] as PortfolioEquityChartPoint[],
        hasBenchmark: false,
      };
    }
    if (spyHistoryQuery.isError || spyHistoryQuery.isPending || spyBars.length === 0) {
      const { points } = buildAlignedEquityPoints(d, new Map(), equityValueMode);
      return {
        hasBenchmark: false,
        points: points.map((p) => ({
          time: p.timeUtc as UTCTimestamp,
          equity: p.equity,
          benchmark: null,
        })),
      };
    }
    const { points, hasBenchmark: hb } = buildAlignedEquityPoints(d, spyMap, equityValueMode);
    return {
      hasBenchmark: hb,
      points: points.map((p) => ({
        time: p.timeUtc as UTCTimestamp,
        equity: p.equity,
        benchmark: p.benchmark,
      })),
    };
  }, [
    performanceHistoryQuery.data,
    spyMap,
    equityValueMode,
    spyHistoryQuery.isError,
    spyHistoryQuery.isPending,
    spyBars.length,
  ]);

  const refetchPerformanceBlock = () => {
    void performanceHistoryQuery.refetch();
    void spyHistoryQuery.refetch();
  };

  const performanceError =
    performanceHistoryQuery.error instanceof Error ? performanceHistoryQuery.error : null;

  const summary = (dashboard?.data?.summary ?? dashboard?.summary ?? dashboard) as
    | import('../../../services/api').DashboardSummary
    | undefined;
  const dayChange = Number(summary?.day_change ?? 0);
  const dayChangePct = Number(summary?.day_change_pct ?? 0);

  const openChart = (symbol: string) => setChartSymbol(symbol);

  return (
    <ChartContext.Provider value={openChart}>
        <div className="flex flex-col gap-4">
          <DailyNarrative />

          <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
            <DisciplineTrajectoryTile accountId={trajectoryDbAccountId} />
            <TierGate
              feature="execution.multi_broker"
              fallback={
                <Card className="border-dashed border-border bg-muted/20 shadow-none ring-0">
                  <CardContent className="flex flex-col gap-2 py-4">
                    <p className="text-sm font-semibold text-muted-foreground">Consolidated trajectory</p>
                    <p className="text-sm text-muted-foreground">
                      Upgrade to Pro+ to consolidate across accounts.
                    </p>
                    <Button asChild size="sm" variant="outline" className="w-fit">
                      <Link href="/pricing">View plans</Link>
                    </Button>
                  </CardContent>
                </Card>
              }
            >
              <DisciplineTrajectoryMultiAccount />
            </TierGate>
          </div>

          {insightsQuery.isError ? (
            <p className={cn('text-sm', semanticTextColorClass('status.danger'))} role="alert">
              Failed to load portfolio insights.
            </p>
          ) : null}

          {liveQuery.isPending ? (
            <p className="text-sm text-muted-foreground">Checking live data status…</p>
          ) : liveQuery.isError ? (
            <Alert variant="destructive">
              <TriangleAlert className="size-4" aria-hidden />
              <AlertTitle className="text-sm">Could not load live status</AlertTitle>
              <AlertDescription className="text-sm">Try again after refreshing portfolio data.</AlertDescription>
            </Alert>
          ) : liveData && !liveData.is_live ? (
            <Alert className="border-[rgb(var(--status-warning)/0.4)] bg-[rgb(var(--status-warning)/0.1)] text-[rgb(var(--status-warning)/1)]">
              <TriangleAlert className="size-4" aria-hidden />
              <AlertTitle className="text-sm">Live data disconnected</AlertTitle>
              <AlertDescription className="text-sm">
                Portfolio values may be stale.{' '}
                <Link href="/settings/connections" className="font-semibold underline underline-offset-2">
                  Reconnect in Settings
                </Link>
              </AlertDescription>
            </Alert>
          ) : null}

          {(overview.isPending || positionsQuery.isPending) && (
            <div className="flex flex-col gap-4">
              <div className="order-1 md:order-2">
                <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
                  {[1, 2, 3, 4].map((i) => (
                    <StatCardSkeleton key={i} />
                  ))}
                </div>
              </div>
              <div className="order-2 md:order-1">
                <Card className="gap-0 border border-border shadow-none ring-0">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-base">Your portfolio over time</CardTitle>
                    <CardDescription>
                      All accounts combined unless a single account is filtered.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-2 pt-0">
                    <PortfolioEquityChart
                      isPending={performanceHistoryQuery.isPending}
                      isError={performanceHistoryQuery.isError}
                      error={performanceError}
                      onRetry={refetchPerformanceBlock}
                      data={performanceHistoryQuery.data}
                      chartPoints={equityChartPack.points}
                      hasBenchmark={equityChartPack.hasBenchmark}
                      valueMode={equityValueMode}
                      onValueModeChange={setEquityValueMode}
                    />
                    <DrawdownUnderwater
                      isPending={performanceHistoryQuery.isPending}
                      isError={performanceHistoryQuery.isError}
                      error={performanceError}
                      onRetry={refetchPerformanceBlock}
                      data={performanceHistoryQuery.data}
                    />
                  </CardContent>
                </Card>
              </div>
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
            const balanceRows = (balancesQuery.isError ? [] : (Array.isArray(balances) ? balances : [])) as Array<
              Record<string, unknown>
            >;
            const filteredBalances =
              filterState.selectedAccount === 'all'
                ? balanceRows
                : balanceRows.filter((b: Record<string, unknown>) => {
                    const raw = sanitizedBrokerRows.find((a) => a.id === b.account_id);
                    return (
                      raw &&
                      (raw.account_number === filterState.selectedAccount ||
                        String(raw.id) === filterState.selectedAccount)
                    );
                  });
            const nlvTotal = filteredBalances.reduce(
              (s: number, b: Record<string, unknown>) => s + Number(b.net_liquidation ?? 0),
              0,
            );
            const kpiValue = nlvTotal > 0 ? nlvTotal : filteredTotal;
            return (
              <>
                <div className="flex flex-col gap-4">
                  <div className="order-1 md:order-2">
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
                  </div>
                  <div className="order-2 md:order-1">
                    <Card className="gap-0 border border-border shadow-none ring-0">
                      <CardHeader className="pb-2">
                        <CardTitle className="text-base">Your portfolio over time</CardTitle>
                        <CardDescription>
                          All accounts combined unless a single account is filtered.
                        </CardDescription>
                      </CardHeader>
                      <CardContent className="space-y-2 pt-0">
                        <PortfolioEquityChart
                          isPending={performanceHistoryQuery.isPending}
                          isError={performanceHistoryQuery.isError}
                          error={performanceError}
                          onRetry={refetchPerformanceBlock}
                          data={performanceHistoryQuery.data}
                          chartPoints={equityChartPack.points}
                          hasBenchmark={equityChartPack.hasBenchmark}
                          valueMode={equityValueMode}
                          onValueModeChange={setEquityValueMode}
                        />
                        <DrawdownUnderwater
                          isPending={performanceHistoryQuery.isPending}
                          isError={performanceHistoryQuery.isError}
                          error={performanceError}
                          onRetry={refetchPerformanceBlock}
                          data={performanceHistoryQuery.data}
                        />
                      </CardContent>
                    </Card>
                  </div>
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
                              {(insights.harvest_candidates ?? []).slice(0, 5).map((c) => (
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
                              {(insights.approaching_lt ?? []).slice(0, 5).map((p) => (
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
                              {(insights.concentration_warnings ?? []).slice(0, 5).map((w) => (
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

                <SyncStatusStrip className="mb-4" showSyncButton={false} />

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
                            const raw = sanitizedBrokerRows.find(
                              (a) => brokerAccountRowKey(a) === acc.account_id,
                            );
                            const bal = balanceRows.find((b: { account_id?: number }) => b.account_id === raw?.id);
                            const nlv = Number(bal?.net_liquidation ?? 0);
                            const displayValue = nlv > 0 ? nlv : acc.total_value;
                            const isSelected = filterState.selectedAccount === acc.account_id;
                            return (
                              <button
                                type="button"
                                key={`${acc.broker}-${acc.account_id}`}
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
                        <Link href="/portfolio/holdings"
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
              </>
            );
          })()}
          {balancesQuery.isError ? (
            <div
              className="flex flex-col items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/5 p-4"
              role="alert"
            >
              <p className={cn('text-sm', semanticTextColorClass('status.danger'))}>Failed to load account balances</p>
              <Button type="button" size="sm" variant="outline" onClick={() => balancesQuery.refetch()}>
                Retry
              </Button>
            </div>
          ) : null}
        </div>
      <ChartSlidePanel symbol={chartSymbol} onClose={() => setChartSymbol(null)} />
    </ChartContext.Provider>
  );
};

export default OverviewTab;
