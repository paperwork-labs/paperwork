/** JSON shapes from Brain `success_response` envelopes (`apis/brain/app/schemas/base.py`). */

export type BrainEnvelope<T> = { success: boolean; data?: T; error?: string };

export type VercelQuotaApiPayload = {
  batch_at: string | null;
  count: number;
  snapshots: VercelQuotaSnapshotRow[];
};

export type VercelQuotaSnapshotRow = {
  id: number;
  created_at: string | null;
  project_id: string | null;
  project_name: string;
  window_days: number;
  deploy_count: number;
  build_minutes: number;
  source_breakdown: Record<string, number>;
  meta: Record<string, unknown>;
};

export type GitHubActionsQuotaApiPayload = {
  batch_at: string | null;
  count: number;
  snapshots: GitHubActionsQuotaSnapshotRow[];
};

export type GitHubActionsQuotaSnapshotRow = {
  id: number;
  recorded_at: string | null;
  repo: string;
  is_public: boolean;
  minutes_used: number | null;
  minutes_limit: number | null;
  included_minutes: number | null;
  paid_minutes_used: number | null;
  total_paid_minutes_used_breakdown: Record<string, number>;
  minutes_used_breakdown: Record<string, number>;
  cache_size_bytes: number | null;
  cache_count: number | null;
  extra_json: Record<string, unknown>;
};

export type RenderQuotaApiPayload = {
  snapshot: RenderQuotaSnapshot | null;
  top_services_by_minutes: RenderTopServiceMinutes[];
};

export type RenderQuotaSnapshot = {
  recorded_at: string;
  month: string;
  pipeline_minutes_used: number;
  pipeline_minutes_included: number;
  usage_ratio: number;
  derived_from: string;
  bandwidth_gb_used: number | null;
  bandwidth_gb_included: number | null;
  unbilled_charges_usd: number | null;
};

export type RenderTopServiceMinutes = {
  service_id?: string;
  name?: string;
  approx_minutes?: number;
};
