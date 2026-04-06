import { useQuery } from '@tanstack/react-query';
import { marketDataApi } from '../services/api';
import { normalizeRegimeCurrentBody } from '../services/regimeCurrentNormalize';

export function useRegime() {
  return useQuery({
    queryKey: ['regime-current'],
    queryFn: async () => {
      const raw = await marketDataApi.getCurrentRegime();
      return normalizeRegimeCurrentBody(raw);
    },
    staleTime: 60_000,
    refetchInterval: 5 * 60_000,
  });
}
