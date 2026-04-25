/** Typed contract for GET /market-data/admin/health */

type DimStatus = 'green' | 'yellow' | 'red' | 'ok' | 'warning' | 'error';

interface BaseDimension {
  status: DimStatus;
  category: 'market' | 'broker' | 'infra';
  advisory?: boolean;
  error?: string;
}

export interface CoverageDimension extends BaseDimension {
  daily_pct: number;
  m5_pct: number;
  stale_daily: number;
  stale_m5: number;
  tracked_count: number;
  expected_date: string | null;
  summary: string;
  indices?: Record<string, number>;
  curated_etf_count?: number;
}

export interface StageQualityDimension extends BaseDimension {
  unknown_rate: number;
  invalid_count: number;
  /**
   * Legacy name for stage-day counter drift. Kept for back-compat — the
   * backend now also emits ``stage_days_drift_count`` with the same value
   * plus ``stage_days_drift_pct`` scaled against the history-rows
   * denominator. Prefer the *_drift_* fields for new UI code.
   */
  monotonicity_issues: number;
  stage_days_drift_count?: number;
  stage_days_drift_pct?: number | null;
  stage_history_rows_checked?: number;
  reason?: string;
  stale_stage_count: number;
  total_symbols: number;
  stage_counts: Record<string, number>;
}

export interface JobsDimension extends BaseDimension {
  window_hours: number;
  total: number;
  ok_count: number;
  error_count: number;
  running_count: number;
  cancelled_count: number;
  completed_count: number;
  success_rate: number;
  latest_failed: {
    id: number;
    task_name: string;
    status: string;
    started_at: string | null;
    error: string | null;
  } | null;
}

export interface AuditDimension extends BaseDimension {
  tracked_total: number | null;
  daily_fill_pct: number;
  snapshot_fill_pct: number;
  missing_sample: string[];
  history_depth_years?: number | null;
  earliest_date?: string | null;
  ohlcv_earliest_date?: string | null;
  ohlcv_symbol_count?: number | null;
}

export interface RegimeDimension extends BaseDimension {
  regime_state: string | null;
  composite_score: number | null;
  as_of_date: string | null;
  age_hours: number;
  multiplier: number | null;
  max_equity_pct: number | null;
  cash_floor_pct: number | null;
}

export interface FundamentalsDimension extends BaseDimension {
  fundamentals_fill_pct: number;
  tracked_total: number;
  filled_count: number;
}

export interface PortfolioSyncDimension extends BaseDimension {
  total_accounts: number;
  stale_accounts: number;
  stale_list: string[];
  note?: string;
}

export interface IbkrGatewayDimension extends BaseDimension {
  connection_status: string;
  last_ping: string | null;
  is_stale: boolean;
  note?: string;
}

/**
 * G28 deploy-health guardrail (D120).
 *
 * Emitted by `AdminHealthService._build_deploys_dimension` — one summary
 * row per monitored Render service plus rollup counters. The dedicated
 * `/api/v1/admin/deploys/health` endpoint returns the same service
 * summaries plus a raw event tail for the timeline UI.
 */
export interface DeployServiceSummary {
  service_id: string;
  service_slug: string;
  service_type: string;
  status: 'green' | 'yellow' | 'red';
  reason: string;
  last_status: string | null;
  last_deploy_sha: string | null;
  last_deploy_at: string | null;
  last_live_sha: string | null;
  last_live_at: string | null;
  consecutive_failures: number;
  failures_24h: number;
  deploys_24h: number;
  in_flight: boolean;
}

export interface DeployEvent {
  id: number;
  service_id: string;
  service_slug: string;
  service_type: string;
  deploy_id: string;
  status: string;
  trigger: string | null;
  commit_sha: string | null;
  commit_message: string | null;
  render_created_at: string;
  render_finished_at: string | null;
  duration_seconds: number | null;
  is_poll_error: boolean;
  poll_error_message: string | null;
  polled_at: string;
}

export interface DeploysDimension extends BaseDimension {
  services: DeployServiceSummary[];
  services_configured: number;
  consecutive_failures_max: number;
  failures_24h_total: number;
  reason: string;
}

export interface DeployHealthDetailResponse {
  status: 'green' | 'yellow' | 'red';
  reason: string;
  services: DeployServiceSummary[];
  services_configured: number;
  consecutive_failures_max: number;
  failures_24h_total: number;
  events: DeployEvent[];
  checked_at: string;
}

export interface DataAccuracyDimension extends BaseDimension {
  mismatch_count: number;
  bars_checked: number;
  bars_matched: number;
  match_rate: number;
  missing_in_db: number;
  sample_size: number;
  checked_at?: string;
  age_days?: number;
  mismatches?: Array<{
    symbol: string;
    date: string;
    type: string;
    ref_close?: number;
    db_close?: number;
    pct_diff?: number;
    data_source?: string;
  }>;
  note?: string;
}

export interface ProviderUsage {
  calls: number;
  budget: number;
  pct: number;
}

export interface ProviderMetrics {
  providers: Record<string, ProviderUsage>;
  l1_hits: number;
  l2_hits: number;
  api_calls: number;
  total_requests: number;
  l2_hit_rate: number;
  cache_hit_rate: number;
  date: string;
}

export interface PreMarketReadiness {
  ready: boolean;
  gaps: string[];
  last_trading_session?: string;
  daily_pct: number;
  snapshot_fill_pct: number;
  regime_age_hours: number;
  checked_at: string;
}

export interface TaskRunEntry {
  task: string;
  status: string;
  ts: string | null;
  payload?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface AdminHealthResponse {
  composite_status: 'green' | 'yellow' | 'red';
  composite_reason: string;
  dimensions: {
    coverage: CoverageDimension;
    stage_quality: StageQualityDimension;
    jobs: JobsDimension;
    audit: AuditDimension;
    regime: RegimeDimension;
    fundamentals: FundamentalsDimension;
    portfolio_sync: PortfolioSyncDimension;
    ibkr_gateway: IbkrGatewayDimension;
    data_accuracy: DataAccuracyDimension;
    deploys?: DeploysDimension;
  };
  task_runs: Record<string, TaskRunEntry | null>;
  thresholds: Record<string, number>;
  checked_at: string;
  provider_metrics?: ProviderMetrics;
}

/** Auto-fix API types — aligned with backend AutoFixPlanItem */
export interface AutoFixTask {
  task: string;
  reason: string;
  task_id?: string;
  status?: 'pending' | 'running' | 'completed' | 'failed';
  started_at?: string | null;
  finished_at?: string | null;
  duration_seconds?: number | null;
  error?: string | null;
}

export interface AutoFixResponse {
  job_id: string;
  status: string;
  message: string;
  plan: AutoFixTask[];
}

export interface AutoFixStatusResponse {
  job_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  completed_count: number;
  total_count: number;
  current_task: string | null;
  plan: AutoFixTask[];
}