/**
 * BrainClient — typed wrapper for Brain admin API calls.
 *
 * Replaces placeholder data in Studio admin pages with live data from
 * `{BRAIN_API_URL}/api/v1/admin/*` using the `X-Brain-Secret` header.
 *
 * Error handling follows the no-silent-fallback rule: callers always receive
 * either typed data or an explicit `BrainClientError` — never a silently
 * coerced zero/empty fallback that masquerades as healthy.
 */

import {
  type BrainAdminAuth,
  getBrainAdminFetchOptions,
} from "@/lib/brain-admin-proxy";
import type { GoalsJson, Objective } from "@/lib/goals-metrics";
import type { BrainEnvelope } from "@/lib/quota-monitor-types";

// ---------------------------------------------------------------------------
// Error type
// ---------------------------------------------------------------------------

export class BrainClientError extends Error {
  readonly status: number;
  readonly endpoint: string;

  constructor(endpoint: string, status: number, detail: string) {
    super(`Brain ${endpoint}: ${detail}`);
    this.name = "BrainClientError";
    this.endpoint = endpoint;
    this.status = status;
  }
}

// ---------------------------------------------------------------------------
// Response shapes (match Brain API JSON envelopes)
// ---------------------------------------------------------------------------

export type OperatingScorePillar = {
  pillar_id: string;
  label: string;
  score: number;
  max_score: number;
  findings: string[];
};

export type OperatingScoreResponse = {
  overall_score: number;
  max_score: number;
  computed_at: string | null;
  pillars: OperatingScorePillar[];
};

export type DispatchLogEntry = {
  dispatched_at: string;
  persona?: string | null;
  persona_slug?: string | null;
  persona_pin?: string | null;
  pr_number?: number | null;
  task_summary?: string | null;
  workstream_id?: string | null;
  workstream_type?: string | null;
  agent_model?: string | null;
  outcome?: {
    merged_at?: string | null;
    reverted?: boolean;
    ci_initial_pass?: boolean;
    review_pass?: boolean;
  } | null;
};

export type DispatchLogResponse = {
  dispatches: DispatchLogEntry[];
  count: number;
};

export type ProbeResult = {
  cuj_id: string;
  name: string;
  status: "pass" | "fail" | "unknown";
  last_run_at: string | null;
  assertion?: string | null;
};

export type ProbeResultsResponse = {
  results: ProbeResult[];
  checked_at: string | null;
};

export type PersonaSpec = {
  persona_id: string;
  name: string;
  description: string | null;
  model: string | null;
  routing_active: boolean;
};

export type PersonasResponse = {
  personas: PersonaSpec[];
};

/** ``GET /admin/memory-stats`` — episode aggregates + storage estimate (WS-82 Phase D). */
export type BrainMemoryStats = {
  organization_id: string;
  total_episodes: number;
  episodes_by_source: { source: string; count: number }[];
  other_sources_episode_count: number;
  trailing_30_days: { episode_count: number; average_per_day: number };
  storage_estimate_bytes: number;
  storage_estimate_note: string;
};

export type PersonaDispatchSummaryRow = {
  persona_slug: string;
  dispatch_count: number;
  success_count: number;
  failure_count: number;
  pending_outcome_count: number;
  last_dispatch_at: string | null;
  recent_dispatch_count_30d: number;
  success_rate: number | null;
};

/** ``GET /admin/persona-dispatch-summary`` */
export type PersonaDispatchSummaryResponse = {
  source_path: string;
  window_days: number;
  dispatch_total: number;
  personas: PersonaDispatchSummaryRow[];
  recent_activity: Record<string, unknown>[];
  notes: string;
};

/** ``GET /admin/operating-score/history`` */
export type OperatingScoreHistoryResponse = {
  days: number;
  series: { date: string; total: number | null }[];
  source: string;
  granularity: string;
};

/** ``GET /admin/cost-breakdown`` — token-derived spend estimates */
export type CostBreakdownResponse = {
  organization_id: string;
  window_days: number;
  currency: string;
  estimated: boolean;
  pricing_note: string;
  by_persona: {
    persona: string;
    tokens_in: number;
    tokens_out: number;
    estimated_usd: number;
  }[];
  by_model: {
    model: string;
    tokens_in: number;
    tokens_out: number;
    estimated_usd: number;
  }[];
  by_day: {
    date: string;
    tokens_in: number;
    tokens_out: number;
    estimated_usd: number;
  }[];
  totals: { tokens_in: number; tokens_out: number; estimated_usd: number };
};

/** ``GET /admin/brain-fill-meter`` */
export type BrainFillMeterResponse = {
  organization_id: string;
  overall_utilization_pct: number;
  tiers: {
    episodic: {
      label: string;
      used_units: number;
      capacity_units: number;
      utilization_pct: number;
    };
    procedural: {
      label: string;
      used_units: number;
      capacity_units: number;
      utilization_pct: number;
    };
    semantic: {
      label: string;
      used_units: number;
      capacity_units: number;
      utilization_pct: number;
      note?: string;
    };
  };
  notes: string;
};

