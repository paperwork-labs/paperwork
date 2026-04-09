import * as React from 'react';
import { AlertTriangle, CheckCircle2, XCircle, Loader2, Clock, ChevronDown, ChevronRight, Square } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { formatRelativeTime } from '../../utils/format';
import type { TaskRunEntry } from '../../types/adminHealth';
import type { PipelineRunMeta } from '../../types/pipeline';

interface Props {
  taskRuns: Record<string, TaskRunEntry | null> | undefined;
  pipelineRuns: PipelineRunMeta[] | undefined;
  onRevokeTask?: (taskKey: string) => void;
  revokingTask?: string | null;
}

interface TimelineEntry {
  id: string;
  taskKey: string;
  name: string;
  status: string;
  ts: string | null;
  error?: string | null;
  duration?: string | null;
  source: 'task' | 'pipeline';
  isLatestPipeline?: boolean;
  triggeredBy?: string | null;
}

const TASK_LABELS: Record<string, string> = {
  admin_coverage_backfill: 'Coverage Backfill',
  admin_indicators_recompute_universe: 'Indicator Recompute',
  compute_daily_regime: 'Regime Computation',
  admin_coverage_backfill_stale: 'Stale Coverage Repair',
  admin_recover_stale_job_runs: 'Recover Stale Jobs',
  admin_snapshots_history_record: 'Snapshot History Record',
  daily_bootstrap: 'Nightly Pipeline',
  health_check: 'Coverage Health Refresh',
  recompute_universe: 'Indicator Recompute',
  record_daily: 'Snapshot History Record',
  compute_daily: 'Regime Computation',
  recover_jobs: 'Recover Stale Jobs',
  stale_daily: 'Stale Coverage Repair',
  auto_ops_health_check: 'Auto-Ops Health',
};

function friendlyPipelineName(run: PipelineRunMeta): string {
  const by = run.triggered_by || '';
  if (by === 'manual' || by === 'admin') return 'Manual Pipeline Run';
  if (by.includes('schedule') || by.includes('nightly') || by.includes('celery-beat'))
    return 'Nightly Pipeline';
  if (by) return `Pipeline (${by})`;
  return 'Pipeline Run';
}

function friendlyTaskName(name: string): string {
  return (
    TASK_LABELS[name] ??
    name
      .replace(/^tasks\./, '')
      .replace(/_/g, ' ')
      .replace(/\b\w/g, (c) => c.toUpperCase())
  );
}

function formatDurationMs(startedAt: string | null, finishedAt: string | null): string | null {
  if (!startedAt || !finishedAt) return null;
  const ms = new Date(finishedAt).getTime() - new Date(startedAt).getTime();
  const s = Math.round(ms / 1000);
  if (s < 60) return `${s}s`;
  return `${Math.floor(s / 60)}m ${s % 60}s`;
}

type Filter = 'all' | 'failed' | 'running';

const StatusIcon = ({ status }: { status: string }) => {
  const Icon =
    status === 'error' ? XCircle
      : status === 'stale' ? AlertTriangle
        : status === 'running' ? Loader2
          : status === 'ok' ? CheckCircle2
            : Clock;
  const cls =
    status === 'error' ? 'text-destructive'
      : status === 'stale' ? 'text-amber-500'
        : status === 'running' ? 'text-amber-500 animate-spin'
          : status === 'ok' ? 'text-emerald-500'
            : 'text-muted-foreground';
  return <Icon className={cn('size-3 shrink-0', cls)} aria-hidden />;
};

