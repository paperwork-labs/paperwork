import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { AlertCircle } from 'lucide-react';

import api from '@/services/api';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';

export const isExternalSignalsViteEnabled = import.meta.env.VITE_ENABLE_EXTERNAL_SIGNALS === 'true';
const externalSignalsEnabled = isExternalSignalsViteEnabled;

export interface ExternalSignalItem {
  id: number;
  source: string;
  signal_type: string;
  signal_date: string;
}

interface ExternalSignalsResponse {
  items: ExternalSignalItem[];
}

export interface ExternalSignalsParentBatch {
  parentLoading: boolean;
  parentError: boolean;
  items: ExternalSignalItem[];
  onRefetch: () => void;
}

/**
 * When `VITE_ENABLE_EXTERNAL_SIGNALS` is true, shows up to two recent auxiliary
 * external-signal badges for the symbol (Finviz/Zacks scaffolds on the backend).
 * Pass `parentBatch` from a parent to avoid N per-symbol API calls.
 */
export const ExternalSignalsChip: React.FC<{
  symbol: string;
  parentBatch?: ExternalSignalsParentBatch;
}> = ({ symbol, parentBatch }) => {
  const self = useQuery<ExternalSignalsResponse>({
    queryKey: ['signals-external', symbol],
    enabled: externalSignalsEnabled && parentBatch === undefined,
    queryFn: async () => {
      const params = new URLSearchParams({ symbol, days: '7' });
      const res = await api.get<ExternalSignalsResponse>(`/signals/external?${params.toString()}`);
      return res.data;
    },
  });
  if (!externalSignalsEnabled) {
    return null;
  }

  if (parentBatch !== undefined) {
    if (parentBatch.parentLoading) {
      return (
        <div data-testid="external-signals-loading" className="pt-0.5">
          <Skeleton className="h-5 w-36" />
        </div>
      );
    }
    if (parentBatch.parentError) {
      return (
        <div
          data-testid="external-signals-error"
          className="inline-flex items-center gap-1 pt-0.5 text-xs text-destructive"
        >
          <AlertCircle className="size-3.5 shrink-0" aria-hidden />
          <span>External context failed to load.</span>
          <Button
            type="button"
            variant="link"
            className="h-auto p-0 text-xs"
            onClick={() => void parentBatch.onRefetch()}
          >
            Retry
          </Button>
        </div>
      );
    }
    const top = parentBatch.items.slice(0, 2);
    if (top.length === 0) {
      return (
        <p data-testid="external-signals-empty" className="pt-0.5 text-xs text-muted-foreground">
          No recent external context
        </p>
      );
    }
    return (
      <div data-testid="external-signals-data" className="flex flex-wrap items-center gap-1 pt-0.5">
        {top.map((i) => (
          <Badge key={i.id} variant="secondary" className="font-mono text-[0.7rem] font-normal">
            {i.source}: {i.signal_type}
          </Badge>
        ))}
      </div>
    );
  }

  if (self.isLoading) {
    return (
      <div data-testid="external-signals-loading" className="pt-0.5">
        <Skeleton className="h-5 w-36" />
      </div>
    );
  }
  if (self.isError) {
    return (
      <div
        data-testid="external-signals-error"
        className="inline-flex items-center gap-1 pt-0.5 text-xs text-destructive"
      >
        <AlertCircle className="size-3.5 shrink-0" aria-hidden />
        <span>External context failed to load.</span>
        <Button type="button" variant="link" className="h-auto p-0 text-xs" onClick={() => void self.refetch()}>
          Retry
        </Button>
      </div>
    );
  }
  const top = (self.data?.items ?? []).slice(0, 2);
  if (top.length === 0) {
    return (
      <p data-testid="external-signals-empty" className="pt-0.5 text-xs text-muted-foreground">
        No recent external context
      </p>
    );
  }
  return (
    <div data-testid="external-signals-data" className="flex flex-wrap items-center gap-1 pt-0.5">
      {top.map((i) => (
        <Badge key={i.id} variant="secondary" className="font-mono text-[0.7rem] font-normal">
          {i.source}: {i.signal_type}
        </Badge>
      ))}
    </div>
  );
};
