/**
 * `HoldingPriceChart` — the flagship per-holding price chart.
 *
 * The visual goal is "premium quant terminal" not "broker dashboard":
 *   - Wrapped in `ChartGlassCard` for the layered, shadowed surface.
 *   - lightweight-charts line series for the primary symbol with a faint
 *     gradient area underneath (depth without distraction).
 *   - Dashed sector / asset-class benchmark overlay so the user can read
 *     relative performance at a glance.
 *   - "Since I bought" period that auto-derives from activity, plus the
 *     usual 1M / 3M / 6M / YTD / 1Y / 5Y / Max ramp.
 *   - Subtle idle "scrubber" pulse when the user isn't actively hovering,
 *     suppressed under reduced-motion.
 *   - First-class loading / error / empty / data states.
 *
 * Wiring: this component is purely additive — it is NOT yet rendered by
 * any page. A follow-up PR places it in PortfolioWorkspace.
 */
import * as React from "react";
import {
  AnimatePresence,
  motion,
  useReducedMotion,
} from "framer-motion";
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

import { AnimatedNumber } from "@/components/ui/AnimatedNumber";
import { ChartGlassCard } from "@/components/ui/ChartGlassCard";
import { ErrorState } from "@/components/ui/ErrorState";
import { RichTooltip } from "@/components/ui/RichTooltip";
import {
  SegmentedPeriodSelector,
  type SegmentedPeriodOption,
} from "@/components/ui/SegmentedPeriodSelector";
import { Skeleton } from "@/components/ui/skeleton";
import { seriesColor } from "@/constants/chart";
import { DURATION, EASE } from "@/lib/motion";
import { cn } from "@/lib/utils";

import { ChartAnnouncer } from "./ChartA11y";
import { ChartCrosshair, useCrosshairTracking } from "./ChartCrosshair";
import { PriceChartSkeleton } from "./skeletons/PriceChartSkeleton";
import {
  resolveThemeColors,
  withAlpha,
} from "@/lib/holdingChart/themeColors";
import {
  useHoldingChartData,
  type HoldingChartPeriod,
} from "@/lib/holdingChart/useHoldingChartData";

export interface HoldingPriceChartProps {
  symbol: string;
  accountId?: string;
  /** Defaults to `"since"` when activity has buys, else `"1y"` (resolved internally). */
  initialPeriod?: HoldingChartPeriod;
  /** Pixel height of the chart area (excluding header / period row). Default 460. */
  height?: number;
  showBenchmark?: boolean;
  benchmarkOverride?: string | null;
  className?: string;
  /** Fired whenever the user picks a new period (used for deeplinks in a later PR). */
  onPeriodChange?: (p: HoldingChartPeriod) => void;
}

const DEFAULT_HEIGHT = 460;

const ALL_PERIOD_OPTIONS: ReadonlyArray<SegmentedPeriodOption<HoldingChartPeriod>> = [
  { value: "since", label: "Since I bought" },
  { value: "1mo", label: "1M" },
  { value: "3mo", label: "3M" },
  { value: "6mo", label: "6M" },
  { value: "ytd", label: "YTD" },
  { value: "1y", label: "1Y" },
  { value: "5y", label: "5Y" },
  { value: "max", label: "Max" },
];

const PERIOD_OPTIONS_NO_SINCE = ALL_PERIOD_OPTIONS.filter(
  (o) => o.value !== "since",
);

/**
 * Custom event name dispatched by `useUserPreferences` whenever the user
 * toggles the color-blind palette. We re-resolve theme + series colors in
 * response so the chart stays in sync with the rest of the app — same
 * pattern `ChartCrosshair` uses for its axis stroke.
 */
const PALETTE_CHANGE_EVENT = "axiomfolio:color-palette-change";

/**
 * Convert an ISO date / timestamp to a UTC seconds value lightweight-charts
 * accepts as a `UTCTimestamp`. Returns null if unparseable so callers can
 * skip the bar rather than feed NaN downstream.
 */
function toUtcTimestamp(iso: string): UTCTimestamp | null {
  const ms = Date.parse(iso);
  if (!Number.isFinite(ms)) return null;
  return Math.floor(ms / 1000) as UTCTimestamp;
}

