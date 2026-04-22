import * as React from "react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

// ── lightweight-charts: stubbed so we can assert series creation without
// pulling in WebGL and without leaking real DOM nodes between tests.
const addSeriesMock = vi.fn();
const removeSeriesMock = vi.fn();
const setDataMock = vi.fn();
const removeMock = vi.fn();
const fitContentMock = vi.fn();
const applyOptionsMock = vi.fn();
const createChartMock = vi.fn();
const createSeriesMarkersMock = vi.fn();
const setMarkersMock = vi.fn();
const subscribeVisibleTimeRangeChangeMock = vi.fn();
const unsubscribeVisibleTimeRangeChangeMock = vi.fn();
const timeToCoordinateMock = vi.fn<(time: unknown) => number | null>(() => null);
// Track the series-instance applyOptions calls per kind so theme-reactivity
// tests can assert that BOTH the primary AreaSeries and (if present) the
// benchmark LineSeries get re-skinned on a palette change event.
type AnyFn = (...args: unknown[]) => unknown;
const seriesApplyOptionsByKind: Record<string, ReturnType<typeof vi.fn<AnyFn>>> = {
  Area: vi.fn<AnyFn>(),
  Line: vi.fn<AnyFn>(),
};

vi.mock("lightweight-charts", () => {
  const stubSeries = (kind: string) => {
    const api = {
      setData: setDataMock,
      applyOptions: (opts: Record<string, unknown>) => {
        seriesApplyOptionsByKind[kind]?.(opts);
      },
      priceLineVisible: false,
    };
    return api;
  };
  return {
    AreaSeries: { __kind: "Area" },
    LineSeries: { __kind: "Line" },
    LineStyle: { Dotted: 1, Dashed: 2, Solid: 0 },
    createChart: (...args: unknown[]) => {
      createChartMock(...args);
      const chart = {
        addSeries: (def: { __kind: string }) => {
          addSeriesMock(def);
          return stubSeries(def.__kind);
        },
        removeSeries: removeSeriesMock,
        timeScale: () => ({
          fitContent: fitContentMock,
          subscribeVisibleTimeRangeChange:
            subscribeVisibleTimeRangeChangeMock,
          unsubscribeVisibleTimeRangeChange:
            unsubscribeVisibleTimeRangeChangeMock,
          timeToCoordinate: timeToCoordinateMock,
        }),
        applyOptions: applyOptionsMock,
        remove: removeMock,
      };
      return chart;
    },
    createSeriesMarkers: (
      series: unknown,
      markers: ReadonlyArray<unknown>,
    ) => {
      createSeriesMarkersMock(series, markers);
      return {
        setMarkers: setMarkersMock,
        markers: () => markers,
        detach: () => undefined,
      };
    },
  };
});

// ── Mock the data hook so we can drive states deterministically.
vi.mock("@/lib/holdingChart/useHoldingChartData", () => {
  return {
    useHoldingChartData: vi.fn(),
  };
});

vi.mock("@/lib/holdingChart/useHoldingIndicators", () => {
  return {
    useHoldingIndicators: vi.fn(),
  };
});

import { useHoldingChartData } from "@/lib/holdingChart/useHoldingChartData";
import { useHoldingIndicators } from "@/lib/holdingChart/useHoldingIndicators";
import type {
  DividendBucket,
  TradeBucket,
} from "@/lib/holdingChart/tradeMarkers";
import { HoldingPriceChart } from "../HoldingPriceChart";

const mockUseData = vi.mocked(useHoldingChartData);
const mockUseIndicators = vi.mocked(useHoldingIndicators);

function withIndicatorDefaults(
  partial: Partial<ReturnType<typeof useHoldingIndicators>> = {},
): ReturnType<typeof useHoldingIndicators> {
  return {
    series: {},
    stageSegments: [],
    rows: 0,
    backfillRequested: false,
    pricePending: false,
    isLoading: false,
    isError: false,
    error: null,
    refetch: vi.fn().mockResolvedValue(undefined),
    ...partial,
  };
}

function makeBars(n: number, base = 100) {
  return Array.from({ length: n }).map((_, i) => {
    const date = new Date(Date.UTC(2026, 0, 1 + i)).toISOString().slice(0, 10);
    const v = base + i;
    return {
      time: date,
      open: v - 0.5,
      high: v + 1,
      low: v - 1,
      close: v,
      volume: 1000,
    };
  });
}

