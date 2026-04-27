/**
 * Underwater drawdown panel — values ≤ 0 vs baseline at 0 (BaselineSeries).
 */
import * as React from "react";
import {
  BaselineSeries,
  createChart,
  LineStyle,
  type IChartApi,
  type ISeriesApi,
  type Time,
} from "lightweight-charts";

import { ErrorState } from "@/components/ui/ErrorState";
import { Skeleton } from "@/components/ui/skeleton";
import { cssVarToCanvasColor } from "@/lib/chartColors";
import { resolveThemeColors, withAlpha } from "@/lib/holdingChart/themeColors";
import { formatLightweightTimeTick } from "@/lib/chartAxisFormat";
import { computeDrawdownUnderwaterSeries } from "@/lib/portfolioDrawdownMath";
import { cn } from "@/lib/utils";

const PALETTE_CHANGE_EVENT = "axiomfolio:color-palette-change";
const DANGER_FALLBACK = "rgb(220, 38, 38)";

export interface DrawdownUnderwaterProps {
  isPending: boolean;
  isError: boolean;
  error: Error | null;
  onRetry: () => void;
  data: Array<{ date: string; total_value: number }> | undefined;
  height?: number;
  className?: string;
}

const DEFAULT_H = 140;

const PCT = new Intl.NumberFormat(undefined, {
  style: "percent",
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});

function formatDd(fraction: number): string {
  if (!Number.isFinite(fraction)) return "—";
  if (Math.abs(fraction) < 1e-12) return "0%";
  return PCT.format(fraction);
}

