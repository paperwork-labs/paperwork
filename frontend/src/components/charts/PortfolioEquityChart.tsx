/**
 * Portfolio equity (total value) chart — line + area, optional SPY benchmark line.
 * // TODO(c4): add trade / dividend segment markers when tx hooks are cheap to wire
 */
import * as React from "react";
import {
  AreaSeries,
  createChart,
  LineSeries,
  LineStyle,
  type IChartApi,
  type ISeriesApi,
  type Time,
  type UTCTimestamp,
} from "lightweight-charts";

import { ErrorState } from "@/components/ui/ErrorState";
import { SegmentedPeriodSelector } from "@/components/ui/SegmentedPeriodSelector";
import { Skeleton } from "@/components/ui/skeleton";
import { cssVarToCanvasColor } from "@/lib/chartColors";
import { resolveThemeColors, withAlpha } from "@/lib/holdingChart/themeColors";
import { cn } from "@/lib/utils";

import { PriceChartSkeleton } from "./skeletons/PriceChartSkeleton";

const MODE_OPTIONS = [
  { value: "usd" as const, label: "$", ariaLabel: "Dollars" },
  { value: "pct" as const, label: "%", ariaLabel: "Percent change from first point" },
];

export interface PortfolioEquityChartPoint {
  time: UTCTimestamp;
  equity: number;
  benchmark: number | null;
}

export interface PortfolioEquityChartProps {
  isPending: boolean;
  isError: boolean;
  error: Error | null;
  onRetry: () => void;
  data: Array<{ date: string; total_value: number }> | undefined;
  chartPoints: PortfolioEquityChartPoint[];
  hasBenchmark: boolean;
  valueMode: "usd" | "pct";
  onValueModeChange: (m: "usd" | "pct") => void;
  height?: number;
  className?: string;
}

const DEFAULT_H = 280;
const BENCH_FALLBACK = "rgb(128, 128, 128)";

const PALETTE_CHANGE_EVENT = "axiomfolio:color-palette-change";

export function PortfolioEquityChart({
  isPending,
  isError,
  error,
  onRetry,
  data,
  chartPoints,
  hasBenchmark,
  valueMode,
  onValueModeChange,
  height = DEFAULT_H,
  className,
}: PortfolioEquityChartProps) {
  const containerRef = React.useRef<HTMLDivElement | null>(null);
  const chartRef = React.useRef<IChartApi | null>(null);
  const areaRef = React.useRef<ISeriesApi<"Area"> | null>(null);
  const benchRef = React.useRef<ISeriesApi<"Line"> | null>(null);
  const [w, setW] = React.useState(0);

  const emptyMessage =
    "No performance history yet. First snapshot lands after your next sync.";

  const applySeriesColors = React.useCallback(() => {
    const area = areaRef.current;
    const ben = benchRef.current;
    const base = cssVarToCanvasColor("--chart-equity", seriesFallback());
    if (area) {
      area.applyOptions({
        lineColor: base,
        topColor: withAlpha(base, 0.22),
        bottomColor: withAlpha(base, 0),
        crosshairMarkerBackgroundColor: base,
      });
    }
    if (ben) {
      const g = withAlpha(
        cssVarToCanvasColor("--muted-foreground", BENCH_FALLBACK),
        0.5,
      );
      ben.applyOptions({ color: g, lineStyle: LineStyle.Solid, lineWidth: 1 });
    }
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
    if (chartPoints.length === 0) return;
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
      rightPriceScale: { borderVisible: false, scaleMargins: { top: 0.12, bottom: 0.08 } },
      timeScale: { borderVisible: false, timeVisible: true, secondsVisible: false },
      crosshair: { mode: 0 },
    });
    chartRef.current = chart;

    if (hasBenchmark) {
      benchRef.current = chart.addSeries(LineSeries, {
        color: withAlpha(cssVarToCanvasColor("--muted-foreground", BENCH_FALLBACK), 0.5),
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
        lineStyle: LineStyle.Solid,
        crosshairMarkerVisible: false,
      });
    }

    const base = cssVarToCanvasColor("--chart-equity", seriesFallback());
    areaRef.current = chart.addSeries(AreaSeries, {
      lineColor: base,
      lineWidth: 2,
      topColor: withAlpha(base, 0.22),
      bottomColor: withAlpha(base, 0),
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: true,
      crosshairMarkerRadius: 4,
      crosshairMarkerBackgroundColor: base,
    });

    if (hasBenchmark && benchRef.current) {
      benchRef.current.setData(
        chartPoints.map((p) => ({
          time: p.time as Time,
          value: p.benchmark as number,
        })),
      );
    }

    if (areaRef.current) {
      areaRef.current.setData(
        chartPoints.map((p) => ({
          time: p.time as Time,
          value: p.equity,
        })),
      );
    }
    try {
      chart.timeScale().fitContent();
    } catch {
      // ignore
    }
    applySeriesColors();
    return () => {
      chart.remove();
      chartRef.current = null;
      areaRef.current = null;
      benchRef.current = null;
    };
  }, [isPending, isError, data, chartPoints, hasBenchmark, height, w, applySeriesColors]);

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
      applySeriesColors();
    };
    const mo = new MutationObserver(fn);
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ["class", "data-palette"] });
    window.addEventListener(PALETTE_CHANGE_EVENT, fn);
    return () => {
      mo.disconnect();
      window.removeEventListener(PALETTE_CHANGE_EVENT, fn);
    };
  }, [applySeriesColors]);

  if (isPending) {
    return (
      <div
        className={cn("flex flex-col gap-2", className)}
        data-testid="portfolio-equity-loading"
        aria-busy
      >
        <div className="flex justify-end">
          <Skeleton className="h-7 w-24" />
        </div>
        <PriceChartSkeleton height={height} label="portfolio equity" />
      </div>
    );
  }

  if (isError) {
    return (
      <div className={cn("flex flex-col gap-2", className)} data-testid="portfolio-equity-error">
        <ErrorState
          title="Could not load performance history"
          description="Try again or check your network connection."
          retry={onRetry}
          error={error}
        />
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <div
        className={cn("flex h-40 items-center justify-center text-sm text-muted-foreground", className)}
        data-testid="portfolio-equity-empty"
        role="status"
      >
        {emptyMessage}
      </div>
    );
  }

  if (chartPoints.length === 0) {
    return (
      <div
        className={cn("flex h-40 items-center justify-center text-sm text-muted-foreground", className)}
        data-testid="portfolio-equity-empty"
        role="status"
      >
        {emptyMessage}
      </div>
    );
  }

  return (
    <div
      className={cn("flex flex-col gap-2", className)}
      data-testid="portfolio-equity-chart-data"
    >
      <div className="flex justify-end">
        <SegmentedPeriodSelector<"usd" | "pct">
          size="sm"
          ariaLabel="Value scale"
          options={MODE_OPTIONS}
          value={valueMode}
          onChange={onValueModeChange}
        />
      </div>
      <div
        ref={containerRef}
        className="relative w-full min-w-0 overflow-hidden rounded-lg"
        style={{ height }}
        role="img"
        aria-label="Portfolio value over time"
        data-testid="portfolio-equity-canvas"
      />
    </div>
  );
}

function seriesFallback(): string {
  return cssVarToCanvasColor("--chart-neutral", "rgb(59, 130, 246)");
}
