import * as React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";

vi.mock("@/services/api", () => {
  return {
    marketDataApi: {
      getHistory: vi.fn(),
      getSnapshot: vi.fn(),
    },
    activityApi: {
      getActivity: vi.fn(),
    },
    unwrapResponse: <T,>(raw: unknown, key: string): T[] => {
      const r = raw as Record<string, any> | undefined;
      return (r?.data?.data?.[key] ?? r?.data?.[key] ?? r?.[key] ?? []) as T[];
    },
  };
});

import { activityApi, marketDataApi } from "@/services/api";
import { useHoldingChartData } from "../useHoldingChartData";

function makeTrackingClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0, staleTime: 0 },
    },
  });
}

function wrapperWithClient(client: QueryClient) {
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );
  };
}

const mockHistory = vi.mocked(marketDataApi.getHistory);
const mockSnapshot = vi.mocked(marketDataApi.getSnapshot);
const mockActivity = vi.mocked(activityApi.getActivity);

function makeWrapper() {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0, staleTime: 0 },
    },
  });
  function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );
  }
  return Wrapper;
}

function priceResponse(symbol: string, days: number, base: number = 100) {
  const bars = Array.from({ length: days }).map((_, i) => {
    const date = new Date(Date.UTC(2026, 0, 1 + i)).toISOString().slice(0, 10);
    const v = base + i;
    return { time: date, open: v - 0.5, high: v + 1, low: v - 1, close: v, volume: 1000 };
  });
  return { symbol, period: "1y", interval: "1d", bars };
}