// ---------------------------------------------------------------------------
// Standalone write helpers (Goals admin — POST/PUT/DELETE/PATCH)
// ---------------------------------------------------------------------------

export type GoalKeyResultInput = {
  title: string;
  target: number;
  current?: number;
  unit?: string;
  source_url?: string | null;
  id?: string | null;
};

export type CreateGoalInput = {
  objective: string;
  owner: string;
  quarter: string;
  due_date?: string | null;
  key_results: GoalKeyResultInput[];
};

export type UpdateGoalInput = {
  objective?: string;
  owner?: string;
  quarter?: string;
  due_date?: string | null;
  key_results?: GoalKeyResultInput[];
};

export type KeyResultProgressResponse = {
  id: string;
  title: string;
  target: number;
  current: number;
  unit: string;
  source_url: string | null;
  note?: string;
  progress_pct: number;
};

async function parseBrainAdminResponse<T>(label: string, res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new BrainClientError(
      label,
      res.status,
      body
        ? `HTTP ${res.status}: ${body.slice(0, 300)}`
        : `HTTP ${res.status}`,
    );
  }

  let json: unknown;
  try {
    json = await res.json();
  } catch {
    throw new BrainClientError(label, res.status, "invalid JSON body");
  }

  const envelope = json as BrainEnvelope<T>;
  if (typeof envelope === "object" && envelope !== null && "success" in envelope) {
    if (!envelope.success) {
      throw new BrainClientError(
        label,
        res.status,
        envelope.error ?? "Brain returned success=false",
      );
    }
    if (envelope.data !== undefined) {
      return envelope.data as T;
    }
  }

  return json as T;
}

async function brainAdminMutationJson<T>(
  label: string,
  path: string,
  method: string,
  body?: unknown,
): Promise<T> {
  const auth = getBrainAdminFetchOptions();
  if (!auth.ok) {
    throw new BrainClientError(
      label,
      0,
      "Brain admin API not configured (BRAIN_API_URL / BRAIN_API_SECRET)",
    );
  }

  const headers: Record<string, string> = { "X-Brain-Secret": auth.secret };
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
  }

  const url = `${auth.root}${path}`;
  let res: Response;
  try {
    res = await fetch(url, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      cache: "no-store",
    });
  } catch (err) {
    throw new BrainClientError(
      label,
      0,
      err instanceof Error ? err.message : "network error",
    );
  }

  return parseBrainAdminResponse<T>(label, res);
}

/** POST ``/admin/goals`` — create objective + optional KRs; sets top-level quarter. */
export async function createGoal(input: CreateGoalInput): Promise<Objective> {
  return brainAdminMutationJson<Objective>("goals/create", "/admin/goals", "POST", input);
}

/** PUT ``/admin/goals/{goal_id}`` — partial update (replace ``key_results`` when supplied). */
export async function updateGoal(goalId: string, input: UpdateGoalInput): Promise<Objective> {
  return brainAdminMutationJson<Objective>(
    "goals/update",
    `/admin/goals/${encodeURIComponent(goalId)}`,
    "PUT",
    input,
  );
}

/** DELETE ``/admin/goals/{goal_id}`` — soft-delete (``archived_at``). */
export async function archiveGoal(goalId: string): Promise<{ id: string; archived_at: string }> {
  return brainAdminMutationJson<{ id: string; archived_at: string }>(
    "goals/archive",
    `/admin/goals/${encodeURIComponent(goalId)}`,
    "DELETE",
  );
}

/** PATCH ``/admin/goals/{goal_id}/key-results/{kr_id}`` — set KR ``current`` from ``current_value``. */
export async function updateKRProgress(
  goalId: string,
  krId: string,
  currentValue: number,
  note?: string | null,
): Promise<KeyResultProgressResponse> {
  const body: { current_value: number; note?: string } = { current_value: currentValue };
  if (note !== undefined && note !== null && note !== "") {
    body.note = note;
  }
  return brainAdminMutationJson<KeyResultProgressResponse>(
    "goals/kr-progress",
    `/admin/goals/${encodeURIComponent(goalId)}/key-results/${encodeURIComponent(krId)}`,
    "PATCH",
    body,
  );
}

// ---------------------------------------------------------------------------
// BrainClient
// ---------------------------------------------------------------------------

export class BrainClient {
  private readonly root: string;
  private readonly secret: string;

  constructor(root: string, secret: string) {
    this.root = root;
    this.secret = secret;
  }

  /**
   * Create a client from environment variables (BRAIN_API_URL, BRAIN_API_SECRET).
   * Returns null if not configured — callers should surface this as an error state.
   */
  static fromEnv(): BrainClient | null {
    const auth: BrainAdminAuth = getBrainAdminFetchOptions();
    if (!auth.ok) return null;
    return new BrainClient(auth.root, auth.secret);
  }

  // -----------------------------------------------------------------------
  // Admin endpoints
  // -----------------------------------------------------------------------

