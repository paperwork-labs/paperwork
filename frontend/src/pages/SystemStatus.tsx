import React, { useState, useCallback, useEffect } from 'react';
import {
  AlertTriangle,
  CheckCircle,
  ChevronDown,
  ChevronUp,
  Clock,
  Loader2,
  RefreshCw,
  XCircle,
  Zap,
} from 'lucide-react';
import toast from 'react-hot-toast';
import useAdminHealth from '../hooks/useAdminHealth';
import useCoverageSnapshot from '../hooks/useCoverageSnapshot';
import { useUserPreferences } from '../hooks/useUserPreferences';
import CoverageHealthStrip from '../components/coverage/CoverageHealthStrip';
import AdminDomainCards from '../components/admin/AdminDomainCards';
import AdminRunbook from '../components/admin/AdminRunbook';
import AdminOperatorActions from '../components/admin/AdminOperatorActions';
import { marketDataApi } from '../services/api';
import api from '../services/api';
import { REGIME_HEX } from '../constants/chart';
import { formatDate, formatRelativeTime } from '../utils/format';
import type { AdminHealthResponse, AutoFixStatusResponse, AutoFixTask } from '../types/adminHealth';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import * as CollapsiblePrimitive from "@radix-ui/react-collapsible";
import { Input } from '@/components/ui/input';
import { Progress } from '@/components/ui/progress';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';

const TASK_LABELS: Record<string, string> = {
  // Legacy taskstatus / JobRun names (still used by Redis publishers today)
  admin_coverage_backfill: 'Nightly Pipeline',
  admin_indicators_recompute_universe: 'Indicator Recompute',
  compute_daily_regime: 'Regime Computation',
  admin_coverage_backfill_stale: 'Stale Coverage Repair',
  admin_recover_stale_job_runs: 'Recover Stale Jobs',
  admin_snapshots_history_record: 'Snapshot History Record',
  // Aligned with backend.tasks.market.<module>.<function> symbols
  daily_bootstrap: 'Nightly Pipeline',
  health_check: 'Coverage Health Refresh',
  recompute_universe: 'Indicator Recompute',
  record_daily: 'Snapshot History Record',
  compute_daily: 'Regime Computation',
  recover_jobs: 'Recover Stale Jobs',
  stale_daily: 'Stale Coverage Repair',
  symbols: 'Daily Bars Backfill',
  'tasks.reconciliation_tasks.reconcile_all_accounts': 'Account Reconciliation',
  'tasks.account_sync.sync_all_ibkr_accounts': 'IBKR Account Sync',
  'tasks.account_sync.sync_all_schwab_accounts': 'Schwab Account Sync',
  'tasks.strategy_tasks.evaluate_strategies': 'Strategy Evaluation',
  'tasks.intelligence_tasks.generate_daily_brief': 'Daily Brief Generation',
  'tasks.auto_ops_tasks.auto_remediate_health': 'Auto-Ops Health Remediation',
};

const friendlyTaskName = (name: string): string =>
  TASK_LABELS[name] ??
  name
    .replace(/^tasks\./, '')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());

const REGIME_LABELS: Record<string, string> = {
  R1: 'Bull',
  R2: 'Cautious',
  R3: 'Chop',
  R4: 'Bear Rally',
  R5: 'Bear',
};

const STATUS_ICON: Record<string, typeof CheckCircle> = {
  green: CheckCircle,
  yellow: AlertTriangle,
  red: XCircle,
};

const STATUS_DOT: Record<string, string> = {
  green: 'bg-emerald-500',
  yellow: 'bg-amber-500',
  red: 'bg-destructive',
};

const estimateTradingDays = (sinceDate: string): number => {
  const from = new Date(sinceDate);
  const now = new Date();
  const years = (now.getTime() - from.getTime()) / (365.25 * 24 * 60 * 60 * 1000);
  return Math.round(years * 252);
};

interface PipelineStatusProps {
  health: AdminHealthResponse | null;
  loading: boolean;
  sinceDate: string;
  timezone: string;
}

