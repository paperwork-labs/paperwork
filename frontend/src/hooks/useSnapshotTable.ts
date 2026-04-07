import { useQuery } from '@tanstack/react-query';
import { marketDataApi } from '../services/api';
import type { SnapshotTableParams, SnapshotTableResponse } from '../types/market';

export function useSnapshotTable(params: SnapshotTableParams) {
  return useQuery<SnapshotTableResponse>({
    queryKey: ['snapshot-table', params],
    queryFn: () => marketDataApi.getSnapshotTable(params),
    staleTime: 120_000,
    refetchInterval: 300_000,
    placeholderData: (prev) => prev,
  });
}
