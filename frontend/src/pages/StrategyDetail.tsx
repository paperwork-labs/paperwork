import React, { useEffect, useState, useCallback } from 'react';
import { ArrowLeft, Edit2, Loader2, Pause, Play, Save } from 'lucide-react';
import { useParams, useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import { Page, PageHeader } from '../components/ui/Page';
import { EntryExitRules } from '../components/strategy/RuleDisplay';
import BacktestResults from '../components/strategy/BacktestResults';
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

  const [signals, setSignals] = useState<Array<{ symbol?: string; action?: string; strength?: unknown }>>([]);
  const [signalsLoading, setSignalsLoading] = useState(false);

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
      const data = extractData<{ signals: Array<{ symbol?: string; action?: string; strength?: unknown }> }>(resp);
      setSignals(data?.signals ?? []);
    } catch {
      toast.error('Evaluation failed');
    } finally {
      setSignalsLoading(false);
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
        <Button className="mt-4" onClick={() => navigate('/strategies')}>
          Back to Strategies
        </Button>
      </Page>
    );
  }

  const params = strategy.parameters ?? {};
  const entryRules = params.entry_rules as ConditionGroupData | undefined;
  const exitRules = params.exit_rules as ConditionGroupData | undefined;

  return (
    <Page>
      <div className="mb-4">
        <Button size="sm" variant="ghost" className="gap-1" onClick={() => navigate('/strategies')}>
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
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
              {signals.map((sig, i) => (
                <Card key={i} className="gap-0 border border-border shadow-none ring-0">
                  <CardContent className="py-3">
                    <div className="mb-1 flex justify-between gap-2">
                      <span className="font-semibold">{sig.symbol}</span>
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
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              {signalsLoading
                ? 'Evaluating...'
                : 'No signals yet. Click "Evaluate Now" to scan the market.'}
            </p>
          )}
        </TabsContent>
      </Tabs>
    </Page>
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
