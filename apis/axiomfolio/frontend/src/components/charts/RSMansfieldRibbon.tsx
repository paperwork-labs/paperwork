/**
 * Thin RS Mansfield strip: baseline 0, green fill above (outperforming),
 * rose fill below (underperforming). Canvas colors via cssVarToCanvasColor.
 */
import * as React from 'react';
import {
  BaselineSeries,
  createChart,
  LineStyle,
  type IChartApi,
  type ISeriesApi,
  type Time,
  type UTCTimestamp,
} from 'lightweight-charts';

import { ErrorState } from '@/components/ui/ErrorState';
import { Skeleton } from '@/components/ui/skeleton';
import type { RSMansfieldPoint } from '@/hooks/useRSMansfield';
import { cssVarToCanvasColor } from '@/lib/chartColors';
import { resolveThemeColors, withAlpha } from '@/lib/holdingChart/themeColors';
import { cn } from '@/lib/utils';

const PALETTE_CHANGE_EVENT = 'axiomfolio:color-palette-change';
const SUCCESS_FALLBACK = 'rgb(22, 163, 74)';
const DANGER_FALLBACK = 'rgb(244, 63, 94)';

export interface RSMansfieldRibbonProps {
  isPending: boolean;
  isError: boolean;
  error: Error | null;
  onRetry: () => void;
  /** Finite points from API; empty after successful fetch means unavailable. */
  points: RSMansfieldPoint[];
  benchmark?: string;
  height?: number;
  className?: string;
}

const DEFAULT_H = 88;

function toUtcDaySec(isoDate: string): UTCTimestamp | null {
  const t = String(isoDate).slice(0, 10);
  if (t.length < 10) return null;
  const ms = Date.parse(`${t}T00:00:00Z`);
  if (!Number.isFinite(ms)) return null;
  return Math.floor(ms / 1000) as UTCTimestamp;
}

