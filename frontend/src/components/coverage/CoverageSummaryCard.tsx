import React from 'react';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import type {
  CoverageAction,
  CoverageBucketGroup,
  CoverageHeroMeta,
  CoverageKpi,
  CoverageSparkline,
} from '../../utils/coverage';

export interface CoverageSummaryCardProps {
  hero: CoverageHeroMeta;
  status?: unknown;
  showUpdated?: boolean;
  children?: React.ReactNode;
}

/**
 * Read-only coverage summary container.
 * Keep this dependency-light so CI doesn't depend on chart libs/DOM quirks.
 */
export const CoverageSummaryCard: React.FC<CoverageSummaryCardProps> = ({
  hero,
  showUpdated = true,
  children,
}) => {
  const label = String(hero.statusLabel || '').toUpperCase() || '—';
  const badgeClass =
    hero.statusColor === 'green'
      ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-800 dark:text-emerald-300'
      : hero.statusColor === 'yellow'
        ? 'border-amber-500/40 bg-amber-500/10 text-amber-900 dark:text-amber-200'
        : hero.statusColor === 'red'
          ? 'border-destructive/40 bg-destructive/10 text-destructive'
          : 'bg-secondary text-secondary-foreground';
  return (
    <Card>
      <CardContent className="space-y-3 pt-6">
        <div>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="font-heading text-sm font-medium">Coverage</h2>
              {showUpdated && hero && hero.updatedRelative && hero.updatedDisplay ? (
                <p className="text-xs text-muted-foreground">
                  Updated {hero.updatedRelative} ({hero.updatedDisplay})
                </p>
              ) : null}
            </div>
            <Badge variant="outline" className={cn('shrink-0', badgeClass)}>
              {label}
            </Badge>
          </div>
          {hero.summary ? <p className="mt-1 text-sm text-muted-foreground">{hero.summary}</p> : null}
          {hero.warningBanner ? (
            <div className="mt-2 rounded-md border border-border bg-muted/60 p-3">
              <p className="font-semibold">{hero.warningBanner.title}</p>
              {hero.warningBanner.description ? (
                <p className="text-sm text-muted-foreground">{hero.warningBanner.description}</p>
              ) : null}
            </div>
          ) : null}
        </div>

        {children ? <div>{children}</div> : null}
      </CardContent>
    </Card>
  );
};

export interface CoverageKpiGridProps {
  kpis: CoverageKpi[];
  variant?: 'compact' | 'stat' | string;
}

export const CoverageKpiGrid: React.FC<CoverageKpiGridProps> = ({ kpis }) => {
  return (
    <div>
      <h3 className="mb-2 font-heading text-xs font-medium">KPIs</h3>
      <div className="grid grid-cols-[repeat(auto-fit,minmax(160px,1fr))] gap-3">
        {kpis.map((kpi) => (
          <div key={kpi.id} className="rounded-md border border-border p-3">
            <p className="text-xs text-muted-foreground">{kpi.label}</p>
            <p className="text-lg font-semibold">
              {kpi.value ?? '—'}
              {kpi.unit ? ` ${kpi.unit}` : ''}
            </p>
            {kpi.help ? <p className="text-xs text-muted-foreground">{kpi.help}</p> : null}
          </div>
        ))}
      </div>
    </div>
  );
};

export interface CoverageTrendGridProps {
  sparkline: CoverageSparkline;
}

export const CoverageTrendGrid: React.FC<CoverageTrendGridProps> = ({ sparkline }) => {
  const daily = sparkline.daily_pct?.[sparkline.daily_pct.length - 1];
  const m5 = sparkline.m5_pct?.[sparkline.m5_pct.length - 1];

  return (
    <div className="mt-4">
      <h3 className="mb-2 font-heading text-xs font-medium">Trend (latest)</h3>
      <div className="grid grid-cols-[repeat(auto-fit,minmax(160px,1fr))] gap-3">
        <div className="rounded-md border border-border p-3">
          <p className="text-xs text-muted-foreground">Daily coverage %</p>
          <p className="text-lg font-semibold">{typeof daily === 'number' ? daily.toFixed(1) : '—'}%</p>
        </div>
        <div className="rounded-md border border-border p-3">
          <p className="text-xs text-muted-foreground">5m coverage %</p>
          <p className="text-lg font-semibold">{typeof m5 === 'number' ? m5.toFixed(1) : '—'}%</p>
        </div>
      </div>
    </div>
  );
};

export interface CoverageBucketsGridProps {
  groups: CoverageBucketGroup[];
}

export const CoverageBucketsGrid: React.FC<CoverageBucketsGridProps> = ({ groups }) => {
  return (
    <div className="mt-4">
      <h3 className="mb-2 font-heading text-xs font-medium">Freshness Buckets</h3>
      <div className="grid grid-cols-[repeat(auto-fit,minmax(240px,1fr))] gap-3">
        {groups.map((group) => (
          <div key={group.interval} className="rounded-md border border-border p-3">
            <p className="mb-2 font-semibold">{group.title}</p>
            <div className="flex flex-col gap-1">
              {group.buckets.map((b) => (
                <div key={b.label} className="flex justify-between gap-2">
                  <span className="text-sm text-muted-foreground">{b.label}</span>
                  <span className="text-sm font-semibold">{b.count}</span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export interface CoverageActionsListProps {
  actions: CoverageAction[];
  onRun: (taskName: string, label?: string) => Promise<void> | void;
  buttonRenderer?: (action: CoverageAction, handleClick: () => void) => React.ReactNode;
}

export const CoverageActionsList: React.FC<CoverageActionsListProps> = ({
  actions,
  onRun,
  buttonRenderer,
}) => {
  return (
    <div className="flex flex-col gap-2">
      {actions.map((action) => {
        const handleClick = () => void onRun(action.task_name, action.label);
        return (
          <div
            key={action.task_name}
            className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-border p-3"
          >
            <div>
              <p className="font-semibold">{action.label}</p>
              {action.description ? (
                <p className="text-sm text-muted-foreground">{action.description}</p>
              ) : null}
            </div>
            <div>
              {buttonRenderer ? (
                buttonRenderer(action, handleClick)
              ) : (
                <button
                  type="button"
                  className="rounded-md border border-input bg-background px-3 py-1.5 text-sm shadow-xs hover:bg-muted"
                  disabled={Boolean(action.disabled)}
                  onClick={handleClick}
                >
                  Run
                </button>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
};
