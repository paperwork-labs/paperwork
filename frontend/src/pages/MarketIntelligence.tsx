import React from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Calendar, FileText, RefreshCw, TrendingUp } from 'lucide-react';

import StageBadge from '../components/shared/StageBadge';
import StatCard from '../components/shared/StatCard';
import { REGIME_HEX } from '../constants/chart';
import { marketDataApi } from '../services/api';
import { formatDateFriendly, formatDateTimeFriendly } from '../utils/format';
import { useUserPreferences } from '../hooks/useUserPreferences';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Page } from '@/components/ui/Page';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { cn } from '@/lib/utils';
import { heatTextClass, semanticTextColorClass } from '@/lib/semantic-text-color';

const DATA_MONO = 'font-mono tracking-tight';

const REGIME_LABELS: Record<string, string> = {
  R1: 'Bull', R2: 'Bull Extended', R3: 'Chop', R4: 'Bear Rally', R5: 'Bear',
};

type BriefType = 'daily' | 'weekly' | 'monthly';

const BRIEF_TAB_META: { key: BriefType; label: string; icon: React.ElementType }[] = [
  { key: 'daily', label: 'Daily Digest', icon: FileText },
  { key: 'weekly', label: 'Weekly Brief', icon: TrendingUp },
  { key: 'monthly', label: 'Monthly Review', icon: Calendar },
];

const fmtPct = (v: unknown): string => {
  if (typeof v !== 'number' || !Number.isFinite(v)) return '—';
  return `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`;
};

function regimeBadgeVariant(state: string): React.ComponentProps<typeof Badge>['variant'] {
  if (state === 'R1') return 'default';
  if (state === 'R5') return 'destructive';
  return 'secondary';
}

