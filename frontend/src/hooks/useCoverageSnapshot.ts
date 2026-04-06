import { useCallback, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
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
  const fillW = opts?.fillTradingDaysWindow ?? null;
  const fillL = opts?.fillLookbackDays ?? null;

  const { data: snapshot = null, isPending: loading, refetch } = useQuery({
    queryKey: ['market-data', 'coverage', fillW, fillL],
    queryFn: async () => {
      const params: Record<string, number> = {};
      if (typeof opts?.fillTradingDaysWindow === 'number') {
        params.fill_trading_days_window = opts.fillTradingDaysWindow;
      }
      if (typeof opts?.fillLookbackDays === 'number') {
        params.fill_lookback_days = opts.fillLookbackDays;
      }
      const response = await api.get(
        '/market-data/coverage',
        Object.keys(params).length ? { params } : undefined,
      );
      return response.data || null;
    },
    staleTime: 60_000,
  });

  const refresh = useCallback(async () => {
    await refetch();
  }, [refetch]);

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
    refresh,
    sparkline: sparkline || defaultSparkline,
    kpis,
    actions,
    hero,
  };
};

export default useCoverageSnapshot;
