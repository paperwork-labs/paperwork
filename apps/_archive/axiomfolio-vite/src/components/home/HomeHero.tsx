/**
 * HomeHero — the warm companion at the top of the authenticated Home page.
 *
 * Renders:
 *   - Time-aware greeting (see `utils/greeting.ts`)
 *   - Total NAV via `AnimatedNumber`
 *   - Day P&L (absolute + %) with token-only chroma
 *   - 30-day NAV sparkline via recharts (no axes, no grid, thin stroke)
 *   - System health dot keyed to the current regime snapshot
 *
 * Background uses a soft regime-tinted gradient composed from semantic tokens
 * plus Tailwind color utilities. Never raw hex.
 *
 * Every state is explicit: loading (skeletons), error (ErrorState + retry),
 * empty ("Connect a broker" CTA), data.
 */
import * as React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Area, AreaChart, ResponsiveContainer, Tooltip as RechartsTooltip } from 'recharts';
import { ArrowRight, Link2, PieChart } from 'lucide-react';

import { AnimatedNumber } from '@/components/ui/AnimatedNumber';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import EmptyState from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { useAuth } from '@/context/AuthContext';
import { marketDataApi, portfolioApi } from '@/services/api';
import type { DashboardResponse } from '@/services/api';
import {
  useAccountBalances,
  usePortfolioPerformanceHistory,
} from '@/hooks/usePortfolio';
import { cn } from '@/lib/utils';
import type { RegimeData } from '@/types/market';
import { formatMoney } from '@/utils/format';
import { getTimeAwareGreeting } from '@/utils/greeting';

/* ------------------------------------------------------------------ */
/*  Regime-tinted gradient                                             */
/* ------------------------------------------------------------------ */

type GradientTone = 'emerald' | 'lime' | 'amber' | 'orange' | 'rose' | 'neutral';

const GRADIENT_CLASSES: Record<GradientTone, string> = {
  emerald: 'from-emerald-500/10 via-background to-background',
  lime: 'from-lime-400/10 via-background to-background',
  amber: 'from-amber-400/10 via-background to-background',
  orange: 'from-orange-500/10 via-background to-background',
  rose: 'from-rose-500/10 via-background to-background',
  neutral: 'from-muted/30 via-background to-background',
};

const REGIME_TO_TONE: Record<string, GradientTone> = {
  R1: 'emerald',
  R2: 'lime',
  R3: 'amber',
  R4: 'orange',
  R5: 'rose',
};

function toneFromRegime(state: string | null): GradientTone {
  if (state == null) return 'neutral';
  return REGIME_TO_TONE[state] ?? 'neutral';
}

/* ------------------------------------------------------------------ */
/*  System health dot                                                  */
/* ------------------------------------------------------------------ */

type HealthStatus = 'ok' | 'degraded' | 'error';

const HEALTH_DOT_CLASS: Record<HealthStatus, string> = {
  ok: 'bg-emerald-500 animate-pulse',
  degraded: 'bg-amber-500',
  error: 'bg-rose-500',
};

const HEALTH_LABEL: Record<HealthStatus, string> = {
  ok: 'Systems healthy',
  degraded: 'Regime data degraded',
  error: 'Unable to reach regime engine',
};

