import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import toast from 'react-hot-toast';

import api, { handleApiError } from '@/services/api';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

export type Sleeve = 'active' | 'conviction';

export const SLEEVE_OPTIONS: ReadonlyArray<{
  value: Sleeve;
  label: string;
  description: string;
}> = [
  {
    value: 'active',
    label: 'Active',
    description: 'Short-dated, swing, daily attention.',
  },
  {
    value: 'conviction',
    label: 'Conviction',
    description: 'Multi-year hold, monthly review.',
  },
];

interface PositionSleeveToggleProps {
  positionId: number;
  symbol: string;
  currentSleeve: Sleeve | null | undefined;
  /**
   * Query keys to invalidate on success so downstream lists (positions
   * table, by-sleeve bucket view) re-fetch. Keep this explicit per
   * callsite rather than blanket-invalidating to avoid stampedes.
   */
  invalidateKeys?: ReadonlyArray<ReadonlyArray<unknown>>;
  disabled?: boolean;
  className?: string;
}

type ToggleStatus = 'idle' | 'optimistic' | 'error' | 'success';

interface PatchResponse {
  id: number;
  symbol: string;
  sleeve: Sleeve;
}

/**
 * Row-level toggle that flips a position between the Active and
 * Conviction sleeves.
 *
 * Four explicit states (per no-silent-fallback rule):
 * - `idle`       — settled, showing the server's current sleeve
 * - `optimistic` — mutation in-flight, UI already shows the target
 * - `error`      — mutation failed, UI rolled back to the pre-flight
 *                  value and emitted a `toast.error`
 * - `success`    — mutation returned, refreshed from the server payload
 */
export function PositionSleeveToggle({
  positionId,
  symbol,
  currentSleeve,
  invalidateKeys,
  disabled = false,
  className,
}: PositionSleeveToggleProps) {
  const queryClient = useQueryClient();
  const serverSleeve: Sleeve = currentSleeve ?? 'active';
  const [optimisticSleeve, setOptimisticSleeve] = useState<Sleeve | null>(null);
  const [status, setStatus] = useState<ToggleStatus>('idle');

  const displaySleeve: Sleeve = optimisticSleeve ?? serverSleeve;

  const mutation = useMutation<
    PatchResponse,
    unknown,
    Sleeve,
    { previous: Sleeve }
  >({
    mutationFn: async (sleeve) => {
      const res = await api.patch<PatchResponse>(
        `/positions/${positionId}/sleeve`,
        { sleeve }
      );
      return res.data;
    },
    onMutate: async (sleeve) => {
      setStatus('optimistic');
      setOptimisticSleeve(sleeve);
      return { previous: serverSleeve };
    },
    onError: (err, _sleeve, _ctx) => {
      setStatus('error');
      // Roll back to the pre-flight server value. We set it to null so
      // the display falls through to `serverSleeve` (the prop). The
      // previous value is in `ctx.previous` but equals `serverSleeve`.
      setOptimisticSleeve(null);
      toast.error(
        `Failed to update ${symbol} sleeve: ${handleApiError(err)}`
      );
    },
    onSuccess: (data) => {
      setStatus('success');
      // Keep the optimistic override pinned to the server-confirmed
      // value. When the parent re-renders with the refreshed prop the
      // two will match; until then we show the confirmed sleeve.
      setOptimisticSleeve(data.sleeve);
      toast.success(
        data.sleeve === 'conviction'
          ? `${symbol} moved to Conviction`
          : `${symbol} moved to Active`
      );
      if (invalidateKeys && invalidateKeys.length > 0) {
        for (const key of invalidateKeys) {
          queryClient.invalidateQueries({
            queryKey: [...key] as unknown[],
          });
        }
      }
    },
  });

  const handleSelect = (next: Sleeve) => {
    if (disabled || mutation.isPending) return;
    if (next === displaySleeve) return;
    mutation.mutate(next);
  };

  return (
    <div
      role="group"
      aria-label={`Sleeve for ${symbol}`}
      data-status={status}
      className={cn(
        'inline-flex items-center gap-1 rounded-md border border-border bg-background p-0.5 text-xs',
        className
      )}
    >
      {SLEEVE_OPTIONS.map((opt) => {
        const selected = displaySleeve === opt.value;
        return (
          <Button
            key={opt.value}
            type="button"
            size="xs"
            variant={selected ? 'secondary' : 'ghost'}
            aria-pressed={selected}
            disabled={disabled || mutation.isPending}
            title={opt.description}
            onClick={() => handleSelect(opt.value)}
            className={cn(
              'px-2',
              selected ? 'font-semibold' : 'text-muted-foreground'
            )}
          >
            {opt.label}
          </Button>
        );
      })}
    </div>
  );
}

export default PositionSleeveToggle;
