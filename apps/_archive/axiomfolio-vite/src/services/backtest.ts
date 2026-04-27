/**
 * Backtest analysis client: walk-forward optimizer and Monte Carlo /
 * scenarios.
 *
 * Walk-forward mirrors `backend/api/routes/backtest/walk_forward.py`; the
 * hook layer (`useWalkForwardStudies`) wraps those calls in TanStack Query.
 *
 * Monte Carlo calls `/api/v1/backtest/monte-carlo` (tier: `research.monte_carlo`).
 * Monetary values return as JSON strings to preserve Decimal precision; we
 * coerce to number only at the chart layer where Recharts needs floats.
 */

import api from './api';

// ---------------------------------------------------------------------------
// Walk-forward
// ---------------------------------------------------------------------------

export type WalkForwardStatus = 'pending' | 'running' | 'completed' | 'failed';

export type ParamSpec =
  | { type: 'int'; low: number; high: number; step?: number }
  | { type: 'float'; low: number; high: number; log?: boolean }
  | { type: 'categorical'; choices: Array<string | number> };

export type ParamSpace = Record<string, ParamSpec>;

export type RegimeFilter = 'R1' | 'R2' | 'R3' | 'R4' | 'R5' | null;

export interface CreateStudyPayload {
  name: string;
  strategy_class: string;
  objective: string;
  param_space: ParamSpace;
  symbols: string[];
  /** YYYY-MM-DD */
  dataset_start: string;
  /** YYYY-MM-DD */
  dataset_end: string;
  train_window_days: number;
  test_window_days: number;
  n_splits: number;
  n_trials: number;
  regime_filter: RegimeFilter;
}

export interface SplitResultPayload {
  split_index: number;
  train_start: string;
  train_end: string;
  test_start: string;
  test_end: string;
  train_score: number;
  test_score: number;
  trade_count: number;
}

export interface RegimeAttributionPayload {
  [regime: string]: { score: number; trades: number; avg_return: number };
}

export interface StudySummary {
  id: number;
  name: string;
  strategy_class: string;
  objective: string;
  status: WalkForwardStatus;
  n_splits: number;
  n_trials: number;
  total_trials: number;
  regime_filter: string | null;
  best_score: number | null;
  created_at: string | null;
  started_at: string | null;
  completed_at: string | null;
}

export interface StudyDetail extends StudySummary {
  param_space: ParamSpace;
  symbols: string[];
  train_window_days: number;
  test_window_days: number;
  dataset_start: string | null;
  dataset_end: string | null;
  best_params: Record<string, unknown> | null;
  per_split_results: SplitResultPayload[] | null;
  regime_attribution: RegimeAttributionPayload | null;
  error_message: string | null;
}

export interface StrategyOptions {
  strategies: string[];
  objectives: string[];
  regimes: string[];
}

const WALK_FORWARD_BASE = '/backtest/walk-forward';

export async function listStudies(limit = 50): Promise<StudySummary[]> {
  const res = await api.get<StudySummary[]>(`${WALK_FORWARD_BASE}/studies`, {
    params: { limit },
  });
  return res.data ?? [];
}

export async function getStudy(id: number): Promise<StudyDetail> {
  const res = await api.get<StudyDetail>(`${WALK_FORWARD_BASE}/studies/${id}`);
  return res.data;
}

export async function createStudy(
  payload: CreateStudyPayload,
): Promise<StudyDetail> {
  const res = await api.post<StudyDetail>(`${WALK_FORWARD_BASE}/studies`, payload);
  return res.data;
}

export async function listStrategyOptions(): Promise<StrategyOptions> {
  const res = await api.get<StrategyOptions>(`${WALK_FORWARD_BASE}/strategies`);
  return res.data;
}

// ---------------------------------------------------------------------------
// Monte Carlo — types
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
// Monte Carlo — API
// ---------------------------------------------------------------------------

/**
 * POST /api/v1/backtest/monte-carlo
 *
 * Errors propagate as the original AxiosError — callers should let
 * TanStack Query distinguish `isError` from `isLoading` per the
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
// Monte Carlo — helpers (UI-side, pure)
// ---------------------------------------------------------------------------

/**
 * Coerce a Decimal-string from the API to a `number` for chart libs.
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
 * Format a fraction-of-1 probability as a percentage string.
 */
export function formatProbability(p: string, fractionDigits = 1): string {
  return `${(decimalToNumber(p) * 100).toFixed(fractionDigits)}%`;
}