const PipelineStatus: React.FC<PipelineStatusProps> = ({ health, loading, sinceDate, timezone }) => {
  if (loading) {
    return (
      <div className="flex flex-col gap-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i}>
            <Skeleton className="mb-2 h-4 w-1/2" />
            <Skeleton className="h-1.5 w-full rounded-full" />
          </div>
        ))}
      </div>
    );
  }

  if (!health) {
    return <p className="text-sm text-muted-foreground">Connecting to system health...</p>;
  }

  const dims = health.dimensions;
  const coverage = dims.coverage;
  const audit = dims.audit;
  const regime = dims.regime;
  const stageQ = dims.stage_quality;
  const jobs = dims.jobs;

  const totalTradingDays = estimateTradingDays(sinceDate);
  const dailyPct = typeof coverage.daily_pct === 'number' ? coverage.daily_pct : 0;
  const snapshotPct = typeof audit.snapshot_fill_pct === 'number' ? audit.snapshot_fill_pct : 0;
  const unknownRate = typeof stageQ.unknown_rate === 'number' ? stageQ.unknown_rate : 0;
  const indicatorPct = Math.max(0, Math.min(100, (1 - unknownRate) * 100));

  const compositeOk = coverage.status === 'green' && regime.status === 'green' && jobs.error_count === 0;
  const statusText = compositeOk
    ? `All pipelines healthy. ${jobs.ok_count} tasks completed in the last ${jobs.window_hours}h.`
    : coverage.status !== 'green'
      ? `Coverage needs attention — ${coverage.stale_daily} symbols missing latest bars. Agent will retry automatically.`
      : jobs.error_count > 0
        ? `${jobs.error_count} task failure${jobs.error_count > 1 ? 's' : ''} detected. Check agent activity below.`
        : 'Some dimensions need attention. See details below.';

  const barColor = (pct: number) =>
    pct >= 95 ? 'bg-emerald-500' : pct >= 70 ? 'bg-amber-500' : 'bg-destructive';

  return (
    <div className="flex flex-col gap-4">
      <div>
        <div className="mb-1 flex items-center justify-between gap-2">
          <span className="text-sm font-medium text-foreground">Daily Bars</span>
          <span className="font-mono text-xs text-muted-foreground">
            {coverage.tracked_count} symbols · Latest: {coverage.expected_date || '—'} · {dailyPct.toFixed(1)}%
          </span>
        </div>
        <div className="relative h-1.5 w-full overflow-hidden rounded-full bg-muted">
          <div
            className={cn('h-full rounded-full transition-[width] duration-500 ease-out', barColor(dailyPct))}
            style={{ width: `${dailyPct}%` }}
          />
        </div>
      </div>
      <div>
        <div className="mb-1 flex items-center justify-between gap-2">
          <span className="text-sm font-medium text-foreground">Indicators</span>
          <span className="font-mono text-xs text-muted-foreground">
            {indicatorPct.toFixed(0)}% classified · Unknown rate: {(unknownRate * 100).toFixed(1)}%
          </span>
        </div>
        <div className="relative h-1.5 w-full overflow-hidden rounded-full bg-muted">
          <div
            className={cn('h-full rounded-full transition-[width] duration-500 ease-out', barColor(indicatorPct))}
            style={{ width: `${indicatorPct}%` }}
          />
        </div>
      </div>
      <div>
        <div className="mb-1 flex items-center justify-between gap-2">
          <span className="text-sm font-medium text-foreground">Snapshot History</span>
          <span className="font-mono text-xs text-muted-foreground">
            ~{totalTradingDays} trading days from {sinceDate} · {snapshotPct.toFixed(1)}%
          </span>
        </div>
        <div className="relative h-1.5 w-full overflow-hidden rounded-full bg-muted">
          <div
            className={cn('h-full rounded-full transition-[width] duration-500 ease-out', barColor(snapshotPct))}
            style={{ width: `${snapshotPct}%` }}
          />
        </div>
      </div>
      <div>
        <div className="mb-1 flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-foreground">Market Regime</span>
            {regime.regime_state ? (
              <Badge
                className="border-0 font-normal text-white"
                style={{ backgroundColor: REGIME_HEX[regime.regime_state] || '#64748B' }}
              >
                {regime.regime_state} {REGIME_LABELS[regime.regime_state] || ''}
              </Badge>
            ) : null}
          </div>
          <span className="font-mono text-xs text-muted-foreground">
            {regime.regime_state
              ? `Score: ${regime.composite_score?.toFixed(1) ?? '—'} · ${regime.multiplier ?? '—'}x sizing · as of ${formatDate(regime.as_of_date, timezone)}`
              : 'Not yet computed'}
          </span>
        </div>
      </div>

      <div className="border-t border-border pt-1">
        <div className="flex gap-2">
          {compositeOk ? (
            <CheckCircle className="mt-0.5 size-3.5 shrink-0 text-emerald-500" aria-hidden />
          ) : (
            <AlertTriangle className="mt-0.5 size-3.5 shrink-0 text-amber-500" aria-hidden />
          )}
          <p className="text-sm text-muted-foreground">{statusText}</p>
        </div>
      </div>
    </div>
  );
};

