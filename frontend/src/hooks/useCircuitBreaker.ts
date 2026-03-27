import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import api from '../services/api';
import type { CircuitBreakerStatus } from '../types/circuitBreaker';

export const circuitBreakerQueryKey = ['circuit-breaker'] as const;

export function useCircuitBreakerStatus(options?: { enabled?: boolean }) {
  return useQuery<CircuitBreakerStatus>({
    queryKey: circuitBreakerQueryKey,
    queryFn: async () => {
      const res = await api.get<{ data: CircuitBreakerStatus }>('/risk/circuit-breaker');
      return res.data.data;
    },
    staleTime: 15_000,
    refetchInterval: 30_000,
    enabled: options?.enabled ?? true,
  });
}

export function useResetCircuitBreakerKillSwitch() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const res = await api.post<{ data: CircuitBreakerStatus }>(
        '/risk/circuit-breaker/reset-kill-switch',
      );
      return res.data.data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: circuitBreakerQueryKey });
    },
  });
}
