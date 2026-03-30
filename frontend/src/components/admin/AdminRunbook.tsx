import React from 'react';
import * as Collapsible from "@radix-ui/react-collapsible";
import { ChevronDown, ChevronUp, Loader2 } from 'lucide-react';
import toast from 'react-hot-toast';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import api from '../../services/api';
import type { AdminHealthResponse } from '../../types/adminHealth';

interface Props {
  health: AdminHealthResponse | null;
  onRefreshHealth?: () => Promise<void>;
}

interface ActionDef {
  label: string;
  endpoint: string;
  method?: 'GET' | 'POST';
  successMsg: string;
}

const DIMENSION_ACTIONS: Record<string, ActionDef[]> = {
  coverage: [
    { label: 'Refresh Coverage', endpoint: '/market-data/admin/backfill/coverage/refresh', successMsg: 'Coverage refresh queued' },
    { label: 'Backfill Daily (Tracked)', endpoint: '/market-data/admin/backfill/coverage', successMsg: 'Daily coverage backfill queued' },
    { label: 'Backfill Stale Only', endpoint: '/market-data/admin/backfill/coverage/stale', successMsg: 'Stale-only backfill queued' },
  ],
  stage_quality: [
    { label: 'Backfill Daily (Tracked)', endpoint: '/market-data/admin/backfill/coverage', successMsg: 'Daily coverage backfill queued' },
    { label: 'Recompute Indicators', endpoint: '/market-data/admin/indicators/recompute-universe', successMsg: 'Indicator recompute queued' },
    { label: 'Repair Stage History', endpoint: '/market-data/admin/stage/repair', successMsg: 'Stage history repair queued' },
  ],
  jobs: [
    { label: 'Recover Stale Jobs', endpoint: '/market-data/admin/jobs/recover-stale', successMsg: 'Stale jobs recovered' },
  ],
  regime: [
    { label: 'Compute Market Regime', endpoint: '/market-data/admin/regime/compute', successMsg: 'Regime computation queued' },
  ],
  audit: [
    { label: 'Backfill Daily (Tracked)', endpoint: '/market-data/admin/backfill/coverage', successMsg: 'Daily coverage backfill queued' },
    { label: 'Backfill Snapshot History', endpoint: '/market-data/admin/backfill/snapshots/history?days=252', successMsg: 'Snapshot history backfill queued' },
  ],
  fundamentals: [
    { label: 'Fill Missing Fundamentals', endpoint: '/market-data/admin/fundamentals/fill-missing', successMsg: 'Fundamentals fill queued' },
  ],
};

interface RunbookEntry {
  what: string;
  steps: string[];
  contextualSteps?: (dim: Record<string, unknown>) => string[];
  threshold: (thresholds: Record<string, number>) => string;
  metricSummary?: (dim: Record<string, unknown>) => Array<{ label: string; value: string; ok: boolean }>;
}

