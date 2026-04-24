/**
 * `useHoldingChartData` — composes the four queries the flagship holding
 * chart needs into a single ergonomic hook.
 *
 * Why a custom hook (vs four `useQuery` calls in the component):
 *   - Smart benchmark resolution depends on the snapshot result.
 *   - "Since I bought" requires the activity result to derive the period.
 *   - The benchmark series MUST share the resolved period to overlay
 *     cleanly — wiring those dependencies inline would make the chart
 *     component a tangle of conditional hooks.
 *   - Keeping it here makes it testable in isolation (no DOM, no
 *     lightweight-charts), and lets us re-use the same data shape for
 *     export / share-card / OG-image flows in later PRs.
 *
 * Caching strategy:
 *   - Snapshot: 5 min stale (sector / instrument_type rarely change).
 *   - Activity: 1 min stale (user may have just transacted).
 *   - Price history: 30 s stale (matches our market-data refresh cadence).
 */
import * as React from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import {
  activityApi,
  marketDataApi,
  portfolioApi,
  unwrapResponse,
} from "@/services/api";

import {
  describeBenchmark,
  resolveBenchmarkSymbol,
  type SnapshotLite,
} from "./benchmarkResolver";
import {
  earliestBuyDate,
  periodCoveringDate,
  type ActivityRowLite,
} from "./sinceIBoughtRange";
import {
  bucketDividendsByDay,
  bucketTradesByDay,
  buildTradeMarkers,
  periodToDividendDays,
  type DividendBucket,
  type DividendRow,
  type SeriesMarker,
  type TradeBucket,
  type TradeRow,
} from "./tradeMarkers";

export type HoldingChartPeriod =
  | "1mo"
  | "3mo"
  | "6mo"
  | "ytd"
  | "1y"
  | "5y"
  | "max"
  | "since";

