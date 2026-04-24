import { useQuery } from '@tanstack/react-query';

import api from '@/services/api';
import type { RegimeHistoryResponse } from '@/types/signals';

/**
 * Regime history for the last `days` calendar days.
 *
 * Backend: GET /api/v1/market-data/regime/history?days=N
 */
export function useRegimeHistory(days: number = 90) {
  return useQuery<RegimeHistoryResponse>({
    queryKey: ['signals', 'regime-history', days],
    queryFn: async () => {
      const res = await api.get<RegimeHistoryResponse>(
        `/market-data/regime/history?days=${days}`,
      );
      return res.data;
    },
    staleTime: 10 * 60_000,
    refetchInterval: 30 * 60_000,
  });
}
