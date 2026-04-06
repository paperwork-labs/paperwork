import { useQuery } from '@tanstack/react-query';
import { marketDataApi } from '../services/api';

export function useVolatility() {
  return useQuery({
    queryKey: ['vol-dashboard'],
    queryFn: () => marketDataApi.getVolatilityDashboard(),
    staleTime: 60_000,
    refetchInterval: 5 * 60_000,
  });
}
