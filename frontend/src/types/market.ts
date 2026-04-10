/** Shared market data types used across hooks, pages, and components. */

export interface MarketSnapshotRow {
  symbol: string;
  name?: string;
  analysis_timestamp?: string;
  as_of_timestamp?: string;
  current_price?: number;
  market_cap?: number;
  pe_ttm?: number;
  peg_ttm?: number;
  roe?: number;
  eps_ttm?: number;
  revenue_ttm?: number;
  eps_growth_yoy?: number;
  eps_growth_qoq?: number;
  revenue_growth_yoy?: number;
  revenue_growth_qoq?: number;
  dividend_yield?: number;
  beta?: number;
  analyst_rating?: string;
  last_earnings?: string;
  next_earnings?: string;
  sector?: string;
  industry?: string;
  sub_industry?: string;
  stage_label?: string;
  stage_label_5d_ago?: string;
  current_stage_days?: number;
  previous_stage_label?: string;
  previous_stage_days?: number;
  rs_mansfield_pct?: number;
  sma_5?: number;
  sma_10?: number;
  sma_14?: number;
  sma_21?: number;
  sma_50?: number;
  sma_100?: number;
  sma_150?: number;
  sma_200?: number;
  ema_8?: number;
  ema_10?: number;
  ema_21?: number;
  atr_14?: number;
  atr_30?: number;
  atrp_14?: number;
  atrp_30?: number;
  range_pos_20d?: number;
  range_pos_50d?: number;
  range_pos_52w?: number;
  atrx_sma_21?: number;
  atrx_sma_50?: number;
  atrx_sma_100?: number;
  atrx_sma_150?: number;
  rsi?: number;
  macd?: number;
  macd_signal?: number;
  perf_1d?: number;
  perf_5d?: number;
  perf_20d?: number;
  perf_60d?: number;
  perf_252d?: number;
  ext_pct?: number;
  sma150_slope?: number;
  sma50_slope?: number;
  ema10_dist_pct?: number;
  ema10_dist_n?: number;
  vol_ratio?: number;
  scan_tier?: string;
  action_label?: string;
  regime_state?: string;
  pass_count?: number;
  atre_promoted?: boolean;
  action_override?: string;
  manual_review?: boolean;
  quad_quarterly?: string;
  quad_monthly?: string;
  quad_divergence_flag?: boolean;
  quad_depth?: number;
  forward_rr?: number;
  correlation_flag?: boolean;
  sector_confirmation?: boolean;
  entry_price?: number | null;
  exit_price?: number | null;
  momentum_score?: number;
  [key: string]: unknown;
}

// ---------------------------------------------------------------------------
// /snapshots/table
// ---------------------------------------------------------------------------

export interface SnapshotTableParams {
  sort_by?: string;
  sort_dir?: 'asc' | 'desc';
  filter_stage?: string;
  search?: string;
  sectors?: string;
  scan_tiers?: string;
  regime_state?: string;
  rs_min?: number;
  rs_max?: number;
  action_labels?: string;
  preset?: string;
  index_name?: string;
  symbols?: string;
  offset?: number;
  limit?: number;
  include_plan?: boolean;
}

export interface SnapshotTableResponse {
  rows: MarketSnapshotRow[];
  total: number;
}

// ---------------------------------------------------------------------------
// /snapshots/aggregates
// ---------------------------------------------------------------------------

export interface SnapshotAggregateParams {
  filter_stage?: string;
  sectors?: string;
  scan_tiers?: string;
  regime_state?: string;
  action_labels?: string;
  preset?: string;
  index_name?: string;
  symbols?: string;
}

export interface StageDistributionEntry {
  stage: string;
  count: number;
}

export interface SectorSummaryEntry {
  sector: string;
  count: number;
  avg_rs: number | null;
  avg_perf_1d: number | null;
  avg_perf_20d: number | null;
  stage2_pct: number | null;
  stage4_pct: number | null;
  health: string | null;
}

export interface TierDistributionEntry {
  scan_tier: string;
  count: number;
}

export interface ActionDistributionEntry {
  action: string;
  count: number;
}

export interface SnapshotAggregateResponse {
  total: number;
  stage_distribution: StageDistributionEntry[];
  sector_summary: SectorSummaryEntry[];
  scan_tier_distribution: TierDistributionEntry[];
  action_distribution: ActionDistributionEntry[];
}

// ---------------------------------------------------------------------------
// /quad/current  +  /quad/history
// ---------------------------------------------------------------------------

export interface QuadState {
  as_of_date: string | null;
  quarterly_quad: string | null;
  monthly_quad: string | null;
  operative_quad: string | null;
  quarterly_depth: number | null;
  monthly_depth: number | null;
  divergence_flag: boolean | null;
  divergence_months: number | null;
  source?: string | null;
}

export interface QuadCurrentResponse {
  quad: QuadState | null;
  message?: string;
}

export interface QuadHistoryResponse {
  history: QuadState[];
}

// ---------------------------------------------------------------------------
// /regime/current (extended)
// ---------------------------------------------------------------------------

export interface RegimeData {
  regime_state: string;
  composite_score: number;
  as_of_date: string;
  vix_spot: number | null;
  vix3m_vix_ratio: number | null;
  vvix_vix_ratio: number | null;
  nh_nl: number | null;
  pct_above_200d: number | null;
  pct_above_50d: number | null;
  score_vix: number | null;
  score_vix3m_vix: number | null;
  score_vvix_vix: number | null;
  score_nh_nl: number | null;
  score_above_200d: number | null;
  score_above_50d: number | null;
  weights_used: number[] | null;
  cash_floor_pct: number | null;
  max_equity_exposure_pct: number | null;
  regime_multiplier: number | null;
}
