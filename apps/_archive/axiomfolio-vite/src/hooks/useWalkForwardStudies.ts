/**
 * useWalkForwardStudies — TanStack hooks for the walk-forward optimizer.
 *
 * Three flavours:
 *
 * 1. `useWalkForwardStudies()` — list of studies for the current user. Cached
 *    for 30s. Invalidated automatically after `useCreateWalkForwardStudy`.
 * 2. `useWalkForwardStudy(id)` — one study with adaptive polling: 1Hz while
 *    `RUNNING` / `PENDING`, off when `COMPLETED` / `FAILED`. The
 *    `refetchInterval` callback consults the latest cached payload so a
 *    completed study never wastes a network round-trip.
 * 3. `useStrategyOptions()` — small dropdown source (strategies + objectives
 *    + regimes). Cached for 5 minutes; almost never changes.
 *
 * Naming follows the rest of the codebase (`use<Domain><Verb>`).
 */

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from '@tanstack/react-query';

import {
  createStudy,
  getStudy,
  listStrategyOptions,
  listStudies,
  type CreateStudyPayload,
  type StudyDetail,
  type StudySummary,
  type StrategyOptions,
} from '../services/backtest';

const STUDIES_KEY = ['walk-forward', 'studies'] as const;
const STUDY_KEY = (id: number) => ['walk-forward', 'study', id] as const;
const STRATEGIES_KEY = ['walk-forward', 'strategies'] as const;

export function useWalkForwardStudies(): UseQueryResult<StudySummary[]> {
  return useQuery<StudySummary[]>({
    queryKey: STUDIES_KEY,
    queryFn: () => listStudies(50),
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });
}

export function useWalkForwardStudy(
  id: number | null,
): UseQueryResult<StudyDetail> {
  return useQuery<StudyDetail>({
    queryKey: id ? STUDY_KEY(id) : ['walk-forward', 'study', 'idle'],
    queryFn: () => {
      if (!id) {
        // Should never run — `enabled` below guards against this — but keep
        // the type checker happy without an `as` cast.
        throw new Error('useWalkForwardStudy called with null id');
      }
      return getStudy(id);
    },
    enabled: id !== null,
    // Adaptive polling: 1Hz while still working, otherwise off. The function
    // form lets TanStack stop polling the moment a poll returns COMPLETED
    // without us having to imperatively unsubscribe.
    refetchInterval: (query) => {
      const data = query.state.data as StudyDetail | undefined;
      if (!data) return 1000;
      return data.status === 'running' || data.status === 'pending'
        ? 1000
        : false;
    },
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: false,
  });
}

export function useStrategyOptions(): UseQueryResult<StrategyOptions> {
  return useQuery<StrategyOptions>({
    queryKey: STRATEGIES_KEY,
    queryFn: listStrategyOptions,
    staleTime: 1000 * 60 * 5,
    refetchOnWindowFocus: false,
  });
}

export function useCreateWalkForwardStudy(): UseMutationResult<
  StudyDetail,
  unknown,
  CreateStudyPayload
> {
  const qc = useQueryClient();
  return useMutation<StudyDetail, unknown, CreateStudyPayload>({
    mutationFn: createStudy,
    onSuccess: (study) => {
      // Insert the freshly created row into the list cache so the user sees
      // their new study without waiting for the 30s list refetch.
      qc.setQueryData<StudySummary[]>(STUDIES_KEY, (old) => {
        const summary: StudySummary = {
          id: study.id,
          name: study.name,
          strategy_class: study.strategy_class,
          objective: study.objective,
          status: study.status,
          n_splits: study.n_splits,
          n_trials: study.n_trials,
          total_trials: study.total_trials,
          regime_filter: study.regime_filter,
          best_score: study.best_score,
          created_at: study.created_at,
          started_at: study.started_at,
          completed_at: study.completed_at,
        };
        return old ? [summary, ...old] : [summary];
      });
      qc.setQueryData<StudyDetail>(STUDY_KEY(study.id), study);
    },
  });
}
