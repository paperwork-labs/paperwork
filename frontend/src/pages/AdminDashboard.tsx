import React from 'react';
import { Loader2 } from 'lucide-react';
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
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';

const selectClass =
  'h-8 rounded-md border border-input bg-background px-2 text-xs text-foreground shadow-xs outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50 dark:bg-input/30';

const AdminDashboard: React.FC = () => {
  const auth = useAuthOptional();
  const user = auth?.user ?? null;
  const refreshMe = auth?.refreshMe;
  const appSettings = auth?.appSettings;
  const refreshAppSettings = auth?.refreshAppSettings;
  const { timezone, coverageHistogramWindowDays } = useUserPreferences();

  const { health, refresh: refreshHealth } = useAdminHealth();

  const [histWindowDays, setHistWindowDays] = React.useState<number>(
    coverageHistogramWindowDays || 50,
  );
  const fillLookbackDays = React.useMemo(() => Math.max(90, histWindowDays * 3), [histWindowDays]);
  const { snapshot: coverage, refresh: refreshCoverage, sparkline, kpis, hero } =
    useCoverageSnapshot({ fillTradingDaysWindow: histWindowDays, fillLookbackDays });

  const [marketOnlyMode, setMarketOnlyMode] = React.useState(true);
  const [portfolioEnabled, setPortfolioEnabled] = React.useState(false);
  const [strategyEnabled, setStrategyEnabled] = React.useState(false);
  const [togglingMarketOnly, setTogglingMarketOnly] = React.useState(false);

  const [backfill5mEnabled, setBackfill5mEnabled] = React.useState(true);
  const [toggling5m, setToggling5m] = React.useState(false);

  const [sanityData, setSanityData] = React.useState<Record<string, unknown> | null>(null);

  const autoRefreshAttemptedRef = React.useRef(false);
  const [refreshingCoverage, setRefreshingCoverage] = React.useState(false);

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

  React.useEffect(() => {
    void loadSanity();
  }, []);

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

  const fmtLastRunFirst = (keys: string[]) => {
    for (const key of keys) {
      const ts = health?.task_runs?.[key]?.ts as string | undefined;
      if (ts) return formatDateTime(ts, timezone);
    }
    return '—';
  };

  return (
    <div className="p-4">
      <h1 className="mb-4 font-heading text-lg font-semibold text-foreground">Admin Dashboard</h1>

      <AdminHealthBanner health={health} timezone={timezone} />

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

          <AdminDomainCards health={health} />

          {dailyFillDist.total > 0 ? (
            <div className="mt-3 rounded-xl border border-border bg-muted/40 p-3">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-foreground">
                    Daily fill by date (1d OHLCV)
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {dailyFillDist.newestDate
                      ? `Newest date: ${dailyFillDist.newestDate} • ${dailyFillDist.newestCount}/${dailyFillDist.total} symbols`
                      : 'No daily bars found'}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-muted-foreground">Window</span>
                  <select
                    className={selectClass}
                    value={histWindowDays}
                    onChange={(e) => {
                      const next = Number(e.target.value);
                      setHistWindowDays(next);
                      void saveHistogramWindowPref(next);
                    }}
                  >
                    <option value={50}>50d</option>
                    <option value={100}>100d</option>
                    <option value={200}>200d</option>
                  </select>
                </div>
              </div>

              <CoverageHealthStrip
                dailyFillSeries={dailyFillSeries}
                snapshotFillSeries={snapshotFillSeries}
                windowDays={histWindowDays}
                totalSymbols={totalSymbols}
              />
            </div>
          ) : null}

          <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="secondary">
                Source: {String((coverage as Record<string, Record<string, unknown>>)?.meta?.source || '—')}
              </Badge>
              <Badge variant="secondary">
                Refreshed: {formatDateTime((coverage as Record<string, Record<string, unknown>>)?.meta?.updated_at as string | undefined, timezone)}
              </Badge>
              {benchmarkStale ? (
                <Badge variant="destructive">
                  SPY stale {benchmarkLatest ? `(${String(benchmarkLatest)})` : ''}
                </Badge>
              ) : null}
              <TooltipProvider delayDuration={200}>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Badge variant="secondary" className="cursor-help">
                      Runs: coverage / pipeline
                    </Badge>
                  </TooltipTrigger>
                  <TooltipContent>
                    <div className="text-xs text-background">
                      <p className="text-background/90">
                        Monitor: {fmtLastRunFirst(['health_check', 'admin_coverage_refresh'])}
                      </p>
                      <p className="text-background/90">
                        Pipeline: {fmtLastRunFirst(['daily_bootstrap', 'admin_coverage_backfill'])}
                      </p>
                    </div>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </div>
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={refreshingCoverage}
              onClick={() => void refreshCoverageNow('manual')}
            >
              {refreshingCoverage ? <Loader2 className="size-3.5 animate-spin" aria-hidden /> : null}
              Refresh coverage
            </Button>
          </div>

          <div className="mt-3 flex items-start gap-3">
            <Checkbox
              id="admin-5m-backfill"
              checked={backfill5mEnabled}
              disabled={toggling5m}
              onCheckedChange={() => void toggleBackfill5m()}
              className="mt-0.5"
            />
            <div className="min-w-0">
              <label htmlFor="admin-5m-backfill" className="text-sm font-medium text-foreground">
                5m Backfill {backfill5mEnabled ? 'Enabled' : 'Disabled'}
              </label>
              <p className="text-xs text-muted-foreground">
                Daily coverage is the primary SLA. When disabled, 5m is informational-only (ignored for status).
              </p>
            </div>
          </div>

          <AdminOperatorActions
            refreshCoverage={refreshCoverage}
            refreshHealth={refreshHealth}
            sanityData={sanityData}
            setSanityData={setSanityData}
          />
        </CoverageSummaryCard>
      )}
    </div>
  );
};

export default AdminDashboard;
