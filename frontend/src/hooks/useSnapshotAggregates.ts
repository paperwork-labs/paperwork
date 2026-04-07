import { useQuery } from '@tanstack/react-query';
import { marketDataApi } from '../services/api';
import type { SnapshotAggregateParams, SnapshotAggregateResponse } from '../types/market';

export function useSnapshotAggregates(params?: SnapshotAggregateParams) {
  return useQuery<SnapshotAggregateResponse>({
    queryKey: ['snapshot-aggregates', params ?? {}],
    queryFn: () => marketDataApi.getSnapshotAggregates(params),
    staleTime: 120_000,
    refetchInterval: 300_000,
  });
}
