/**
 * `tradeMarkers` — pure transforms that turn raw activity / dividend rows
 * into UI-ready primitives for the HoldingPriceChart:
 *
 *   - `bucketTradesByDay`   — group trade rows by UTC day so the same-day
 *                             cluster shows as one marker (not five).
 *   - `bucketDividendsByDay`— filter to symbol, group by ex-date, sum amounts.
 *   - `buildTradeMarkers`   — render-ready `lightweight-charts` marker
 *                             payloads (arrow up / arrow down / circle).
 *   - `periodToDividendDays`— map our chart period strings to a `days`
 *                             window for the dividends API.
 *
 * No React, no DOM — every function is a pure data transform. This is
 * deliberate so the file stays trivially unit-testable and so the same
 * helpers can be reused later by export / share-card / OG-image flows.
 */
import type { UTCTimestamp } from "lightweight-charts";

import { isBuySide, isSellSide } from "./sideTokens";

export interface TradeRow {
  /** Primary date field. Some upstreams send `date` instead. */
  transaction_date?: string;
  date?: string;
  /** 'BUY' / 'SELL' / 'B' / 'S' (case-insensitive). */
  side?: string;
  quantity?: number;
  price?: number;
  symbol?: string;
  account?: string;
}

export interface DividendRow {
  symbol?: string;
  ex_date?: string;
  pay_date?: string;
  dividend_per_share?: number;
  shares_held?: number;
  total_dividend?: number;
  account_id?: string;
  currency?: string;
}

/**
 * Lightweight marker payload (the lightweight-charts type for markers v5).
 * We define our own narrow surface area instead of pulling the library
 * type so the pure-data transform doesn't depend on the runtime; the chart
 * component widens at the call site.
 */
export interface SeriesMarker {
  time: UTCTimestamp;
  position: "aboveBar" | "belowBar";
  shape: "arrowDown" | "arrowUp" | "circle" | "square";
  color: string;
  text?: string;
  size?: number;
  /** Stable id used by the tooltip for bucket lookup; lightweight-charts ignores it. */
  id: string;
}

/** Day-keyed bucket of original trade rows so the tooltip can list them all. */
export interface TradeBucket {
  /** YYYY-MM-DD UTC. */
  dayKey: string;
  time: UTCTimestamp;
  buys: TradeRow[];
  sells: TradeRow[];
  /** Signed: + for net buy, − for net sell. */
  totalShares: number;
  /** Weighted average across rows that have prices; 0 if no rows had a price. */
  weightedAvgPrice: number;
}

/** Day-keyed dividend group (multiple lots same ex-date are summed). */
export interface DividendBucket {
  dayKey: string;
  time: UTCTimestamp;
  /** Original ex-date string preserved for tooltip / accessibility copy. */
  exDate: string;
  /** Weighted average per share across rows (currency assumed consistent). */
  perShare: number;
  /** Sum of `total_dividend` across all rows in the bucket. */
  totalAmount: number;
  rowCount: number;
  currency?: string;
}

/**
 * Marker glyph colors — these are visual-language constants (alert /
 * confirm / warning), NOT theme tokens, so it's correct to hard-code
 * them. They map 1:1 to the emerald/rose/amber palette used by the
 * change pill and stage badges. `lightweight-charts` paints markers
 * to a canvas without resolving CSS variables, so concrete strings
 * are required regardless.
 */
const MARKER_COLOR_BUY = "#10b981";
const MARKER_COLOR_SELL = "#ef4444";
const MARKER_COLOR_MIXED = "#f59e0b";

/** Period → dividends API `days` window. */
const PERIOD_TO_DAYS: Record<string, number> = {
  "1mo": 31,
  "3mo": 93,
  "6mo": 186,
  ytd: 365,
  "1y": 365,
  "5y": 1825,
  max: 3650,
  since: 1825,
};

/** Returns days for the dividends API; defaults to 365 for unknown periods. */
export function periodToDividendDays(p: string): number {
  return PERIOD_TO_DAYS[p] ?? 365;
}

/**
 * Resolve the most authoritative date string we can on a trade row, then
 * normalize to a UTC `YYYY-MM-DD` key. Returns null if neither field is
 * parseable so the caller can skip the row entirely (vs. clustering
 * everything under "unknown").
 */
