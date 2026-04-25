/** Shared types for signal surfaces (candidates, regime, scan).
 *
 * Every shape matches the backend response schema exactly — do not invent
 * fields. See:
 *   - backend/api/routes/picks/candidates_today.py
 *   - backend/api/routes/market/regime.py
 */

// ---------------------------------------------------------------------------
// /picks/candidates/today
// ---------------------------------------------------------------------------

export interface CandidateScoreComponents {
  [componentName: string]: number | null | undefined;
}

export interface CandidateScoreBreakdown {
  total_score?: number | null;
  components?: CandidateScoreComponents | null;
  regime_multiplier?: number | null;
  computed_at?: string | null;
}

export interface CandidateRow {
  id: number;
  ticker: string;
  action: string;
  generator_name: string | null;
  generator_version: string | null;
  generator_score: string | null;
  pick_quality_score: string | null;
  score: CandidateScoreBreakdown | null;
  thesis: string | null;
  signals: Record<string, unknown> | null;
  generated_at: string | null;
}

export interface CandidatesTodayResponse {
  items: CandidateRow[];
  total: number;
  limit: number;
  offset: number;
}

// ---------------------------------------------------------------------------
// /market-data/regime/history
// ---------------------------------------------------------------------------

export interface RegimeHistoryRow {
  as_of_date: string | null;
  regime_state: string | null;
  composite_score: number | null;
}

export interface RegimeHistoryResponse {
  history: RegimeHistoryRow[];
}
