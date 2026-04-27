import React from 'react';
import { Loader2 } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';
import type { BacktestValidationStatus, BacktestValidationSummary } from '../../types/strategy';

const STATUS_BADGE_CLASS: Record<BacktestValidationStatus, string> = {
  PASSED: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-800 dark:text-emerald-200',
  FAILED: 'border-destructive/40 bg-destructive/10 text-destructive',
  VETOED: 'border-orange-500/40 bg-orange-500/10 text-orange-900 dark:text-orange-200',
  PENDING: 'border-border bg-muted/60 text-muted-foreground',
  RUNNING: 'border-blue-500/40 bg-blue-500/10 text-blue-900 dark:text-blue-200',
};

function formatSharpe(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return '—';
  return v.toFixed(2);
}

function formatDrawdownPct(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return '—';
  return `${v.toFixed(2)}%`;
}

function formatWinRate(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return '—';
  const pct = v <= 1 && v >= 0 ? v * 100 : v;
  return `${pct.toFixed(1)}%`;
}

function normalizeValidation(
  raw: BacktestValidationSummary | null | undefined
): BacktestValidationSummary {
  if (!raw || typeof raw.status !== 'string') {
    return {
      status: 'PENDING',
      sharpe_ratio: null,
      max_drawdown_pct: null,
      win_rate: null,
    };
  }
  const allowed: BacktestValidationStatus[] = ['PENDING', 'RUNNING', 'PASSED', 'FAILED', 'VETOED'];
  const status = allowed.includes(raw.status as BacktestValidationStatus)
    ? (raw.status as BacktestValidationStatus)
    : 'PENDING';
  return {
    status,
    sharpe_ratio: raw.sharpe_ratio ?? null,
    max_drawdown_pct: raw.max_drawdown_pct ?? null,
    win_rate: raw.win_rate ?? null,
  };
}

export interface BacktestStatusBadgeProps {
  validation?: BacktestValidationSummary | null;
  className?: string;
  /** Prevents parent row/card click when interacting with the badge. */
  stopRowClick?: boolean;
}

export function BacktestStatusBadge({ validation, className, stopRowClick }: BacktestStatusBadgeProps) {
  const v = normalizeValidation(validation);
  const label =
    v.status === 'PENDING'
      ? 'Backtest: Pending'
      : v.status === 'RUNNING'
        ? 'Backtest: Running'
        : v.status === 'PASSED'
          ? 'Backtest: Passed'
          : v.status === 'FAILED'
            ? 'Backtest: Failed'
            : 'Backtest: Vetoed';

  const detail = (
    <div className="flex min-w-[10rem] flex-col gap-1 text-left font-normal">
      <p className="font-semibold text-background">Validation metrics</p>
      <p className="text-background/90">Sharpe: {formatSharpe(v.sharpe_ratio)}</p>
      <p className="text-background/90">Max drawdown: {formatDrawdownPct(v.max_drawdown_pct)}</p>
      <p className="text-background/90">Win rate: {formatWinRate(v.win_rate)}</p>
    </div>
  );

  const badge = (
    <Badge
      variant="outline"
      className={cn(
        'h-5 gap-1 text-[10px] font-medium',
        STATUS_BADGE_CLASS[v.status],
        v.status === 'RUNNING' && 'pr-1.5',
        className
      )}
    >
      {v.status === 'RUNNING' ? (
        <Loader2 className="size-3 shrink-0 animate-spin" aria-hidden />
      ) : null}
      {v.status}
    </Badge>
  );

  const trigger = (
    <button
      type="button"
      className={cn(
        'inline-flex cursor-help rounded-md border-0 bg-transparent p-0 text-left',
        'focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:outline-none'
      )}
      aria-label={label}
      onClick={(e) => {
        if (stopRowClick) e.stopPropagation();
      }}
      onPointerDown={(e) => {
        if (stopRowClick) e.stopPropagation();
      }}
    >
      {badge}
    </button>
  );

  return (
    <Tooltip delayDuration={200}>
      <TooltipTrigger asChild>{trigger}</TooltipTrigger>
      <TooltipContent side="bottom" className="max-w-xs">
        {detail}
      </TooltipContent>
    </Tooltip>
  );
}
