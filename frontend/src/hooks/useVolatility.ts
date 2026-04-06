import { useQuery } from '@tanstack/react-query';
import { marketDataApi } from '../services/api';

function unwrapVolatilityPayload(resp: unknown): Record<string, unknown> | null {
  if (resp == null || typeof resp !== 'object') {
    return null;
  }
  const r = resp as Record<string, unknown>;
  const inner = r.data;
  if (inner != null && typeof inner === 'object' && !Array.isArray(inner)) {
    return inner as Record<string, unknown>;
  }
  return r;
}

export function useVolatility() {
  return useQuery({
    queryKey: ['vol-dashboard'],
    queryFn: async () => {
      const raw = await marketDataApi.getVolatilityDashboard();
      return unwrapVolatilityPayload(raw);
    },
    staleTime: 60_000,
    refetchInterval: 5 * 60_000,
  });
}
