import React, { useEffect, useState, useCallback } from 'react';
import { ArrowLeft, Check, Edit2, ExternalLink, Loader2, Pause, Play, Save, X as XIcon } from 'lucide-react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { Page, PageHeader } from '../components/ui/Page';
import { EntryExitRules } from '../components/strategy/RuleDisplay';
import BacktestResults from '../components/strategy/BacktestResults';
import { BacktestStatusBadge } from '../components/strategy/BacktestStatusBadge';
import api from '../services/api';
import { formatDateFriendly } from '../utils/format';
import { useUserPreferences } from '../hooks/useUserPreferences';
import type { Strategy, StrategyStatus, BacktestResult, ConditionGroupData } from '../types/strategy';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { cn } from '@/lib/utils';
import { semanticTextColorClass } from '@/lib/semantic-text-color';
import { SymbolLink, ChartContext, ChartSlidePanel } from '@/components/market/SymbolChartUI';

function extractData<T>(resp: { data?: { data?: T } }): T {
  return (resp?.data as { data?: T })?.data ?? (resp?.data as T);
}

const STATUS_BADGE_CLASS: Record<StrategyStatus, string> = {
  active: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-800 dark:text-emerald-200',
  paused: 'border-amber-500/40 bg-amber-500/10 text-amber-900 dark:text-amber-100',
  draft: 'border-border bg-muted/60 text-muted-foreground',
  stopped: 'border-destructive/40 bg-destructive/10 text-destructive',
  archived: 'border-destructive/40 bg-destructive/10 text-destructive',
};

interface SignalSubResult {
  rule: string;
  passed: boolean;
  actual_value?: number;
  threshold?: string;
}

interface EvaluateSignal {
  symbol?: string;
  action?: string;
  strength?: unknown;
  context?: {
    sub_results?: SignalSubResult[];
  };
  regime_state?: string;
  regime_multiplier?: number;
}

interface EvaluateSummary {
  universe_scanned: number;
  matches: number;
}

interface BacktestHistoryItem {
  id: number;
  name?: string;
  created_at: string;
  start_date: string;
  end_date: string;
  status?: string;
  total_return_pct: number;
  max_drawdown_pct?: number;
  win_rate_pct: number;
  total_trades: number;
}

type PaperValidationStatus = 'not_started' | 'in_progress' | 'passed' | 'failed' | 'expired';

interface PaperValidationState {
  status: PaperValidationStatus;
  days_elapsed?: number;
  trades_count?: number;
  win_rate_pct?: number;
  total_return_pct?: number;
  max_drawdown_pct?: number;
  profit_factor?: number;
  can_go_live?: boolean;
  message?: string;
  started_at?: string;
  completed_at?: string;
}

