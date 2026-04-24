/**
 * TanStack Query hook for RS Mansfield ribbon (workspace chart).
 * Four consumer states: loading, error, empty, ready via `viewState`.
 */

import { useQuery } from '@tanstack/react-query';

import { marketDataApi, unwrapResponse } from '@/services/api';

export type RSMansfieldPoint = { date: string; value: number };

export type RSMansfieldViewState = 'loading' | 'error' | 'empty' | 'ready';

export interface UseRSMansfieldOptions {
  period?: string;
  benchmark?: string;
  /** When false, query does not run. */
  enabled?: boolean;
}

export function useRSMansfield(symbol: string | null, options: UseRSMansfieldOptions = {}) {
  const { period = '1y', benchmark = 'SPY', enabled = true } = options;

  const query = useQuery({
    queryKey: ['rsMansfield', symbol, period, benchmark],
    queryFn: async () => {
      const res = await marketDataApi.getRSMansfieldSeries(symbol!, { period, benchmark });
      const points = unwrapResponse<RSMansfieldPoint>(res, 'data');
      return { points };
    },
    enabled: Boolean(symbol) && enabled,
    staleTime: 300_000,
  });

  const points = query.data?.points ?? [];
  const viewState: RSMansfieldViewState = query.isPending
    ? 'loading'
    : query.isError
      ? 'error'
      : points.length === 0
        ? 'empty'
        : 'ready';

  return {
    ...query,
    points,
    viewState,
    isEmpty: viewState === 'empty',
  };
}