function HealthDot({ status, detail }: { status: HealthStatus; detail: string }) {
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            aria-label={HEALTH_LABEL[status]}
            className="inline-flex items-center gap-2 rounded-full px-2 py-1 text-xs text-muted-foreground hover:bg-muted/60"
          >
            <span
              className={cn('inline-block size-2.5 rounded-full', HEALTH_DOT_CLASS[status])}
              aria-hidden
            />
            <span className="hidden sm:inline">{HEALTH_LABEL[status]}</span>
          </button>
        </TooltipTrigger>
        <TooltipContent>{detail}</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

/* ------------------------------------------------------------------ */
/*  Sparkline                                                          */
/* ------------------------------------------------------------------ */

interface SparklinePoint {
  date: string;
  total_value: number;
}

function Sparkline({
  points,
  positive,
  currency,
}: {
  points: ReadonlyArray<SparklinePoint>;
  positive: boolean;
  currency: string;
}) {
  const strokeClass = positive
    ? 'text-[rgb(var(--status-success)/1)]'
    : 'text-[rgb(var(--status-danger)/1)]';
  const gradientId = React.useId();

  return (
    <div className={cn('h-16 w-full', strokeClass)} data-testid="home-hero-sparkline">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={points as SparklinePoint[]} margin={{ top: 4, right: 0, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="currentColor" stopOpacity={0.35} />
              <stop offset="95%" stopColor="currentColor" stopOpacity={0} />
            </linearGradient>
          </defs>
          <RechartsTooltip
            cursor={false}
            contentStyle={{
              background: 'var(--popover, var(--background))',
              border: '1px solid var(--border)',
              borderRadius: 6,
              fontSize: 12,
              padding: '4px 8px',
            }}
            labelFormatter={(label: unknown) => String(label)}
            formatter={(value: unknown) => [
              formatMoney(Number(value), currency, { maximumFractionDigits: 0 }),
              'NAV',
            ]}
          />
          <Area
            type="monotone"
            dataKey="total_value"
            stroke="currentColor"
            strokeWidth={1.5}
            fill={`url(#${gradientId})`}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function toNumberOrNull(value: unknown): number | null {
  if (value == null) return null;
  if (typeof value === 'number') return Number.isFinite(value) ? value : null;
  if (typeof value === 'string' && value.trim() !== '') {
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

function pickTotalValue(payload: DashboardResponse | undefined): number | null {
  if (!payload) return null;
  const data = (payload as unknown as Record<string, unknown>).data as
    | Record<string, unknown>
    | undefined;
  const nested = toNumberOrNull(data?.total_value);
  if (nested != null) return nested;
  const summary = payload.data?.summary ?? payload.summary;
  return toNumberOrNull(summary?.total_market_value);
}

function pickDayChange(
  payload: DashboardResponse | undefined,
): { abs: number | null; pct: number | null } {
  const summary = payload?.data?.summary ?? payload?.summary;
  const data = (payload as unknown as Record<string, unknown> | undefined)?.data as
    | Record<string, unknown>
    | undefined;
  const abs =
    toNumberOrNull(summary?.day_change) ?? toNumberOrNull(data?.day_change);
  const pct =
    toNumberOrNull(summary?.day_change_pct) ?? toNumberOrNull(data?.day_change_pct);
  return { abs, pct };
}

/* ------------------------------------------------------------------ */
/*  Shell                                                              */
/* ------------------------------------------------------------------ */

interface HeroShellProps {
  tone: GradientTone;
  greeting: string;
  healthDot: React.ReactNode;
  children: React.ReactNode;
}

function HeroShell({ tone, greeting, healthDot, children }: HeroShellProps) {
  return (
    <Card
      variant="flat"
      size="none"
      className={cn(
        'relative overflow-hidden rounded-xl border-border bg-gradient-to-b',
        GRADIENT_CLASSES[tone],
      )}
      data-testid="home-hero"
    >
      <CardContent className="flex flex-col gap-4 px-5 py-6 sm:px-6 sm:py-7">
        <div className="flex items-start justify-between gap-3">
          <h1 className="font-heading text-xl leading-tight font-semibold tracking-tight text-foreground sm:text-2xl">
            {greeting}
          </h1>
          {healthDot}
        </div>
        {children}
      </CardContent>
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/*  HomeHero                                                           */
/* ------------------------------------------------------------------ */

export interface HomeHeroProps {
  /** When false, renders the "Connect a broker" CTA inline. */
  hasBrokers: boolean;
  /**
   * When the parent has already detected a broker-presence error, the hero
   * surfaces the error state rather than fetching dashboard data.
   */
  brokersError?: unknown;
  /** If true, renders the skeleton state for the whole hero. */
  brokersLoading?: boolean;
  onRetryBrokers?: () => void;
}

function HomeHeroInner({
  hasBrokers,
  brokersError,
  brokersLoading = false,
  onRetryBrokers,
}: HomeHeroProps) {
  const { user } = useAuth();
  const navigate = useNavigate();
  const displayName =
    (typeof user?.full_name === 'string' && user.full_name.trim()) ||
    (typeof user?.username === 'string' && user.username.trim()) ||
    null;
  const greeting = React.useMemo(
    () => getTimeAwareGreeting({ name: displayName }).text,
    [displayName],
  );
  const currency =
    typeof user?.currency_preference === 'string' && user.currency_preference.trim() !== ''
      ? user.currency_preference
      : 'USD';

  const regimeQuery = useQuery({
    queryKey: ['home-hero-regime'],
    queryFn: () => marketDataApi.getCurrentRegime(),
    staleTime: 60_000,
    refetchInterval: 5 * 60_000,
  });
  const dashboardQuery = useQuery({
    queryKey: ['home-hero-dashboard'],
    queryFn: () => portfolioApi.getDashboard(),
    enabled: hasBrokers,
    staleTime: 20_000,
  });
  const historyQuery = usePortfolioPerformanceHistory({ period: '30d' });

  const regime = (regimeQuery.data ?? null) as Partial<RegimeData> | null;
  const regimeState = typeof regime?.regime_state === 'string' ? regime.regime_state : null;
  const tone = toneFromRegime(regimeState);

  const healthStatus: HealthStatus = regimeQuery.isError
    ? 'error'
    : regimeQuery.isPending || regimeState == null
      ? 'degraded'
      : 'ok';
  const healthDetail = regimeQuery.isError
    ? 'Regime engine did not respond. Try refreshing.'
    : regimeState == null
      ? 'Waiting for the next regime snapshot.'
      : `Regime ${regimeState} · score ${
          typeof regime?.composite_score === 'number'
            ? regime.composite_score.toFixed(1)
            : '—'
        }`;
  const healthDot = <HealthDot status={healthStatus} detail={healthDetail} />;

  /* ── Brokers: loading / error / empty ─────────────────────────── */

  if (brokersLoading) {
    return (
      <HeroShell tone={tone} greeting={greeting} healthDot={healthDot}>
        <div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <div className="flex flex-col gap-2">
            <Skeleton className="h-4 w-20" />
            <Skeleton className="h-9 w-48" />
            <Skeleton className="h-4 w-32" />
          </div>
          <Skeleton className="h-16 w-full" />
        </div>
      </HeroShell>
    );
  }

  if (brokersError) {
    return (
      <HeroShell tone={tone} greeting={greeting} healthDot={healthDot}>
        <ErrorState
          title="Couldn't load accounts"
          description="We couldn't determine whether any brokers are connected."
          error={brokersError}
          retry={onRetryBrokers}
        />
      </HeroShell>
    );
  }

  if (!hasBrokers) {
    return (
      <HeroShell tone={tone} greeting={greeting} healthDot={healthDot}>
        <EmptyState
          icon={Link2}
          title="Connect a broker to see your book"
          description="Your NAV, day P&L, and 30-day shape will appear here once an account is linked."
          action={{ label: 'Connect a broker', onClick: () => navigate('/connect') }}
          secondaryAction={{ label: 'See pricing', onClick: () => navigate('/pricing') }}
        />
      </HeroShell>
    );
  }

  /* ── Dashboard: loading / error / data ───────────────────────── */

  if (dashboardQuery.isPending) {
    return (
      <HeroShell tone={tone} greeting={greeting} healthDot={healthDot}>
        <div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <div className="flex flex-col gap-2">
            <Skeleton className="h-4 w-20" />
            <Skeleton className="h-9 w-48" />
            <Skeleton className="h-4 w-32" />
          </div>
          <Skeleton className="h-16 w-full" />
        </div>
      </HeroShell>
    );
  }

  if (dashboardQuery.isError) {
    return (
      <HeroShell tone={tone} greeting={greeting} healthDot={healthDot}>
        <ErrorState
          title="Couldn't load NAV"
          description="The portfolio service didn't respond."
          error={dashboardQuery.error}
          retry={() => {
            void dashboardQuery.refetch();
          }}
        />
      </HeroShell>
    );
  }

  const totalValue = pickTotalValue(dashboardQuery.data);
  const { abs: dayChange, pct: dayChangePct } = pickDayChange(dashboardQuery.data);

  const dayPositive = (dayChange ?? 0) >= 0;
  const dayColor =
    dayChange == null
      ? 'text-foreground'
      : dayChange > 0
        ? 'text-[rgb(var(--status-success)/1)]'
        : dayChange < 0
          ? 'text-[rgb(var(--status-danger)/1)]'
          : 'text-foreground';

  const sparkPoints = historyQuery.data ?? [];
  const sparkFirst = sparkPoints[0]?.total_value ?? null;
  const sparkLast = sparkPoints[sparkPoints.length - 1]?.total_value ?? null;
  const sparkPositive =
    sparkFirst != null && sparkLast != null ? sparkLast >= sparkFirst : dayPositive;

  return (
    <HeroShell tone={tone} greeting={greeting} healthDot={healthDot}>
      <div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] sm:items-end">
        <div className="flex flex-col gap-1">
          <span className="text-xs uppercase tracking-wide text-muted-foreground">
            Total NAV
          </span>
          {totalValue != null ? (
            <AnimatedNumber
              value={totalValue}
              format={(n) => formatMoney(n, currency, { maximumFractionDigits: 0 })}
              className="font-heading text-3xl font-semibold tracking-tight text-foreground sm:text-4xl"
              ariaLabel={`Total NAV ${formatMoney(totalValue, currency, { maximumFractionDigits: 0 })}`}
            />
          ) : (
            <span className="font-heading text-3xl font-semibold tracking-tight text-muted-foreground">
              —
            </span>
          )}
          <span
            className={cn(
              'inline-flex items-baseline gap-2 text-sm font-medium tabular-nums',
              dayColor,
            )}
          >
            {dayChange != null
              ? `${dayChange >= 0 ? '+' : ''}${formatMoney(dayChange, currency, { maximumFractionDigits: 0 })}`
              : '—'}
            {dayChangePct != null ? (
              <span className="text-xs text-muted-foreground">
                ({dayChangePct >= 0 ? '+' : ''}
                {dayChangePct.toFixed(2)}%)
              </span>
            ) : null}
            <span className="text-xs text-muted-foreground">today</span>
          </span>
        </div>

        <div className="flex flex-col gap-1" data-testid="home-hero-sparkline-wrapper">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>Last 30 days</span>
            <Link
              to="/portfolio?tab=performance"
              className="inline-flex items-center gap-1 hover:text-foreground"
            >
              Performance
              <ArrowRight className="size-3" aria-hidden />
            </Link>
          </div>
          {historyQuery.isPending ? (
            <Skeleton className="h-16 w-full" />
          ) : historyQuery.isError ? (
            <p className="text-xs text-muted-foreground">Couldn't load performance history.</p>
          ) : sparkPoints.length === 0 ? (
            <p className="text-xs text-muted-foreground">
              Once daily NAV snapshots arrive, your shape appears here.
            </p>
          ) : (
            <Sparkline points={sparkPoints} positive={sparkPositive} currency={currency} />
          )}
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2 pt-1 text-xs">
        <div className="text-muted-foreground">
          {regimeState
            ? `Regime ${regimeState}${
                typeof regime?.composite_score === 'number'
                  ? ` · score ${regime.composite_score.toFixed(1)}`
                  : ''
              }`
            : 'Regime —'}
        </div>
        <Button asChild variant="ghost" size="sm">
          <Link to="/market" aria-label="Open market dashboard">
            <PieChart className="size-3.5" aria-hidden />
            Markets
            <ArrowRight className="size-3" aria-hidden />
          </Link>
        </Button>
      </div>
    </HeroShell>
  );
}

export const HomeHero = React.memo(HomeHeroInner);

/**
 * Standalone gated variant for Home.tsx: reads `useAccountBalances` directly
 * so the page doesn't need to thread the broker-presence flag through. Kept
 * as a named export so stories can drive `HomeHero` with explicit props.
 */
function HomeHeroGatedInner() {
  const balancesQuery = useAccountBalances();
  const hasBrokers = (balancesQuery.data?.length ?? 0) > 0;
  return (
    <HomeHero
      hasBrokers={hasBrokers}
      brokersError={balancesQuery.isError ? balancesQuery.error : undefined}
      brokersLoading={balancesQuery.isPending}
      onRetryBrokers={() => {
        void balancesQuery.refetch();
      }}
    />
  );
}

export const HomeHeroGated = React.memo(HomeHeroGatedInner);

export default HomeHero;
