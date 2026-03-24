/** Typed contract for GET /market-data/admin/health */

export interface CoverageDimension {
  status: 'green' | 'red';
  daily_pct: number;
  m5_pct: number;
  stale_daily: number;
  stale_m5: number;
  tracked_count: number;
  expected_date: string | null;
  summary: string;
  error?: string;
}

export interface StageQualityDimension {
  status: 'green' | 'red';
  unknown_rate: number;
  invalid_count: number;
  monotonicity_issues: number;
  stale_stage_count: number;
  total_symbols: number;
  stage_counts: Record<string, number>;
  error?: string;
}

export interface JobsDimension {
  status: 'green' | 'red';
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
  error?: string;
}

export interface AuditDimension {
  status: 'green' | 'red';
  tracked_total: number | null;
  daily_fill_pct: number;
  snapshot_fill_pct: number;
  missing_sample: string[];
  error?: string;
}

export interface RegimeDimension {
  status: 'green' | 'red';
  regime_state: string | null;
  composite_score: number | null;
  as_of_date: string | null;
  age_hours: number;
  multiplier: number | null;
  max_equity_pct: number | null;
  cash_floor_pct: number | null;
  error?: string;
}

export interface TaskRunEntry {
  ts: string | null;
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
  };
  task_runs: Record<string, TaskRunEntry | null>;
  thresholds: Record<string, number>;
  checked_at: string;
}