export function Timeline({ taskRuns, pipelineRuns, onRevokeTask, revokingTask }: Props) {
  const [filter, setFilter] = React.useState<Filter>('all');
  const [olderExpanded, setOlderExpanded] = React.useState(false);

  const entries = React.useMemo<TimelineEntry[]>(() => {
    const items: TimelineEntry[] = [];

    if (taskRuns) {
      for (const [name, run] of Object.entries(taskRuns)) {
        if (!run) continue;
        const payload = run.payload as Record<string, unknown> | undefined;
        items.push({
          id: `task-${name}`,
          taskKey: name,
          name: friendlyTaskName(name),
          status: run.status,
          ts: run.ts ?? '',
          error: typeof payload?.error === 'string' ? payload.error : null,
          duration: null,
          source: 'task',
        });
      }
    }

    if (pipelineRuns) {
      const sorted = [...pipelineRuns].sort(
        (a, b) => (b.started_at || '').localeCompare(a.started_at || ''),
      );
      sorted.forEach((run, idx) => {
        items.push({
          id: `pipe-${run.run_id}`,
          taskKey: run.run_id,
          name: friendlyPipelineName(run),
          status: run.status,
          ts: run.started_at,
          error: null,
          duration: formatDurationMs(run.started_at, run.finished_at),
          source: 'pipeline',
          isLatestPipeline: idx === 0,
          triggeredBy: run.triggered_by,
        });
      });
    }

    items.sort((a, b) => (b.ts || '').localeCompare(a.ts || ''));

    const STALE_MS = 30 * 60 * 1000;
    const now = Date.now();
    for (const item of items) {
      if (item.status === 'running' && item.ts) {
        const age = now - new Date(item.ts).getTime();
        if (age > STALE_MS) item.status = 'stale';
      }
    }

    return items;
  }, [taskRuns, pipelineRuns]);

  const filtered = React.useMemo(() => {
    if (filter === 'failed') return entries.filter((e) => e.status === 'error');
    if (filter === 'running') return entries.filter((e) => e.status === 'running' || e.status === 'queued');
    return entries;
  }, [entries, filter]);

  const latestPipeline = filtered.find((e) => e.isLatestPipeline);
  const rest = filtered.filter((e) => !e.isLatestPipeline);
  const runningItems = rest.filter((e) => e.status === 'running' || e.status === 'queued');
  const nonRunning = rest.filter((e) => e.status !== 'running' && e.status !== 'queued');
  const recentItems = [...runningItems, ...nonRunning.slice(0, 8 - runningItems.length)];
  const olderItems = nonRunning.slice(Math.max(0, 8 - runningItems.length));

  return (
    <div>
      <div className="mb-2 flex items-center justify-between gap-2">
        <p className="text-xs font-semibold tracking-wider text-muted-foreground uppercase">
          Timeline
        </p>
        <div className="flex gap-1">
          {(['all', 'failed', 'running'] as Filter[]).map((f) => (
            <button
              key={f}
              type="button"
              onClick={() => setFilter(f)}
              className={cn(
                'cursor-pointer rounded-md px-2 py-0.5 text-[10px] font-medium outline-none transition-colors',
                'focus-visible:ring-2 focus-visible:ring-ring',
                filter === f
                  ? 'bg-primary/10 text-primary'
                  : 'text-muted-foreground hover:bg-muted',
              )}
            >
              {f === 'all' ? 'All' : f === 'failed' ? 'Failed' : 'Running'}
            </button>
          ))}
        </div>
      </div>

      {filtered.length === 0 ? (
        <p className="text-xs text-muted-foreground">No activity recorded.</p>
      ) : (
        <div className="flex flex-col gap-0.5">
          {/* Latest pipeline run — prominent */}
          {latestPipeline && (
            <div className="mb-1 rounded-lg border border-primary/20 bg-primary/5 px-3 py-2">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <StatusIcon status={latestPipeline.status} />
                  <span className="text-xs font-medium text-foreground">
                    {latestPipeline.name}
                  </span>
                  <Badge variant="outline" className="text-[8px] px-1 py-0 border-primary/30">
                    Latest
                  </Badge>
                </div>
                <div className="flex shrink-0 items-center gap-1.5">
                  {latestPipeline.duration && (
                    <span className="font-mono text-[10px] text-muted-foreground">
                      {latestPipeline.duration}
                    </span>
                  )}
                  <span className="font-mono text-[10px] text-muted-foreground">
                    {formatRelativeTime(latestPipeline.ts || null)}
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Recent entries — compact */}
          {recentItems.map((entry) => (
            <div
              key={entry.id}
              className="group flex items-start gap-2 rounded-md px-2 py-1 transition-colors hover:bg-muted/80"
            >
              <StatusIcon status={entry.status} />
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate text-xs text-foreground">{entry.name}</span>
                  <div className="flex shrink-0 items-center gap-1.5">
                    {(entry.status === 'running' || entry.status === 'stale') && entry.source === 'task' && onRevokeTask && (
                      <button
                        type="button"
                        onClick={() => onRevokeTask(entry.taskKey)}
                        disabled={revokingTask === entry.taskKey}
                        className="rounded px-1 py-0.5 text-[9px] font-medium text-destructive/70 transition-colors hover:bg-destructive/10 hover:text-destructive"
                        aria-label={`Stop ${entry.name}`}
                      >
                        {revokingTask === entry.taskKey ? (
                          <Loader2 className="size-3 animate-spin" aria-hidden />
                        ) : (
                          'Kill'
                        )}
                      </button>
                    )}
                    {entry.duration && (
                      <span className="font-mono text-[10px] text-muted-foreground">
                        {entry.duration}
                      </span>
                    )}
                    {entry.source === 'pipeline' && (
                      <Badge variant="outline" className="text-[8px] px-1 py-0">
                        DAG
                      </Badge>
                    )}
                    <span className="font-mono text-[10px] text-muted-foreground">
                      {formatRelativeTime(entry.ts || null)}
                    </span>
                  </div>
                </div>
                {entry.error && (
                  <p className="mt-0.5 text-[10px] text-destructive line-clamp-2">
                    {entry.error.slice(0, 200)}
                  </p>
                )}
              </div>
            </div>
          ))}

          {/* Older entries — collapsible */}
          {olderItems.length > 0 && (
            <button
              type="button"
              onClick={() => setOlderExpanded((v) => !v)}
              className={cn(
                'mt-1 flex w-full items-center gap-1 rounded-md px-2 py-1 text-left outline-none',
                'text-[10px] font-medium text-muted-foreground hover:text-foreground',
                'focus-visible:ring-2 focus-visible:ring-ring',
              )}
            >
              {olderExpanded ? (
                <ChevronDown className="size-3" aria-hidden />
              ) : (
                <ChevronRight className="size-3" aria-hidden />
              )}
              {olderItems.length} older {olderItems.length === 1 ? 'entry' : 'entries'}
            </button>
          )}
          {olderExpanded &&
            olderItems.map((entry) => (
              <div
                key={entry.id}
                className="flex items-start gap-2 rounded-md px-2 py-0.5 text-muted-foreground transition-colors hover:bg-muted/80"
              >
                <StatusIcon status={entry.status} />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate text-[11px]">{entry.name}</span>
                    <span className="shrink-0 font-mono text-[10px]">
                      {formatRelativeTime(entry.ts || null)}
                    </span>
                  </div>
                </div>
              </div>
            ))}
        </div>
      )}
    </div>
  );
}

export default Timeline;
