import { useQuery, useQueryClient } from '@tanstack/react-query';
import api from '../services/api';
import type { AdminHealthResponse } from '../types/adminHealth';

interface UseAdminHealthResult {
  health: AdminHealthResponse | null;
  loading: boolean;
  isError: boolean;
  refresh: () => Promise<void>;
}

const useAdminHealth = (): UseAdminHealthResult => {
  const queryClient = useQueryClient();
  const { data, isPending, isError } = useQuery<AdminHealthResponse | null>({
    queryKey: ['admin-health'],
    queryFn: async () => {
      const res = await api.get<AdminHealthResponse>('/market-data/admin/health');
      return res?.data ?? null;
    },
    staleTime: 1000 * 60 * 2,
    refetchInterval: 1000 * 60 * 5,
  });

  const refresh = async () => {
    await queryClient.invalidateQueries({ queryKey: ['admin-health'] });
  };

  return { health: data ?? null, loading: isPending, isError, refresh };
};

export default useAdminHealth;
