/**
 * Home — authenticated landing page.
 *
 * Four sections, top-down, each with explicit loading / error / empty / data
 * states (per `no-silent-fallback.mdc`):
 *   1. Regime hero
 *   2. Today's trade cards (top 3)
 *   3. Portfolio snapshot (NAV, day P&L, open positions, cash)
 *   4. Open positions vs plan (top 5)
 *
 * Missing plan fields (stop distance, days held) render as "—", never 0.
 * Portfolio sections are gated on `appSettings.portfolio_enabled`; market-
 * only users see a "Connect a broker" empty state instead of an API call.
 */
import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { isAxiosError } from 'axios';
import {
  ArrowRight,
  BarChart2,
  Briefcase,
  Link2,
  PieChart,
  Sparkles,
  Wallet,
} from 'lucide-react';

import apiClient, {
  marketDataApi,
  portfolioApi,
  unwrapResponse,
} from '@/services/api';
import type { DashboardResponse, DashboardSummary } from '@/services/api';
import { useAuth } from '@/context/AuthContext';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Page, PageHeader } from '@/components/ui/Page';
import { Skeleton } from '@/components/ui/skeleton';
import EmptyState from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { REGIME_HEX } from '@/constants/chart';
import { cn } from '@/lib/utils';
import { formatMoney, formatRelativeTime } from '@/utils/format';
import type { RegimeData } from '@/types/market';
import type { EnrichedPosition } from '@/types/portfolio';

const REGIME_LABELS: Record<string, string> = {
  R1: 'Bull',
  R2: 'Bull Extended',
  R3: 'Chop',
  R4: 'Bear Rally',
  R5: 'Bear',
};

/* ------------------------------------------------------------------ */
/*  Trade cards                                                        */
/* ------------------------------------------------------------------ */

interface TradeCard {
  id: string | number;
  symbol: string;
  thesis?: string | null;
  action?: string | null;
  score?: number | null;
  stage_label?: string | null;
  setup?: string | null;
  published_at?: string | null;
}

interface TradeCardsResponse {
  items: TradeCard[];
}

/* ------------------------------------------------------------------ */
/*  Section shell                                                      */
/* ------------------------------------------------------------------ */

interface SectionShellProps {
  title: string;
  description?: string;
  icon?: React.ElementType;
  action?: React.ReactNode;
  children: React.ReactNode;
}

