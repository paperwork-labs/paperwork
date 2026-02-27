import React from 'react';
import { Box, Badge, Button, HStack, Text } from '@chakra-ui/react';
import toast from 'react-hot-toast';
import api from '../../services/api';

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
  const [advancedOpen, setAdvancedOpen] = React.useState(false);
  const [snapshotHistoryPeriod, setSnapshotHistoryPeriod] = React.useState<
    '6mo' | '1y' | '2y' | '5y' | 'max'
  >('1y');
  const [sinceDate, setSinceDate] = React.useState('2021-01-01');
  const [sinceDateTouched, setSinceDateTouched] = React.useState(false);
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
        market_indices_constituents_refresh: {
          method: 'POST',
          endpoint: '/market-data/indices/constituents/refresh',
        },
        market_universe_tracked_refresh: {
          method: 'POST',
          endpoint: '/market-data/universe/tracked/refresh',
        },
        admin_indicators_recompute_universe: {
          method: 'POST',
          endpoint: '/market-data/admin/indicators/recompute-universe',
        },
        admin_snapshots_history_record: {
          method: 'POST',
          endpoint: '/market-data/admin/snapshots/history/record',
        },
        admin_fundamentals_fill_missing: {
          method: 'POST',
          endpoint: '/market-data/admin/fundamentals/fill-missing',
        },
        admin_stage_repair: {
          method: 'POST',
          endpoint: '/market-data/admin/stage/repair',
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
      if (!dailyOk) { toast.error('Failed daily bars for selected period'); return; }
      const indicatorsOk = await runNamedTask('admin_indicators_recompute_universe', 'Recompute indicators');
      if (!indicatorsOk) { toast.error('Failed indicator recompute'); return; }
      const historyOk = await backfillSnapshotHistoryPeriod({ silent: true });
      if (!historyOk) { toast.error('Failed snapshot history'); return; }
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
      await api.post(`/market-data/admin/backfill/daily/since-date?since_date=${encodeURIComponent(sinceDate)}&batch_size=25`);
      toast.success(`Queued daily backfill since ${sinceDate}`);
      void refreshHealth();
    } catch (err) {
      handleError(err, 'Failed to queue daily backfill since date');
    }
  };

  const backfillSnapshotHistorySinceDate = async () => {
    try {
      await api.post(`/market-data/admin/backfill/snapshots/history?days=3000&since_date=${encodeURIComponent(sinceDate)}`);
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
    <Box mt={4} display="flex" flexDirection="column" gap={2}>
      {/* Safe actions */}
      <Text fontSize="sm" fontWeight="semibold">Safe Actions</Text>
      <Box display="flex" gap={2} flexWrap="wrap">
        <Button size="sm" variant="outline" loading={state.refreshingCoverage} onClick={() => void refreshCoverageNow()}>
          Refresh Coverage
        </Button>
        <Button size="sm" variant="outline" loading={state.sanityLoading} onClick={() => void runSanityCheck()}>
          Sanity Check (DB)
        </Button>
        <Button size="sm" variant="outline" onClick={() => void runNamedTask('market_indices_constituents_refresh', 'Refresh constituents')}>
          Refresh Constituents
        </Button>
        <Button size="sm" variant="outline" onClick={() => void runNamedTask('market_universe_tracked_refresh', 'Update tracked')}>
          Update Tracked
        </Button>
        <Button size="sm" variant="outline" loading={state.sendingDiscord} onClick={() => void sendSnapshotDigestToDiscord()}>
          Send Snapshot Digest to Discord
        </Button>
      </Box>

      {benchmarkBad ? (
        <Text fontSize="xs" color="status.danger">
          SPY history is missing. Stage/RS cannot be computed until daily bars are backfilled.
        </Text>
      ) : null}

      {/* Backfill actions */}
      <Text fontSize="sm" fontWeight="semibold" mt={2}>Backfill Actions</Text>
      <Box display="flex" gap={2} flexWrap="wrap">
        <Button colorScheme="brand" size="sm" loading={state.restoringDaily} onClick={() => void restoreDailyCoverageTracked()}>
          Backfill Daily Coverage (Tracked)
        </Button>
        <Button variant="outline" size="sm" loading={state.backfillingStale} onClick={() => void backfillStaleDailyOnly()}>
          Backfill Daily (Stale Only)
        </Button>
      </Box>

      {/* Advanced / Destructive */}
      <Box mt={2}>
        <Button variant="ghost" size="sm" onClick={() => setAdvancedOpen(!advancedOpen)}>
          {advancedOpen ? 'Hide Advanced' : 'Show Advanced'}
        </Button>
      </Box>
      {advancedOpen ? (
        <Box mt={2} borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={3} bg="bg.muted">
          <Text fontSize="xs" color="fg.muted" mb={2}>
            Advanced controls (use when debugging). These are more granular and may be slower/noisier.
          </Text>
          <Box mt={3} display="grid" gridTemplateColumns={{ base: '1fr', lg: '1.1fr 0.9fr' }} gap={3}>
            <Box borderWidth="1px" borderColor="border.subtle" borderRadius="md" bg="bg.card" px={3} py={2}>
              <Text fontSize="xs" fontWeight="semibold" color="fg.default" mb={2}>Backfill</Text>
              <Text fontSize="xs" color="fg.muted" mb={2}>
                Use "Backfill Daily Coverage" for missing days. Snapshot History backfills are for analytics/backtesting.
              </Text>
              <Box display="flex" flexDirection="column" gap={3}>
                <Box>
                  <Text fontSize="xs" color="fg.muted" mb={1}>Since date</Text>
                  <Box display="flex" gap={2} flexWrap="wrap" alignItems="center">
                    <input
                      type="date"
                      value={sinceDate}
                      onChange={(e) => { setSinceDateTouched(true); setSinceDate(e.target.value); }}
                      style={{
                        fontSize: 12, padding: '6px 8px', borderRadius: 10,
                        border: '1px solid var(--chakra-colors-border-subtle)',
                        background: 'var(--chakra-colors-bg-input)',
                        color: 'var(--chakra-colors-fg-default)',
                      }}
                    />
                    <Button size="xs" variant="outline" onClick={() => void backfillDailySinceDate()}>
                      Backfill Daily Bars (since)
                    </Button>
                    <Button size="xs" variant="outline" onClick={() => void backfillSnapshotHistorySinceDate()}>
                      Backfill Snapshot History (since)
                    </Button>
                  </Box>
                  <Box mt={2} display="flex" flexDirection="column" gap={1}>
                    <Box display="flex" gap={2} flexWrap="wrap" alignItems="center">
                      <Button size="xs" colorScheme="brand" loading={backfillingSinceDate} onClick={() => void backfillSinceDate()}>
                        Backfill Full Flow (since date)
                      </Button>
                    </Box>
                    <Text fontSize="xs" color="fg.muted">
                      1. Fetch OHLCV bars from provider → 2. Compute indicator series (SMA, RSI, MACD, Stage, RS...) → 3. Persist to MarketSnapshotHistory (immutable daily ledger)
                    </Text>
                  </Box>
                </Box>
                <Box>
                  <Text fontSize="xs" color="fg.muted" mb={1}>Period</Text>
                  <Box display="flex" gap={2} flexWrap="wrap" alignItems="center">
                    <select
                      aria-label="Snapshot history period"
                      value={snapshotHistoryPeriod}
                      onChange={(e) => setSnapshotHistoryPeriod(e.target.value as '6mo' | '1y' | '2y' | '5y' | 'max')}
                      style={{
                        fontSize: 12, padding: '6px 8px', borderRadius: 10,
                        border: '1px solid var(--chakra-colors-border-subtle)',
                        background: 'var(--chakra-colors-bg-input)',
                        color: 'var(--chakra-colors-fg-default)',
                      }}
                    >
                      <option value="6mo">6mo (~126d)</option>
                      <option value="1y">1y (~252d)</option>
                      <option value="2y">2y (~504d)</option>
                      <option value="5y">5y (~1260d)</option>
                      <option value="max">max (≤3000d)</option>
                    </select>
                    <Button size="xs" variant="outline" loading={backfillingDailyPeriod} onClick={() => void backfillDailyBarsPeriod()}>
                      Backfill Daily Bars (period)
                    </Button>
                    <Button size="xs" variant="outline" loading={backfillingSnapshotHistory} onClick={() => void backfillSnapshotHistoryPeriod()}>
                      Backfill Snapshot History (period)
                    </Button>
                  </Box>
                  <Box mt={2} display="flex" flexDirection="column" gap={1}>
                    <Box display="flex" gap={2} flexWrap="wrap" alignItems="center">
                      <Button size="xs" colorScheme="brand" loading={backfillingPeriodFlow} onClick={() => void backfillPeriodFlow()}>
                        Backfill Full Flow (period)
                      </Button>
                    </Box>
                    <Text fontSize="xs" color="fg.muted">
                      1. Fetch OHLCV bars from provider → 2. Compute indicator series (SMA, RSI, MACD, Stage, RS...) → 3. Persist to MarketSnapshotHistory (immutable daily ledger)
                    </Text>
                  </Box>
                </Box>
              </Box>
            </Box>

            <Box borderWidth="1px" borderColor="border.subtle" borderRadius="md" bg="bg.card" px={3} py={2}>
              <Box display="flex" alignItems="center" justifyContent="space-between" mb={2}>
                <Text fontSize="xs" fontWeight="semibold" color="fg.default">Maintenance</Text>
                <Badge size="sm" variant="subtle">ops</Badge>
              </Box>
              <Box display="flex" flexDirection="column" gap={2}>
                <Text fontSize="xs" color="fg.muted">Compute</Text>
                <Box display="flex" gap={2} flexWrap="wrap">
                  <Button size="xs" variant="outline" onClick={() => void runNamedTask('admin_indicators_recompute_universe', 'Recompute indicators')}>
                    Recompute Indicators (Market Snapshot)
                  </Button>
                  <Button size="xs" variant="outline" onClick={() => void runNamedTask('admin_snapshots_history_record', 'Record history')}>
                    Record History
                  </Button>
                </Box>
                <Text mt={2} fontSize="xs" color="fg.muted">Maintenance</Text>
                <Box display="flex" gap={2} flexWrap="wrap">
                  <Button size="xs" variant="outline" onClick={() => void runNamedTask('admin_fundamentals_fill_missing', 'Fill missing fundamentals queued')}>
                    Fill Missing Fundamentals
                  </Button>
                  <Button size="xs" variant="outline" onClick={() => void runNamedTask('admin_stage_repair', 'Repair stage history queued')}>
                    Repair Stage History
                  </Button>
                </Box>
                <Text mt={2} fontSize="xs" color="fg.muted">
                  If Stage/RS look empty, run "Recompute Indicators (Market Snapshot)".
                </Text>
              </Box>
            </Box>
          </Box>
        </Box>
      ) : null}
    </Box>
  );
};

export default AdminOperatorActions;
