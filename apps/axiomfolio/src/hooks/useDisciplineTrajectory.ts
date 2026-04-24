/**
 * `useDisciplineTrajectory` — GET /api/v1/portfolio/discipline-trajectory.
 *
 * Callers must branch on loading / error / empty / data (see `no-silent-fallback.mdc`).
 */

import { useQuery } from '@tanstack/react-query';

import { portfolioApi } from '@/services/api';

export interface DisciplineTrajectoryAnchors {
  unleveraged_ceiling: number;
  leveraged_ceiling: number;
  speculative_ceiling: number;
}

export interface DisciplineTrajectoryByAccountRow {
  account_id: string;
  broker: string;
  account_number_suffix: string;
  starting_equity: number | null;
  current_equity: number;
}

export interface DisciplineTrajectoryPayload {
  account_id: string | null;
  aggregate: boolean;
  starting_equity: number | null;
  current_equity: number;
  anchors: DisciplineTrajectoryAnchors | null;
  projected_year_end: number | null;
  trend: 'up' | 'flat' | 'down';
  as_of: string;
  by_account: DisciplineTrajectoryByAccountRow[] | null;
}

function parsePayload(raw: unknown): DisciplineTrajectoryPayload {
  const r = raw as Record<string, unknown> | null | undefined;
  const inner =
    r && typeof r.current_equity === 'number' && typeof r.aggregate === 'boolean'
      ? r
      : ((r?.data as Record<string, unknown> | undefined) ?? undefined);
  if (!inner || typeof inner.current_equity !== 'number' || typeof inner.aggregate !== 'boolean') {
    throw new Error('discipline-trajectory: invalid payload');
  }
  return inner as unknown as DisciplineTrajectoryPayload;
}

export function useDisciplineTrajectory(params: { accountId?: number; aggregate?: boolean }) {
  const aggregate = Boolean(params.aggregate);
  return useQuery<DisciplineTrajectoryPayload>({
    queryKey: ['disciplineTrajectory', params.accountId ?? 'default', aggregate],
    queryFn: async () => {
      const raw = await portfolioApi.getDisciplineTrajectory({
        accountId: params.accountId,
        aggregate,
      });
      return parsePayload(raw);
    },
    staleTime: 60_000,
  });
}
