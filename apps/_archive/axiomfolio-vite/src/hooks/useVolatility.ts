import { useQuery } from '@tanstack/react-query';
import { marketDataApi } from '../services/api';

/** Matches backend `VolatilityService.get_dashboard` payload. */
export interface VolatilityDashboardData {
  vix: number | null;
  vvix: number | null;
  vix3m: number | null;
  term_structure_ratio: number | null;
  vol_of_vol_ratio: number | null;
  regime: string;
  signal: string;
}

function toNumOrNull(v: unknown): number | null {
  if (v == null) return null;
  if (typeof v === 'number' && Number.isFinite(v)) return v;
  if (typeof v === 'string' && v.trim() !== '') {
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

function normalizeVolatilityPayload(payload: Record<string, unknown>): VolatilityDashboardData {
  return {
    vix: toNumOrNull(payload.vix),
    vvix: toNumOrNull(payload.vvix),
    vix3m: toNumOrNull(payload.vix3m),
    term_structure_ratio: toNumOrNull(payload.term_structure_ratio),
    vol_of_vol_ratio: toNumOrNull(payload.vol_of_vol_ratio),
    regime: typeof payload.regime === 'string' ? payload.regime : 'unknown',
    signal: typeof payload.signal === 'string' ? payload.signal : '',
  };
}

function unwrapVolatilityPayload(resp: unknown): VolatilityDashboardData | null {
  if (resp == null || typeof resp !== 'object') {
    return null;
  }
  const r = resp as Record<string, unknown>;
  const inner = r.data;
  const raw =
    inner != null && typeof inner === 'object' && !Array.isArray(inner)
      ? (inner as Record<string, unknown>)
      : r;
  return normalizeVolatilityPayload(raw);
}

export function useVolatility() {
  return useQuery<VolatilityDashboardData | null>({
    queryKey: ['vol-dashboard'],
    queryFn: async () => {
      const raw = await marketDataApi.getVolatilityDashboard();
      return unwrapVolatilityPayload(raw);
    },
    staleTime: 60_000,
    refetchInterval: 5 * 60_000,
  });
}
