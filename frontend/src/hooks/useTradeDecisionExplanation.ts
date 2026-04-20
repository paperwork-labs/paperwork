import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { tradeDecisionApi } from '../services/tradeDecision';
import type { TradeDecisionExplanation } from '../types/tradeDecision';

const QUERY_KEY_PREFIX = 'tradeDecisionExplanation';

export function tradeDecisionQueryKey(orderId: number) {
  return [QUERY_KEY_PREFIX, orderId] as const;
}

export interface UseTradeDecisionExplanationOptions {
  orderId: number | null;
  enabled?: boolean;
}

/**
 * Fetch (and cache) the explanation row for one order.
 *
 * The hook follows the loading / error / empty / data four-state
 * convention required by the no-silent-fallback rule: callers branch on
 * `isLoading`, `isError`, and `data` explicitly rather than coalescing
 * to a default.
 */
export function useTradeDecisionExplanation({
  orderId,
  enabled = true,
}: UseTradeDecisionExplanationOptions) {
  return useQuery<TradeDecisionExplanation>({
    queryKey: orderId == null ? [QUERY_KEY_PREFIX, 'noop'] : tradeDecisionQueryKey(orderId),
    queryFn: () => {
      if (orderId == null) {
        throw new Error('orderId is required');
      }
      return tradeDecisionApi.get(orderId);
    },
    enabled: enabled && orderId != null,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });
}

export function useRegenerateTradeDecisionExplanation(orderId: number | null) {
  const qc = useQueryClient();
  return useMutation<TradeDecisionExplanation, Error, void>({
    mutationFn: () => {
      if (orderId == null) {
        throw new Error('orderId is required');
      }
      return tradeDecisionApi.regenerate(orderId);
    },
    onSuccess: (data) => {
      if (orderId != null) {
        qc.setQueryData(tradeDecisionQueryKey(orderId), data);
      }
    },
  });
}
