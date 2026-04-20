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
        timeScale: () => ({ fitContent: fitContentMock }),
        applyOptions: applyOptionsMock,
        remove: removeMock,
      };
      return chart;
    },
  };
});

// ── Mock the data hook so we can drive states deterministically.
vi.mock("@/lib/holdingChart/useHoldingChartData", () => {
  return {
    useHoldingChartData: vi.fn(),
  };
});

import { useHoldingChartData } from "@/lib/holdingChart/useHoldingChartData";
import { HoldingPriceChart } from "../HoldingPriceChart";

const mockUseData = vi.mocked(useHoldingChartData);

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
  seriesApplyOptionsByKind.Area.mockReset();
  seriesApplyOptionsByKind.Line.mockReset();
  mockUseData.mockReset();
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
    // Regression guard: the textColor / grid.color must NEVER contain
    // `var(--…)` — lightweight-charts paints to a canvas and cannot
    // resolve CSS variables, so anything but a concrete color string
    // silently falls back to the library default.
    expect(chartOpts.layout?.textColor).toMatch(/^color-mix\(/);
    expect(chartOpts.layout?.textColor).not.toContain("var(");
    expect(chartOpts.grid?.vertLines?.color).toMatch(/^color-mix\(/);
    expect(chartOpts.grid?.horzLines?.color).toMatch(/^color-mix\(/);
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
    expect(chartCall.layout?.textColor).toMatch(/^color-mix\(/);
    expect(chartCall.grid?.vertLines?.color).toMatch(/^color-mix\(/);
    const areaCalls = seriesApplyOptionsByKind.Area.mock.calls;
    const areaCall = areaCalls[areaCalls.length - 1]?.[0] as {
      lineColor?: string;
      topColor?: string;
      bottomColor?: string;
    };
    expect(areaCall.lineColor).toBeTruthy();
    expect(areaCall.topColor).toMatch(/^color-mix\(/);
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
});
