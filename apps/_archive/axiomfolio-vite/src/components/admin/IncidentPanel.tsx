import * as React from 'react';
import { AlertTriangle, CheckCircle2, Loader2 } from 'lucide-react';
import toast from 'react-hot-toast';
import * as Collapsible from '@radix-ui/react-collapsible';
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
    { label: 'Backfill Stale Only', endpoint: '/market-data/admin/backfill/coverage/stale', successMsg: 'Stale-only backfill queued' },
  ],
  stage_quality: [
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
    { label: 'Backfill Snapshot History', endpoint: '/market-data/admin/backfill/snapshots/history?days=252', successMsg: 'Snapshot history backfill queued' },
  ],
  fundamentals: [
    { label: 'Fill Missing Fundamentals', endpoint: '/market-data/admin/fundamentals/fill-missing', successMsg: 'Fundamentals fill queued' },
  ],
};

const DIMENSION_LABELS: Record<string, string> = {
  coverage: 'Coverage',
  stage_quality: 'Stage Quality',
  jobs: 'Jobs',
  regime: 'Market Regime',
  audit: 'Data Audit',
  fundamentals: 'Fundamentals',
  data_accuracy: 'Data Accuracy',
  portfolio_sync: 'Portfolio Sync',
  ibkr_gateway: 'IBKR Gateway',
};

function getDimensionReason(key: string, dim: Record<string, unknown>): string {
  switch (key) {
    case 'coverage':
      return `${dim.stale_daily ?? 0} stale symbols — auto-ops retries automatically`;
    case 'stage_quality': {
      const parts: string[] = [];
      if (Number(dim.unknown_rate ?? 0) > 0.35) parts.push('High unknown rate');
      if (Number(dim.invalid_count ?? 0) > 0) parts.push(`${dim.invalid_count} invalid`);
      const driftPctRaw = dim.stage_days_drift_pct;
      const driftCount = Number(dim.stage_days_drift_count ?? dim.monotonicity_issues ?? 0);
      if (typeof driftPctRaw === 'number' && driftPctRaw > 2) {
        parts.push(`${driftPctRaw.toFixed(2)}% stage-day drift`);
      } else if (driftCount > 0 && typeof driftPctRaw !== 'number') {
        parts.push(`${driftCount} stage-day drift`);
      }
      return parts.join(', ') || 'Quality below threshold';
    }
    case 'jobs':
      return `${dim.error_count ?? 0} failures in the last ${dim.window_hours ?? 24}h`;
    case 'regime':
      return Number(dim.age_hours ?? 0) > 48 ? `Stale — ${Number(dim.age_hours ?? 0).toFixed(0)}h old` : 'Regime data issue';
    case 'audit':
      return `Daily fill: ${Number(dim.daily_fill_pct ?? 0).toFixed(0)}%, Snapshot fill: ${Number(dim.snapshot_fill_pct ?? 0).toFixed(0)}%`;
    case 'fundamentals':
      return `Fill rate: ${Number(dim.fundamentals_fill_pct ?? 0).toFixed(0)}%`;
    default:
      return 'Needs attention';
  }
}

const ActionButtons: React.FC<{ dimKey: string; onDone?: () => void }> = ({ dimKey, onDone }) => {
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
    <div className="mt-2 flex flex-wrap gap-1.5">
      {actions.map((action) => (
        <Button
          key={action.endpoint}
          size="xs"
          variant="outline"
          disabled={!!loading[action.endpoint]}
          onClick={() => void dispatch(action)}
          className="inline-flex gap-1 text-[10px]"
        >
          {loading[action.endpoint] ? <Loader2 className="size-3 shrink-0 animate-spin" aria-hidden /> : null}
          {action.label}
        </Button>
      ))}
    </div>
  );
};

