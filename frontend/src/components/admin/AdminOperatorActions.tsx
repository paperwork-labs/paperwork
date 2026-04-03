import React from 'react';
import { Loader2 } from 'lucide-react';
import toast from 'react-hot-toast';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import api from '../../services/api';
import { defaultHistoryStart } from '../../constants/market';

interface ActionState {
  refreshingCoverage: boolean;
  restoringDaily: boolean;
  backfillingStale: boolean;
  sanityLoading: boolean;
  sendingDiscord: boolean;
}

interface Props {
  refreshCoverage: () => Promise<void>;
  refreshHealth: () => Promise<void>;
  sanityData: Record<string, unknown> | null;
  setSanityData: (d: Record<string, unknown> | null) => void;
}

const controlClass =
  'h-8 min-w-0 rounded-md border border-input bg-background px-2 text-xs shadow-xs outline-none transition-[color,box-shadow] focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 dark:bg-input/30';

const AdminOperatorActions: React.FC<Props> = ({
  refreshCoverage,
  refreshHealth,
  sanityData,
  setSanityData,
}) => {
  const [state, setState] = React.useState<ActionState>({
    refreshingCoverage: false,
    restoringDaily: false,
    backfillingStale: false,
    sanityLoading: false,
    sendingDiscord: false,
  });
  const [snapshotHistoryPeriod, setSnapshotHistoryPeriod] = React.useState<
    '6mo' | '1y' | '2y' | '5y' | 'max'
  >('1y');
  const [sinceDate, setSinceDate] = React.useState(defaultHistoryStart());
  const [, setSinceDateTouched] = React.useState(false);
  const [backfillingDailyPeriod, setBackfillingDailyPeriod] = React.useState(false);
  const [backfillingSnapshotHistory, setBackfillingSnapshotHistory] = React.useState(false);
  const [backfillingSinceDate, setBackfillingSinceDate] = React.useState(false);
  const [backfillingPeriodFlow, setBackfillingPeriodFlow] = React.useState(false);

  const delayedRefresh = () => {
    setTimeout(() => void refreshCoverage(), 1500);
    setTimeout(() => void refreshCoverage(), 4500);
  };

  const handleError = (err: unknown, fallback: string) => {
    const axiosErr = err as { response?: { data?: { detail?: string } }; message?: string } | undefined;
    const msg = axiosErr?.response?.data?.detail || axiosErr?.message || fallback;
    toast.error(msg);
  };

  const refreshCoverageNow = async () => {
    if (state.refreshingCoverage) return;
    setState((s) => ({ ...s, refreshingCoverage: true }));
    try {
      await api.post('/market-data/admin/backfill/coverage/refresh');
      toast.success('Coverage refresh queued');
      delayedRefresh();
      void refreshHealth();
    } catch (err) {
      handleError(err, 'Failed to refresh coverage');
    } finally {
      setState((s) => ({ ...s, refreshingCoverage: false }));
    }
  };

  const restoreDailyCoverageTracked = async () => {
    if (state.restoringDaily) return;
    setState((s) => ({ ...s, restoringDaily: true }));
    try {
      await api.post('/market-data/admin/backfill/coverage');
      toast.success('Daily coverage backfill queued');
      delayedRefresh();
      void refreshHealth();
    } catch (err) {
      handleError(err, 'Failed to queue daily coverage backfill');
    } finally {
      setState((s) => ({ ...s, restoringDaily: false }));
    }
  };

  const backfillStaleDailyOnly = async () => {
    if (state.backfillingStale) return;
    setState((s) => ({ ...s, backfillingStale: true }));
    try {
      const res = await api.post('/market-data/admin/backfill/coverage/stale');
      const staleCandidates = (res?.data as Record<string, number>)?.stale_candidates;
      toast.success(
        typeof staleCandidates === 'number'
          ? `Queued stale-only backfill (${staleCandidates} symbols)`
          : 'Queued stale-only backfill',
      );
      delayedRefresh();
      void refreshHealth();
    } catch (err) {
      handleError(err, 'Failed to backfill stale daily');
    } finally {
      setState((s) => ({ ...s, backfillingStale: false }));
    }
  };

  const runSanityCheck = async () => {
    if (state.sanityLoading) return;
    setState((s) => ({ ...s, sanityLoading: true }));
    try {
      const res = await api.get('/market-data/admin/coverage/sanity');
      const d = (res?.data || {}) as Record<string, unknown>;
      setSanityData(d);
      toast.success(
        `Sanity: daily ${d.latest_daily_date || '—'} ${d.latest_daily_symbol_count || 0}/${d.tracked_total || 0}`,
      );
    } catch (err) {
      handleError(err, 'Sanity check failed');
    } finally {
      setState((s) => ({ ...s, sanityLoading: false }));
    }
  };

  const sendSnapshotDigestToDiscord = async () => {
    if (state.sendingDiscord) return;
    setState((s) => ({ ...s, sendingDiscord: true }));
    try {
      const res = await api.post('/market-data/admin/snapshots/discord-digest');
      const ok = Boolean((res?.data as Record<string, boolean>)?.sent);
      toast.success(ok ? 'Sent snapshot digest to Discord' : 'Discord send attempted (not sent)');
    } catch (err) {
      handleError(err, 'Failed to send digest to Discord');
    } finally {
      setState((s) => ({ ...s, sendingDiscord: false }));
    }
  };

  const runNamedTask = async (taskName: string, label: string): Promise<boolean> => {
    try {
      const taskEndpoints: Record<string, { method: 'GET' | 'POST'; endpoint: string }> = {
        recompute_universe: {
          method: 'POST',
          endpoint: '/market-data/admin/indicators/recompute-universe',
        },
        admin_fundamentals_fill_missing: {
          method: 'POST',
          endpoint: '/market-data/admin/fundamentals/fill-missing',
        },
        admin_stage_repair: {
          method: 'POST',
          endpoint: '/market-data/admin/stage/repair',
        },
        recover_jobs: {
          method: 'POST',
          endpoint: '/market-data/admin/jobs/recover-stale',
        },
        compute_daily: {
          method: 'POST',
          endpoint: '/market-data/admin/regime/compute',
        },
        refresh_constituents: {
          method: 'POST',
          endpoint: '/market-data/indices/constituents/refresh',
        },
      };
      const task = taskEndpoints[taskName];
      if (!task) throw new Error(`Unsupported task: ${taskName}`);
      if (task.method === 'GET') await api.get(task.endpoint);
      else await api.post(task.endpoint);
      toast.success(label);
      void refreshCoverage();
      void refreshHealth();
      return true;
    } catch (err) {
      handleError(err, `Failed to run ${label}`);
      return false;
    }
  };

  const snapshotHistoryDays = (p: string): number => {
    if (p === '6mo') return 126;
    if (p === '1y') return 252;
    if (p === '2y') return 504;
    if (p === '5y') return 1260;
    return 3000;
  };

  const backfillDailyBarsPeriod = async (opts?: { silent?: boolean }): Promise<boolean> => {
    if (backfillingDailyPeriod) return false;
    setBackfillingDailyPeriod(true);
    try {
      const days = snapshotHistoryDays(snapshotHistoryPeriod);
      await api.post(`/market-data/admin/backfill/daily?days=${days}`);
      if (!opts?.silent) {
        toast.success(`Daily bars (${snapshotHistoryPeriod}) queued`);
        delayedRefresh();
        void refreshHealth();
      }
      return true;
    } catch (err) {
      if (!opts?.silent) handleError(err, 'Failed to queue daily bars backfill');
      return false;
    } finally {
      setBackfillingDailyPeriod(false);
    }
  };

  const backfillSnapshotHistoryPeriod = async (opts?: { silent?: boolean }): Promise<boolean> => {
    if (backfillingSnapshotHistory) return false;
    setBackfillingSnapshotHistory(true);
    try {
      const days = snapshotHistoryDays(snapshotHistoryPeriod);
      await api.post(`/market-data/admin/backfill/snapshots/history?days=${days}`);
      if (!opts?.silent) {
        toast.success(`Snapshot history (${snapshotHistoryPeriod}) queued`);
        delayedRefresh();
        void refreshHealth();
      }
      return true;
    } catch (err) {
      if (!opts?.silent) handleError(err, 'Failed to queue snapshot history backfill');
      return false;
    } finally {
      setBackfillingSnapshotHistory(false);
    }
  };

  const backfillPeriodFlow = async () => {
    if (backfillingPeriodFlow) return;
    setBackfillingPeriodFlow(true);
    try {
      const dailyOk = await backfillDailyBarsPeriod({ silent: true });
      if (!dailyOk) {
        toast.error('Failed daily bars for selected period');
        return;
      }
      const indicatorsOk = await runNamedTask('recompute_universe', 'Recompute indicators');
      if (!indicatorsOk) {
        toast.error('Failed indicator recompute');
        return;
      }
      const historyOk = await backfillSnapshotHistoryPeriod({ silent: true });
      if (!historyOk) {
        toast.error('Failed snapshot history');
        return;
      }
      toast.success(`Queued full backfill flow (${snapshotHistoryPeriod})`);
      delayedRefresh();
      void refreshHealth();
    } catch (err) {
      handleError(err, 'Failed to queue full backfill flow');
    } finally {
      setBackfillingPeriodFlow(false);
    }
  };

  const backfillDailySinceDate = async () => {
    try {
      await api.post(
        `/market-data/admin/backfill/daily/since-date?since_date=${encodeURIComponent(sinceDate)}&batch_size=25`,
      );
      toast.success(`Queued daily backfill since ${sinceDate}`);
      void refreshHealth();
    } catch (err) {
      handleError(err, 'Failed to queue daily backfill since date');
    }
  };

  const backfillSnapshotHistorySinceDate = async () => {
    try {
      await api.post(
        `/market-data/admin/backfill/snapshots/history?days=3000&since_date=${encodeURIComponent(sinceDate)}`,
      );
      toast.success(`Queued snapshot history backfill since ${sinceDate}`);
      void refreshHealth();
    } catch (err) {
      handleError(err, 'Failed to queue snapshot history backfill since date');
    }
  };

  const backfillSinceDate = async () => {
    if (backfillingSinceDate) return;
    setBackfillingSinceDate(true);
    try {
      await api.post(`/market-data/admin/backfill/since-date?since_date=${encodeURIComponent(sinceDate)}`);
      toast.success(`Backfill since ${sinceDate} queued (daily → indicators → snapshot history)`);
      delayedRefresh();
      void refreshHealth();
    } catch (err) {
      handleError(err, 'Failed to queue backfill since date');
    } finally {
      setBackfillingSinceDate(false);
    }
  };

  const benchmarkBad = sanityData?.benchmark && (sanityData.benchmark as Record<string, unknown>)?.ok === false;

  return (
    <div className="mt-4 flex flex-col gap-2">
      <p className="text-sm font-semibold">Safe Actions</p>
      <div className="flex flex-wrap gap-2">
        <Button
          size="sm"
          variant="outline"
          disabled={state.refreshingCoverage}
          onClick={() => void refreshCoverageNow()}
          className="inline-flex gap-1.5"
        >
          {state.refreshingCoverage ? <Loader2 className="size-3.5 shrink-0 animate-spin" aria-hidden /> : null}
          Refresh Coverage
        </Button>
        <Button
          size="sm"
          variant="outline"
          disabled={state.sanityLoading}
          onClick={() => void runSanityCheck()}
          className="inline-flex gap-1.5"
        >
          {state.sanityLoading ? <Loader2 className="size-3.5 shrink-0 animate-spin" aria-hidden /> : null}
          Sanity Check (DB)
        </Button>
        <Button
          size="sm"
          variant="outline"
          disabled={state.sendingDiscord}
          onClick={() => void sendSnapshotDigestToDiscord()}
          className="inline-flex gap-1.5"
        >
          {state.sendingDiscord ? <Loader2 className="size-3.5 shrink-0 animate-spin" aria-hidden /> : null}
          Send Snapshot Digest to Discord
        </Button>
        <Button size="sm" variant="outline" onClick={() => void runNamedTask('compute_daily', 'Compute regime')}>
          Compute Market Regime
        </Button>
      </div>

      {benchmarkBad ? (
        <p className="text-xs text-[rgb(var(--status-danger)/1)]">
          SPY history is missing. Stage/RS cannot be computed until daily bars are backfilled.
        </p>
      ) : null}

      <p className="mt-2 text-sm font-semibold">Backfill Actions</p>
      <div className="flex flex-wrap gap-2">
        <Button
          size="sm"
          disabled={state.restoringDaily}
          onClick={() => void restoreDailyCoverageTracked()}
          className="inline-flex gap-1.5"
        >
          {state.restoringDaily ? <Loader2 className="size-3.5 shrink-0 animate-spin" aria-hidden /> : null}
          Backfill Daily Coverage (Tracked)
        </Button>
        <Button
          size="sm"
          variant="outline"
          disabled={state.backfillingStale}
          onClick={() => void backfillStaleDailyOnly()}
          className="inline-flex gap-1.5"
        >
          {state.backfillingStale ? <Loader2 className="size-3.5 shrink-0 animate-spin" aria-hidden /> : null}
          Backfill Daily (Stale Only)
        </Button>
      </div>

      <p className="mt-2 text-sm font-semibold">Advanced Controls</p>
      <div className="mt-2 rounded-lg border border-border bg-muted/50 p-3">
        <p className="mb-2 text-xs text-muted-foreground">
          Granular controls for debugging and maintenance. These are typically handled by automated agents.
        </p>
        <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-[1.1fr_0.9fr]">
          <div className="rounded-md border border-border bg-card px-3 py-2">
            <p className="mb-2 text-xs font-semibold text-foreground">Backfill</p>
            <p className="mb-2 text-xs text-muted-foreground">
              Use &quot;Backfill Daily Coverage&quot; for missing days. Snapshot History backfills are for analytics/backtesting.
            </p>
            <div className="flex flex-col gap-3">
              <div>
                <p className="mb-1 text-xs text-muted-foreground">Since date</p>
                <div className="flex flex-wrap items-center gap-2">
                  <Input
                    type="date"
                    value={sinceDate}
                    onChange={(e) => {
                      setSinceDateTouched(true);
                      setSinceDate(e.target.value);
                    }}
                    className={cn(controlClass, 'w-auto min-w-[9.5rem]')}
                  />
                  <Button size="xs" variant="outline" onClick={() => void backfillDailySinceDate()}>
                    Backfill Daily Bars (since)
                  </Button>
                  <Button size="xs" variant="outline" onClick={() => void backfillSnapshotHistorySinceDate()}>
                    Backfill Snapshot History (since)
                  </Button>
                </div>
                <div className="mt-2 flex flex-col gap-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <Button
                      size="xs"
                      disabled={backfillingSinceDate}
                      onClick={() => void backfillSinceDate()}
                      className="inline-flex gap-1.5"
                    >
                      {backfillingSinceDate ? <Loader2 className="size-3 shrink-0 animate-spin" aria-hidden /> : null}
                      Backfill Full Flow (since date)
                    </Button>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    1. Fetch OHLCV bars from provider → 2. Compute indicator series (SMA, RSI, MACD, Stage, RS...) → 3.
                    Persist to MarketSnapshotHistory (immutable daily ledger)
                  </p>
                </div>
              </div>
              <div>
                <p className="mb-1 text-xs text-muted-foreground">Period</p>
                <div className="flex flex-wrap items-center gap-2">
                  <select
                    aria-label="Snapshot history period"
                    value={snapshotHistoryPeriod}
                    onChange={(e) =>
                      setSnapshotHistoryPeriod(e.target.value as '6mo' | '1y' | '2y' | '5y' | 'max')
                    }
                    className={cn(controlClass, 'min-w-[8.5rem]')}
                  >
                    <option value="6mo">6mo (~126d)</option>
                    <option value="1y">1y (~252d)</option>
                    <option value="2y">2y (~504d)</option>
                    <option value="5y">5y (~1260d)</option>
                    <option value="max">max (≤3000d)</option>
                  </select>
                  <Button
                    size="xs"
                    variant="outline"
                    disabled={backfillingDailyPeriod}
                    onClick={() => void backfillDailyBarsPeriod()}
                    className="inline-flex gap-1.5"
                  >
                    {backfillingDailyPeriod ? <Loader2 className="size-3 shrink-0 animate-spin" aria-hidden /> : null}
                    Backfill Daily Bars (period)
                  </Button>
                  <Button
                    size="xs"
                    variant="outline"
                    disabled={backfillingSnapshotHistory}
                    onClick={() => void backfillSnapshotHistoryPeriod()}
                    className="inline-flex gap-1.5"
                  >
                    {backfillingSnapshotHistory ? (
                      <Loader2 className="size-3 shrink-0 animate-spin" aria-hidden />
                    ) : null}
                    Backfill Snapshot History (period)
                  </Button>
                </div>
                <div className="mt-2 flex flex-col gap-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <Button
                      size="xs"
                      disabled={backfillingPeriodFlow}
                      onClick={() => void backfillPeriodFlow()}
                      className="inline-flex gap-1.5"
                    >
                      {backfillingPeriodFlow ? <Loader2 className="size-3 shrink-0 animate-spin" aria-hidden /> : null}
                      Backfill Full Flow (period)
                    </Button>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    1. Fetch OHLCV bars from provider → 2. Compute indicator series (SMA, RSI, MACD, Stage, RS...) → 3.
                    Persist to MarketSnapshotHistory (immutable daily ledger)
                  </p>
                </div>
              </div>
            </div>
          </div>

          <div className="rounded-md border border-border bg-card px-3 py-2">
            <div className="mb-2 flex items-center justify-between">
              <p className="text-xs font-semibold text-foreground">Maintenance</p>
              <Badge variant="secondary" className="text-xs">
                ops
              </Badge>
            </div>
            <div className="flex flex-col gap-2">
              <p className="text-xs text-muted-foreground">Compute</p>
              <div className="flex flex-wrap gap-2">
                <Button
                  size="xs"
                  variant="outline"
                  onClick={() => void runNamedTask('recompute_universe', 'Recompute indicators')}
                >
                  Recompute Indicators (Market Snapshot)
                </Button>
              </div>
              <p className="mt-2 text-xs text-muted-foreground">Maintenance</p>
              <div className="flex flex-wrap gap-2">
                <Button
                  size="xs"
                  variant="outline"
                  onClick={() =>
                    void runNamedTask('refresh_constituents', 'Index constituents refresh queued')
                  }
                >
                  Refresh Index Constituents
                </Button>
                <Button
                  size="xs"
                  variant="outline"
                  onClick={() =>
                    void runNamedTask('admin_fundamentals_fill_missing', 'Fill missing fundamentals queued')
                  }
                >
                  Fill Missing Fundamentals
                </Button>
                <Button
                  size="xs"
                  variant="outline"
                  onClick={() => void runNamedTask('admin_stage_repair', 'Repair stage history completed')}
                >
                  Repair Stage History
                </Button>
                <Button
                  size="xs"
                  variant="outline"
                  onClick={() => void runNamedTask('recover_jobs', 'Stale jobs recovered')}
                >
                  Recover Stale Jobs
                </Button>
              </div>
              <p className="mt-2 text-xs text-muted-foreground">
                If Stage/RS look empty, run &quot;Recompute Indicators (Market Snapshot)&quot;. If jobs list shows many
                &quot;running&quot;, run &quot;Recover Stale Jobs&quot;.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AdminOperatorActions;