interface AgentActivityProps {
  taskRuns: AdminHealthResponse['task_runs'] | undefined;
}

const AgentActivity: React.FC<AgentActivityProps> = ({ taskRuns }) => {
  if (!taskRuns) return null;

  const entries = Object.entries(taskRuns)
    .filter(([, v]) => v !== null)
    .sort((a, b) => {
      const ta = a[1]?.ts ?? '';
      const tb = b[1]?.ts ?? '';
      return tb.localeCompare(ta);
    })
    .slice(0, 10);

  if (!entries.length) {
    return <p className="text-sm text-muted-foreground">No recent agent activity recorded.</p>;
  }

  return (
    <div className="flex flex-col">
      {entries.map(([name, run]) => (
        <div
          key={name}
          className="flex items-center justify-between gap-2 rounded-md px-3 py-2 transition-colors hover:bg-muted/80"
        >
          <div className="flex min-w-0 items-center gap-2.5">
            <CheckCircle className="size-3 shrink-0 text-emerald-500" aria-hidden />
            <span className="truncate text-xs text-foreground">{friendlyTaskName(name)}</span>
          </div>
          <span className="shrink-0 font-mono text-xs text-muted-foreground">{formatRelativeTime(run?.ts)}</span>
        </div>
      ))}
    </div>
  );
};

const getDimensionHint = (key: string, dim: any): string | null => {
  if (dim.status === 'green') return null;
  switch (key) {
    case 'coverage':
      return `${dim.stale_daily} stale symbol${dim.stale_daily !== 1 ? 's' : ''} — agent retries hourly`;
    case 'stage_quality':
      return `${dim.invalid_count} invalid, ${dim.monotonicity_issues} monotonicity — recomputed nightly`;
    case 'audit':
      return 'Fill below threshold — backfill scheduled';
    case 'jobs':
      return `${dim.error_count} failure${dim.error_count !== 1 ? 's' : ''} — check activity log`;
    case 'regime':
      return dim.age_hours > 24 ? 'Regime stale — recomputed at market close' : null;
    default:
      return null;
  }
};