// Pin the system clock so tests that derive the "Since I bought" period
// from a hardcoded ISO date stay deterministic regardless of when the
// suite actually runs (previously a real-time clock could flip 2026-01-05
// from "in the past" to "in the future" depending on the calendar).
// Use `shouldAdvanceTime: true` so React Query's internal timers (e.g.
// gcTime / staleTime polling) keep ticking under fake timers.
const FROZEN_NOW = new Date("2026-06-15T00:00:00Z");

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  vi.setSystemTime(FROZEN_NOW);
  mockHistory.mockReset();
  mockSnapshot.mockReset();
  mockActivity.mockReset();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("useHoldingChartData", () => {
  it("resolves benchmark from snapshot sector and fetches both series", async () => {
    mockSnapshot.mockResolvedValueOnce({
      symbol: "AAPL",
      snapshot: { sector: "Technology", instrument_type: "EQUITY" },
    });
    mockActivity.mockResolvedValueOnce({
      activity: [{ transaction_date: "2025-08-01T10:00:00Z", side: "BUY" }],
    });
    mockHistory.mockImplementation(async (sym: string) => priceResponse(sym, 10));

    const { result } = renderHook(
      () => useHoldingChartData({ symbol: "AAPL", period: "1y" }),
      { wrapper: makeWrapper() },
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.benchmarkSymbol).toBe("XLK");
    expect(result.current.benchmarkLabel).toContain("XLK");
    expect(result.current.bars).toHaveLength(10);
    expect(result.current.benchmarkBars).toHaveLength(10);
    expect(mockHistory).toHaveBeenCalledWith("AAPL", "1y", "1d");
    expect(mockHistory).toHaveBeenCalledWith("XLK", "1y", "1d");
  });

  it("suppresses the benchmark fetch when symbol === benchmark", async () => {
    mockSnapshot.mockResolvedValueOnce({
      symbol: "SPY",
      snapshot: { instrument_type: "ETF" },
    });
    mockActivity.mockResolvedValueOnce({ activity: [] });
    mockHistory.mockResolvedValueOnce(priceResponse("SPY", 5));

    const { result } = renderHook(
      () => useHoldingChartData({ symbol: "SPY", period: "1y" }),
      { wrapper: makeWrapper() },
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.benchmarkSymbol).toBe("");
    expect(result.current.benchmarkBars).toEqual([]);
    expect(result.current.bars).toHaveLength(5);
    // Only the primary symbol should have been fetched.
    expect(mockHistory).toHaveBeenCalledTimes(1);
    expect(mockHistory).toHaveBeenCalledWith("SPY", "1y", "1d");
  });

  it("derives 'since' period from earliest buy date", async () => {
    mockSnapshot.mockResolvedValueOnce({
      symbol: "AAPL",
      snapshot: { sector: "Technology" },
    });
    mockActivity.mockResolvedValueOnce({
      activity: [
        { transaction_date: "2025-09-01T10:00:00Z", side: "BUY" },
        { transaction_date: "2025-12-15T10:00:00Z", side: "BUY" },
      ],
    });
    mockHistory.mockImplementation(async (sym: string) => priceResponse(sym, 10));

    const { result } = renderHook(
      () => useHoldingChartData({ symbol: "AAPL", period: "since" }),
      { wrapper: makeWrapper() },
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.earliestBuyDate).toBe("2025-09-01");
    expect(result.current.effectiveStart).toBe("2025-09-01");
    // Either '1y' or '5y' depending on today's date — assert on the
    // BACKEND_PERIODS membership rather than a fixed string so the test
    // doesn't break with the calendar.
    expect(["1y", "5y", "max"]).toContain(result.current.effectivePeriod);
  });

  it("falls back to '1y' for 'since' when there are no buys", async () => {
    mockSnapshot.mockResolvedValueOnce({
      symbol: "AAPL",
      snapshot: { sector: "Technology" },
    });
    mockActivity.mockResolvedValueOnce({ activity: [] });
    mockHistory.mockImplementation(async (sym: string) => priceResponse(sym, 5));

    const { result } = renderHook(
      () => useHoldingChartData({ symbol: "AAPL", period: "since" }),
      { wrapper: makeWrapper() },
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.earliestBuyDate).toBeNull();
    expect(result.current.effectivePeriod).toBe("1y");
    expect(result.current.effectiveStart).toBeNull();
  });

  it("trims bars to the earliest buy date when period === 'since'", async () => {
    mockSnapshot.mockResolvedValueOnce({
      symbol: "AAPL",
      snapshot: { sector: "Technology" },
    });
    mockActivity.mockResolvedValueOnce({
      activity: [{ transaction_date: "2026-01-05T10:00:00Z", side: "BUY" }],
    });
    // 10 bars starting 2026-01-01; cutoff at 2026-01-05 should retain 6.
    mockHistory.mockImplementation(async (sym: string) => priceResponse(sym, 10));

    const { result } = renderHook(
      () => useHoldingChartData({ symbol: "AAPL", period: "since" }),
      { wrapper: makeWrapper() },
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.bars[0].time).toBe("2026-01-05");
    expect(result.current.bars).toHaveLength(6);
    expect(result.current.benchmarkBars[0].time).toBe("2026-01-05");
    expect(result.current.benchmarkBars).toHaveLength(6);
  });

  it("respects an explicit benchmark override", async () => {
    mockSnapshot.mockResolvedValueOnce({
      symbol: "AAPL",
      snapshot: { sector: "Technology", instrument_type: "EQUITY" },
    });
    mockActivity.mockResolvedValueOnce({ activity: [] });
    mockHistory.mockImplementation(async (sym: string) => priceResponse(sym, 5));

    const { result } = renderHook(
      () =>
        useHoldingChartData({
          symbol: "AAPL",
          period: "1y",
          benchmarkOverride: "QQQ",
        }),
      { wrapper: makeWrapper() },
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.benchmarkSymbol).toBe("QQQ");
    expect(mockHistory).toHaveBeenCalledWith("QQQ", "1y", "1d");
  });

  it("surfaces errors from any underlying query", async () => {
    mockSnapshot.mockResolvedValueOnce({
      symbol: "AAPL",
      snapshot: { sector: "Technology" },
    });
    mockActivity.mockResolvedValueOnce({ activity: [] });
    mockHistory.mockRejectedValueOnce(new Error("boom"));
    mockHistory.mockResolvedValueOnce(priceResponse("XLK", 5));

    const { result } = renderHook(
      () => useHoldingChartData({ symbol: "AAPL", period: "1y" }),
      { wrapper: makeWrapper() },
    );

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toBeInstanceOf(Error);
  });

  it("does not run any query when disabled", () => {
    renderHook(
      () => useHoldingChartData({ symbol: "AAPL", period: "1y", enabled: false }),
      { wrapper: makeWrapper() },
    );
    expect(mockSnapshot).not.toHaveBeenCalled();
    expect(mockActivity).not.toHaveBeenCalled();
    expect(mockHistory).not.toHaveBeenCalled();
  });

  it("skips the benchmark fetch when fetchBenchmark is false", async () => {
    mockSnapshot.mockResolvedValueOnce({
      symbol: "AAPL",
      snapshot: { sector: "Technology", instrument_type: "EQUITY" },
    });
    mockActivity.mockResolvedValueOnce({ activity: [] });
    mockHistory.mockResolvedValueOnce(priceResponse("AAPL", 5));

    const { result } = renderHook(
      () =>
        useHoldingChartData({
          symbol: "AAPL",
          period: "1y",
          fetchBenchmark: false,
        }),
      { wrapper: makeWrapper() },
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    // Only the primary symbol — never the resolved XLK benchmark — should
    // have hit the network. This protects against the wasted-bandwidth
    // regression where `showBenchmark={false}` consumers still paid for
    // the benchmark fetch.
    expect(mockHistory).toHaveBeenCalledTimes(1);
    expect(mockHistory).toHaveBeenCalledWith("AAPL", "1y", "1d");
    expect(mockHistory).not.toHaveBeenCalledWith("XLK", "1y", "1d");
    // And the legend strings should be blanked so consumers don't render
    // a benchmark chip for a series we never fetched.
    expect(result.current.benchmarkSymbol).toBe("");
    expect(result.current.benchmarkLabel).toBe("");
    expect(result.current.benchmarkBars).toEqual([]);
  });

  it("invalidates every cached query that mentions the symbol or its benchmark on refetch", async () => {
    mockSnapshot.mockResolvedValueOnce({
      symbol: "AAPL",
      snapshot: { sector: "Technology", instrument_type: "EQUITY" },
    });
    mockActivity.mockResolvedValueOnce({ activity: [] });
    mockHistory.mockImplementation(async (sym: string) => priceResponse(sym, 5));

    const client = makeTrackingClient();
    const { result } = renderHook(
      () => useHoldingChartData({ symbol: "AAPL", period: "1y" }),
      { wrapper: wrapperWithClient(client) },
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    // Sanity-check the cache is populated under the real keys the hook
    // uses (the previous bug was: refetch invalidated the WRONG key).
    const symbolKey = ["holdingChart", "snapshot", "AAPL"];
    const priceKey = ["holdingChart", "price", "AAPL", "1y"];
    const benchKey = ["holdingChart", "benchmarkPrice", "XLK", "1y"];
    expect(client.getQueryState(symbolKey)).toBeDefined();
    expect(client.getQueryState(priceKey)).toBeDefined();
    expect(client.getQueryState(benchKey)).toBeDefined();

    await result.current.refetch();

    // Every query whose key mentions the symbol OR its resolved
    // benchmark must be flagged invalidated. Without the predicate-based
    // `invalidateQueries` we ship in this fix, none of these would flip.
    expect(client.getQueryState(symbolKey)?.isInvalidated).toBe(true);
    expect(client.getQueryState(priceKey)?.isInvalidated).toBe(true);
    expect(client.getQueryState(benchKey)?.isInvalidated).toBe(true);
  });

  it("returns an empty bar list when the backend hands back a non-array shape", async () => {
    mockSnapshot.mockResolvedValueOnce({
      symbol: "AAPL",
      snapshot: { sector: "Technology" },
    });
    mockActivity.mockResolvedValueOnce({ activity: [] });
    // Simulate a future API drift where `bars` is an object (or null).
    // Without the `Array.isArray` guard, `.filter()` would throw and
    // crash the chart instead of degrading to "empty".
    mockHistory.mockResolvedValue({
      symbol: "AAPL",
      period: "1y",
      interval: "1d",
      bars: { unexpected: "shape" },
    } as unknown as ReturnType<typeof priceResponse>);

    const { result } = renderHook(
      () =>
        useHoldingChartData({
          symbol: "AAPL",
          period: "1y",
          fetchBenchmark: false,
        }),
      { wrapper: makeWrapper() },
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    // The guard kicks in: bars is non-array → `[]`. The hook does not
    // crash, no error is surfaced, the chart degrades to empty.
    expect(result.current.bars).toEqual([]);
    expect(result.current.isError).toBe(false);
  });
});