export function IncidentPanel({ health, onRefreshHealth }: Props) {
  const dims = health?.dimensions;
  const redDims = dims
    ? Object.entries(dims).filter(([, d]) => d.status === 'red' || d.status === 'error')
    : [];
  const yellowDims = dims
    ? Object.entries(dims).filter(([, d]) => d.status === 'yellow' || d.status === 'warning')
    : [];
  const issueCount = redDims.length + yellowDims.length;

  // Collapsed by default so the page stays calm; expand only when the operator opens it.
  const [expanded, setExpanded] = React.useState(false);

  if (!health || issueCount === 0) {
    return (
      <div
        className="flex items-center gap-2 rounded-lg border border-emerald-500/20 bg-emerald-500/5 px-4 py-2.5"
        aria-live="polite"
      >
        <CheckCircle2 className="size-4 text-emerald-500" aria-hidden />
        <p className="text-sm text-emerald-700 dark:text-emerald-300">
          All systems operational — auto-ops is monitoring everything.
        </p>
      </div>
    );
  }

  const handleActionDone = () => {
    setTimeout(() => void onRefreshHealth?.(), 1500);
    setTimeout(() => void onRefreshHealth?.(), 4500);
  };

  return (
    <Collapsible.Root open={expanded} onOpenChange={setExpanded}>
      <div
        className={cn(
          'rounded-lg border p-3',
          redDims.length > 0
            ? 'border-destructive/30 bg-destructive/5'
            : 'border-amber-500/30 bg-amber-500/5',
        )}
        role="region"
        aria-live="polite"
        aria-label="Incident panel"
      >
        <Collapsible.Trigger
          type="button"
          className="flex w-full cursor-pointer select-none items-center justify-between gap-2 text-left outline-none focus-visible:ring-2 focus-visible:ring-ring"
          aria-expanded={expanded}
        >
          <div className="flex items-center gap-2">
            <AlertTriangle
              className={cn(
                'size-4 shrink-0',
                redDims.length > 0 ? 'text-destructive' : 'text-amber-500',
              )}
              aria-hidden
            />
            <span className="text-sm font-semibold text-foreground">
              {redDims.length > 0
                ? `${redDims.length} critical issue${redDims.length > 1 ? 's' : ''}`
                : `${yellowDims.length} warning${yellowDims.length > 1 ? 's' : ''}`}
              {' — '}
              <span className="font-normal text-muted-foreground">
                {health.composite_reason || 'auto-ops is working on it'}
              </span>
            </span>
          </div>
          <Badge variant="outline" className="shrink-0 text-[10px]">
            {expanded ? 'collapse' : 'expand'}
          </Badge>
        </Collapsible.Trigger>

        <Collapsible.Content>
          <div className="mt-3 space-y-2">
            {redDims.map(([key, dimData]) => {
              const dim = dimData as unknown as Record<string, unknown>;
              return (
                <div key={key} className="rounded-md border border-destructive/20 bg-card p-2.5">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-semibold text-destructive">
                      {DIMENSION_LABELS[key] ?? key}
                    </span>
                    <Badge variant="outline" className="border-destructive/30 text-[10px] text-destructive">
                      Critical
                    </Badge>
                  </div>
                  <p className="mt-0.5 text-xs text-muted-foreground">{getDimensionReason(key, dim)}</p>
                  <ActionButtons dimKey={key} onDone={handleActionDone} />
                </div>
              );
            })}
            {yellowDims.map(([key, dimData]) => {
              const dim = dimData as unknown as Record<string, unknown>;
              return (
                <div key={key} className="rounded-md border border-amber-500/20 bg-card p-2.5">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-semibold text-amber-600 dark:text-amber-400">
                      {DIMENSION_LABELS[key] ?? key}
                    </span>
                    <Badge variant="outline" className="border-amber-500/30 text-[10px] text-amber-600 dark:text-amber-400">
                      Warning
                    </Badge>
                  </div>
                  <p className="mt-0.5 text-xs text-muted-foreground">{getDimensionReason(key, dim)}</p>
                  <ActionButtons dimKey={key} onDone={handleActionDone} />
                </div>
              );
            })}
          </div>
        </Collapsible.Content>
      </div>
    </Collapsible.Root>
  );
}

export default IncidentPanel;
