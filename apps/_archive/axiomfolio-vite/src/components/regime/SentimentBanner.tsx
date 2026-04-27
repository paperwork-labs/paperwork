import * as React from 'react';
import { AlertCircle } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';

import { useSentimentComposite } from '@/hooks/useSentimentComposite';

const REGIME_LABELS: Record<string, string> = {
  R1: 'Bull',
  R2: 'Bull Extended',
  R3: 'Chop',
  R4: 'Bear Rally',
  R5: 'Bear',
};

const REGIME_SURFACE: Record<string, string> = {
  R1: 'rgb(var(--regime-tint-r1) / 0.16)',
  R2: 'rgb(var(--regime-tint-r2) / 0.16)',
  R3: 'rgb(var(--regime-tint-r3) / 0.18)',
  R4: 'rgb(var(--regime-tint-r4) / 0.16)',
  R5: 'rgb(var(--regime-tint-r5) / 0.16)',
};

function DataMissing() {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span
          className="cursor-help border-b border-dotted border-muted-foreground/60 tabular-nums"
          aria-label="Data unavailable"
        >
          —
        </span>
      </TooltipTrigger>
      <TooltipContent side="bottom">Data unavailable</TooltipContent>
    </Tooltip>
  );
}

function formatAaiiNet(net: number): string {
  if (Number.isInteger(net)) {
    return `${net >= 0 ? '+' : ''}${net}`;
  }
  return `${net >= 0 ? '+' : ''}${net.toFixed(1)}`;
}

export const SentimentBanner: React.FC = () => {
  const { data, isPending, isError, error, refetch, isRefetching } = useSentimentComposite();

  const surfaceStyle: React.CSSProperties = React.useMemo(() => {
    const st = data?.regime?.state;
    if (st && REGIME_SURFACE[st]) {
      return { backgroundColor: REGIME_SURFACE[st] };
    }
    return { backgroundColor: 'rgb(var(--muted) / 0.45)' };
  }, [data?.regime?.state]);

  if (isPending) {
    return (
      <div
        className="h-9 w-full max-w-4xl animate-pulse rounded-md border border-border/60 bg-muted/80"
        aria-hidden
        role="status"
        aria-label="Loading sentiment"
      />
    );
  }

  if (isError) {
    const message = error instanceof Error ? error.message : 'Request failed';
    return (
      <div
        className="flex h-9 max-w-4xl flex-wrap items-center gap-2 rounded-md border border-destructive/30 bg-destructive/10 px-3 text-xs"
        role="alert"
      >
        <AlertCircle className="size-3.5 shrink-0 text-destructive" aria-hidden />
        <span className="text-foreground">Sentiment unavailable</span>
        <span className="text-muted-foreground">·</span>
        <span className="min-w-0 truncate text-muted-foreground">{message}</span>
        <Button
          type="button"
          size="sm"
          variant="ghost"
          className="h-7 px-2 text-xs"
          onClick={() => void refetch()}
          disabled={isRefetching}
        >
          {isRefetching ? '…' : 'Retry'}
        </Button>
      </div>
    );
  }

  const vix = data?.vix ?? null;
  const aaii = data?.aaii ?? null;
  const fear = data?.fear_greed ?? null;
  const regime = data?.regime ?? null;

  const regimeName = regime?.state ? (REGIME_LABELS[regime.state] ?? regime.state) : null;
  const regimeSegment =
    regimeName != null && regime?.state ? (
      <span className="font-medium tabular-nums">
        {regime.state} — {regimeName}
      </span>
    ) : (
      <span className="inline-flex items-center gap-1 font-medium">
        Regime <DataMissing />
      </span>
    );

  const vixSegment =
    vix != null ? (
      <span>
        VIX <span className="tabular-nums">{vix.toFixed(1)}</span>
      </span>
    ) : (
      <span className="inline-flex items-center gap-1">
        VIX <DataMissing />
      </span>
    );

  const aaiiSegment =
    aaii != null ? (
      <span>
        AAII {formatAaiiNet(aaii.net)}
      </span>
    ) : (
      <span className="inline-flex items-center gap-1">
        AAII <DataMissing />
      </span>
    );

  const fgSegment =
    fear != null ? (
      <span>
        F&G <span className="tabular-nums">{fear.value}</span>
        {fear.label ? (
          <span className="text-muted-foreground"> {fear.label}</span>
        ) : null}
      </span>
    ) : (
      <span className="inline-flex items-center gap-1">
        F&G <DataMissing />
      </span>
    );

  return (
    <TooltipProvider delayDuration={200}>
      <div
        className={cn(
          'flex h-9 max-w-4xl items-center border border-border/50 px-3 text-xs leading-none',
          'text-foreground shadow-sm',
        )}
        style={surfaceStyle}
        data-regime={regime?.state ?? undefined}
        aria-label="Market sentiment and regime"
      >
        <p className="flex min-w-0 flex-1 flex-wrap items-center gap-x-2 gap-y-1">
          {regimeSegment}
          <span className="text-muted-foreground" aria-hidden>
            ·
          </span>
          {vixSegment}
          <span className="text-muted-foreground" aria-hidden>
            ·
          </span>
          {aaiiSegment}
          <span className="text-muted-foreground" aria-hidden>
            ·
          </span>
          {fgSegment}
        </p>
      </div>
    </TooltipProvider>
  );
};

export default SentimentBanner;
