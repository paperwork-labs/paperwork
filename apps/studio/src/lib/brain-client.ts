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
import type { GoalsJson } from "@/lib/goals-metrics";
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
