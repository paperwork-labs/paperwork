import { useCallback, useEffect, useState } from 'react';
import api from '../services/api';
import type { AdminHealthResponse } from '../types/adminHealth';

interface UseAdminHealthResult {
  health: AdminHealthResponse | null;
  loading: boolean;
  refresh: () => Promise<void>;
}

const useAdminHealth = (): UseAdminHealthResult => {
  const [health, setHealth] = useState<AdminHealthResponse | null>(null);
  const [loading, setLoading] = useState(false);

  const fetchHealth = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get('/market-data/admin/health');
      setHealth(res?.data ?? null);
    } catch {
      setHealth(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchHealth();
  }, [fetchHealth]);

  return { health, loading, refresh: fetchHealth };
};

export default useAdminHealth;
