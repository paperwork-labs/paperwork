import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { marketDataApi } from '../../services/api';
import { REGIME_HEX } from '../../constants/chart';
import { cn } from '@/lib/utils';

export interface RegimeData {
  regime_state: string;
  composite_score: number;
  as_of_date: string;
  vix_spot: number | null;
  vix3m_vix_ratio: number | null;
  vvix_vix_ratio: number | null;
  nh_nl: number | null;
  pct_above_200d: number | null;
  pct_above_50d: number | null;
  cash_floor_pct: number | null;
  max_equity_exposure_pct: number | null;
  regime_multiplier: number | null;
}

const REGIME_LABELS: Record<string, string> = {
  R1: 'Bull',
  R2: 'Bull Extended',
  R3: 'Chop',
  R4: 'Bear Rally',
  R5: 'Bear',
};

const RegimeBanner: React.FC = () => {
  const { data, isPending, isError, error } = useQuery<RegimeData | null>({
    queryKey: ['regime-current'],
    queryFn: async (): Promise<RegimeData | null> => {
      const row = await marketDataApi.getCurrentRegime();
      return (row as RegimeData | null) ?? null;
    },
    refetchInterval: 5 * 60 * 1000,
    staleTime: 2 * 60 * 1000,
  });

  if (isPending) {
    return (
      <div className="mb-3 rounded-lg border border-border bg-card p-3">
        <p className="text-xs text-muted-foreground">Loading regime data...</p>
      </div>
    );
  }

  if (isError) {
    const detail =
      error instanceof Error
        ? error.message
        : typeof error === 'object' &&
            error !== null &&
            'message' in error &&
            typeof (error as { message: unknown }).message === 'string'
          ? (error as { message: string }).message
          : 'Request failed.';
    return (
      <div className="mb-3 rounded-lg border border-destructive/30 bg-destructive/10 p-3">
        <p className="text-xs text-destructive">Failed to load regime data.</p>
        <p className="mt-1 text-xs text-muted-foreground">{detail}</p>
      </div>
    );
  }

  if (data == null) {
    return (
      <div className="mb-3 rounded-lg border border-border bg-card p-3">
        <p className="text-xs text-muted-foreground">
          No regime data yet. Open System Status, expand Operator Actions, and run &quot;Compute
          Market Regime&quot; when the pipeline is ready.
        </p>
      </div>
    );
  }

  const color = REGIME_HEX[data.regime_state] || '#718096';
  const label = REGIME_LABELS[data.regime_state] || data.regime_state;

  return (
    <div
      className="mb-3 rounded-lg border-2 bg-card p-3"
      style={{ borderColor: color }}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <div
              className="size-3.5 shrink-0 rounded-sm"
              style={{ backgroundColor: color }}
              aria-hidden
            />
            <span className="text-base font-bold">{data.regime_state}</span>
            <span
              className={cn(
                'inline-flex h-5 shrink-0 items-center rounded-full border px-2 py-0 text-xs font-medium',
                'border-transparent'
              )}
              style={{
                backgroundColor: `${color}22`,
                color,
              }}
            >
              {label}
            </span>
          </div>
          <p className="text-sm text-muted-foreground">
            Composite:{' '}
            <span className="font-semibold text-foreground">
              {data.composite_score?.toFixed(1)}
            </span>
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-4">
          {data.vix_spot != null && (
            <div className="flex flex-col items-center gap-0">
              <span className="text-[10px] text-muted-foreground">VIX</span>
              <span className="text-xs font-semibold">{data.vix_spot.toFixed(1)}</span>
            </div>
          )}
          {data.vix3m_vix_ratio != null && (
            <div className="flex flex-col items-center gap-0">
              <span className="text-[10px] text-muted-foreground">VIX3M/VIX</span>
              <span className="text-xs font-semibold">{data.vix3m_vix_ratio.toFixed(2)}</span>
            </div>
          )}
          {data.nh_nl != null && (
            <div className="flex flex-col items-center gap-0">
              <span className="text-[10px] text-muted-foreground">NH−NL</span>
              <span className="text-xs font-semibold">{data.nh_nl}</span>
            </div>
          )}
          {data.pct_above_200d != null && (
            <div className="flex flex-col items-center gap-0">
              <span className="text-[10px] text-muted-foreground">&gt;200D</span>
              <span className="text-xs font-semibold">{data.pct_above_200d.toFixed(0)}%</span>
            </div>
          )}
          {data.pct_above_50d != null && (
            <div className="flex flex-col items-center gap-0">
              <span className="text-[10px] text-muted-foreground">&gt;50D</span>
              <span className="text-xs font-semibold">{data.pct_above_50d.toFixed(0)}%</span>
            </div>
          )}
          {data.regime_multiplier != null && (
            <div className="flex flex-col items-center gap-0">
              <span className="text-[10px] text-muted-foreground">Size Mult</span>
              <span className="text-xs font-semibold">{data.regime_multiplier.toFixed(2)}×</span>
            </div>
          )}
          {data.max_equity_exposure_pct != null && (
            <div className="flex flex-col items-center gap-0">
              <span className="text-[10px] text-muted-foreground">Max Eq</span>
              <span className="text-xs font-semibold">{data.max_equity_exposure_pct.toFixed(0)}%</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default RegimeBanner;
