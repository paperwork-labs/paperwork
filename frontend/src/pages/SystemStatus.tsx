import React, { useState, useCallback, useEffect } from 'react';
import {
  AlertTriangle,
  CheckCircle,
  ChevronRight,
  Clock,
  Loader2,
  OctagonX,
  Play,
  RefreshCw,
  XCircle,
  Zap,
} from 'lucide-react';
import toast from 'react-hot-toast';
import useAdminHealth from '../hooks/useAdminHealth';
import useCoverageSnapshot from '../hooks/useCoverageSnapshot';
import {
  useActiveTasks,
  usePipelineAmbient,
  usePipelineDAG,
  usePipelineRun,
  usePipelineRuns,
  useRetryStep,
  useStopAllTasks,
  useTriggerPipeline,
} from '../hooks/usePipelineRun';
import type { CoverageFillByDateRow } from '../utils/coverage';
import { useUserPreferences } from '../hooks/useUserPreferences';
import CoverageHealthStrip from '../components/coverage/CoverageHealthStrip';

import AdminOperatorActions from '../components/admin/AdminOperatorActions';
import { IncidentPanel } from '../components/admin/IncidentPanel';
import { ProviderIntelligence } from '../components/admin/ProviderIntelligence';
import { Timeline } from '../components/admin/Timeline';
import { PipelineDAG } from '../components/pipeline/PipelineDAG';
import { HealthGrid } from '../components/shared/HealthGrid';
import { marketDataApi, pipelineApi } from '../services/api';
import api from '../services/api';
import { formatRelativeTime } from '../utils/format';
import type { AdminHealthResponse, AutoFixStatusResponse, AutoFixTask } from '../types/adminHealth';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import { Switch } from '@/components/ui/switch';
import { cn } from '@/lib/utils';
import ErrorBoundary from '@/components/ErrorBoundary';

// ---------------------------------------------------------------------------
// Status Banner
// ---------------------------------------------------------------------------

interface StatusBannerProps {
  health: AdminHealthResponse | null;
  loading: boolean;
  isError: boolean;
  onRefresh: () => void;
  onAutoFix: () => void;
  autoFixLoading: boolean;
  autoFixJobId: string | null;
  redDimCount: number;
}