export function DrawdownUnderwater({
  isPending,
  isError,
  error,
  onRetry,
  data,
  height = DEFAULT_H,
  className,
}: DrawdownUnderwaterProps) {
  const containerRef = React.useRef<HTMLDivElement | null>(null);
  const chartRef = React.useRef<IChartApi | null>(null);
  const seriesRef = React.useRef<ISeriesApi<"Baseline"> | null>(null);
  const [w, setW] = React.useState(0);

  const emptyMessage =
    "No performance history yet. First snapshot lands after your next sync.";

  const sorted = React.useMemo(() => {
    const times: number[] = [];
    const values: number[] = [];
    if (!data?.length) return { times, values };
    const rows = [...data]
      .map((p) => ({
        t: String(p.date).slice(0, 10),
        v: Number(p.total_value),
      }))
      .filter((r) => r.t.length >= 10 && Number.isFinite(r.v) && r.v > 0)
      .sort((a, b) => a.t.localeCompare(b.t));
    for (const r of rows) {
      const ms = Date.parse(r.t) || Date.parse(`${r.t}T00:00:00Z`);
      if (!Number.isFinite(ms)) continue;
      const sec = Math.floor(ms / 1000);
      if (sec <= 0) continue;
      times.push(sec);
      values.push(r.v);
    }
    return { times, values };
  }, [data]);

  const stats = React.useMemo(
    () => computeDrawdownUnderwaterSeries(sorted.times, sorted.values),
    [sorted.times, sorted.values],
  );

  const multiYear = React.useMemo(() => {
    const pts = stats.points;
    if (pts.length < 2) return false;
    const t0 = pts[0].timeUtc as number;
    const t1 = pts[pts.length - 1].timeUtc as number;
    const y0 = new Date(t0 * 1000).getUTCFullYear();
    const y1 = new Date(t1 * 1000).getUTCFullYear();
    return y0 !== y1;
  }, [stats.points]);

  const applyColors = React.useCallback(() => {
    const s = seriesRef.current;
    if (!s) return;
    const d = withAlpha(
      cssVarToCanvasColor("--chart-danger", DANGER_FALLBACK),
      0.35,
    );
    const d2 = withAlpha(
      cssVarToCanvasColor("--chart-danger", DANGER_FALLBACK),
      0.08,
    );
    const line = cssVarToCanvasColor("--chart-danger", DANGER_FALLBACK);
    s.applyOptions({
      baseValue: { type: "price", price: 0 },
      topFillColor1: "transparent",
      topFillColor2: "transparent",
      topLineColor: "transparent",
      bottomFillColor1: d,
      bottomFillColor2: d2,
      bottomLineColor: line,
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
    if (!data || data.length === 0) return;
    if (stats.points.length === 0) return;
    const node = containerRef.current;
    if (!node || w <= 0) return;

    const t = resolveThemeColors();
    const chart = createChart(node, {
      autoSize: false,
      width: w,
      height,
      layout: {
        background: { color: "transparent" },
        textColor: t.text,
        fontFamily:
          "'Inter Variable', ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, sans-serif",
      },
      grid: {
        vertLines: { color: t.gridLine, style: LineStyle.Dotted },
        horzLines: { color: t.gridLine, style: LineStyle.Dotted },
      },
      localization: {
        priceFormatter: (p: number) => {
          if (Math.abs(p) < 1e-12) return "0%";
          return PCT.format(p);
        },
      },
      rightPriceScale: { borderVisible: false, scaleMargins: { top: 0.05, bottom: 0.12 } },
      timeScale: {
        borderVisible: false,
        timeVisible: true,
        secondsVisible: false,
        tickMarkFormatter: (time: Time) => formatLightweightTimeTick(time, multiYear),
      },
      crosshair: { mode: 0 },
    });
    chartRef.current = chart;

    const d = withAlpha(
      cssVarToCanvasColor("--chart-danger", DANGER_FALLBACK),
      0.35,
    );
    const d2 = withAlpha(
      cssVarToCanvasColor("--chart-danger", DANGER_FALLBACK),
      0.08,
    );
    const line = cssVarToCanvasColor("--chart-danger", DANGER_FALLBACK);

    seriesRef.current = chart.addSeries(BaselineSeries, {
      baseValue: { type: "price", price: 0 },
      lineWidth: 1,
      lineStyle: LineStyle.Solid,
      topFillColor1: "transparent",
      topFillColor2: "transparent",
      topLineColor: "transparent",
      bottomFillColor1: d,
      bottomFillColor2: d2,
      bottomLineColor: line,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
      priceFormat: { type: "percent", minMove: 0.0001, precision: 1 },
    });
    seriesRef.current.setData(
      stats.points.map((p) => ({
        time: p.timeUtc as Time,
        value: p.drawdown,
      })),
    );
    try {
      chart.timeScale().fitContent();
    } catch {
      // ignore
    }
    applyColors();
    return () => {
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, [isPending, isError, data, stats.points, height, w, applyColors, multiYear]);

  const rw = w > 0 ? w : containerRef.current?.clientWidth ?? 0;
  React.useEffect(() => {
    if (chartRef.current && rw > 0) {
      chartRef.current.applyOptions({ width: Math.floor(rw), height });
    }
  }, [height, rw]);

  React.useEffect(() => {
    if (typeof window === "undefined") return;
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
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ["class", "data-palette"] });
    window.addEventListener(PALETTE_CHANGE_EVENT, fn);
    return () => {
      mo.disconnect();
      window.removeEventListener(PALETTE_CHANGE_EVENT, fn);
    };
  }, [applyColors]);

  if (isPending) {
    return (
      <div
        className={cn("relative", className)}
        data-testid="drawdown-underwater-loading"
        aria-busy
        style={{ height }}
      >
        <Skeleton className="h-full w-full rounded-lg" />
      </div>
    );
  }

  if (isError) {
    return (
      <div className={className} data-testid="drawdown-underwater-error">
        <ErrorState
          title="Could not load drawdown"
          description="Try again or check your network connection."
          retry={onRetry}
          error={error}
        />
      </div>
    );
  }

  if (!data || data.length === 0 || stats.points.length === 0) {
    return (
      <div
        className={cn(
          "flex items-center justify-center text-sm text-muted-foreground",
          className,
        )}
        data-testid="drawdown-underwater-empty"
        role="status"
        style={{ minHeight: height }}
      >
        {emptyMessage}
      </div>
    );
  }

  return (
    <div
      className={cn("relative w-full", className)}
      data-testid="drawdown-underwater-data"
    >
      <p className="mb-0.5 flex w-full items-center justify-between gap-2 px-0.5 text-[10px] text-muted-foreground">
        <span>Time</span>
        <span>Drawdown (%)</span>
      </p>
      <div className="pointer-events-none absolute right-2 top-5 z-10 flex flex-col items-end gap-0.5 text-[10px] tabular-nums text-muted-foreground">
        <span>Max {formatDd(stats.maxDrawdown)}</span>
        <span>Current {formatDd(stats.currentDrawdown)}</span>
      </div>
      <div
        ref={containerRef}
        className="w-full min-w-0 overflow-hidden rounded-lg"
        style={{ height }}
        role="img"
        aria-label="Drawdown over time"
        data-testid="drawdown-underwater-canvas"
      />
    </div>
  );
}