function withDefaults(partial: Partial<ReturnType<typeof useHoldingChartData>> = {}) {
  const defaults: ReturnType<typeof useHoldingChartData> = {
    symbol: "AAPL",
    bars: makeBars(20),
    benchmarkBars: makeBars(20, 50).map((b) => ({ time: b.time, close: b.close })),
    benchmarkSymbol: "XLK",
    benchmarkLabel: "vs XLK",
    benchmarkTooltip: "Technology Select Sector SPDR",
    snapshot: { sector: "Technology" },
    trades: [],
    tradeMarkers: [],
    dividends: [],
    earliestBuyDate: "2025-09-01",
    effectivePeriod: "1y",
    effectiveStart: null,
    isLoading: false,
    isError: false,
    error: null,
    refetch: vi.fn().mockResolvedValue(undefined),
  };
  return { ...defaults, ...partial };
}

function renderChart(
  ui: React.ReactElement = <HoldingPriceChart symbol="AAPL" height={400} />,
) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>{ui}</QueryClientProvider>,
  );
}

beforeEach(() => {
  addSeriesMock.mockReset();
  removeSeriesMock.mockReset();
  setDataMock.mockReset();
  removeMock.mockReset();
  fitContentMock.mockReset();
  applyOptionsMock.mockReset();
  createChartMock.mockReset();
  createSeriesMarkersMock.mockReset();
  setMarkersMock.mockReset();
  subscribeVisibleTimeRangeChangeMock.mockReset();
  unsubscribeVisibleTimeRangeChangeMock.mockReset();
  timeToCoordinateMock.mockReset();
  timeToCoordinateMock.mockImplementation(() => null);
  seriesApplyOptionsByKind.Area.mockReset();
  seriesApplyOptionsByKind.Line.mockReset();
  mockUseData.mockReset();
  mockUseIndicators.mockReset();
  mockUseIndicators.mockReturnValue(withIndicatorDefaults());
});