function SectionShell({ title, description, icon: Icon, action, children }: SectionShellProps) {
  return (
    <Card variant="flat">
      <CardHeader className="flex flex-row items-start justify-between gap-3 pb-2">
        <div className="min-w-0">
          <CardTitle className="flex items-center gap-2">
            {Icon ? <Icon className="size-4 text-muted-foreground" aria-hidden /> : null}
            <span>{title}</span>
          </CardTitle>
          {description ? (
            <p className="mt-0.5 text-xs text-muted-foreground">{description}</p>
          ) : null}
        </div>
        {action ? <div className="shrink-0">{action}</div> : null}
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/*  Regime hero                                                        */
/* ------------------------------------------------------------------ */

function RegimeHero() {
  const regimeQuery = useQuery({
    queryKey: ['home-regime'],
    queryFn: () => marketDataApi.getCurrentRegime(),
    staleTime: 60_000,
    refetchInterval: 5 * 60_000,
  });

  const action = (
    <Button asChild variant="ghost" size="sm">
      <Link to="/market" aria-label="Open market dashboard">
        Markets
        <ArrowRight className="size-3.5" aria-hidden />
      </Link>
    </Button>
  );

  if (regimeQuery.isPending) {
    return (
      <SectionShell title="Market regime" icon={BarChart2} action={action}>
        <div className="flex flex-wrap items-center gap-4">
          <Skeleton className="h-7 w-24" />
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-4 w-40" />
        </div>
      </SectionShell>
    );
  }

  if (regimeQuery.isError) {
    return (
      <SectionShell title="Market regime" icon={BarChart2} action={action}>
        <ErrorState
          title="Couldn't load market regime"
          description="We were unable to reach the regime engine."
          error={regimeQuery.error}
          retry={() => {
            void regimeQuery.refetch();
          }}
        />
      </SectionShell>
    );
  }

  const raw = regimeQuery.data;
  if (raw == null) {
    return (
      <SectionShell title="Market regime" icon={BarChart2} action={action}>
        <EmptyState
          title="No regime data yet"
          description="The regime engine hasn't published a snapshot. Check back after the next pipeline run."
        />
      </SectionShell>
    );
  }

  const regime = raw as unknown as Partial<RegimeData>;
  const state = typeof regime.regime_state === 'string' ? regime.regime_state : null;
  if (!state) {
    return (
      <SectionShell title="Market regime" icon={BarChart2} action={action}>
        <EmptyState
          title="No regime data yet"
          description="The regime engine hasn't published a snapshot. Check back after the next pipeline run."
        />
      </SectionShell>
    );
  }

  const color = REGIME_HEX[state] ?? 'var(--muted-foreground)';
  const label = REGIME_LABELS[state] ?? state;
  const composite = typeof regime.composite_score === 'number' ? regime.composite_score : null;
  const updated = typeof regime.as_of_date === 'string' ? regime.as_of_date : null;
  const sizeMult = typeof regime.regime_multiplier === 'number' ? regime.regime_multiplier : null;
  const maxEq =
    typeof regime.max_equity_exposure_pct === 'number' ? regime.max_equity_exposure_pct : null;

  return (
    <SectionShell title="Market regime" icon={BarChart2} action={action}>
      <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
        <div className="flex items-center gap-2">
          <span
            className="inline-block size-3 rounded-sm"
            style={{ backgroundColor: color }}
            aria-hidden
          />
          <span className="font-mono text-xl font-semibold tracking-tight">{state}</span>
          <Badge
            variant="outline"
            className="border-transparent font-medium"
            style={{ backgroundColor: `${color}22`, color }}
          >
            {label}
          </Badge>
        </div>
        <div className="flex flex-col gap-0">
          <span className="text-[10px] uppercase tracking-wide text-muted-foreground">Score</span>
          <span className="font-mono text-sm font-semibold" data-testid="home-regime-score">
            {composite != null ? composite.toFixed(1) : '—'}
          </span>
        </div>
        {sizeMult != null ? (
          <div className="flex flex-col gap-0">
            <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
              Size mult
            </span>
            <span className="font-mono text-sm font-semibold">{sizeMult.toFixed(2)}×</span>
          </div>
        ) : null}
        {maxEq != null ? (
          <div className="flex flex-col gap-0">
            <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
              Max equity
            </span>
            <span className="font-mono text-sm font-semibold">{maxEq.toFixed(0)}%</span>
          </div>
        ) : null}
        <div className="ml-auto text-xs text-muted-foreground">
          {updated ? `As of ${updated}` : 'As of —'}
        </div>
      </div>
    </SectionShell>
  );
}

/* ------------------------------------------------------------------ */
/*  Trade cards                                                        */
/* ------------------------------------------------------------------ */

function TradeCardsSection() {
  const query = useQuery({
    queryKey: ['home-trade-cards'],
    queryFn: async (): Promise<TradeCardsResponse | null> => {
      try {
        const res = await apiClient.get<TradeCardsResponse>('/trade-cards/today');
        return res.data ?? { items: [] };
      } catch (err) {
        // The /trade-cards/today endpoint may not exist yet. A 404 is treated
        // as an empty state (feature not live), not a hard error. Every other
        // status propagates so the four-state contract still distinguishes
        // "loading" from "0 cards".
        if (isAxiosError(err) && err.response?.status === 404) {
          return null;
        }
        throw err;
      }
    },
    retry: false,
    staleTime: 60_000,
  });

  const action = (
    <Button asChild variant="ghost" size="sm">
      <Link to="/signals/picks" aria-label="Open signals feed">
        All picks
        <ArrowRight className="size-3.5" aria-hidden />
      </Link>
    </Button>
  );

  if (query.isPending) {
    return (
      <SectionShell
        title="Today's trade cards"
        description="Top candidates scored by the signal engine."
        icon={Sparkles}
        action={action}
      >
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-28 w-full" />
          ))}
        </div>
      </SectionShell>
    );
  }

  if (query.isError) {
    return (
      <SectionShell
        title="Today's trade cards"
        description="Top candidates scored by the signal engine."
        icon={Sparkles}
        action={action}
      >
        <ErrorState
          title="Couldn't load trade cards"
          description="The signal feed didn't respond."
          error={query.error}
          retry={() => {
            void query.refetch();
          }}
        />
      </SectionShell>
    );
  }

  const items = query.data?.items ?? [];
  const top = items.slice(0, 3);

  if (top.length === 0) {
    return (
      <SectionShell
        title="Today's trade cards"
        description="Top candidates scored by the signal engine."
        icon={Sparkles}
        action={action}
      >
        <EmptyState
          title="No cards yet today"
          description="Trade cards arrive here when candidates score. Check back after the next scan run."
        />
      </SectionShell>
    );
  }

  return (
    <SectionShell
      title="Today's trade cards"
      description="Top candidates scored by the signal engine."
      icon={Sparkles}
      action={action}
    >
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {top.map((card) => (
          <TradeCardTile key={String(card.id)} card={card} />
        ))}
      </div>
    </SectionShell>
  );
}

