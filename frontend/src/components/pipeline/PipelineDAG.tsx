import * as React from 'react';
import {
  CheckCircle2,
  XCircle,
  Loader2,
  Clock,
  History,
  SkipForward,
  RotateCcw,
} from 'lucide-react';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import type {
  ActiveTaskInfo,
  PipelineDAGDefinition,
  PipelineRunState,
  PipelineStepState,
  PipelineStepStatus,
  PipelineVisualStatus,
} from '@/types/pipeline';
import type { AdminHealthResponse, ProviderMetrics } from '@/types/adminHealth';
import { formatDateFriendly, formatDateTimeFriendly } from '@/utils/format';

// ---------------------------------------------------------------------------
// Vertical grid layout — 4 rows, top-to-bottom pipeline flow
//
// Row 0  Ingestion:   constituents → tracked_cache → daily_bars → mv_refresh
// Row 1  Compute:     [gap] regime  indicators  exit_cascade
// Row 2  Downstream:  [gap] scan    strategy    snapshot_history
// Row 3  Reporting:   digest  health  audit  warm_dashboard
// ---------------------------------------------------------------------------

interface NodePos {
  col: number;
  row: number;
}

const NODE_POSITIONS: Record<string, NodePos> = {
  constituents:     { row: 0, col: 0 },
  tracked_cache:    { row: 0, col: 1 },
  daily_bars:       { row: 0, col: 2 },
  mv_refresh:       { row: 0, col: 3 },
  regime:           { row: 1, col: 1 },
  indicators:       { row: 1, col: 2 },
  exit_cascade:     { row: 1, col: 3 },
  scan_overlay:     { row: 2, col: 1 },
  strategy_eval:    { row: 2, col: 2 },
  snapshot_history: { row: 2, col: 3 },
  digest:           { row: 3, col: 0 },
  health_check:     { row: 3, col: 1 },
  audit:            { row: 3, col: 2 },
  warm_dashboard:   { row: 3, col: 3 },
};

const NODE_W = 160;
const NODE_H = 64;
const COL_GAP = 36;
const ROW_GAP = 40;
const PAD = 12;

// ---------------------------------------------------------------------------
// Health dimension mapping — connects DAG nodes to health data
// ---------------------------------------------------------------------------

type HealthDims = AdminHealthResponse['dimensions'];

const NODE_HEALTH_DIM: Record<string, keyof HealthDims> = {
  constituents: 'coverage',
  tracked_cache: 'coverage',
  daily_bars: 'coverage',
  indicators: 'stage_quality',
  regime: 'regime',
  snapshot_history: 'audit',
  health_check: 'jobs',
  audit: 'audit',
};

/** Anything older than this is rendered as ``stale`` instead of ``ok``/``error``. */
export const STALE_AGE_MS = 12 * 60 * 60 * 1000;

/** Exported for testing — true when the step's last event is older than `STALE_AGE_MS`. */
export function isStaleByAge(state: PipelineStepState | undefined): boolean {
  const lastEvent = state?.finished_at ?? state?.started_at;
  if (!lastEvent) return false;
  const t = Date.parse(lastEvent);
  if (Number.isNaN(t)) return false;
  return Date.now() - t > STALE_AGE_MS;
}

export function resolveVisualStatus(
  pipelineStatus: PipelineStepStatus,
  nodeName: string,
  dims: HealthDims | null | undefined,
  activeTasks?: ActiveTaskInfo[],
  ambientSteps?: Record<string, PipelineStepState>,
  state?: PipelineStepState,
): PipelineVisualStatus {
  if (pipelineStatus === 'running') return 'running';

  if (activeTasks?.some((t) => t.dag_step === nodeName)) return 'running';

  const ambientStep = ambientSteps?.[nodeName];
  if (ambientStep?.status === 'running') return 'running';

  if (pipelineStatus === 'skipped') return 'skipped';

  // Stale-age override for terminal statuses.  An `error` node from
  // 3 days ago should not render as a screaming red alarm — operators
  // already know about it. Same for `ok` results that haven't been
  // refreshed (likely the pipeline simply hasn't run today).
  // The state we look at is the merged step state (real run + ambient
  // fallback) when provided.
  if (pipelineStatus === 'error') {
    if (isStaleByAge(state) && isStaleByAge(ambientStep)) return 'stale';
    return 'error';
  }

  if (pipelineStatus === 'ok') {
    if (isStaleByAge(state) && isStaleByAge(ambientStep)) return 'stale';
    return 'ok';
  }

  // Health dimension overrides only apply to 'pending' nodes (ambient fill-in).
  // All real pipeline statuses are preserved above.
  if (pipelineStatus !== 'pending') return pipelineStatus;

  if (dims) {
    const dimKey = NODE_HEALTH_DIM[nodeName];
    if (dimKey) {
      const dim = dims[dimKey];
      if (dim) {
        const hs = dim.status;
        if (hs === 'green' || hs === 'ok') return 'ok';
        if (hs === 'red' || hs === 'error') return 'error';
      }
    }
  }

  return pipelineStatus;
}

