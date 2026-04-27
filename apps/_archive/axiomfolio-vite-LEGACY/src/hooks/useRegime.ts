import { useQuery } from '@tanstack/react-query';
import { marketDataApi } from '../services/api';

export function useRegime() {
  return useQuery({
    queryKey: ['regime-current'],
    queryFn: () => marketDataApi.getCurrentRegime(),
    staleTime: 60_000,
    refetchInterval: 5 * 60_000,
  });
}
