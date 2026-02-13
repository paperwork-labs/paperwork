import React from 'react';
import {
  Box,
  Heading,
  Button,
  Text,
  HStack,
  Badge,
  Tooltip,
} from '@chakra-ui/react';
import toast from 'react-hot-toast';
import api from '../services/api';
import useCoverageSnapshot from '../hooks/useCoverageSnapshot';
import { useUserPreferences } from '../hooks/useUserPreferences';
import { formatDateTime } from '../utils/format';
import { authApi, appSettingsApi, handleApiError } from '../services/api';
import { useAuthOptional } from '../context/AuthContext';
import {
  CoverageBucketsGrid,
  CoverageKpiGrid,
  CoverageSummaryCard,
  CoverageTrendGrid,
} from '../components/coverage/CoverageSummaryCard';

const AdminDashboard: React.FC = () => {
  const auth = useAuthOptional();
  const user = auth?.user ?? null;
  const refreshMe = auth?.refreshMe;
  const appSettings = auth?.appSettings;
  const refreshAppSettings = auth?.refreshAppSettings;
  const { timezone, coverageHistogramWindowDays } = useUserPreferences();
  const [backfill5mEnabled, setBackfill5mEnabled] = React.useState<boolean>(true);
  const [toggling5m, setToggling5m] = React.useState<boolean>(false);
  const [marketOnlyMode, setMarketOnlyMode] = React.useState<boolean>(true);
  const [portfolioEnabled, setPortfolioEnabled] = React.useState<boolean>(false);
  const [strategyEnabled, setStrategyEnabled] = React.useState<boolean>(false);
  const [togglingMarketOnly, setTogglingMarketOnly] = React.useState<boolean>(false);
  const [refreshingCoverage, setRefreshingCoverage] = React.useState<boolean>(false);
  const [restoringDaily, setRestoringDaily] = React.useState<boolean>(false);
  const [backfillingStale, setBackfillingStale] = React.useState<boolean>(false);
  const [backfillingSnapshotHistory, setBackfillingSnapshotHistory] = React.useState<boolean>(false);
  const [backfillingDailyPeriod, setBackfillingDailyPeriod] = React.useState<boolean>(false);
  const [backfillingSinceDate, setBackfillingSinceDate] = React.useState<boolean>(false);
  const [backfillingPeriodFlow, setBackfillingPeriodFlow] = React.useState<boolean>(false);
  const [snapshotHistoryPeriod, setSnapshotHistoryPeriod] = React.useState<'6mo' | '1y' | '2y' | '5y' | 'max'>('1y');
  const [advancedOpen, setAdvancedOpen] = React.useState<boolean>(false);
  const [sendingDiscord, setSendingDiscord] = React.useState<boolean>(false);
  const [sanityLoading, setSanityLoading] = React.useState<boolean>(false);
  const [sanityData, setSanityData] = React.useState<any | null>(null);
  const [taskStatus, setTaskStatus] = React.useState<Record<string, any> | null>(null);
  const [stageQuality, setStageQuality] = React.useState<any | null>(null);
  const [jobsSummary, setJobsSummary] = React.useState<any | null>(null);
  const [marketAudit, setMarketAudit] = React.useState<any | null>(null);
  const [histWindowDays, setHistWindowDays] = React.useState<number>(
    coverageHistogramWindowDays || 50,
  );
  const [sinceDate, setSinceDate] = React.useState<string>('2021-01-01');
  const [sinceDateTouched, setSinceDateTouched] = React.useState<boolean>(false);
  const fillLookbackDays = React.useMemo(() => Math.max(90, histWindowDays * 3), [histWindowDays]);
  const { snapshot: coverage, refresh: refreshCoverage, sparkline, kpis, actions: coverageActions, hero } = useCoverageSnapshot({
    fillTradingDaysWindow: histWindowDays,
    fillLookbackDays,
  });
  const benchmark = (coverage as any)?.meta?.benchmark ?? sanityData?.benchmark;
  const benchmarkStale = benchmark && benchmark.ok === false;
  const benchmarkLatest = benchmark?.latest_daily_date;
  const autoRefreshAttemptedRef = React.useRef(false);

  React.useEffect(() => {
    // Preference wins; otherwise fall back to backend-provided default window.
    if (coverageHistogramWindowDays && coverageHistogramWindowDays !== histWindowDays) {
      setHistWindowDays(coverageHistogramWindowDays);
      return;
    }
    if (!coverageHistogramWindowDays) {
      const backendDefault = Number((coverage as any)?.meta?.fill_trading_days_window ?? NaN);
      if (Number.isFinite(backendDefault) && backendDefault > 0 && backendDefault !== histWindowDays) {
        setHistWindowDays(backendDefault);
      }
    }
  }, [coverageHistogramWindowDays, (coverage as any)?.meta?.fill_trading_days_window]);

  const saveHistogramWindowPref = async (next: number) => {
    try {
      if (!user || typeof refreshMe !== 'function') return;
      const existing = (user?.ui_preferences && typeof user.ui_preferences === 'object') ? user.ui_preferences : {};
      await authApi.updateMe({
        ui_preferences: {
          ...existing,
          coverage_histogram_window_days: next,
        },
      });
      await refreshMe();
    } catch (e) {
      toast.error(handleApiError(e));
    }
  };

  React.useEffect(() => {
    if (coverage?.meta?.backfill_5m_enabled !== undefined) {
      setBackfill5mEnabled(Boolean(coverage.meta.backfill_5m_enabled));
    }
  }, [coverage]);

  React.useEffect(() => {
    if (appSettings?.market_only_mode !== undefined) {
      setMarketOnlyMode(Boolean(appSettings.market_only_mode));
    }
    if (appSettings?.portfolio_enabled !== undefined) {
      setPortfolioEnabled(Boolean(appSettings.portfolio_enabled));
    }
    if (appSettings?.strategy_enabled !== undefined) {
      setStrategyEnabled(Boolean(appSettings.strategy_enabled));
    }
  }, [appSettings?.market_only_mode, appSettings?.portfolio_enabled, appSettings?.strategy_enabled]);

  const updateReleaseControls = async (patch: { market_only_mode?: boolean; portfolio_enabled?: boolean; strategy_enabled?: boolean }) => {
    if (togglingMarketOnly) return;
    setTogglingMarketOnly(true);
    try {
      const res: any = await appSettingsApi.update(patch);
      setMarketOnlyMode(Boolean(res?.market_only_mode));
      setPortfolioEnabled(Boolean(res?.portfolio_enabled));
      setStrategyEnabled(Boolean(res?.strategy_enabled));
      if (typeof refreshAppSettings === 'function') {
        await refreshAppSettings();
      }
      toast.success('Release controls updated');
    } catch (e) {
      toast.error(handleApiError(e));
    } finally {
      setTogglingMarketOnly(false);
    }
  };

  const toggleMarketOnlyMode = async () => {
    await updateReleaseControls({ market_only_mode: !marketOnlyMode });
  };

  const togglePortfolioEnabled = async () => {
    await updateReleaseControls({ portfolio_enabled: !portfolioEnabled });
  };

  const toggleStrategyEnabled = async () => {
    await updateReleaseControls({ strategy_enabled: !strategyEnabled });
  };

  const loadTaskStatus = async () => {
    try {
      const res = await api.get('/market-data/admin/tasks/status');
      setTaskStatus(res?.data || null);
    } catch {
      setTaskStatus(null);
    }
  };

  const loadStageQuality = async () => {
    try {
      const res = await api.get('/market-data/admin/stage-quality?lookback_days=120');
      setStageQuality(res?.data || null);
    } catch {
      setStageQuality(null);
    }
  };

  const loadJobsSummary = async () => {
    try {
      const res = await api.get('/market-data/admin/jobs/summary?lookback_hours=24');
      setJobsSummary(res?.data || null);
    } catch {
      setJobsSummary(null);
    }
  };

  const loadMarketAudit = async () => {
    try {
      const res = await api.get('/market-data/admin/market-audit');
      setMarketAudit(res?.data?.audit || null);
    } catch {
      setMarketAudit(null);
    }
  };

  React.useEffect(() => {
    void loadTaskStatus();
    void loadStageQuality();
    void loadJobsSummary();
    void loadMarketAudit();
  }, []);

  const refreshCoverageNow = async (origin: 'manual' | 'auto') => {
    if (refreshingCoverage) return;
    setRefreshingCoverage(true);
    try {
      const res = await api.post('/market-data/admin/backfill/coverage/refresh');
      const taskId = res?.data?.task_id;
      toast.success(origin === 'auto' ? 'Coverage refresh queued (auto)' : 'Coverage refresh queued');
      // Task may take a moment; do a couple of lightweight refreshes.
      setTimeout(() => void refreshCoverage(), 1500);
      setTimeout(() => void refreshCoverage(), 4500);
      void taskId;
      void loadTaskStatus();
      void loadStageQuality();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || err?.message || 'Failed to refresh coverage');
    } finally {
      setRefreshingCoverage(false);
    }
  };

  const restoreDailyCoverageTracked = async () => {
    if (restoringDaily) return;
    setRestoringDaily(true);
    try {
      // Guided orchestrator (daily only, tracked universe)
      await api.post('/market-data/admin/backfill/coverage');
      toast.success('Daily coverage backfill queued');
      setTimeout(() => void refreshCoverage(), 1500);
      setTimeout(() => void refreshCoverage(), 4500);
      void loadTaskStatus();
      void loadStageQuality();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || err?.message || 'Failed to queue daily coverage backfill');
    } finally {
      setRestoringDaily(false);
    }
  };

  const backfillStaleDailyOnly = async () => {
    if (backfillingStale) return;
    setBackfillingStale(true);
    try {
      const res = await api.post('/market-data/admin/backfill/coverage/stale');
      const staleCandidates = res?.data?.stale_candidates;
      toast.success(
        typeof staleCandidates === 'number'
          ? `Queued stale-only backfill (${staleCandidates} symbols)`
          : 'Queued stale-only backfill',
      );
      setTimeout(() => void refreshCoverage(), 1500);
      setTimeout(() => void refreshCoverage(), 4500);
      void loadTaskStatus();
      void loadStageQuality();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || err?.message || 'Failed to backfill stale daily');
    } finally {
      setBackfillingStale(false);
    }
  };

  const snapshotHistoryDaysForPeriod = (p: '6mo' | '1y' | '2y' | '5y' | 'max'): number => {
    // Snapshot history backfill is DB-only and uses *trading days*.
    // We keep period labels in UI because that’s what operators think in; map to standard approximations.
    if (p === '6mo') return 126;
    if (p === '1y') return 252;
    if (p === '2y') return 504;
    if (p === '5y') return 1260;
    return 3000; // max (bounded by backend)
  };

  const backfillSnapshotHistoryPeriod = async (options?: { silent?: boolean }): Promise<boolean> => {
    if (backfillingSnapshotHistory) return false;
    setBackfillingSnapshotHistory(true);
    try {
      const days = snapshotHistoryDaysForPeriod(snapshotHistoryPeriod);
      const tracked = Number((coverage as any)?.tracked_count ?? totalSymbols ?? 0) || 0;
      const estimatedRows = tracked ? tracked * days : null;
      await api.post(`/market-data/admin/backfill/snapshots/history?days=${days}`);
      if (!options?.silent) {
        toast.success(
          estimatedRows
            ? `Snapshot history (${snapshotHistoryPeriod}) queued (~${estimatedRows.toLocaleString()} rows). Track progress in Admin → Jobs.`
            : `Snapshot history (${snapshotHistoryPeriod}) queued. Track progress in Admin → Jobs.`,
        );
        setTimeout(() => void refreshCoverage(), 1500);
        setTimeout(() => void refreshCoverage(), 4500);
        void loadTaskStatus();
      }
      return true;
    } catch (err: any) {
      if (!options?.silent) {
        toast.error(err?.response?.data?.detail || err?.message || 'Failed to queue snapshot history backfill');
      }
      return false;
    } finally {
      setBackfillingSnapshotHistory(false);
    }
  };

  const backfillDailyBarsPeriod = async (options?: { silent?: boolean }): Promise<boolean> => {
    if (backfillingDailyPeriod) return false;
    setBackfillingDailyPeriod(true);
    try {
      const days = snapshotHistoryDaysForPeriod(snapshotHistoryPeriod);
      await api.post(`/market-data/admin/backfill/daily?days=${days}`);
      if (!options?.silent) {
        toast.success(`Daily bars (${snapshotHistoryPeriod}) queued. Track progress in Admin → Jobs.`);
        setTimeout(() => void refreshCoverage(), 1500);
        setTimeout(() => void refreshCoverage(), 4500);
        void loadTaskStatus();
      }
      return true;
    } catch (err: any) {
      if (!options?.silent) {
        toast.error(err?.response?.data?.detail || err?.message || 'Failed to queue daily bars backfill');
      }
      return false;
    } finally {
      setBackfillingDailyPeriod(false);
    }
  };

  const backfillPeriodFlow = async () => {
    if (backfillingPeriodFlow) return;
    setBackfillingPeriodFlow(true);
    try {
      const dailyOk = await backfillDailyBarsPeriod({ silent: true });
      if (!dailyOk) {
        toast.error('Failed to queue daily bars for selected period.');
        return;
      }
      const indicatorsOk = await runNamedTask('admin_indicators_recompute_universe', 'Recompute indicators');
      if (!indicatorsOk) {
        toast.error('Failed to queue indicator recompute for selected period.');
        return;
      }
      const historyOk = await backfillSnapshotHistoryPeriod({ silent: true });
      if (!historyOk) {
        toast.error('Failed to queue snapshot history for selected period.');
        return;
      }
      toast.success(`Queued full backfill flow (${snapshotHistoryPeriod}). Track progress in Admin → Jobs.`);
      setTimeout(() => void refreshCoverage(), 1500);
      setTimeout(() => void refreshCoverage(), 4500);
      void loadTaskStatus();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || err?.message || 'Failed to queue full backfill flow');
    } finally {
      setBackfillingPeriodFlow(false);
    }
  };

  const backfillDailySinceDate = async () => {
    try {
      await api.post(`/market-data/admin/backfill/daily/since-date?since_date=${encodeURIComponent(sinceDate)}&batch_size=25`);
      toast.success(`Queued daily backfill since ${sinceDate}`);
      void loadTaskStatus();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || err?.message || 'Failed to queue daily backfill since date');
    }
  };

  const backfillSinceDate = async () => {
    if (backfillingSinceDate) return;
    setBackfillingSinceDate(true);
    try {
      await api.post(`/market-data/admin/backfill/since-date?since_date=${encodeURIComponent(sinceDate)}`);
      toast.success(`Backfill since ${sinceDate} queued (daily → indicators → snapshot history)`);
      setTimeout(() => void refreshCoverage(), 1500);
      setTimeout(() => void refreshCoverage(), 4500);
      void loadTaskStatus();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || err?.message || 'Failed to queue backfill since date');
    } finally {
      setBackfillingSinceDate(false);
    }
  };

  const backfillSnapshotHistorySinceDate = async () => {
    try {
      await api.post(`/market-data/admin/backfill/snapshots/history?days=3000&since_date=${encodeURIComponent(sinceDate)}`);
      toast.success(`Queued snapshot history backfill since ${sinceDate}`);
      void loadTaskStatus();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || err?.message || 'Failed to queue snapshot history backfill since date');
    }
  };

  const runNamedTask = async (taskName: string, label?: string): Promise<boolean> => {
    // Special-case: schedule coverage monitor as an hourly beat entry
    if (taskName === 'schedule_coverage_monitor') {
      try {
        await api.post('/admin/schedules', {
          name: 'admin_coverage_refresh',
          task: 'backend.tasks.market_data_tasks.monitor_coverage_health',
          cron: '0 * * * *',
          timezone: 'UTC',
        });
        toast.success('Coverage monitor scheduled (hourly)');
        await refreshCoverage();
        return true;
      } catch (err: any) {
        toast.error(err?.response?.data?.detail || err?.message || 'Failed to schedule monitor');
      }
      return false;
    }
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
      };
      const task = taskEndpoints[taskName];
      if (!task) {
        throw new Error(`Unsupported task: ${taskName}`);
      }
      await runTaskEndpoint(task.endpoint, task.method);
      toast.success(label || taskName);
      await refreshCoverage();
      void loadTaskStatus();
      return true;
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || err?.message || `Failed to run ${label || taskName}`);
      return false;
    }
  };

  const sendSnapshotDigestToDiscord = async () => {
    if (sendingDiscord) return;
    setSendingDiscord(true);
    try {
      const res = await api.post('/market-data/admin/snapshots/discord-digest');
      const ok = Boolean(res?.data?.sent);
      toast.success(ok ? 'Sent snapshot digest to Discord' : 'Discord send attempted (not sent)');
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || err?.message || 'Failed to send digest to Discord');
    } finally {
      setSendingDiscord(false);
    }
  };

  const runSanityCheck = async () => {
    if (sanityLoading) return;
    setSanityLoading(true);
    try {
      const res = await api.get('/market-data/admin/coverage/sanity');
      const d = res?.data || {};
      setSanityData(d);
      toast.success(
        `Sanity: daily ${d.latest_daily_date || '—'} ${d.latest_daily_symbol_count || 0}/${d.tracked_total || 0}; ` +
        `history ${d.latest_snapshot_history_date || '—'} ${d.latest_snapshot_history_symbol_count || 0}/${d.tracked_total || 0} (${d.latest_snapshot_history_fill_pct || 0}%)`,
      );
    } catch (err: any) {
      const status = Number(err?.response?.status || 0);
      if (status === 404) {
        toast.error('Sanity check endpoint not found. Restart backend: make up');
      } else {
        toast.error(err?.response?.data?.detail || err?.message || 'Sanity check failed');
      }
    } finally {
      setSanityLoading(false);
    }
  };

  const loadSanity = async () => {
    try {
      const res = await api.get('/market-data/admin/coverage/sanity');
      setSanityData(res?.data || null);
    } catch (err: any) {
      const status = Number(err?.response?.status || 0);
      if (status === 404) {
        toast.error('Sanity check endpoint not found. Restart backend: make up');
      }
    }
  };

  const toggleBackfill5m = async () => {
    if (toggling5m) return;
    setToggling5m(true);
    const next = !backfill5mEnabled;
    try {
      const res = await api.post('/market-data/admin/backfill/5m/toggle', { enabled: next });
      const flag = res?.data?.backfill_5m_enabled ?? next;
      setBackfill5mEnabled(Boolean(flag));
      toast.success(`5m backfill ${flag ? 'enabled' : 'disabled'}`);
      await refreshCoverage();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || err?.message || 'Failed to update 5m backfill toggle');
    } finally {
      setToggling5m(false);
    }
  };

  // Auto-trigger coverage monitor when cache is missing/stale.
  React.useEffect(() => {
    if (!coverage || autoRefreshAttemptedRef.current) return;
    const age = Number(coverage?.meta?.snapshot_age_seconds ?? NaN);
    const source = String(coverage?.meta?.source || '');
    const stale = !Number.isFinite(age) || age > 15 * 60 || source !== 'cache';
    if (stale) {
      autoRefreshAttemptedRef.current = true;
      void refreshCoverageNow('auto');
    }
  }, [coverage]);

  React.useEffect(() => {
    void loadSanity();
  }, []);

  const fmtLastRun = (key: string) => {
    const raw = (taskStatus || {})[key];
    const ts = raw?.ts;
    return formatDateTime(ts, timezone);
  };

  const runTaskEndpoint = async (endpoint: string, method: 'GET' | 'POST' = 'POST') => {
    if (method === 'GET') return api.get(endpoint);
    return api.post(endpoint);
  };

  const dailyFillSeries = (coverage as any)?.daily?.fill_by_date as
    | Array<{ date: string; symbol_count: number; pct_of_universe: number }>
    | undefined;
  const snapshotFillSeries = (coverage as any)?.daily?.snapshot_fill_by_date as
    | Array<{ date: string; symbol_count: number; pct_of_universe: number }>
    | undefined;

  const totalSymbols = Number((coverage as any)?.symbols ?? (coverage as any)?.tracked_count ?? 0);

  const lastGreenSnapshotDate = React.useMemo(() => {
    const rows = (snapshotFillSeries || [])
      .filter((r) => r && r.date)
      .map((r) => ({
        date: String(r.date).slice(0, 10),
        pct: Number(r.pct_of_universe || 0),
      }))
      .filter((r) => r.pct >= 95);
    if (!rows.length) return null;
    rows.sort((a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : 0));
    return rows[0].date;
  }, [snapshotFillSeries]);

  React.useEffect(() => {
    if (sinceDateTouched) return;
    if (!lastGreenSnapshotDate) return;
    if (sinceDate === '2021-01-01' || !sinceDate) {
      setSinceDate(lastGreenSnapshotDate);
    }
  }, [lastGreenSnapshotDate, sinceDateTouched]);

  const dailyFillDist = React.useMemo(() => {
    const rows = (dailyFillSeries || [])
      .filter((r) => r && r.date)
      .slice()
      .sort((a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : 0)); // newest-first
    const newestDate = rows.length ? rows[0].date : null;
    const newestCount = rows.length ? Number(rows[0].symbol_count || 0) : 0;
    const newestPct = rows.length ? Number(rows[0].pct_of_universe || 0) : 0;
    return { newestDate, newestCount, newestPct, total: totalSymbols || 0, rows };
  }, [dailyFillSeries, totalSymbols]);

  const heroEffective = React.useMemo(() => {
    if (!hero) return hero;
    // When 5m is disabled, suppress noisy “missing 5m data” messaging in the hero.
    if (!backfill5mEnabled && hero?.staleCounts?.daily === 0 && hero?.staleCounts?.m5 > 0) {
      return {
        ...hero,
        summary: '5m is disabled (ignored for status).',
      };
    }
    return hero;
  }, [hero, backfill5mEnabled]);

  const dailyHistogram = React.useMemo(() => {
    const { rows, newestDate, total } = dailyFillDist;
    if (!rows.length || !newestDate || !total) return null;

    const normDateKey = (d: any) => {
      if (!d) return '';
      // Be resilient to backend variations (date vs datetime strings).
      // We only care about the YYYY-MM-DD part for histogram alignment.
      const s = String(d);
      return s.length >= 10 ? s.slice(0, 10) : s;
    };

    const pctFor = (row: { pct_of_universe: number }) => Number(row?.pct_of_universe || 0);
    const colorForPct = (pct: number) => {
      // HSL: red(0) -> green(120), driven by % (height)
      const t = Math.max(0, Math.min(1, pct / 100));
      const hue = 0 + 120 * t;
      return `hsl(${hue}, 70%, 45%)`;
    };

    const barMaxH = 40;
    const markerH = 12; // snapshot marker strip + spacing below bar
    const fillMap = new Map(rows.map((r) => [normDateKey(r.date), r]));
    const snapshotPctByDate = new Map(
      (snapshotFillSeries || []).map((r) => [normDateKey(r.date), Number(r.pct_of_universe || 0)]),
    );

    // Trading-day series: use the last N observed dates in fill_by_date.
    // This naturally excludes weekends/holidays (no OHLCV rows expected) and avoids confusing gaps.
    const windowDays = Math.max(
      1,
      Number((coverage as any)?.meta?.fill_trading_days_window ?? 50),
    );
    const bars: Array<{ date: string; symbol_count: number; pct_of_universe: number }> = rows
      .slice() // newest-first
      .reverse() // oldest-first
      .slice(-windowDays) // keep last N trading days
      .map((r) => ({
        date: normDateKey(r.date),
        symbol_count: Number(r.symbol_count || 0),
        pct_of_universe: Number(r.pct_of_universe || 0),
      }));

    return (
      <Box mt={2}>
        <Box
          borderRadius="md"
          borderWidth="1px"
          borderColor="border.subtle"
          bg="bg.card"
          px={2}
          py={2}
          overflowX="auto"
          overflowY="hidden"
        >
          <HStack align="end" gap={1} h={`${barMaxH + markerH}px`} w="full">
            {bars.map((r) => {
              const pct = pctFor(r);
              const h = Math.max(2, Math.round((pct / 100) * barMaxH));
              const snapPct = snapshotPctByDate.get(normDateKey(r.date));
              const snapOk = typeof snapPct === 'number' && snapPct >= 95;
              const snapNone = typeof snapPct !== 'number';
              // Snapshot marker thresholds: green = basically complete, orange = partial,
              // red = low coverage, gray = no snapshot run recorded.
              const markerBg =
                snapNone
                  ? 'gray.400'
                  : snapOk
                    ? 'green.500'
                    : (snapPct || 0) >= 50
                      ? 'orange.500'
                      : 'red.500';
              return (
                <Box
                  key={r.date}
                  flex="1 0 0"
                  minW="6px"
                  title={`${r.date}: ${r.symbol_count}/${total} (${Math.round(pct * 10) / 10}%)`}
                >
                  <Box w="full" h={`${h}px`} borderRadius="sm" bg={colorForPct(pct)} />
                  <Box
                    mt="3px"
                    mx="auto"
                    w="80%"
                    h="5px"
                    borderRadius="999px"
                    bg={markerBg}
                    borderWidth="1px"
                    borderColor="bg.card"
                    opacity={snapNone ? 0.65 : 1}
                    title={
                      snapNone
                        ? `${r.date}: snapshots —`
                        : `${r.date}: snapshots ${Math.round((snapPct || 0) * 10) / 10}%`
                    }
                  />
                </Box>
              );
            })}
          </HStack>
        </Box>
        <Text mt={1} fontSize="xs" color="fg.muted">
          Histogram bars (daily, last {windowDays} trading days): height + color represent % of symbols with a stored 1d OHLCV bar on that date.
          Marker strip under each bar indicates technical snapshot coverage for that date (green ≥95%, orange ≥50%, red &lt;50%, gray = no snapshot run recorded).
        </Text>
      </Box>
    );
  }, [dailyFillDist, snapshotFillSeries]);

  return (
    <Box p={4}>
      <Heading size="md" mb={4}>Admin Dashboard</Heading>

      {coverage && (
        <CoverageSummaryCard hero={heroEffective} status={coverage.status} showUpdated={false}>
          <Box mb={3} borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={3} bg="bg.muted">
            <Text fontSize="sm" fontWeight="semibold" color="fg.default" mb={1}>
              Release Controls
            </Text>
            <Text fontSize="xs" color="fg.muted" mb={3}>
              Keep market-only enabled while building. Disable market-only and enable sections when ready.
            </Text>
            <HStack justify="space-between" align="center" flexWrap="wrap" gap={3} mb={2}>
              <Text fontSize="sm">Market-only mode</Text>
              <HStack gap={2}>
                <Badge colorScheme={marketOnlyMode ? 'green' : 'gray'} variant="subtle">
                  {marketOnlyMode ? 'ON' : 'OFF'}
                </Badge>
                <Button size="xs" variant="outline" loading={togglingMarketOnly} onClick={toggleMarketOnlyMode}>
                  {marketOnlyMode ? 'Disable' : 'Enable'}
                </Button>
              </HStack>
            </HStack>
            <HStack justify="space-between" align="center" flexWrap="wrap" gap={3} mb={2}>
              <Text fontSize="sm">Portfolio section</Text>
              <HStack gap={2}>
                <Badge colorScheme={portfolioEnabled ? 'green' : 'gray'} variant="subtle">
                  {portfolioEnabled ? 'ENABLED' : 'DISABLED'}
                </Badge>
                <Button size="xs" variant="outline" loading={togglingMarketOnly} onClick={togglePortfolioEnabled}>
                  {portfolioEnabled ? 'Disable' : 'Enable'}
                </Button>
              </HStack>
            </HStack>
            <HStack justify="space-between" align="center" flexWrap="wrap" gap={3}>
              <Text fontSize="sm">Strategy section</Text>
              <HStack gap={2}>
                <Badge colorScheme={strategyEnabled ? 'green' : 'gray'} variant="subtle">
                  {strategyEnabled ? 'ENABLED' : 'DISABLED'}
                </Badge>
                <Button size="xs" variant="outline" loading={togglingMarketOnly} onClick={toggleStrategyEnabled}>
                  {strategyEnabled ? 'Disable' : 'Enable'}
                </Button>
              </HStack>
            </HStack>
          </Box>
          <CoverageKpiGrid kpis={kpis} variant="stat" />
          <CoverageTrendGrid sparkline={sparkline} />
          <CoverageBucketsGrid groups={hero?.buckets || []} />
          <Box
            mt={3}
            display="grid"
            gridTemplateColumns={{ base: '1fr', lg: 'repeat(3, minmax(0, 1fr))' }}
            gap={3}
          >
            <Box borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={3} bg="bg.card">
              <HStack justify="space-between" align="center" mb={1}>
                <Text fontSize="sm" fontWeight="semibold">Stage Quality</Text>
                <Badge
                  variant="subtle"
                  colorScheme={stageQuality?.status === 'warning' ? 'orange' : 'green'}
                >
                  {(stageQuality?.status || 'unknown').toUpperCase()}
                </Badge>
              </HStack>
              <Text fontSize="xs" color="fg.muted">
                Unknown rate: {typeof stageQuality?.unknown_rate === 'number'
                  ? `${(stageQuality.unknown_rate * 100).toFixed(1)}%`
                  : '—'}
              </Text>
              <Text fontSize="xs" color="fg.muted">
                Invalid rows: {stageQuality?.invalid_stage_count ?? 0}
              </Text>
              <Text fontSize="xs" color="fg.muted">
                Monotonicity issues: {stageQuality?.monotonicity_issues ?? 0}
              </Text>
              <Text fontSize="xs" color="fg.muted">
                Stale stage rows: {stageQuality?.stale_stage_count ?? 0}
              </Text>
            </Box>

            <Box borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={3} bg="bg.card">
              <HStack justify="space-between" align="center" mb={1}>
                <Text fontSize="sm" fontWeight="semibold">Jobs Health (24h)</Text>
                <Badge
                  variant="subtle"
                  colorScheme={Number(jobsSummary?.error_count || 0) > 0 ? 'orange' : 'green'}
                >
                  {Number(jobsSummary?.error_count || 0) > 0 ? 'DEGRADED' : 'OK'}
                </Badge>
              </HStack>
              <Text fontSize="xs" color="fg.muted">
                Success rate: {typeof jobsSummary?.success_rate === 'number'
                  ? `${(jobsSummary.success_rate * 100).toFixed(1)}%`
                  : '—'}
              </Text>
              <Text fontSize="xs" color="fg.muted">
                Failed: {jobsSummary?.error_count ?? 0} / Completed: {jobsSummary?.completed_count ?? 0}
              </Text>
              <Text fontSize="xs" color="fg.muted">
                Running: {jobsSummary?.running_count ?? 0}
              </Text>
              <Text fontSize="xs" color="fg.muted" lineClamp={1}>
                Latest failure: {jobsSummary?.latest_failed?.task_name || '—'}
              </Text>
            </Box>

            <Box borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={3} bg="bg.card">
              <HStack justify="space-between" align="center" mb={1}>
                <Text fontSize="sm" fontWeight="semibold">Market Audit</Text>
                <Badge variant="subtle">
                  {marketAudit ? 'AVAILABLE' : 'MISSING'}
                </Badge>
              </HStack>
              <Text fontSize="xs" color="fg.muted">
                Tracked total: {marketAudit?.tracked_total ?? '—'}
              </Text>
              <Text fontSize="xs" color="fg.muted">
                Daily fill (latest): {typeof marketAudit?.latest_daily_fill_pct === 'number'
                  ? `${marketAudit.latest_daily_fill_pct.toFixed(1)}%`
                  : '—'}
              </Text>
              <Text fontSize="xs" color="fg.muted">
                Snapshot fill (latest): {typeof marketAudit?.latest_snapshot_history_fill_pct === 'number'
                  ? `${marketAudit.latest_snapshot_history_fill_pct.toFixed(1)}%`
                  : '—'}
              </Text>
              <Text fontSize="xs" color="fg.muted" lineClamp={1}>
                Missing sample: {Array.isArray(marketAudit?.missing_snapshot_history_sample)
                  ? (marketAudit.missing_snapshot_history_sample.slice(0, 3).join(', ') || '—')
                  : '—'}
              </Text>
            </Box>
          </Box>
          {dailyFillDist.total > 0 ? (
            <Box mt={3} borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={3} bg="bg.muted">
              <HStack justify="space-between" align="start" flexWrap="wrap" gap={3}>
                <Box>
                  <Text fontSize="sm" fontWeight="semibold" color="fg.default">
                    Daily fill by date (1d OHLCV)
                  </Text>
                  <Text fontSize="xs" color="fg.muted">
                    {dailyFillDist.newestDate
                      ? `Newest date: ${dailyFillDist.newestDate} • ${dailyFillDist.newestCount}/${dailyFillDist.total} symbols`
                      : 'No daily bars found'}
                  </Text>
                </Box>
                <HStack gap={2} align="center">
                  <Text fontSize="xs" color="fg.muted">
                    Window
                  </Text>
                  <select
                    value={histWindowDays}
                    onChange={(e) => {
                      const next = Number(e.target.value);
                      setHistWindowDays(next);
                      void saveHistogramWindowPref(next);
                    }}
                    style={{
                      fontSize: 12,
                      padding: '6px 8px',
                      borderRadius: 10,
                      border: '1px solid var(--chakra-colors-border-subtle)',
                      background: 'var(--chakra-colors-bg-input)',
                      color: 'var(--chakra-colors-fg-default)',
                    }}
                  >
                    <option value={50}>50d</option>
                    <option value={100}>100d</option>
                    <option value={200}>200d</option>
                  </select>
                </HStack>
                <Badge variant="subtle" colorScheme="green">
                  {dailyFillDist.total > 0
                    ? `${Math.round((dailyFillDist.newestPct || 0) * 10) / 10}% filled on newest`
                    : '—'}
                </Badge>
              </HStack>
              {dailyHistogram}
              <Text mt={2} fontSize="xs" color="fg.muted">
                Hover a bar to see date, filled symbols, fill %, and snapshot %.
              </Text>
            </Box>
          ) : null}
          <Box mt={3} display="flex" alignItems="center" justifyContent="space-between" gap={3} flexWrap="wrap">
            <HStack gap={2} flexWrap="wrap">
              <Badge variant="subtle">Source: {String(coverage?.meta?.source || '—')}</Badge>
              <Badge variant="subtle">Refreshed: {formatDateTime(coverage?.meta?.updated_at, timezone)}</Badge>
              {benchmarkStale ? (
                <Badge variant="subtle" colorScheme="red">
                  SPY stale {benchmarkLatest ? `(${benchmarkLatest})` : ''}
                </Badge>
              ) : null}
              <Tooltip.Root openDelay={200} positioning={{ placement: 'top' }}>
                <Tooltip.Trigger asChild>
                  <Badge variant="subtle" cursor="help">
                    Runs: monitor/backfill
                  </Badge>
                </Tooltip.Trigger>
                <Tooltip.Positioner>
                  <Tooltip.Content>
                    <Box>
                      <Text fontSize="xs" color="fg.muted">
                        Monitor: {fmtLastRun('admin_coverage_refresh')}
                      </Text>
                      <Text fontSize="xs" color="fg.muted">
                        Backfill: {fmtLastRun('admin_coverage_backfill')}
                      </Text>
                    </Box>
                  </Tooltip.Content>
                </Tooltip.Positioner>
              </Tooltip.Root>
            </HStack>
            <Button size="sm" variant="outline" loading={refreshingCoverage} onClick={() => void refreshCoverageNow('manual')}>
              Refresh coverage
            </Button>
          </Box>
          <Box mt={3} display="flex" alignItems="center" gap={3}>
            <input
              type="checkbox"
              checked={backfill5mEnabled}
              onChange={() => void toggleBackfill5m()}
              disabled={toggling5m}
            />
            <Box>
              <Text fontSize="sm" fontWeight="medium">
                5m Backfill {backfill5mEnabled ? 'Enabled' : 'Disabled'}
              </Text>
              <Text fontSize="xs" color="gray.400">
                Daily coverage is the primary SLA. When disabled, 5m is informational-only (ignored for status).
              </Text>
            </Box>
          </Box>
          <Box mt={4} display="flex" flexDirection="column" gap={2}>
            <Text fontSize="sm" fontWeight="semibold">Backfill Actions</Text>
            <Box display="flex" gap={2} flexWrap="wrap">
              <Button colorScheme="brand" size="sm" loading={restoringDaily} onClick={() => void restoreDailyCoverageTracked()}>
                Backfill Daily Coverage (Tracked)
              </Button>
              <Button variant="outline" size="sm" loading={backfillingStale} onClick={() => void backfillStaleDailyOnly()}>
                Backfill Daily (Stale Only)
              </Button>
              <Button variant="ghost" size="sm" onClick={() => setAdvancedOpen(!advancedOpen)}>
                {advancedOpen ? 'Hide Advanced' : 'Show Advanced'}
              </Button>
            </Box>
            {advancedOpen ? (
              <Box mt={2} borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={3} bg="bg.muted">
                <Text fontSize="xs" color="fg.muted" mb={2}>
                  Advanced controls (use when debugging). These are more granular and may be slower/noisier.
                </Text>
                <Box
                  mt={3}
                  display="grid"
                  gridTemplateColumns={{ base: '1fr', lg: '1.1fr 0.9fr' }}
                  gap={3}
                >
                  <Box
                    borderWidth="1px"
                    borderColor="border.subtle"
                    borderRadius="md"
                    bg="bg.card"
                    px={3}
                    py={2}
                  >
                    <Box display="flex" alignItems="center" justifyContent="space-between" mb={1}>
                      <Text fontSize="xs" fontWeight="semibold" color="fg.default">
                        Backfill
                      </Text>
                    </Box>
                    <Text fontSize="xs" color="fg.muted" mb={2}>
                      Use “Backfill Daily Coverage” for missing days. Snapshot History backfills are for analytics/backtesting.
                    </Text>
                    <Box display="flex" flexDirection="column" gap={3}>
                      <Box>
                        <Text fontSize="xs" color="fg.muted" mb={1}>
                          Since date
                        </Text>
                        <Box display="flex" gap={2} flexWrap="wrap" alignItems="center">
                          <input
                            type="date"
                            value={sinceDate}
                            onChange={(e) => {
                              setSinceDateTouched(true);
                              setSinceDate(e.target.value);
                            }}
                            style={{
                              fontSize: 12,
                              padding: '6px 8px',
                              borderRadius: 10,
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
                        <Box mt={2} display="flex" gap={2} flexWrap="wrap" alignItems="center">
                          <Button size="xs" colorScheme="brand" loading={backfillingSinceDate} onClick={() => void backfillSinceDate()}>
                            Backfill Full Flow (since date)
                          </Button>
                          <HStack gap={1}>
                            <Badge size="sm" variant="subtle">Daily</Badge>
                            <Text fontSize="xs" color="fg.muted">-&gt;</Text>
                            <Badge size="sm" variant="subtle">Indicators</Badge>
                            <Text fontSize="xs" color="fg.muted">-&gt;</Text>
                            <Badge size="sm" variant="subtle">History</Badge>
                          </HStack>
                          <Text fontSize="xs" color="fg.muted">
                            Uses date picker (defaults to last green snapshot when available).
                          </Text>
                        </Box>
                      </Box>
                      <Box>
                        <Text fontSize="xs" color="fg.muted" mb={1}>
                          Period
                        </Text>
                        <Box display="flex" gap={2} flexWrap="wrap" alignItems="center">
                          <select
                            aria-label="Snapshot history period"
                            value={snapshotHistoryPeriod}
                            onChange={(e) => setSnapshotHistoryPeriod(e.target.value as any)}
                            style={{
                              fontSize: 12,
                              padding: '6px 8px',
                              borderRadius: 10,
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
                          <Button
                            size="xs"
                            variant="outline"
                            loading={backfillingDailyPeriod}
                            onClick={() => void backfillDailyBarsPeriod()}
                          >
                            Backfill Daily Bars (period)
                          </Button>
                          <Button
                            size="xs"
                            variant="outline"
                            loading={backfillingSnapshotHistory}
                            onClick={() => void backfillSnapshotHistoryPeriod()}
                          >
                            Backfill Snapshot History (period)
                          </Button>
                        </Box>
                        <Box mt={2} display="flex" gap={2} flexWrap="wrap" alignItems="center">
                          <Button
                            size="xs"
                            colorScheme="brand"
                            loading={backfillingPeriodFlow}
                            onClick={() => void backfillPeriodFlow()}
                          >
                            Backfill Full Flow (period)
                          </Button>
                          <HStack gap={1}>
                            <Badge size="sm" variant="subtle">Daily</Badge>
                            <Text fontSize="xs" color="fg.muted">-&gt;</Text>
                            <Badge size="sm" variant="subtle">Indicators</Badge>
                            <Text fontSize="xs" color="fg.muted">-&gt;</Text>
                            <Badge size="sm" variant="subtle">History</Badge>
                          </HStack>
                          <Text fontSize="xs" color="fg.muted">
                            Runs the full flow for the selected period.
                          </Text>
                        </Box>
                      </Box>
                    </Box>
                  </Box>

                  <Box
                    borderWidth="1px"
                    borderColor="border.subtle"
                    borderRadius="md"
                    bg="bg.card"
                    px={3}
                    py={2}
                  >
                    <Box display="flex" alignItems="center" justifyContent="space-between" mb={2}>
                      <Text fontSize="xs" fontWeight="semibold" color="fg.default">
                        Maintenance
                      </Text>
                      <Badge size="sm" variant="subtle">
                        ops
                      </Badge>
                    </Box>
                    <Box display="flex" flexDirection="column" gap={2}>
                      <Text fontSize="xs" color="fg.muted">
                        Universe
                      </Text>
                      <Box display="flex" gap={2} flexWrap="wrap">
                        <Button size="xs" variant="outline" onClick={() => void runNamedTask('market_indices_constituents_refresh', 'Refresh constituents')}>
                          Refresh Constituents
                        </Button>
                        <Button size="xs" variant="outline" onClick={() => void runNamedTask('market_universe_tracked_refresh', 'Update tracked')}>
                          Update Tracked
                        </Button>
                      </Box>
                      <Text fontSize="xs" color="fg.muted" mt={2}>
                        Compute
                      </Text>
                      <Box display="flex" gap={2} flexWrap="wrap">
                        <Button size="xs" variant="outline" onClick={() => void runNamedTask('admin_indicators_recompute_universe', 'Recompute indicators')}>
                          Recompute Indicators (Market Snapshot)
                        </Button>
                        <Button size="xs" variant="outline" onClick={() => void runNamedTask('admin_snapshots_history_record', 'Record history')}>
                          Record History
                        </Button>
                      </Box>
                      <Text mt={2} fontSize="xs" color="fg.muted">
                        Diagnostics
                      </Text>
                      <Text fontSize="xs" color="fg.muted">
                        Sanity Check verifies DB counts without relying on cache.
                      </Text>
                      <Box display="flex" gap={2} flexWrap="wrap">
                        <Button size="xs" variant="outline" loading={sanityLoading} onClick={() => void runSanityCheck()}>
                          Sanity Check (DB)
                        </Button>
                        <Button size="xs" variant="outline" loading={sendingDiscord} onClick={() => void sendSnapshotDigestToDiscord()}>
                          Send Snapshot Digest to Discord
                        </Button>
                      </Box>
                      {sanityData?.benchmark?.ok === false ? (
                        <Text mt={2} fontSize="xs" color="red.500">
                          SPY history is missing ({sanityData?.benchmark?.daily_bars || 0}/{sanityData?.benchmark?.required_bars || 0}).
                          Stage/RS cannot be computed until daily bars are backfilled.
                        </Text>
                      ) : null}
                      <Text mt={2} fontSize="xs" color="fg.muted">
                        If Stage/RS look empty, run “Recompute Indicators (Market Snapshot)”.
                      </Text>
                    </Box>
                  </Box>
                </Box>
              </Box>
            ) : null}
          </Box>
        </CoverageSummaryCard>
      )}
    </Box>
  );
};

export default AdminDashboard;