function getNodeMetric(name: string, dims: HealthDims | null | undefined): string | null {
  if (!dims) return null;
  switch (name) {
    case 'constituents':
      return `${dims.coverage.tracked_count.toLocaleString()} tracked`;
    case 'tracked_cache':
      return `${dims.coverage.tracked_count.toLocaleString()} symbols`;
    case 'daily_bars':
      return dims.coverage.daily_pct >= 100
        ? '100% filled'
        : `${dims.coverage.daily_pct.toFixed(0)}% · ${dims.coverage.stale_daily} stale`;
    case 'indicators':
      return `${dims.stage_quality.total_symbols.toLocaleString()} · ${(dims.stage_quality.unknown_rate * 100).toFixed(0)}% unk`;
    case 'regime':
      return dims.regime.regime_state
        ? `${dims.regime.regime_state} · ${dims.regime.composite_score?.toFixed(2) ?? '—'}`
        : null;
    case 'snapshot_history':
      return `${dims.audit.snapshot_fill_pct.toFixed(0)}% today`;
    case 'health_check':
      return `${(dims.jobs.success_rate * 100).toFixed(0)}% success`;
    case 'audit':
      return `${dims.audit.daily_fill_pct.toFixed(0)}% daily`;
    default:
      return null;
  }
}

function nodeCenter(name: string): { x: number; y: number } {
  const pos = NODE_POSITIONS[name] ?? { col: 0, row: 0 };
  return {
    x: PAD + pos.col * (NODE_W + COL_GAP) + NODE_W / 2,
    y: PAD + pos.row * (NODE_H + ROW_GAP) + NODE_H / 2,
  };
}

function nodeTopLeft(name: string): { x: number; y: number } {
  const pos = NODE_POSITIONS[name] ?? { col: 0, row: 0 };
  return {
    x: PAD + pos.col * (NODE_W + COL_GAP),
    y: PAD + pos.row * (NODE_H + ROW_GAP),
  };
}

// ---------------------------------------------------------------------------
// Status styling
// ---------------------------------------------------------------------------

const STATUS_CLASSES: Record<PipelineVisualStatus, string> = {
  ok: 'border-emerald-500/50 bg-emerald-500/5',
  running: 'border-primary bg-primary/10 animate-pulse',
  error: 'border-destructive bg-destructive/5',
  pending: 'border-border bg-muted/50',
  skipped: 'border-border bg-muted/30 border-dashed',
  stale: 'border-border bg-muted/30',
};

const STATUS_ICON: Record<PipelineVisualStatus, React.ElementType> = {
  ok: CheckCircle2,
  running: Loader2,
  error: XCircle,
  pending: Clock,
  skipped: SkipForward,
  stale: History,
};

const STATUS_ICON_CLASS: Record<PipelineVisualStatus, string> = {
  ok: 'text-emerald-500',
  running: 'text-primary animate-spin',
  error: 'text-destructive',
  pending: 'text-muted-foreground',
  skipped: 'text-muted-foreground',
  stale: 'text-muted-foreground',
};

const EDGE_STROKE: Record<PipelineVisualStatus, string> = {
  ok: 'stroke-emerald-500/40',
  running: 'stroke-primary/50',
  error: 'stroke-destructive/30',
  pending: 'stroke-border',
  skipped: 'stroke-border',
  stale: 'stroke-border',
};

function formatDuration(seconds: number | null): string {
  if (seconds == null) return '';
  if (seconds < 60) return `${seconds.toFixed(0)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}m ${s}s`;
}