describe("HoldingPriceChart", () => {
  it("renders the skeleton during initial load", () => {
    mockUseData.mockReturnValue(
      withDefaults({ isLoading: true, bars: [], benchmarkBars: [] }),
    );
    renderChart();
    expect(screen.getByTestId("price-chart-skeleton")).toBeInTheDocument();
  });

  it("renders the error state with a retry handler when fetch fails", async () => {
    const refetch = vi.fn().mockResolvedValue(undefined);
    mockUseData.mockReturnValue(
      withDefaults({
        isLoading: false,
        isError: true,
        error: new Error("boom"),
        bars: [],
        benchmarkBars: [],
        refetch,
      }),
    );
    renderChart();
    expect(screen.getByText("Couldn't load chart")).toBeInTheDocument();
    const retry = screen.getByRole("button", { name: /try again/i });
    fireEvent.click(retry);
    await waitFor(() => expect(refetch).toHaveBeenCalledTimes(1));
  });

  it("renders the chart with primary + benchmark series after load", async () => {
    mockUseData.mockReturnValue(withDefaults());
    renderChart();
    // Two series added: primary (Area) + benchmark (Line).
    await waitFor(() => expect(addSeriesMock).toHaveBeenCalled());
    const kinds = addSeriesMock.mock.calls.map((c) => c[0].__kind);
    expect(kinds).toContain("Area");
    expect(kinds).toContain("Line");
    expect(setDataMock).toHaveBeenCalled();
    expect(screen.getByTestId("benchmark-legend")).toBeInTheDocument();
  });

  it("does NOT render a benchmark series when benchmarkBars is empty", async () => {
    mockUseData.mockReturnValue(
      withDefaults({
        benchmarkBars: [],
        benchmarkSymbol: "",
        benchmarkLabel: "",
        benchmarkTooltip: "",
      }),
    );
    renderChart();
    await waitFor(() => expect(addSeriesMock).toHaveBeenCalled());
    const kinds = addSeriesMock.mock.calls.map((c) => c[0].__kind);
    expect(kinds).toContain("Area");
    expect(kinds).not.toContain("Line");
    expect(screen.queryByTestId("benchmark-legend")).toBeNull();
  });

  it("hides the 'Since I bought' option when there are no buys", () => {
    mockUseData.mockReturnValue(withDefaults({ earliestBuyDate: null }));
    renderChart();
    expect(
      screen.queryByRole("radio", { name: /since i bought/i }),
    ).toBeNull();
    expect(screen.getByRole("radio", { name: /1Y/i })).toBeInTheDocument();
  });

  it("shows the 'Since I bought' option when activity has buys", () => {
    mockUseData.mockReturnValue(withDefaults());
    renderChart();
    expect(
      screen.getByRole("radio", { name: /since i bought/i }),
    ).toBeInTheDocument();
  });

  it("calls onPeriodChange when a different period is picked", () => {
    const onPeriodChange = vi.fn();
    mockUseData.mockReturnValue(withDefaults());
    renderChart(
      <HoldingPriceChart
        symbol="AAPL"
        height={400}
        initialPeriod="1y"
        onPeriodChange={onPeriodChange}
      />,
    );
    fireEvent.click(screen.getByRole("radio", { name: /3M/i }));
    expect(onPeriodChange).toHaveBeenCalledWith("3mo");
  });

  it("renders the empty-state copy when bars is empty (no skeleton, no error)", () => {
    mockUseData.mockReturnValue(
      withDefaults({
        bars: [],
        benchmarkBars: [],
        benchmarkSymbol: "",
        benchmarkLabel: "",
        benchmarkTooltip: "",
      }),
    );
    renderChart();
    expect(screen.getByTestId("holding-chart-empty")).toBeInTheDocument();
  });

  it("exposes the chart container with role=img and a descriptive aria-label", () => {
    mockUseData.mockReturnValue(withDefaults());
    renderChart();
    const img = screen.getByRole("img", { name: /AAPL latest close/i });
    expect(img).toBeInTheDocument();
  });

  it("passes runtime-resolved color-mix() strings (not raw var(...)) to lightweight-charts", async () => {
    mockUseData.mockReturnValue(withDefaults());
    renderChart();
    await waitFor(() => expect(createChartMock).toHaveBeenCalled());
    const chartOpts = createChartMock.mock.calls[0]?.[1] as {
      layout?: { textColor?: string };
      grid?: {
        vertLines?: { color?: string };
        horzLines?: { color?: string };
      };
    };
    // Regression guard: textColor / grid.color must be a canvas-parseable
    // `rgb(...)` / `rgba(...)` string. lightweight-charts v5 rejects both
    // `var(--…)` (never resolved inside a canvas) and `oklch(...)` /
    // `color-mix(...)` (its parser doesn't support them), so we normalize
    // via DOM probe in `resolveThemeColors()`.
    expect(chartOpts.layout?.textColor).toMatch(/^rgba?\(/);
    expect(chartOpts.layout?.textColor).not.toContain("var(");
    expect(chartOpts.layout?.textColor).not.toMatch(/oklch|color-mix/);
    expect(chartOpts.grid?.vertLines?.color).toMatch(/^rgba?\(/);
    expect(chartOpts.grid?.horzLines?.color).toMatch(/^rgba?\(/);
  });

  it("re-skins chart + series colors when the palette change event fires", async () => {
    mockUseData.mockReturnValue(withDefaults());
    renderChart();
    await waitFor(() => expect(addSeriesMock).toHaveBeenCalled());

    applyOptionsMock.mockClear();
    seriesApplyOptionsByKind.Area.mockClear();
    seriesApplyOptionsByKind.Line.mockClear();

    window.dispatchEvent(new Event("axiomfolio:color-palette-change"));

    await waitFor(() => {
      expect(applyOptionsMock).toHaveBeenCalled();
      expect(seriesApplyOptionsByKind.Area).toHaveBeenCalled();
      expect(seriesApplyOptionsByKind.Line).toHaveBeenCalled();
    });
    const lastChart =
      applyOptionsMock.mock.calls[applyOptionsMock.mock.calls.length - 1];
    const chartCall = lastChart?.[0] as {
      layout?: { textColor?: string };
      grid?: {
        vertLines?: { color?: string };
        horzLines?: { color?: string };
      };
    };
    expect(chartCall.layout?.textColor).toMatch(/^rgba?\(/);
    expect(chartCall.grid?.vertLines?.color).toMatch(/^rgba?\(/);
    const areaCalls = seriesApplyOptionsByKind.Area.mock.calls;
    const areaCall = areaCalls[areaCalls.length - 1]?.[0] as {
      lineColor?: string;
      topColor?: string;
      bottomColor?: string;
    };
    expect(areaCall.lineColor).toBeTruthy();
    // withAlpha() composes then normalizes to canvas-safe rgb/rgba (same
    // invariant as resolveThemeColors / layout options).
    expect(areaCall.topColor).toMatch(/^rgba?\(/);
    expect(areaCall.topColor).not.toMatch(/oklch|color-mix/);
    expect(areaCall.bottomColor).toBe("transparent");
  });

  it("pauses the idle aliveness scrubber on mouseenter (no movement required)", async () => {
    mockUseData.mockReturnValue(withDefaults());
    renderChart();
    // Initial state: chart renders idle, so the scrubber should be in
    // the DOM. Wait for the chart container to mount before asserting.
    await waitFor(() => expect(addSeriesMock).toHaveBeenCalled());
    expect(screen.getByTestId("holding-chart-aliveness")).toBeInTheDocument();

    // mouseenter alone — without a follow-up mousemove — must mark the
    // chart non-idle. Previously only mousemove/mouseleave reset idle,
    // so a hovered-but-still cursor left the scrubber animating under it.
    const chartContainer = screen.getByRole("img", { name: /AAPL latest close/i });
    fireEvent.mouseEnter(chartContainer);

    await waitFor(() =>
      expect(screen.queryByTestId("holding-chart-aliveness")).toBeNull(),
    );
  });

  it("announces the empty-state copy (not 'loading') when bars is empty", () => {
    mockUseData.mockReturnValue(
      withDefaults({
        bars: [],
        benchmarkBars: [],
        benchmarkSymbol: "",
        benchmarkLabel: "",
        benchmarkTooltip: "",
      }),
    );
    renderChart();
    // The visible empty-state div shows the copy; the ChartAnnouncer
    // aria-live region must show the SAME copy so screen-reader users
    // hear "no data" instead of a misleading "AAPL chart loading."
    // Two nodes (one visible, one in the live region) carry the text.
    expect(screen.getAllByText("No price data yet for AAPL.").length).toBeGreaterThanOrEqual(1);
    const announcer = screen.getByTestId("chart-announcer");
    expect(announcer).toHaveTextContent("No price data yet for AAPL.");
    expect(announcer.textContent ?? "").not.toContain("chart loading");
  });

  it("re-skins chart colors when <html> class flips (theme toggle)", async () => {
    mockUseData.mockReturnValue(withDefaults());
    renderChart();
    await waitFor(() => expect(addSeriesMock).toHaveBeenCalled());

    applyOptionsMock.mockClear();

    // Simulate a light → dark theme toggle.
    document.documentElement.classList.add("dark");

    await waitFor(() => expect(applyOptionsMock).toHaveBeenCalled());
    document.documentElement.classList.remove("dark");
  });

  it("attaches markers via createSeriesMarkers when tradeMarkers is non-empty", async () => {
    const tradeMarkers = [
      {
        time: 1735689600 as unknown as number,
        position: "belowBar" as const,
        shape: "arrowUp" as const,
        color: "#10b981",
        id: "2026-01-01:buy",
      },
    ];
    mockUseData.mockReturnValue(
      withDefaults({
        tradeMarkers: tradeMarkers as ReturnType<
          typeof useHoldingChartData
        >["tradeMarkers"],
      }),
    );
    renderChart();
    await waitFor(() => expect(createSeriesMarkersMock).toHaveBeenCalled());
    const [, markersArg] = createSeriesMarkersMock.mock.calls[0] ?? [];
    expect(Array.isArray(markersArg)).toBe(true);
    expect((markersArg as unknown[]).length).toBe(1);
  });

  it("calls setMarkers (not createSeriesMarkers again) when markers update", async () => {
    const initialMarkers = [
      {
        time: 1735689600,
        position: "belowBar" as const,
        shape: "arrowUp" as const,
        color: "#10b981",
        id: "a",
      },
    ];
    mockUseData.mockReturnValue(
      withDefaults({
        tradeMarkers: initialMarkers as ReturnType<
          typeof useHoldingChartData
        >["tradeMarkers"],
      }),
    );
    const { rerender } = renderChart();
    await waitFor(() => expect(createSeriesMarkersMock).toHaveBeenCalledTimes(1));

    const updatedMarkers = [
      ...initialMarkers,
      {
        time: 1735776000,
        position: "aboveBar" as const,
        shape: "arrowDown" as const,
        color: "#ef4444",
        id: "b",
      },
    ];
    mockUseData.mockReturnValue(
      withDefaults({
        tradeMarkers: updatedMarkers as ReturnType<
          typeof useHoldingChartData
        >["tradeMarkers"],
      }),
    );
    rerender(
      <QueryClientProvider
        client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
      >
        <HoldingPriceChart symbol="AAPL" height={400} />
      </QueryClientProvider>,
    );

    await waitFor(() => expect(setMarkersMock).toHaveBeenCalled());
    // The plugin must be reused — never recreated on every data change.
    expect(createSeriesMarkersMock).toHaveBeenCalledTimes(1);
  });

  it("does NOT render the rich tooltip when the crosshair is off-chart", () => {
    mockUseData.mockReturnValue(withDefaults());
    renderChart();
    expect(screen.queryByTestId("holding-chart-tooltip")).toBeNull();
  });

  it("renders the rich tooltip with date + OHLC when crosshair is on-chart", async () => {
    // The chart's tooltip is only painted when the container has a
    // non-zero width AND the pointer is inside its bounding rect. In
    // JSDOM neither is true by default — ResizeObserver is a no-op
    // stub and getBoundingClientRect() returns a zero-area rect — so
    // we patch both for the duration of the test.
    const originalRO = globalThis.ResizeObserver;
    class ImmediateRO {
      private cb: ResizeObserverCallback;
      constructor(cb: ResizeObserverCallback) {
        this.cb = cb;
      }
      observe(target: Element): void {
        this.cb(
          [
            {
              target,
              contentRect: { width: 800, height: 400 } as DOMRectReadOnly,
            } as unknown as ResizeObserverEntry,
          ],
          this as unknown as ResizeObserver,
        );
      }
      unobserve(): void {}
      disconnect(): void {}
    }
    (globalThis as { ResizeObserver: typeof ResizeObserver }).ResizeObserver =
      ImmediateRO as unknown as typeof ResizeObserver;
    try {
      mockUseData.mockReturnValue(withDefaults());
      renderChart();
      await waitFor(() => expect(addSeriesMock).toHaveBeenCalled());
      const chartContainer = screen.getByRole("img", { name: /AAPL latest close/i });
      chartContainer.getBoundingClientRect = () =>
        ({
          left: 0,
          top: 0,
          right: 800,
          bottom: 400,
          width: 800,
          height: 400,
          x: 0,
          y: 0,
          toJSON: () => ({}),
        }) as DOMRect;
      fireEvent.mouseMove(chartContainer, { clientX: 400, clientY: 200 });
      const tooltip = await screen.findByTestId("holding-chart-tooltip");
      expect(tooltip.textContent).toMatch(/O/);
      expect(tooltip.textContent).toMatch(/C/);
    } finally {
      (globalThis as { ResizeObserver: typeof ResizeObserver }).ResizeObserver =
        originalRO;
    }
  });

  it("shows trade details inside the tooltip when hovering a trade day", async () => {
    const originalRO = globalThis.ResizeObserver;
    class ImmediateRO {
      private cb: ResizeObserverCallback;
      constructor(cb: ResizeObserverCallback) {
        this.cb = cb;
      }
      observe(target: Element): void {
        this.cb(
          [
            {
              target,
              contentRect: { width: 800, height: 400 } as DOMRectReadOnly,
            } as unknown as ResizeObserverEntry,
          ],
          this as unknown as ResizeObserver,
        );
      }
      unobserve(): void {}
      disconnect(): void {}
    }
    (globalThis as { ResizeObserver: typeof ResizeObserver }).ResizeObserver =
      ImmediateRO as unknown as typeof ResizeObserver;
    try {
      const bars = makeBars(20);
      const tradeDay = bars[10].time;
      const tradeBucket: TradeBucket = {
        dayKey: tradeDay,
        time: (Date.parse(tradeDay) / 1000) as unknown as TradeBucket["time"],
        buys: [
          { transaction_date: tradeDay, side: "BUY", quantity: 10, price: 105 },
        ],
        sells: [],
        totalShares: 10,
        weightedAvgPrice: 105,
      };
      mockUseData.mockReturnValue(
        withDefaults({
          bars,
          trades: [tradeBucket],
          tradeMarkers: [
            {
              time: tradeBucket.time,
              position: "belowBar",
              shape: "arrowUp",
              color: "#10b981",
              id: `${tradeDay}:buy`,
            } as ReturnType<typeof useHoldingChartData>["tradeMarkers"][number],
          ],
        }),
      );
      renderChart();
      const chartContainer = screen.getByRole("img", { name: /AAPL latest close/i });
      chartContainer.getBoundingClientRect = () =>
        ({
          left: 0,
          top: 0,
          right: 800,
          bottom: 400,
          width: 800,
          height: 400,
          x: 0,
          y: 0,
          toJSON: () => ({}),
        }) as DOMRect;
      // Hover roughly at index 10 of 20 bars → ~50% of width.
      fireEvent.mouseMove(chartContainer, { clientX: 400, clientY: 200 });
      const tooltip = await screen.findByTestId("holding-chart-tooltip");
      expect(tooltip.textContent ?? "").toMatch(/You bought/);
      expect(tooltip.textContent ?? "").toMatch(/10/);
    } finally {
      (globalThis as { ResizeObserver: typeof ResizeObserver }).ResizeObserver =
        originalRO;
    }
  });

  it("renders dividend dots only when timeToCoordinate yields finite values", async () => {
    timeToCoordinateMock.mockImplementation(() => 250);
    const dividend: DividendBucket = {
      dayKey: "2026-01-15",
      time: 1736899200 as unknown as DividendBucket["time"],
      exDate: "2026-01-15",
      perShare: 0.24,
      totalAmount: 4.8,
      rowCount: 1,
      currency: "USD",
    };
    mockUseData.mockReturnValue(
      withDefaults({ dividends: [dividend] }),
    );
    renderChart();
    // The row only mounts after the primary series flips ready and the
    // effect runs; wait for it and assert one dot.
    const row = await screen.findByTestId("dividend-dot-row");
    const dots = row.querySelectorAll("[role=listitem]");
    expect(dots.length).toBe(1);
    expect(dots[0].getAttribute("aria-label")).toMatch(/Dividend/);
    expect(dots[0].getAttribute("aria-label")).toMatch(/2026-01-15/);
  });

  it("renders no dividend row when there are no dividends", async () => {
    mockUseData.mockReturnValue(withDefaults({ dividends: [] }));
    renderChart();
    await waitFor(() => expect(addSeriesMock).toHaveBeenCalled());
    expect(screen.queryByTestId("dividend-dot-row")).toBeNull();
  });

  it("subscribes to visible time range changes when dividends are present", async () => {
    timeToCoordinateMock.mockImplementation(() => 250);
    const dividend: DividendBucket = {
      dayKey: "2026-01-15",
      time: 1736899200 as unknown as DividendBucket["time"],
      exDate: "2026-01-15",
      perShare: 0.24,
      totalAmount: 4.8,
      rowCount: 1,
      currency: "USD",
    };
    mockUseData.mockReturnValue(withDefaults({ dividends: [dividend] }));
    renderChart();
    await waitFor(() =>
      expect(subscribeVisibleTimeRangeChangeMock).toHaveBeenCalled(),
    );
  });

  it("preserves bucket↔coordinate pairing when the first dividend is off-screen", async () => {
    // Regression for Copilot review comments F + G. The previous
    // implementation maintained two parallel arrays — `xs[]` and the
    // unfiltered `dividends[]` — and paired them by index in the
    // renderer. When a dividend was off-screen its X was skipped from
    // `xs`, but its bucket was NOT skipped from `dividends`, so every
    // subsequent dot ended up rendered with the WRONG aria-label
    // (shifted by one). Now that visible buckets and coordinates are
    // paired at filter time as `VisibleDividend[]`, this drift is
    // unrepresentable. The test pins it down: three dividends, the
    // first off-screen, the surviving two dots must carry labels for
    // the SECOND and THIRD buckets — never the first.
    const off: DividendBucket = {
      dayKey: "2026-01-05",
      time: 1736035200 as unknown as DividendBucket["time"],
      exDate: "2026-01-05",
      perShare: 0.10,
      totalAmount: 1,
      rowCount: 1,
      currency: "USD",
    };
    const onA: DividendBucket = {
      dayKey: "2026-02-10",
      time: 1739145600 as unknown as DividendBucket["time"],
      exDate: "2026-02-10",
      perShare: 0.24,
      totalAmount: 4.8,
      rowCount: 1,
      currency: "USD",
    };
    const onB: DividendBucket = {
      dayKey: "2026-03-15",
      time: 1742000000 as unknown as DividendBucket["time"],
      exDate: "2026-03-15",
      perShare: 0.30,
      totalAmount: 6,
      rowCount: 1,
      currency: "USD",
    };

    // The first call returns `null` (off-screen), the next two return
    // finite x coordinates. Iteration in the effect is stable in
    // bucket order, so call #1 corresponds to `off`, call #2 to `onA`,
    // call #3 to `onB`.
    timeToCoordinateMock
      .mockImplementationOnce(() => null)
      .mockImplementationOnce(() => 250)
      .mockImplementationOnce(() => 500);

    mockUseData.mockReturnValue(
      withDefaults({ dividends: [off, onA, onB] }),
    );
    renderChart();

    const row = await screen.findByTestId("dividend-dot-row");
    const dots = row.querySelectorAll("[role=listitem]");
    expect(dots.length).toBe(2);

    const labels = Array.from(dots).map((d) => d.getAttribute("aria-label") ?? "");
    expect(labels[0]).toContain("2026-02-10");
    expect(labels[1]).toContain("2026-03-15");
    // The off-screen bucket's exDate must NOT leak onto either visible
    // dot — that was the literal symptom of the parallel-array bug.
    for (const label of labels) {
      expect(label).not.toContain("2026-01-05");
    }
  });

  // ────────────────────────── PR #4 additions ──────────────────────────

  it("renders the AxiomFolio metric strip when showMetricStrip is true", async () => {
    mockUseData.mockReturnValue(
      withDefaults({
        snapshot: {
          sector: "Technology",
          stage_label: "2B",
          rsi: 64.2,
          atrp_14: 2.4,
          macd: 1.32,
          adx: 28.6,
          rs_mansfield_pct: 14.3,
        },
      }),
    );
    renderChart(
      <HoldingPriceChart symbol="AAPL" height={400} showMetricStrip />,
    );
    await waitFor(() => expect(addSeriesMock).toHaveBeenCalled());
    expect(screen.getByTestId("axiom-metric-strip")).toBeInTheDocument();
    expect(screen.getByText("Stage")).toBeInTheDocument();
    expect(screen.getByText("RSI")).toBeInTheDocument();
    expect(screen.getByText("ATR%")).toBeInTheDocument();
    expect(screen.getByText("MACD")).toBeInTheDocument();
    expect(screen.getByText("ADX")).toBeInTheDocument();
    expect(screen.getByText("RS Mansfield")).toBeInTheDocument();
  });

  it("does NOT render the metric strip when showMetricStrip is false", async () => {
    mockUseData.mockReturnValue(withDefaults());
    renderChart(
      <HoldingPriceChart
        symbol="AAPL"
        height={400}
        showMetricStrip={false}
      />,
    );
    await waitFor(() => expect(addSeriesMock).toHaveBeenCalled());
    expect(screen.queryByTestId("axiom-metric-strip")).toBeNull();
  });

  it("adds extra Line series for each enabled SMA overlay", async () => {
    mockUseData.mockReturnValue(withDefaults());
    mockUseIndicators.mockReturnValue(
      withIndicatorDefaults({
        series: {
          sma_50: [{ time: "2026-01-01", value: 100 }],
          sma_200: [{ time: "2026-01-01", value: 95 }],
        },
        rows: 1,
      }),
    );
    renderChart(
      <HoldingPriceChart
        symbol="AAPL"
        height={400}
        overlays={["sma50", "sma200"]}
      />,
    );
    // Line kinds: 1 benchmark + 2 overlays = 3.
    await waitFor(() => {
      const lineCount = addSeriesMock.mock.calls.filter(
        (c) => c[0].__kind === "Line",
      ).length;
      expect(lineCount).toBeGreaterThanOrEqual(3);
    });
  });

  it("adds two Line series for the Bollinger overlay (upper + lower)", async () => {
    mockUseData.mockReturnValue(withDefaults());
    mockUseIndicators.mockReturnValue(
      withIndicatorDefaults({
        series: {
          bollinger_upper: [{ time: "2026-01-01", value: 105 }],
          bollinger_lower: [{ time: "2026-01-01", value: 95 }],
        },
        rows: 1,
      }),
    );
    renderChart(
      <HoldingPriceChart
        symbol="AAPL"
        height={400}
        overlays={["bollinger"]}
      />,
    );
    await waitFor(() => {
      // 1 benchmark + 2 bollinger lines = 3 Line series total.
      const lineCount = addSeriesMock.mock.calls.filter(
        (c) => c[0].__kind === "Line",
      ).length;
      expect(lineCount).toBeGreaterThanOrEqual(3);
    });
  });

  it("removes overlay series when the overlay is toggled off", async () => {
    mockUseData.mockReturnValue(withDefaults());
    mockUseIndicators.mockReturnValue(
      withIndicatorDefaults({
        series: {
          sma_50: [{ time: "2026-01-01", value: 100 }],
        },
        rows: 1,
      }),
    );
    const { rerender } = renderChart(
      <HoldingPriceChart
        symbol="AAPL"
        height={400}
        overlays={["sma50"]}
      />,
    );
    await waitFor(() => {
      const lineCount = addSeriesMock.mock.calls.filter(
        (c) => c[0].__kind === "Line",
      ).length;
      expect(lineCount).toBeGreaterThanOrEqual(2);
    });
    removeSeriesMock.mockClear();
    mockUseIndicators.mockReturnValue(withIndicatorDefaults());
    rerender(
      <QueryClientProvider
        client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
      >
        <HoldingPriceChart symbol="AAPL" height={400} overlays={[]} />
      </QueryClientProvider>,
    );
    await waitFor(() => expect(removeSeriesMock).toHaveBeenCalled());
  });

  it("renders the StageOverlay layer when showStageBands is true and segments are present", async () => {
    // The overlay short-circuits to `null` when the chart container has
    // zero width (no bands can be painted yet). JSDOM's ResizeObserver
    // is a no-op stub, so we install a synchronous one that fires the
    // first observation immediately with a realistic content rect.
    const originalRO = globalThis.ResizeObserver;
    class ImmediateRO {
      private cb: ResizeObserverCallback;
      constructor(cb: ResizeObserverCallback) {
        this.cb = cb;
      }
      observe(target: Element): void {
        this.cb(
          [
            {
              target,
              contentRect: { width: 800, height: 400 } as DOMRectReadOnly,
            } as unknown as ResizeObserverEntry,
          ],
          this as unknown as ResizeObserver,
        );
      }
      unobserve(): void {}
      disconnect(): void {}
    }
    (globalThis as { ResizeObserver: typeof ResizeObserver }).ResizeObserver =
      ImmediateRO as unknown as typeof ResizeObserver;
    try {
      // Return distinct x's for the segment's start vs end so the band
      // has non-zero width (the overlay drops bands where right <= left).
      let call = 0;
      timeToCoordinateMock.mockImplementation(() => {
        call += 1;
        return call === 1 ? 100 : 400;
      });
      mockUseData.mockReturnValue(withDefaults());
      mockUseIndicators.mockReturnValue(
        withIndicatorDefaults({
          stageSegments: [
            { startTime: "2026-01-01", endTime: "2026-01-10", label: "2B" },
          ],
          rows: 10,
        }),
      );
      renderChart(
        <HoldingPriceChart symbol="AAPL" height={400} showStageBands />,
      );
      const overlay = await screen.findByTestId("stage-overlay");
      expect(overlay).toBeInTheDocument();
    } finally {
      (globalThis as { ResizeObserver: typeof ResizeObserver }).ResizeObserver =
        originalRO;
    }
  });

  it("does NOT render the StageOverlay when showStageBands is false", async () => {
    mockUseData.mockReturnValue(withDefaults());
    mockUseIndicators.mockReturnValue(
      withIndicatorDefaults({
        stageSegments: [
          { startTime: "2026-01-01", endTime: "2026-01-10", label: "2B" },
        ],
      }),
    );
    renderChart(
      <HoldingPriceChart symbol="AAPL" height={400} showStageBands={false} />,
    );
    await waitFor(() => expect(addSeriesMock).toHaveBeenCalled());
    expect(screen.queryByTestId("stage-overlay")).toBeNull();
  });

  it("renders the overlay control group with stage band toggle", async () => {
    mockUseData.mockReturnValue(withDefaults());
    renderChart();
    await waitFor(() => expect(addSeriesMock).toHaveBeenCalled());
    expect(screen.getByTestId("overlay-controls")).toBeInTheDocument();
    expect(
      screen.getByRole("switch", { name: /stage bands/i }),
    ).toBeInTheDocument();
  });

  it("calls onOverlaysChange when an overlay button is toggled", async () => {
    mockUseData.mockReturnValue(withDefaults());
    const onOverlaysChange = vi.fn();
    renderChart(
      <HoldingPriceChart
        symbol="AAPL"
        height={400}
        overlays={[]}
        onOverlaysChange={onOverlaysChange}
      />,
    );
    await waitFor(() => expect(addSeriesMock).toHaveBeenCalled());
    const sma50Button = screen.getByRole("button", { name: /^SMA 50$/i });
    fireEvent.click(sma50Button);
    expect(onOverlaysChange).toHaveBeenCalledWith(["sma50"]);
  });

  it("calls onShowStageBandsChange when the stage band switch is toggled", async () => {
    mockUseData.mockReturnValue(withDefaults());
    const onShowStageBandsChange = vi.fn();
    renderChart(
      <HoldingPriceChart
        symbol="AAPL"
        height={400}
        showStageBands={false}
        onShowStageBandsChange={onShowStageBandsChange}
      />,
    );
    await waitFor(() => expect(addSeriesMock).toHaveBeenCalled());
    fireEvent.click(screen.getByRole("switch", { name: /stage bands/i }));
    expect(onShowStageBandsChange).toHaveBeenCalledWith(true);
  });

  it("re-skins active overlay series when the palette change event fires", async () => {
    mockUseData.mockReturnValue(withDefaults());
    mockUseIndicators.mockReturnValue(
      withIndicatorDefaults({
        series: {
          sma_50: [{ time: "2026-01-01", value: 100 }],
        },
        rows: 1,
      }),
    );
    renderChart(
      <HoldingPriceChart
        symbol="AAPL"
        height={400}
        overlays={["sma50"]}
      />,
    );
    await waitFor(() => expect(addSeriesMock).toHaveBeenCalled());
    seriesApplyOptionsByKind.Line.mockClear();
    window.dispatchEvent(new Event("axiomfolio:color-palette-change"));
    await waitFor(() => {
      expect(seriesApplyOptionsByKind.Line).toHaveBeenCalled();
    });
  });
});