  /** Fetch the current operating score with per-pillar breakdown. */
  async getOperatingScore(): Promise<OperatingScoreResponse> {
    return this.get<OperatingScoreResponse>(
      "/admin/operating-score",
      "operating-score",
    );
  }

  /**
   * Fetch persona/agent dispatch events from Brain (`agent_dispatch_log.json` on the Brain host).
   * Uses `/admin/agent-dispatch-log` — not `/admin/logs` (that route is application logs).
   *
   * @param limit  Max entries to return (default 100).
   * @param since  ISO-8601 lower bound for `dispatched_at`.
   */
  async getDispatchLog(
    limit = 100,
    since?: string,
  ): Promise<DispatchLogResponse> {
    const params = new URLSearchParams();
    params.set("limit", String(limit));
    if (since) params.set("since", since);
    return this.get<DispatchLogResponse>(
      `/admin/agent-dispatch-log?${params}`,
      "agent-dispatch-log",
    );
  }

  /** Fetch the latest CUJ probe results. */
  async getProbeResults(product?: string): Promise<ProbeResultsResponse> {
    const params = new URLSearchParams();
    if (product) params.set("product", product);
    const qs = params.toString();
    const path = qs ? `/probes/health?${qs}` : "/probes/health";
    return this.get<ProbeResultsResponse>(path, "probe-results");
  }

  /** Fetch the persona registry from the Brain API. */
  async getPersonas(): Promise<PersonasResponse> {
    return this.get<PersonasResponse>("/admin/personas", "personas");
  }

  /** Fetch goals / OKRs payload for Studio admin (same shape as static goals.json). */
  async getGoals(): Promise<GoalsJson> {
    return this.get<GoalsJson>("/admin/goals", "goals");
  }

  /** Memory layer statistics for Overview health tiles. */
  async getMemoryStats(organizationId = "paperwork-labs"): Promise<BrainMemoryStats> {
    const params = new URLSearchParams({ organization_id: organizationId });
    return this.get<BrainMemoryStats>(`/admin/memory-stats?${params}`, "memory-stats");
  }

  /** Dispatch roll-ups for Personas admin enrichment. */
  async getPersonaDispatchSummary(): Promise<PersonaDispatchSummaryResponse> {
    return this.get<PersonaDispatchSummaryResponse>(
      "/admin/persona-dispatch-summary",
      "persona-dispatch-summary",
    );
  }

  /** Daily operating score series (forward-filled) for sparklines. */
  async getOperatingScoreHistory(days = 30): Promise<OperatingScoreHistoryResponse> {
    const params = new URLSearchParams({ days: String(days) });
    return this.get<OperatingScoreHistoryResponse>(
      `/admin/operating-score/history?${params}`,
      "operating-score/history",
    );
  }

  /** LLM cost estimates from episode tokens (Infra cost tab). */
  async getCostBreakdown(
    days = 30,
    organizationId = "paperwork-labs",
  ): Promise<CostBreakdownResponse> {
    const params = new URLSearchParams({
      days: String(days),
      organization_id: organizationId,
    });
    return this.get<CostBreakdownResponse>(`/admin/cost-breakdown?${params}`, "cost-breakdown");
  }

  /** Tier utilization snapshot (episodic / procedural / semantic). */
  async getBrainFillMeter(organizationId = "paperwork-labs"): Promise<BrainFillMeterResponse> {
    const params = new URLSearchParams({ organization_id: organizationId });
    return this.get<BrainFillMeterResponse>(
      `/admin/brain-fill-meter?${params}`,
      "brain-fill-meter",
    );
  }

  // -----------------------------------------------------------------------
  // Internal helpers
  // -----------------------------------------------------------------------

  /**
   * Issue a GET request to the Brain API, unwrap the `{ success, data, error }`
   * envelope, and return typed data — or throw `BrainClientError`.
   */
  private async get<T>(path: string, label: string): Promise<T> {
    const url = `${this.root}${path}`;
    let res: Response;
    try {
      res = await fetch(url, {
        method: "GET",
        headers: { "X-Brain-Secret": this.secret },
        cache: "no-store",
      });
    } catch (err) {
      throw new BrainClientError(
        label,
        0,
        err instanceof Error ? err.message : "network error",
      );
    }

    if (!res.ok) {
      const body = await res.text().catch(() => "");
      throw new BrainClientError(
        label,
        res.status,
        body
          ? `HTTP ${res.status}: ${body.slice(0, 300)}`
          : `HTTP ${res.status}`,
      );
    }

    let json: unknown;
    try {
      json = await res.json();
    } catch {
      throw new BrainClientError(label, res.status, "invalid JSON body");
    }

    // Unwrap Brain envelope
    const envelope = json as BrainEnvelope<T>;
    if (
      typeof envelope === "object" &&
      envelope !== null &&
      "success" in envelope
    ) {
      if (!envelope.success) {
        throw new BrainClientError(
          label,
          res.status,
          envelope.error ?? "Brain returned success=false",
        );
      }
      if (envelope.data !== undefined) {
        return envelope.data as T;
      }
    }

    // Some endpoints return raw JSON without an envelope — pass through.
    return json as T;
  }
}
