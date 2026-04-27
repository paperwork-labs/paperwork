/**
 * useMonteCarlo
 * =============
 *
 * Thin TanStack Query mutation around ``runMonteCarlo``. We use a
 * mutation (not a query) because the simulation is parameterized by a
 * variable-sized trade-returns array; treating it as a query would
 * force us to encode the whole array in the cache key, which is both
 * wasteful and makes manual re-runs (the "Run again with new seed"
 * UX) awkward.
 *
 * No silent fallbacks here -- the caller is expected to read
 * ``isPending``, ``isError``, ``error``, and ``data`` and render the
 * four states explicitly.
 */
import { useMutation } from '@tanstack/react-query';

import {
  type MonteCarloRequest,
  type MonteCarloResponse,
  runMonteCarlo,
} from '@/services/backtest';

export interface UseMonteCarloOptions {
  onSuccess?: (data: MonteCarloResponse) => void;
  onError?: (error: unknown) => void;
}

export function useMonteCarlo(options: UseMonteCarloOptions = {}) {
  return useMutation<MonteCarloResponse, unknown, MonteCarloRequest>({
    mutationFn: runMonteCarlo,
    onSuccess: options.onSuccess,
    onError: options.onError,
  });
}
