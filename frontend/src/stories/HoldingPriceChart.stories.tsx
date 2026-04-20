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

/**
 * Match the dividends API: an array of `{ symbol, ex_date, ... }`. The
 * hook filters client-side by symbol so the story can prime as many or
 * as few rows as it likes.
 */
type DividendSeed = {
  symbol: string;
  ex_date: string;
  pay_date?: string;
  dividend_per_share: number;
  shares_held: number;
  total_dividend: number;
  currency?: string;
};

/**
 * Match the activity API: rows like `{ transaction_date, side, quantity,
 * price, symbol }`. Only the fields used by the bucketing transform are
 * required; extra fields are ignored.
 */
type TradeSeed = {
  transaction_date: string;
  side: string;
  quantity?: number;
  price?: number;
  symbol?: string;
};

function primeCache(
  client: QueryClient,
  symbol: string,
  bars: ReturnType<typeof makeBars>,
  benchmarkSymbol: string | null,
  benchmarkBars: ReturnType<typeof makeBars>,
  snapshot: Record<string, unknown> | null,
  activity: Array<TradeSeed>,
  dividends: Array<DividendSeed> = [],
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
  // Dividends key is account-wide (the API has no `symbol` filter and
  // the cache slot is shared across holdings — see the queryKey comment
  // in `useHoldingChartData.ts`). `1y` → `periodToDividendDays('1y')`
  // → 365; mirror that here so the cache priming actually satisfies
  // the hook's `useQuery`.
  client.setQueryData(
    ["holdingChart", "dividends", null, 365],
    { dividends },
  );
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
  dividends,
  initialPeriod,
  showBenchmark = true,
}: {
  symbol: string;
  benchmarkSymbol: string | null;
  snapshot: Record<string, unknown> | null;
  activity?: Array<TradeSeed>;
  dividends?: Array<DividendSeed>;
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
      dividends ?? [],
    );
  }, [client, symbol, benchmarkSymbol, snapshot, activity, dividends]);
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

/**
 * Helper: produce N synthetic trade rows on dates spread across the last
 * `daysBack` days so the markers land on visible bars regardless of when
 * the story is rendered. We alternate buy / sell so the mixed-day branch
 * also gets exercised in the design tool.
 */
function makeTrades(
  symbol: string,
  daysBack: number,
  pattern: ReadonlyArray<{ side: "BUY" | "SELL"; qty: number; price: number }>,
): TradeSeed[] {
  const today = Date.now();
  const day = 86_400_000;
  return pattern.map((p, i) => ({
    transaction_date: new Date(
      today - (daysBack - i * Math.floor(daysBack / pattern.length)) * day,
    ).toISOString(),
    side: p.side,
    quantity: p.qty,
    price: p.price,
    symbol,
  }));
}

/**
 * Helper: produce N synthetic dividend rows on quarter-spaced ex-dates.
 * Mirrors the real cadence well enough that the dot row shows ~4
 * dividends across a 1-year window.
 */