export default function StrategyDetail() {
  const { strategyId } = useParams<{ strategyId: string }>();
  const navigate = useNavigate();
  const { timezone } = useUserPreferences();
  const [strategy, setStrategy] = useState<Strategy | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('overview');

  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState('');
  const [editDesc, setEditDesc] = useState('');
  const [saving, setSaving] = useState(false);

  const [backtestLoading, setBacktestLoading] = useState(false);
  const [backtestResult, setBacktestResult] = useState<BacktestResult | null>(null);
  const [btStartDate, setBtStartDate] = useState('2024-01-01');
  const [btEndDate, setBtEndDate] = useState('2025-01-01');
  const [btCapital, setBtCapital] = useState(100000);

  const [signals, setSignals] = useState<EvaluateSignal[]>([]);
  const [signalsLoading, setSignalsLoading] = useState(false);
  const [evaluateSummary, setEvaluateSummary] = useState<EvaluateSummary | null>(null);
  const [chartSymbol, setChartSymbol] = useState<string | null>(null);
  const [selectedHistBacktestId, setSelectedHistBacktestId] = useState<number | null>(null);
  const [validationLoading, setValidationLoading] = useState<string | null>(null);
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!strategyId) return;
    (async () => {
      try {
        const resp = await api.get(`/strategies/${strategyId}`);
        const data = extractData<Strategy>(resp);
        setStrategy(data);
        setEditName(data?.name ?? '');
        setEditDesc(data?.description ?? '');
      } catch {
        toast.error('Failed to load strategy');
      } finally {
        setLoading(false);
      }
    })();
  }, [strategyId]);

  const handleSave = useCallback(async () => {
    if (!strategy) return;
    setSaving(true);
    try {
      const resp = await api.put(`/strategies/${strategy.id}`, {
        name: editName,
        description: editDesc,
      });
      setStrategy(extractData<Strategy>(resp));
      setEditing(false);
      toast.success('Strategy updated');
    } catch {
      toast.error('Failed to update');
    } finally {
      setSaving(false);
    }
  }, [strategy, editName, editDesc]);

  const handleStatusChange = useCallback(async (newStatus: string) => {
    if (!strategy) return;
    try {
      const resp = await api.put(`/strategies/${strategy.id}`, { status: newStatus });
      setStrategy(extractData<Strategy>(resp));
      toast.success(`Strategy ${newStatus}`);
    } catch {
      toast.error('Failed to update status');
    }
  }, [strategy]);

  const runBacktest = useCallback(async () => {
    if (!strategy) return;
    setBacktestLoading(true);
    setBacktestResult(null);
    try {
      const resp = await api.post(`/strategies/${strategy.id}/backtest`, {
        start_date: btStartDate,
        end_date: btEndDate,
        initial_capital: btCapital,
        position_size_pct: Number(strategy.position_size_pct ?? 5),
      });
      setBacktestResult(extractData<BacktestResult>(resp));
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      toast.error(err?.response?.data?.detail ?? 'Backtest failed');
    } finally {
      setBacktestLoading(false);
    }
  }, [strategy, btStartDate, btEndDate, btCapital]);

  const runEvaluate = useCallback(async () => {
    if (!strategy) return;
    const params = strategy.parameters ?? {};
    const entryRules = params.entry_rules as ConditionGroupData | undefined;
    if (!entryRules) {
      toast.error('No entry rules configured');
      return;
    }
    setSignalsLoading(true);
    try {
      const resp = await api.post(`/strategies/${strategy.id}/evaluate`, {
        rules: entryRules,
      });
      const data = extractData<{ signals: EvaluateSignal[]; universe_scanned?: number; matches?: number }>(resp);
      setSignals(data?.signals ?? []);
      if (data?.universe_scanned != null) {
        setEvaluateSummary({
          universe_scanned: data.universe_scanned,
          matches: data.matches ?? data?.signals?.length ?? 0,
        });
      }
    } catch {
      toast.error('Evaluation failed');
    } finally {
      setSignalsLoading(false);
    }
  }, [strategy]);

  const backtestHistoryQuery = useQuery<BacktestHistoryItem[]>({
    queryKey: ['strategy-backtest-history', strategyId],
    queryFn: async () => {
      const resp = await api.get(`/strategies/${strategyId}/backtests`);
      return extractData<BacktestHistoryItem[]>(resp) ?? [];
    },
    enabled: activeTab === 'backtest' && !!strategyId,
    staleTime: 60_000,
  });

  const historicalBacktestQuery = useQuery<BacktestResult>({
    queryKey: ['strategy-backtest-detail', selectedHistBacktestId],
    queryFn: async () => {
      const resp = await api.get(`/strategies/backtests/${selectedHistBacktestId}`);
      return extractData<BacktestResult>(resp);
    },
    enabled: !!selectedHistBacktestId,
    staleTime: 5 * 60_000,
  });

  const validationQuery = useQuery<PaperValidationState>({
    queryKey: ['strategy-paper-validation', strategyId],
    queryFn: async () => {
      const resp = await api.get(`/strategies/${strategyId}/paper-validation/status`);
      return extractData<PaperValidationState>(resp) ?? { status: 'not_started' as const };
    },
    enabled: activeTab === 'overview' && !!strategyId,
    staleTime: 30_000,
    refetchInterval: (query) => {
      return query.state.data?.status === 'in_progress' ? 5_000 : false;
    },
  });

  const handleStartValidation = useCallback(async () => {
    if (!strategyId) return;
    setValidationLoading('start');
    try {
      await api.post(`/strategies/${strategyId}/paper-validation/start`);
      queryClient.invalidateQueries({ queryKey: ['strategy-paper-validation', strategyId] });
      toast.success('Paper validation started');
    } catch {
      toast.error('Failed to start validation');
    } finally {
      setValidationLoading(null);
    }
  }, [strategyId, queryClient]);

  const handleResetValidation = useCallback(async () => {
    if (!strategyId) return;
    setValidationLoading('reset');
    try {
      await api.post(`/strategies/${strategyId}/paper-validation/reset`);
      queryClient.invalidateQueries({ queryKey: ['strategy-paper-validation', strategyId] });
      toast.success('Validation reset');
    } catch {
      toast.error('Failed to reset validation');
    } finally {
      setValidationLoading(null);
    }
  }, [strategyId, queryClient]);

  const handlePromoteToLive = useCallback(async () => {
    if (!strategy) return;
    setValidationLoading('promote');
    try {
      await api.post(`/strategies/${strategy.id}/paper-validation/promote`);
      toast.success('Strategy promoted to live');
      const resp = await api.get(`/strategies/${strategy.id}`);
      setStrategy(extractData<Strategy>(resp));
    } catch {
      toast.error('Failed to promote strategy');
    } finally {
      setValidationLoading(null);
    }
  }, [strategy]);

  if (loading) {
    return (
      <Page>
        <p className="text-sm text-muted-foreground">Loading strategy...</p>
      </Page>
    );
  }

  if (!strategy) {
    return (
      <Page>
        <p className={cn('text-sm', semanticTextColorClass('status.danger'))}>Strategy not found</p>
        <Button className="mt-4" onClick={() => navigate('/market/strategies')}>
          Back to Strategies
        </Button>
      </Page>
    );
  }

  const params = strategy.parameters ?? {};
  const entryRules = params.entry_rules as ConditionGroupData | undefined;
  const exitRules = params.exit_rules as ConditionGroupData | undefined;

  return (
    <ChartContext.Provider value={setChartSymbol}>
    <Page>
      <div className="mb-4">
        <Button size="sm" variant="ghost" className="gap-1" onClick={() => navigate('/market/strategies')}>
          <ArrowLeft className="size-4" aria-hidden />
          Back
        </Button>
      </div>

      <PageHeader
        title={editing ? '' : strategy.name}
        subtitle={editing ? '' : strategy.description || 'No description'}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            {strategy.status === 'draft' && (
              <Button size="sm" className="gap-1 bg-emerald-600 hover:bg-emerald-700" onClick={() => handleStatusChange('active')}>
                <Play className="size-4" aria-hidden />
                Activate
              </Button>
            )}
            {strategy.status === 'active' && (
              <Button
                size="sm"
                className="gap-1 bg-amber-500 text-amber-950 hover:bg-amber-400"
                onClick={() => handleStatusChange('paused')}
              >
                <Pause className="size-4" aria-hidden />
                Pause
              </Button>
            )}
            {strategy.status === 'paused' && (
              <Button size="sm" className="gap-1 bg-emerald-600 hover:bg-emerald-700" onClick={() => handleStatusChange('active')}>
                <Play className="size-4" aria-hidden />
                Resume
              </Button>
            )}
            <BacktestStatusBadge validation={strategy.backtest_validation} className="h-6 px-2.5 text-xs" />
            <Badge
              variant="outline"
              className={cn('h-6 px-2.5 text-xs font-medium', STATUS_BADGE_CLASS[strategy.status] ?? STATUS_BADGE_CLASS.draft)}
            >
              {strategy.status}
            </Badge>
          </div>
        }
      />

      <Tabs value={activeTab} onValueChange={setActiveTab} className="mt-4">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="rules">Rules</TabsTrigger>
          <TabsTrigger value="backtest">Backtest</TabsTrigger>
          <TabsTrigger value="signals">Signals</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="mt-4 flex flex-col gap-4">
          {editing ? (
            <Card className="gap-0 border border-border shadow-none ring-0">
              <CardContent className="flex flex-col gap-3 py-4">
                <div>
                  <p className="mb-1 text-sm font-semibold">Name</p>
                  <Input value={editName} onChange={(e) => setEditName(e.target.value)} />
                </div>
                <div>
                  <p className="mb-1 text-sm font-semibold">Description</p>
                  <Input value={editDesc} onChange={(e) => setEditDesc(e.target.value)} />
                </div>
                <div className="flex gap-2">
                  <Button size="sm" className="gap-1" disabled={saving} onClick={handleSave}>
                    {saving ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Save className="size-4" aria-hidden />}
                    Save
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => setEditing(false)}>
                    Cancel
                  </Button>
                </div>
              </CardContent>
            </Card>
          ) : (
            <div className="flex">
              <Button size="xs" variant="ghost" className="gap-1" onClick={() => setEditing(true)}>
                <Edit2 className="size-3.5" aria-hidden />
                Edit
              </Button>
            </div>
          )}

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            <InfoCard label="Strategy Type" value={strategy.strategy_type} />
            <InfoCard label="Execution Mode" value={strategy.execution_mode ?? 'paper'} />
            <InfoCard label="Position Size" value={`${strategy.position_size_pct ?? '—'}%`} />
            <InfoCard label="Max Positions" value={String(strategy.max_positions ?? '—')} />
            <InfoCard label="Stop Loss" value={strategy.stop_loss_pct ? `${strategy.stop_loss_pct}%` : '—'} />
            <InfoCard label="Take Profit" value={strategy.take_profit_pct ? `${strategy.take_profit_pct}%` : '—'} />
            <InfoCard label="Run Frequency" value={strategy.run_frequency ?? 'on_demand'} />
            <InfoCard label="Created" value={formatDateFriendly(strategy.created_at, timezone)} />
            <InfoCard label="Updated" value={formatDateFriendly(strategy.updated_at, timezone)} />
          </div>

          <Card className="gap-0 border border-border shadow-none ring-0">
            <CardContent className="py-4">
              <div className="mb-3 flex items-center gap-2">
                <p className="font-semibold">Validation</p>
                <Badge
                  variant="outline"
                  className={cn(
                    'h-5 text-[10px]',
                    validationQuery.data?.status === 'passed' && 'border-emerald-500/40 bg-emerald-500/10 text-emerald-800 dark:text-emerald-200',
                    validationQuery.data?.status === 'in_progress' && 'border-amber-500/40 bg-amber-500/10 text-amber-900 dark:text-amber-100',
                    validationQuery.data?.status === 'failed' && 'border-destructive/40 bg-destructive/10 text-destructive',
                    (!validationQuery.data || validationQuery.data.status === 'not_started') && 'border-border bg-muted/60 text-muted-foreground',
                  )}
                >
                  {validationQuery.data?.status?.replace('_', ' ') ?? 'not started'}
                </Badge>
              </div>
              {entryRules && exitRules ? (
                <div className="flex flex-col gap-3">
                  {validationQuery.data?.status === 'in_progress' && validationQuery.data.days_elapsed != null && (
                    <p className="text-xs text-muted-foreground">
                      Day {validationQuery.data.days_elapsed} — {validationQuery.data.trades_count ?? 0} trades so far
                    </p>
                  )}
                  <div className="flex flex-wrap gap-2">
                    {(!validationQuery.data || validationQuery.data.status === 'not_started' || validationQuery.data.status === 'failed') && (
                      <Button
                        size="sm"
                        className="gap-1"
                        disabled={validationLoading === 'start'}
                        onClick={handleStartValidation}
                      >
                        {validationLoading === 'start' && <Loader2 className="size-4 animate-spin" aria-hidden />}
                        Start Paper Validation
                      </Button>
                    )}
                    {validationQuery.data?.status === 'passed' && (
                      <Button
                        size="sm"
                        className="gap-1 bg-emerald-600 hover:bg-emerald-700"
                        disabled={validationLoading === 'promote'}
                        onClick={handlePromoteToLive}
                      >
                        {validationLoading === 'promote' && <Loader2 className="size-4 animate-spin" aria-hidden />}
                        Promote to Live
                      </Button>
                    )}
                    {validationQuery.data && validationQuery.data.status !== 'not_started' && (
                      <Button
                        size="sm"
                        variant="outline"
                        className="gap-1"
                        disabled={validationLoading === 'reset'}
                        onClick={handleResetValidation}
                      >
                        {validationLoading === 'reset' && <Loader2 className="size-4 animate-spin" aria-hidden />}
                        Reset
                      </Button>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Lifecycle: Draft → Backtest → Paper Validate → Live
                  </p>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">
                  Add entry and exit rules to enable paper validation.
                </p>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="rules" className="mt-4 flex flex-col gap-4">
          <EntryExitRules entryRules={entryRules} exitRules={exitRules} />
          {!entryRules && !exitRules && (
            <Card className="gap-0 border border-border shadow-none ring-0">
              <CardContent className="py-4">
                <p className="text-sm text-muted-foreground">
                  No rules configured yet. Rules are stored in the strategy parameters as entry_rules and exit_rules
                  condition groups.
                </p>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="backtest" className="mt-4 flex flex-col gap-4">
          <Card className="gap-0 border border-border shadow-none ring-0">
            <CardContent className="flex flex-col gap-3 py-4">
              <p className="font-semibold">Backtest Configuration</p>
              <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                <div>
                  <p className="mb-1 text-xs text-muted-foreground">Start Date</p>
                  <Input type="date" value={btStartDate} onChange={(e) => setBtStartDate(e.target.value)} />
                </div>
                <div>
                  <p className="mb-1 text-xs text-muted-foreground">End Date</p>
                  <Input type="date" value={btEndDate} onChange={(e) => setBtEndDate(e.target.value)} />
                </div>
                <div>
                  <p className="mb-1 text-xs text-muted-foreground">Initial Capital</p>
                  <Input
                    type="number"
                    value={btCapital}
                    onChange={(e) => setBtCapital(Number(e.target.value) || 100000)}
                  />
                </div>
              </div>
              <Button size="sm" className="w-fit gap-2" disabled={!entryRules || !exitRules || backtestLoading} onClick={runBacktest}>
                {backtestLoading ? <Loader2 className="size-4 animate-spin" aria-hidden /> : null}
                Run Backtest
              </Button>
              {(!entryRules || !exitRules) && (
                <p className={cn('text-xs', semanticTextColorClass('status.warning'))}>
                  Strategy must have both entry and exit rules to run a backtest.
                </p>
              )}
            </CardContent>
          </Card>
          {backtestResult ? <BacktestResults result={backtestResult} /> : null}

          <Card className="gap-0 border border-border shadow-none ring-0">
            <CardContent className="py-4">
              <p className="mb-3 font-semibold">Backtest History</p>
              {backtestHistoryQuery.isLoading ? (
                <div className="flex items-center gap-2">
                  <Loader2 className="size-4 animate-spin" aria-hidden />
                  <span className="text-sm text-muted-foreground">Loading history…</span>
                </div>
              ) : backtestHistoryQuery.data?.length ? (
                <div className="space-y-2">
                  {backtestHistoryQuery.data.map((bt) => (
                    <button
                      key={bt.id}
                      type="button"
                      className={cn(
                        'flex w-full items-center justify-between rounded-md border border-border px-3 py-2 text-left text-sm transition-colors hover:bg-muted/60',
                        selectedHistBacktestId === bt.id && 'border-primary bg-primary/5',
                      )}
                      onClick={() => setSelectedHistBacktestId(bt.id)}
                    >
                      <div className="flex flex-col gap-0.5">
                        <span className="font-medium">{bt.start_date} → {bt.end_date}</span>
                        <span className="text-xs text-muted-foreground">{formatDateFriendly(bt.created_at, timezone)}</span>
                      </div>
                      <div className="flex items-center gap-3 text-xs">
                        <span className={cn(bt.total_return_pct >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-destructive')}>
                          {bt.total_return_pct >= 0 ? '+' : ''}{bt.total_return_pct.toFixed(1)}%
                        </span>
                        <span className="text-muted-foreground">WR {bt.win_rate_pct.toFixed(0)}%</span>
                        <span className="text-muted-foreground">{bt.total_trades} trades</span>
                      </div>
                    </button>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">No historical backtests</p>
              )}
            </CardContent>
          </Card>
          {historicalBacktestQuery.data && !historicalBacktestQuery.isFetching ? (
            <BacktestResults result={historicalBacktestQuery.data} />
          ) : null}
          {historicalBacktestQuery.isFetching && selectedHistBacktestId && (
            <div className="flex items-center gap-2 py-4">
              <Loader2 className="size-4 animate-spin" aria-hidden />
              <span className="text-sm text-muted-foreground">Loading backtest details…</span>
            </div>
          )}
        </TabsContent>

        <TabsContent value="signals" className="mt-4 flex flex-col gap-4">
          <div className="flex flex-wrap items-center gap-3">
            <Button size="sm" className="gap-2" disabled={!entryRules || signalsLoading} onClick={runEvaluate}>
              {signalsLoading ? <Loader2 className="size-4 animate-spin" aria-hidden /> : null}
              Evaluate Now
            </Button>
            <span className="text-xs text-muted-foreground">Runs entry rules against current market snapshots</span>
          </div>
          {signals.length > 0 ? (
            <>
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
                {signals.map((sig, i) => (
                  <Card key={i} className="gap-0 border border-border shadow-none ring-0">
                    <CardContent className="py-3">
                      <div className="mb-1 flex justify-between gap-2">
                        {sig.symbol ? (
                          <SymbolLink symbol={sig.symbol} showHeldBadge={false} />
                        ) : (
                          <span className="text-sm text-muted-foreground">—</span>
                        )}
                        <Badge
                          variant="outline"
                          className={cn(
                            'h-5 text-[10px]',
                            sig.action === 'buy'
                              ? 'border-emerald-500/40 bg-emerald-500/10'
                              : 'border-red-500/40 bg-red-500/10',
                          )}
                        >
                          {sig.action}
                        </Badge>
                      </div>
                      <p className="text-xs text-muted-foreground">Strength: {String(sig.strength ?? '—')}</p>
                      {(sig.regime_state || sig.regime_multiplier != null) && (
                        <div className="mt-1 flex flex-wrap gap-2 text-xs text-muted-foreground">
                          {sig.regime_state && (
                            <span>Regime: <span className="font-medium text-foreground">{sig.regime_state}</span></span>
                          )}
                          {sig.regime_multiplier != null && (
                            <span>Multiplier: <span className="font-medium text-foreground">{sig.regime_multiplier}×</span></span>
                          )}
                        </div>
                      )}
                      {sig.context?.sub_results?.length ? (
                        <ul className="mt-2 space-y-0.5">
                          {sig.context.sub_results.map((r, j) => (
                            <li key={j} className="flex items-start gap-1.5 text-xs">
                              {r.passed ? (
                                <Check className="mt-0.5 size-3 shrink-0 text-emerald-500" aria-hidden />
                              ) : (
                                <XIcon className="mt-0.5 size-3 shrink-0 text-destructive" aria-hidden />
                              )}
                              <span className={r.passed ? 'text-foreground' : 'text-muted-foreground'}>
                                {r.rule}
                                {r.threshold != null && r.actual_value != null && (
                                  <span className="text-muted-foreground"> (actual: {r.actual_value})</span>
                                )}
                              </span>
                            </li>
                          ))}
                        </ul>
                      ) : null}
                      {sig.symbol && (
                        <Link
                          to={`/market/tracked?symbols=${sig.symbol}`}
                          className="mt-2 inline-flex items-center gap-1 text-xs text-primary hover:underline"
                        >
                          Open in Table
                          <ExternalLink className="size-3" aria-hidden />
                        </Link>
                      )}
                    </CardContent>
                  </Card>
                ))}
              </div>
              {evaluateSummary && (
                <Card className="gap-0 border border-border shadow-none ring-0">
                  <CardContent className="flex flex-wrap items-center justify-between gap-3 py-3">
                    <span className="text-sm text-muted-foreground">
                      Scanned{' '}
                      <span className="font-semibold text-foreground">{evaluateSummary.universe_scanned}</span>{' '}
                      symbols,{' '}
                      <span className="font-semibold text-foreground">{evaluateSummary.matches}</span> matches
                      {evaluateSummary.universe_scanned > 0 && (
                        <> ({((evaluateSummary.matches / evaluateSummary.universe_scanned) * 100).toFixed(1)}%)</>
                      )}
                    </span>
                    <Button
                      size="sm"
                      variant="outline"
                      className="gap-1"
                      onClick={() => {
                        const symbols = Array.from(
                          new Set(signals.map((s) => s.symbol).filter(Boolean))
                        );
                        if (symbols.length === 0) return;
                        const params = new URLSearchParams({
                          symbols: symbols.join(','),
                          limit: String(symbols.length),
                        });
                        navigate(`/market/tracked?${params.toString()}`);
                      }}
                    >
                      <ExternalLink className="size-3.5" aria-hidden />
                      View all matches in Market Table
                    </Button>
                  </CardContent>
                </Card>
              )}
            </>
          ) : (
            <p className="text-sm text-muted-foreground">
              {signalsLoading
                ? 'Evaluating…'
                : 'No signals yet. Click "Evaluate Now" to scan the market.'}
            </p>
          )}
        </TabsContent>
      </Tabs>
      <ChartSlidePanel symbol={chartSymbol} onClose={() => setChartSymbol(null)} />
    </Page>
    </ChartContext.Provider>
  );
}

function InfoCard({ label, value }: { label: string; value: string }) {
  return (
    <Card className="gap-0 border border-border shadow-none ring-0">
      <CardContent className="py-3">
        <p className="text-xs text-muted-foreground">{label}</p>
        <p className="text-base font-semibold text-foreground">{value}</p>
      </CardContent>
    </Card>
  );
}
