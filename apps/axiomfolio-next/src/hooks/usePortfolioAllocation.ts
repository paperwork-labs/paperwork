/**
 * `usePortfolioAllocation` — hook backing the `/portfolio/allocation` page.
 *
 * Wraps the `GET /api/v1/portfolio/allocation` aggregator in TanStack Query.
 * The backend returns `{group_by, total_value, generated_at, groups[]}` with
 * already-percentaged numbers so the chart layer is rendering only.
 *
 * The hook deliberately does NOT collapse loading / error / empty into one
 * boolean -- callers split those four states explicitly per the design
 * system rule (`no-silent-fallback.mdc`).
 */
import { useQuery } from '@tanstack/react-query';

import { portfolioApi } from '../services/api';

export type AllocationGroupBy = 'sector' | 'asset_class' | 'account';

export interface AllocationHolding {
  symbol: string;
  value: number;
  percentage: number;
}

export interface AllocationGroup {
  key: string;
  label: string;
  total_value: number;
  percentage: number;
  holdings: AllocationHolding[];
}

export interface AllocationPayload {
  group_by: AllocationGroupBy;
  total_value: number;
  generated_at: string;
  groups: AllocationGroup[];
}

export function usePortfolioAllocation(groupBy: AllocationGroupBy) {
  return useQuery<AllocationPayload>({
    queryKey: ['portfolioAllocation', groupBy],
    queryFn: async () => {
      const raw = (await portfolioApi.getAllocation(groupBy)) as unknown;
      // The route returns the payload as the raw response body; axios + the
      // request queue already drop down to `response.data`. Defensively
      // unwrap a single legacy `{data: {...}}` envelope just in case a
      // gateway middleware re-wraps it later -- the keys we depend on
      // (`groups`, `total_value`) are unique enough to detect.
      const body = raw as Partial<AllocationPayload> & {
        data?: Partial<AllocationPayload>;
      };
      const settled =
        body?.groups !== undefined ? (body as AllocationPayload) : (body?.data as AllocationPayload);
      if (!settled || !Array.isArray(settled.groups)) {
        throw new Error('Allocation response missing `groups` array');
      }
      return settled;
    },
    staleTime: 60_000,
  });
}
