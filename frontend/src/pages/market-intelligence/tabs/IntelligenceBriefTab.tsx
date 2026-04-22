import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  AreaChart,
  Area,
  XAxis,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
} from 'recharts';
import {
  ArrowLeft,
  ArrowLeftRight,
  ChevronDown,
  ChevronUp,
  RefreshCw,
} from 'lucide-react';

import { SymbolLink } from '@/components/market/SymbolChartUI';
import StageBadge from '@/components/shared/StageBadge';
import StatCard from '@/components/shared/StatCard';
import { ACTION_COLORS, REGIME_HEX, STAGE_HEX } from '@/constants/chart';
import { marketDataApi } from '@/services/api';
import { formatDateFriendly, formatDateTimeFriendly } from '@/utils/format';
import { useUserPreferences } from '@/hooks/useUserPreferences';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { useActiveTab } from '@/components/layout/TabbedPageShell';
import { heatTextClass, semanticTextColorClass } from '@/lib/semantic-text-color';

/* ─── Constants ─── */

const DATA_MONO = 'font-mono tracking-tight';
const CARD_RING = 'shadow-xs ring-1 ring-foreground/10';
const PAGE_SIZE = 10;

const REGIME_LABELS: Record<string, string> = {
  R1: 'Bull',
  R2: 'Bull Extended',
  R3: 'Chop',
  R4: 'Bear Rally',
  R5: 'Bear',
};

type BriefType = 'daily' | 'weekly' | 'monthly';

const STAGE_ORDER = ['1A', '1B', '2A', '2B', '2B(RS-)', '2C', '3A', '3B', '4A', '4B', '4C'];

/* ─── Helpers ─── */

const fmtPct = (v: unknown): string => {
  if (typeof v !== 'number' || !Number.isFinite(v)) return '—';
  return `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`;
};

function regimeBadgeVariant(state: string): React.ComponentProps<typeof Badge>['variant'] {
  if (state === 'R1') return 'default';
  if (state === 'R5') return 'destructive';
  return 'secondary';
}

function actionBadgeClass(action: string): string {
  const color = ACTION_COLORS[action];
  if (color === 'green')
    return 'border-transparent bg-[rgb(var(--status-success)/0.12)] text-[rgb(var(--status-success)/1)]';
  if (color === 'red') return 'border-transparent bg-destructive/10 text-destructive';
  if (color === 'orange')
    return 'border-transparent bg-amber-500/20 text-amber-700 dark:text-amber-300';
  return 'bg-secondary text-secondary-foreground';
}

const formatLabel = (key: string): string =>
  key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());

function stageHex(stage: string): string {
  return STAGE_HEX[stage]?.[0] || '#64748B';
}

function breadthColor(pct: number): string {
  if (pct >= 50) return REGIME_HEX.R1;
  if (pct >= 30) return REGIME_HEX.R3;
  return REGIME_HEX.R5;
}

function unwrapBrief(resp: any): any {
  return resp?.data?.brief ?? resp?.brief ?? null;
}

function unwrapBriefMeta(resp: any): { generated_at?: string } {
  const d = resp?.data ?? resp ?? {};
  return { generated_at: d.generated_at };
}

function unwrapList(resp: any): { briefs: any[]; total: number | null } {
  const inner = resp?.data ?? resp ?? {};
  return {
    briefs: inner.briefs ?? [],
    total: inner.total ?? null,
  };
}

/* ─── Shared sub-components ─── */

const SectionFooterLink: React.FC<{ to: string; label: string }> = ({ to, label }) => (
  <Link
    to={to}
    className="mt-3 inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
  >
    {label} <span aria-hidden>→</span>
  </Link>
);

