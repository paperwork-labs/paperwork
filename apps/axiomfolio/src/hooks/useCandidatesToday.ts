import { useQuery } from '@tanstack/react-query';

import api from '@/services/api';
import type { CandidatesTodayResponse } from '@/types/signals';

interface UseCandidatesTodayParams {
  limit?: number;
  offset?: number;
}

/**
 * Fetches today's system-generated trade candidates ranked by pick quality.
 *
 * Backend: GET /api/v1/picks/candidates/today
 *   (mounted in backend/api/main.py with prefix `/api/v1/picks`)
 */
export function useCandidatesToday(params: UseCandidatesTodayParams = {}) {
  const limit = params.limit ?? 50;
  const offset = params.offset ?? 0;
  return useQuery<CandidatesTodayResponse>({
    queryKey: ['signals', 'candidates-today', { limit, offset }],
    queryFn: async () => {
      const qs = new URLSearchParams({ limit: String(limit), offset: String(offset) });
      const res = await api.get<CandidatesTodayResponse>(
        `/picks/candidates/today?${qs.toString()}`,
      );
      return res.data;
    },
    staleTime: 5 * 60_000,
    refetchInterval: 10 * 60_000,
  });
}
