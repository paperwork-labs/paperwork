/**
 * AutoOps explainer API client.
 *
 * Thin typed wrapper over the admin AnomalyExplainer endpoints exposed by
 * `backend/api/routes/admin/autoops.py`. Kept in its own module so the
 * SystemStatus surface (drawer + recent panel) stays free of axios
 * boilerplate and the wire shapes have a single source of truth that
 * mirrors `AutoOpsExplanationOut` on the backend.
 */
import api from './api';

export interface AutoOpsRemediationStep {
  order: number;
  description: string;
  runbook_section?: string | null;
  proposed_task?: string | null;
  requires_approval: boolean;
  rationale?: string | null;
}

export interface AutoOpsExplanationPayload {
  schema_version?: string;
  anomaly_id?: string;
  title?: string;
  summary?: string;
  root_cause_hypothesis?: string;
  narrative?: string;
  steps?: AutoOpsRemediationStep[];
  confidence?: string | number;
  runbook_excerpts?: string[];
  generated_at?: string;
  model?: string;
  is_fallback?: boolean;
}

export interface AutoOpsExplanation {
  id: number;
  schema_version: string;
  anomaly_id: string;
  category: string;
  severity: string;
  title: string;
  summary: string;
  confidence: string;
  is_fallback: boolean;
  model: string;
  generated_at: string | null;
  payload: AutoOpsExplanationPayload;
}

export interface AutoOpsExplanationList {
  total: number;
  items: AutoOpsExplanation[];
}

export async function listExplanations(
  params: {
    limit?: number;
    offset?: number;
    category?: string;
    severity?: string;
    fallbackOnly?: boolean;
  } = {},
): Promise<AutoOpsExplanationList> {
  const qs = new URLSearchParams();
  qs.set('limit', String(params.limit ?? 10));
  if (params.offset != null) qs.set('offset', String(params.offset));
  if (params.category) qs.set('category', params.category);
  if (params.severity) qs.set('severity', params.severity);
  if (params.fallbackOnly != null) {
    qs.set('fallback_only', String(params.fallbackOnly));
  }
  const { data } = await api.get<AutoOpsExplanationList>(
    `/admin/agent/explanations?${qs.toString()}`,
  );
  return data;
}

export async function explainDimension(args: {
  dimension: string;
  dimensionPayload: Record<string, unknown>;
}): Promise<AutoOpsExplanation> {
  const { data } = await api.post<AutoOpsExplanation>(
    '/admin/agent/explain/dimension',
    {
      dimension: args.dimension,
      dimension_payload: args.dimensionPayload,
    },
  );
  return data;
}