const PRICE_FORMATTER = new Intl.NumberFormat(undefined, {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const PCT_FORMATTER = new Intl.NumberFormat(undefined, {
  style: "percent",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

function formatChangePct(open: number, close: number): string {
  if (!Number.isFinite(open) || !Number.isFinite(close) || open === 0) return "";
  const pct = (close - open) / open;
  const sign = pct >= 0 ? "+" : "";
  return `${sign}${PCT_FORMATTER.format(pct)}`;
}

/**
 * Idle "aliveness" scrubber: a faint vertical bar drifts left-to-right
 * when the user is not actively interacting with the chart. The animation
 * obeys reduced-motion (renders nothing) and pauses for `IDLE_MS` after
 * any pointer activity to avoid feeling jumpy.
 */
const IDLE_MS = 3_000;
const SCRUB_DURATION_S = 4;
const SCRUB_LOOP_GAP_S = 8;

function IdleAliveness({
  active,
  height,
}: {
  active: boolean;
  height: number;
}) {
  const reduced = useReducedMotion();
  if (reduced || !active) return null;
  return (
    <motion.div
      aria-hidden
      data-testid="holding-chart-aliveness"
      // Deliberately deterministic timing — never `Math.random()` so the
      // animation reads as designed motion, not noise.
      initial={{ left: "0%", opacity: 0 }}
      animate={{
        left: ["0%", "0%", "100%", "100%"],
        opacity: [0, 0.18, 0.18, 0],
      }}
      transition={{
        duration: SCRUB_DURATION_S + SCRUB_LOOP_GAP_S,
        ease: EASE.standard,
        times: [0, 0.05, 0.95, 1],
        repeat: Infinity,
        repeatDelay: 0,
      }}
      style={{ height }}
      className={cn(
        "pointer-events-none absolute top-0 w-px",
        "bg-foreground/30",
      )}
    />
  );
}

/** Binary search for the index of the bar whose time is the largest <= t. */
function findBarIndex(bars: ReadonlyArray<{ time: string }>, t: number): number {
  let lo = 0;
  let hi = bars.length - 1;
  let best = -1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    const ms = Date.parse(bars[mid].time);
    if (ms <= t) {
      best = mid;
      lo = mid + 1;
    } else {
      hi = mid - 1;
    }
  }
  return best;
}

export function HoldingPriceChart({
  symbol,
  accountId,
  initialPeriod,
  height = DEFAULT_HEIGHT,
  showBenchmark = true,
  benchmarkOverride = null,
  className,
  onPeriodChange,
}: HoldingPriceChartProps) {
  // Track the initial period as INITIAL — re-renders when `initialPeriod`
  // changes mid-flight don't yank the user's selection out from under them.
  const [period, setPeriod] = React.useState<HoldingChartPeriod>(
    initialPeriod ?? "since",
  );
  React.useEffect(() => {
    if (initialPeriod) setPeriod(initialPeriod);
  }, [initialPeriod]);

  const data = useHoldingChartData({
    symbol,
    accountId,
    period,
    benchmarkOverride,
    // Skip the benchmark fetch entirely when the consumer has hidden
    // the overlay — keeps the network call in lock-step with the UI.
    fetchBenchmark: showBenchmark,
  });

  const handlePeriodChange = React.useCallback(
    (next: HoldingChartPeriod) => {
      setPeriod(next);
      onPeriodChange?.(next);
    },
    [onPeriodChange],
  );

  const periodOptions = React.useMemo(
    () => (data.earliestBuyDate ? ALL_PERIOD_OPTIONS : PERIOD_OPTIONS_NO_SINCE),
    [data.earliestBuyDate],
  );

  // If the user is on 'since' but has no buys yet, default the visible
  // selection to '1y' so the radiogroup shows a checked option. We don't
  // mutate `period` state because `useHoldingChartData` already maps
  // 'since' → '1y' under the hood.
  const visiblePeriod: HoldingChartPeriod =
    period === "since" && !data.earliestBuyDate ? "1y" : period;

  // ── Chart wiring ───────────────────────────────────────────────────────
  const containerRef = React.useRef<HTMLDivElement | null>(null);
  const chartRef = React.useRef<IChartApi | null>(null);
  const primaryRef = React.useRef<ISeriesApi<"Area"> | null>(null);
  const benchmarkRef = React.useRef<ISeriesApi<"Line"> | null>(null);
  const [containerSize, setContainerSize] = React.useState({ width: 0, height });

  // Resize observer keeps the chart wrapping correctly across container
  // changes — drawer collapses, sidebar resizes, etc.
  React.useEffect(() => {
    const node = containerRef.current;
    if (!node) return;
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const w = entry.contentRect.width;
        setContainerSize((prev) => (prev.width === w ? prev : { width: w, height }));
        if (chartRef.current) {
          chartRef.current.applyOptions({ width: Math.floor(w), height });
        }
      }
    });
    ro.observe(node);
    return () => ro.disconnect();
  }, [height]);

  // Create the chart once the container is mounted. We tear it down on
  // unmount; data updates flow through a separate effect below so we don't
  // recreate the WebGL context on every prop change.
  React.useEffect(() => {
    const node = containerRef.current;
    if (!node) return;

    const initialTheme = resolveThemeColors();
    const chart = createChart(node, {
      autoSize: false,
      width: node.clientWidth,
      height,
      layout: {
        background: { color: "transparent" },
        textColor: initialTheme.text,
        fontFamily:
          "'Inter Variable', ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, sans-serif",
      },
      grid: {
        vertLines: { color: initialTheme.gridLine, style: LineStyle.Dotted },
        horzLines: { color: initialTheme.gridLine, style: LineStyle.Dotted },
      },
      rightPriceScale: {
        borderVisible: false,
        scaleMargins: { top: 0.15, bottom: 0.05 },
      },
      timeScale: {
        borderVisible: false,
        timeVisible: true,
        secondsVisible: false,
      },
      crosshair: {
        // Mode 1 ("Normal" — magnet snap), but we hide the built-in lines
        // and render our own design-system crosshair as an overlay so it
        // matches the rest of the app visually.
        mode: 1,
        vertLine: { visible: false, labelVisible: false },
        horzLine: { visible: false, labelVisible: false },
      },
      handleScale: { mouseWheel: true, pinch: true, axisPressedMouseMove: true },
      handleScroll: { mouseWheel: false, pressedMouseMove: true },
    });
    chartRef.current = chart;

    return () => {
      chart.remove();
      chartRef.current = null;
      primaryRef.current = null;
      benchmarkRef.current = null;
    };
  }, [height]);

  // Push primary + benchmark series data into the chart. Resolve series
  // colors at runtime so a palette toggle re-skins both lines without
  // recreating the chart.
  React.useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;

    const primaryColor = seriesColor(0);
    const benchmarkColor = seriesColor(1);

    if (!primaryRef.current) {
      primaryRef.current = chart.addSeries(AreaSeries, {
        lineColor: primaryColor,
        lineWidth: 2,
        // `color-mix` keeps the alpha modulation valid for both hex AND
        // `rgb(...)` palette outputs (the previous `${color}2E` trick
        // silently broke when `seriesColor()` returned an rgb string).
        topColor: withAlpha(primaryColor, 0.18),
        bottomColor: withAlpha(primaryColor, 0),
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: true,
        crosshairMarkerRadius: 4,
        crosshairMarkerBackgroundColor: primaryColor,
      });
    }

    const seriesData = data.bars
      .map((b) => {
        const t = toUtcTimestamp(b.time);
        if (t === null) return null;
        return { time: t as Time, value: b.close };
      })
      .filter(
        (
          v,
        ): v is { time: Time; value: number } => v !== null,
      );

    primaryRef.current.setData(seriesData);

    // Benchmark: create only if requested AND data exists; otherwise tear
    // it down so the legend stays in sync with the chart visuals.
    const wantBenchmark =
      showBenchmark && data.benchmarkBars.length > 0;
    if (wantBenchmark) {
      if (!benchmarkRef.current) {
        benchmarkRef.current = chart.addSeries(LineSeries, {
          color: benchmarkColor,
          lineWidth: 2,
          lineStyle: LineStyle.Dashed,
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
        });
      }
      const benchmarkData = data.benchmarkBars
        .map((b) => {
          const t = toUtcTimestamp(b.time);
          if (t === null) return null;
          return { time: t as Time, value: b.close };
        })
        .filter(
          (
            v,
          ): v is { time: Time; value: number } => v !== null,
        );
      benchmarkRef.current.setData(benchmarkData);
    } else if (benchmarkRef.current) {
      chart.removeSeries(benchmarkRef.current);
      benchmarkRef.current = null;
    }

    if (seriesData.length > 0) {
      chart.timeScale().fitContent();
    }
  }, [data.bars, data.benchmarkBars, showBenchmark]);

  // ── Theme + palette reactivity ────────────────────────────────────────
  // lightweight-charts paints to a canvas and never re-resolves CSS
  // variables on its own. We have to push fresh colors whenever:
  //   - the user toggles the color-blind palette
  //     (`useUserPreferences` dispatches `axiomfolio:color-palette-change`),
  //   - the user toggles light / dark mode (the `.dark` class flips on
  //     `<html>`),
  //   - the user changes any other class / data attribute on `<html>` that
  //     might rebind the palette CSS variables.
  // Same subscription pattern as `ChartCrosshair.useAxisColor()`, so the
  // chart and its overlay stay in lock-step.
  React.useEffect(() => {
    if (typeof window === "undefined") return;

    const applyTheme = () => {
      const chart = chartRef.current;
      if (!chart) return;
      const colors = resolveThemeColors();
      chart.applyOptions({
        layout: { textColor: colors.text },
        grid: {
          vertLines: { color: colors.gridLine },
          horzLines: { color: colors.gridLine },
        },
      });
      const primaryColor = seriesColor(0);
      primaryRef.current?.applyOptions({
        lineColor: primaryColor,
        topColor: withAlpha(primaryColor, 0.18),
        bottomColor: withAlpha(primaryColor, 0),
        crosshairMarkerBackgroundColor: primaryColor,
      });
      benchmarkRef.current?.applyOptions({ color: seriesColor(1) });
    };

    window.addEventListener(PALETTE_CHANGE_EVENT, applyTheme);
    const observer = new MutationObserver(applyTheme);
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["class", "data-palette"],
    });

    return () => {
      window.removeEventListener(PALETTE_CHANGE_EVENT, applyTheme);
      observer.disconnect();
    };
  }, []);

  // ── Crosshair + idle aliveness ────────────────────────────────────────
  const crosshair = useCrosshairTracking();
  const [idle, setIdle] = React.useState(true);
  const idleTimer = React.useRef<ReturnType<typeof setTimeout> | null>(null);

  const onChartMouseMove = React.useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      crosshair.onMouseMove(e);
      setIdle(false);
      if (idleTimer.current) clearTimeout(idleTimer.current);
      idleTimer.current = setTimeout(() => setIdle(true), IDLE_MS);
    },
    [crosshair],
  );

  const onChartMouseLeave = React.useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      crosshair.onMouseLeave(e);
      if (idleTimer.current) clearTimeout(idleTimer.current);
      idleTimer.current = setTimeout(() => setIdle(true), IDLE_MS);
    },
    [crosshair],
  );

  // Mouse-enter alone (without movement) should also pause the scrubber —
  // a user who hovers the chart and freezes their cursor still expects
  // the aliveness pulse to back off. Without this, the pulse keeps
  // animating UNDER the user's cursor until they nudge the mouse.
  const onChartMouseEnter = React.useCallback(() => {
    setIdle(false);
    if (idleTimer.current) clearTimeout(idleTimer.current);
    idleTimer.current = setTimeout(() => setIdle(true), IDLE_MS);
  }, []);

  React.useEffect(
    () => () => {
      if (idleTimer.current) clearTimeout(idleTimer.current);
    },
    [],
  );

  // ── Header / a11y summary derivations ─────────────────────────────────
  const lastBar = data.bars.length > 0 ? data.bars[data.bars.length - 1] : null;
  const firstBar = data.bars.length > 0 ? data.bars[0] : null;
  const lastClose = lastBar ? Number.parseFloat(String(lastBar.close)) : NaN;
  const firstOpen = firstBar
    ? Number.parseFloat(String(firstBar.open ?? firstBar.close))
    : NaN;
  const periodChangePct = formatChangePct(firstOpen, lastClose);
  const periodChangeIsPositive =
    Number.isFinite(firstOpen) && Number.isFinite(lastClose)
      ? lastClose >= firstOpen
      : true;

  const sector =
    typeof data.snapshot?.sector === "string"
      ? (data.snapshot.sector as string)
      : null;

  // Crosshair → bar lookup for screen-reader announcement.
  const announceText = React.useMemo(() => {
    // Empty-state announcement must match the visible "No price data
    // yet for {symbol}." copy or screen-reader users get a misleading
    // "loading" message even though the visible UI says "no data".
    if (data.bars.length === 0) {
      return `No price data yet for ${symbol}.`;
    }
    if (!lastBar || !Number.isFinite(lastClose)) {
      return `${symbol} chart loading.`;
    }
    if (crosshair.x === null) {
      return `${symbol} closed at ${PRICE_FORMATTER.format(lastClose)} on ${lastBar.time}${
        periodChangePct ? `, ${periodChangePct} for the period.` : "."
      }`;
    }
    // Map x to a bar by simple proportion since lightweight-charts
    // doesn't expose a synchronous time-from-x without a chart event.
    if (containerSize.width <= 0) return `${symbol} chart.`;
    const fraction = Math.max(
      0,
      Math.min(1, crosshair.x / containerSize.width),
    );
    const idx = Math.min(
      data.bars.length - 1,
      Math.max(0, Math.round(fraction * (data.bars.length - 1))),
    );
    // Binary search by approximate ms — guards against uneven bar spacing
    // (e.g. weekends gaps) producing visibly off-by-N announcements.
    const approxMs = Date.parse(data.bars[idx].time);
    const refined = Number.isFinite(approxMs) ? findBarIndex(data.bars, approxMs) : idx;
    const bar = data.bars[refined] ?? data.bars[idx];
    const close = Number.parseFloat(String(bar.close));
    return `${symbol} closed at ${PRICE_FORMATTER.format(close)} on ${bar.time}.`;
  }, [crosshair.x, containerSize.width, data.bars, lastBar, lastClose, periodChangePct, symbol]);

  // ── Render ─────────────────────────────────────────────────────────────
  if (data.isLoading) {
    return (
      <ChartGlassCard
        ariaLabel={`${symbol} price chart`}
        className={cn("flex flex-col gap-4", className)}
      >
        <HeaderRow
          symbol={symbol}
          sector={null}
          loading
        />
        <div className="flex items-center justify-between gap-4">
          <Skeleton className="h-9 w-72" />
        </div>
        <PriceChartSkeleton height={height} />
      </ChartGlassCard>
    );
  }

  if (data.isError) {
    return (
      <ChartGlassCard
        ariaLabel={`${symbol} price chart`}
        className={cn("flex flex-col gap-4", className)}
      >
        <HeaderRow symbol={symbol} sector={sector} />
        <ErrorState
          title="Couldn't load chart"
          description="Try again or check your network connection."
          retry={() => {
            void data.refetch();
          }}
          error={data.error}
        />
      </ChartGlassCard>
    );
  }

  return (
    <ChartGlassCard
      ariaLabel={`${symbol} price chart`}
      interactive
      className={cn("flex flex-col gap-4", className)}
    >
      <HeaderRow
        symbol={symbol}
        sector={sector}
        lastClose={lastClose}
        changePct={periodChangePct}
        changeIsPositive={periodChangeIsPositive}
      />

      <div className="flex flex-wrap items-center justify-between gap-3">
        <SegmentedPeriodSelector<HoldingChartPeriod>
          ariaLabel="Time period"
          options={periodOptions}
          value={visiblePeriod}
          onChange={handlePeriodChange}
        />
        {showBenchmark && data.benchmarkSymbol ? (
          <BenchmarkLegend
            symbol={symbol}
            benchmarkSymbol={data.benchmarkSymbol}
            benchmarkLabel={data.benchmarkLabel}
            benchmarkTooltip={data.benchmarkTooltip}
          />
        ) : null}
      </div>

      <div
        ref={containerRef}
        role="img"
        aria-label={
          Number.isFinite(lastClose)
            ? `${symbol} latest close ${PRICE_FORMATTER.format(lastClose)}${
                periodChangePct ? `, ${periodChangePct}` : ""
              }`
            : `${symbol} price chart`
        }
        onMouseEnter={onChartMouseEnter}
        onMouseMove={onChartMouseMove}
        onMouseLeave={onChartMouseLeave}
        className="relative w-full overflow-hidden rounded-lg"
        style={{ height }}
      >
        {data.bars.length === 0 ? (
          <div
            className="flex h-full items-center justify-center text-sm text-muted-foreground"
            data-testid="holding-chart-empty"
          >
            No price data yet for {symbol}.
          </div>
        ) : null}

        {/* Idle aliveness: faint left→right scrubber when not interacting. */}
        <AnimatePresence initial={false}>
          {data.bars.length > 0 ? (
            <IdleAliveness active={idle} height={height} />
          ) : null}
        </AnimatePresence>

        <ChartCrosshair
          width={containerSize.width}
          height={height}
          x={crosshair.x}
          y={crosshair.y}
        />
      </div>

      <ChartAnnouncer summary={announceText} />
    </ChartGlassCard>
  );
}

