import React, { useMemo } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { TableSkeleton } from '@/components/shared/Skeleton';
import { cn } from '@/lib/utils';
import { useOpenOptionsTaxSummary } from '@/hooks/usePortfolio';
import { useUserPreferences } from '@/hooks/useUserPreferences';
import { formatMoney } from '@/utils/format';

const pctFmt = new Intl.NumberFormat('en-US', {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});

function parseMoney(raw: string | null): number | null {
  if (raw === null || raw === undefined) return null;
  const n = Number(raw);
  return Number.isFinite(n) ? n : null;
}

export const OpenOptionsSection: React.FC = () => {
  const { currency } = useUserPreferences();
  const q = useOpenOptionsTaxSummary();

  const totalPnl = useMemo(() => parseMoney(q.data?.total_unrealized_pnl ?? null), [q.data?.total_unrealized_pnl]);

  if (q.isPending) {
    return (
      <Card className="gap-0 border border-border bg-muted/20 shadow-none ring-0">
        <CardHeader className="pb-2">
          <span className="text-sm font-semibold text-foreground">Open options</span>
        </CardHeader>
        <CardContent className="pt-0">
          <TableSkeleton rows={4} cols={8} />
        </CardContent>
      </Card>
    );
  }

  if (q.isError) {
    return (
      <Card className="gap-0 border border-border shadow-none ring-0">
        <CardContent className="flex flex-col gap-3 py-6 text-sm">
          <span className="font-semibold text-foreground">Could not load open options</span>
          <span className="text-muted-foreground">This is usually a transient error. Try again in a moment.</span>
          <div>
            <Button type="button" size="sm" onClick={() => void q.refetch()}>
              Retry
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  const items = q.data?.items ?? [];

  if (items.length === 0) {
    return (
      <Card className="gap-0 border border-border bg-muted/20 shadow-none ring-0">
        <CardHeader className="pb-2">
          <span className="text-sm font-semibold text-foreground">Open options</span>
        </CardHeader>
        <CardContent className="py-6 text-center text-sm text-muted-foreground">No open option positions</CardContent>
      </Card>
    );
  }

  return (
    <Card className="gap-0 border border-border bg-muted/20 shadow-none ring-0">
      <CardHeader className="pb-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="text-sm font-semibold text-foreground">Open options</span>
          {totalPnl !== null && (
            <span
              className={cn(
                'text-sm font-semibold tabular-nums',
                totalPnl >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-destructive',
              )}
            >
              Total unrealized: {formatMoney(totalPnl, currency, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </span>
          )}
        </div>
        <p className="text-xs text-muted-foreground">
          {q.data?.counts != null
            ? `${q.data.counts.longs} long · ${q.data.counts.shorts} short (positions)`
            : null}
        </p>
      </CardHeader>
      <CardContent className="px-0 pb-4">
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs text-muted-foreground">
                <th className="p-2 font-medium">Symbol</th>
                <th className="p-2 font-medium">Type</th>
                <th className="p-2 text-end font-medium">Qty</th>
                <th className="p-2 text-end font-medium">Cost basis</th>
                <th className="p-2 text-end font-medium">Mark</th>
                <th className="p-2 text-end font-medium">Unrealized P/L</th>
                <th className="p-2 text-end font-medium">Days to expiry</th>
                <th className="p-2 font-medium">Tax class</th>
              </tr>
            </thead>
            <tbody>
              {items.map((row) => {
                const cost = parseMoney(row.cost_basis);
                const mark = parseMoney(row.mark);
                const pnl = parseMoney(row.unrealized_pnl);
                const pnlPct = parseMoney(row.unrealized_pnl_pct);
                const term =
                  row.tax_holding_class === 'long_term'
                    ? 'Long-term'
                    : row.tax_holding_class === 'short_term'
                      ? 'Short-term'
                      : '—';
                return (
                  <tr key={row.id} className="border-b border-border/60">
                    <td className="p-2 font-mono text-xs font-semibold">{row.symbol}</td>
                    <td className="p-2 text-muted-foreground">{row.option_type}</td>
                    <td className="p-2 text-end tabular-nums">{row.open_quantity.toLocaleString()}</td>
                    <td className="p-2 text-end tabular-nums text-muted-foreground">
                      {cost !== null
                        ? formatMoney(cost, currency, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
                        : '—'}
                    </td>
                    <td className="p-2 text-end tabular-nums text-muted-foreground">
                      {mark !== null
                        ? formatMoney(mark, currency, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
                        : '—'}
                    </td>
                    <td className="p-2 text-end tabular-nums">
                      {pnl !== null ? (
                        <span className={cn(pnl >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-destructive')}>
                          {formatMoney(pnl, currency, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                          {pnlPct !== null ? (
                            <span className="ml-1 text-xs text-muted-foreground">({pctFmt.format(pnlPct)}%)</span>
                          ) : null}
                        </span>
                      ) : (
                        '—'
                      )}
                    </td>
                    <td className="p-2 text-end tabular-nums text-muted-foreground">
                      {row.days_to_expiry !== null && row.days_to_expiry !== undefined ? row.days_to_expiry : '—'}
                    </td>
                    <td className="p-2 text-muted-foreground">{term}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
};
