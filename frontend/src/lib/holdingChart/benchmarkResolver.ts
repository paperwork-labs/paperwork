/**
 * `benchmarkResolver` — pick the canonical benchmark symbol for a holding.
 *
 * Comparing AAPL to SPY is fine, but comparing AAPL to its sector ETF (XLK)
 * is the question a swing trader actually asks: am I beating my industry,
 * not just the index? This module encodes the priority order the chart UI
 * uses to make that call without bothering the user.
 *
 * Pure, dependency-free, and exhaustively tested so the chart layer can
 * call it during render without surprises.
 */

export type BenchmarkSymbol = string;

export interface SnapshotLite {
  sector?: string | null;
  industry?: string | null;
  /** Backend snapshot uses 'ETF' | 'EQUITY' | 'CRYPTO' | 'FUND' | etc. */
  instrument_type?: string | null;
}

interface BenchmarkDescriptor {
  label: string;
  tooltip: string;
}

/**
 * Sector → SPDR sector ETF mapping. Patterns are matched against the
 * backend-supplied `sector` field (case-insensitive). First match wins so
 * order matters: more specific patterns must come BEFORE broader ones.
 *
 * Sourced from Stage_Analysis.docx §Sector Reference and SPDR's own
 * fund descriptions (so the labels in `describeBenchmark` line up with the
 * official ETF names users see in their broker).
 */
export const SECTOR_TO_ETF: ReadonlyArray<readonly [pattern: RegExp, etf: string]> =
  [
    [/technology|info(rmation)? tech/i, "XLK"],
    [/health/i, "XLV"],
    [/financ/i, "XLF"],
    [/communication/i, "XLC"],
    [/consumer discretionary|consumer cyclical/i, "XLY"],
    [/consumer (staples|defensive)/i, "XLP"],
    [/energy/i, "XLE"],
    [/utilit/i, "XLU"],
    [/real estate/i, "XLRE"],
    [/industrial/i, "XLI"],
    [/material|basic material/i, "XLB"],
  ] as const;

/**
 * Recognised crypto tickers. We compare BTC-USD as the "asset class"
 * benchmark — the same way SPY benchmarks equities. ETH gets benchmarked
 * against BTC because that's the conversation crypto traders actually have.
 */
const CRYPTO_TICKER_RE = /^(BTC|ETH|SOL|ADA|XRP|DOGE|MATIC|DOT|AVAX|LINK)(-USD|USD|USDT)?$/i;

/**
 * Returns the canonical benchmark symbol for a holding.
 *
 * Priority (first match wins):
 *   1. Explicit `override` (uppercased) — user pinned a comparison.
 *   2. ETF holdings → SPY (compare equity ETFs to broad market).
 *   3. Crypto holdings → BTC-USD (asset-class benchmark).
 *   4. Sector lookup via SECTOR_TO_ETF.
 *   5. SPY default.
 */
export function resolveBenchmarkSymbol(
  symbol: string,
  snapshot?: SnapshotLite | null,
  override?: BenchmarkSymbol | null,
): BenchmarkSymbol {
  if (override && override.trim().length > 0) {
    return override.trim().toUpperCase();
  }

  const instrumentType = snapshot?.instrument_type?.toUpperCase() ?? null;

  // ETFs: compare against SPY by default (broad market reference).
  if (instrumentType === "ETF") {
    return "SPY";
  }

  // Crypto: detect either via instrument_type OR ticker pattern. Some sync
  // pipelines tag crypto with a specific instrument_type, others rely on the
  // ticker convention — both should resolve identically.
  if (
    instrumentType === "CRYPTO" ||
    (typeof symbol === "string" && CRYPTO_TICKER_RE.test(symbol.trim()))
  ) {
    return "BTC-USD";
  }

  const sector = snapshot?.sector?.trim();
  if (sector && sector.length > 0) {
    for (const [pattern, etf] of SECTOR_TO_ETF) {
      if (pattern.test(sector)) return etf;
    }
  }

  return "SPY";
}

/**
 * Human-readable description for a benchmark symbol. Drives the legend
 * label ("vs S&P 500") and the tooltip body ("S&P 500 ETF").
 *
 * Falls back to `vs <SYMBOL>` for any unknown ticker so a user-pinned
 * override always renders coherently.
 */
const BENCHMARK_DESCRIPTORS: Readonly<Record<string, BenchmarkDescriptor>> = {
  SPY: { label: "vs S&P 500", tooltip: "S&P 500 ETF" },
  QQQ: { label: "vs Nasdaq 100", tooltip: "Invesco QQQ — Nasdaq 100 ETF" },
  DIA: { label: "vs Dow", tooltip: "SPDR Dow Jones Industrial Average ETF" },
  IWM: { label: "vs Russell 2000", tooltip: "iShares Russell 2000 ETF" },
  XLK: { label: "vs XLK", tooltip: "Technology Select Sector SPDR" },
  XLV: { label: "vs XLV", tooltip: "Health Care Select Sector SPDR" },
  XLF: { label: "vs XLF", tooltip: "Financial Select Sector SPDR" },
  XLC: { label: "vs XLC", tooltip: "Communication Services Select Sector SPDR" },
  XLY: { label: "vs XLY", tooltip: "Consumer Discretionary Select Sector SPDR" },
  XLP: { label: "vs XLP", tooltip: "Consumer Staples Select Sector SPDR" },
  XLE: { label: "vs XLE", tooltip: "Energy Select Sector SPDR" },
  XLU: { label: "vs XLU", tooltip: "Utilities Select Sector SPDR" },
  XLRE: { label: "vs XLRE", tooltip: "Real Estate Select Sector SPDR" },
  XLI: { label: "vs XLI", tooltip: "Industrial Select Sector SPDR" },
  XLB: { label: "vs XLB", tooltip: "Materials Select Sector SPDR" },
  "BTC-USD": { label: "vs Bitcoin", tooltip: "Bitcoin / USD" },
  "ETH-USD": { label: "vs Ethereum", tooltip: "Ethereum / USD" },
};

export function describeBenchmark(symbol: BenchmarkSymbol): BenchmarkDescriptor {
  const upper = symbol.trim().toUpperCase();
  const known = BENCHMARK_DESCRIPTORS[upper];
  if (known) return known;
  return { label: `vs ${upper}`, tooltip: upper };
}
