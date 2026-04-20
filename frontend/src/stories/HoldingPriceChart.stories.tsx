/**
 * Ladle stories for the flagship HoldingPriceChart.
 *
 * Each story drives the underlying data hook through a vi.mock-style
 * monkey patch on the global `globalThis.__HOLDING_CHART_FIXTURES__`
 * (set by the story before render) — but to keep things deterministic we
 * use a simpler approach here: a `MockedHoldingPriceChart` wrapper that
 * applies a per-story shim around the data hook via React Query primed
 * caches. This avoids depending on MSW for design-tool browsing.
 */
import * as React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { HoldingPriceChart } from "../components/charts/HoldingPriceChart";

export default {
  title: "Charts / HoldingPriceChart",
};

function makeBars(n: number, base = 100) {
  const today = Date.now();
  const day = 86_400_000;
  return Array.from({ length: n }).map((_, i) => {
    const date = new Date(today - (n - i) * day).toISOString().slice(0, 10);
    // Smooth-ish synthetic series so the chart looks like a real holding
    // rather than random noise in the design tool.
    const drift = base + i * 0.4;
    const wave = Math.sin(i / 6) * 4;
    const close = drift + wave;
    return {
      time: date,
      open: close - 0.6,
      high: close + 1.2,
      low: close - 1.1,
      close,
      volume: 1_000_000,
    };
  });
}

function primeCache(
  client: QueryClient,
  symbol: string,
  bars: ReturnType<typeof makeBars>,
  benchmarkSymbol: string | null,
  benchmarkBars: ReturnType<typeof makeBars>,
  snapshot: Record<string, unknown> | null,
  activity: Array<{ transaction_date: string; side: string }>,
) {
  client.setQueryData(["holdingChart", "snapshot", symbol], { snapshot });
  client.setQueryData(["holdingChart", "activity", symbol, null], { activity });
  client.setQueryData(["holdingChart", "price", symbol, "1y"], { symbol, bars });
  if (benchmarkSymbol) {
    client.setQueryData(
      ["holdingChart", "benchmarkPrice", benchmarkSymbol, "1y"],
      { symbol: benchmarkSymbol, bars: benchmarkBars },
    );
  }
}

function StoryShell({ children }: { children: React.ReactNode }) {
  const [client] = React.useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: Infinity,
            retry: false,
            refetchOnWindowFocus: false,
          },
        },
      }),
  );
  return (
    <QueryClientProvider client={client}>
      <div className="min-h-screen bg-background p-6 text-foreground">
        {children}
      </div>
    </QueryClientProvider>
  );
}

function PrimeAndRender({
  symbol,
  benchmarkSymbol,
  snapshot,
  activity,
  initialPeriod,
  showBenchmark = true,
}: {
  symbol: string;
  benchmarkSymbol: string | null;
  snapshot: Record<string, unknown> | null;
  activity?: Array<{ transaction_date: string; side: string }>;
  initialPeriod?: "1y" | "3mo" | "since" | "max";
  showBenchmark?: boolean;
}) {
  const [client] = React.useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: Infinity,
            retry: false,
            refetchOnWindowFocus: false,
          },
        },
      }),
  );
  React.useEffect(() => {
    const bars = makeBars(180, 150);
    const benchmarkBars = makeBars(180, 100);
    primeCache(
      client,
      symbol,
      bars,
      benchmarkSymbol,
      benchmarkBars,
      snapshot,
      activity ?? [],
    );
  }, [client, symbol, benchmarkSymbol, snapshot, activity]);
  return (
    <QueryClientProvider client={client}>
      <div className="min-h-screen bg-background p-6 text-foreground">
        <div className="mx-auto max-w-5xl">
          <HoldingPriceChart
            symbol={symbol}
            initialPeriod={initialPeriod}
            showBenchmark={showBenchmark}
          />
        </div>
      </div>
    </QueryClientProvider>
  );
}

/** Default flagship view: AAPL with sector benchmark XLK and a "Since I bought" anchor. */
export const Default = () => (
  <PrimeAndRender
    symbol="AAPL"
    benchmarkSymbol="XLK"
    snapshot={{ sector: "Technology", instrument_type: "EQUITY" }}
    activity={[{ transaction_date: "2025-09-01T10:00:00Z", side: "BUY" }]}
    initialPeriod="since"
  />
);

/** No trades yet — the 'Since I bought' option is suppressed and SPY is the fallback. */
export const NoTradesYet = () => (
  <PrimeAndRender
    symbol="MSFT"
    benchmarkSymbol="SPY"
    snapshot={{ sector: null, instrument_type: "EQUITY" }}
    activity={[]}
    initialPeriod="1y"
  />
);

/** ETF holding: benchmark suppressed because SPY === SPY. */
export const EtfHolding = () => (
  <PrimeAndRender
    symbol="SPY"
    benchmarkSymbol={null}
    snapshot={{ sector: null, instrument_type: "ETF" }}
    activity={[]}
    initialPeriod="1y"
  />
);

/** Crypto holding: ETH-USD vs BTC-USD. */
export const CryptoHolding = () => (
  <PrimeAndRender
    symbol="ETH-USD"
    benchmarkSymbol="BTC-USD"
    snapshot={{ instrument_type: "CRYPTO" }}
    activity={[{ transaction_date: "2025-06-12T10:00:00Z", side: "BUY" }]}
    initialPeriod="since"
  />
);

/** Loading state: nothing primed in the cache → hook reports isLoading. */
export const Loading = () => (
  <StoryShell>
    <div className="mx-auto max-w-5xl">
      <HoldingPriceChart symbol="LOADING-DEMO" initialPeriod="1y" />
    </div>
  </StoryShell>
);

/** Error state: every query under `holdingChart/*` rejects. */
export const ErrorStateStory = () => {
  const [client] = React.useState(() => {
    const c = new QueryClient({
      defaultOptions: {
        queries: { staleTime: Infinity, retry: false, refetchOnWindowFocus: false },
      },
    });
    // setQueryDefaults installs the queryFn for ANY key starting with
    // ["holdingChart"], so the FIRST call by the hook actually executes
    // (and throws). The previous `cache.build()` approach only registered
    // a key that the hook never subscribed to → query never ran → no
    // error state ever surfaced in the visual story.
    c.setQueryDefaults(["holdingChart"], {
      queryFn: async () => {
        throw new Error("Network unreachable (story)");
      },
      staleTime: Infinity,
      retry: false,
      refetchOnWindowFocus: false,
    });
    return c;
  });
  return (
    <QueryClientProvider client={client}>
      <div className="min-h-screen bg-background p-6 text-foreground">
        <div className="mx-auto max-w-5xl">
          <HoldingPriceChart symbol="ERR" initialPeriod="1y" />
        </div>
      </div>
    </QueryClientProvider>
  );
};