export function RSMansfieldRibbon({
  isPending,
  isError,
  error,
  onRetry,
  points,
  benchmark = 'SPY',
  height = DEFAULT_H,
  className,
}: RSMansfieldRibbonProps) {
  const containerRef = React.useRef<HTMLDivElement | null>(null);
  const chartRef = React.useRef<IChartApi | null>(null);
  const seriesRef = React.useRef<ISeriesApi<'Baseline'> | null>(null);
  const [w, setW] = React.useState(0);

  const chartData = React.useMemo(() => {
    const out: { time: UTCTimestamp; value: number }[] = [];
    for (const p of points) {
      const sec = toUtcDaySec(p.date);
      if (sec == null) continue;
      const v = Number(p.value);
      if (!Number.isFinite(v)) continue;
      out.push({ time: sec, value: v });
    }
    return out.sort((a, b) => a.time - b.time);
  }, [points]);

  const applyColors = React.useCallback(() => {
    const s = seriesRef.current;
    if (!s) return;
    const up1 = withAlpha(cssVarToCanvasColor('--chart-success', SUCCESS_FALLBACK), 0.35);
    const up2 = withAlpha(cssVarToCanvasColor('--chart-success', SUCCESS_FALLBACK), 0.08);
    const upLine = cssVarToCanvasColor('--chart-success', SUCCESS_FALLBACK);
    const dn1 = withAlpha(cssVarToCanvasColor('--chart-danger', DANGER_FALLBACK), 0.32);
    const dn2 = withAlpha(cssVarToCanvasColor('--chart-danger', DANGER_FALLBACK), 0.07);
    const dnLine = cssVarToCanvasColor('--chart-danger', DANGER_FALLBACK);
    s.applyOptions({
      baseValue: { type: 'price', price: 0 },
      topFillColor1: up1,
      topFillColor2: up2,
      topLineColor: upLine,
      bottomFillColor1: dn1,
      bottomFillColor2: dn2,
      bottomLineColor: dnLine,
    });
  }, []);

  React.useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const measure = () => setW(Math.floor(el.clientWidth));
    measure();
    const ro = new ResizeObserver(() => measure());
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  React.useEffect(() => {
    if (isPending || isError) return;
    if (chartData.length === 0) return;
    const node = containerRef.current;
    if (!node || w <= 0) return;

    const t = resolveThemeColors();
    const chart = createChart(node, {
      autoSize: false,
      width: w,
      height,
      layout: {
        background: { color: 'transparent' },
        textColor: t.text,
        fontFamily:
          "'Inter Variable', ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, sans-serif",
      },
      grid: {
        vertLines: { color: t.gridLine, style: LineStyle.Dotted },
        horzLines: { color: t.gridLine, style: LineStyle.Dotted },
      },
      rightPriceScale: { borderVisible: false, scaleMargins: { top: 0.08, bottom: 0.08 } },
      timeScale: { borderVisible: false, timeVisible: true, secondsVisible: false },
      crosshair: { mode: 0 },
    });
    chartRef.current = chart;

    seriesRef.current = chart.addSeries(BaselineSeries, {
      baseValue: { type: 'price', price: 0 },
      lineWidth: 1,
      lineStyle: LineStyle.Solid,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
      priceFormat: { type: 'price', precision: 1, minMove: 0.1 },
    });
    applyColors();
    seriesRef.current.setData(
      chartData.map((p) => ({
        time: p.time as Time,
        value: p.value,
      })),
    );
    try {
      chart.timeScale().fitContent();
    } catch {
      // ignore
    }

    return () => {
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, [isPending, isError, chartData, height, w, applyColors]);

  const rw = w > 0 ? w : containerRef.current?.clientWidth ?? 0;
  React.useEffect(() => {
    if (chartRef.current && rw > 0) {
      chartRef.current.applyOptions({ width: Math.floor(rw), height });
    }
  }, [height, rw]);

  React.useEffect(() => {
    if (typeof window === 'undefined') return;
    const fn = () => {
      if (!chartRef.current) return;
      const tc = resolveThemeColors();
      chartRef.current.applyOptions({
        layout: { textColor: tc.text },
        grid: {
          vertLines: { color: tc.gridLine },
          horzLines: { color: tc.gridLine },
        },
      });
      applyColors();
    };
    const mo = new MutationObserver(fn);
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ['class', 'data-palette'] });
    window.addEventListener(PALETTE_CHANGE_EVENT, fn);
    return () => {
      mo.disconnect();
      window.removeEventListener(PALETTE_CHANGE_EVENT, fn);
    };
  }, [applyColors]);

  if (isPending) {
    return (
      <div
        className={cn('relative px-4', className)}
        data-testid="rs-mansfield-ribbon-loading"
        aria-busy
        style={{ height }}
      >
        <Skeleton className="h-full w-full rounded-lg" />
      </div>
    );
  }

  if (isError) {
    return (
      <div className={cn('px-4', className)} data-testid="rs-mansfield-ribbon-error">
        <ErrorState
          title="Could not load RS ribbon"
          description="Try again or check your connection."
          retry={onRetry}
          error={error}
        />
      </div>
    );
  }

  if (chartData.length === 0) {
    return (
      <div
        className={cn(
          'mx-4 flex items-center rounded-md border border-border bg-muted/30 px-3 py-2 text-xs text-muted-foreground',
          className,
        )}
        data-testid="rs-mansfield-ribbon-unavailable"
        role="status"
      >
        RS ribbon unavailable for this symbol
      </div>
    );
  }

  return (
    <div className={cn('relative w-full px-4', className)} data-testid="rs-mansfield-ribbon-data">
      <div className="pointer-events-none absolute right-6 top-1 z-10 text-[10px] text-muted-foreground">
        RS Mansfield (52w) vs {benchmark}
      </div>
      <div
        ref={containerRef}
        className="w-full min-w-0 overflow-hidden rounded-lg"
        style={{ height }}
        role="img"
        aria-label="RS Mansfield versus benchmark over time"
      />
    </div>
  );
}
