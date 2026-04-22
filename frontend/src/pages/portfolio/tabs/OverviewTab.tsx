import React, { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Loader2, RefreshCw, TriangleAlert } from 'lucide-react';
import { ChartContext, ChartSlidePanel } from '../../../components/market/SymbolChartUI';
import StatCard from '../../../components/shared/StatCard';
import StageBar from '../../../components/shared/StageBar';
import PnlText from '../../../components/shared/PnlText';
import { PageHeader } from '../../../components/ui/Page';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { cn } from '@/lib/utils';
import { semanticTextColorClass } from '@/lib/semantic-text-color';
import { useAccountFilter } from '../../../hooks/useAccountFilter';
import { DashboardResponse } from '../../../services/api';
import {
  usePortfolioOverview,
  usePositions,
  usePortfolioSync,
  usePortfolioInsights,
  useAccountBalances,
  useLiveSummary,
  usePnlSummary,
} from '../../../hooks/usePortfolio';
import { useUserPreferences } from '../../../hooks/useUserPreferences';
import { formatMoney } from '../../../utils/format';
import {
  buildAccountsFromPositions,
  stageCountsFromPositions,
  sectorAllocationFromPositions,
  topMoversFromPositions,
  timeAgo,
} from '../../../utils/portfolio';
import { StatCardSkeleton } from '../../../components/shared/Skeleton';
import { DailyNarrative } from '../../../components/portfolio/DailyNarrative';
import type { AccountData } from '../../../hooks/useAccountFilter';
import type { EnrichedPosition } from '../../../types/portfolio';
import { SECTOR_PALETTE } from '../../../constants/chart';
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Legend,
  Tooltip,
} from 'recharts';

const OverviewTab: React.FC = () => {
  const [chartSymbol, setChartSymbol] = useState<string | null>(null);
  const { currency } = useUserPreferences();
  const overview = usePortfolioOverview();
  const positionsQuery = usePositions();
  const syncMutation = usePortfolioSync();
  const insightsQuery = usePortfolioInsights();
  const insights = insightsQuery.data;
  const balancesQuery = useAccountBalances();
  const balances = balancesQuery.data;
  const liveQuery = useLiveSummary();
  const liveData = liveQuery.data;
  const positionRows = (positionsQuery.data as EnrichedPosition[] | undefined) ?? [];
  const dashboard = overview.summary.data as DashboardResponse | undefined;
  const rawAccounts = overview.accountsData ?? [];

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
        positionRows,
      ),
    [rawAccounts, positionRows],
  );

  const filterState = useAccountFilter(positionRows as import('../../../hooks/useAccountFilter').FilterableItem[], accounts);
  const filteredPositions = filterState.filteredData as EnrichedPosition[];

  const pnlSummaryQuery = usePnlSummary(
    filterState.selectedAccount === 'all' ? undefined : filterState.selectedAccount,
  );
  const pnlSummary = pnlSummaryQuery.data;

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
                <Link to="/settings/connections" className="font-semibold underline underline-offset-2">
                  Reconnect in Settings
                </Link>
              </AlertDescription>
            </Alert>
          ) : null}

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
            const balanceRows = (balancesQuery.isError ? [] : (balances ?? [])) as Array<Record<string, unknown>>;
            const filteredBalances =
              filterState.selectedAccount === 'all'
                ? balanceRows
                : balanceRows.filter((b: Record<string, unknown>) => {
                    const raw = rawAccounts.find((a: { id?: number }) => a.id === b.account_id);
                    return (
                      raw &&
                      ((raw as { account_number?: string }).account_number === filterState.selectedAccount ||
                        String((raw as { id?: unknown }).id) === filterState.selectedAccount)
                    );
                  });
            const nlvTotal = filteredBalances.reduce(
              (s: number, b: Record<string, unknown>) => s + Number(b.net_liquidation ?? 0),
              0,
            );
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
                            ? 'bg-[rgb(var(--status-success))]'
                            : ageHours < 24
                              ? 'bg-[rgb(var(--status-warning))]'
                              : 'bg-[rgb(var(--status-danger))]';
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
              </>
            );
          })()}
          {balancesQuery.isError ? (
            <p className={cn('text-sm', semanticTextColorClass('status.danger'))}>Failed to load account balances</p>
          ) : null}
        </div>
      <ChartSlidePanel symbol={chartSymbol} onClose={() => setChartSymbol(null)} />
    </ChartContext.Provider>
  );
};

export default OverviewTab;
