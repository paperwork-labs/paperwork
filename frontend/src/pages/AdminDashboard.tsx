import React from 'react';
import { Box, Heading, Badge, Button, HStack, Text, Tooltip } from '@chakra-ui/react';
import toast from 'react-hot-toast';
import api from '../services/api';
import useCoverageSnapshot from '../hooks/useCoverageSnapshot';
import useAdminHealth from '../hooks/useAdminHealth';
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
import {
  AdminHealthBanner,
  AdminDomainCards,
  AdminReleaseControls,
  AdminOperatorActions,
  AdminRunbook,
} from '../components/admin';
import CoverageHealthStrip from '../components/coverage/CoverageHealthStrip';

const AdminDashboard: React.FC = () => {
  const auth = useAuthOptional();
  const user = auth?.user ?? null;
  const refreshMe = auth?.refreshMe;
  const appSettings = auth?.appSettings;
  const refreshAppSettings = auth?.refreshAppSettings;
  const { timezone, coverageHistogramWindowDays } = useUserPreferences();

  // Composite health (single API call replaces 4 old load functions)
  const { health, loading: healthLoading, refresh: refreshHealth } = useAdminHealth();

  // Coverage snapshot (kept -- powers the coverage summary card / histogram / KPIs)
  const [histWindowDays, setHistWindowDays] = React.useState<number>(
    coverageHistogramWindowDays || 50,
  );
  const fillLookbackDays = React.useMemo(() => Math.max(90, histWindowDays * 3), [histWindowDays]);
  const { snapshot: coverage, refresh: refreshCoverage, sparkline, kpis, hero } =
    useCoverageSnapshot({ fillTradingDaysWindow: histWindowDays, fillLookbackDays });

  // Release controls
  const [marketOnlyMode, setMarketOnlyMode] = React.useState(true);
  const [portfolioEnabled, setPortfolioEnabled] = React.useState(false);
  const [strategyEnabled, setStrategyEnabled] = React.useState(false);
  const [togglingMarketOnly, setTogglingMarketOnly] = React.useState(false);

  // 5m toggle
  const [backfill5mEnabled, setBackfill5mEnabled] = React.useState(true);
  const [toggling5m, setToggling5m] = React.useState(false);

  // Sanity data (passed to operator actions)
  const [sanityData, setSanityData] = React.useState<Record<string, unknown> | null>(null);

  // Auto-refresh state
  const autoRefreshAttemptedRef = React.useRef(false);
  const [refreshingCoverage, setRefreshingCoverage] = React.useState(false);

  // ---------- Sync state from backend ----------

  React.useEffect(() => {
    if (coverageHistogramWindowDays && coverageHistogramWindowDays !== histWindowDays) {
      setHistWindowDays(coverageHistogramWindowDays);
      return;
    }
    if (!coverageHistogramWindowDays) {
      const backendDefault = Number((coverage as Record<string, Record<string, unknown>>)?.meta?.fill_trading_days_window ?? NaN);
      if (Number.isFinite(backendDefault) && backendDefault > 0 && backendDefault !== histWindowDays) {
        setHistWindowDays(backendDefault);
      }
    }
  }, [coverageHistogramWindowDays, (coverage as Record<string, Record<string, unknown>>)?.meta?.fill_trading_days_window]);

  React.useEffect(() => {
    if ((coverage as Record<string, Record<string, unknown>>)?.meta?.backfill_5m_enabled !== undefined) {
      setBackfill5mEnabled(Boolean((coverage as Record<string, Record<string, unknown>>).meta.backfill_5m_enabled));
    }
  }, [coverage]);

  React.useEffect(() => {
    if (appSettings?.market_only_mode !== undefined) setMarketOnlyMode(Boolean(appSettings.market_only_mode));
    if (appSettings?.portfolio_enabled !== undefined) setPortfolioEnabled(Boolean(appSettings.portfolio_enabled));
    if (appSettings?.strategy_enabled !== undefined) setStrategyEnabled(Boolean(appSettings.strategy_enabled));
  }, [appSettings?.market_only_mode, appSettings?.portfolio_enabled, appSettings?.strategy_enabled]);

  // Auto-trigger coverage monitor when cache is stale
  React.useEffect(() => {
    if (!coverage || autoRefreshAttemptedRef.current) return;
    const age = Number((coverage as Record<string, Record<string, unknown>>)?.meta?.snapshot_age_seconds ?? NaN);
    const source = String((coverage as Record<string, Record<string, unknown>>)?.meta?.source || '');
    const stale = !Number.isFinite(age) || age > 15 * 60 || source !== 'cache';
    if (stale) {
      autoRefreshAttemptedRef.current = true;
      void refreshCoverageNow('auto');
    }
  }, [coverage]);

  // Load sanity on mount
  React.useEffect(() => {
    void loadSanity();
  }, []);

  // ---------- Handlers ----------

  const saveHistogramWindowPref = async (next: number) => {
    try {
      if (!user || typeof refreshMe !== 'function') return;
      const existing = (user?.ui_preferences && typeof user.ui_preferences === 'object') ? user.ui_preferences : {};
      await authApi.updateMe({
        ui_preferences: { ...existing, coverage_histogram_window_days: next },
      });
      await refreshMe();
    } catch (e) {
      toast.error(handleApiError(e));
    }
  };

  const updateReleaseControls = async (patch: { market_only_mode?: boolean; portfolio_enabled?: boolean; strategy_enabled?: boolean }) => {
    if (togglingMarketOnly) return;
    setTogglingMarketOnly(true);
    try {
      const res: Record<string, unknown> = await appSettingsApi.update(patch) as Record<string, unknown>;
      setMarketOnlyMode(Boolean(res?.market_only_mode));
      setPortfolioEnabled(Boolean(res?.portfolio_enabled));
      setStrategyEnabled(Boolean(res?.strategy_enabled));
      if (typeof refreshAppSettings === 'function') await refreshAppSettings();
      toast.success('Release controls updated');
    } catch (e) {
      toast.error(handleApiError(e));
    } finally {
      setTogglingMarketOnly(false);
    }
  };

  const refreshCoverageNow = async (origin: 'manual' | 'auto') => {
    if (refreshingCoverage) return;
    setRefreshingCoverage(true);
    try {
      await api.post('/market-data/admin/backfill/coverage/refresh');
      toast.success(origin === 'auto' ? 'Coverage refresh queued (auto)' : 'Coverage refresh queued');
      setTimeout(() => void refreshCoverage(), 1500);
      setTimeout(() => void refreshCoverage(), 4500);
      void refreshHealth();
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } }; message?: string } | undefined;
      toast.error(axiosErr?.response?.data?.detail || axiosErr?.message || 'Failed to refresh coverage');
    } finally {
      setRefreshingCoverage(false);
    }
  };

  const toggleBackfill5m = async () => {
    if (toggling5m) return;
    setToggling5m(true);
    const next = !backfill5mEnabled;
    try {
      const res = await api.post('/market-data/admin/backfill/5m/toggle', { enabled: next });
      const flag = (res?.data as Record<string, boolean>)?.backfill_5m_enabled ?? next;
      setBackfill5mEnabled(Boolean(flag));
      toast.success(`5m backfill ${flag ? 'enabled' : 'disabled'}`);
      await refreshCoverage();
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } }; message?: string } | undefined;
      toast.error(axiosErr?.response?.data?.detail || axiosErr?.message || 'Failed to update 5m backfill toggle');
    } finally {
      setToggling5m(false);
    }
  };

  const loadSanity = async () => {
    try {
      const res = await api.get('/market-data/admin/coverage/sanity');
      setSanityData((res?.data || null) as Record<string, unknown> | null);
    } catch { /* swallow */ }
  };

  // ---------- Derived data ----------

  const heroEffective = React.useMemo(() => {
    if (!hero) return hero;
    if (!backfill5mEnabled && hero?.staleCounts?.daily === 0 && hero?.staleCounts?.m5 > 0) {
      return { ...hero, summary: '5m is disabled (ignored for status).' };
    }
    return hero;
  }, [hero, backfill5mEnabled]);

  const dailyFillSeries = ((coverage as Record<string, Record<string, unknown>>)?.daily?.fill_by_date as Array<{ date: string; symbol_count: number; pct_of_universe: number }>) || [];
  const snapshotFillSeries = ((coverage as Record<string, Record<string, unknown>>)?.daily?.snapshot_fill_by_date as Array<{ date: string; symbol_count: number; pct_of_universe: number }>) || [];
  const totalSymbols = Number((coverage as Record<string, unknown>)?.symbols ?? (coverage as Record<string, unknown>)?.tracked_count ?? 0);
  const benchmark = (coverage as Record<string, Record<string, unknown>>)?.meta?.benchmark ?? sanityData?.benchmark;
  const benchmarkStale = benchmark && (benchmark as Record<string, unknown>).ok === false;
  const benchmarkLatest = (benchmark as Record<string, unknown>)?.latest_daily_date;

  const dailyFillDist = React.useMemo(() => {
    const rows = [...dailyFillSeries]
      .filter((r) => r && r.date)
      .sort((a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : 0));
    const newestDate = rows.length ? rows[0].date : null;
    const newestCount = rows.length ? Number(rows[0].symbol_count || 0) : 0;
    const newestPct = rows.length ? Number(rows[0].pct_of_universe || 0) : 0;
    return { newestDate, newestCount, newestPct, total: totalSymbols || 0, rows };
  }, [dailyFillSeries, totalSymbols]);

  const fmtLastRun = (key: string) => {
    const raw = health?.task_runs?.[key];
    const ts = raw?.ts;
    return formatDateTime(ts as string | undefined, timezone);
  };

  // ---------- Render ----------

  return (
    <Box p={4}>
      <Heading size="md" mb={4}>Admin Dashboard</Heading>

      {/* Composite Health Banner */}
      <AdminHealthBanner health={health} timezone={timezone} />

      {/* Runbook / On-Call Guide (shows remediation for RED dimensions) */}
      <AdminRunbook health={health} />

      {coverage && (
        <CoverageSummaryCard hero={heroEffective} status={coverage.status} showUpdated={false}>
          <AdminReleaseControls
            marketOnlyMode={marketOnlyMode}
            portfolioEnabled={portfolioEnabled}
            strategyEnabled={strategyEnabled}
            toggling={togglingMarketOnly}
            onToggleMarketOnly={() => void updateReleaseControls({ market_only_mode: !marketOnlyMode })}
            onTogglePortfolio={() => void updateReleaseControls({ portfolio_enabled: !portfolioEnabled })}
            onToggleStrategy={() => void updateReleaseControls({ strategy_enabled: !strategyEnabled })}
          />
          <CoverageKpiGrid kpis={kpis} variant="stat" />
          <CoverageTrendGrid sparkline={sparkline} />
          <CoverageBucketsGrid groups={hero?.buckets || []} />

          {/* Domain cards from composite health */}
          <AdminDomainCards health={health} />

          {/* Coverage health strip */}
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
                  <Text fontSize="xs" color="fg.muted">Window</Text>
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
              </HStack>

              <CoverageHealthStrip
                dailyFillSeries={dailyFillSeries}
                snapshotFillSeries={snapshotFillSeries}
                windowDays={histWindowDays}
                totalSymbols={totalSymbols}
              />
            </Box>
          ) : null}

          {/* Meta badges + refresh */}
          <Box mt={3} display="flex" alignItems="center" justifyContent="space-between" gap={3} flexWrap="wrap">
            <HStack gap={2} flexWrap="wrap">
              <Badge variant="subtle">Source: {String((coverage as Record<string, Record<string, unknown>>)?.meta?.source || '—')}</Badge>
              <Badge variant="subtle">Refreshed: {formatDateTime((coverage as Record<string, Record<string, unknown>>)?.meta?.updated_at as string | undefined, timezone)}</Badge>
              {benchmarkStale ? (
                <Badge variant="subtle" colorScheme="red">
                  SPY stale {benchmarkLatest ? `(${String(benchmarkLatest)})` : ''}
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

          {/* 5m toggle */}
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
              <Text fontSize="xs" color="fg.subtle">
                Daily coverage is the primary SLA. When disabled, 5m is informational-only (ignored for status).
              </Text>
            </Box>
          </Box>

          {/* Operator actions with safe/destructive grouping */}
          <AdminOperatorActions
            refreshCoverage={refreshCoverage}
            refreshHealth={refreshHealth}
            sanityData={sanityData}
            setSanityData={setSanityData}
          />
        </CoverageSummaryCard>
      )}
    </Box>
  );
};

export default AdminDashboard;
