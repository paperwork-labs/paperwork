import { useQuery } from '@tanstack/react-query';

import api from '@/services/api';

/**
 * IV-rank coverage state for a single symbol.
 *
 * Backing endpoint: ``GET /api/v1/market-data/iv/coverage/{symbol}``
 * (see ``backend/api/routes/market/iv.py``).
 *
 * Four meaningful states:
 *   - ``isLoading``            -- query in flight, render a skeleton.
 *   - ``isRamping``            -- we have some history but < 252 daily
 *                                samples, so ``iv_rank_252`` is not yet
 *                                trustworthy. UI should show "N/A" with
 *                                a tooltip, NEVER "0".
 *   - ``hasRank && ivRank`` -- render as ``0-100`` percentile.
 *   - neither                 -- no history at all; render "—".
 *
 * Matches G5 plan §Frontend (``docs/plans/G5_IV_RANK_SURFACE.md``).
 */

export type IvCoverageRow = {
  symbol: string;
  iv_rank: number | null;
  has_rank: boolean;
  is_ramping: boolean;
  sample_count: number;
  as_of: string | null;
  source: 'ibkr' | 'yahoo' | null;
};

export type IvCoverage = {
  symbol: string;
  ivRank: number | null;
  hasRank: boolean;
  isRamping: boolean;
  sampleCount: number;
  asOf: string | null;
  source: 'ibkr' | 'yahoo' | null;
};

function adapt(raw: IvCoverageRow): IvCoverage {
  return {
    symbol: raw.symbol,
    ivRank: raw.iv_rank,
    hasRank: raw.has_rank,
    isRamping: raw.is_ramping,
    sampleCount: raw.sample_count,
    asOf: raw.as_of,
    source: raw.source,
  };
}

/**
 * Per-symbol IV-coverage hook.
 *
 * Pass an empty / nullish symbol to short-circuit the query (useful for
 * row cells that might not know their symbol yet).
 */
export function useIvCoverage(symbol: string | null | undefined) {
  const sym = (symbol ?? '').toUpperCase().trim();
  return useQuery<IvCoverage>({
    queryKey: ['market', 'iv-coverage', sym],
    enabled: !!sym,
    queryFn: async () => {
      const res = await api.get<IvCoverageRow>(
        `/market-data/iv/coverage/${encodeURIComponent(sym)}`,
      );
      return adapt(res.data);
    },
    // IV rank only moves once per trading day; caching heavily is fine.
    staleTime: 10 * 60_000,
    refetchInterval: 60 * 60_000,
  });
}

/**
 * Batch IV-coverage hook for watchlist / scan tables.
 *
 * Accepts any iterable of symbols; dedupes and uppercases them before
 * sending. Returns a ``Record<symbol, IvCoverage>`` for O(1) lookups.
 */
export function useIvCoverageBatch(symbols: readonly string[] | undefined | null) {
  const cleaned = Array.from(
    new Set((symbols ?? []).map((s) => (s ?? '').toUpperCase().trim()).filter(Boolean)),
  ).sort();
  const enabled = cleaned.length > 0;
  const key = cleaned.join(',');
  return useQuery<Record<string, IvCoverage>>({
    queryKey: ['market', 'iv-coverage-batch', key],
    enabled,
    queryFn: async () => {
      const res = await api.get<{ count: number; rows: IvCoverageRow[] }>(
        `/market-data/iv/coverage?symbols=${encodeURIComponent(key)}`,
      );
      const out: Record<string, IvCoverage> = {};
      for (const row of res.data?.rows ?? []) {
        out[row.symbol] = adapt(row);
      }
      return out;
    },
    staleTime: 10 * 60_000,
    refetchInterval: 60 * 60_000,
  });
}
