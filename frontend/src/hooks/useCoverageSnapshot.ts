import { useCallback, useEffect, useMemo, useState } from 'react';
import api from '../services/api';
import { useUserPreferences } from './useUserPreferences';
import {
  buildCoverageActions,
  buildCoverageKpis,
  CoverageAction,
  CoverageHeroMeta,
  CoverageKpi,
  CoverageSparkline,
  deriveSparklineSeries,
  formatCoverageHero,
} from '../utils/coverage';

interface UseCoverageSnapshotResult {
  snapshot: any | null;
  loading: boolean;
  refresh: () => Promise<void>;
  sparkline: CoverageSparkline;
  kpis: CoverageKpi[];
  actions: CoverageAction[];
  hero: CoverageHeroMeta;
}

type CoverageSnapshotOptions = {
  fillTradingDaysWindow?: number;
  fillLookbackDays?: number;
};

const defaultSparkline = deriveSparklineSeries();

const useCoverageSnapshot = (opts?: CoverageSnapshotOptions): UseCoverageSnapshotResult => {
  const { timezone } = useUserPreferences();
  const [snapshot, setSnapshot] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);

  const fetchSnapshot = useCallback(async () => {
    setLoading(true);
    try {
      const params: any = {};
      if (typeof opts?.fillTradingDaysWindow === 'number') {
        params.fill_trading_days_window = opts.fillTradingDaysWindow;
      }
      if (typeof opts?.fillLookbackDays === 'number') {
        params.fill_lookback_days = opts.fillLookbackDays;
      }
      const response = await api.get('/market-data/coverage', Object.keys(params).length ? { params } : undefined);
      setSnapshot(response.data || null);
    } catch (error) {
      if (import.meta.env.DEV) {
        console.error('Failed to load coverage snapshot', error);
      }
      setSnapshot(null);
    } finally {
      setLoading(false);
    }
  }, [opts?.fillTradingDaysWindow, opts?.fillLookbackDays]);

  useEffect(() => {
    fetchSnapshot();
  }, [fetchSnapshot]);

  const sparkline = useMemo(
    () =>
      deriveSparklineSeries(snapshot?.meta?.sparkline, snapshot?.history || snapshot?.meta?.history),
    [snapshot],
  );

  const kpis = useMemo(
    () => buildCoverageKpis(snapshot?.meta?.kpis, snapshot, snapshot?.status),
    [snapshot],
  );

  const actions = useMemo(
    () => buildCoverageActions(snapshot?.meta?.actions),
    [snapshot],
  );

  const hero = useMemo(() => formatCoverageHero(snapshot, 1800, timezone), [snapshot, timezone]);

  return {
    snapshot,
    loading,
    refresh: fetchSnapshot,
    sparkline: sparkline || defaultSparkline,
    kpis,
    actions,
    hero,
  };
};

export default useCoverageSnapshot;