function makeDividends(
  symbol: string,
  daysBack: number,
  count = 4,
): DividendSeed[] {
  const today = Date.now();
  const day = 86_400_000;
  return Array.from({ length: count }).map((_, i) => {
    const offset = Math.round((daysBack / (count + 1)) * (i + 1));
    return {
      symbol,
      ex_date: new Date(today - offset * day).toISOString(),
      dividend_per_share: 0.24,
      shares_held: 100,
      total_dividend: 24,
      currency: "USD",
    };
  });
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

/**
 * Trade markers only: mix of buys and sells across the period so each
 * marker shape (arrow up / arrow down / circle for mixed days) renders
 * in the gallery view. No dividends.
 */
export const WithTrades = () => (
  <PrimeAndRender
    symbol="AAPL"
    benchmarkSymbol="XLK"
    snapshot={{ sector: "Technology", instrument_type: "EQUITY" }}
    activity={makeTrades("AAPL", 360, [
      { side: "BUY", qty: 100, price: 150 },
      { side: "BUY", qty: 50, price: 162 },
      { side: "SELL", qty: 30, price: 178 },
      { side: "BUY", qty: 25, price: 165 },
      { side: "SELL", qty: 25, price: 188 },
    ])}
    initialPeriod="1y"
  />
);

/**
 * Dividend dots only: a year of quarterly dividend events show as the
 * indigo dot row at the bottom of the chart. Hover over each dot to see
 * the per-share / total in the rich tooltip.
 */
export const WithDividends = () => (
  <PrimeAndRender
    symbol="MSFT"
    benchmarkSymbol="XLK"
    snapshot={{ sector: "Technology", instrument_type: "EQUITY" }}
    activity={[]}
    dividends={makeDividends("MSFT", 360, 4)}
    initialPeriod="1y"
  />
);

/**
 * The full flagship rendering: trade markers on the price line AND
 * dividend dots underneath, with the rich crosshair tooltip surfacing
 * all three (price, trades, dividends) on the hovered day.
 */
export const WithBoth = () => (
  <PrimeAndRender
    symbol="AAPL"
    benchmarkSymbol="XLK"
    snapshot={{ sector: "Technology", instrument_type: "EQUITY" }}
    activity={makeTrades("AAPL", 360, [
      { side: "BUY", qty: 100, price: 150 },
      { side: "BUY", qty: 50, price: 162 },
      { side: "SELL", qty: 30, price: 178 },
    ])}
    dividends={makeDividends("AAPL", 360, 4)}
    initialPeriod="1y"
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

// ---------- PR #4: overlays + stage bands + metric strip ----------

/**
 * Build a synthetic indicator response that mirrors the
 * `IndicatorSeriesResponse` shape returned by the backend
 * `/market-data/prices/{symbol}/indicators` endpoint.
 *
 * `bars` must be the same array used to prime the price cache so the
 * indicator dates align bar-for-bar (otherwise overlay lines render at
 * times that don't exist on the chart).
 */
function makeIndicatorResponse(
  symbol: string,
  bars: ReturnType<typeof makeBars>,
  columns: ReadonlyArray<string>,
  options: { stageBands?: boolean } = {},
) {
  const dates = bars.map((b) => b.time);
  const series: Record<string, Array<number | string | null>> = { dates };
  for (const col of columns) {
    series[col] = bars.map((b, i) => {
      switch (col) {
        case 'sma_50':
          return b.close * 0.97 + Math.sin(i / 8) * 0.5;
        case 'sma_150':
          return b.close * 0.94;
        case 'sma_200':
          return b.close * 0.92;
        case 'ema_21':
          return b.close * 0.99 + Math.cos(i / 5) * 0.4;
        case 'bollinger_upper':
          return b.close + 4;
        case 'bollinger_lower':
          return b.close - 4;
        default:
          return b.close;
      }
    });
  }
  if (options.stageBands) {
    series.stage_label = bars.map((_, i) => {
      const segment = Math.floor(i / Math.max(1, Math.floor(bars.length / 4)));
      return ['1B', '2A', '2B', '2C'][segment % 4] ?? '2B';
    });
  }
  return {
    symbol,
    rows: dates.length,
    backfill_requested: false,
    price_data_pending: false,
    series,
  };
}

interface OverlayStoryProps {
  initialOverlays?: Array<
    'sma50' | 'sma100' | 'sma150' | 'sma200' | 'ema21' | 'ema200' | 'bollinger'
  >;
  initialStageBands?: boolean;
  showMetricStrip?: boolean;
}

function OverlayStory({
  initialOverlays = [],
  initialStageBands = false,
  showMetricStrip = true,
}: OverlayStoryProps) {
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

  const symbol = 'AAPL';
  React.useEffect(() => {
    const bars = makeBars(180, 150);
    const benchBars = makeBars(180, 100);
    primeCache(
      client,
      symbol,
      bars,
      'XLK',
      benchBars,
      {
        sector: 'Technology',
        instrument_type: 'EQUITY',
        stage_label: '2B',
        rsi: 64.2,
        atrp_14: 2.4,
        macd: 1.32,
        adx: 28.6,
        rs_mansfield_pct: 14.3,
      },
      [{ transaction_date: '2025-04-15T10:00:00Z', side: 'BUY' }],
      [],
    );

    // Prime indicator queries for every superset of the overlays the
    // story exposes, so toggling controls in the design tool feels
    // instant and never shows a loading flash.
    const allCols = [
      'sma_50',
      'sma_100',
      'sma_150',
      'sma_200',
      'ema_21',
      'ema_200',
      'bollinger_upper',
      'bollinger_lower',
    ];
    const seedKeys: Array<string[]> = [
      [...allCols],
      [...allCols, 'stage_label'],
    ];
    for (const cols of seedKeys) {
      const sorted = [...cols].sort();
      client.setQueryData(
        ['holdingChart', 'indicators', symbol, '1y', sorted.join(',')],
        makeIndicatorResponse(symbol, bars, cols, {
          stageBands: cols.includes('stage_label'),
        }),
      );
    }
  }, [client]);

  return (
    <QueryClientProvider client={client}>
      <div className="min-h-screen bg-background p-6 text-foreground">
        <div className="mx-auto max-w-5xl">
          <HoldingPriceChart
            symbol={symbol}
            initialPeriod="1y"
            overlays={initialOverlays}
            showStageBands={initialStageBands}
            showMetricStrip={showMetricStrip}
          />
        </div>
      </div>
    </QueryClientProvider>
  );
}

/** Overlay row: SMA 50/150/200 over the price line. */
export const WithMovingAverages = () => (
  <OverlayStory initialOverlays={['sma50', 'sma150', 'sma200']} />
);

/** Bollinger bands rendered as upper / lower lines with shaded fill. */
export const WithBollingerBands = () => (
  <OverlayStory initialOverlays={['bollinger']} />
);

/** Stage Analysis bands: translucent backdrop coloured by current stage. */
export const WithStageBands = () => (
  <OverlayStory initialStageBands />
);

/** Full flagship rendering: overlays + stage bands + metric strip. */
export const WithEverything = () => (
  <OverlayStory
    initialOverlays={['sma50', 'sma200', 'bollinger']}
    initialStageBands
  />
);

/** Metric strip standalone (no overlays / bands) so the typography reads cleanly. */
export const MetricStripOnly = () => <OverlayStory />;

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
