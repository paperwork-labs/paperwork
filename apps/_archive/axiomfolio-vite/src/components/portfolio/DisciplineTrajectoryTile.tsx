import React from 'react';

import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { cn } from '@/lib/utils';
import { semanticTextColorClass } from '@/lib/semantic-text-color';
import { TRAJECTORY_BANDS } from '@/constants/chart';
import { useUserPreferences } from '@/hooks/useUserPreferences';
import {
  useDisciplineTrajectory,
  type DisciplineTrajectoryAnchors,
  type DisciplineTrajectoryPayload,
} from '@/hooks/useDisciplineTrajectory';
import { formatMoney } from '@/utils/format';

export function trajectoryScaleMax(
  anchors: DisciplineTrajectoryAnchors,
  currentEquity: number,
  projectedYearEnd: number | null,
): number {
  return Math.max(anchors.speculative_ceiling, projectedYearEnd ?? 0, currentEquity, 1) * 1.08;
}

export function trajectoryPctOnScale(value: number, scale: number): number {
  if (!(scale > 0) || !Number.isFinite(value)) return 0;
  return Math.min(100, Math.max(0, (value / scale) * 100));
}

export interface TrajectoryVisualProps {
  data: DisciplineTrajectoryPayload;
  currency: string;
  /** Optional footer line (e.g. consolidated subtitle). */
  footer?: React.ReactNode;
}

export const TrajectoryVisual: React.FC<TrajectoryVisualProps> = ({ data, currency, footer }) => {
  const anchors = data.anchors;
  if (!anchors || data.starting_equity === null) {
    return null;
  }

  const scale = trajectoryScaleMax(anchors, data.current_equity, data.projected_year_end);
  const u = anchors.unleveraged_ceiling;
  const l = anchors.leveraged_ceiling;
  const s = anchors.speculative_ceiling;

  const wu = trajectoryPctOnScale(u, scale);
  const wl = Math.max(0, trajectoryPctOnScale(l, scale) - wu);
  const ws = Math.max(0, trajectoryPctOnScale(s, scale) - trajectoryPctOnScale(l, scale));
  const wb = Math.max(0, 100 - trajectoryPctOnScale(s, scale));

  const pCur = trajectoryPctOnScale(data.current_equity, scale);
  const pProj =
    data.projected_year_end != null
      ? trajectoryPctOnScale(data.projected_year_end, scale)
      : null;

  const trendColor =
    data.trend === 'up'
      ? 'status.success'
      : data.trend === 'down'
        ? 'status.danger'
        : 'fg.muted';

  const showArrow =
    pProj != null && Math.abs(pProj - pCur) > 0.35 && data.projected_year_end != null;

  return (
    <div className="flex flex-col gap-3">
      <div className="grid grid-cols-3 gap-2 text-xs sm:text-sm">
        <div>
          <p className="text-muted-foreground">Starting</p>
          <p className="font-semibold tabular-nums">{formatMoney(data.starting_equity, currency)}</p>
        </div>
        <div>
          <p className="text-muted-foreground">Current</p>
          <p className={cn('font-semibold tabular-nums', semanticTextColorClass(trendColor))}>
            {formatMoney(data.current_equity, currency)}
          </p>
        </div>
        <div>
          <p className="text-muted-foreground">Projected (Y/E)</p>
          <p className="font-semibold tabular-nums text-foreground">
            {data.projected_year_end != null
              ? formatMoney(data.projected_year_end, currency)
              : '—'}
          </p>
        </div>
      </div>

      <div className="relative pt-1">
        <p className="mb-1.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
          Discipline bands (D119 proportional)
        </p>
        <div className="flex h-9 w-full overflow-hidden rounded-md border border-border">
          {wu > 0 ? (
            <div
              style={{ width: `${wu}%` }}
              className={cn('h-full border-r', TRAJECTORY_BANDS.unleveraged.bandClass)}
              title={TRAJECTORY_BANDS.unleveraged.label}
            />
          ) : null}
          {wl > 0 ? (
            <div
              style={{ width: `${wl}%` }}
              className={cn('h-full border-r', TRAJECTORY_BANDS.leveraged.bandClass)}
              title={TRAJECTORY_BANDS.leveraged.label}
            />
          ) : null}
          {ws > 0 ? (
            <div
              style={{ width: `${ws}%` }}
              className={cn('h-full border-r', TRAJECTORY_BANDS.speculative.bandClass)}
              title={TRAJECTORY_BANDS.speculative.label}
            />
          ) : null}
          {wb > 0 ? (
            <div
              style={{ width: `${wb}%` }}
              className={cn('h-full', TRAJECTORY_BANDS.beyond.bandClass)}
              title={TRAJECTORY_BANDS.beyond.label}
            />
          ) : null}
        </div>

        <div
          className="pointer-events-none absolute left-0 top-8 h-8 w-full"
          aria-hidden={!showArrow}
        >
          {showArrow ? (
            <svg
              viewBox="0 0 100 32"
              className="h-full w-full text-primary"
              preserveAspectRatio="none"
              role="img"
              aria-label="Trajectory toward projected year-end"
            >
              <defs>
                <marker
                  id="traj-arrow"
                  markerWidth="6"
                  markerHeight="6"
                  refX="5"
                  refY="3"
                  orient="auto"
                >
                  <path d="M0,0 L6,3 L0,6 z" fill="currentColor" />
                </marker>
              </defs>
              <line
                x1={pCur}
                y1="16"
                x2={pProj ?? pCur}
                y2="16"
                stroke="currentColor"
                strokeWidth="1.2"
                markerEnd="url(#traj-arrow)"
              />
            </svg>
          ) : null}
        </div>

        <div
          className="absolute top-[1.85rem] z-10 size-3.5 -translate-x-1/2 rounded-full border-2 border-background bg-foreground shadow-sm"
          style={{ left: `${pCur}%` }}
          title="Current equity"
        />

        {pProj != null ? (
          <div
            className="absolute top-[1.85rem] z-10 size-2 -translate-x-1/2 rounded-full border border-dashed border-primary bg-background"
            style={{ left: `${pProj}%` }}
            title="Projected year-end"
          />
        ) : null}
      </div>

      <div className="flex flex-wrap gap-3 text-[10px] text-muted-foreground">
        <span>{TRAJECTORY_BANDS.unleveraged.label}</span>
        <span>{TRAJECTORY_BANDS.leveraged.label}</span>
        <span>{TRAJECTORY_BANDS.speculative.label}</span>
      </div>

      {footer ? <div className="text-xs text-muted-foreground">{footer}</div> : null}

      <p className="text-[10px] text-muted-foreground">As of {new Date(data.as_of).toLocaleString()}</p>
    </div>
  );
};

