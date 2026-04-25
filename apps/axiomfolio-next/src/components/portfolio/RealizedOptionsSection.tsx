import React, { useMemo, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { TableSkeleton } from '@/components/shared/Skeleton';
import { cn } from '@/lib/utils';
import { useRealizedOptionsTax, type RealizedOptionTaxItem } from '@/hooks/usePortfolio';
import { useUserPreferences } from '@/hooks/useUserPreferences';
import { formatMoney } from '@/utils/format';

function parseMoney(raw: string | null | undefined): number | null {
  if (raw === null || raw === undefined) return null;
  const n = Number(raw);
  return Number.isFinite(n) ? n : null;
}

function yearChoices(anchor: number, span = 8): number[] {
  return Array.from({ length: span }, (_, i) => anchor - i);
}

function RealizedTable({
  title,
  rows,
  totalPnl,
  currency,
}: {
  title: string;
  rows: RealizedOptionTaxItem[];
  totalPnl: number | null;
  currency: string;
}) {
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{title}</span>
        {totalPnl !== null && (
          <span
            className={cn(
              'text-sm font-semibold tabular-nums',
              totalPnl >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-destructive',
            )}
          >
            Total: {formatMoney(totalPnl, currency, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </span>
        )}
        {totalPnl === null && rows.length > 0 && (
          <span className="text-sm font-medium text-muted-foreground">Total: —</span>
        )}
      </div>
      <div className="overflow-x-auto rounded-md border border-border">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/30 text-left text-xs text-muted-foreground">
              <th className="p-2 font-medium">Symbol</th>
              <th className="p-2 font-medium">Type</th>
              <th className="p-2 text-end font-medium">Qty closed</th>
              <th className="p-2 text-end font-medium">Cost / contract</th>
              <th className="p-2 text-end font-medium">Proceeds / contract</th>
              <th className="p-2 text-end font-medium">Realized P/L</th>
              <th className="p-2 font-medium">Closed</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const pnl = parseMoney(row.realized_pnl);
              const cost = parseMoney(row.cost_basis_per_contract);
              const proceeds = parseMoney(row.proceeds_per_contract);
              return (
                <tr key={row.id} className="border-b border-border/60">
                  <td className="p-2 font-mono text-xs font-semibold">{row.symbol}</td>
                  <td className="p-2 text-muted-foreground">{row.option_type}</td>
                  <td className="p-2 text-end tabular-nums">{row.quantity_closed}</td>
                  <td className="p-2 text-end tabular-nums text-muted-foreground">
                    {cost !== null
                      ? formatMoney(cost, currency, { minimumFractionDigits: 2, maximumFractionDigits: 4 })
                      : '—'}
                  </td>
                  <td className="p-2 text-end tabular-nums text-muted-foreground">
                    {proceeds !== null
                      ? formatMoney(proceeds, currency, { minimumFractionDigits: 2, maximumFractionDigits: 4 })
                      : '—'}
                  </td>
                  <td className="p-2 text-end tabular-nums">
                    {pnl !== null ? (
                      <span className={cn(pnl >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-destructive')}>
                        {formatMoney(pnl, currency, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </span>
                    ) : (
                      '—'
                    )}
                  </td>
                  <td className="p-2 text-xs text-muted-foreground">
                    {row.closed_at ? row.closed_at.slice(0, 10) : '—'}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export const RealizedOptionsSection: React.FC = () => {
  const { currency } = useUserPreferences();
  const currentYear = new Date().getFullYear();
  const [year, setYear] = useState(currentYear);
  const q = useRealizedOptionsTax(year);

  const years = useMemo(() => yearChoices(currentYear), [currentYear]);

  const shortRows = useMemo(
    () => (q.data?.items ?? []).filter((i) => i.holding_class === 'short_term'),
    [q.data?.items],
  );
  const longRows = useMemo(
    () => (q.data?.items ?? []).filter((i) => i.holding_class === 'long_term'),
    [q.data?.items],
  );

  const totalShort = useMemo(() => parseMoney(q.data?.total_realized_pnl_short ?? null), [q.data?.total_realized_pnl_short]);
  const totalLong = useMemo(() => parseMoney(q.data?.total_realized_pnl_long ?? null), [q.data?.total_realized_pnl_long]);

  if (q.isPending) {
    return (
      <Card className="gap-0 border border-border bg-muted/20 shadow-none ring-0">
        <CardHeader className="pb-2">
          <span className="text-sm font-semibold text-foreground">Realized options</span>
        </CardHeader>
        <CardContent className="pt-0">
          <TableSkeleton rows={4} cols={7} />
        </CardContent>
      </Card>
    );
  }

  if (q.isError) {
    return (
      <Card className="gap-0 border border-border shadow-none ring-0">
        <CardContent className="flex flex-col gap-3 py-6 text-sm">
          <span className="font-semibold text-foreground">Could not load realized options</span>
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
  const empty = items.length === 0;

  return (
    <Card className="gap-0 border border-border bg-muted/20 shadow-none ring-0">
      <CardHeader className="pb-2">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <span className="text-sm font-semibold text-foreground">Realized options</span>
          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            <span>Tax year</span>
            <select
              className="rounded-md border border-input bg-background px-2 py-1 text-sm text-foreground"
              value={year}
              onChange={(e) => setYear(Number(e.target.value))}
            >
              {years.map((y) => (
                <option key={y} value={y}>
                  {y}
                </option>
              ))}
            </select>
          </label>
        </div>
        {q.data?.counts != null ? (
          <p className="text-xs text-muted-foreground">
            {q.data.counts.total} closed lot{q.data.counts.total === 1 ? '' : 's'} · {q.data.counts.short_term}{' '}
            short-term · {q.data.counts.long_term} long-term
          </p>
        ) : null}
      </CardHeader>
      <CardContent className="space-y-6 px-0 pb-4">
        {empty ? (
          <p className="px-4 text-center text-sm text-muted-foreground">No realized option lots for {year}</p>
        ) : (
          <>
            <div className="px-4">
              <RealizedTable title="Short-term" rows={shortRows} totalPnl={totalShort} currency={currency} />
            </div>
            <div className="px-4">
              <RealizedTable title="Long-term" rows={longRows} totalPnl={totalLong} currency={currency} />
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
};