const BreadthBar: React.FC<{ label: string; pct: number }> = ({ label, pct }) => {
  const val = typeof pct === 'number' && Number.isFinite(pct) ? pct : 0;
  const color = breadthColor(val);
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-xs">
        <span className="text-muted-foreground">{label}</span>
        <span className={cn(DATA_MONO, 'font-semibold')}>{val.toFixed(1)}%</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${Math.min(val, 100)}%`, backgroundColor: color }}
        />
      </div>
    </div>
  );
};

const StageDistributionBar: React.FC<{ distribution: Record<string, number> }> = ({
  distribution,
}) => {
  const entries = Object.entries(distribution)
    .filter(([, count]) => typeof count === 'number' && count > 0)
    .sort((a, b) => STAGE_ORDER.indexOf(a[0]) - STAGE_ORDER.indexOf(b[0]));
  const total = entries.reduce((sum, [, count]) => sum + (count as number), 0);
  if (total === 0) return <p className="text-xs text-muted-foreground">No data</p>;

  return (
    <div>
      <div className="flex h-7 w-full overflow-hidden rounded-md">
        {entries.map(([stage, count]) => {
          const pct = ((count as number) / total) * 100;
          return (
            <Link
              key={stage}
              to={`/market/tracked?filter_stage=${encodeURIComponent(stage)}`}
              className="flex items-center justify-center text-[10px] font-bold text-white transition-opacity hover:opacity-80"
              style={{
                width: `${pct}%`,
                backgroundColor: stageHex(stage),
                minWidth: pct > 0 ? 2 : 0,
              }}
              title={`${stage}: ${count} (${pct.toFixed(0)}%)`}
            >
              {pct > 6 ? stage : ''}
            </Link>
          );
        })}
      </div>
      <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1">
        {entries.map(([stage, count]) => (
          <Link
            key={stage}
            to={`/market/tracked?filter_stage=${encodeURIComponent(stage)}`}
            className="flex items-center gap-1 text-xs hover:underline"
          >
            <span
              className="inline-block size-2.5 rounded-sm"
              style={{ backgroundColor: stageHex(stage) }}
            />
            <span className="font-medium">{stage}</span>
            <span className="text-muted-foreground">{count as number}</span>
          </Link>
        ))}
      </div>
    </div>
  );
};

/* ─── Recharts: regime mini-chart ─── */

const RegimeChartTooltip = ({ active, payload }: any) => {
  if (!active || !payload?.[0]) return null;
  const d = payload[0].payload;
  const color = REGIME_HEX[d.state] || '#64748B';
  return (
    <div className="rounded-md border border-border bg-popover px-2 py-1 text-xs shadow-sm">
      <p className="font-medium">{d.date}</p>
      <p style={{ color }}>
        {d.state} — {REGIME_LABELS[d.state] || d.state} ({d.score?.toFixed(2) ?? '—'})
      </p>
    </div>
  );
};

const RegimeDot = (props: any) => {
  const { cx, cy, payload } = props;
  if (cx == null || cy == null) return null;
  return (
    <circle
      cx={cx}
      cy={cy}
      r={3}
      fill={REGIME_HEX[payload.state] || '#64748B'}
      stroke="none"
    />
  );
};

const RegimeTrendChart: React.FC<{
  data: any[];
  gradientId?: string;
  height?: number;
}> = ({ data, gradientId = 'regime-grad', height = 80 }) => {
  const chartData = useMemo(
    () =>
      data.map((r) => ({
        date: r.date?.slice(5) ?? '',
        score: r.score ?? 0,
        state: r.state,
      })),
    [data],
  );

  const latestColor = REGIME_HEX[data[data.length - 1]?.state] || '#64748B';

  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={chartData} margin={{ top: 4, right: 4, bottom: 0, left: 4 }}>
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={latestColor} stopOpacity={0.35} />
            <stop offset="100%" stopColor={latestColor} stopOpacity={0.05} />
          </linearGradient>
        </defs>
        <XAxis dataKey="date" tick={{ fontSize: 10 }} tickLine={false} axisLine={false} />
        <RechartsTooltip content={<RegimeChartTooltip />} />
        <Area
          type="monotone"
          dataKey="score"
          stroke={latestColor}
          strokeWidth={2}
          fill={`url(#${gradientId})`}
          dot={RegimeDot}
          activeDot={{ r: 4, strokeWidth: 0 }}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
};

/* ─── Brief diff summary (comparison mode) ─── */

const BriefDiffSummary: React.FC<{ historical: any; latest: any }> = ({
  historical,
  latest,
}) => {
  const regimeChanged = historical.regime?.state !== latest.regime?.state;

  const histTransSyms = new Set<string>(
    (historical.stage_transitions || []).map((t: any) => t.symbol),
  );
  const latestTransSyms = new Set<string>(
    (latest.stage_transitions || []).map((t: any) => t.symbol),
  );
  const newTransitions = (latest.stage_transitions || []).filter(
    (t: any) => !histTransSyms.has(t.symbol),
  );
  const resolvedTransitions = (historical.stage_transitions || []).filter(
    (t: any) => !latestTransSyms.has(t.symbol),
  );

  const histExitSyms = new Set<string>(
    (historical.exit_alerts || []).map((a: any) => a.symbol),
  );
  const latestExitSyms = new Set<string>(
    (latest.exit_alerts || []).map((a: any) => a.symbol),
  );
  const newExits = (latest.exit_alerts || []).filter(
    (a: any) => !histExitSyms.has(a.symbol),
  );
  const resolvedExits = (historical.exit_alerts || []).filter(
    (a: any) => !latestExitSyms.has(a.symbol),
  );

  const nothingChanged =
    !regimeChanged &&
    newTransitions.length === 0 &&
    resolvedTransitions.length === 0 &&
    newExits.length === 0 &&
    resolvedExits.length === 0;

  if (nothingChanged) {
    return (
      <Card className={cn('gap-0 py-4', CARD_RING)}>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            No significant changes between these briefs.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={cn('gap-0 py-4', CARD_RING)}>
      <CardContent className="flex flex-col gap-3">
        <p className="text-sm font-semibold">Changes Summary</p>

        {regimeChanged && (
          <div className="flex items-center gap-2 text-xs">
            <span className="text-muted-foreground">Regime:</span>
            <Badge
              variant={regimeBadgeVariant(historical.regime?.state)}
              className="font-normal"
            >
              {historical.regime?.state}
            </Badge>
            <span className="text-muted-foreground">→</span>
            <Badge variant={regimeBadgeVariant(latest.regime?.state)} className="font-normal">
              {latest.regime?.state}
            </Badge>
          </div>
        )}

        {newTransitions.length > 0 && (
          <div>
            <p className="mb-1 text-xs font-medium">
              New Transitions{' '}
              <Badge variant="secondary" className="ml-1 text-[10px] font-normal">
                NEW
              </Badge>
            </p>
            <div className="flex flex-wrap gap-2">
              {newTransitions.map((t: any) => (
                <div key={t.symbol} className="flex items-center gap-1 text-xs">
                  <SymbolLink symbol={t.symbol} />
                  <StageBadge stage={t.from_stage} />
                  <span className="text-muted-foreground">→</span>
                  <StageBadge stage={t.to_stage} />
                </div>
              ))}
            </div>
          </div>
        )}

        {resolvedTransitions.length > 0 && (
          <div>
            <p className="mb-1 text-xs font-medium">
              Resolved{' '}
              <Badge variant="secondary" className="ml-1 text-[10px] font-normal">
                RESOLVED
              </Badge>
            </p>
            <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
              {resolvedTransitions.map((t: any) => (
                <SymbolLink key={t.symbol} symbol={t.symbol} />
              ))}
            </div>
          </div>
        )}

        {newExits.length > 0 && (
          <div>
            <p className="mb-1 text-xs font-medium text-destructive">
              New Exit Alerts{' '}
              <Badge variant="secondary" className="ml-1 text-[10px] font-normal">
                NEW
              </Badge>
            </p>
            <div className="flex flex-wrap gap-2 text-xs">
              {newExits.map((a: any) => (
                <SymbolLink key={a.symbol} symbol={a.symbol} />
              ))}
            </div>
          </div>
        )}

        {resolvedExits.length > 0 && (
          <div>
            <p className="mb-1 text-xs font-medium">
              Resolved Alerts{' '}
              <Badge variant="secondary" className="ml-1 text-[10px] font-normal">
                RESOLVED
              </Badge>
            </p>
            <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
              {resolvedExits.map((a: any) => (
                <SymbolLink key={a.symbol} symbol={a.symbol} />
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

/* ─── Daily Digest view ─── */

const DailyDigestView: React.FC<{ brief: any }> = ({ brief }) => {
  const regime = brief.regime || {};
  const regimeColor = REGIME_HEX[regime.state] || '#64748B';
  const [showBreakdown, setShowBreakdown] = useState(false);

  const inputScores =
    regime.input_scores || regime.inputs || regime.score_breakdown || null;

  const transitionSymbols = useMemo(
    () => (brief.stage_transitions || []).map((t: any) => t.symbol).join(','),
    [brief.stage_transitions],
  );

  return (
    <div className="flex flex-col gap-4">
      {/* Regime Hero */}
      <Card
        className={cn('relative gap-0 overflow-hidden border-2 py-4', CARD_RING)}
        style={{ borderColor: regimeColor }}
      >
        <div
          className="pointer-events-none absolute inset-0 opacity-[0.06]"
          style={{ backgroundColor: regimeColor }}
          aria-hidden
        />
        <CardContent className="relative flex flex-col gap-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-3">
              <div
                className="rounded-md px-3 py-1 text-lg font-bold text-white"
                style={{ backgroundColor: regimeColor }}
              >
                {regime.state}
              </div>
              <div>
                <p className="font-semibold">
                  {REGIME_LABELS[regime.state] || regime.state}
                </p>
                <p className={cn('text-xs text-muted-foreground', DATA_MONO)}>
                  Score: {regime.score?.toFixed(2)}
                </p>
              </div>
              {regime.changed && (
                <Badge
                  variant="secondary"
                  className="border-transparent bg-amber-500/20 text-amber-800 dark:text-amber-200"
                >
                  Changed from {regime.previous_state}
                </Badge>
              )}
            </div>
            <div className="grid w-full max-w-md grid-cols-3 gap-3 sm:w-auto">
              <StatCard label="VIX" value={regime.vix_spot?.toFixed(1) ?? '—'} />
              <StatCard label="Sizing" value={`${regime.multiplier?.toFixed(2) ?? '—'}x`} />
              <StatCard label="Max Equity" value={`${regime.max_equity_pct ?? '—'}%`} />
            </div>
          </div>

          {inputScores && typeof inputScores === 'object' && (
            <div>
              <button
                type="button"
                onClick={() => setShowBreakdown(!showBreakdown)}
                className="flex items-center gap-1 text-xs text-muted-foreground transition-colors hover:text-foreground"
                aria-expanded={showBreakdown}
              >
                Score breakdown
                {showBreakdown ? (
                  <ChevronUp className="size-3" aria-hidden />
                ) : (
                  <ChevronDown className="size-3" aria-hidden />
                )}
              </button>
              {showBreakdown && (
                <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 md:grid-cols-3">
                  {Object.entries(inputScores as Record<string, unknown>).map(
                    ([key, val]) => (
                      <div
                        key={key}
                        className="flex items-center justify-between text-xs"
                      >
                        <span className="text-muted-foreground">
                          {formatLabel(key)}
                        </span>
                        <span className={cn(DATA_MONO, 'font-semibold')}>
                          {typeof val === 'number'
                            ? val.toFixed(2)
                            : String(val ?? '—')}
                        </span>
                      </div>
                    ),
                  )}
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Market Breadth */}
      <Card className={cn('gap-0 py-4', CARD_RING)}>
        <CardContent className="flex flex-col gap-3">
          <p className="text-sm font-semibold">Market Breadth</p>
          <BreadthBar label="Above 50 DMA" pct={brief.breadth?.above_50d_pct ?? 0} />
          <BreadthBar label="Above 200 DMA" pct={brief.breadth?.above_200d_pct ?? 0} />
        </CardContent>
      </Card>

      {/* Stage Distribution */}
      {brief.stage_distribution && (
        <Card className={cn('gap-0 py-4', CARD_RING)}>
          <CardContent>
            <p className="mb-2 text-sm font-semibold">Stage Distribution</p>
            <StageDistributionBar distribution={brief.stage_distribution} />
          </CardContent>
        </Card>
      )}

      {/* Stage Transitions */}
      {brief.stage_transitions?.length > 0 && (
        <Card className={cn('gap-0 py-4', CARD_RING)}>
          <CardContent>
            <p className="mb-2 text-sm font-semibold">Stage Transitions</p>
            <div className="flex flex-col gap-1">
              {brief.stage_transitions.map((t: any, i: number) => (
                <div
                  key={`${t.symbol}-${i}`}
                  className="flex items-center justify-between text-xs"
                >
                  <SymbolLink symbol={t.symbol} />
                  <div className="flex items-center gap-1">
                    <StageBadge stage={t.from_stage} />
                    <span className="text-muted-foreground">→</span>
                    <StageBadge stage={t.to_stage} />
                    {t.days_in_stage != null && (
                      <span className="text-muted-foreground">{t.days_in_stage}d</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
            {transitionSymbols && (
              <SectionFooterLink
                to={`/market/tracked?symbols=${encodeURIComponent(transitionSymbols)}`}
                label="View all in Market Table"
              />
            )}
          </CardContent>
        </Card>
      )}

      {/* Scan Changes */}
      {brief.scan_changes?.length > 0 && (
        <Card className={cn('gap-0 py-4', CARD_RING)}>
          <CardContent>
            <p className="mb-2 text-sm font-semibold">Scan Changes</p>
            <div className="flex flex-col gap-1">
              {brief.scan_changes.map((sc: any, i: number) => (
                <div
                  key={`scan-${sc.symbol}-${i}`}
                  className="flex items-center justify-between text-xs"
                >
                  <SymbolLink symbol={sc.symbol} />
                  <div className="flex items-center gap-1">
                    {sc.scan_tier && (
                      <Badge variant="secondary" className="text-[10px] font-normal">
                        {sc.scan_tier}
                      </Badge>
                    )}
                    {sc.action_label && (
                      <Badge
                        variant="secondary"
                        className={cn(
                          'text-[10px] font-normal',
                          actionBadgeClass(sc.action_label),
                        )}
                      >
                        {sc.action_label}
                      </Badge>
                    )}
                  </div>
                </div>
              ))}
            </div>
            <SectionFooterLink
              to="/market/tracked?mode=scan&action_labels=BUY"
              label="View Buy Candidates"
            />
          </CardContent>
        </Card>
      )}

      {/* Exit Alerts */}
      {brief.exit_alerts?.length > 0 && (
        <Card className={cn('gap-0 py-4', CARD_RING)}>
          <CardContent>
            <p className="mb-2 text-sm font-semibold text-destructive">Exit Alerts</p>
            <div className="flex flex-col gap-1">
              {brief.exit_alerts.map((a: any, i: number) => (
                <div
                  key={`exit-${a.symbol}-${i}`}
                  className="flex items-center justify-between text-xs"
                >
                  <div className="flex items-center gap-2">
                    <SymbolLink symbol={a.symbol} />
                    <StageBadge stage={a.stage} />
                  </div>
                  {a.pnl_pct != null && (
                    <span
                      className={cn(
                        DATA_MONO,
                        semanticTextColorClass(
                          a.pnl_pct >= 0 ? 'green.500' : 'red.500',
                        ),
                      )}
                    >
                      {a.pnl_pct >= 0 ? '+' : ''}
                      {a.pnl_pct}%
                    </span>
                  )}
                </div>
              ))}
            </div>
            <SectionFooterLink
              to="/market/tracked?action_labels=REDUCE,AVOID"
              label="View Reduce/Exit"
            />
          </CardContent>
        </Card>
      )}
    </div>
  );
};

/* ─── Weekly Brief view ─── */

const WeeklyBriefView: React.FC<{ brief: any }> = ({ brief }) => (
  <div className="flex flex-col gap-4">
    {/* Regime Trend — mini AreaChart */}
    {brief.regime_trend?.length > 0 && (
      <Card className={cn('gap-0 py-4', CARD_RING)}>
        <CardContent>
          <p className="mb-2 text-sm font-semibold">Regime Trend (7d)</p>
          <RegimeTrendChart
            data={brief.regime_trend}
            gradientId="weekly-regime-grad"
            height={80}
          />
        </CardContent>
      </Card>
    )}

    {/* Pick Lists */}
    {brief.top_picks && (
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <PickList
          title="Buy List"
          items={brief.top_picks.buy}
          tone="green"
          footerTo="/market/tracked?mode=scan&action_labels=BUY"
          footerLabel="View all Buy Candidates in Market Table"
        />
        <PickList
          title="Watch List"
          items={brief.top_picks.watch}
          tone="blue"
          footerTo="/market/tracked?mode=scan&action_labels=WATCH"
          footerLabel="View Watch List in Market Table"
        />
        <PickList
          title="Short List"
          items={brief.top_picks.short}
          tone="red"
          footerTo="/market/tracked?mode=scan&action_labels=SHORT"
          footerLabel="View Short Candidates"
        />
      </div>
    )}

    {/* Sector Analysis with RS bars */}
    {brief.sector_analysis?.length > 0 && (
      <Card className={cn('gap-0 py-4', CARD_RING)}>
        <CardContent>
          <p className="mb-2 text-sm font-semibold">Sector Analysis</p>
          <div className="flex flex-col gap-1.5">
            {brief.sector_analysis.map((s: any) => {
              const rs = typeof s.avg_rs === 'number' ? s.avg_rs : 0;
              const barWidth = Math.min(Math.abs(rs) * 10, 100);
              const barColor = rs >= 0 ? REGIME_HEX.R1 : REGIME_HEX.R5;
              return (
                <Link
                  key={s.sector}
                  to={`/market/tracked?sectors=${encodeURIComponent(s.sector)}`}
                  className="flex items-center gap-2 rounded-md px-2 py-1 text-xs transition-colors hover:bg-muted/80"
                >
                  <span className="w-24 shrink-0 truncate font-medium">
                    {s.sector}
                  </span>
                  <span className="shrink-0 text-muted-foreground">({s.count})</span>
                  <div className="flex-1">
                    <div className="h-2 overflow-hidden rounded-full bg-muted">
                      <div
                        className="h-full rounded-full transition-all"
                        style={{ width: `${barWidth}%`, backgroundColor: barColor }}
                      />
                    </div>
                  </div>
                  <span
                    className={cn(
                      DATA_MONO,
                      'w-14 shrink-0 text-right',
                      heatTextClass(rs),
                    )}
                  >
                    {fmtPct(rs)}
                  </span>
                  <span
                    className={cn(
                      DATA_MONO,
                      'w-16 shrink-0 text-right',
                      semanticTextColorClass('green.500'),
                    )}
                  >
                    S2: {s.stage2_pct}%
                  </span>
                </Link>
              );
            })}
          </div>
        </CardContent>
      </Card>
    )}

    {/* Stage Distribution */}
    {brief.stage_distribution && (
      <Card className={cn('gap-0 py-4', CARD_RING)}>
        <CardContent>
          <p className="mb-2 text-sm font-semibold">Stage Distribution</p>
          <StageDistributionBar distribution={brief.stage_distribution} />
        </CardContent>
      </Card>
    )}
  </div>
);

/* ─── Monthly Review view ─── */

const MonthlyReviewView: React.FC<{ brief: any }> = ({ brief }) => (
  <div className="flex flex-col gap-4">
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
      <StatCard
        label="Period"
        value={`${brief.period_start ?? '—'} to ${brief.as_of ?? '—'}`}
      />
      <StatCard label="Regime Transitions" value={String(brief.regime_transitions ?? 0)} />
      <StatCard label="Avg 20D Perf" value={fmtPct(brief.performance_summary?.avg_20d)} />
      <StatCard
        label="Median 20D Perf"
        value={fmtPct(brief.performance_summary?.median_20d)}
      />
    </div>

    {/* Regime History — mini AreaChart replaces thin divs */}
    {brief.regime_history?.length > 0 && (
      <Card className={cn('gap-0 py-4', CARD_RING)}>
        <CardContent>
          <p className="mb-2 text-sm font-semibold">Regime History (30d)</p>
          <RegimeTrendChart
            data={brief.regime_history}
            gradientId="monthly-regime-grad"
            height={100}
          />
        </CardContent>
      </Card>
    )}

    {/* Best / Worst performers with SymbolLink */}
    {brief.performance_summary && (
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Card className={cn('gap-0 py-4', CARD_RING)}>
          <CardContent>
            <p className="mb-2 text-sm font-semibold text-[rgb(var(--status-success)/1)]">
              Top 5 Performers (20d)
            </p>
            <div className="flex flex-col gap-1">
              {(brief.performance_summary.best || []).map((s: any) => (
                <div
                  key={s.symbol}
                  className="flex items-center justify-between text-xs"
                >
                  <SymbolLink symbol={s.symbol} />
                  <span className={cn(DATA_MONO, semanticTextColorClass('green.500'))}>
                    {fmtPct(s.perf_20d)}
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
        <Card className={cn('gap-0 py-4', CARD_RING)}>
          <CardContent>
            <p className="mb-2 text-sm font-semibold text-destructive">
              Bottom 5 Performers (20d)
            </p>
            <div className="flex flex-col gap-1">
              {(brief.performance_summary.worst || []).map((s: any) => (
                <div
                  key={s.symbol}
                  className="flex items-center justify-between text-xs"
                >
                  <SymbolLink symbol={s.symbol} />
                  <span className={cn(DATA_MONO, semanticTextColorClass('red.500'))}>
                    {fmtPct(s.perf_20d)}
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    )}
  </div>
);

/* ─── PickList ─── */

const PickList: React.FC<{
  title: string;
  items: any[];
  tone: 'green' | 'blue' | 'red';
  footerTo?: string;
  footerLabel?: string;
}> = ({ title, items, tone, footerTo, footerLabel }) => {
  const badgeClass =
    tone === 'green'
      ? 'border-transparent bg-[rgb(var(--status-success)/0.12)] text-[rgb(var(--status-success)/1)]'
      : tone === 'red'
        ? 'border-transparent bg-destructive/10 text-destructive'
        : 'bg-secondary text-secondary-foreground';
  return (
    <Card className={cn('gap-0 py-4', CARD_RING)}>
      <CardContent>
        <div className="mb-2 flex items-center justify-between">
          <p className="text-sm font-semibold">{title}</p>
          <Badge variant="secondary" className={cn('font-normal', badgeClass)}>
            {items?.length ?? 0}
          </Badge>
        </div>
        {!items?.length ? (
          <p className="text-xs text-muted-foreground">None</p>
        ) : (
          <div className="flex flex-col gap-1">
            {items.map((p: any, i: number) => (
              <div
                key={`${p.symbol}-${i}`}
                className="flex items-center justify-between text-xs"
              >
                <SymbolLink symbol={p.symbol} />
                <div className="flex items-center gap-1">
                  <StageBadge stage={p.stage || '—'} />
                  {p.scan_tier && (
                    <span className="text-muted-foreground">{p.scan_tier}</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
        {footerTo && footerLabel && (
          <SectionFooterLink to={footerTo} label={footerLabel} />
        )}
      </CardContent>
    </Card>
  );
};

/* ─── Main component ─── */

const IntelligenceBriefTab: React.FC = () => {
  const { timezone } = useUserPreferences();
  const queryClient = useQueryClient();

  const activeType = useActiveTab<BriefType>();
  const [selectedBriefId, setSelectedBriefId] = useState<number | null>(null);
  const [compareMode, setCompareMode] = useState(false);
  const [isPolling, setIsPolling] = useState(false);
  const [generateError, setGenerateError] = useState<string | null>(null);
  const [briefListOffset, setBriefListOffset] = useState(0);
  const [accumulatedBriefs, setAccumulatedBriefs] = useState<any[]>([]);

  useEffect(() => {
    setSelectedBriefId(null);
    setCompareMode(false);
    setGenerateError(null);
    setBriefListOffset(0);
    setAccumulatedBriefs([]);
  }, [activeType]);

  useEffect(() => {
    if (!isPolling) return;
    const timer = setTimeout(() => setIsPolling(false), 30_000);
    return () => clearTimeout(timer);
  }, [isPolling]);

  /* ─ Queries ─ */

  const {
    data: latestBriefData,
    isPending: latestPending,
    isError: latestError,
    error: latestErrObj,
  } = useQuery({
    queryKey: ['intelligence-brief', activeType],
    queryFn: async () => {
      const resp = await marketDataApi.getLatestBrief(activeType);
      return (resp as any)?.data ?? resp ?? null;
    },
    staleTime: 2 * 60_000,
    refetchInterval: isPolling ? 3_000 : false,
  });

  const { data: selectedBriefData, isPending: selectedPending, isError: selectedError, error: selectedErrObj } = useQuery({
    queryKey: ['intelligence-brief-by-id', selectedBriefId],
    queryFn: async () => {
      const resp = await marketDataApi.getBrief(selectedBriefId!);
      return (resp as any)?.data ?? resp ?? null;
    },
    enabled: selectedBriefId != null,
    staleTime: 5 * 60_000,
  });

  const { data: briefListRaw } = useQuery({
    queryKey: ['intelligence-list', activeType, briefListOffset],
    queryFn: () => marketDataApi.listBriefs(activeType, PAGE_SIZE, briefListOffset),
    staleTime: 5 * 60_000,
    refetchInterval: isPolling ? 5_000 : false,
  });

  useEffect(() => {
    const { briefs } = unwrapList(briefListRaw);
    if (briefs.length === 0) return;
    setAccumulatedBriefs((prev) => {
      if (briefListOffset === 0) return briefs;
      const existingIds = new Set(prev.map((b: any) => b.id));
      const newBriefs = briefs.filter((b: any) => !existingIds.has(b.id));
      return [...prev, ...newBriefs];
    });
  }, [briefListRaw, briefListOffset]);

  const { total: briefListTotal } = useMemo(
    () => unwrapList(briefListRaw),
    [briefListRaw],
  );
  const briefList = accumulatedBriefs;

  const generateMutation = useMutation({
    mutationFn: () => marketDataApi.triggerBrief(activeType),
    onSuccess: () => {
      setIsPolling(true);
      setSelectedBriefId(null);
      setCompareMode(false);
      queryClient.invalidateQueries({
        queryKey: ['intelligence-brief', activeType],
      });
      queryClient.invalidateQueries({
        queryKey: ['intelligence-list', activeType],
      });
    },
    onError: (err: any) => {
      const status = err?.response?.status;
      if (status === 403) {
        setGenerateError('Admin access required to generate briefs.');
      } else {
        setGenerateError(err?.message || 'Failed to trigger brief generation.');
      }
    },
  });

  useEffect(() => {
    if (isPolling && (latestBriefData as any)?.brief) {
      setIsPolling(false);
    }
  }, [isPolling, latestBriefData]);

  /* ─ Derived state ─ */

  const isViewingHistorical = selectedBriefId != null;
  const latestBrief = (latestBriefData as any)?.brief ?? null;
  const selectedBrief = useMemo(() => unwrapBrief(selectedBriefData), [selectedBriefData]);

  const activeBrief = isViewingHistorical ? selectedBrief : latestBrief;
  const activeMeta = isViewingHistorical
    ? unwrapBriefMeta(selectedBriefData)
    : unwrapBriefMeta(latestBriefData);

  const isPending = isViewingHistorical ? selectedPending : latestPending;
  const activeError = isViewingHistorical ? selectedError : latestError;
  const activeErrObj = isViewingHistorical ? selectedErrObj : latestErrObj;

  const hasMore =
    briefListTotal != null
      ? briefList.length < briefListTotal
      : briefList.length > 0 && briefList.length % PAGE_SIZE === 0;

  /* ─ View dispatch ─ */

  const renderBriefView = useCallback(
    (brief: any) => {
      if (activeType === 'daily') return <DailyDigestView brief={brief} />;
      if (activeType === 'weekly') return <WeeklyBriefView brief={brief} />;
      return <MonthlyReviewView brief={brief} />;
    },
    [activeType],
  );

  return (
        <div className="flex flex-col gap-4">
          <div className="flex flex-wrap items-center justify-end gap-2">
              <Button
                type="button"
                size="xs"
                variant="outline"
                className="gap-1"
                onClick={() => {
                  setGenerateError(null);
                  generateMutation.mutate();
                }}
                disabled={generateMutation.isPending || isPolling}
              >
                <RefreshCw
                  className={cn(
                    'size-3',
                    (generateMutation.isPending || isPolling) && 'animate-spin',
                  )}
                  aria-hidden
                />
                {isPolling ? 'Generating...' : 'Generate'}
              </Button>
          </div>

          {/* Generate error */}
          {generateError && (
            <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-3">
              <p className="text-sm text-destructive">{generateError}</p>
            </div>
          )}

          {/* Historical viewing toolbar */}
          {isViewingHistorical && (
            <div className="flex flex-wrap items-center gap-2">
              <Button
                type="button"
                size="xs"
                variant="outline"
                className="gap-1"
                onClick={() => {
                  setSelectedBriefId(null);
                  setCompareMode(false);
                }}
              >
                <ArrowLeft className="size-3" aria-hidden />
                Back to latest
              </Button>
              {latestBrief && (
                <Button
                  type="button"
                  size="xs"
                  variant={compareMode ? 'default' : 'outline'}
                  className="gap-1"
                  onClick={() => setCompareMode(!compareMode)}
                >
                  <ArrowLeftRight className="size-3" aria-hidden />
                  {compareMode ? 'Exit comparison' : 'Compare with latest'}
                </Button>
              )}
            </div>
          )}

          {/* Main content */}
          {activeError ? (
            <Card className={cn('border-destructive/30 py-8', CARD_RING)}>
              <CardContent className="text-center">
                <p className="mb-2 text-sm text-destructive">Failed to load brief.</p>
                <p className="text-xs text-muted-foreground">
                  {(activeErrObj as any)?.message || 'An unexpected error occurred.'}
                </p>
              </CardContent>
            </Card>
          ) : isPending ? (
            <div className="flex flex-col gap-4 py-4">
              <Skeleton className="h-20 rounded-xl" />
              <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                {Array.from({ length: 4 }).map((_, i) => (
                  <Skeleton key={i} className="h-16 rounded-lg" />
                ))}
              </div>
              <Skeleton className="h-[120px] rounded-lg" />
            </div>
          ) : !activeBrief ? (
            <Card className={cn('py-8', CARD_RING)}>
              <CardContent className="text-center">
                <p className="mb-3 text-sm text-muted-foreground">
                  No {activeType} brief available yet.
                </p>
                <Button
                  type="button"
                  size="sm"
                  onClick={() => generateMutation.mutate()}
                  disabled={generateMutation.isPending}
                >
                  Generate {activeType} brief
                </Button>
              </CardContent>
            </Card>
          ) : compareMode && isViewingHistorical && latestBrief ? (
            /* Comparison mode: side-by-side */
            <div className="flex flex-col gap-4">
              <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                <div>
                  <p className="mb-2 text-xs font-semibold text-muted-foreground">
                    Historical —{' '}
                    {activeBrief.as_of ??
                      formatDateFriendly(activeMeta.generated_at, timezone)}
                  </p>
                  {renderBriefView(activeBrief)}
                </div>
                <div>
                  <p className="mb-2 text-xs font-semibold text-muted-foreground">
                    Latest —{' '}
                    {latestBrief.as_of ??
                      formatDateFriendly(
                        (latestBriefData as any)?.generated_at,
                        timezone,
                      )}
                  </p>
                  {renderBriefView(latestBrief)}
                </div>
              </div>
              <BriefDiffSummary historical={activeBrief} latest={latestBrief} />
            </div>
          ) : (
            /* Single brief view */
            <>
              <div className="flex flex-wrap justify-between gap-2">
                <p className="text-xs text-muted-foreground">
                  Generated: {formatDateTimeFriendly(activeMeta.generated_at, timezone)}
                  {' | '}
                  {activeBrief.snapshot_count ?? 0} symbols analyzed
                </p>
              </div>
              {renderBriefView(activeBrief)}
            </>
          )}

          {/* Previous Briefs with pagination */}
          {briefList.length > 0 && (
            <Card className={cn('gap-0 py-4', CARD_RING)}>
              <CardContent className="flex flex-col gap-1">
                <p className="mb-2 text-sm font-semibold">Previous Briefs</p>
                {briefList.map((b: any) => {
                  const isActive = b.id === selectedBriefId;
                  const transCount =
                    b.summary?.transitions_count ??
                    b.summary?.stage_transitions ??
                    null;
                  return (
                    <button
                      key={b.id}
                      type="button"
                      onClick={() => {
                        setSelectedBriefId(b.id);
                        setCompareMode(false);
                      }}
                      className={cn(
                        'flex w-full flex-wrap items-center justify-between gap-2 rounded-md px-2 py-1.5 text-left text-xs transition-colors',
                        isActive
                          ? 'bg-primary/10 ring-1 ring-primary/30'
                          : 'hover:bg-muted/80',
                      )}
                    >
                      <div className="flex items-center gap-2">
                        <Badge variant="secondary" className="font-normal">
                          {b.type}
                        </Badge>
                        <span className={DATA_MONO}>{b.summary?.as_of ?? '—'}</span>
                        {transCount != null && transCount > 0 && (
                          <span className="text-muted-foreground">
                            {transCount} transitions
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        {b.summary?.regime_state && (
                          <Badge
                            variant={regimeBadgeVariant(b.summary.regime_state)}
                            className="font-normal"
                          >
                            {b.summary.regime_state}
                          </Badge>
                        )}
                        <span className="text-muted-foreground">
                          {formatDateFriendly(b.generated_at, timezone)}
                        </span>
                      </div>
                    </button>
                  );
                })}
                {hasMore && (
                  <Button
                    type="button"
                    size="xs"
                    variant="ghost"
                    className="mt-1 self-center text-xs"
                    onClick={() => setBriefListOffset((prev) => prev + PAGE_SIZE)}
                  >
                    Load more
                  </Button>
                )}
              </CardContent>
            </Card>
          )}
        </div>
  );
};

export default IntelligenceBriefTab;
