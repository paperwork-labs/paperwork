/**
 * QuietFooter — four muted StatCards at the foot of the Home page.
 *
 * YTD Income (dividends), YTD Realized, Portfolio Heat, Concentration top-5.
 * Each card links to its deep page so the founder can dive in with one click.
 * Every stat has an explicit loading / error / empty / data treatment — no
 * "0" placeholders masquerading as real values (see `no-silent-fallback`).
 */
import * as React from 'react';
import { Link } from 'react-router-dom';

import { Card, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import StatCard from '@/components/shared/StatCard';
import { useAuth } from '@/context/AuthContext';
import {
  usePnlSummary,
  usePortfolioInsights,
  useRiskMetrics,
} from '@/hooks/usePortfolio';
import { cn } from '@/lib/utils';
import { formatMoney } from '@/utils/format';

interface FooterCardLinkProps {
  to: string;
  label: string;
  state: 'loading' | 'error' | 'empty' | 'data';
  value: string;
  sub?: string;
  color?: string;
  className?: string;
}

function FooterCardLink({ to, label, state, value, sub, color, className }: FooterCardLinkProps) {
  if (state === 'loading') {
    return (
      <Card variant="flat" size="none" className={cn('flex-1 min-w-[140px]', className)}>
        <CardContent className="flex flex-col gap-2 px-3 py-3">
          <Skeleton className="h-3 w-20" />
          <Skeleton className="h-5 w-24" />
          <Skeleton className="h-3 w-16" />
        </CardContent>
      </Card>
    );
  }
  return (
    <Link
      to={to}
      aria-label={`${label}: ${value}${sub ? ` (${sub})` : ''}`}
      className={cn(
        'flex-1 min-w-[140px] rounded-lg transition-transform duration-200 hover:-translate-y-px focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50',
        className,
      )}
    >
      <StatCard label={label} value={value} sub={sub} color={color} />
    </Link>
  );
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

function QuietFooterInner() {
  const { user } = useAuth();
  const currency =
    typeof user?.currency_preference === 'string' && user.currency_preference.trim() !== ''
      ? user.currency_preference
      : 'USD';

  const pnlQuery = usePnlSummary();
  const insightsQuery = usePortfolioInsights();
  const riskQuery = useRiskMetrics();

  const pnlState: FooterCardLinkProps['state'] = pnlQuery.isPending
    ? 'loading'
    : pnlQuery.isError
      ? 'error'
      : pnlQuery.data == null
        ? 'empty'
        : 'data';

  const dividends = toNumberOrNull(pnlQuery.data?.total_dividends);
  const realized = toNumberOrNull(pnlQuery.data?.realized_pnl);

  const insightsState: FooterCardLinkProps['state'] = insightsQuery.isPending
    ? 'loading'
    : insightsQuery.isError
      ? 'error'
      : insightsQuery.data == null
        ? 'empty'
        : 'data';

  const concentrationTop5 = (insightsQuery.data?.concentration_warnings ?? [])
    .slice(0, 5)
    .reduce<number | null>((acc, w) => {
      const v = toNumberOrNull(w.pct_of_portfolio);
      if (v == null) return acc;
      return (acc ?? 0) + v;
    }, null);

  const riskState: FooterCardLinkProps['state'] = riskQuery.isPending
    ? 'loading'
    : riskQuery.isError
      ? 'error'
      : riskQuery.data == null
        ? 'empty'
        : 'data';

  const riskAny = riskQuery.data as Record<string, unknown> | undefined;
  const heatRaw =
    (riskAny?.data as Record<string, unknown> | undefined)?.portfolio_heat_pct ??
    riskAny?.portfolio_heat_pct ??
    (riskAny?.data as Record<string, unknown> | undefined)?.heat_pct ??
    riskAny?.heat_pct;
  const heatPct = toNumberOrNull(heatRaw);

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <FooterCardLink
        to="/portfolio/income"
        label="YTD Income"
        state={
          pnlState === 'data' && dividends == null
            ? 'empty'
            : pnlState
        }
        value={
          pnlState === 'loading'
            ? ''
            : pnlState === 'error'
              ? '—'
              : dividends != null
                ? formatMoney(dividends, currency, { maximumFractionDigits: 0 })
                : '—'
        }
        sub={pnlState === 'error' ? 'Retry from Income' : 'Dividends + distributions'}
        color="status.success"
      />
      <FooterCardLink
        to="/portfolio/tax"
        label="YTD Realized"
        state={
          pnlState === 'data' && realized == null
            ? 'empty'
            : pnlState
        }
        value={
          pnlState === 'loading'
            ? ''
            : pnlState === 'error'
              ? '—'
              : realized != null
                ? `${realized >= 0 ? '+' : ''}${formatMoney(realized, currency, {
                    maximumFractionDigits: 0,
                  })}`
                : '—'
        }
        sub={pnlState === 'error' ? 'Retry from Tax' : 'Closed P&L year-to-date'}
        color={realized != null && realized < 0 ? 'status.danger' : 'status.success'}
      />
      <FooterCardLink
        to="/portfolio?tab=risk"
        label="Portfolio Heat"
        state={
          riskState === 'data' && heatPct == null
            ? 'empty'
            : riskState
        }
        value={
          riskState === 'loading'
            ? ''
            : riskState === 'error'
              ? '—'
              : heatPct != null
                ? `${heatPct.toFixed(1)}%`
                : '—'
        }
        sub={riskState === 'error' ? 'Retry from Risk' : 'Total R at risk'}
        color={heatPct != null && heatPct >= 6 ? 'status.warning' : undefined}
      />
      <FooterCardLink
        to="/portfolio?tab=allocation"
        label="Concentration Top-5"
        state={
          insightsState === 'data' && concentrationTop5 == null
            ? 'empty'
            : insightsState
        }
        value={
          insightsState === 'loading'
            ? ''
            : insightsState === 'error'
              ? '—'
              : concentrationTop5 != null
                ? `${concentrationTop5.toFixed(1)}%`
                : '—'
        }
        sub={insightsState === 'error' ? 'Retry from Allocation' : 'Share of book in top 5'}
        color={concentrationTop5 != null && concentrationTop5 >= 50 ? 'status.warning' : undefined}
      />
    </div>
  );
}

export const QuietFooter = React.memo(QuietFooterInner);
export default QuietFooter;