function TradeCardTile({ card }: { card: TradeCard }) {
  const action = (card.action ?? '').toUpperCase();
  const score = typeof card.score === 'number' ? card.score : null;
  return (
    <Card variant="flat" className="h-full">
      <CardContent className="flex h-full flex-col gap-2 py-3">
        <div className="flex items-baseline justify-between gap-2">
          <span className="font-mono text-lg font-semibold tracking-tight">{card.symbol}</span>
          {action ? (
            <Badge variant="outline" className="uppercase">
              {action}
            </Badge>
          ) : null}
        </div>
        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          {card.stage_label ? <span>Stage {card.stage_label}</span> : null}
          {card.setup ? <span>{card.setup}</span> : null}
          {score != null ? (
            <span className="ml-auto font-mono text-foreground">{score.toFixed(1)}</span>
          ) : null}
        </div>
        {card.thesis ? (
          <p className="line-clamp-3 text-xs text-muted-foreground">{card.thesis}</p>
        ) : null}
      </CardContent>
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/*  Portfolio snapshot                                                 */
/* ------------------------------------------------------------------ */

interface BalanceRow {
  account_id?: number;
  broker?: string;
  cash_balance?: number | string | null;
  total_cash_value?: number | string | null;
  net_liquidation?: number | string | null;
}

function toNumberOrNull(value: unknown): number | null {
  if (value == null) return null;
  if (typeof value === 'number') return Number.isFinite(value) ? value : null;
  if (typeof value === 'string' && value.trim() !== '') {
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

function pickSummary(payload: DashboardResponse | undefined): DashboardSummary | null {
  if (!payload) return null;
  return payload.data?.summary ?? payload.summary ?? null;
}

function pickTotalValue(payload: DashboardResponse | undefined): number | null {
  if (!payload) return null;
  const direct = (payload as unknown as Record<string, unknown>).data as
    | Record<string, unknown>
    | undefined;
  const nested = toNumberOrNull(direct?.total_value);
  if (nested != null) return nested;
  const summary = pickSummary(payload);
  return toNumberOrNull(summary?.total_market_value);
}

function PortfolioSnapshotSection() {
  const navigate = useNavigate();
  const { appSettings, appSettingsReady, user } = useAuth();
  const currency =
    typeof user?.currency_preference === 'string' && user.currency_preference.trim() !== ''
      ? user.currency_preference
      : 'USD';
  const portfolioEnabled = Boolean(appSettings?.portfolio_enabled);

  const dashboardQuery = useQuery({
    queryKey: ['home-portfolio-dashboard'],
    queryFn: () => portfolioApi.getDashboard(),
    enabled: appSettingsReady && portfolioEnabled,
    staleTime: 20_000,
  });

  const balancesQuery = useQuery<BalanceRow[]>({
    queryKey: ['home-portfolio-balances'],
    queryFn: async () => {
      const raw = (await portfolioApi.getBalances()) as Record<string, unknown> | undefined;
      const nested = (raw?.data as Record<string, unknown> | undefined)?.data as
        | Record<string, unknown>
        | undefined;
      const list =
        (nested?.balances as BalanceRow[] | undefined) ??
        ((raw?.data as Record<string, unknown> | undefined)?.balances as BalanceRow[] | undefined) ??
        (raw?.balances as BalanceRow[] | undefined) ??
        [];
      return Array.isArray(list) ? list : [];
    },
    enabled: appSettingsReady && portfolioEnabled,
    staleTime: 60_000,
  });

  const action = (
    <Button asChild variant="ghost" size="sm">
      <Link to="/portfolio" aria-label="Open portfolio overview">
        Portfolio
        <ArrowRight className="size-3.5" aria-hidden />
      </Link>
    </Button>
  );

  if (appSettingsReady && !portfolioEnabled) {
    return (
      <SectionShell title="Portfolio snapshot" icon={Wallet}>
        <EmptyState
          icon={Link2}
          title="Connect a broker to see your portfolio"
          description="Your NAV, day P&L, open positions, and cash will appear here once an account is linked."
          action={{
            label: 'Connect a broker',
            onClick: () => {
              navigate('/connect');
            },
          }}
          secondaryAction={{
            label: 'See pricing',
            onClick: () => {
              navigate('/pricing');
            },
          }}
        />
      </SectionShell>
    );
  }

  const isLoading =
    !appSettingsReady || dashboardQuery.isPending || balancesQuery.isPending;
  const hasError = dashboardQuery.isError || balancesQuery.isError;
  const portfolioError = dashboardQuery.isError
    ? dashboardQuery.error
    : balancesQuery.isError
      ? balancesQuery.error
      : undefined;

  if (isLoading) {
    return (
      <SectionShell title="Portfolio snapshot" icon={Wallet} action={action}>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-20 w-full" />
          ))}
        </div>
      </SectionShell>
    );
  }

  if (hasError) {
    return (
      <SectionShell title="Portfolio snapshot" icon={Wallet} action={action}>
        <ErrorState
          title="Couldn't load portfolio"
          description="We were unable to reach the portfolio service."
          error={portfolioError}
          retry={() => {
            void dashboardQuery.refetch();
            void balancesQuery.refetch();
          }}
        />
      </SectionShell>
    );
  }

  const dashboard = dashboardQuery.data;
  const summary = pickSummary(dashboard);
  const totalValue = pickTotalValue(dashboard);
  const dayChange =
    toNumberOrNull(summary?.day_change) ??
    toNumberOrNull((dashboard?.data as Record<string, unknown> | undefined)?.day_change);
  const dayChangePct =
    toNumberOrNull(summary?.day_change_pct) ??
    toNumberOrNull((dashboard?.data as Record<string, unknown> | undefined)?.day_change_pct);
  const positionsCount =
    toNumberOrNull(summary?.positions_count) ??
    toNumberOrNull((dashboard?.data as Record<string, unknown> | undefined)?.holdings_count);

  const balances = balancesQuery.data ?? [];
  const cash = balances.reduce<number | null>((acc, b) => {
    const v = toNumberOrNull(b.cash_balance) ?? toNumberOrNull(b.total_cash_value);
    if (v == null) return acc;
    return (acc ?? 0) + v;
  }, null);

  const emptyDashboard =
    totalValue == null && positionsCount == null && cash == null;

  if (emptyDashboard) {
    return (
      <SectionShell title="Portfolio snapshot" icon={Wallet} action={action}>
        <EmptyState
          icon={Link2}
          title="No positions yet"
          description="Once your broker finishes syncing, your NAV and positions will show up here."
          action={{
            label: 'Go to portfolio',
            onClick: () => {
              navigate('/portfolio');
            },
          }}
        />
      </SectionShell>
    );
  }

  const dayChangeColor =
    dayChange == null
      ? 'text-foreground'
      : dayChange > 0
        ? 'text-[rgb(var(--status-success)/1)]'
        : dayChange < 0
          ? 'text-[rgb(var(--status-danger)/1)]'
          : 'text-foreground';

  return (
    <SectionShell title="Portfolio snapshot" icon={Wallet} action={action}>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <SnapshotTile
          label="Total NAV"
          value={
            totalValue != null
              ? formatMoney(totalValue, currency, { maximumFractionDigits: 0 })
              : '—'
          }
        />
        <SnapshotTile
          label="Day P&L"
          value={
            dayChange != null
              ? formatMoney(dayChange, currency, { maximumFractionDigits: 0 })
              : '—'
          }
          sub={dayChangePct != null ? `${dayChangePct >= 0 ? '+' : ''}${dayChangePct.toFixed(2)}%` : undefined}
          valueClassName={dayChangeColor}
        />
        <SnapshotTile
          label="Open positions"
          value={positionsCount != null ? String(positionsCount) : '—'}
        />
        <SnapshotTile
          label="Cash"
          value={cash != null ? formatMoney(cash, currency, { maximumFractionDigits: 0 }) : '—'}
          sub={
            balances.length > 0
              ? `${balances.length} account${balances.length === 1 ? '' : 's'}`
              : undefined
          }
        />
      </div>
    </SectionShell>
  );
}

function SnapshotTile({
  label,
  value,
  sub,
  valueClassName,
}: {
  label: string;
  value: string;
  sub?: string;
  valueClassName?: string;
}) {
  return (
    <Card variant="flat" size="none">
      <CardContent className="flex flex-col gap-1 px-3 py-3">
        <span className="text-xs text-muted-foreground">{label}</span>
        <span
          className={cn(
            'font-mono text-lg font-bold leading-tight tracking-tight text-foreground',
            valueClassName,
          )}
        >
          {value}
        </span>
        {sub ? <span className="text-xs text-muted-foreground">{sub}</span> : null}
      </CardContent>
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/*  Open positions vs plan                                             */
/* ------------------------------------------------------------------ */

function OpenPositionsSection() {
  const navigate = useNavigate();
  const { appSettings, appSettingsReady } = useAuth();
  const portfolioEnabled = Boolean(appSettings?.portfolio_enabled);

  const positionsQuery = useQuery<EnrichedPosition[]>({
    queryKey: ['home-open-positions'],
    queryFn: async () => {
      const r = await portfolioApi.getStocks();
      return unwrapResponse<EnrichedPosition>(r, 'stocks');
    },
    enabled: appSettingsReady && portfolioEnabled,
    staleTime: 60_000,
  });

  const action = (
    <Button asChild variant="ghost" size="sm">
      <Link to="/portfolio/holdings" aria-label="Open all holdings">
        All holdings
        <ArrowRight className="size-3.5" aria-hidden />
      </Link>
    </Button>
  );

  if (appSettingsReady && !portfolioEnabled) {
    return (
      <SectionShell title="Open positions vs plan" icon={Briefcase}>
        <EmptyState
          icon={Link2}
          title="No open positions to show"
          description="Once a broker is connected, the top 5 positions by market value will appear here with their P&L and plan distance."
          action={{
            label: 'Connect a broker',
            onClick: () => {
              navigate('/connect');
            },
          }}
        />
      </SectionShell>
    );
  }

  if (!appSettingsReady || positionsQuery.isPending) {
    return (
      <SectionShell title="Open positions vs plan" icon={Briefcase} action={action}>
        <div className="flex flex-col gap-2">
          {[0, 1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-10 w-full" />
          ))}
        </div>
      </SectionShell>
    );
  }

  if (positionsQuery.isError) {
    return (
      <SectionShell title="Open positions vs plan" icon={Briefcase} action={action}>
        <ErrorState
          title="Couldn't load positions"
          description="The holdings endpoint didn't respond."
          error={positionsQuery.error}
          retry={() => {
            void positionsQuery.refetch();
          }}
        />
      </SectionShell>
    );
  }

  const rows = positionsQuery.data ?? [];
  if (rows.length === 0) {
    return (
      <SectionShell title="Open positions vs plan" icon={Briefcase} action={action}>
        <EmptyState
          title="No open positions"
          description="When your broker sync completes, your top positions will appear here with P&L and plan distance."
        />
      </SectionShell>
    );
  }

  const top = [...rows]
    .sort((a, b) => (Number(b.market_value) || 0) - (Number(a.market_value) || 0))
    .slice(0, 5);

  return (
    <SectionShell title="Open positions vs plan" icon={Briefcase} action={action}>
      <div className="overflow-hidden rounded-md border border-border">
        <table className="w-full border-collapse text-sm">
          <thead className="bg-muted/30 text-xs uppercase tracking-wide text-muted-foreground">
            <tr>
              <th scope="col" className="px-3 py-2 text-left">
                Symbol
              </th>
              <th scope="col" className="px-3 py-2 text-right">
                P&L %
              </th>
              <th scope="col" className="px-3 py-2 text-right">
                Plan stop dist
              </th>
              <th scope="col" className="px-3 py-2 text-right">
                Last updated
              </th>
            </tr>
          </thead>
          <tbody>
            {top.map((row) => {
              const pnlPct = toNumberOrNull(row.unrealized_pnl_pct);
              const pnlColor =
                pnlPct == null
                  ? 'text-foreground'
                  : pnlPct > 0
                    ? 'text-[rgb(var(--status-success)/1)]'
                    : pnlPct < 0
                      ? 'text-[rgb(var(--status-danger)/1)]'
                      : 'text-foreground';
              return (
                <tr
                  key={`${row.symbol}-${row.id ?? row.account_number ?? ''}`}
                  className="border-t border-border"
                >
                  <td className="px-3 py-2 font-mono font-medium">
                    <Link to={`/holding/${encodeURIComponent(row.symbol)}`} className="hover:underline">
                      {row.symbol}
                    </Link>
                  </td>
                  <td className={cn('px-3 py-2 text-right font-mono tabular-nums', pnlColor)}>
                    {pnlPct != null ? `${pnlPct >= 0 ? '+' : ''}${pnlPct.toFixed(2)}%` : '—'}
                  </td>
                  <td className="px-3 py-2 text-right font-mono tabular-nums text-muted-foreground">
                    {/* Plan stop distance not yet surfaced by the holdings API.
                        Render "—" per no-silent-fallback rules. */}
                    —
                  </td>
                  <td className="px-3 py-2 text-right font-mono tabular-nums text-muted-foreground">
                    {/* /portfolio/stocks exposes position sync time as last_updated, not days_held. */}
                    {row.last_updated
                      ? formatRelativeTime(row.last_updated) || '—'
                      : '—'}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </SectionShell>
  );
}

/* ------------------------------------------------------------------ */
/*  Page                                                                */
/* ------------------------------------------------------------------ */

const Home: React.FC = () => {
  const { user } = useAuth();
  const displayName = (user?.full_name ?? user?.username ?? '').trim();
  const subtitle = displayName
    ? `Welcome back, ${displayName}.`
    : 'Regime, signals, and portfolio at a glance.';

  return (
    <Page>
      <PageHeader
        title="Home"
        subtitle={subtitle}
        rightContent={
          <Button asChild variant="outline" size="sm">
            <Link to="/market">
              <PieChart className="size-3.5" aria-hidden />
              Open market view
            </Link>
          </Button>
        }
      />
      <div className="flex flex-col gap-4">
        <RegimeHero />
        <TradeCardsSection />
        <PortfolioSnapshotSection />
        <OpenPositionsSection />
      </div>
    </Page>
  );
};

export default Home;
