import React from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  PolarAngleAxis,
  PolarGrid,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip as RcTooltip,
  XAxis,
  YAxis,
} from 'recharts';

import { ChartGlassCard } from '@/components/ui/ChartGlassCard';

import type { StudyDetail } from '@/services/backtest';

/**
 * StudyResults — render the result of a single walk-forward study.
 *
 * Three panels:
 *   1. Header (status, progress, best params + score)
 *   2. Per-split test-score bar chart (stability check)
 *   3. Per-regime attribution radar chart (where the strategy wins)
 *
 * State handling follows the no-silent-fallback rule: explicit branches for
 * pending / running / failed / completed-but-empty. We never render "0" as a
 * stand-in for "still loading" — every label that could be a real value has
 * a sibling state above it.
 */

interface StudyResultsProps {
  study: StudyDetail;
}

function fmtScore(s: number | null | undefined): string {
  if (s === null || s === undefined || Number.isNaN(s)) return '—';
  return s.toFixed(3);
}

function fmtTimestamp(iso: string | null): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString(undefined, {
      year: 'numeric',
      month: 'short',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

const StatusPill: React.FC<{ status: StudyDetail['status'] }> = ({ status }) => {
  const tone =
    status === 'completed'
      ? 'bg-emerald-500/15 text-emerald-500 ring-emerald-500/30'
      : status === 'running'
        ? 'bg-amber-500/15 text-amber-500 ring-amber-500/30'
        : status === 'failed'
          ? 'bg-rose-500/15 text-rose-500 ring-rose-500/30'
          : 'bg-muted text-muted-foreground ring-muted-foreground/30';
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ${tone}`}
    >
      {status}
    </span>
  );
};

const StudyResults: React.FC<StudyResultsProps> = ({ study }) => {
  const splits = study.per_split_results ?? [];
  const regimeMap = study.regime_attribution ?? null;

  // Build radar payload only from canonical R1..R5 + unknown so the axis is
  // identical across studies and the user can compare regime profiles by eye.
  const radarData = regimeMap
    ? ['R1', 'R2', 'R3', 'R4', 'R5'].map((r) => ({
        regime: r,
        score: regimeMap[r]?.score ?? 0,
        trades: regimeMap[r]?.trades ?? 0,
      }))
    : [];

  return (
    <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
      {/* Header card */}
      <ChartGlassCard
        as="section"
        ariaLabel="Walk-forward study summary"
        padding="md"
        className="xl:col-span-2"
      >
        <header className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h2 className="truncate text-base font-semibold">{study.name}</h2>
              <StatusPill status={study.status} />
            </div>
            <p className="text-xs text-muted-foreground">
              {study.strategy_class} · {study.objective}
              {study.regime_filter ? ` · regime ${study.regime_filter}` : ''}
            </p>
          </div>
          <div className="text-right text-xs text-muted-foreground">
            <div>Created {fmtTimestamp(study.created_at)}</div>
            {study.completed_at ? (
              <div>Completed {fmtTimestamp(study.completed_at)}</div>
            ) : study.started_at ? (
              <div>Started {fmtTimestamp(study.started_at)}</div>
            ) : null}
          </div>
        </header>

        <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <div>
            <dt className="text-xs text-muted-foreground">Best score</dt>
            <dd className="mt-0.5 font-mono text-lg">
              {study.status === 'completed'
                ? fmtScore(study.best_score)
                : study.status === 'failed'
                  ? '—'
                  : 'pending'}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">Trials</dt>
            <dd className="mt-0.5 font-mono text-lg">
              {study.total_trials} / {study.n_trials}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">Splits</dt>
            <dd className="mt-0.5 font-mono text-lg">{study.n_splits}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">Symbols</dt>
            <dd className="mt-0.5 truncate font-mono text-sm">
              {study.symbols.join(', ')}
            </dd>
          </div>
        </dl>

        {study.status === 'failed' && study.error_message ? (
          <div className="mt-4 rounded-md border border-rose-500/30 bg-rose-500/5 p-3 text-sm text-rose-500">
            <strong className="font-semibold">Failure: </strong>
            {study.error_message}
          </div>
        ) : null}

        {study.best_params && study.status === 'completed' ? (
          <div className="mt-4">
            <div className="mb-1 text-xs uppercase tracking-wide text-muted-foreground">
              Best params
            </div>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {Object.entries(study.best_params).map(([k, v]) => (
                <div
                  key={k}
                  className="rounded-md border border-border bg-muted/40 px-2 py-1.5 font-mono text-xs"
                >
                  <span className="text-muted-foreground">{k}: </span>
                  <span>{String(v)}</span>
                </div>
              ))}
            </div>
          </div>
        ) : null}
      </ChartGlassCard>

      {/* Per-split bar chart */}
      <ChartGlassCard
        as="section"
        ariaLabel="Per-split test scores"
        padding="md"
      >
        <header className="mb-3">
          <h3 className="text-sm font-semibold">Per-split test scores</h3>
          <p className="text-xs text-muted-foreground">
            Stability of the best trial across rolling out-of-sample windows.
          </p>
        </header>
        {splits.length === 0 ? (
          <div className="grid h-56 place-content-center text-sm text-muted-foreground">
            {study.status === 'pending' || study.status === 'running'
              ? 'Awaiting first completed trial…'
              : 'No splits to display'}
          </div>
        ) : (
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={splits.map((s) => ({
                  label: `#${s.split_index + 1}`,
                  test: s.test_score,
                  trades: s.trade_count,
                }))}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="label" stroke="var(--muted-foreground)" />
                <YAxis stroke="var(--muted-foreground)" />
                <RcTooltip
                  contentStyle={{
                    background: 'var(--popover)',
                    border: '1px solid var(--border)',
                    borderRadius: 8,
                  }}
                />
                <Bar dataKey="test" radius={[4, 4, 0, 0]}>
                  {splits.map((s) => (
                    <Cell
                      key={s.split_index}
                      fill={
                        s.test_score >= 0
                          ? 'rgb(var(--status-success))'
                          : 'rgb(var(--status-warning))'
                      }
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </ChartGlassCard>

      {/* Regime attribution radar */}
      <ChartGlassCard
        as="section"
        ariaLabel="Regime attribution"
        padding="md"
      >
        <header className="mb-3">
          <h3 className="text-sm font-semibold">Regime attribution</h3>
          <p className="text-xs text-muted-foreground">
            Best-trial trades scored within each market regime (R1–R5).
          </p>
        </header>
        {radarData.length === 0 ? (
          <div className="grid h-56 place-content-center text-sm text-muted-foreground">
            {study.status === 'pending' || study.status === 'running'
              ? 'Awaiting first completed trial…'
              : 'No regime attribution available'}
          </div>
        ) : (
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <RadarChart data={radarData}>
                <PolarGrid stroke="var(--border)" />
                <PolarAngleAxis dataKey="regime" stroke="var(--muted-foreground)" />
                <RcTooltip
                  contentStyle={{
                    background: 'var(--popover)',
                    border: '1px solid var(--border)',
                    borderRadius: 8,
                  }}
                />
                <Radar
                  dataKey="score"
                  stroke="rgb(var(--accent))"
                  fill="rgb(var(--accent))"
                  fillOpacity={0.35}
                />
              </RadarChart>
            </ResponsiveContainer>
          </div>
        )}
      </ChartGlassCard>
    </div>
  );
};

export default StudyResults;