function dayKeyOf(iso: string | undefined): {
  dayKey: string;
  time: UTCTimestamp;
} | null {
  if (!iso) return null;
  const ms = Date.parse(iso);
  if (!Number.isFinite(ms)) return null;
  const d = new Date(ms);
  const yyyy = d.getUTCFullYear();
  const mm = String(d.getUTCMonth() + 1).padStart(2, "0");
  const dd = String(d.getUTCDate()).padStart(2, "0");
  const dayKey = `${yyyy}-${mm}-${dd}`;
  // Pin to UTC midnight so all rows on the same calendar day share the
  // exact `time` lightweight-charts uses for x-axis placement.
  const utcMidnightMs = Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate());
  return {
    dayKey,
    time: Math.floor(utcMidnightMs / 1000) as UTCTimestamp,
  };
}

/**
 * Group trade rows by UTC day. Skips rows without parseable dates and
 * rows whose side isn't recognizable as buy or sell — they don't belong
 * on a marker either way. `isBuySide` / `isSellSide` are the SAME
 * helpers used by `sinceIBoughtRange`, so a row that contributes to the
 * "Since I bought" anchor will always also produce a marker (and vice-
 * versa). Diverging the two predicates is a known foot-gun.
 */
export function bucketTradesByDay(
  rows: ReadonlyArray<TradeRow>,
): TradeBucket[] {
  const map = new Map<string, TradeBucket>();
  for (const row of rows) {
    const dk = dayKeyOf(row.transaction_date ?? row.date);
    if (!dk) continue;
    const isBuy = isBuySide(row.side);
    const isSell = isSellSide(row.side);
    if (!isBuy && !isSell) continue;

    let bucket = map.get(dk.dayKey);
    if (!bucket) {
      bucket = {
        dayKey: dk.dayKey,
        time: dk.time,
        buys: [],
        sells: [],
        totalShares: 0,
        weightedAvgPrice: 0,
      };
      map.set(dk.dayKey, bucket);
    }
    if (isBuy) bucket.buys.push(row);
    else bucket.sells.push(row);
  }

  // Compute net shares + weighted avg price per bucket. We iterate the
  // already-bucketed rows once so this stays O(n) overall.
  for (const bucket of map.values()) {
    let netShares = 0;
    let priceWeightSum = 0;
    let qtyWithPrice = 0;
    for (const row of bucket.buys) {
      const qty = typeof row.quantity === "number" && Number.isFinite(row.quantity)
        ? Math.abs(row.quantity)
        : 0;
      netShares += qty;
      if (typeof row.price === "number" && Number.isFinite(row.price) && qty > 0) {
        priceWeightSum += row.price * qty;
        qtyWithPrice += qty;
      }
    }
    for (const row of bucket.sells) {
      const qty = typeof row.quantity === "number" && Number.isFinite(row.quantity)
        ? Math.abs(row.quantity)
        : 0;
      netShares -= qty;
      if (typeof row.price === "number" && Number.isFinite(row.price) && qty > 0) {
        priceWeightSum += row.price * qty;
        qtyWithPrice += qty;
      }
    }
    bucket.totalShares = netShares;
    bucket.weightedAvgPrice = qtyWithPrice > 0 ? priceWeightSum / qtyWithPrice : 0;
  }

  // Stable ordering by day so downstream tests don't fight Map iteration.
  return [...map.values()].sort((a, b) =>
    a.dayKey < b.dayKey ? -1 : a.dayKey > b.dayKey ? 1 : 0,
  );
}

/**
 * Filter dividends to a symbol (case-insensitive), then group by ex-date.
 * Rows without a parseable ex-date are skipped — there is no sensible
 * x-axis position for them.
 */