const RUNBOOK: Record<string, RunbookEntry> = {
  coverage: {
    what: 'Daily price coverage has dropped below the required fill percentage or has stale trading dates.',
    steps: [
      'Auto-ops checks health every 15 minutes and triggers backfills automatically.',
      'Refresh coverage to see current state.',
      'If still stale, backfill daily coverage for tracked symbols or stale-only.',
      'Check Agent Activity above for failed nightly pipeline or backfill tasks.',
    ],
    threshold: (t) =>
      `Daily fill >= ${t.coverage_daily_pct_min ?? 95}%, stale daily rows <= ${t.coverage_stale_daily_max ?? 0}`,
  },
  stage_quality: {
    what: 'Stage analysis has too many unknowns, invalid rows, or monotonicity violations in stage duration counters.',
    steps: [
      'Ensure daily bars are backfilled — stages cannot compute without OHLCV data.',
      'Recompute indicators to recalculate stage labels for the full universe.',
      'Repair stage history to fix stage duration counters (current_stage_days) across history.',
      'Check Agent Activity above for failed compute or backfill tasks.',
    ],
    contextualSteps: (dim) => {
      const steps: string[] = [];
      const unknownRate = Number(dim.unknown_rate ?? 0);
      const monotonicity = Number(dim.monotonicity_issues ?? 0);
      const invalidCount = Number(dim.invalid_count ?? 0);

      if (unknownRate > 0.35) {
        steps.push('Too many UNKNOWN stages — daily bars are likely missing. Backfill daily coverage first, then recompute indicators.');
      }
      if (monotonicity > 0) {
        steps.push('Stage day-counter gaps detected — repair stage history to recompute current_stage_days across the last 120 days.');
      }
      if (invalidCount > 0) {
        steps.push('Invalid stage rows found — check Agent Activity for failed tasks, then recompute indicators.');
      }
      if (unknownRate <= 0.35 && monotonicity === 0 && invalidCount === 0) {
        steps.push('All stage sub-checks are passing. If this dimension is still red, check Agent Activity for ongoing issues.');
      }
      return steps;
    },
    threshold: (t) =>
      `Unknown rate <= ${((t.stage_unknown_rate_max ?? 0.35) * 100).toFixed(0)}%, invalid rows <= ${t.stage_invalid_max ?? 0}, monotonicity issues <= ${t.stage_monotonicity_max ?? 0}`,
    metricSummary: (dim) => [
      { label: 'Unknown rate', value: `${((Number(dim.unknown_rate ?? 0)) * 100).toFixed(2)}%`, ok: Number(dim.unknown_rate ?? 0) <= 0.35 },
      { label: 'Invalid rows', value: String(dim.invalid_count ?? 0), ok: Number(dim.invalid_count ?? 0) === 0 },
      { label: 'Monotonicity', value: String(dim.monotonicity_issues ?? 0), ok: Number(dim.monotonicity_issues ?? 0) === 0 },
      { label: 'Stale stages', value: String(dim.stale_stage_count ?? 0), ok: Number(dim.stale_stage_count ?? 0) === 0 },
    ],
  },
  jobs: {
    what: 'One or more background jobs have failed in the lookback window.',
    steps: [
      'Inspect Agent Activity above for the failed task and error details.',
      'Recover stale jobs to reset stuck RUNNING tasks.',
      'If the error is environmental (API key, network), fix the root cause. The schedule auto-retries on the next cron tick.',
    ],
    threshold: (t) =>
      `Success rate >= ${((t.jobs_success_rate_min ?? 0.9) * 100).toFixed(0)}% in the last ${t.jobs_lookback_hours ?? 24}h`,
  },
  regime: {
    what: 'Market regime data is missing or stale (>48h since last computation).',
    steps: [
      'Check Agent Activity for failed nightly pipeline or regime tasks.',
      'Verify VIX/breadth data feeds are accessible (yfinance for ^VIX, ^VIX3M).',
      'Compute the market regime manually if the nightly pipeline missed it.',
      'If breadth data (% >200D, % >50D) is off, ensure the nightly indicator pipeline ran successfully first.',
    ],
    threshold: () => 'Regime data must be less than 48 hours old',
    metricSummary: (dim) => [
      { label: 'State', value: String(dim.regime_state ?? '—'), ok: !!dim.regime_state },
      { label: 'Score', value: String(dim.composite_score ?? '—'), ok: !!dim.composite_score },
      { label: 'Age', value: `${Number(dim.age_hours ?? 0).toFixed(1)}h`, ok: Number(dim.age_hours ?? 0) < 48 },
    ],
  },
  audit: {
    what: 'Market audit detected that daily or snapshot fill percentages are below acceptable thresholds for the tracked universe.',
    steps: [
      'Auto-ops checks health every 15 minutes and triggers remediation automatically.',
      'For low daily fill: backfill daily coverage for tracked symbols.',
      'For low snapshot fill: backfill snapshot history.',
      'If specific symbols are listed as missing, verify they are still tracked in Market > Tracked.',
    ],
    threshold: (t) =>
      `Daily fill >= ${t.audit_daily_fill_pct_min ?? 95}%, snapshot fill >= ${t.audit_snapshot_fill_pct_min ?? 90}%`,
    metricSummary: (dim) => [
      { label: 'Daily fill', value: `${Number(dim.daily_fill_pct ?? 0).toFixed(1)}%`, ok: Number(dim.daily_fill_pct ?? 0) >= 95 },
      { label: 'Snapshot fill', value: `${Number(dim.snapshot_fill_pct ?? 0).toFixed(1)}%`, ok: Number(dim.snapshot_fill_pct ?? 0) >= 90 },
      { label: 'Tracked total', value: String(dim.tracked_total ?? '—'), ok: true },
    ],
  },
  fundamentals: {
    what: 'Fundamentals data (earnings, sector, market cap) is incomplete for the tracked universe.',
    steps: [
      'Fill missing fundamentals to fetch data from the provider for symbols without it.',
      'Check Agent Activity for failed fundamentals tasks.',
    ],
    threshold: (t) =>
      `Fill >= ${t.fundamentals_fill_pct_pass ?? 80}% (warn at ${t.fundamentals_fill_pct_warn ?? 50}%)`,
    metricSummary: (dim) => [
      { label: 'Fill', value: `${Number(dim.fundamentals_fill_pct ?? 0).toFixed(1)}%`, ok: Number(dim.fundamentals_fill_pct ?? 0) >= 80 },
      { label: 'Filled', value: String(dim.filled_count ?? 0), ok: true },
      { label: 'Tracked', value: String(dim.tracked_total ?? '—'), ok: true },
    ],
  },
};

function metricBadgeClass(ok: boolean): string {
  return ok
    ? 'border-transparent bg-[rgb(var(--status-success)/0.12)] text-[rgb(var(--status-success)/1)]'
    : 'border-transparent bg-destructive/10 text-destructive';
}

