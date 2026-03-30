/** Typed contract for GET /market-data/admin/health */

type DimStatus = 'green' | 'yellow' | 'red' | 'ok' | 'warning' | 'error';

interface BaseDimension {
  status: DimStatus;
  category: 'market' | 'broker';
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
}

export interface StageQualityDimension extends BaseDimension {
  unknown_rate: number;
  invalid_count: number;
  monotonicity_issues: number;
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
  market_only_mode: boolean;
  dimensions: {
    coverage: CoverageDimension;
    stage_quality: StageQualityDimension;
    jobs: JobsDimension;
    audit: AuditDimension;
    regime: RegimeDimension;
    fundamentals: FundamentalsDimension;
    portfolio_sync: PortfolioSyncDimension;
    ibkr_gateway: IbkrGatewayDimension;
  };
  task_runs: Record<string, TaskRunEntry | null>;
  thresholds: Record<string, number>;
  checked_at: string;
}

/** Auto-fix API types */
export interface AutoFixTask {
  task_name: string;
  label: string;
  reason: string;
  priority: number;
  task_id?: string;
  status?: 'pending' | 'running' | 'completed' | 'failed';
  started_at?: string | null;
  finished_at?: string | null;
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
  overall_status: 'pending' | 'running' | 'completed' | 'failed';
  completed_count: number;
  total_count: number;
  current_task: string | null;
  plan: AutoFixTask[];
}