interface HeaderRowProps {
  symbol: string;
  sector: string | null;
  lastClose?: number;
  changePct?: string;
  changeIsPositive?: boolean;
  loading?: boolean;
}

function HeaderRow({
  symbol,
  sector,
  lastClose,
  changePct,
  changeIsPositive = true,
  loading = false,
}: HeaderRowProps) {
  return (
    <div className="flex items-start justify-between gap-4">
      <div className="flex flex-col gap-0.5">
        <span className="font-heading text-2xl font-semibold tracking-tight text-foreground">
          {symbol}
        </span>
        {sector ? (
          <span className="text-sm text-muted-foreground">{sector}</span>
        ) : loading ? (
          <Skeleton className="h-4 w-32" />
        ) : null}
      </div>
      <div className="flex flex-col items-end gap-1">
        {loading ? (
          <>
            <Skeleton className="h-7 w-24" />
            <Skeleton className="h-4 w-16" />
          </>
        ) : Number.isFinite(lastClose ?? NaN) ? (
          <>
            <AnimatedNumber
              className="text-2xl font-semibold tracking-tight text-foreground"
              value={lastClose ?? 0}
              format={(n) => PRICE_FORMATTER.format(n)}
            />
            {changePct ? (
              <span
                className={cn(
                  "rounded-full px-2 py-0.5 text-xs font-medium tabular-nums",
                  changeIsPositive
                    ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                    : "bg-rose-500/10 text-rose-600 dark:text-rose-400",
                )}
                aria-label={`Period change ${changePct}`}
              >
                {changePct}
              </span>
            ) : null}
          </>
        ) : null}
      </div>
    </div>
  );
}

