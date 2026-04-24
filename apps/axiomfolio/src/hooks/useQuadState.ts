import { useQuery } from '@tanstack/react-query';
import { marketDataApi } from '../services/api';
import type { QuadCurrentResponse, QuadHistoryResponse } from '../types/market';

export function useQuadState() {
  return useQuery<QuadCurrentResponse>({
    queryKey: ['quad-current'],
    queryFn: () => marketDataApi.getQuadCurrent(),
    staleTime: 60_000,
    refetchInterval: 300_000,
  });
}

export function useQuadHistory(days: number = 90) {
  return useQuery<QuadHistoryResponse>({
    queryKey: ['quad-history', days],
    queryFn: () => marketDataApi.getQuadHistory(days),
    staleTime: 300_000,
  });
}