// ---------------------------------------------------------------------------
// Edge SVG — smart routing based on relative node positions
// ---------------------------------------------------------------------------

interface EdgeProps {
  fromName: string;
  toName: string;
  status: PipelineVisualStatus;
  highlighted: boolean;
  dimmed: boolean;
}

function Edge({ fromName, toName, status, highlighted, dimmed }: EdgeProps) {
  const fromPos = NODE_POSITIONS[fromName] ?? { col: 0, row: 0 };
  const toPos = NODE_POSITIONS[toName] ?? { col: 0, row: 0 };

  let d: string;
  if (fromPos.row === toPos.row) {
    const fromEdge = { x: nodeTopLeft(fromName).x + NODE_W, y: nodeCenter(fromName).y };
    const toEdge = { x: nodeTopLeft(toName).x, y: nodeCenter(toName).y };
    const midX = (fromEdge.x + toEdge.x) / 2;
    d = `M ${fromEdge.x} ${fromEdge.y} C ${midX} ${fromEdge.y}, ${midX} ${toEdge.y}, ${toEdge.x} ${toEdge.y}`;
  } else {
    const fromEdge = { x: nodeCenter(fromName).x, y: nodeTopLeft(fromName).y + NODE_H };
    const toEdge = { x: nodeCenter(toName).x, y: nodeTopLeft(toName).y };
    const midY = (fromEdge.y + toEdge.y) / 2;
    const dx = fromEdge.x - toEdge.x;
    const cp2x = toEdge.x + dx * 0.15;
    d = `M ${fromEdge.x} ${fromEdge.y} C ${fromEdge.x} ${midY}, ${cp2x} ${midY}, ${toEdge.x} ${toEdge.y}`;
  }

  return (
    <path
      d={d}
      fill="none"
      strokeWidth={highlighted ? 2.5 : 1.5}
      className={cn(
        'transition-all duration-300',
        highlighted && 'stroke-primary !opacity-100',
        dimmed && 'opacity-15',
        !highlighted && !dimmed && EDGE_STROKE[status],
      )}
      markerEnd={highlighted ? 'url(#arrow-hl)' : 'url(#arrow)'}
    />
  );
}

// ---------------------------------------------------------------------------
// Tooltip counter formatting
// ---------------------------------------------------------------------------

const ISO_DATE_RE = /^\d{4}-\d{2}-\d{2}/;

function formatCounterValue(v: unknown, tz?: string): string {
  if (v == null) return '—';
  if (typeof v === 'number')
    return Number.isInteger(v) ? v.toLocaleString() : Number(v).toFixed(1);
  const s = String(v);
  if (ISO_DATE_RE.test(s)) return formatDateFriendly(s, tz);
  return s.length > 24 ? s.slice(0, 24) + '…' : s;
}

function shortenCounterKey(k: string): string {
  return k
    .replace(/^latest_snapshot_history_/, '')
    .replace(/^latest_/, '')
    .replace(/_count$/, '')
    .replace(/_/g, ' ');
}

// ---------------------------------------------------------------------------
// Node
// ---------------------------------------------------------------------------

interface NodeProps {
  name: string;
  displayName: string;
  state: PipelineStepState;
  visualStatus: PipelineVisualStatus;
  metric: string | null;
  isSelected: boolean;
  onSelect: (name: string) => void;
  timezone?: string;
}

