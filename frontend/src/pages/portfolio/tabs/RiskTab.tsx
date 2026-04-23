import React from 'react';
import { Coins, Landmark, Shield, Wallet } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import { semanticTextColorClass } from '@/lib/semantic-text-color';
import { CircuitBreakerBanner } from '../../../components/shared/CircuitBreakerBanner';
import StatCard from '../../../components/shared/StatCard';
import {
  useAccountBalances,
  useDividendSummary,
  useLiveSummary,
  useMarginInterest,
  useRiskMetrics,
} from '../../../hooks/usePortfolio';
import { useUserPreferences } from '../../../hooks/useUserPreferences';
import { formatMoney } from '../../../utils/format';

function SectionError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div
      className="flex flex-col items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/5 p-4"
      role="alert"
    >
      <p className={cn('text-sm', semanticTextColorClass('status.danger'))}>{message}</p>
      <Button type="button" size="sm" variant="outline" onClick={onRetry}>
        Retry
      </Button>
    </div>
  );
}

const RiskTab: React.FC = () => {
  const { currency } = useUserPreferences();
  const balancesQuery = useAccountBalances();
  const dividendQuery = useDividendSummary();
  const marginQuery = useMarginInterest();
  const liveQuery = useLiveSummary();
  const riskQuery = useRiskMetrics();

  const liveData = liveQuery.data;
  const dividendData = dividendQuery.data;
  const marginItems = Array.isArray(marginQuery.data) ? marginQuery.data : [];
  const riskData = riskQuery.data;
  const balances = Array.isArray(balancesQuery.data) ? balancesQuery.data : [];

  const riskSubPending = riskQuery.isPending;
  const riskSubError = riskQuery.isError;
  const riskSubReady = !riskSubPending && !riskSubError && riskQuery.data != null;

  return (
    <div className="flex flex-col gap-4">
      <CircuitBreakerBanner />

      <Card className="gap-0 border border-border shadow-none ring-0">
        <CardContent className="py-4">
          <p className="mb-3 text-sm font-semibold text-muted-foreground">Risk profile</p>
          {riskQuery.isPending ? (
            <p className="text-sm text-muted-foreground">Loading risk metrics…</p>
          ) : riskQuery.isError ? (
            <SectionError message="Failed to load risk metrics." onRetry={() => riskQuery.refetch()} />
          ) : riskData ? (
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-5">
              <StatCard
                label="Beta"
                value={riskData.beta != null ? Number(riskData.beta).toFixed(2) : '—'}
                sub={
                  riskSubPending
                    ? 'Loading…'
                    : riskSubError
                      ? '—'
                      : riskData.beta_portfolio_regression != null
                        ? `vs ${riskData.benchmark_symbol ?? 'SPY'} (${riskData.benchmark_overlap_days ?? 0}d regression)`
                        : riskData.beta_weighted_snapshot != null
                          ? 'Weighted per-symbol snapshot'
                          : 'Insufficient coverage'
                }
              />
              <StatCard
                label="Volatility (Ann.)"
                value={riskData.volatility != null ? `${Number(riskData.volatility).toFixed(1)}%` : '—'}
                sub={
                  riskSubPending
                    ? 'Loading…'
                    : riskSubError
                      ? '—'
                      : riskData.volatility == null
                        ? 'Need ≥20 daily snapshots'
                        : undefined
                }
                color={
                  riskData.volatility != null && Number(riskData.volatility) > 30 ? 'status.danger' : undefined
                }
              />
              <StatCard
                label="Sharpe Ratio"
                value={riskData.sharpe_ratio != null ? Number(riskData.sharpe_ratio).toFixed(2) : '—'}
                sub={
                  riskSubPending
                    ? 'Loading…'
                    : riskSubError
                      ? '—'
                      : riskData.sharpe_ratio == null
                        ? 'Need ≥90d history'
                        : undefined
                }
              />
              <StatCard
                label="Top 5 Weight"
                value={`${riskData.top5_weight ?? 0}%`}
                sub={
                  riskSubReady
                    ? (riskData.concentration_label ?? '')
                    : riskSubPending
                      ? 'Loading…'
                      : riskSubError
                        ? '—'
                        : ''
                }
              />
              <StatCard
                label="HHI"
                value={riskData.hhi ?? 0}
                sub={
                  riskSubReady
                    ? (riskData.concentration_label ?? '')
                    : riskSubPending
                      ? 'Loading…'
                      : riskSubError
                        ? '—'
                        : ''
                }
              />
            </div>
          ) : (
            <div className="flex flex-col items-center gap-2 py-2 text-center">
              <Shield className="size-7 text-muted-foreground" aria-hidden />
              <p className="text-sm text-foreground">
                Risk metrics are still warming up — we need a longer history before the profile
                is meaningful.
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="gap-0 border border-border shadow-none ring-0">
        <CardContent className="py-4">
          <p className="mb-3 text-sm font-semibold text-muted-foreground">Dividend income</p>
          {dividendQuery.isPending ? (
            <p className="text-sm text-muted-foreground">Loading dividend summary…</p>
          ) : dividendQuery.isError ? (
            <SectionError message="Failed to load dividend data." onRetry={() => dividendQuery.refetch()} />
          ) : dividendData &&
            (dividendData.trailing_12m_income != null ||
              (dividendData.top_payers && dividendData.top_payers.length > 0)) ? (
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-4">
              <StatCard
                label="Trailing 12M Income"
                value={formatMoney(dividendData.trailing_12m_income ?? 0, currency, {
                  maximumFractionDigits: 0,
                })}
                color="status.success"
              />
              <StatCard label="Forward Yield" value={`${dividendData.estimated_forward_yield_pct ?? 0}%`} />
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
          ) : (
            <div className="flex flex-col items-center gap-2 py-2 text-center">
              <Coins className="size-7 text-muted-foreground" aria-hidden />
              <p className="text-sm text-foreground">
                Dividend income has not shown up on the tape yet — your payers will land here
                first.
              </p>
              <p className="text-xs text-muted-foreground">Tip: Figures sync with your connected brokerage.</p>
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="gap-0 border border-border shadow-none ring-0">
        <CardContent className="py-4">
          <p className="mb-3 text-sm font-semibold text-muted-foreground">Margin and interest</p>
          {marginQuery.isPending ? (
            <p className="text-sm text-muted-foreground">Loading margin interest…</p>
          ) : marginQuery.isError ? (
            <SectionError message="Failed to load margin interest." onRetry={() => marginQuery.refetch()} />
          ) : marginItems.length > 0 ? (
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-4">
              {marginItems.slice(0, 4).map((m: Record<string, unknown>) => (
                <div key={String(m.id)} className="rounded-md border border-border p-2">
                  <p className="text-xs text-muted-foreground">
                    {String(m.from_date)} – {String(m.to_date)}
                  </p>
                  <p className="text-sm font-bold">{formatMoney(Number(m.interest_accrued ?? 0), currency)}</p>
                  {m.interest_rate != null && (
                    <p className="text-xs text-muted-foreground">Rate: {(Number(m.interest_rate) * 100).toFixed(2)}%</p>
                  )}
                  {m.ending_balance != null && (
                    <p className="text-xs text-muted-foreground">
                      Balance: {formatMoney(Number(m.ending_balance), currency, { maximumFractionDigits: 0 })}
                    </p>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="flex flex-col items-center gap-2 py-2 text-center">
              <Landmark className="size-7 text-muted-foreground" aria-hidden />
              <p className="text-sm text-foreground">
                Nothing borrowed, nothing due — you have no margin interest this window.
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="gap-0 border border-border shadow-none ring-0">
        <CardContent className="py-4">
          <div className="mb-3 flex items-center gap-2">
            <span className="text-sm font-semibold text-muted-foreground">Account health</span>
            {liveQuery.isSuccess && liveData?.is_live ? (
              <Badge className="h-5 bg-emerald-500/15 text-[10px] text-emerald-700 dark:text-emerald-300">Live</Badge>
            ) : null}
          </div>
          {balancesQuery.isPending ? (
            <p className="text-sm text-muted-foreground">Loading account health…</p>
          ) : balancesQuery.isError ? (
            <SectionError
              message="Failed to load balances for account health."
              onRetry={() => balancesQuery.refetch()}
            />
          ) : balances.some((b: Record<string, unknown>) => b.initial_margin_req != null) ? (
            <div className="flex flex-wrap gap-3">
              {(balances as Array<Record<string, unknown>>).map((b: Record<string, unknown>) => {
                const marginUtil = Number(b.margin_utilization_pct ?? 0);
                const marginColor =
                  marginUtil > 60 ? 'status.danger' : marginUtil > 30 ? 'yellow.400' : 'status.success';
                const netLiq =
                  liveData?.is_live && liveData.net_liquidation != null && balances.length === 1
                    ? Number(liveData.net_liquidation)
                    : Number(b.net_liquidation ?? 0);
                return (
                  <React.Fragment key={String(b.account_id)}>
                    <StatCard
                      label={`Cash (${String(b.broker ?? '')})`}
                      value={formatMoney(Number(b.cash_balance ?? b.total_cash_value ?? 0), currency, {
                        maximumFractionDigits: 0,
                      })}
                      sub={
                        b.available_funds != null
                          ? `Avail ${formatMoney(b.available_funds as number, currency, { maximumFractionDigits: 0 })}`
                          : undefined
                      }
                    />
                    <StatCard label="Net Liquidation" value={formatMoney(netLiq, currency, { maximumFractionDigits: 0 })} />
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
                    {b.leverage != null && <StatCard label="Leverage" value={`${Number(b.leverage).toFixed(2)}x`} />}
                    {b.cushion != null && (
                      <StatCard label="Cushion" value={`${(Number(b.cushion) * 100).toFixed(1)}%`} />
                    )}
                  </React.Fragment>
                );
              })}
            </div>
          ) : balances.length > 0 ? (
            <p className="text-sm text-muted-foreground">No margin accounts — health metrics appear when margin is enabled.</p>
          ) : (
            <div className="flex flex-col items-center gap-2 py-2 text-center">
              <Wallet className="size-7 text-muted-foreground" aria-hidden />
              <p className="text-sm text-foreground">No account balances in view — connect a broker to see the full picture.</p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default RiskTab;
