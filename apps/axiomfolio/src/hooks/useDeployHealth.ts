import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import api from '../services/api';
import type { DeployHealthDetailResponse } from '../types/adminHealth';

/**
 * G28 deploy-health guardrail (D120).
 *
 * Wraps `GET /api/v1/admin/deploys/health` and `POST /api/v1/admin/deploys/poll`.
 * Admin-only — callers must gate the UI on `user.is_admin`.
 */
export interface UseDeployHealthResult {
  data: DeployHealthDetailResponse | null;
  isLoading: boolean;
  isError: boolean;
  error: unknown;
  refresh: () => Promise<void>;
  poll: () => Promise<void>;
  polling: boolean;
}

const useDeployHealth = (): UseDeployHealthResult => {
  const queryClient = useQueryClient();

  const query = useQuery<DeployHealthDetailResponse | null>({
    queryKey: ['admin-deploy-health'],
    queryFn: async () => {
      const res = await api.get<DeployHealthDetailResponse>(
        '/admin/deploys/health?limit=50',
      );
      return res?.data ?? null;
    },
    // Refetch every 60s so the UI surfaces a fresh storm within one minute,
    // even though the Beat poll runs every 5 minutes. staleTime matches so
    // the next visible render actually re-queries instead of showing cache.
    staleTime: 1000 * 60,
    refetchInterval: 1000 * 60,
  });

  const refresh = async () => {
    await queryClient.invalidateQueries({ queryKey: ['admin-deploy-health'] });
  };

  const mutation = useMutation({
    mutationFn: async () => {
      await api.post('/admin/deploys/poll');
    },
    onSuccess: () => refresh(),
  });

  return {
    data: query.data ?? null,
    isLoading: query.isPending,
    isError: query.isError,
    error: query.error,
    refresh,
    poll: async () => {
      await mutation.mutateAsync();
    },
    polling: mutation.isPending,
  };
};

export default useDeployHealth;