const RunbookActions: React.FC<{ dimKey: string; onDone?: () => void }> = ({ dimKey, onDone }) => {
  const actions = DIMENSION_ACTIONS[dimKey];
  const [loading, setLoading] = React.useState<Record<string, boolean>>({});

  if (!actions?.length) return null;

  const dispatch = async (action: ActionDef) => {
    if (loading[action.endpoint]) return;
    setLoading((s) => ({ ...s, [action.endpoint]: true }));
    try {
      if (action.method === 'GET') {
        await api.get(action.endpoint);
      } else {
        await api.post(action.endpoint);
      }
      toast.success(action.successMsg);
      onDone?.();
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } }; message?: string };
      toast.error(e?.response?.data?.detail || e?.message || `Failed: ${action.label}`);
    } finally {
      setLoading((s) => ({ ...s, [action.endpoint]: false }));
    }
  };

  return (
    <div className="mt-2 flex flex-wrap gap-2">
      {actions.map((action) => (
        <Button
          key={action.endpoint}
          size="xs"
          variant="outline"
          disabled={!!loading[action.endpoint]}
          onClick={() => void dispatch(action)}
          className="inline-flex gap-1.5"
        >
          {loading[action.endpoint] ? <Loader2 className="size-3 shrink-0 animate-spin" aria-hidden /> : null}
          {action.label}
        </Button>
      ))}
    </div>
  );
};

const AdminRunbook: React.FC<Props> = ({ health, onRefreshHealth }) => {
  const [expanded, setExpanded] = React.useState(false);

  if (!health) return null;

  const dims = health.dimensions;
  const redDims = Object.entries(dims).filter(
    ([, dim]) => dim.status === 'red' || dim.status === 'error',
  );

  const handleActionDone = () => {
    setTimeout(() => void onRefreshHealth?.(), 1500);
    setTimeout(() => void onRefreshHealth?.(), 4500);
  };

  return (
    <Collapsible.Root open={expanded} onOpenChange={setExpanded}>
      <div className="mb-4 rounded-lg border border-border bg-muted/50 p-3">
        <Collapsible.Trigger
          type="button"
          className="flex w-full cursor-pointer select-none items-center justify-between gap-2 rounded-md text-left outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
          aria-expanded={expanded}
        >
          <span className="text-sm font-semibold">
            Runbook / On-Call Guide{' '}
            {redDims.length > 0 ? `(${redDims.length} issue${redDims.length > 1 ? 's' : ''})` : ''}
          </span>
          <span className="flex shrink-0 items-center gap-1 text-xs text-muted-foreground">
            {expanded ? (
              <>
                <ChevronUp className="size-3.5" aria-hidden />
                collapse
              </>
            ) : (
              <>
                <ChevronDown className="size-3.5" aria-hidden />
                expand
              </>
            )}
          </span>
        </Collapsible.Trigger>

        <Collapsible.Content>
          <div className="mt-2">
            {redDims.length === 0 ? (
              <p className="text-xs text-[rgb(var(--status-success)/1)]">All systems healthy — no action needed.</p>
            ) : (
              redDims.map(([key, dimData]) => {
                const entry = RUNBOOK[key];
                if (!entry) return null;

                const dim = dimData as unknown as Record<string, unknown>;
                let steps: string[];
                try {
                  steps = entry.contextualSteps ? entry.contextualSteps(dim) : entry.steps;
                } catch {
                  steps = entry.steps;
                }

                const metrics = entry.metricSummary ? entry.metricSummary(dim) : null;

                return (
                  <div
                    key={key}
                    className="mt-2 rounded-md border border-border bg-card p-2"
                  >
                    <p className="mb-1 text-sm font-semibold text-[rgb(var(--status-danger)/1)]">
                      {key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
                    </p>
                    <p className="mb-1 text-xs text-foreground">
                      <strong>What:</strong> {entry.what}
                    </p>
                    <p className="mb-1 text-xs text-foreground">
                      <strong>Fix:</strong>
                    </p>
                    <ol className="mb-1 list-decimal pl-4 text-xs text-foreground">
                      {steps.map((step, idx) => (
                        <li key={idx} className="mb-0.5">
                          {step}
                        </li>
                      ))}
                    </ol>
                    <RunbookActions dimKey={key} onDone={handleActionDone} />
                    {metrics && (
                      <div className="mb-1 mt-2 flex flex-wrap gap-3">
                        {metrics.map((m) => (
                          <Badge
                            key={m.label}
                            variant="outline"
                            className={cn('text-xs font-medium', metricBadgeClass(m.ok))}
                          >
                            {m.label}: {m.value}
                          </Badge>
                        ))}
                      </div>
                    )}
                    <p className="mt-1 text-xs text-muted-foreground">
                      <strong>Threshold:</strong> {entry.threshold(health.thresholds)}
                    </p>
                  </div>
                );
              })
            )}
          </div>
        </Collapsible.Content>
      </div>
    </Collapsible.Root>
  );
};

export default AdminRunbook;