function Node({ name, displayName, state, visualStatus, metric, isSelected, onSelect, timezone }: NodeProps) {
  const pos = nodeTopLeft(name);
  const Icon = STATUS_ICON[visualStatus] ?? Clock;
  const iconCls = STATUS_ICON_CLASS[visualStatus] ?? 'text-muted-foreground';

  return (
    <TooltipProvider delayDuration={200}>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            className={cn(
              'absolute flex flex-col items-start justify-between rounded-lg border px-2.5 py-1.5 text-left outline-none transition-all duration-300',
              'focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background',
              'cursor-pointer select-none',
              STATUS_CLASSES[visualStatus],
              isSelected && 'ring-2 ring-ring',
            )}
            style={{
              left: pos.x,
              top: pos.y,
              width: NODE_W,
              height: NODE_H,
            }}
            onClick={() => onSelect(name)}
            aria-label={
              visualStatus === 'stale'
                ? `${displayName}: stale, last updated more than 12 hours ago`
                : `${displayName}: ${state.status}`
            }
          >
            {visualStatus === 'stale' && (
              <span className="sr-only">Stale, last updated more than 12 hours ago</span>
            )}
            <span className="w-full truncate text-[11px] font-medium leading-tight text-foreground">
              {displayName}
            </span>
            {metric && (
              <span className="w-full truncate text-[9px] leading-tight text-muted-foreground">
                {metric}
              </span>
            )}
            <div className="flex w-full items-center justify-between">
              <Icon className={cn('size-3.5 shrink-0', iconCls)} aria-hidden />
              <span className="font-mono text-[10px] text-muted-foreground">
                {formatDuration(state.duration_s)}
              </span>
            </div>
          </button>
        </TooltipTrigger>
        <TooltipContent side="bottom" className="block max-w-sm">
          <p className="text-xs font-medium">{displayName}</p>
          <p className="text-xs text-muted-foreground">
            Status: {state.status}
            {state.duration_s != null && ` | ${formatDuration(state.duration_s)}`}
          </p>
          {state.error && (
            <p className="mt-1 text-xs text-destructive line-clamp-3">{state.error}</p>
          )}
          {state.counters && Object.keys(state.counters).length > 0 && (
            <div className="mt-1 space-y-px text-[10px]">
              {Object.entries(state.counters)
                .filter(([k, v]) => k !== 'status' && k !== 'error' && v != null && v !== '' && typeof v !== 'object')
                .slice(0, 8)
                .map(([k, v]) => (
                  <div key={k} className="flex justify-between gap-3">
                    <span className="truncate opacity-60">{shortenCounterKey(k)}</span>
                    <span className="shrink-0 font-medium">
                      {formatCounterValue(v, timezone)}
                    </span>
                  </div>
                ))}
            </div>
          )}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

// ---------------------------------------------------------------------------
// Node Detail Panel — comprehensive health diagnostics per node
// ---------------------------------------------------------------------------

interface DetailPanelProps {
  name: string;
  displayName: string;
  state: PipelineStepState;
  depsOk: boolean;
  onRetry: (step: string) => void;
  retrying: boolean;
  canRetry: boolean;
  onClose: () => void;
  healthDimensions?: HealthDims | null;
  providerMetrics?: ProviderMetrics | null;
  timezone?: string;
}

function getHealthDetail(name: string, dims: HealthDims | null | undefined, pm?: ProviderMetrics | null): Array<[string, string]> {
  if (!dims) return [];
  const pairs: Array<[string, string]> = [];
  switch (name) {
    case 'daily_bars': {
      pairs.push(['Daily fill', `${dims.coverage.daily_pct.toFixed(1)}%`]);
      if (dims.coverage.stale_daily > 0) pairs.push(['Stale symbols', String(dims.coverage.stale_daily)]);
      if (dims.coverage.expected_date) pairs.push(['Expected date', dims.coverage.expected_date]);
      const da = dims.data_accuracy;
      if (da) {
        pairs.push(['Data accuracy', `${da.match_rate?.toFixed(1) ?? '—'}%`]);
        pairs.push(['Bars checked', `${da.bars_checked ?? 0} across ${da.sample_size ?? 0} symbols`]);
        if (da.mismatch_count > 0) pairs.push(['Mismatches', String(da.mismatch_count)]);
        if (da.missing_in_db > 0) pairs.push(['Missing in DB', String(da.missing_in_db)]);
        if (da.age_days != null) pairs.push(['Last check', `${da.age_days}d ago`]);
        if (da.note) pairs.push(['Note', da.note]);
        if (da.mismatches && da.mismatches.length > 0) {
          const sample = da.mismatches.slice(0, 3).map(
            (m) => `${m.symbol} ${m.date}: ${m.type === 'missing_in_db' ? 'missing' : `${m.pct_diff}%`}`,
          ).join(' · ');
          pairs.push(['Samples', sample]);
        }
      }
      if (pm) {
        const fmpUsage = pm.providers?.fmp;
        if (fmpUsage) {
          pairs.push(['FMP usage', `${fmpUsage.calls.toLocaleString()}/${fmpUsage.budget.toLocaleString()} (${fmpUsage.pct.toFixed(1)}%)`]);
        }
        const otherProviders = Object.entries(pm.providers ?? {}).filter(([k]) => k !== 'fmp');
        for (const [pName, usage] of otherProviders) {
          if (usage.calls > 0) {
            pairs.push([pName, `${usage.calls.toLocaleString()}/${usage.budget.toLocaleString()}`]);
          }
        }
        if (pm.cache_hit_rate > 0) pairs.push(['Cache hit rate', `${pm.cache_hit_rate.toFixed(0)}%`]);
      }
      break;
    }
    case 'indicators': {
      pairs.push(['Total symbols', dims.stage_quality.total_symbols.toLocaleString()]);
      pairs.push(['Unknown rate', `${(dims.stage_quality.unknown_rate * 100).toFixed(1)}%`]);
      if (dims.stage_quality.invalid_count > 0) pairs.push(['Invalid', String(dims.stage_quality.invalid_count)]);
      if (dims.stage_quality.monotonicity_issues > 0) pairs.push(['Monotonicity', String(dims.stage_quality.monotonicity_issues)]);
      if (dims.stage_quality.stale_stage_count > 0) pairs.push(['Stale stages', String(dims.stage_quality.stale_stage_count)]);
      const sc = dims.stage_quality.stage_counts;
      if (sc && Object.keys(sc).length > 0) {
        const stages = Object.entries(sc).sort(([, a], [, b]) => b - a);
        pairs.push(['Stage distribution', stages.map(([s, c]) => `${s}: ${c}`).join(' · ')]);
      }
      const fund = dims.fundamentals;
      if (fund) {
        pairs.push(['Fundamentals fill', `${fund.fundamentals_fill_pct?.toFixed(0) ?? '—'}%`]);
        pairs.push(['Fund. coverage', `${fund.filled_count ?? 0}/${fund.tracked_total ?? 0}`]);
      }
      break;
    }
    case 'regime':
      if (dims.regime.regime_state) pairs.push(['Regime', dims.regime.regime_state]);
      if (dims.regime.composite_score != null) pairs.push(['Score', dims.regime.composite_score.toFixed(2)]);
      if (dims.regime.multiplier != null) pairs.push(['Sizing multiplier', `${dims.regime.multiplier}x`]);
      if (dims.regime.max_equity_pct != null) pairs.push(['Max equity', `${dims.regime.max_equity_pct}%`]);
      if (dims.regime.cash_floor_pct != null) pairs.push(['Cash floor', `${dims.regime.cash_floor_pct}%`]);
      pairs.push(['Age', `${dims.regime.age_hours.toFixed(0)}h`]);
      if (dims.regime.as_of_date) pairs.push(['As of', dims.regime.as_of_date]);
      break;
    case 'snapshot_history':
      pairs.push(['Snapshot fill', `${dims.audit.snapshot_fill_pct.toFixed(1)}%`]);
      pairs.push(['Daily fill', `${dims.audit.daily_fill_pct.toFixed(1)}%`]);
      pairs.push(['Tracked total', String(dims.audit.tracked_total ?? '—')]);
      if (dims.audit.history_depth_years != null) pairs.push(['History depth', `${dims.audit.history_depth_years}y`]);
      if (dims.audit.earliest_date) pairs.push(['Earliest snapshot', dims.audit.earliest_date]);
      if (dims.audit.missing_sample.length > 0) pairs.push(['Missing (sample)', dims.audit.missing_sample.slice(0, 5).join(', ')]);
      break;
    case 'audit':
      pairs.push(['Daily fill', `${dims.audit.daily_fill_pct.toFixed(1)}%`]);
      pairs.push(['Snapshot fill', `${dims.audit.snapshot_fill_pct.toFixed(1)}%`]);
      pairs.push(['Tracked total', String(dims.audit.tracked_total ?? '—')]);
      if (dims.audit.ohlcv_earliest_date) pairs.push(['OHLCV since', dims.audit.ohlcv_earliest_date]);
      if (dims.audit.ohlcv_symbol_count != null) pairs.push(['OHLCV symbols', String(dims.audit.ohlcv_symbol_count)]);
      if (dims.audit.earliest_date) pairs.push(['Snapshots since', dims.audit.earliest_date]);
      if (dims.audit.history_depth_years != null) pairs.push(['Depth', `${dims.audit.history_depth_years}y`]);
      if (dims.audit.missing_sample.length > 0) pairs.push(['Missing (sample)', dims.audit.missing_sample.slice(0, 5).join(', ')]);
      break;
    case 'health_check':
      pairs.push(['Success rate', `${(dims.jobs.success_rate * 100).toFixed(0)}%`]);
      pairs.push(['Window', `${dims.jobs.window_hours ?? 24}h`]);
      pairs.push(['Completed', String(dims.jobs.completed_count ?? 0)]);
      pairs.push(['Running', String(dims.jobs.running_count ?? 0)]);
      if (dims.jobs.error_count > 0) pairs.push(['Failed', String(dims.jobs.error_count)]);
      pairs.push(['Total', String(dims.jobs.total)]);
      if (dims.jobs.latest_failed) pairs.push(['Latest failure', dims.jobs.latest_failed.task_name]);
      break;
    case 'constituents':
    case 'tracked_cache':
      pairs.push(['Tracked', dims.coverage.tracked_count.toLocaleString()]);
      pairs.push(['Daily fill', `${dims.coverage.daily_pct.toFixed(1)}%`]);
      if (dims.coverage.stale_daily > 0) pairs.push(['Stale daily', String(dims.coverage.stale_daily)]);
      if (dims.coverage.expected_date) pairs.push(['Latest date', dims.coverage.expected_date]);
      if (dims.coverage.indices && Object.keys(dims.coverage.indices).length > 0) {
        Object.entries(dims.coverage.indices).forEach(([idx, count]) => {
          pairs.push([idx, String(count)]);
        });
      }
      if (dims.coverage.curated_etf_count != null && dims.coverage.curated_etf_count > 0) {
        pairs.push(['ETFs', String(dims.coverage.curated_etf_count)]);
      }
      break;
  }
  return pairs;
}

function DetailPanel({ name, displayName, state, depsOk, onRetry, retrying, canRetry, onClose, healthDimensions, providerMetrics, timezone }: DetailPanelProps) {
  const healthDetail = getHealthDetail(name, healthDimensions, providerMetrics);

  return (
    <div className="mt-4 rounded-lg border border-border bg-card p-4" role="region" aria-label={`${displayName} details`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-foreground">{displayName}</h3>
          <p className="text-xs text-muted-foreground">
            Step: <span className="font-mono">{name}</span> | Status: {state.status}
            {state.duration_s != null && ` | Duration: ${formatDuration(state.duration_s)}`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {state.status === 'error' && depsOk && canRetry && (
            <Button
              size="xs"
              variant="outline"
              className="gap-1 text-destructive"
              onClick={() => onRetry(name)}
              disabled={retrying}
            >
              {retrying ? <Loader2 className="size-3 animate-spin" aria-hidden /> : <RotateCcw className="size-3" aria-hidden />}
              Retry This Step
            </Button>
          )}
          <Button size="xs" variant="ghost" onClick={onClose}>
            Close
          </Button>
        </div>
      </div>

      {state.error && (
        <div className="mt-3 rounded-md bg-destructive/5 p-2">
          <p className="text-xs font-medium text-destructive">Error</p>
          <p className="mt-0.5 font-mono text-xs text-destructive/80 whitespace-pre-wrap break-all">{state.error}</p>
        </div>
      )}

      {state.counters && Object.keys(state.counters).length > 0 && (
        <div className="mt-3">
          <p className="mb-1 text-[10px] font-semibold tracking-wider text-muted-foreground uppercase">Counters</p>
          <div className="grid grid-cols-2 gap-x-4 gap-y-0.5 sm:grid-cols-3">
            {Object.entries(state.counters)
              .filter(([k, v]) => k !== 'status' && k !== 'error' && v != null && typeof v !== 'object')
              .map(([k, v]) => (
                <div key={k} className="text-xs text-muted-foreground">
                  {shortenCounterKey(k)}: <span className="font-medium text-foreground">{formatCounterValue(v, timezone)}</span>
                </div>
              ))}
          </div>
        </div>
      )}

      {healthDetail.length > 0 && (
        <div className="mt-3">
          <p className="mb-1 text-[10px] font-semibold tracking-wider text-muted-foreground uppercase">Health</p>
          <div className="grid grid-cols-2 gap-x-4 gap-y-0.5 sm:grid-cols-3">
            {healthDetail.map(([label, value]) => (
              <div key={label} className="text-xs text-muted-foreground">
                {label}: <span className="font-medium text-foreground">{value}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="mt-3 flex gap-4 text-[10px] text-muted-foreground">
        {state.started_at && <span>Started: {formatDateTimeFriendly(state.started_at, timezone)}</span>}
        {state.finished_at && <span>Finished: {formatDateTimeFriendly(state.finished_at, timezone)}</span>}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main DAG component
// ---------------------------------------------------------------------------

interface PipelineDAGProps {
  dag: PipelineDAGDefinition | undefined;
  run: PipelineRunState | null | undefined;
  loading?: boolean;
  loadError?: boolean;
  onRetryLoad?: () => void;
  onRetry: (runId: string, step: string) => void;
  retrying?: boolean;
  healthDimensions?: AdminHealthResponse['dimensions'] | null;
  providerMetrics?: ProviderMetrics | null;
  activeTasks?: ActiveTaskInfo[];
  ambientSteps?: Record<string, PipelineStepState>;
  timezone?: string;
}

const DEFAULT_STEP: PipelineStepState = {
  status: 'pending',
  started_at: null,
  finished_at: null,
  duration_s: null,
  error: null,
  counters: null,
};

export function PipelineDAG({ dag, run, loading, loadError, onRetryLoad, onRetry, retrying, healthDimensions, providerMetrics, activeTasks, ambientSteps, timezone }: PipelineDAGProps) {
  const [selected, setSelected] = React.useState<string | null>(null);

  const connectedEdgeKeys = React.useMemo(() => {
    if (!selected || !dag) return new Set<string>();
    const keys = new Set<string>();

    const upstream = new Map<string, string[]>();
    const downstream = new Map<string, string[]>();
    dag.edges.forEach((e) => {
      if (!upstream.has(e.target)) upstream.set(e.target, []);
      upstream.get(e.target)!.push(e.source);
      if (!downstream.has(e.source)) downstream.set(e.source, []);
      downstream.get(e.source)!.push(e.target);
    });

    const visited = new Set<string>([selected]);
    const queue = [selected];
    while (queue.length > 0) {
      const node = queue.shift()!;
      for (const src of upstream.get(node) ?? []) {
        keys.add(`${src}-${node}`);
        if (!visited.has(src)) {
          visited.add(src);
          queue.push(src);
        }
      }
    }

    const visitedDown = new Set<string>([selected]);
    const queueDown = [selected];
    while (queueDown.length > 0) {
      const node = queueDown.shift()!;
      for (const tgt of downstream.get(node) ?? []) {
        keys.add(`${node}-${tgt}`);
        if (!visitedDown.has(tgt)) {
          visitedDown.add(tgt);
          queueDown.push(tgt);
        }
      }
    }

    return keys;
  }, [selected, dag]);

  if (loading && !dag) {
    return (
      <div className="flex flex-col gap-3">
        <Skeleton className="h-[420px] w-full rounded-lg" />
      </div>
    );
  }

  if (loadError && !dag) {
    return (
      <div
        className="flex flex-col items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/5 p-4"
        role="alert"
      >
        <p className="text-sm text-foreground">Could not load the pipeline diagram.</p>
        <p className="text-xs text-muted-foreground">
          Check that you are signed in as an admin and the API is reachable.
        </p>
        {onRetryLoad ? (
          <Button type="button" size="xs" variant="outline" onClick={() => onRetryLoad()}>
            Retry
          </Button>
        ) : null}
      </div>
    );
  }

  if (!dag) {
    return (
      <div className="flex flex-col gap-3">
        <Skeleton className="h-[420px] w-full rounded-lg" />
      </div>
    );
  }

  const steps = run?.steps ?? {};
  const maxCol = dag.nodes.length > 0 ? Math.max(...dag.nodes.map((n) => NODE_POSITIONS[n.name]?.col ?? 0)) : 0;
  const maxRow = dag.nodes.length > 0 ? Math.max(...dag.nodes.map((n) => NODE_POSITIONS[n.name]?.row ?? 0)) : 0;
  const svgW = (maxCol + 1) * (NODE_W + COL_GAP) - COL_GAP + PAD * 2;
  const svgH = (maxRow + 1) * (NODE_H + ROW_GAP) - ROW_GAP + PAD * 2;

  const selectedStep = selected ? steps[selected] ?? DEFAULT_STEP : null;
  const selectedNode = selected ? dag.nodes.find((n) => n.name === selected) : null;
  const selectedDepsOk = selected
    ? (selectedNode?.deps ?? []).every((d) => (steps[d]?.status) === 'ok')
    : false;

  return (
    <div>
      <div className="overflow-x-auto pb-2">
        <div className="relative mx-auto" style={{ width: svgW, height: svgH, maxWidth: '100%' }}>
          <svg
            className="pointer-events-none absolute inset-0"
            width={svgW}
            height={svgH}
            aria-hidden
          >
            <defs>
              <marker
                id="arrow"
                viewBox="0 0 8 7"
                refX="8"
                refY="3.5"
                markerWidth="5"
                markerHeight="4"
                orient="auto"
              >
                <polygon
                  points="0 0.5, 8 3.5, 0 6.5"
                  className="fill-border"
                />
              </marker>
              <marker
                id="arrow-hl"
                viewBox="0 0 8 7"
                refX="8"
                refY="3.5"
                markerWidth="5"
                markerHeight="4"
                orient="auto"
              >
                <polygon
                  points="0 0.5, 8 3.5, 0 6.5"
                  className="fill-primary"
                />
              </marker>
            </defs>
            {dag.edges.map((e) => {
              const edgeKey = `${e.source}-${e.target}`;
              return (
                <Edge
                  key={edgeKey}
                  fromName={e.source}
                  toName={e.target}
                  status={resolveVisualStatus(
                    (steps[e.target]?.status) ?? 'pending',
                    e.target,
                    healthDimensions,
                    activeTasks,
                    ambientSteps,
                    steps[e.target],
                  )}
                  highlighted={connectedEdgeKeys.has(edgeKey)}
                  dimmed={selected != null && !connectedEdgeKeys.has(edgeKey)}
                />
              );
            })}
          </svg>

          {dag.nodes.map((node) => {
            const stepState = steps[node.name] ?? DEFAULT_STEP;
            return (
              <Node
                key={node.name}
                name={node.name}
                displayName={node.display_name}
                state={stepState}
                visualStatus={resolveVisualStatus(
                  stepState.status,
                  node.name,
                  healthDimensions,
                  activeTasks,
                  ambientSteps,
                  stepState,
                )}
                metric={getNodeMetric(node.name, healthDimensions)}
                isSelected={selected === node.name}
                onSelect={setSelected}
                timezone={timezone}
              />
            );
          })}
        </div>
      </div>

      {healthDimensions && !selected && (() => {
        const msgs: string[] = [];
        const cov = healthDimensions.coverage;
        if (cov.stale_daily > 0) msgs.push(`${cov.stale_daily} symbols missing latest bars`);
        const sq = healthDimensions.stage_quality;
        if (sq.unknown_rate > 0.01) msgs.push(`${(sq.unknown_rate * 100).toFixed(1)}% unknown stages`);
        if (sq.monotonicity_issues > 0) msgs.push(`${sq.monotonicity_issues} monotonicity issues`);
        const jobs = healthDimensions.jobs;
        if (jobs.error_count > 0) msgs.push(`${jobs.error_count} failed jobs (${jobs.window_hours ?? 24}h)`);
        if (msgs.length === 0) return (
          <p className="mt-2 text-[10px] text-emerald-500/80">
            All systems nominal. Agents monitor pipelines automatically.
          </p>
        );
        return (
          <p className="mt-2 text-[10px] text-amber-500/80">
            {msgs.join(' · ')}. Auto-ops will retry automatically.
          </p>
        );
      })()}

      {selected && selectedStep && selectedNode && (
        <DetailPanel
          name={selected}
          displayName={selectedNode.display_name}
          state={selectedStep}
          depsOk={selectedDepsOk}
          onRetry={(step) => run?.run_id && onRetry(run.run_id, step)}
          retrying={retrying ?? false}
          canRetry={!!run?.run_id}
          onClose={() => setSelected(null)}
          healthDimensions={healthDimensions}
          providerMetrics={providerMetrics}
          timezone={timezone}
        />
      )}
    </div>
  );
}

export default PipelineDAG;