export interface PriceBar {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

export interface BenchmarkBar {
  time: string;
  close: number;
}

export interface UseHoldingChartDataOptions {
  symbol: string;
  accountId?: string;
  period: HoldingChartPeriod;
  benchmarkOverride?: string | null;
  enabled?: boolean;
  /**
   * Skip the benchmark price fetch when false. Defaults to true. The
   * consumer typically derives this from the same `showBenchmark` prop
   * that controls the legend / overlay so the network request matches
   * what the user can actually see.
   */
  fetchBenchmark?: boolean;
  /**
   * Skip the dividends fetch entirely. Defaults to true. Useful for
   * stories / smaller chart variants that don't render the dividend
   * dot overlay and so don't need to pay the network round-trip.
   */
  fetchDividends?: boolean;
}

export interface HoldingChartData {
  symbol: string;
  bars: PriceBar[];
  benchmarkBars: BenchmarkBar[];
  benchmarkSymbol: string;
  benchmarkLabel: string;
  benchmarkTooltip: string;
  snapshot: Record<string, unknown> | null;
  /** Activity rows bucketed by UTC day (one bucket per trade day). */
  trades: TradeBucket[];
  /** Render-ready marker payloads for `createSeriesMarkers`. */
  tradeMarkers: SeriesMarker[];
  /** Dividend rows filtered to symbol and bucketed by ex-date. */
  dividends: DividendBucket[];
  earliestBuyDate: string | null;
  /** Resolved 'since' → concrete backend period (used for refetch keys). */
  effectivePeriod: Exclude<HoldingChartPeriod, "since">;
  /** Visual-axis start in YYYY-MM-DD. Null when the consumer didn't ask for "since". */
  effectiveStart: string | null;
  isLoading: boolean;
  isError: boolean;
  error: unknown;
  refetch: () => Promise<void>;
}

const SNAPSHOT_STALE_MS = 5 * 60_000;
const ACTIVITY_STALE_MS = 60_000;
const PRICE_STALE_MS = 30_000;
// Dividends are now scoped per-symbol at the backend (the endpoint
// accepts an optional `symbol` filter applied at the SQL layer; see
// `backend/api/routes/portfolio/dividends.py`). 5 minutes is a
// deliberate compromise between two pulls:
//   - Long enough that flipping period stays snappy without re-thrashing
//     the network for the same (account, symbol, window) tuple.
//   - Not so long that a freshly-paid dividend takes hours to surface.
//     Dividends only post once a quarter per symbol, so 5 minutes is
//     comfortably under the human-noticeable threshold for a quarterly
//     event.
const DIVIDEND_STALE_MS = 5 * 60_000;

export const BACKEND_PERIODS = [
  "1mo",
  "3mo",
  "6mo",
  "ytd",
  "1y",
  "5y",
  "max",
] as const;
export type BackendPeriod = (typeof BACKEND_PERIODS)[number];

export function isBackendPeriod(p: HoldingChartPeriod): p is BackendPeriod {
  return (BACKEND_PERIODS as readonly string[]).includes(p);
}

/**
 * Pulls the snapshot object off the backend response. The market-data
 * snapshot endpoint has been wrapped twice during its evolution:
 *   - axios envelope: `response.data.snapshot`
 *   - status envelope: `response.data.data.snapshot`
 *   - flat: `response.snapshot`
 * Tolerate all three so consumers don't fight schema drift.
 */
function extractSnapshot(raw: unknown): Record<string, unknown> | null {
  if (raw == null || typeof raw !== "object") return null;
  const r = raw as Record<string, unknown>;
  const fromEnvelope = (r.data as { data?: { snapshot?: unknown }; snapshot?: unknown } | undefined);
  const candidate =
    fromEnvelope?.data?.snapshot ??
    fromEnvelope?.snapshot ??
    r.snapshot ??
    null;
  return (candidate && typeof candidate === "object" ? (candidate as Record<string, unknown>) : null);
}

/**
 * Pulls the activity rows off the backend response — see `extractSnapshot`
 * for the envelope rationale.
 */
function extractActivityRows(raw: unknown): ActivityRowLite[] {
  if (!raw) return [];
  const rows = unwrapResponse<ActivityRowLite>(raw, "activity");
  return Array.isArray(rows) ? rows : [];
}

/** Same envelope tolerance as `extractActivityRows`, scoped to dividends. */
function extractDividendRows(raw: unknown): DividendRow[] {
  if (!raw) return [];
  const rows = unwrapResponse<DividendRow>(raw, "dividends");
  return Array.isArray(rows) ? rows : [];
}

function snapshotLite(s: Record<string, unknown> | null): SnapshotLite | null {
  if (!s) return null;
  return {
    sector: typeof s.sector === "string" ? s.sector : null,
    industry: typeof s.industry === "string" ? s.industry : null,
    instrument_type:
      typeof s.instrument_type === "string" ? s.instrument_type : null,
  };
}

function asBars(raw: unknown): PriceBar[] {
  // `unwrapResponse` is a typed cast and will happily hand back whatever
  // shape the backend produced. If a future API drift changes `bars` to
  // an object or null, the subsequent `.filter()` would throw. Guard
  // explicitly so the chart degrades to "empty" rather than crashing.
  const bars = unwrapResponse<PriceBar>(raw, "bars");
  if (!Array.isArray(bars)) return [];
  // Defensive: only surface rows with a numeric close; the chart cannot
  // render holes mid-series without producing visual artifacts.
  return bars.filter(
    (b) => typeof b?.close === "number" && Number.isFinite(b.close),
  );
}

function clampToStart(bars: PriceBar[], startIso: string | null): PriceBar[] {
  if (!startIso) return bars;
  const cutoff = Date.parse(`${startIso}T00:00:00Z`);
  if (!Number.isFinite(cutoff)) return bars;
  return bars.filter((b) => {
    const t = Date.parse(b.time);
    return Number.isFinite(t) ? t >= cutoff : true;
  });
}

function clampBenchmarks(
  bars: BenchmarkBar[],
  startIso: string | null,
): BenchmarkBar[] {
  if (!startIso) return bars;
  const cutoff = Date.parse(`${startIso}T00:00:00Z`);
  if (!Number.isFinite(cutoff)) return bars;
  return bars.filter((b) => {
    const t = Date.parse(b.time);
    return Number.isFinite(t) ? t >= cutoff : true;
  });
}

export function useHoldingChartData(
  opts: UseHoldingChartDataOptions,
): HoldingChartData {
  const {
    symbol,
    accountId,
    period,
    benchmarkOverride,
    enabled = true,
    fetchBenchmark = true,
    fetchDividends = true,
  } = opts;
  const queryClient = useQueryClient();

  const enabledForSymbol = enabled && Boolean(symbol);

  const snapshotQuery = useQuery({
    queryKey: ["holdingChart", "snapshot", symbol],
    queryFn: () => marketDataApi.getSnapshot(symbol),
    enabled: enabledForSymbol,
    staleTime: SNAPSHOT_STALE_MS,
  });

  const activityQuery = useQuery({
    queryKey: ["holdingChart", "activity", symbol, accountId ?? null],
    queryFn: () => activityApi.getActivity({ symbol, accountId, limit: 500 }),
    enabled: enabledForSymbol,
    staleTime: ACTIVITY_STALE_MS,
  });

  const snapshot = React.useMemo(
    () => extractSnapshot(snapshotQuery.data),
    [snapshotQuery.data],
  );
  const activityRows = React.useMemo(
    () => extractActivityRows(activityQuery.data),
    [activityQuery.data],
  );
  const earliest = React.useMemo(
    () => earliestBuyDate(activityRows),
    [activityRows],
  );

  const benchmarkSymbol = React.useMemo(
    () => resolveBenchmarkSymbol(symbol, snapshotLite(snapshot), benchmarkOverride),
    [symbol, snapshot, benchmarkOverride],
  );

  // Benchmark === primary symbol means the comparison would be tautological
  // (e.g. SPY vs SPY). Suppress the secondary fetch and signal upstream by
  // returning an empty `benchmarkBars` array.
  const sameSymbolAsBenchmark =
    symbol.trim().toUpperCase() === benchmarkSymbol.trim().toUpperCase();

  const effectivePeriod: BackendPeriod = React.useMemo(() => {
    if (isBackendPeriod(period)) return period;
    // 'since' resolution: prefer the smallest period that covers the
    // earliest buy. If there's no buy data yet (genuinely brand-new
    // holding, or sync still warming) fall back to '1y' so the chart
    // still tells a useful story.
    if (earliest) return periodCoveringDate(earliest);
    return "1y";
  }, [period, earliest]);

  const effectiveStart = period === "since" ? earliest : null;

  const priceQuery = useQuery({
    queryKey: ["holdingChart", "price", symbol, effectivePeriod],
    queryFn: () => marketDataApi.getHistory(symbol, effectivePeriod, "1d"),
    enabled: enabledForSymbol,
    staleTime: PRICE_STALE_MS,
  });

  // Skip the benchmark fetch when:
  //   - `fetchBenchmark` is false (consumer hid the overlay → no point
  //     paying the network round-trip), OR
  //   - the resolved benchmark equals the primary symbol (SPY-vs-SPY
  //     would be tautological).
  const benchmarkEnabled =
    enabledForSymbol && fetchBenchmark && !sameSymbolAsBenchmark;

  const benchmarkQuery = useQuery({
    queryKey: ["holdingChart", "benchmarkPrice", benchmarkSymbol, effectivePeriod],
    queryFn: () => marketDataApi.getHistory(benchmarkSymbol, effectivePeriod, "1d"),
    enabled: benchmarkEnabled,
    staleTime: PRICE_STALE_MS,
  });

  // Dividends are filtered to `symbol` at the backend (SQL `WHERE
  // dividends.symbol = :symbol`). The query key MUST include `symbol`
  // because the response is now per-symbol; sharing a cache slot
  // across symbols would bleed AAPL's dividends into MSFT's chart.
  // The narrower payload is the right trade-off: a per-holding fetch
  // returns ~1 row/quarter instead of N×M rows, and the chart never
  // discards data on the client.
  const dividendDays = React.useMemo(
    () => periodToDividendDays(effectivePeriod),
    [effectivePeriod],
  );
  const dividendsEnabled = enabledForSymbol && fetchDividends;
  // Normalize once so the React Query cache key and the backend request
  // can never disagree on casing/whitespace. Without this, a caller that
  // passed `aapl` and another that passed `AAPL` would create two cache
  // entries pointing at the same backend response and invalidation would
  // silently miss one of them.
  const normalizedSymbol = React.useMemo(
    () => symbol?.trim().toUpperCase() || undefined,
    [symbol],
  );
  const dividendsQuery = useQuery({
    queryKey: [
      "holdingChart",
      "dividends",
      accountId ?? null,
      dividendDays,
      normalizedSymbol ?? null,
    ],
    queryFn: () =>
      portfolioApi.getDividends(accountId, dividendDays, normalizedSymbol),
    enabled: dividendsEnabled,
    staleTime: DIVIDEND_STALE_MS,
  });

  const bars = React.useMemo(
    () => clampToStart(asBars(priceQuery.data), effectiveStart),
    [priceQuery.data, effectiveStart],
  );

  // Trade buckets + render-ready markers. We feed the same activity rows
  // that drive the "Since I bought" anchor through the marker pipeline so
  // the chart and the period selector stay perfectly in sync.
  const trades = React.useMemo<TradeBucket[]>(
    () => bucketTradesByDay(activityRows as TradeRow[]),
    [activityRows],
  );
  const tradeMarkers = React.useMemo<SeriesMarker[]>(
    () => buildTradeMarkers(trades),
    [trades],
  );

  // Dividend buckets. Rows come pre-filtered to `symbol` from the
  // backend (no client-side discard pass), so we just bucket them by
  // ex-date. Always returns `[]` (never undefined) so consumer
  // rendering stays simple — `fetchDividends={false}` short-circuits
  // to `[]` too.
  const dividends = React.useMemo<DividendBucket[]>(() => {
    if (!dividendsEnabled) return [];
    const rows = extractDividendRows(dividendsQuery.data);
    return bucketDividendsByDay(rows);
  }, [dividendsEnabled, dividendsQuery.data]);
  const benchmarkBars = React.useMemo<BenchmarkBar[]>(() => {
    if (!benchmarkEnabled) return [];
    const raw = asBars(benchmarkQuery.data);
    const trimmed = clampBenchmarks(
      raw.map((b) => ({ time: b.time, close: b.close })),
      effectiveStart,
    );
    return trimmed;
  }, [benchmarkQuery.data, effectiveStart, benchmarkEnabled]);

  const isLoading =
    enabledForSymbol &&
    (snapshotQuery.isLoading ||
      activityQuery.isLoading ||
      priceQuery.isLoading ||
      (benchmarkEnabled && benchmarkQuery.isLoading));

  // First-class error surface: any failed query bubbles up. We intentionally
  // do NOT silently fall back to partial data — if the snapshot 500s but the
  // bars succeed, the user sees an error state. (See no-silent-fallback.)
  //
  // Dividends are deliberately NOT part of `isError` — they're a secondary
  // overlay and a missing dividend feed should not blow away the chart.
  // The portfolioApi shim already returns an empty list on backend failure,
  // so a true error here is rare; we still log it via React Query devtools
  // but don't propagate it to the chart's error gate.
  const isError =
    snapshotQuery.isError ||
    activityQuery.isError ||
    priceQuery.isError ||
    (benchmarkEnabled && benchmarkQuery.isError);

  const error =
    snapshotQuery.error ??
    activityQuery.error ??
    priceQuery.error ??
    (benchmarkEnabled ? benchmarkQuery.error : null) ??
    null;

  const descriptor = React.useMemo(
    () => describeBenchmark(benchmarkSymbol),
    [benchmarkSymbol],
  );

  const refetch = React.useCallback(async () => {
    // Refetch in parallel; we don't care about ordering and React Query
    // will dedupe in-flight requests if any are already pending.
    await Promise.all([
      snapshotQuery.refetch(),
      activityQuery.refetch(),
      priceQuery.refetch(),
      benchmarkEnabled ? benchmarkQuery.refetch() : Promise.resolve(),
      dividendsEnabled ? dividendsQuery.refetch() : Promise.resolve(),
    ]);
    // Bust holdingChart cache entries this hook would consume.
    // Now that dividends are keyed per-symbol (the backend filters by
    // SQL), the symbol-match path covers them too — we no longer have
    // to nuke account-wide dividend cache slots that other holdings
    // depend on.
    queryClient.invalidateQueries({
      predicate: (query) => {
        const key = query.queryKey;
        if (!Array.isArray(key) || key[0] !== "holdingChart") return false;
        return key.some((k) => k === symbol || k === benchmarkSymbol);
      },
    });
  }, [
    activityQuery,
    benchmarkEnabled,
    benchmarkQuery,
    benchmarkSymbol,
    dividendsEnabled,
    dividendsQuery,
    priceQuery,
    queryClient,
    snapshotQuery,
    symbol,
  ]);

  return {
    symbol,
    bars,
    benchmarkBars,
    benchmarkSymbol: benchmarkEnabled ? benchmarkSymbol : "",
    benchmarkLabel: benchmarkEnabled ? descriptor.label : "",
    benchmarkTooltip: benchmarkEnabled ? descriptor.tooltip : "",
    snapshot,
    trades,
    tradeMarkers,
    dividends,
    earliestBuyDate: earliest,
    effectivePeriod,
    effectiveStart,
    isLoading,
    isError,
    error,
    refetch,
  };
}
