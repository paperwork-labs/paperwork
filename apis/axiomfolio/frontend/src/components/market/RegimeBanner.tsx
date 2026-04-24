import React from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import { REGIME_HEX } from '../../constants/chart';
import { useRegime } from '../../hooks/useRegime';
import type { RegimeData } from '../../types/market';
import { cn } from '@/lib/utils';

export type { RegimeData };

const REGIME_LABELS: Record<string, string> = {
  R1: 'Bull',
  R2: 'Bull Extended',
  R3: 'Chop',
  R4: 'Bear Rally',
  R5: 'Bear',
};

const SCORE_LABELS: { key: keyof RegimeData; label: string }[] = [
  { key: 'score_vix', label: 'VIX' },
  { key: 'score_vix3m_vix', label: 'VIX3M/VIX' },
  { key: 'score_vvix_vix', label: 'VVIX/VIX' },
  { key: 'score_nh_nl', label: 'NH−NL' },
  { key: 'score_above_200d', label: '>200D' },
  { key: 'score_above_50d', label: '>50D' },
];

function ScoreChip({ label, value, max = 5 }: { label: string; value: number | null; max?: number }) {
  if (value == null) return null;
  const pct = Math.min(100, Math.max(0, (value / max) * 100));
  const color =
    value <= 1.5 ? 'bg-emerald-500' :
    value <= 2.5 ? 'bg-amber-400' :
    value <= 3.5 ? 'bg-orange-500' :
    'bg-red-500';
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center justify-between gap-2">
        <span className="text-[10px] text-muted-foreground">{label}</span>
        <span className="text-[10px] font-semibold tabular-nums">{value.toFixed(1)}</span>
      </div>
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-muted">
        <div className={cn('h-full rounded-full transition-all', color)} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

const RegimeBanner: React.FC = () => {
  const { data, isPending, isError, error } = useRegime();
  const [expanded, setExpanded] = React.useState(false);

  if (isPending) {
    return (
      <div className="mb-3 rounded-lg border border-border bg-card p-3">
        <p className="text-xs text-muted-foreground">Loading regime data...</p>
      </div>
    );
  }

  if (isError) {
    const detail =
      error instanceof Error
        ? error.message
        : typeof error === 'object' &&
            error !== null &&
            'message' in error &&
            typeof (error as { message: unknown }).message === 'string'
          ? (error as { message: string }).message
          : 'Request failed.';
    return (
      <div className="mb-3 rounded-lg border border-destructive/30 bg-destructive/10 p-3">
        <p className="text-xs text-destructive">Failed to load regime data.</p>
        <p className="mt-1 text-xs text-muted-foreground">{detail}</p>
      </div>
    );
  }

  if (data == null || typeof data !== 'object') {
    return (
      <div className="mb-3 rounded-lg border border-border bg-card p-3">
        <p className="text-xs text-muted-foreground">
          No regime data yet. Open System Status, expand Operator Actions, and run &quot;Compute
          Market Regime&quot; when the pipeline is ready.
        </p>
      </div>
    );
  }

  const row = data as unknown as RegimeData;
  const color = REGIME_HEX[row.regime_state] || '#718096';
  const label = REGIME_LABELS[row.regime_state] || row.regime_state;
  const hasScores = SCORE_LABELS.some(({ key }) => (row[key] as number | null) != null);

  return (
    <div
      className="mb-3 rounded-lg border-2 bg-card p-3"
      style={{ borderColor: color }}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <div
              className="size-3.5 shrink-0 rounded-sm"
              style={{ backgroundColor: color }}
              aria-hidden
            />
            <span className="text-base font-bold">{row.regime_state}</span>
            <span
              className={cn(
                'inline-flex h-5 shrink-0 items-center rounded-full border px-2 py-0 text-xs font-medium',
                'border-transparent'
              )}
              style={{
                backgroundColor: `${color}22`,
                color,
              }}
            >
              {label}
            </span>
          </div>
          <p className="text-sm text-muted-foreground">
            Composite:{' '}
            <span className="font-semibold text-foreground">
              {row.composite_score?.toFixed(1)}
            </span>
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-4">
          {row.vix_spot != null && (
            <div className="flex flex-col items-center gap-0">
              <span className="text-[10px] text-muted-foreground">VIX</span>
              <span className="text-xs font-semibold">{row.vix_spot.toFixed(1)}</span>
            </div>
          )}
          {row.vix3m_vix_ratio != null && (
            <div className="flex flex-col items-center gap-0">
              <span className="text-[10px] text-muted-foreground">VIX3M/VIX</span>
              <span className="text-xs font-semibold">{row.vix3m_vix_ratio.toFixed(2)}</span>
            </div>
          )}
          {row.nh_nl != null && (
            <div className="flex flex-col items-center gap-0">
              <span className="text-[10px] text-muted-foreground">NH−NL</span>
              <span className="text-xs font-semibold">{row.nh_nl}</span>
            </div>
          )}
          {row.pct_above_200d != null && (
            <div className="flex flex-col items-center gap-0">
              <span className="text-[10px] text-muted-foreground">&gt;200D</span>
              <span className="text-xs font-semibold">{row.pct_above_200d.toFixed(0)}%</span>
            </div>
          )}
          {row.pct_above_50d != null && (
            <div className="flex flex-col items-center gap-0">
              <span className="text-[10px] text-muted-foreground">&gt;50D</span>
              <span className="text-xs font-semibold">{row.pct_above_50d.toFixed(0)}%</span>
            </div>
          )}
          {row.regime_multiplier != null && (
            <div className="flex flex-col items-center gap-0">
              <span className="text-[10px] text-muted-foreground">Size Mult</span>
              <span className="text-xs font-semibold">{row.regime_multiplier.toFixed(2)}×</span>
            </div>
          )}
          {row.max_equity_exposure_pct != null && (
            <div className="flex flex-col items-center gap-0">
              <span className="text-[10px] text-muted-foreground">Max Eq</span>
              <span className="text-xs font-semibold">{row.max_equity_exposure_pct.toFixed(0)}%</span>
            </div>
          )}
          {hasScores && (
            <button
              type="button"
              onClick={() => setExpanded((v) => !v)}
              className="ml-1 flex items-center gap-0.5 text-[10px] text-muted-foreground transition-colors hover:text-foreground"
              aria-expanded={expanded}
              aria-label={expanded ? 'Collapse score details' : 'Expand score details'}
            >
              Details
              {expanded ? <ChevronUp className="size-3" /> : <ChevronDown className="size-3" />}
            </button>
          )}
        </div>
      </div>

      {expanded && hasScores && (
        <div className="mt-3 border-t border-border pt-3" role="region" aria-label="Regime component scores">
          <div className="flex flex-wrap items-start gap-5">
            <div className="flex flex-wrap gap-4">
              {SCORE_LABELS.map(({ key, label: scoreLabel }) => (
                <ScoreChip key={key} label={scoreLabel} value={row[key] as number | null} />
              ))}
            </div>
            {row.weights_used && row.weights_used.length > 0 && (
              <div className="flex flex-col gap-1">
                <span className="text-[10px] text-muted-foreground">Weights</span>
                <div className="flex flex-wrap gap-1">
                  {SCORE_LABELS.map(({ label: wLabel }, i) => (
                    <span key={i} className="rounded bg-muted px-1.5 py-0.5 text-[10px] font-mono text-muted-foreground">
                      {wLabel}: {row.weights_used?.[i]?.toFixed(1) ?? '—'}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default RegimeBanner;