const SystemStatus: React.FC = () => {
  const { health, loading, refresh } = useAdminHealth();
  const { snapshot, hero: coverageHero } = useCoverageSnapshot({ fillTradingDaysWindow: 60 });
  const { timezone } = useUserPreferences();
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [sanityData, setSanityData] = useState<Record<string, unknown> | null>(null);
  const [sinceDate, setSinceDate] = useState('2021-01-01');
  const [sinceDateSaving, setSinceDateSaving] = useState(false);
  const [pollingUntil, setPollingUntil] = useState<number | null>(null);

  const [autoFixJobId, setAutoFixJobId] = useState<string | null>(null);
  const [autoFixStatus, setAutoFixStatus] = useState<AutoFixStatusResponse | null>(null);
  const [autoFixLoading, setAutoFixLoading] = useState(false);

  const compositeStatus = health?.composite_status ?? 'red';
  const StatusIcon = STATUS_ICON[compositeStatus] ?? XCircle;
  const statusIconColor =
    compositeStatus === 'green'
      ? 'text-emerald-500'
      : compositeStatus === 'yellow'
        ? 'text-amber-500'
        : 'text-destructive';

  const triggerAggressivePolling = () => {
    setPollingUntil(Date.now() + 60000);
  };

  useEffect(() => {
    if (!pollingUntil) return;
    if (Date.now() > pollingUntil) {
      setPollingUntil(null);
      return;
    }
    const interval = setInterval(() => {
      if (Date.now() > pollingUntil) {
        setPollingUntil(null);
        clearInterval(interval);
      } else {
        void refresh();
      }
    }, 5000);
    return () => clearInterval(interval);
  }, [pollingUntil, refresh]);

  const handleAutoFix = useCallback(async () => {
    setAutoFixLoading(true);
    try {
      const { data } = await marketDataApi.startAutoFix();
      if (data.status === 'healthy') {
        toast.success('All systems operational — nothing to fix!');
        setAutoFixLoading(false);
        return;
      }
      setAutoFixJobId(data.job_id);
      setAutoFixStatus({
        job_id: data.job_id,
        overall_status: 'running',
        completed_count: 0,
        total_count: data.plan.length,
        current_task: data.plan[0]?.label || null,
        plan: data.plan,
      });
      toast.success(`Agent started fixing ${data.plan.length} issue${data.plan.length !== 1 ? 's' : ''}`);
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } }; message?: string };
      toast.error(e?.response?.data?.detail || e?.message || 'Failed to start auto-fix');
      setAutoFixLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!autoFixJobId) return;

    const pollStatus = async () => {
      try {
        const { data } = await marketDataApi.getAutoFixStatus(autoFixJobId);
        setAutoFixStatus(data);

        if (data.overall_status === 'completed') {
          toast.success('Agent finished fixing all issues!');
          setAutoFixJobId(null);
          setAutoFixLoading(false);
          void refresh();
        } else if (data.overall_status === 'failed') {
          const failedTask = data.plan.find((t: AutoFixTask) => t.status === 'failed');
          toast.error(`Agent fix failed: ${failedTask?.label || 'Unknown task'}`);
          setAutoFixJobId(null);
          setAutoFixLoading(false);
          void refresh();
        }
      } catch {
        /* transient polling errors — next tick retries */
      }
    };

    void pollStatus();
    const interval = setInterval(pollStatus, 3000);
    return () => clearInterval(interval);
  }, [autoFixJobId, refresh]);

  const handleRefreshWithPolling = async () => {
    triggerAggressivePolling();
    await refresh();
  };

  const dailyFillSeries = (snapshot?.fill_by_date || []).map((r: any) => ({
    date: r.date,
    symbol_count: r.daily_filled || r.symbol_count || 0,
    pct_of_universe: r.daily_pct || r.pct_of_universe || 0,
  }));

  const snapshotFillSeries = (snapshot?.snapshot_fill_by_date || []).map((r: any) => ({
    date: r.date,
    symbol_count: r.snapshot_filled || r.symbol_count || 0,
    pct_of_universe: r.snapshot_pct || r.pct_of_universe || 0,
  }));

  const totalSymbols = coverageHero.totalSymbols || snapshot?.symbols || 0;

  const handleSinceDateUpdate = async () => {
    setSinceDateSaving(true);
    try {
      await api.post(`/market-data/admin/backfill/since-date?since_date=${encodeURIComponent(sinceDate)}`);
      toast.success(`Deep backfill queued from ${sinceDate}. This may take a while.`);
      setTimeout(() => void refresh(), 2000);
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } }; message?: string };
      toast.error(e?.response?.data?.detail || e?.message || 'Failed to queue backfill');
    } finally {
      setSinceDateSaving(false);
    }
  };

  const redDimCount = health
    ? Object.values(health.dimensions).filter((d) => d.status === 'red').length
    : 0;

  return (
    <div className="mx-auto flex max-w-[960px] flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          {loading ? (
            <Skeleton className="h-10 w-[280px] rounded-xl" />
          ) : (
            <>
              <div className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-muted">
                <StatusIcon className={cn('size-5', statusIconColor)} aria-hidden />
              </div>
              <div>
                <h1 className="font-heading text-lg font-semibold tracking-tight text-foreground">System Status</h1>
                <p className="text-xs text-muted-foreground">
                  {compositeStatus === 'green'
                    ? 'All systems operational — agents are monitoring everything.'
                    : health?.composite_reason || 'Checking system health...'}
                </p>
              </div>
            </>
          )}
        </div>
        <div className="flex items-center gap-2">
          {health?.checked_at && (
            <div className="flex items-center gap-1 text-xs text-muted-foreground">
              <Clock className="size-3" aria-hidden />
              {formatRelativeTime(health.checked_at)}
            </div>
          )}
          {redDimCount > 0 && !autoFixJobId && (
            <Button
              type="button"
              size="xs"
              className="gap-1 bg-amber-600 text-white hover:bg-amber-600/90"
              onClick={() => void handleAutoFix()}
              disabled={autoFixLoading}
            >
              <Zap className="size-3" aria-hidden />
              Fix All Issues ({redDimCount})
            </Button>
          )}
          <Button
            type="button"
            size="icon-xs"
            variant="ghost"
            onClick={() => void refresh()}
            aria-label="Refresh"
            disabled={autoFixLoading}
          >
            <RefreshCw className="size-3.5" />
          </Button>
        </div>
      </div>

      {autoFixStatus && autoFixJobId && (
        <Card className="border-orange-700/50 bg-gradient-to-br from-orange-950/40 to-card">
          <CardContent className="space-y-4 pt-6">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <Loader2 className="size-4 animate-spin text-orange-400" aria-hidden />
                <div>
                  <p className="text-sm font-semibold text-orange-300">Agent Fixing Issues</p>
                  <p className="text-xs text-muted-foreground">
                    {autoFixStatus.completed_count} of {autoFixStatus.total_count} tasks completed
                  </p>
                </div>
              </div>
              <Badge variant="outline" className="border-orange-500/40 bg-orange-500/10 text-orange-200">
                {Math.round((autoFixStatus.completed_count / autoFixStatus.total_count) * 100)}%
              </Badge>
            </div>
            <Progress
              value={(autoFixStatus.completed_count / autoFixStatus.total_count) * 100}
              className="h-2 bg-white/10 [&>[data-slot=progress-indicator]]:bg-orange-400"
            />
            <div className="flex flex-col gap-2">
              {autoFixStatus.plan.map((task) => {
                const TaskIcon =
                  task.status === 'completed'
                    ? CheckCircle
                    : task.status === 'running'
                      ? Loader2
                      : task.status === 'failed'
                        ? XCircle
                        : Clock;
                const iconCls =
                  task.status === 'completed'
                    ? 'text-emerald-400'
                    : task.status === 'running'
                      ? 'text-orange-400'
                      : task.status === 'failed'
                        ? 'text-red-400'
                        : 'text-muted-foreground';

                return (
                  <div
                    key={task.task_name}
                    className={cn(
                      'flex items-start gap-3 rounded-md px-3 py-2',
                      task.status === 'running' ? 'bg-white/5' : '',
                    )}
                  >
                    <div className={cn('shrink-0 pt-0.5', iconCls)}>
                      {task.status === 'running' ? (
                        <Loader2 className="size-3.5 animate-spin text-orange-400" aria-hidden />
                      ) : (
                        <TaskIcon className="size-3.5" aria-hidden />
                      )}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p
                        className={cn(
                          'text-sm',
                          task.status === 'running'
                            ? 'font-medium text-foreground'
                            : task.status === 'completed'
                              ? 'text-muted-foreground'
                              : 'text-muted-foreground/80',
                        )}
                      >
                        {task.label}
                      </p>
                      {task.status === 'running' && task.reason && (
                        <p className="text-[10px] text-muted-foreground">{task.reason}</p>
                      )}
                      {task.error && <p className="text-[10px] text-red-400">{task.error}</p>}
                    </div>
                    {task.status === 'completed' && (
                      <span className="shrink-0 font-mono text-[10px] text-muted-foreground">Done</span>
                    )}
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardContent className="space-y-4 pt-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-xs font-semibold tracking-wider text-muted-foreground uppercase">Pipeline Status</p>
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs text-muted-foreground">Data valid from</span>
              <Input
                type="date"
                value={sinceDate}
                onChange={(e) => setSinceDate(e.target.value)}
                className="h-7 w-[140px] font-mono text-xs"
              />
              <Button
                type="button"
                size="xs"
                variant="outline"
                onClick={() => void handleSinceDateUpdate()}
                disabled={sinceDateSaving}
              >
                {sinceDateSaving ? 'Queuing...' : 'Update'}
              </Button>
            </div>
          </div>
          <PipelineStatus health={health} loading={loading} sinceDate={sinceDate} timezone={timezone} />
          <p className="text-xs text-muted-foreground">
            Agents monitor all pipelines automatically. Coverage refreshes hourly, indicators recompute daily, regime
            scores at market close.
          </p>
        </CardContent>
      </Card>

      {dailyFillSeries.length > 0 && (
        <Card>
          <CardContent className="pt-6">
            <p className="mb-2 text-xs font-semibold tracking-wider text-muted-foreground uppercase">
              Data Coverage — Last 60 Trading Days
            </p>
            <CoverageHealthStrip
              dailyFillSeries={dailyFillSeries}
              snapshotFillSeries={snapshotFillSeries}
              windowDays={60}
              totalSymbols={totalSymbols}
            />
          </CardContent>
        </Card>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardContent className="pt-6">
            <p className="mb-3 text-xs font-semibold tracking-wider text-muted-foreground uppercase">
              Agent Activity
            </p>
            <div className="max-h-[280px] overflow-y-auto">
              <AgentActivity taskRuns={health?.task_runs} />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <p className="mb-3 text-xs font-semibold tracking-wider text-muted-foreground uppercase">
              Health Dimensions
            </p>
            {loading ? (
              <div className="flex flex-col gap-2">
                {[1, 2, 3, 4, 5].map((i) => (
                  <Skeleton key={i} className="h-8 w-full rounded-md" />
                ))}
              </div>
            ) : (
              <div className="flex flex-col gap-1.5">
                {health &&
                  Object.entries(health.dimensions).map(([key, dim]) => {
                    const status = dim.status;
                    const hint = getDimensionHint(key, dim);
                    return (
                      <div key={key} className="rounded-lg bg-muted/50 px-3 py-2">
                        <div className="flex items-center justify-between gap-2">
                          <div className="flex items-center gap-2">
                            <span
                              className={cn(
                                'size-[7px] shrink-0 rounded-full',
                                STATUS_DOT[status] || 'bg-muted-foreground/50',
                              )}
                            />
                            <span className="text-sm font-medium capitalize text-foreground">
                              {key.replace(/_/g, ' ')}
                            </span>
                          </div>
                          <Badge
                            variant="outline"
                            className={cn(
                              'font-normal',
                              status === 'green'
                                ? 'border-emerald-500/40 text-emerald-700 dark:text-emerald-300'
                                : 'border-destructive/40 text-destructive',
                            )}
                          >
                            {status.toUpperCase()}
                          </Badge>
                        </div>
                        {hint && <p className="mt-1 ml-4 text-[10px] text-muted-foreground">{hint}</p>}
                      </div>
                    );
                  })}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {redDimCount > 0 && <AdminRunbook health={health} />}

      <div>
        <p className="mb-2 text-xs font-semibold tracking-wider text-muted-foreground uppercase">Detailed Diagnostics</p>
        <AdminDomainCards health={health} />
      </div>

      <div className="h-px w-full bg-border" role="separator" />

      <CollapsiblePrimitive.Root open={advancedOpen} onOpenChange={setAdvancedOpen}>
        <CollapsiblePrimitive.Trigger asChild>
          <Button type="button" variant="ghost" size="sm" className="h-auto gap-2 px-2 text-muted-foreground">
            {advancedOpen ? <ChevronUp className="size-4" /> : <ChevronDown className="size-4" />}
            <span className="text-sm">Operator Actions</span>
          </Button>
        </CollapsiblePrimitive.Trigger>
        <CollapsiblePrimitive.Content className="overflow-hidden">
          <div className="mt-3">
            <AdminOperatorActions
              refreshCoverage={handleRefreshWithPolling}
              refreshHealth={handleRefreshWithPolling}
              sanityData={sanityData}
              setSanityData={setSanityData}
            />
          </div>
        </CollapsiblePrimitive.Content>
      </CollapsiblePrimitive.Root>
    </div>
  );
};

export default SystemStatus;