interface BenchmarkLegendProps {
  symbol: string;
  benchmarkSymbol: string;
  benchmarkLabel: string;
  benchmarkTooltip: string;
}

function BenchmarkLegend({
  symbol,
  benchmarkSymbol,
  benchmarkLabel,
  benchmarkTooltip,
}: BenchmarkLegendProps) {
  const reduced = useReducedMotion();
  const primaryDot = seriesColor(0);
  const benchmarkDot = seriesColor(1);
  return (
    <motion.div
      initial={reduced ? false : { opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={
        reduced ? { duration: 0 } : { duration: DURATION.fast, ease: EASE.standard }
      }
      className="flex items-center gap-3 text-xs text-muted-foreground"
      data-testid="benchmark-legend"
    >
      <span className="inline-flex items-center gap-1.5">
        <span
          aria-hidden
          className="inline-block size-2 rounded-full"
          style={{ backgroundColor: primaryDot }}
        />
        <span className="font-medium text-foreground">{symbol}</span>
      </span>
      <span className="text-muted-foreground/60">·</span>
      <RichTooltip
        side="top"
        ariaLabel={`${benchmarkSymbol} description`}
        trigger={
          <span
            tabIndex={0}
            className="inline-flex cursor-help items-center gap-1.5 rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <span
              aria-hidden
              className="inline-block size-2 rounded-full"
              style={{ backgroundColor: benchmarkDot }}
            />
            <span>{benchmarkLabel}</span>
          </span>
        }
      >
        <div className="flex flex-col gap-1 text-sm">
          <span className="font-medium text-foreground">{benchmarkSymbol}</span>
          <span className="text-muted-foreground">{benchmarkTooltip}</span>
        </div>
      </RichTooltip>
    </motion.div>
  );
}

export default HoldingPriceChart;
