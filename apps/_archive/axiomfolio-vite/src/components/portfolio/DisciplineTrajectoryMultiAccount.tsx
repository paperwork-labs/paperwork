import React, { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';

import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { useUserPreferences } from '@/hooks/useUserPreferences';
import { useDisciplineTrajectory } from '@/hooks/useDisciplineTrajectory';
import { formatMoney } from '@/utils/format';
import {
  TrajectoryVisual,
  trajectoryPctOnScale,
  trajectoryScaleMax,
} from '@/components/portfolio/DisciplineTrajectoryTile';

const DisciplineTrajectoryMultiAccount: React.FC = () => {
  const { currency } = useUserPreferences();
  const [open, setOpen] = useState(false);
  const q = useDisciplineTrajectory({ aggregate: true });

  if (q.isPending) {
    return (
      <Card className="border-border shadow-none ring-0">
        <CardContent className="py-4">
          <div className="h-36 animate-pulse rounded-md bg-muted/60" />
        </CardContent>
      </Card>
    );
  }

  if (q.isError) {
    return (
      <Alert variant="destructive">
        <AlertTitle className="text-sm">Consolidated trajectory unavailable</AlertTitle>
        <AlertDescription className="flex flex-col gap-2 text-sm">
          <span>Could not load multi-account trajectory.</span>
          <Button type="button" size="sm" variant="outline" onClick={() => q.refetch()}>
            Retry
          </Button>
        </AlertDescription>
      </Alert>
    );
  }

  const data = q.data;
  if (!data) {
    return (
      <Alert>
        <AlertTitle className="text-sm">Consolidated trajectory</AlertTitle>
        <AlertDescription className="text-sm">No data returned.</AlertDescription>
      </Alert>
    );
  }

  const isEmpty = data.starting_equity === null || data.anchors === null;

  if (isEmpty) {
    return (
      <Card className="border-border shadow-none ring-0">
        <CardContent className="py-4">
          <p className="text-sm font-semibold text-muted-foreground">
            Consolidated discipline trajectory
          </p>
          <p className="mt-2 text-sm text-muted-foreground">
            YTD baselines are not available for all linked accounts yet. Sync balances to anchor the
            consolidated view.
          </p>
        </CardContent>
      </Card>
    );
  }

  const scale =
    data.anchors != null
      ? trajectoryScaleMax(data.anchors, data.current_equity, data.projected_year_end)
      : 1;
  const rows = data.by_account ?? [];

  return (
    <Card className="border-border shadow-none ring-0">
      <CardContent className="py-4">
        <p className="mb-3 text-sm font-semibold text-muted-foreground">
          Consolidated discipline trajectory
        </p>
        <TrajectoryVisual
          data={data}
          currency={currency}
          footer={
            <span>
              Combined across {rows.length} linked account{rows.length === 1 ? '' : 's'}.
            </span>
          }
        />

        {rows.length > 0 ? (
          <div className="mt-4 border-t border-border pt-3">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="mb-2 h-8 gap-1 px-2 text-xs"
              onClick={() => setOpen((v) => !v)}
              aria-expanded={open}
            >
              {open ? <ChevronDown className="size-3.5" aria-hidden /> : <ChevronRight className="size-3.5" aria-hidden />}
              Per-account positions on band scale
            </Button>
            {open ? (
              <ul className="flex flex-col gap-0">
                {rows.map((row) => {
                  const p = trajectoryPctOnScale(row.current_equity, scale);
                  return (
                    <li
                      key={row.account_id}
                      className="border-b border-border py-2 last:border-0"
                    >
                      <div className="mb-1 flex justify-between gap-2 text-xs">
                        <span className="font-medium">
                          {row.broker.toUpperCase()} ···{row.account_number_suffix}
                        </span>
                        <span className="tabular-nums text-muted-foreground">
                          {formatMoney(row.current_equity, currency)}
                        </span>
                      </div>
                      <div className="relative h-2 w-full overflow-hidden rounded bg-muted/80">
                        <div
                          className="absolute top-1/2 z-10 size-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-background bg-foreground"
                          style={{ left: `${p}%` }}
                          title="Current equity"
                        />
                      </div>
                    </li>
                  );
                })}
              </ul>
            ) : null}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
};

export default DisciplineTrajectoryMultiAccount;
