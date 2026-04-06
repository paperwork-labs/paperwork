import { useQuery } from '@tanstack/react-query';
import { marketDataApi } from '../services/api';

const SNAPSHOT_LIMIT = 5000;

export interface MarketSnapshotRow {
  symbol: string;
  name?: string;
  stage_label?: string;
  scan_tier?: string;
  action_label?: string;
  rs_mansfield_pct?: number;
  vol_ratio?: number;
  current_price?: number;
  perf_5d?: number;
  perf_20d?: number;
  perf_60d?: number;
  sma150_slope?: number;
  atrp_14?: number;
  sector?: string;
  regime_state?: string;
  ext_pct?: number;
  rsi?: number;
  current_stage_days?: number;
  [key: string]: unknown;
}

/** Shared cache for full market snapshot list (Scanner, Market Dashboard, etc.). */
export function useMarketSnapshots() {
  return useQuery<MarketSnapshotRow[]>({
    queryKey: ['market-snapshots'],
    queryFn: async () => {
      const payload = await marketDataApi.getSnapshots(SNAPSHOT_LIMIT);
      const rows = (payload as { rows?: unknown[] } | null | undefined)?.rows;
      return Array.isArray(rows) ? (rows as MarketSnapshotRow[]) : [];
    },
    staleTime: 120_000,
    refetchInterval: 300_000,
  });
}
