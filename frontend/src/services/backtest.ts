/**
 * Backtest analysis client (Monte Carlo, walk-forward, scenarios).
 *
 * Calls into ``/api/v1/backtest/...`` which are tier-gated to Pro+
 * (``research.monte_carlo``). All monetary values come back from the
 * backend as JSON strings to preserve ``Decimal`` precision; we keep
 * them as ``string`` here and only coerce to ``number`` at the chart
 * layer where Recharts needs floats.
 *
 * Why string-typed numbers
 * ------------------------
 * The backend uses ``Decimal`` end-to-end and serializes to strings.
 * If we typed these as ``number`` here we'd silently lose precision
 * for very small (sub-cent) percentile values and would also lose the
 * ability to feed the same blob back into a future "save scenario"
 * mutation without round-tripping through float.
 */
import api from './api';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** A list of per-step Decimal-string equity values, one per trade. */
export interface MonteCarloEquityCurve {
  p5: string[];
  p25: string[];
  p50: string[];
  p75: string[];
  p95: string[];
}

/** Six-number summary of a one-dimensional distribution. */
export interface MonteCarloDistribution {
  mean: string;
  median: string;
  p5: string;
  p25: string;
  p75: string;
  p95: string;
  std: string;
}

/** Echo of the inputs the backend received, for label rendering. */
export interface MonteCarloParams {
  n_simulations: number;
  n_trades: number;
  initial_capital: string;
  seed: number | null;
  risk_free_rate: string;
  weighted: boolean;
}

export interface MonteCarloResult {
  equity_curve: MonteCarloEquityCurve;
  /** Max drawdown as a percent of peak (0..100). */
  max_drawdown_pct: MonteCarloDistribution;
  sharpe: MonteCarloDistribution;
  terminal_value: MonteCarloDistribution;
  /** Probability terminal < initial capital, in [0,1]. */
  probability_of_loss: string;
  /** Probability terminal >= 2 * initial capital, in [0,1]. */
  probability_of_2x: string;
  params: MonteCarloParams;
}

export type MonteCarloScenarioName =
  | 'iid_baseline'
  | 'optimistic_skew'
  | 'pessimistic_skew';

export interface MonteCarloScenario {
  name: MonteCarloScenarioName;
  description: string;
  result: MonteCarloResult;
}

export type MonteCarloMode = 'single' | 'scenario' | 'all_scenarios';

export interface MonteCarloResponse {
  mode: MonteCarloMode;
  result?: MonteCarloResult;
  scenario?: MonteCarloScenario;
  scenarios?: Record<MonteCarloScenarioName, MonteCarloScenario>;
  available_scenarios: MonteCarloScenarioName[];
}

export interface MonteCarloRequest {
  /**
   * Per-trade returns as decimal fractions (0.025 = +2.5%). Encoded as
   * strings so very small returns survive JSON round-tripping; the
   * backend Pydantic model accepts string or number.
   */
  trade_returns: Array<string | number>;
  n_simulations?: number;
  initial_capital?: string | number;
  seed?: number | null;
  risk_free_rate?: string | number;
  scenario?: MonteCarloScenarioName;
  run_all_scenarios?: boolean;
}

// ---------------------------------------------------------------------------
// API
// ---------------------------------------------------------------------------

/**
 * POST /api/v1/backtest/monte-carlo
 *
 * Synchronous endpoint that returns either a single result or a map of
 * scenario results, depending on the request body. The backend caps
 * ``n_simulations`` at 100k so this stays comfortably under the
 * request-budget ceiling.
 *
 * Errors propagate as the original AxiosError -- callers should let
 * TanStack Query distinguish ``isError`` from ``isLoading`` per the
 * no-silent-fallback rule.
 */
export async function runMonteCarlo(
  payload: MonteCarloRequest,
): Promise<MonteCarloResponse> {
  const response = await api.post<MonteCarloResponse>(
    '/backtest/monte-carlo',
    payload,
  );
  return response.data;
}

// ---------------------------------------------------------------------------
// Helpers (UI-side, pure)
// ---------------------------------------------------------------------------

/**
 * Coerce a Decimal-string from the API to a `number` for chart libs.
 *
 * We deliberately do NOT round here; let Recharts/format helpers decide
 * display precision. Returns `0` only for the literal string `"0"` or
 * empty. `null` / `undefined` throw so missing API fields cannot masquerade
 * as zero (no-silent-fallback).
 */
export function decimalToNumber(value: string | undefined | null): number {
  if (value == null) {
    throw new Error('backtest: missing Decimal string from API');
  }
  if (value === '') return 0;
  const n = Number(value);
  if (!Number.isFinite(n)) {
    throw new Error(`backtest: cannot parse Decimal string "${value}"`);
  }
  return n;
}

/**
 * Build the row format Recharts expects for the equity-curve fan chart:
 * one row per trade-index with p5/p25/p50/p75/p95 numeric fields.
 *
 * We synthesize a ``trade`` index (1-based) since the backend curves
 * are indexed by trade position, not by date.
 */
export interface EquityFanRow {
  trade: number;
  p5: number;
  p25: number;
  p50: number;
  p75: number;
  p95: number;
}

export function equityCurveToRows(
  curve: MonteCarloEquityCurve,
): EquityFanRow[] {
  const len = curve.p50.length;
  const rows: EquityFanRow[] = [];
  for (let i = 0; i < len; i++) {
    rows.push({
      trade: i + 1,
      p5: decimalToNumber(curve.p5[i]),
      p25: decimalToNumber(curve.p25[i]),
      p50: decimalToNumber(curve.p50[i]),
      p75: decimalToNumber(curve.p75[i]),
      p95: decimalToNumber(curve.p95[i]),
    });
  }
  return rows;
}

/**
 * Format a fraction-of-1 probability as a percentage string. The
 * backend always emits Decimals in the [0,1] range for these fields.
 */
export function formatProbability(p: string, fractionDigits = 1): string {
  return `${(decimalToNumber(p) * 100).toFixed(fractionDigits)}%`;
}
