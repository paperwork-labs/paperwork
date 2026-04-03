import React from 'react';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import type { AdminHealthResponse } from '../../types/adminHealth';
import { REGIME_HEX } from '../../constants/chart';
import { formatDate } from '../../utils/format';
import { useUserPreferences } from '../../hooks/useUserPreferences';

interface Props {
  health: AdminHealthResponse | null;
}

function dimBadgeClass(status: string): string {
  switch (status) {
    case 'green':
      return 'border-transparent bg-[rgb(var(--status-success)/0.12)] text-[rgb(var(--status-success)/1)]';
    case 'yellow':
      return 'border-transparent bg-[rgb(var(--status-warning)/0.12)] text-[rgb(var(--status-warning)/1)]';
    case 'red':
      return 'border-transparent bg-destructive/10 text-destructive';
    default:
      return 'border-transparent bg-muted text-muted-foreground';
  }
}

const DimBadge: React.FC<{ status: string }> = ({ status }) => (
  <Badge variant="outline" className={cn('font-medium uppercase', dimBadgeClass(status))}>
    {status.toUpperCase()}
  </Badge>
);

const AdminDomainCards: React.FC<Props> = ({ health }) => {
  const { timezone } = useUserPreferences();
  if (!health) return null;
  const { coverage, stage_quality, jobs, audit, regime, fundamentals, data_accuracy } = health.dimensions;

  return (
    <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-2">
      {regime && (
        <Card className="gap-0 py-0 shadow-xs ring-1 ring-border">
          <div className="flex flex-col gap-1 p-3">
            <div className="mb-1 flex items-center justify-between">
              <span className="text-sm font-semibold">Market Regime</span>
              <DimBadge status={regime.status} />
            </div>
            {regime.regime_state ? (
              <>
                <div className="mb-1 flex flex-wrap items-center gap-2">
                  <Badge
                    className="border-0 font-medium text-white"
                    style={{
                      backgroundColor: (regime.regime_state && REGIME_HEX[regime.regime_state]) || '#718096',
                    }}
                  >
                    {regime.regime_state}
                  </Badge>
                  <span className="text-xs text-muted-foreground">
                    Score: {regime.composite_score ?? '—'}
                  </span>
                </div>
                <p className="text-xs text-muted-foreground">
                  Sizing multiplier: {regime.multiplier ?? '—'}x · Max equity: {regime.max_equity_pct ?? '—'}%
                </p>
                <p className="text-xs text-muted-foreground">
                  Age: {regime.age_hours != null ? `${regime.age_hours}h` : '—'} · As of:{' '}
                  {formatDate(regime.as_of_date, timezone)}
                </p>
              </>
            ) : (
              <p className="text-xs text-muted-foreground">{regime.error || 'No regime data'}</p>
            )}
          </div>
        </Card>
      )}

      <Card className="gap-0 py-0 shadow-xs ring-1 ring-border">
        <div className="flex flex-col gap-1 p-3">
          <div className="mb-1 flex items-center justify-between">
            <span className="text-sm font-semibold">Coverage</span>
            <DimBadge status={coverage.status} />
          </div>
          <p className="text-xs text-muted-foreground">
            Daily: {typeof coverage.daily_pct === 'number' ? `${coverage.daily_pct.toFixed(1)}%` : '—'}
          </p>
          <p className="text-xs text-muted-foreground">Stale daily: {coverage.stale_daily ?? 0}</p>
          <p className="text-xs text-muted-foreground">Tracked: {coverage.tracked_count ?? 0}</p>
          {coverage.indices && Object.keys(coverage.indices).length > 0 && (
            <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5">
              {Object.entries(coverage.indices).map(([idx, count]) => (
                <span key={idx} className="text-xs text-muted-foreground">
                  {idx}: <span className="font-medium text-foreground">{count}</span>
                </span>
              ))}
            </div>
          )}
          {coverage.expected_date && (
            <p className="text-xs text-muted-foreground">Latest date: {coverage.expected_date}</p>
          )}
        </div>
      </Card>

      <Card className="gap-0 py-0 shadow-xs ring-1 ring-border">
        <div className="flex flex-col gap-1 p-3">
          <div className="mb-1 flex items-center justify-between">
            <span className="text-sm font-semibold">Stage Quality</span>
            <DimBadge status={stage_quality.status} />
          </div>
          <p className="text-xs text-muted-foreground">
            Unknown rate:{' '}
            {typeof stage_quality.unknown_rate === 'number'
              ? `${(stage_quality.unknown_rate * 100).toFixed(1)}%`
              : '—'}
          </p>
          <p className="text-xs text-muted-foreground">Invalid rows: {stage_quality.invalid_count ?? 0}</p>
          <p className="text-xs text-muted-foreground">
            Monotonicity issues: {stage_quality.monotonicity_issues ?? 0}
          </p>
          <p className="text-xs text-muted-foreground">Stale stage rows: {stage_quality.stale_stage_count ?? 0}</p>
        </div>
      </Card>

      <Card className="gap-0 py-0 shadow-xs ring-1 ring-border">
        <div className="flex flex-col gap-1 p-3">
          <div className="mb-1 flex items-center justify-between">
            <span className="text-sm font-semibold">Jobs ({jobs.window_hours ?? 24}h)</span>
            <DimBadge status={jobs.status} />
          </div>
          <p className="text-xs text-muted-foreground">
            Success rate:{' '}
            {typeof jobs.success_rate === 'number' ? `${(jobs.success_rate * 100).toFixed(1)}%` : '—'}
          </p>
          <p className="text-xs text-muted-foreground">
            Failed: {jobs.error_count ?? 0} / Completed: {jobs.completed_count ?? 0}
          </p>
          <p className="text-xs text-muted-foreground">Running: {jobs.running_count ?? 0}</p>
          <p className="line-clamp-1 text-xs text-muted-foreground">
            Latest failure: {jobs.latest_failed?.task_name || '—'}
          </p>
        </div>
      </Card>

      {fundamentals && (
        <Card className="gap-0 py-0 shadow-xs ring-1 ring-border">
          <div className="flex flex-col gap-1 p-3">
            <div className="mb-1 flex items-center justify-between">
              <span className="text-sm font-semibold">Fundamentals</span>
              <DimBadge status={fundamentals.status} />
            </div>
            <p className="text-xs text-muted-foreground">
              Fill rate:{' '}
              {typeof fundamentals.fundamentals_fill_pct === 'number'
                ? `${fundamentals.fundamentals_fill_pct.toFixed(1)}%`
                : '—'}
            </p>
            <p className="text-xs text-muted-foreground">
              Filled: {fundamentals.filled_count ?? 0} / {fundamentals.tracked_total ?? 0}
            </p>
          </div>
        </Card>
      )}

      {data_accuracy && (
        <Card className="gap-0 py-0 shadow-xs ring-1 ring-border">
          <div className="flex flex-col gap-1 p-3">
            <div className="mb-1 flex items-center justify-between">
              <span className="text-sm font-semibold">Data Accuracy</span>
              <DimBadge status={data_accuracy.status} />
            </div>
            <p className="text-xs text-muted-foreground">
              Match rate:{' '}
              {typeof data_accuracy.match_rate === 'number'
                ? `${data_accuracy.match_rate.toFixed(1)}%`
                : '—'}
            </p>
            <p className="text-xs text-muted-foreground">
              Checked: {data_accuracy.bars_checked ?? 0} bars across {data_accuracy.sample_size ?? 0} symbols
            </p>
            <p className="text-xs text-muted-foreground">
              Mismatches: {data_accuracy.mismatch_count ?? 0} · Missing: {data_accuracy.missing_in_db ?? 0}
            </p>
            {data_accuracy.checked_at && (
              <p className="text-xs text-muted-foreground">
                Last check: {data_accuracy.age_days != null ? `${data_accuracy.age_days}d ago` : data_accuracy.checked_at}
              </p>
            )}
            {data_accuracy.note && (
              <p className="text-xs text-amber-600">{data_accuracy.note}</p>
            )}
            {data_accuracy.mismatches && data_accuracy.mismatches.length > 0 && (
              <div className="mt-1 space-y-0.5">
                {data_accuracy.mismatches.slice(0, 5).map((m, i) => (
                  <p key={i} className="text-xs text-destructive">
                    {m.symbol} {m.date}: {m.type === 'missing_in_db' ? 'missing' : `${m.pct_diff}% diff`}
                  </p>
                ))}
              </div>
            )}
          </div>
        </Card>
      )}

      <Card className="gap-0 py-0 shadow-xs ring-1 ring-border">
        <div className="flex flex-col gap-1 p-3">
          <div className="mb-1 flex items-center justify-between">
            <span className="text-sm font-semibold">Market Audit</span>
            <DimBadge status={audit.status} />
          </div>
          <p className="text-xs text-muted-foreground">Tracked total: {audit.tracked_total ?? '—'}</p>
          <p className="text-xs text-muted-foreground">
            Daily fill:{' '}
            {typeof audit.daily_fill_pct === 'number' ? `${audit.daily_fill_pct.toFixed(1)}%` : '—'}
          </p>
          <p className="text-xs text-muted-foreground">
            Snapshot fill:{' '}
            {typeof audit.snapshot_fill_pct === 'number' ? `${audit.snapshot_fill_pct.toFixed(1)}%` : '—'}
          </p>
          <p className="line-clamp-1 text-xs text-muted-foreground">
            Missing:{' '}
            {Array.isArray(audit.missing_sample)
              ? audit.missing_sample.slice(0, 3).join(', ') || '—'
              : '—'}
          </p>
        </div>
      </Card>

      {health.provider_metrics?.providers && Object.keys(health.provider_metrics.providers).length > 0 && (
        <Card className="gap-0 py-0 shadow-xs ring-1 ring-border lg:col-span-2">
          <div className="flex flex-col gap-1 p-3">
            <div className="mb-1 flex items-center justify-between">
              <span className="text-sm font-semibold">Provider Usage (Today)</span>
              <Badge variant="outline" className="text-xs">
                L2 Hit Rate: {health.provider_metrics.l2_hit_rate ?? 0}%
              </Badge>
            </div>
            <div className="flex flex-wrap gap-x-4 gap-y-1">
              {health.provider_metrics.providers && Object.entries(health.provider_metrics.providers).map(([name, data]) => {
                const usage = data as { calls: number; budget: number; pct: number };
                return (
                  <div key={name} className="text-xs text-muted-foreground">
                    <span className="font-medium text-foreground">{name}</span>:{' '}
                    {usage.calls}/{usage.budget}{' '}
                    <span className={cn(
                      usage.pct > 90 ? 'text-destructive' : usage.pct > 70 ? 'text-amber-600' : 'text-emerald-600'
                    )}>
                      ({usage.pct}%)
                    </span>
                  </div>
                );
              })}
            </div>
            <p className="text-xs text-muted-foreground">
              Cache: {health.provider_metrics.l1_hits ?? 0} L1 + {health.provider_metrics.l2_hits ?? 0} L2 ={' '}
              {health.provider_metrics.cache_hit_rate ?? 0}% hit rate
            </p>
          </div>
        </Card>
      )}
    </div>
  );
};

export default AdminDomainCards;