function StatusBanner({
  health,
  loading,
  isError,
  onRefresh,
  onAutoFix,
  autoFixLoading,
  autoFixJobId,
  redDimCount,
}: StatusBannerProps) {
  if (loading) {
    return <Skeleton className="h-14 w-full rounded-xl" />;
  }

  if (isError) {
    return (
      <div
        className="flex items-center justify-between gap-3 rounded-xl border border-amber-500/30 bg-amber-500/5 px-4 py-3"
        role="alert"
        aria-live="polite"
      >
        <div className="flex items-center gap-3">
          <AlertTriangle className="size-5 text-amber-500" aria-hidden />
          <div>
            <p className="text-sm font-semibold text-foreground">Health data unavailable</p>
            <p className="text-xs text-muted-foreground">
              Unable to reach the health API. Displaying last known state.
            </p>
          </div>
        </div>
        <Button size="xs" variant="outline" onClick={onRefresh}>
          <RefreshCw className="mr-1 size-3" aria-hidden />
          Retry
        </Button>
      </div>
    );
  }

  const compositeStatus = health?.composite_status ?? 'red';

  if (compositeStatus === 'green') {
    return (
      <div
        className="flex items-center justify-between gap-3 rounded-xl border border-emerald-500/20 bg-emerald-500/5 px-4 py-3"
        aria-live="polite"
      >
        <div className="flex items-center gap-3">
          <CheckCircle className="size-5 text-emerald-500" aria-hidden />
          <div>
            <p className="text-sm font-semibold text-foreground">All systems operational</p>
            <p className="text-xs text-muted-foreground">
              Auto-ops is monitoring everything.
              {health?.checked_at && ` Last check: ${formatRelativeTime(health.checked_at)}`}
            </p>
          </div>
        </div>
        <Button size="icon-xs" variant="ghost" onClick={onRefresh} aria-label="Refresh">
          <RefreshCw className="size-3.5" />
        </Button>
      </div>
    );
  }

  return (
    <div
      className={cn(
        'flex items-center justify-between gap-3 rounded-xl border px-4 py-3',
        compositeStatus === 'red'
          ? 'border-destructive/30 bg-destructive/5'
          : 'border-amber-500/30 bg-amber-500/5',
      )}
      role="alert"
      aria-live="polite"
    >
      <div className="flex items-center gap-3">
        {compositeStatus === 'red' ? (
          <XCircle className="size-5 text-destructive" aria-hidden />
        ) : (
          <AlertTriangle className="size-5 text-amber-500" aria-hidden />
        )}
        <div>
          <p className="text-sm font-semibold text-foreground">
            {health?.composite_reason || 'System needs attention'}
          </p>
          <p className="text-xs text-muted-foreground">
            Auto-ops is working on it.
            {health?.checked_at && ` Last check: ${formatRelativeTime(health.checked_at)}`}
          </p>
        </div>
      </div>
      <div className="flex items-center gap-2">
        {redDimCount > 0 && !autoFixJobId && (
          <Button
            size="xs"
            className="gap-1 bg-amber-600 text-white hover:bg-amber-600/90"
            onClick={onAutoFix}
            disabled={autoFixLoading}
          >
            <Zap className="size-3" aria-hidden />
            Fix All ({redDimCount})
          </Button>
        )}
        <Button size="icon-xs" variant="ghost" onClick={onRefresh} aria-label="Refresh">
          <RefreshCw className="size-3.5" />
        </Button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// AutoFix Progress
// ---------------------------------------------------------------------------

interface AutoFixProgressProps {
  status: AutoFixStatusResponse;
}

const AUTOFIX_LABELS: Record<string, string> = {
  backfill_stale_daily: 'Backfill Stale Daily Bars',
  recompute_indicators: 'Recompute Indicators',
  record_snapshot_history: 'Record Snapshot History',
  compute_regime: 'Compute Market Regime',
  recover_stale_jobs: 'Recover Stale Jobs',
};

function AutoFixProgress({ status }: AutoFixProgressProps) {
  const pct = status.total_count > 0
    ? Math.round((status.completed_count / status.total_count) * 100)
    : 0;

  return (
    <Card className="border-orange-700/50 bg-gradient-to-br from-orange-950/40 to-card">
      <CardContent className="space-y-3 pt-6">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <Loader2 className="size-4 animate-spin text-orange-400" aria-hidden />
            <div>
              <p className="text-sm font-semibold text-orange-300">Agent Fixing Issues</p>
              <p className="text-xs text-muted-foreground">
                {status.completed_count} of {status.total_count} tasks completed
              </p>
            </div>
          </div>
          <Badge variant="outline" className="border-orange-500/40 bg-orange-500/10 text-orange-200">
            {pct}%
          </Badge>
        </div>
        <div className="flex flex-col gap-1.5">
          {status.plan.map((task) => {
            const TaskIcon =
              task.status === 'completed' ? CheckCircle
                : task.status === 'running' ? Loader2
                  : task.status === 'failed' ? XCircle
                    : Clock;
            const iconCls =
              task.status === 'completed' ? 'text-emerald-400'
                : task.status === 'running' ? 'text-orange-400'
                  : task.status === 'failed' ? 'text-red-400'
                    : 'text-muted-foreground';
            const displayLabel = AUTOFIX_LABELS[task.task] ?? task.task.replace(/_/g, ' ');
            return (
              <div
                key={task.task}
                className={cn('flex items-center gap-2.5 rounded-md px-2 py-1', task.status === 'running' && 'bg-white/5')}
              >
                {task.status === 'running' ? (
                  <Loader2 className="size-3 animate-spin text-orange-400" aria-hidden />
                ) : (
                  <TaskIcon className={cn('size-3', iconCls)} aria-hidden />
                )}
                <span className={cn('text-xs', task.status === 'running' ? 'font-medium text-foreground' : 'text-muted-foreground')}>
                  {displayLabel}
                </span>
                {task.reason && task.status !== 'completed' && (
                  <span className="text-[10px] text-muted-foreground/70">({task.reason})</span>
                )}
                {task.error && <span className="text-[10px] text-red-400">{task.error}</span>}
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Health dimension hint helper
// ---------------------------------------------------------------------------

const getDimensionHint = (key: string, dim: unknown): string | null => {
  const d = dim as Record<string, unknown>;
  const status = d.status as string;
  const isHealthy = status === 'green' || status === 'ok';

  switch (key) {
    case 'coverage':
      if (isHealthy) return `${Number(d.daily_pct ?? 0).toFixed(0)}% daily · ${Number(d.tracked_count ?? 0).toLocaleString()} tracked`;
      return `${d.stale_daily} stale symbol${d.stale_daily !== 1 ? 's' : ''} — agent retries hourly`;
    case 'stage_quality':
      if (isHealthy) return `${Number(d.total_symbols ?? 0).toLocaleString()} symbols · ${(Number(d.unknown_rate ?? 0) * 100).toFixed(0)}% unknown`;
      return `${d.invalid_count} invalid, ${d.monotonicity_issues} monotonicity — recomputed nightly`;
    case 'audit':
      if (isHealthy) return `${Number(d.daily_fill_pct ?? 0).toFixed(0)}% daily · ${Number(d.snapshot_fill_pct ?? 0).toFixed(0)}% snapshot`;
      return 'Fill below threshold — backfill scheduled';
    case 'jobs': {
      const rate = `${(Number(d.success_rate ?? 0) * 100).toFixed(0)}%`;
      if (isHealthy) return `${rate} success · ${d.total ?? 0} jobs (24h)`;
      return `${d.error_count} failure${d.error_count !== 1 ? 's' : ''} (${rate} success rate)`;
    }
    case 'regime':
      if (d.regime_state) return `${d.regime_state} · score ${Number(d.composite_score ?? 0).toFixed(2)} · ${Number(d.age_hours ?? 0).toFixed(0)}h ago`;
      return Number(d.age_hours ?? 0) > 24 ? 'Regime stale — recomputed at market close' : null;
    case 'fundamentals':
      if (isHealthy) return `${Number(d.fundamentals_fill_pct ?? 0).toFixed(0)}% filled`;
      return status === 'warning' ? `Fill at ${Number(d.fundamentals_fill_pct ?? 0).toFixed(0)}%` : 'Fundamentals data incomplete';
    case 'data_accuracy':
      if (d.note) return String(d.note);
      if (isHealthy) return `${Number(d.match_rate ?? 0).toFixed(1)}% match · ${d.bars_checked ?? 0} bars checked`;
      return `${d.mismatch_count} mismatch${Number(d.mismatch_count ?? 0) !== 1 ? 'es' : ''}`;
    case 'portfolio_sync':
      return Number(d.stale_accounts ?? 0) > 0 ? `${d.stale_accounts} stale account${d.stale_accounts !== 1 ? 's' : ''}` : null;
    case 'ibkr_gateway':
      return (d.note as string) || ((d.connection_status as string) === 'unknown' ? 'IBKR gateway not configured' : 'Gateway disconnected');
    default:
      return null;
  }
};

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

const SystemStatus: React.FC = () => {
  const { health, loading, isError, refresh } = useAdminHealth();
  const { snapshot, hero: coverageHero } = useCoverageSnapshot({ fillTradingDaysWindow: 60 });
  const { timezone } = useUserPreferences();
  const [sanityData, setSanityData] = useState<Record<string, unknown> | null>(null);
  const [operatorExpanded, setOperatorExpanded] = useState(false);


  const [autoFixJobId, setAutoFixJobId] = useState<string | null>(null);
  const [autoFixStatus, setAutoFixStatus] = useState<AutoFixStatusResponse | null>(null);
  const [autoFixLoading, setAutoFixLoading] = useState(false);

  const [pinnedPipelineRunId, setPinnedPipelineRunId] = useState<string | null>(null);
  const [runsTurboUntil, setRunsTurboUntil] = useState<number | null>(null);
  const [m5Enabled, setM5Enabled] = useState<boolean | null>(null);

  const { data: dagDef, isLoading: dagLoading, isError: dagError, refetch: refetchDag } = usePipelineDAG();
  const runsQuery = usePipelineRuns(20, runsTurboUntil);
  const effectivePipelineRunId =
    pinnedPipelineRunId ?? runsQuery.data?.[0]?.run_id ?? null;
  const { data: latestRun } = usePipelineRun(effectivePipelineRunId);
  const retryMutation = useRetryStep();
  const triggerMutation = useTriggerPipeline();
  const stopAllMutation = useStopAllTasks();
  const { data: activeTasks } = useActiveTasks();
  const [confirmStop, setConfirmStop] = useState(false);
  const [revokingTask, setRevokingTask] = useState<string | null>(null);

  // ``waiting`` is healthy backpressure (worker is busy, will start soon),
  // not a failure — keep polling fast and don't unpin the row.
  const runIsLive =
    latestRun?.status === 'running' ||
    latestRun?.status === 'queued' ||
    latestRun?.status === 'waiting';
  const { data: ambientState } = usePipelineAmbient();

  const mergedRun = React.useMemo(() => {
    const base = runIsLive ? latestRun : (ambientState ?? latestRun ?? null);
    if (!base) return null;
    if (!ambientState || base.run_id === 'ambient') return base;
    const merged = { ...base, steps: { ...base.steps } };
    for (const [step, ambientStep] of Object.entries(ambientState.steps)) {
      const pipelineStep = merged.steps[step];
      if (!pipelineStep || pipelineStep.status === 'pending') {
        merged.steps[step] = ambientStep;
      }
    }
    return merged;
  }, [latestRun, ambientState, runIsLive]);

  const displayRun = mergedRun;
  const showingAmbient = !runIsLive && displayRun?.run_id === 'ambient';

  useEffect(() => {
    if (!runsTurboUntil) return;
    if (Date.now() >= runsTurboUntil) {
      setRunsTurboUntil(null);
      return;
    }
    const ms = runsTurboUntil - Date.now();
    const t = window.setTimeout(() => setRunsTurboUntil(null), ms);
    return () => window.clearTimeout(t);
  }, [runsTurboUntil]);

  useEffect(() => {
    if (!pinnedPipelineRunId || !latestRun) return;
    if (latestRun.run_id !== pinnedPipelineRunId) return;
    const s = latestRun.status;
    if (s === 'ok' || s === 'error' || s === 'partial') {
      setPinnedPipelineRunId(null);
    }
  }, [pinnedPipelineRunId, latestRun]);

  useEffect(() => {
    marketDataApi.getBackfill5mToggle()
      .then((res) => setM5Enabled(Boolean(res?.backfill_5m_enabled)))
      .catch(() => {});
  }, []);

  const handleToggle5m = useCallback(async () => {
    const next = !m5Enabled;
    try {
      await marketDataApi.setBackfill5mToggle(next);
      setM5Enabled(next);
      toast.success(`5m candle backfill ${next ? 'enabled' : 'disabled'}`);
    } catch {
      toast.error('Failed to toggle 5m backfill');
    }
  }, [m5Enabled]);


  const compositeStatus = health?.composite_status ?? 'red';
  const redDimCount = health
    ? Object.values(health.dimensions).filter((d) => d.status === 'red' || d.status === 'error').length
    : 0;

  // Auto-fix handler
  const handleAutoFix = useCallback(async () => {
    setAutoFixLoading(true);
    try {
      const { data } = await marketDataApi.startAutoFix();
      if (data.status === 'ok') {
        toast.success('All systems operational — nothing to fix!');
        setAutoFixLoading(false);
        return;
      }
      setAutoFixJobId(data.job_id);
      setAutoFixStatus({
        job_id: data.job_id,
        status: 'running',
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

  // Auto-fix polling with failure resilience
  useEffect(() => {
    if (!autoFixJobId) return;
    let failures = 0;
    const poll = async () => {
      try {
        const { data } = await marketDataApi.getAutoFixStatus(autoFixJobId);
        failures = 0;
        setAutoFixStatus(data);
        if (data.status === 'completed') {
          toast.success('Agent finished fixing all issues!');
          setAutoFixJobId(null);
          setAutoFixLoading(false);
          void refresh();
        } else if (data.status === 'failed') {
          const failedTask = data.plan.find((t: AutoFixTask) => t.status === 'failed');
          toast.error(`Agent fix failed: ${failedTask?.task || 'Unknown task'}`);
          setAutoFixJobId(null);
          setAutoFixLoading(false);
          void refresh();
        }
      } catch {
        failures += 1;
        if (failures >= 5) {
          toast.error('Lost connection to auto-fix job. Check manually.');
          setAutoFixJobId(null);
          setAutoFixLoading(false);
        }
      }
    };
    void poll();
    const interval = setInterval(poll, 3000);
    return () => clearInterval(interval);
  }, [autoFixJobId, refresh]);

  const handleRevokeTask = useCallback(async (taskKey: string) => {
    setRevokingTask(taskKey);
    try {
      const res = await pipelineApi.revokeTask(taskKey);
      const msg = (res as { message?: string })?.message;
      toast.success(msg || `Task ${taskKey} revoked`);
      void refresh();
    } catch {
      toast.error(`Failed to revoke ${taskKey}`);
    } finally {
      setRevokingTask(null);
    }
  }, [refresh]);

  // Pipeline step retry handler
  const handleRetryStep = useCallback(
    (runId: string, step: string) => {
      retryMutation.mutate(
        { runId, step },
        {
          onSuccess: () => toast.success(`Retrying step: ${step}`),
          onError: (err: unknown) => {
            const e = err as { response?: { data?: { detail?: string } }; message?: string };
            toast.error(e?.response?.data?.detail || e?.message || `Failed to retry ${step}`);
          },
        },
      );
    },
    [retryMutation],
  );

  // Coverage data
  const dailyFillSeries = (snapshot?.daily?.fill_by_date || []).map((r: CoverageFillByDateRow) => ({
    date: r.date,
    symbol_count: r.daily_filled || r.symbol_count || 0,
    pct_of_universe: r.daily_pct || r.pct_of_universe || 0,
  }));
  const snapshotFillSeries = (snapshot?.daily?.snapshot_fill_by_date || []).map((r: CoverageFillByDateRow) => ({
    date: r.date,
    symbol_count: r.snapshot_filled || r.symbol_count || 0,
    pct_of_universe: r.snapshot_pct || r.pct_of_universe || 0,
  }));
  const totalSymbols = coverageHero.totalSymbols || Number(snapshot?.symbols) || 0;

  const pipelineActive = runIsLive;
  const lastRunTime = latestRun?.finished_at
    ? formatRelativeTime(latestRun.finished_at)
    : latestRun?.started_at
      ? `started ${formatRelativeTime(latestRun.started_at)}`
      : null;

  return (
    <div className="mx-auto flex max-w-[1040px] flex-col gap-5">
      {/* 1. Status Banner */}
      <StatusBanner
        health={health}
        loading={loading}
        isError={isError}
        onRefresh={() => void refresh()}
        onAutoFix={() => void handleAutoFix()}
        autoFixLoading={autoFixLoading}
        autoFixJobId={autoFixJobId}
        redDimCount={redDimCount}
      />

      {/* 2. Pipeline DAG — the centerpiece */}
      <Card>
        <CardContent className="pt-6">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <p className="text-xs font-semibold tracking-wider text-muted-foreground uppercase">
                Pipeline
              </p>
              {pipelineActive && latestRun?.status !== 'waiting' && (
                <Badge variant="outline" className="border-primary/40 text-primary text-[10px] gap-1">
                  <Loader2 className="size-2.5 animate-spin" aria-hidden />
                  {latestRun?.status === 'queued' ? 'Queued' : 'Running'}
                </Badge>
              )}
              {latestRun?.status === 'waiting' && (
                <Badge
                  variant="outline"
                  className="gap-1 border-amber-500/40 text-amber-500 text-[10px]"
                  title={
                    latestRun.current_task?.name
                      ? `Behind ${latestRun.current_task.name} (running for ${
                          latestRun.current_task.running_for_s ?? '?'
                        }s on ${latestRun.current_task.worker ?? 'worker'})`
                      : `Queued for ${latestRun.waiting_for_s ?? '?'}s`
                  }
                >
                  <Loader2 className="size-2.5 animate-spin" aria-hidden />
                  {latestRun.current_task?.name
                    ? `Waiting on ${latestRun.current_task.name}`
                    : `Waiting (${Math.round(latestRun.waiting_for_s ?? 0)}s)`}
                </Badge>
              )}
              {showingAmbient && (
                <span className="text-[10px] text-muted-foreground italic">Latest task states</span>
              )}
              {lastRunTime && !pipelineActive && !showingAmbient && (
                <span className="text-[10px] text-muted-foreground">Last run: {lastRunTime}</span>
              )}
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {m5Enabled != null && (
                <>
                  <div className="flex items-center gap-2">
                    <Switch
                      id="backfill-5m"
                      checked={m5Enabled}
                      onCheckedChange={() => void handleToggle5m()}
                      className="scale-75"
                    />
                    <Label htmlFor="backfill-5m" className="cursor-pointer text-xs text-muted-foreground">
                      5m Candles
                    </Label>
                  </div>
                  <div className="h-4 w-px bg-border" />
                </>
              )}
              <Button
                size="xs"
                variant="outline"
                className="gap-1"
                onClick={() => {
                  triggerMutation.mutate(undefined, {
                    onSuccess: (data) => {
                      setPinnedPipelineRunId(data.run_id);
                      setRunsTurboUntil(Date.now() + 60_000);
                      toast.success('Pipeline run dispatched');
                    },
                    onError: () => toast.error('Failed to trigger pipeline'),
                  });
                }}
                disabled={triggerMutation.isPending || pipelineActive}
              >
                <Play className="size-3" aria-hidden />
                Trigger Run
              </Button>
              {confirmStop ? (
                <div className="flex items-center gap-1">
                  <Button
                    size="xs"
                    variant="destructive"
                    className="gap-1 text-[10px]"
                    onClick={() => {
                      stopAllMutation.mutate(undefined, {
                        onSuccess: (data) => {
                          toast.success(data.message);
                          setConfirmStop(false);
                        },
                        onError: () => toast.error('Failed to stop tasks'),
                      });
                    }}
                    disabled={stopAllMutation.isPending}
                  >
                    {stopAllMutation.isPending ? (
                      <Loader2 className="size-3 animate-spin" aria-hidden />
                    ) : (
                      <OctagonX className="size-3" aria-hidden />
                    )}
                    Confirm
                  </Button>
                  <Button
                    size="xs"
                    variant="ghost"
                    className="text-[10px]"
                    onClick={() => setConfirmStop(false)}
                  >
                    Cancel
                  </Button>
                </div>
              ) : (
                <Button
                  size="xs"
                  variant="outline"
                  className="gap-1 text-destructive border-destructive/30 hover:bg-destructive/10"
                  onClick={() => setConfirmStop(true)}
                >
                  <OctagonX className="size-3" aria-hidden />
                  Stop All
                  {(() => {
                    const dagCount = activeTasks?.tasks.filter((t) => t.dag_step).length ?? 0;
                    return dagCount > 0 ? (
                      <Badge variant="secondary" className="ml-0.5 px-1 py-0 text-[9px]">
                        {dagCount}
                      </Badge>
                    ) : null;
                  })()}
                </Button>
              )}
            </div>
          </div>

          {/* Universe Overview */}
          {health?.dimensions && (
            <div className="mb-3 rounded-lg border border-border/50 bg-muted/30 px-3 py-2">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                {/* Index counts */}
                {health.dimensions.coverage?.indices && (
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                    {([
                      ['SP500', 'S&P'],
                      ['NASDAQ100', 'NDX'],
                      ['DOW30', 'DOW'],
                      ['RUSSELL2000', 'R2K'],
                    ] as const).map(([key, label]) => {
                      const count = (health.dimensions.coverage.indices as Record<string, number>)?.[key];
                      return count != null ? (
                        <span key={key} className="text-[10px] text-muted-foreground">
                          <span className="font-semibold tabular-nums text-foreground">{count.toLocaleString()}</span> {label}
                        </span>
                      ) : null;
                    })}
                    {health.dimensions.coverage.curated_etf_count != null && health.dimensions.coverage.curated_etf_count > 0 && (
                      <span className="text-[10px] text-muted-foreground">
                        <span className="font-semibold tabular-nums text-foreground">{health.dimensions.coverage.curated_etf_count}</span> ETFs
                      </span>
                    )}
                    <span className="hidden text-border/40 sm:inline">|</span>
                    {health.dimensions.coverage && (
                      <span className="text-[10px] font-medium text-muted-foreground">
                        {health.dimensions.coverage.tracked_count.toLocaleString()} total
                      </span>
                    )}
                  </div>
                )}
                {/* Data depth */}
                <div className="flex items-center gap-3 text-[10px] text-muted-foreground/70">
                  {health.dimensions.audit.ohlcv_earliest_date && (
                    <span>OHLCV from {new Date(health.dimensions.audit.ohlcv_earliest_date).getFullYear()}</span>
                  )}
                  {health.dimensions.audit.earliest_date && (
                    <span>Snapshots from {new Date(health.dimensions.audit.earliest_date).getFullYear()}</span>
                  )}
                </div>
              </div>
            </div>
          )}

          <PipelineDAG
            dag={dagDef}
            run={displayRun}
            loading={dagLoading}
            loadError={dagError}
            onRetryLoad={() => void refetchDag()}
            onRetry={handleRetryStep}
            retrying={retryMutation.isPending}
            healthDimensions={health?.dimensions}
            providerMetrics={health?.provider_metrics}
            activeTasks={activeTasks?.tasks}
            ambientSteps={ambientState?.steps}
            timezone={timezone}
          />

          {/* Coverage strip — inside pipeline card */}
          {dailyFillSeries.length > 0 && (
            <div className="mt-3 border-t border-border pt-3">
              <div className="flex items-center justify-between gap-3 mb-2">
                <p className="text-[10px] font-semibold tracking-wider text-muted-foreground uppercase">
                  Data Coverage — Last 60 Trading Days
                </p>
                <div className="flex items-center gap-3 text-[9px] text-muted-foreground">
                  <span className="flex items-center gap-1">
                    <span className="inline-block h-2 w-4 rounded-sm bg-emerald-500" />
                    Daily bars
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="inline-block h-2 w-4 rounded-sm bg-amber-500" />
                    Snapshots
                  </span>
                </div>
              </div>
              <CoverageHealthStrip
                dailyFillSeries={dailyFillSeries}
                snapshotFillSeries={snapshotFillSeries}
                windowDays={60}
                totalSymbols={totalSymbols}
              />
            </div>
          )}

          <p className="mt-3 text-xs text-muted-foreground">
            Agents monitor all pipelines automatically. Coverage refreshes hourly, indicators recompute daily, regime
            scores at market close.
          </p>
        </CardContent>
      </Card>

      {/* 3. Incident Panel */}
      <IncidentPanel health={health} onRefreshHealth={refresh} />

      {/* Auto-fix progress (shows only during active remediation) */}
      {autoFixStatus && autoFixJobId && <AutoFixProgress status={autoFixStatus} />}

      {/* 4. Health Dimensions + Timeline */}
      <div className="grid gap-4 lg:grid-cols-2 items-stretch">
        <Card className="flex flex-col">
          <CardContent className="flex flex-1 flex-col pt-6">
            <p className="mb-3 text-xs font-semibold tracking-wider text-muted-foreground uppercase">
              Health Dimensions
            </p>
            <HealthGrid
              dimensions={health?.dimensions ?? null}
              loading={loading}
              getHint={getDimensionHint}
              compact
            />
          </CardContent>
        </Card>

        <Card className="flex flex-col">
          <CardContent className="flex flex-1 min-h-0 flex-col pt-6">
            <div className="flex-1 min-h-0 overflow-y-auto">
              <Timeline
                taskRuns={health?.task_runs}
                pipelineRuns={runsQuery.data ?? undefined}
                onRevokeTask={handleRevokeTask}
                revokingTask={revokingTask}
              />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* 5. Provider Intelligence */}
      {health?.provider_metrics && (
        <Card>
          <CardContent className="pt-6">
            <ProviderIntelligence metrics={health.provider_metrics} checkedAt={health.checked_at} />
          </CardContent>
        </Card>
      )}

      {/* 6. Operator Actions (collapsed) */}
      <Collapsible open={operatorExpanded} onOpenChange={setOperatorExpanded}>
        <CollapsibleTrigger
          type="button"
          id="system-status-operator-actions-trigger"
          className={cn(
            'flex w-full cursor-pointer select-none items-center gap-2 rounded-md py-1 text-left outline-none',
            'text-xs font-semibold tracking-wider text-muted-foreground uppercase',
            'hover:text-foreground',
            'focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background',
          )}
          aria-expanded={operatorExpanded}
          aria-controls="system-status-operator-actions-panel"
        >
          <ChevronRight
            className={cn('size-4 shrink-0 text-muted-foreground transition-transform', operatorExpanded && 'rotate-90')}
            aria-hidden
          />
          Operator Actions
        </CollapsibleTrigger>
        <CollapsibleContent id="system-status-operator-actions-panel" className="mt-2">
          <ErrorBoundary
            fallback={<div className="p-4 text-sm text-muted-foreground">Something went wrong. Try refreshing.</div>}
          >
            <AdminOperatorActions
              refreshCoverage={refresh}
              refreshHealth={refresh}
              sanityData={sanityData}
              setSanityData={setSanityData}
            />
          </ErrorBoundary>
        </CollapsibleContent>
      </Collapsible>
    </div>
  );
};

export default SystemStatus;