const MarketIntelligence: React.FC = () => {
  const { timezone } = useUserPreferences();
  const [activeType, setActiveType] = React.useState<BriefType>('daily');
  const [isPolling, setIsPolling] = React.useState(false);
  const queryClient = useQueryClient();

  React.useEffect(() => {
    if (!isPolling) return;
    const timer = setTimeout(() => setIsPolling(false), 30_000);
    return () => clearTimeout(timer);
  }, [isPolling]);

  const { data: briefData, isPending, isError, error } = useQuery({
    queryKey: ['intelligence-brief', activeType],
    queryFn: async () => {
      const resp = await marketDataApi.getLatestBrief(activeType);
      return resp?.data ?? resp ?? null;
    },
    staleTime: 2 * 60_000,
    refetchInterval: isPolling ? 3_000 : false,
  });

  const { data: briefList } = useQuery({
    queryKey: ['intelligence-list', activeType],
    queryFn: async () => {
      const resp = await marketDataApi.listBriefs(activeType, 10);
      return resp?.data?.briefs ?? resp?.briefs ?? [];
    },
    staleTime: 5 * 60_000,
    refetchInterval: isPolling ? 5_000 : false,
  });

  const generateMutation = useMutation({
    mutationFn: () => marketDataApi.triggerBrief(activeType),
    onSuccess: () => {
      setIsPolling(true);
      queryClient.invalidateQueries({ queryKey: ['intelligence-brief', activeType] });
      queryClient.invalidateQueries({ queryKey: ['intelligence-list', activeType] });
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

  const [generateError, setGenerateError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (isPolling && briefData?.brief) {
      setIsPolling(false);
    }
  }, [isPolling, briefData]);

  React.useEffect(() => {
    setGenerateError(null);
  }, [activeType]);

  const brief = briefData?.brief;

  return (
    <Page>
      <div className="flex flex-col gap-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
          <h1 className="font-heading text-2xl font-semibold tracking-tight text-foreground md:text-3xl">
            Intelligence Briefs
          </h1>
          <div className="flex flex-wrap items-center gap-2">
            <Tabs value={activeType} onValueChange={(v) => setActiveType(v as BriefType)}>
              <TabsList className="h-8 flex-wrap gap-0.5 p-1">
                {BRIEF_TAB_META.map((tab) => {
                  const Icon = tab.icon;
                  return (
                    <TabsTrigger key={tab.key} value={tab.key} className="h-7 gap-1 px-2 text-xs">
                      <Icon className="size-3" aria-hidden />
                      {tab.label}
                    </TabsTrigger>
                  );
                })}
              </TabsList>
            </Tabs>
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
              <RefreshCw className={cn('size-3', (generateMutation.isPending || isPolling) && 'animate-spin')} aria-hidden />
              {isPolling ? 'Generating...' : 'Generate'}
            </Button>
          </div>
        </div>

        {generateError ? (
          <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-3">
            <p className="text-sm text-destructive">{generateError}</p>
          </div>
        ) : null}

        {isError ? (
          <Card className="border-destructive/30 py-8 shadow-xs ring-1 ring-foreground/10">
            <CardContent className="text-center">
              <p className="mb-2 text-sm text-destructive">Failed to load brief.</p>
              <p className="text-xs text-muted-foreground">{(error as any)?.message || 'An unexpected error occurred.'}</p>
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
        ) : !brief ? (
          <Card className="py-8 shadow-xs ring-1 ring-foreground/10">
            <CardContent className="text-center">
              <p className="mb-3 text-sm text-muted-foreground">No {activeType} brief available yet.</p>
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
        ) : (
          <>
            <div className="flex flex-wrap justify-between gap-2">
              <p className="text-xs text-muted-foreground">
                Generated: {formatDateTimeFriendly(briefData?.generated_at, timezone)}
                {' | '}{brief.snapshot_count ?? 0} symbols analyzed
              </p>
            </div>

            {activeType === 'daily' && <DailyDigestView brief={brief} />}
            {activeType === 'weekly' && <WeeklyBriefView brief={brief} />}
            {activeType === 'monthly' && <MonthlyReviewView brief={brief} />}
          </>
        )}

        {Array.isArray(briefList) && briefList.length > 0 ? (
          <Card className="gap-0 py-4 shadow-xs ring-1 ring-foreground/10">
            <CardContent className="flex flex-col gap-1">
              <p className="mb-2 text-sm font-semibold">Previous Briefs</p>
              {briefList.map((b: any) => (
                <div
                  key={b.id}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-md px-2 py-1 text-xs transition-colors hover:bg-muted/80"
                >
                  <div className="flex items-center gap-2">
                    <Badge variant="secondary" className="font-normal">
                      {b.type}
                    </Badge>
                    <span className={DATA_MONO}>{b.summary?.as_of ?? '—'}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    {b.summary?.regime_state ? (
                      <Badge variant={regimeBadgeVariant(b.summary.regime_state)} className="font-normal">
                        {b.summary.regime_state}
                      </Badge>
                    ) : null}
                    <span className="text-muted-foreground">{formatDateFriendly(b.generated_at, timezone)}</span>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        ) : null}
      </div>
    </Page>
  );
};

const DailyDigestView: React.FC<{ brief: any }> = ({ brief }) => {
  const regime = brief.regime || {};
  const regimeColor = REGIME_HEX[regime.state] || '#64748B';

  return (
    <div className="flex flex-col gap-4">
      <Card
        className="relative gap-0 overflow-hidden border-2 py-4 shadow-xs ring-1 ring-foreground/10"
        style={{ borderColor: regimeColor }}
      >
        <div
          className="pointer-events-none absolute inset-0 opacity-[0.06]"
          style={{ backgroundColor: regimeColor }}
          aria-hidden
        />
        <CardContent className="relative flex flex-col flex-wrap gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-wrap items-center gap-3">
            <div
              className="rounded-md px-3 py-1 text-lg font-bold text-white"
              style={{ backgroundColor: regimeColor }}
            >
              {regime.state}
            </div>
            <div>
              <p className="font-semibold">{REGIME_LABELS[regime.state] || regime.state}</p>
              <p className={cn('text-xs text-muted-foreground', DATA_MONO)}>Score: {regime.score?.toFixed(2)}</p>
            </div>
            {regime.changed ? (
              <Badge variant="secondary" className="border-transparent bg-amber-500/20 text-amber-800 dark:text-amber-200">
                Changed from {regime.previous_state}
              </Badge>
            ) : null}
          </div>
          <div className="grid w-full max-w-md grid-cols-3 gap-3 sm:w-auto">
            <StatCard label="VIX" value={regime.vix_spot?.toFixed(1) ?? '—'} />
            <StatCard label="Sizing" value={`${regime.multiplier?.toFixed(2) ?? '—'}x`} />
            <StatCard label="Max Equity" value={`${regime.max_equity_pct ?? '—'}%`} />
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <StatCard label="Above 50 DMA" value={`${brief.breadth?.above_50d_pct ?? 0}%`} />
        <StatCard label="Above 200 DMA" value={`${brief.breadth?.above_200d_pct ?? 0}%`} />
        <StatCard label="Stage Transitions" value={String(brief.stage_transitions?.length ?? 0)} />
        <StatCard label="Exit Alerts" value={String(brief.exit_alerts?.length ?? 0)} />
      </div>

      {brief.stage_distribution ? (
        <Card className="gap-0 py-4 shadow-xs ring-1 ring-foreground/10">
          <CardContent>
            <p className="mb-2 text-sm font-semibold">Stage Distribution</p>
            <div className="flex flex-wrap gap-2">
              {Object.entries(brief.stage_distribution).map(([stage, count]: [string, any]) => (
                <div key={stage} className="flex items-center gap-1">
                  <StageBadge stage={stage} />
                  <span className="text-xs">{count}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      ) : null}

      {brief.stage_transitions?.length > 0 ? (
        <Card className="gap-0 py-4 shadow-xs ring-1 ring-foreground/10">
          <CardContent>
            <p className="mb-2 text-sm font-semibold">Stage Transitions</p>
            <div className="flex flex-col gap-1">
              {brief.stage_transitions.map((t: any, i: number) => (
                <div key={`${t.symbol}-${i}`} className="flex items-center justify-between text-xs">
                  <span className="font-semibold">{t.symbol}</span>
                  <div className="flex items-center gap-1">
                    <StageBadge stage={t.from_stage} />
                    <span className="text-muted-foreground">→</span>
                    <StageBadge stage={t.to_stage} />
                    {t.days_in_stage != null ? <span className="text-muted-foreground">{t.days_in_stage}d</span> : null}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      ) : null}

      {brief.exit_alerts?.length > 0 ? (
        <Card className="gap-0 py-4 shadow-xs ring-1 ring-foreground/10">
          <CardContent>
            <p className="mb-2 text-sm font-semibold text-destructive">Exit Alerts</p>
            <div className="flex flex-col gap-1">
              {brief.exit_alerts.map((a: any, i: number) => (
                <div key={`exit-${a.symbol}-${i}`} className="flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold">{a.symbol}</span>
                    <StageBadge stage={a.stage} />
                  </div>
                  {a.pnl_pct != null ? (
                    <span className={cn(DATA_MONO, semanticTextColorClass(a.pnl_pct >= 0 ? 'green.500' : 'red.500'))}>
                      {a.pnl_pct >= 0 ? '+' : ''}{a.pnl_pct}%
                    </span>
                  ) : null}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
};

const WeeklyBriefView: React.FC<{ brief: any }> = ({ brief }) => (
  <div className="flex flex-col gap-4">
    {brief.regime_trend?.length > 0 ? (
      <Card className="gap-0 py-4 shadow-xs ring-1 ring-foreground/10">
        <CardContent>
          <p className="mb-2 text-sm font-semibold">Regime Trend (7d)</p>
          <div className="flex flex-wrap gap-1">
            {brief.regime_trend.map((r: any, i: number) => (
              <span
                key={i}
                className="rounded-md px-2 py-1 text-xs font-bold text-white"
                style={{ backgroundColor: REGIME_HEX[r.state] || '#64748B' }}
                title={`${r.date}: ${r.state} (${r.score})`}
              >
                {r.state}
              </span>
            ))}
          </div>
        </CardContent>
      </Card>
    ) : null}

    {brief.top_picks ? (
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <PickList title="Buy List" items={brief.top_picks.buy} tone="green" />
        <PickList title="Watch List" items={brief.top_picks.watch} tone="blue" />
        <PickList title="Short List" items={brief.top_picks.short} tone="red" />
      </div>
    ) : null}

    {brief.sector_analysis?.length > 0 ? (
      <Card className="gap-0 py-4 shadow-xs ring-1 ring-foreground/10">
        <CardContent>
          <p className="mb-2 text-sm font-semibold">Sector Analysis</p>
          <div className="flex flex-col gap-1">
            {brief.sector_analysis.map((s: any) => (
              <div
                key={s.sector}
                className="flex flex-wrap items-center justify-between gap-2 rounded-md px-2 py-1 text-xs transition-colors hover:bg-muted/80"
              >
                <span className="font-medium">{s.sector} ({s.count})</span>
                <div className="flex items-center gap-3">
                  <span className={cn(DATA_MONO, heatTextClass(s.avg_rs))}>RS {fmtPct(s.avg_rs)}</span>
                  <span className={cn(DATA_MONO, semanticTextColorClass('green.500'))}>Stage 2: {s.stage2_pct}%</span>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    ) : null}

    {brief.stage_distribution ? (
      <Card className="gap-0 py-4 shadow-xs ring-1 ring-foreground/10">
        <CardContent>
          <p className="mb-2 text-sm font-semibold">Stage Distribution</p>
          <div className="flex flex-wrap gap-2">
            {Object.entries(brief.stage_distribution).map(([stage, count]: [string, any]) => (
              <div key={stage} className="flex items-center gap-1">
                <StageBadge stage={stage} />
                <span className="text-xs">{count}</span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    ) : null}
  </div>
);

const MonthlyReviewView: React.FC<{ brief: any }> = ({ brief }) => (
  <div className="flex flex-col gap-4">
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
      <StatCard label="Period" value={`${brief.period_start} to ${brief.as_of}`} />
      <StatCard label="Regime Transitions" value={String(brief.regime_transitions ?? 0)} />
      <StatCard label="Avg 20D Perf" value={fmtPct(brief.performance_summary?.avg_20d)} />
      <StatCard label="Median 20D Perf" value={fmtPct(brief.performance_summary?.median_20d)} />
    </div>

    {brief.regime_history?.length > 0 ? (
      <Card className="gap-0 py-4 shadow-xs ring-1 ring-foreground/10">
        <CardContent>
          <p className="mb-2 text-sm font-semibold">Regime History (30d)</p>
          <div className="flex flex-wrap gap-0">
            {brief.regime_history.map((r: any, i: number) => (
              <div
                key={i}
                className="h-6 w-0.5 rounded-[1px]"
                style={{ backgroundColor: REGIME_HEX[r.state] || '#64748B' }}
                title={`${r.date}: ${r.state} (${r.score})`}
              />
            ))}
          </div>
        </CardContent>
      </Card>
    ) : null}

    {brief.performance_summary ? (
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Card className="gap-0 py-4 shadow-xs ring-1 ring-foreground/10">
          <CardContent>
            <p className="mb-2 text-sm font-semibold text-[rgb(var(--status-success)/1)]">Top 5 Performers (20d)</p>
            <div className="flex flex-col gap-1">
              {(brief.performance_summary.best || []).map((s: any) => (
                <div key={s.symbol} className="flex items-center justify-between text-xs">
                  <span className="font-semibold">{s.symbol}</span>
                  <span className={cn(DATA_MONO, semanticTextColorClass('green.500'))}>{fmtPct(s.perf_20d)}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
        <Card className="gap-0 py-4 shadow-xs ring-1 ring-foreground/10">
          <CardContent>
            <p className="mb-2 text-sm font-semibold text-destructive">Bottom 5 Performers (20d)</p>
            <div className="flex flex-col gap-1">
              {(brief.performance_summary.worst || []).map((s: any) => (
                <div key={s.symbol} className="flex items-center justify-between text-xs">
                  <span className="font-semibold">{s.symbol}</span>
                  <span className={cn(DATA_MONO, semanticTextColorClass('red.500'))}>{fmtPct(s.perf_20d)}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    ) : null}
  </div>
);

const PickList: React.FC<{ title: string; items: any[]; tone: 'green' | 'blue' | 'red' }> = ({ title, items, tone }) => {
  const badgeClass =
    tone === 'green'
      ? 'border-transparent bg-[rgb(var(--status-success)/0.12)] text-[rgb(var(--status-success)/1)]'
      : tone === 'red'
        ? 'border-transparent bg-destructive/10 text-destructive'
        : 'bg-secondary text-secondary-foreground';
  return (
    <Card className="gap-0 py-4 shadow-xs ring-1 ring-foreground/10">
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
              <div key={`${p.symbol}-${i}`} className="flex items-center justify-between text-xs">
                <span className="font-semibold">{p.symbol}</span>
                <div className="flex items-center gap-1">
                  <StageBadge stage={p.stage || '—'} />
                  {p.scan_tier ? <span className="text-muted-foreground">{p.scan_tier}</span> : null}
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default MarketIntelligence;
