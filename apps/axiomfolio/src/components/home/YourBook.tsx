/**
 * YourBook — top 5–8 positions by market value, rendered as a compact table
 * on desktop and collapsed two-line rows on mobile.
 *
 * Data comes from `usePositions()`. Empty state nudges the user toward the
 * signals page rather than leaving them in front of a blank card.
 */
import * as React from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { ArrowRight, Briefcase, Link2, Rocket } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import EmptyState from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { Skeleton } from '@/components/ui/skeleton';
import StageBadge from '@/components/shared/StageBadge';
import { useAuth } from '@/context/AuthContext';
import {
  useAccountBalances,
  usePositions,
} from '@/hooks/usePortfolio';
import { cn } from '@/lib/utils';
import type { EnrichedPosition } from '@/types/portfolio';
import { formatMoney } from '@/utils/format';

const TOP_COUNT = 6;

function toNumberOrNull(value: unknown): number | null {
  if (value == null) return null;
  if (typeof value === 'number') return Number.isFinite(value) ? value : null;
  if (typeof value === 'string' && value.trim() !== '') {
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

function pnlClass(value: number | null): string {
  if (value == null || value === 0) return 'text-foreground';
  if (value > 0) return 'text-[rgb(var(--status-success)/1)]';
  return 'text-[rgb(var(--status-danger)/1)]';
}

function hasRunnerSince(row: EnrichedPosition): boolean {
  const raw = (row as unknown as { runner_since?: unknown }).runner_since;
  return typeof raw === 'string' && raw.trim() !== '';
}

interface PositionRowProps {
  row: EnrichedPosition;
  currency: string;
}

function DesktopRow({ row, currency }: PositionRowProps) {
  const marketValue = toNumberOrNull(row.market_value);
  const dayPnl = toNumberOrNull(row.day_pnl);
  const dayPnlPct = toNumberOrNull(row.day_pnl_pct);
  const totalPnl = toNumberOrNull(row.unrealized_pnl);
  const totalPnlPct = toNumberOrNull(row.unrealized_pnl_pct);
  const shares = toNumberOrNull(row.shares);

  return (
    <tr className="border-t border-border hover:bg-muted/40">
      <td className="px-3 py-2">
        <div className="flex items-center gap-2">
          <Link
            href={`/holding/${encodeURIComponent(row.symbol)}`}
            className="font-mono font-medium hover:underline"
          >
            {row.symbol}
          </Link>
          {row.stage_label ? <StageBadge stage={row.stage_label} size="sm" /> : null}
          {hasRunnerSince(row) ? (
            <Badge
              variant="outline"
              className="gap-1 border-[rgb(var(--status-success)/0.35)] bg-[rgb(var(--status-success)/0.08)] text-[rgb(var(--status-success)/1)]"
              aria-label="Runner"
            >
              <Rocket className="size-3" aria-hidden />
              Runner
            </Badge>
          ) : null}
        </div>
      </td>
      <td className="px-3 py-2 text-right font-mono tabular-nums text-muted-foreground">
        {shares != null ? shares.toLocaleString() : '—'}
      </td>
      <td className="px-3 py-2 text-right font-mono tabular-nums">
        {marketValue != null
          ? formatMoney(marketValue, currency, { maximumFractionDigits: 0 })
          : '—'}
      </td>
      <td className={cn('px-3 py-2 text-right font-mono tabular-nums', pnlClass(dayPnl))}>
        {dayPnl != null
          ? `${dayPnl >= 0 ? '+' : ''}${formatMoney(dayPnl, currency, { maximumFractionDigits: 0 })}`
          : '—'}
        {dayPnlPct != null ? (
          <span className="ml-1 text-xs text-muted-foreground">
            ({dayPnlPct >= 0 ? '+' : ''}
            {dayPnlPct.toFixed(2)}%)
          </span>
        ) : null}
      </td>
      <td className={cn('px-3 py-2 text-right font-mono tabular-nums', pnlClass(totalPnl))}>
        {totalPnl != null
          ? `${totalPnl >= 0 ? '+' : ''}${formatMoney(totalPnl, currency, { maximumFractionDigits: 0 })}`
          : '—'}
        {totalPnlPct != null ? (
          <span className="ml-1 text-xs text-muted-foreground">
            ({totalPnlPct >= 0 ? '+' : ''}
            {totalPnlPct.toFixed(2)}%)
          </span>
        ) : null}
      </td>
    </tr>
  );
}

function MobileRow({ row, currency }: PositionRowProps) {
  const marketValue = toNumberOrNull(row.market_value);
  const totalPnlPct = toNumberOrNull(row.unrealized_pnl_pct);
  return (
    <Link
      href={`/holding/${encodeURIComponent(row.symbol)}`}
      className="flex items-center justify-between gap-3 rounded-md px-3 py-2 hover:bg-muted/40"
    >
      <div className="flex min-w-0 items-center gap-2">
        <span className="font-mono font-medium">{row.symbol}</span>
        {row.stage_label ? <StageBadge stage={row.stage_label} size="sm" /> : null}
        {hasRunnerSince(row) ? (
          <Rocket className="size-3 text-[rgb(var(--status-success)/1)]" aria-hidden />
        ) : null}
      </div>
      <div className="flex flex-col items-end text-right">
        <span className="font-mono text-sm tabular-nums">
          {marketValue != null
            ? formatMoney(marketValue, currency, { maximumFractionDigits: 0 })
            : '—'}
        </span>
        <span
          className={cn(
            'font-mono text-xs tabular-nums',
            pnlClass(totalPnlPct),
          )}
        >
          {totalPnlPct != null
            ? `${totalPnlPct >= 0 ? '+' : ''}${totalPnlPct.toFixed(2)}%`
            : '—'}
        </span>
      </div>
    </Link>
  );
}

function YourBookInner() {
  const router = useRouter();
  const { user } = useAuth();
  const currency =
    typeof user?.currency_preference === 'string' && user.currency_preference.trim() !== ''
      ? user.currency_preference
      : 'USD';
  const balancesQuery = useAccountBalances();
  const hasBrokers = (balancesQuery.data?.length ?? 0) > 0;
  const positionsQuery = usePositions();

  const action = (
    <Button asChild variant="ghost" size="sm">
      <Link href="/portfolio/holdings" aria-label="Open all holdings">
        All holdings
        <ArrowRight className="size-3" aria-hidden />
      </Link>
    </Button>
  );

  return (
    <Card variant="flat">
      <CardHeader className="flex flex-row items-start justify-between gap-3 pb-2">
        <CardTitle className="flex items-center gap-2 text-sm">
          <Briefcase className="size-4 text-muted-foreground" aria-hidden />
          <span>Your book</span>
        </CardTitle>
        {hasBrokers ? action : null}
      </CardHeader>
      <CardContent className="pt-0">
        {balancesQuery.isPending || (hasBrokers && positionsQuery.isPending) ? (
          <div className="flex flex-col gap-2">
            {[0, 1, 2, 3, 4].map((i) => (
              <Skeleton key={i} className="h-9 w-full" />
            ))}
          </div>
        ) : balancesQuery.isError ? (
          <ErrorState
            title="Couldn't load accounts"
            description="We couldn't determine whether any brokers are connected."
            error={balancesQuery.error}
            retry={() => {
              void balancesQuery.refetch();
            }}
          />
        ) : !hasBrokers ? (
          <EmptyState
            icon={Link2}
            title="Your book is empty. Let's find your next setup."
            description="Connect a broker or explore today's signals to seed your first position."
            action={{ label: 'Explore signals', onClick: () => router.push('/signals') }}
            secondaryAction={{ label: 'Connect a broker', onClick: () => router.push('/connect') }}
          />
        ) : positionsQuery.isError ? (
          <ErrorState
            title="Couldn't load positions"
            description="The holdings endpoint didn't respond."
            error={positionsQuery.error}
            retry={() => {
              void positionsQuery.refetch();
            }}
          />
        ) : (() => {
            const rows = positionsQuery.data ?? [];
            if (rows.length === 0) {
              return (
                <EmptyState
                  title="Your book is empty. Let's find your next setup."
                  action={{ label: 'Explore signals', onClick: () => router.push('/signals') }}
                />
              );
            }
            const top = [...rows]
              .sort((a, b) => (Number(b.market_value) || 0) - (Number(a.market_value) || 0))
              .slice(0, TOP_COUNT);
            return (
              <>
                <div className="hidden overflow-hidden rounded-md border border-border sm:block">
                  <table className="w-full border-collapse text-sm">
                    <thead className="bg-muted/30 text-xs uppercase tracking-wide text-muted-foreground">
                      <tr>
                        <th scope="col" className="px-3 py-2 text-left">Symbol</th>
                        <th scope="col" className="px-3 py-2 text-right">Qty</th>
                        <th scope="col" className="px-3 py-2 text-right">Mkt Val</th>
                        <th scope="col" className="px-3 py-2 text-right">Day P&amp;L</th>
                        <th scope="col" className="px-3 py-2 text-right">Total P&amp;L</th>
                      </tr>
                    </thead>
                    <tbody>
                      {top.map((row) => (
                        <DesktopRow
                          key={`${row.symbol}-${row.id ?? row.account_number ?? ''}`}
                          row={row}
                          currency={currency}
                        />
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="flex flex-col divide-y divide-border sm:hidden">
                  {top.map((row) => (
                    <MobileRow
                      key={`${row.symbol}-${row.id ?? row.account_number ?? ''}-m`}
                      row={row}
                      currency={currency}
                    />
                  ))}
                </div>
              </>
            );
          })()}
      </CardContent>
    </Card>
  );
}

export const YourBook = React.memo(YourBookInner);
export default YourBook;
