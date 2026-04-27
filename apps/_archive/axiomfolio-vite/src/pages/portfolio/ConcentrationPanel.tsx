import * as React from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import { semanticTextColorClass } from '@/lib/semantic-text-color';
import { usePositions } from '../../hooks/usePortfolio';
import { useUserPreferences } from '../../hooks/useUserPreferences';
import { formatMoney } from '../../utils/format';
import type { EnrichedPosition } from '../../types/portfolio';

/**
 * Top five positions by portfolio weight for the allocation tab.
 */
export function ConcentrationPanel() {
  const { currency } = useUserPreferences();
  const positionsQuery = usePositions();

  if (positionsQuery.isPending) {
    return <p className="text-sm text-muted-foreground">Loading positions…</p>;
  }
  if (positionsQuery.isError) {
    return (
      <p className={cn('text-sm', semanticTextColorClass('status.danger'))} role="alert">
        Failed to load positions for concentration view.
      </p>
    );
  }

  const rows = (positionsQuery.data as EnrichedPosition[] | undefined) ?? [];
  if (rows.length === 0) {
    return <p className="text-sm text-muted-foreground">No open positions yet.</p>;
  }

  const total = rows.reduce((s, p) => s + Number(p.market_value ?? 0), 0);
  const top = [...rows]
    .sort((a, b) => Number(b.market_value ?? 0) - Number(a.market_value ?? 0))
    .slice(0, 5);

  return (
    <Card className="gap-0 border border-border shadow-none ring-0">
      <CardContent className="py-4">
        <p className="mb-3 text-sm font-semibold text-muted-foreground">Top 5 by weight</p>
        <ul className="flex flex-col gap-2">
          {top.map((p) => {
            const mv = Number(p.market_value ?? 0);
            const pct = total > 0 ? ((mv / total) * 100).toFixed(1) : '0';
            return (
              <li key={p.id} className="flex items-center justify-between gap-2 text-sm">
                <span className="font-mono font-medium">{p.symbol}</span>
                <span className="text-muted-foreground">
                  {pct}% · {formatMoney(mv, currency, { maximumFractionDigits: 0 })}
                </span>
              </li>
            );
          })}
        </ul>
      </CardContent>
    </Card>
  );
}