export function bucketDividendsByDay(
  rows: ReadonlyArray<DividendRow>,
  symbol: string,
): DividendBucket[] {
  const target = symbol.trim().toUpperCase();
  if (!target) return [];

  // Per-day per-share aggregates accumulated alongside the buckets so we
  // do this in ONE PASS over `rows`. The previous version walked `rows`
  // again for every bucket — O(rows * buckets) — which is harmless at
  // typical sizes but lit up Copilot review for a holding with hundreds
  // of historical pay-dates and made the function harder to reason about.
  interface PerShareAcc {
    /** Σ (perShare * shares) for rows that reported BOTH. */
    weightSum: number;
    /** Σ shares for rows that reported both. */
    sharesSum: number;
    /** Σ perShare across rows that reported a perShare (used as fallback). */
    perShareSum: number;
    /** Number of rows that reported a perShare. */
    perShareCount: number;
  }

  const map = new Map<string, DividendBucket>();
  const perShareAcc = new Map<string, PerShareAcc>();

  for (const row of rows) {
    const sym = (row.symbol ?? "").trim().toUpperCase();
    if (sym !== target) continue;
    const dk = dayKeyOf(row.ex_date);
    if (!dk) continue;

    let bucket = map.get(dk.dayKey);
    if (!bucket) {
      bucket = {
        dayKey: dk.dayKey,
        time: dk.time,
        exDate: row.ex_date ?? dk.dayKey,
        perShare: 0,
        totalAmount: 0,
        rowCount: 0,
        currency: typeof row.currency === "string" ? row.currency : undefined,
      };
      map.set(dk.dayKey, bucket);
      perShareAcc.set(dk.dayKey, {
        weightSum: 0,
        sharesSum: 0,
        perShareSum: 0,
        perShareCount: 0,
      });
    }

    const total = typeof row.total_dividend === "number" && Number.isFinite(row.total_dividend)
      ? row.total_dividend
      : 0;
    bucket.totalAmount += total;
    bucket.rowCount += 1;
    // Currency falls back to whichever non-empty value we see first; if
    // an upstream produces mixed currencies we'd already have a bigger
    // problem, but at least we won't drop a value silently.
    if (!bucket.currency && typeof row.currency === "string") {
      bucket.currency = row.currency;
    }

    const acc = perShareAcc.get(dk.dayKey)!;
    const perShare =
      typeof row.dividend_per_share === "number" &&
      Number.isFinite(row.dividend_per_share)
        ? row.dividend_per_share
        : null;
    const shares =
      typeof row.shares_held === "number" && Number.isFinite(row.shares_held)
        ? Math.abs(row.shares_held)
        : 0;
    if (perShare !== null && perShare > 0 && shares > 0) {
      acc.weightSum += perShare * shares;
      acc.sharesSum += shares;
    }
    if (perShare !== null) {
      acc.perShareSum += perShare;
      acc.perShareCount += 1;
    }
  }

  // Resolve per-share for each bucket using the share-weighted average
  // when available, otherwise the simple per-share average — preserving
  // the original semantics without the second pass.
  for (const [dayKey, bucket] of map) {
    const acc = perShareAcc.get(dayKey)!;
    if (acc.sharesSum > 0) {
      bucket.perShare = acc.weightSum / acc.sharesSum;
    } else {
      bucket.perShare = acc.perShareCount > 0 ? acc.perShareSum / acc.perShareCount : 0;
    }
  }

  return [...map.values()].sort((a, b) =>
    a.dayKey < b.dayKey ? -1 : a.dayKey > b.dayKey ? 1 : 0,
  );
}

/**
 * Build lightweight-charts marker payloads from bucketed trades.
 *
 * Rules:
 *   - Only buys → `arrowUp` `belowBar`, success color.
 *   - Only sells → `arrowDown` `aboveBar`, danger color.
 *   - Both → `circle` `aboveBar`, warning color, text `B+S` (or
 *     `B+S ×N` when more than 2 trades share the day, so a "5 buys + 3
 *     sells" cluster doesn't visually flatten to a "1 buy + 1 sell" one).
 *   - 2+ trades same side same day → text `×N` (count badge).
 */
export function buildTradeMarkers(
  buckets: ReadonlyArray<TradeBucket>,
): SeriesMarker[] {
  const markers: SeriesMarker[] = [];
  for (const bucket of buckets) {
    const buyCount = bucket.buys.length;
    const sellCount = bucket.sells.length;
    if (buyCount === 0 && sellCount === 0) continue;

    if (buyCount > 0 && sellCount > 0) {
      const totalCount = buyCount + sellCount;
      // Threshold > 2 (not >= 2) so the simplest mixed day — exactly one
      // buy and one sell — keeps the spare "B+S" label everyone is used
      // to. Only larger clusters earn the count suffix.
      const text = totalCount > 2 ? `B+S ×${totalCount}` : "B+S";
      markers.push({
        time: bucket.time,
        position: "aboveBar",
        shape: "circle",
        color: MARKER_COLOR_MIXED,
        text,
        id: `${bucket.dayKey}:mixed`,
      });
      continue;
    }

    if (buyCount > 0) {
      markers.push({
        time: bucket.time,
        position: "belowBar",
        shape: "arrowUp",
        color: MARKER_COLOR_BUY,
        text: buyCount >= 2 ? `×${buyCount}` : undefined,
        id: `${bucket.dayKey}:buy`,
      });
      continue;
    }

    // sellCount > 0
    markers.push({
      time: bucket.time,
      position: "aboveBar",
      shape: "arrowDown",
      color: MARKER_COLOR_SELL,
      text: sellCount >= 2 ? `×${sellCount}` : undefined,
      id: `${bucket.dayKey}:sell`,
    });
  }
  return markers;
}