export interface DisciplineTrajectoryTileProps {
  accountId?: number;
}

const DisciplineTrajectoryTile: React.FC<DisciplineTrajectoryTileProps> = ({ accountId }) => {
  const { currency } = useUserPreferences();
  const q = useDisciplineTrajectory({ accountId, aggregate: false });

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
        <AlertTitle className="text-sm">Discipline trajectory unavailable</AlertTitle>
        <AlertDescription className="flex flex-col gap-2 text-sm">
          <span>Could not load trajectory data.</span>
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
        <AlertTitle className="text-sm">Discipline trajectory</AlertTitle>
        <AlertDescription className="text-sm">No data returned.</AlertDescription>
      </Alert>
    );
  }

  const isEmpty = data.starting_equity === null || data.anchors === null;

  if (isEmpty) {
    return (
      <Card className="border-border shadow-none ring-0">
        <CardContent className="py-4">
          <p className="text-sm font-semibold text-muted-foreground">Discipline-bounded trajectory</p>
          <p className="mt-2 text-sm text-muted-foreground">
            YTD starting equity is not available yet. Sync account balances so we can anchor your
            trajectory to the year and show discipline tiers.
          </p>
          {data.current_equity > 0 ? (
            <p className="mt-2 text-xs tabular-nums text-foreground">
              Latest equity:{' '}
              <span className="font-medium">{formatMoney(data.current_equity, currency)}</span>
            </p>
          ) : null}
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="border-border shadow-none ring-0">
      <CardContent className="py-4">
        <p className="mb-3 text-sm font-semibold text-muted-foreground">
          Discipline-bounded trajectory
        </p>
        <TrajectoryVisual data={data} currency={currency} />
      </CardContent>
    </Card>
  );
};

export default DisciplineTrajectoryTile;
