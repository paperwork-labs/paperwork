import { useQuery } from '@tanstack/react-query';
import { marketDataApi } from '../services/api';
import type { SnapshotAggregateParams, SnapshotAggregateResponse } from '../types/market';

/**
 * Snapshot aggregates query (TanStack Query `useQuery`).
 *
 * Returned fields include `data` (`SnapshotAggregateResponse` on success),
 * `isLoading`, `isFetching`, `isError`, `error`, `status`, `fetchStatus`,
 * and `refetch` (same shape as other hooks using `useQuery`).
 *
 * Consumers MUST distinguish loading / error / empty / data states explicitly;
 * never render `data?.total ?? 0` directly as a user-facing count, because that
 * hides loading and error states behind a fake "0".
 * See `.cursor/rules/no-silent-fallback.mdc`.
 *
 * For a compact count string for badges, pair this hook with
 * `formatAggregateCount(query)` below.
 */
export function useSnapshotAggregates(params?: SnapshotAggregateParams) {
  return useQuery<SnapshotAggregateResponse>({
    queryKey: ['snapshot-aggregates', params ?? {}],
    queryFn: () => marketDataApi.getSnapshotAggregates(params),
    staleTime: 120_000,
    refetchInterval: 300_000,
    retry: 2,
  });
}

/**
 * Return a label suitable for a count badge that distinguishes loading,
 * error, and zero from real counts.
 *
 * - loading (no prior data): returns an ellipsis string
 * - error or missing total (no prior numeric total): returns a dash placeholder string
 * - data present with numeric `total`: the stringified count (which may legitimately be 0)
 *
 * If a previous successful response exists, we prefer the stale count
 * over a placeholder so the UI does not flicker on background refetch.
 */
export function formatAggregateCount(query: {
  data?: { total?: number } | undefined;
  isLoading: boolean;
  isError: boolean;
}): string {
  if (query.data && typeof query.data.total === 'number') {
    return String(query.data.total);
  }
  if (query.isLoading) return '…';
  if (query.isError) return '—';
  return '—';
}
