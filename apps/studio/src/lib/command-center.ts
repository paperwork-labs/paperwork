import type { InfraStatus, InfrastructureView } from "@/lib/infra-types";
import type {
  BrainFillMeterResponse,
  BrainMemoryStats,
  CostBreakdownResponse,
  OperatingScoreHistoryResponse,
  PersonaDispatchSummaryResponse,
} from "@/lib/brain-client";
import { collectRenderAndVercelProbes } from "@/lib/infra-probes";

export type { InfraStatus, InfrastructureView, PlatformHealthSummary } from "@/lib/infra-types";

const responseCache = new Map<string, { data: unknown; ts: number }>();
export function cached<T>(key: string, ttlMs: number, fn: () => Promise<T>): Promise<T> {
  const hit = responseCache.get(key);
  if (hit && Date.now() - hit.ts < ttlMs) return Promise.resolve(hit.data as T);
  return fn().then((data) => {
    responseCache.set(key, { data, ts: Date.now() });
    return data;
  });
}

export type N8nWorkflow = {
  id: string;
  name: string;
  active: boolean;
  createdAt?: string;
  updatedAt?: string;
};

export type N8nExecution = {
  id: string;
  finished: boolean;
  mode: string;
  startedAt?: string;
  stoppedAt?: string;
  workflowId?: string;
  status?: string;
  workflowData?: { name?: string };
};

export type PullRequestSummary = {
  number: number;
  title: string;
  html_url: string;
  created_at: string;
  updated_at: string;
  draft: boolean;
  user?: { login?: string };
};

export type WorkflowMeta = {
  model: string | null;
  costPerRun: string;
  trigger: string;
  role: string;
};

// Source: docs/AI_MODEL_REGISTRY.md + infra/hetzner/workflows/*.json
export const WORKFLOW_META: Record<string, WorkflowMeta> = {
  "Annual Data Update Trigger (P2.10)": {
    model: null,
    costPerRun: "$0",
    trigger: "Cron Oct 1, 9am PT",
    role: "No AI",
  },
  "Brain Daily Trigger": {
    model: "Brain-routed",
    costPerRun: "~$0.003",
    trigger: "Cron 7am (daily briefing)",
    role: "ea",
  },
  "Brain PR Summary": {
    model: "Brain-routed",
    costPerRun: "~$0.001",
    trigger: "GitHub webhook",
    role: "engineering",
  },
  "Brain Slack Adapter": {
    model: "Brain-routed",
    costPerRun: "~$0.02",
    trigger: "Slack webhook (POST /brain-slack)",
    role: "thread-resolved persona",
  },
  "Brain Weekly Trigger": {
    model: "Brain-routed",
    costPerRun: "~$0.005",
    trigger: "Cron Sun 6pm (weekly plan)",
    role: "ea",
  },
  "CPA Tax Review": {
    model: "Brain-routed",
    costPerRun: "~$0.05",
    trigger: "POST webhook",
    role: "cpa",
  },
  "Credential Expiry Check": {
    model: null,
    costPerRun: "$0",
    trigger: "Cron 8am PT",
    role: "No AI",
  },
  "Data Deep Validator (P2.9)": {
    model: null,
    costPerRun: "$0",
    trigger: "Cron monthly (1st, 3am PT)",
    role: "No AI",
  },
  "Data Source Monitor (P2.8)": {
    model: null,
    costPerRun: "$0",
    trigger: "Cron Mon 6am PT",
    role: "No AI",
  },
  "Decision Logger": {
    model: null,
    costPerRun: "$0",
    trigger: "Slack webhook",
    role: "No AI",
  },
  "Error Notification": {
    model: null,
    costPerRun: "$0",
    trigger: "n8n workflow error hook",
    role: "No AI",
  },
  "Growth Content Writer": {
    model: "gpt-4o",
    costPerRun: "~$0.05",
    trigger: "POST webhook",
    role: "growth",
  },
  "Infra Health Check": {
    model: null,
    costPerRun: "$0",
    trigger: "Cron every 30m",
    role: "No AI",
  },
  "Infra Heartbeat": {
    model: null,
    costPerRun: "$0",
    trigger: "Cron daily",
    role: "No AI",
  },
  "Infra Status Slash Command": {
    model: null,
    costPerRun: "$0",
    trigger: "Slack slash command",
    role: "No AI",
  },
  "Partnership Outreach Drafter": {
    model: "gpt-4o",
    costPerRun: "~$0.03",
    trigger: "POST webhook",
    role: "partnerships",
  },
  "QA Security Scan": {
    model: "Brain-routed",
    costPerRun: "~$0.05",
    trigger: "POST webhook",
    role: "qa",
  },
  "Social Content Generator": {
    model: "gpt-4o",
    costPerRun: "~$0.05",
    trigger: "POST webhook",
    role: "social",
  },
  "Sprint Close": {
    model: "gpt-4o",
    costPerRun: "~$0.04",
    trigger: "Cron Fri 9pm PT",
    role: "strategy",
  },
  "Sprint Kickoff": {
    model: "Brain-routed",
    costPerRun: "~$0.05",
    trigger: "Cron Mon 7am PT",
    role: "strategy",
  },
  "Weekly Strategy Check-in": {
    model: "gpt-4o",
    costPerRun: "~$0.04",
    trigger: "Cron Mon 9am PT",
    role: "strategy",
  },
};

function normalizeBaseUrl(raw: string | undefined) {
  if (!raw) return undefined;
  return raw.trim().replace(/\/+$/, "");
}

function getN8nApiRoot() {
  const base = normalizeBaseUrl(process.env.N8N_API_URL) || normalizeBaseUrl(process.env.N8N_HOST);
  if (!base) return undefined;
  return base.endsWith("/api/v1") ? base : `${base}/api/v1`;
}

function getN8nHeaders() {
  const apiKey = process.env.N8N_API_KEY?.trim();
  if (apiKey) {
    return { "X-N8N-API-KEY": apiKey } as Record<string, string>;
  }

  const basicRaw = process.env.N8N_BASIC_AUTH?.trim();
  if (basicRaw) {
    return { Authorization: `Basic ${Buffer.from(basicRaw).toString("base64")}` } as Record<string, string>;
  }

  const basicUser = process.env.N8N_BASIC_AUTH_USER?.trim();
  const basicPassword = process.env.N8N_BASIC_AUTH_PASSWORD?.trim();
  if (basicUser && basicPassword) {
    return {
      Authorization: `Basic ${Buffer.from(`${basicUser}:${basicPassword}`).toString("base64")}`,
    } as Record<string, string>;
  }

  return undefined;
}

/** True when n8n REST base URL and credentials are configured (F-014 / F-020; same gate as workflow/execution fetches). */
export function isN8nIntegrationConfigured(): boolean {
  return Boolean(getN8nApiRoot() && getN8nHeaders());
}

export type FetchJsonOk<T> = { ok: true; data: T };
export type FetchJsonErr = { ok: false; error: string; status?: number };
export type FetchJsonResult<T> = FetchJsonOk<T> | FetchJsonErr;

function truncateFetchDetail(raw: string, max = 280): string {
  const t = raw.trim().replace(/\s+/g, " ");
  return t.length <= max ? t : `${t.slice(0, max)}…`;
}

/** Typed HTTP+JSON fetch — surfaces HTTP, network, and parse failures (F-005 / no-silent-fallback). */
export async function fetchJsonResult<T>(url: string, init?: RequestInit): Promise<FetchJsonResult<T>> {
  try {
    const res = await fetch(url, { ...init, cache: "no-store" });
    const text = await res.text();

    if (!res.ok) {
      let detail = "";
      try {
        const j = JSON.parse(text) as { message?: string };
        if (typeof j?.message === "string" && j.message.trim()) detail = j.message.trim();
      } catch {
        if (text.trim()) detail = text.trim().slice(0, 200);
      }
      return {
        ok: false,
        error: detail ? `HTTP ${res.status}: ${truncateFetchDetail(detail)}` : `HTTP ${res.status}`,
        status: res.status,
      };
    }

    if (!text.trim()) {
      return { ok: false, error: "Empty response body" };
    }

    try {
      return { ok: true, data: JSON.parse(text) as T };
    } catch {
      return { ok: false, error: "Response was not valid JSON" };
    }
  } catch (err) {
    const message = err instanceof Error ? err.message : "Network request failed";
    return { ok: false, error: message };
  }
}

/** Legacy helper: callers lose error detail — prefer {@link fetchJsonResult} for user-facing flows. */
async function fetchJson<T>(url: string, init?: RequestInit): Promise<T | null> {
  const r = await fetchJsonResult<T>(url, init);
  return r.ok ? r.data : null;
}

export type BrainPersonaSpec = {
  name: string;
  description: string;
  default_model: string;
  escalation_model: string | null;
  escalate_if: string[];
  requires_tools: boolean;
  daily_cost_ceiling_usd: number | null;
  confidence_floor: number | null;
  compliance_flagged: boolean;
  owner_channel: string | null;
  mode: "chat" | "task";
};

function getBrainApiRoot() {
  const raw = normalizeBaseUrl(process.env.BRAIN_API_URL);
  if (!raw) return undefined;
  return raw.endsWith("/api/v1") ? raw : `${raw}/api/v1`;
}

export type BrainPersonasFetchResult = {
  personas: BrainPersonaSpec[];
  /** Present when credentials are missing, the request fails, or Brain reports failure — not an empty catalog. */
  error?: string;
};

export async function getBrainPersonas(): Promise<BrainPersonasFetchResult> {
  const apiRoot = getBrainApiRoot();
  const secret = process.env.BRAIN_API_SECRET?.trim();
  if (!apiRoot || !secret) {
    return {
      personas: [],
      error: "Brain not configured — set BRAIN_API_URL and BRAIN_API_SECRET.",
    };
  }
  const data = await fetchJson<{
    success?: boolean;
    data?: { count: number; personas: BrainPersonaSpec[] };
  }>(`${apiRoot}/admin/personas`, {
    headers: { "X-Brain-Secret": secret },
  });
  if (data == null) {
    return {
      personas: [],
      error: "Could not load personas from Brain (request failed or unreachable).",
    };
  }
  if (data.success === false) {
    return {
      personas: [],
      error: "Brain returned an error for the personas list.",
    };
  }
  return { personas: data.data?.personas ?? [] };
}

/** ``GET /api/v1/admin/memory-stats`` — Brain episode aggregates for Overview (never throws). */
export async function getBrainMemoryStats(): Promise<{
  data: BrainMemoryStats | null;
  error?: string;
}> {
  const apiRoot = getBrainApiRoot();
  const secret = process.env.BRAIN_API_SECRET?.trim();
  if (!apiRoot || !secret) {
    return {
      data: null,
      error: "Brain not configured — set BRAIN_API_URL and BRAIN_API_SECRET.",
    };
  }
  const data = await fetchJson<{ success?: boolean; data?: BrainMemoryStats }>(
    `${apiRoot}/admin/memory-stats`,
    { headers: { "X-Brain-Secret": secret } },
  );
  if (data == null) {
    return { data: null, error: "Could not load memory stats from Brain." };
  }
  if (data.success === false) {
    return { data: null, error: "Brain returned an error for memory-stats." };
  }
  return { data: data.data ?? null };
}

/** ``GET /api/v1/admin/persona-dispatch-summary`` */
export async function getBrainPersonaDispatchSummary(): Promise<{
  data: PersonaDispatchSummaryResponse | null;
  error?: string;
}> {
  const apiRoot = getBrainApiRoot();
  const secret = process.env.BRAIN_API_SECRET?.trim();
  if (!apiRoot || !secret) {
    return {
      data: null,
      error: "Brain not configured — set BRAIN_API_URL and BRAIN_API_SECRET.",
    };
  }
  const data = await fetchJson<{
    success?: boolean;
    data?: PersonaDispatchSummaryResponse;
  }>(`${apiRoot}/admin/persona-dispatch-summary`, {
    headers: { "X-Brain-Secret": secret },
  });
  if (data == null) {
    return { data: null, error: "Could not load persona dispatch summary from Brain." };
  }
  if (data.success === false) {
    return { data: null, error: "Brain returned an error for persona-dispatch-summary." };
  }
  return { data: data.data ?? null };
}

/** ``GET /api/v1/admin/operating-score/history`` — daily POS series for charts. */
export async function getBrainOperatingScoreHistory(days = 30): Promise<{
  data: OperatingScoreHistoryResponse | null;
  error?: string;
}> {
  const apiRoot = getBrainApiRoot();
  const secret = process.env.BRAIN_API_SECRET?.trim();
  if (!apiRoot || !secret) {
    return {
      data: null,
      error: "Brain not configured — set BRAIN_API_URL and BRAIN_API_SECRET.",
    };
  }
  const qs = new URLSearchParams({ days: String(days) });
  const data = await fetchJson<{ success?: boolean; data?: OperatingScoreHistoryResponse }>(
    `${apiRoot}/admin/operating-score/history?${qs}`,
    { headers: { "X-Brain-Secret": secret } },
  );
  if (data == null) {
    return { data: null, error: "Could not load operating score history from Brain." };
  }
  if (data.success === false) {
    return { data: null, error: "Brain returned an error for operating-score/history." };
  }
  return { data: data.data ?? null };
}

/** ``GET /api/v1/admin/cost-breakdown`` — token-derived LLM spend estimates. */
export async function getBrainCostBreakdown(days = 30): Promise<{
  data: CostBreakdownResponse | null;
  error?: string;
}> {
  const apiRoot = getBrainApiRoot();
  const secret = process.env.BRAIN_API_SECRET?.trim();
  if (!apiRoot || !secret) {
    return {
      data: null,
      error: "Brain not configured — set BRAIN_API_URL and BRAIN_API_SECRET.",
    };
  }
  const qs = new URLSearchParams({ days: String(days) });
  const data = await fetchJson<{ success?: boolean; data?: CostBreakdownResponse }>(
    `${apiRoot}/admin/cost-breakdown?${qs}`,
    { headers: { "X-Brain-Secret": secret } },
  );
  if (data == null) {
    return { data: null, error: "Could not load cost breakdown from Brain." };
  }
  if (data.success === false) {
    return { data: null, error: "Brain returned an error for cost-breakdown." };
  }
  return { data: data.data ?? null };
}

/** ``GET /api/v1/admin/brain-fill-meter`` — memory tier utilization. */
export async function getBrainFillMeter(): Promise<{
  data: BrainFillMeterResponse | null;
  error?: string;
}> {
  const apiRoot = getBrainApiRoot();
  const secret = process.env.BRAIN_API_SECRET?.trim();
  if (!apiRoot || !secret) {
    return {
      data: null,
      error: "Brain not configured — set BRAIN_API_URL and BRAIN_API_SECRET.",
    };
  }
  const data = await fetchJson<{ success?: boolean; data?: BrainFillMeterResponse }>(
    `${apiRoot}/admin/brain-fill-meter`,
    { headers: { "X-Brain-Secret": secret } },
  );
  if (data == null) {
    return { data: null, error: "Could not load brain fill meter from Brain." };
  }
  if (data.success === false) {
    return { data: null, error: "Brain returned an error for brain-fill-meter." };
  }
  return { data: data.data ?? null };
}

export type N8nMirrorPerJob = {
  key: string;
  enabled: boolean;
  last_run: string | null;
  last_status: string | null;
  success_count_24h: number;
  error_count_24h: number;
};

export type N8nMirrorSchedulerStatus = {
  /** True when Brain no longer registers n8n shadow APScheduler jobs (Track K complete). */
  retired?: boolean;
  message?: string;
  global_enabled: boolean;
  per_job: N8nMirrorPerJob[];
};

/**
 * `GET /api/v1/admin/scheduler/n8n-mirror/status` — shadow registration + 24h run stats.
 * Returns null if Brain is not configured or the request fails.
 */
export async function getN8nMirrorSchedulerStatus(): Promise<N8nMirrorSchedulerStatus | null> {
  const apiRoot = getBrainApiRoot();
  const secret = process.env.BRAIN_API_SECRET?.trim();
  if (!apiRoot || !secret) return null;
  const data = await fetchJson<{
    success?: boolean;
    data?: N8nMirrorSchedulerStatus;
  }>(`${apiRoot}/admin/scheduler/n8n-mirror/status`, {
    headers: { "X-Brain-Secret": secret },
  });
  if (!data?.data) return null;
  return data.data;
}

export async function getN8nWorkflows() {
  const apiRoot = getN8nApiRoot();
  const headers = getN8nHeaders();
  if (!apiRoot || !headers) return [] as N8nWorkflow[];
  const data = await fetchJson<{ data?: N8nWorkflow[] }>(`${apiRoot}/workflows`, {
    headers,
  });
  return data?.data ?? [];
}

export async function getN8nExecutions(limit = 20) {
  const apiRoot = getN8nApiRoot();
  const headers = getN8nHeaders();
  if (!apiRoot || !headers) return [] as N8nExecution[];
  const data = await fetchJson<{ data?: N8nExecution[] }>(`${apiRoot}/executions?limit=${limit}`, {
    headers,
  });
  return data?.data ?? [];
}

export type MissingGithubCredential = "GITHUB_TOKEN";

export type RecentPullRequestsResult = {
  data: PullRequestSummary[];
  missingCred?: MissingGithubCredential;
  /** Token is set but the GitHub request failed or the response shape was unexpected. */
  fetchError?: string;
};

export type RecentCIRunsResult = {
  data: CIRun[];
  missingCred?: MissingGithubCredential;
  fetchError?: string;
};

export async function getRecentPullRequests(limit = 5): Promise<RecentPullRequestsResult> {
  const token = process.env.GITHUB_TOKEN?.trim();
  if (!token) return { data: [], missingCred: "GITHUB_TOKEN" };
  const result = await fetchJsonResult<PullRequestSummary[]>(
    `https://api.github.com/repos/paperwork-labs/paperwork/pulls?state=open&per_page=${limit}`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/vnd.github+json",
      },
    },
  );
  if (!result.ok) return { data: [], fetchError: result.error };
  if (!Array.isArray(result.data)) {
    return {
      data: [],
      fetchError: "GitHub returned an unexpected response (expected a JSON array of pull requests).",
    };
  }
  return { data: result.data };
}

export type BrainPRReview = {
  pr_number: number;
  head_sha: string;
  verdict: "APPROVE" | "COMMENT" | "REQUEST_CHANGES" | string;
  model: string;
  summary: string;
  created_at: string;
};

/**
 * Most recent Brain PR-review episodes, keyed by PR number. Used by the
 * Overview to show a verdict + SHA badge alongside the open PR list.
 *
 * Never throws — a Brain outage must not break the dashboard.
 */
export async function getBrainPRReviews(limit = 50): Promise<Map<number, BrainPRReview>> {
  const apiRoot = getBrainApiRoot();
  const secret = process.env.BRAIN_API_SECRET?.trim();
  if (!apiRoot || !secret) return new Map();
  type RawEpisode = {
    source?: string;
    summary?: string;
    metadata?: { pr_number?: number; head_sha?: string; verdict?: string; model?: string };
    full_context?: string;
    created_at?: string;
  };
  const data = await fetchJson<{ success?: boolean; data?: { episodes?: RawEpisode[] } }>(
    `${apiRoot}/admin/memory/episodes?source_prefix=brain:pr-review&limit=${limit}`,
    { headers: { "X-Brain-Secret": secret } },
  );
  const episodes = data?.data?.episodes ?? [];
  const byPr = new Map<number, BrainPRReview>();
  for (const ep of episodes) {
    const prNum = ep?.metadata?.pr_number;
    if (!prNum) continue;
    const existing = byPr.get(prNum);
    const ts = ep.created_at ? Date.parse(ep.created_at) : 0;
    const existingTs = existing?.created_at ? Date.parse(existing.created_at) : 0;
    if (existing && existingTs >= ts) continue;
    byPr.set(prNum, {
      pr_number: prNum,
      head_sha: ep.metadata?.head_sha ?? "",
      verdict: ep.metadata?.verdict ?? "COMMENT",
      model: ep.metadata?.model ?? "",
      summary: (ep.summary ?? "").slice(0, 200),
      created_at: ep.created_at ?? "",
    });
  }
  return byPr;
}

export type SlackActivityEntry = {
  id: number;
  persona: string;
  channel_id: string;
  summary: string;
  created_at: string;
  model: string;
  persona_pinned: boolean;
};

/**
 * Track C: Brain-originated Slack activity for the Studio overview tile.
 *
 * We pull recent Brain episodes where ``source`` starts with ``brain:slack``
 * and project them into a compact shape for the dashboard. Never throws.
 */
export async function getRecentSlackActivity(limit = 15): Promise<SlackActivityEntry[]> {
  const apiRoot = getBrainApiRoot();
  const secret = process.env.BRAIN_API_SECRET?.trim();
  if (!apiRoot || !secret) return [];
  type RawEpisode = {
    id?: number;
    source?: string;
    persona?: string;
    channel?: string;
    summary?: string;
    metadata?: { pinned?: boolean; persona_pin?: string };
    model_used?: string;
    created_at?: string;
  };
  const data = await fetchJson<{ success?: boolean; data?: { episodes?: RawEpisode[] } }>(
    `${apiRoot}/admin/memory/episodes?source_prefix=brain:slack&limit=${limit}`,
    { headers: { "X-Brain-Secret": secret } },
  );
  const episodes = data?.data?.episodes ?? [];
  return episodes
    .filter((ep) => ep.id != null && ep.persona && ep.persona !== "router")
    .map((ep) => ({
      id: ep.id as number,
      persona: ep.persona as string,
      channel_id: ep.channel ?? "",
      summary: (ep.summary ?? "").slice(0, 200),
      created_at: ep.created_at ?? "",
      model: ep.model_used ?? "",
      persona_pinned: Boolean(ep.metadata?.pinned || ep.metadata?.persona_pin),
    }));
}

export type BrainLearningEpisode = {
  id: number;
  source: string;
  source_ref: string | null;
  channel: string | null;
  persona: string | null;
  product: string | null;
  summary: string;
  importance: number;
  metadata: Record<string, unknown>;
  model_used: string | null;
  tokens_in: number | null;
  tokens_out: number | null;
  user_id: string | null;
  created_at: string | null;
};

export type BrainLearningDecision = {
  id: number;
  persona: string | null;
  summary: string;
  outcome: unknown;
  model_used: string | null;
  tokens_in: number | null;
  tokens_out: number | null;
  created_at: string | null;
  metadata: Record<string, unknown>;
};

export type BrainLearningSparkPoint = {
  date: string;
  episode_count: number;
  decision_count: number;
};

export type BrainLearningSummary = {
  anchor_date: string;
  day_start_utc: string;
  day_end_utc: string;
  counts_by_persona_product: { persona: string | null; product: string | null; episode_count: number }[];
  top_by_importance: BrainLearningEpisode[];
  model_token_totals: { model: string | null; tokens_in: number; tokens_out: number }[];
  totals: { episodes: number; routing_decisions: number; tokens_in: number; tokens_out: number };
  spark: BrainLearningSparkPoint[];
};

/**
 * J2/J3: `GET /api/v1/admin/brain/learning-summary` — aggregates + 14d spark.
 * Returns null if Brain is not configured or the request fails.
 */
export async function getBrainLearningSummary(
  onDate: string | undefined,
  options?: { sparkDays?: number },
): Promise<BrainLearningSummary | null> {
  const apiRoot = getBrainApiRoot();
  const secret = process.env.BRAIN_API_SECRET?.trim();
  if (!apiRoot || !secret) return null;
  const u = new URL(`${apiRoot}/admin/brain/learning-summary`);
  if (onDate) u.searchParams.set("date", onDate);
  u.searchParams.set("spark_days", String(options?.sparkDays ?? 14));
  const data = await fetchJson<{ success?: boolean; data?: BrainLearningSummary }>(u.toString(), {
    headers: { "X-Brain-Secret": secret },
  });
  return data?.data ?? null;
}

/**
 * J2/J3: time-bounded episodes (excludes `model_router` by default).
 */
export async function getBrainLearningEpisodes(params: {
  since: string;
  limit?: number;
  persona?: string;
  product?: string;
}): Promise<BrainLearningEpisode[] | null> {
  const apiRoot = getBrainApiRoot();
  const secret = process.env.BRAIN_API_SECRET?.trim();
  if (!apiRoot || !secret) return null;
  const u = new URL(`${apiRoot}/admin/brain/episodes`);
  u.searchParams.set("since", params.since);
  u.searchParams.set("limit", String(params.limit ?? 50));
  u.searchParams.set("exclude_routing", "true");
  if (params.persona) u.searchParams.set("persona", params.persona);
  if (params.product !== undefined) u.searchParams.set("product", params.product);
  const data = await fetchJson<{
    success?: boolean;
    data?: { episodes?: BrainLearningEpisode[] };
  }>(u.toString(), { headers: { "X-Brain-Secret": secret } });
  if (!data?.data) return null;
  return data.data.episodes ?? [];
}

/** J2/J3: routing decision quality rows (`source=model_router`). */
export async function getBrainLearningDecisions(params: {
  since: string;
  limit?: number;
}): Promise<BrainLearningDecision[] | null> {
  const apiRoot = getBrainApiRoot();
  const secret = process.env.BRAIN_API_SECRET?.trim();
  if (!apiRoot || !secret) return null;
  const u = new URL(`${apiRoot}/admin/brain/decisions`);
  u.searchParams.set("since", params.since);
  u.searchParams.set("limit", String(params.limit ?? 100));
  const data = await fetchJson<{
    success?: boolean;
    data?: { decisions?: BrainLearningDecision[] };
  }>(u.toString(), { headers: { "X-Brain-Secret": secret } });
  if (!data?.data) return null;
  return data.data.decisions ?? [];
}

export type CIRun = {
  id: number;
  name: string;
  status: string;
  conclusion: string | null;
  url: string;
  createdAt: string;
  updatedAt: string;
};

export async function getRecentCIRuns(limit = 10): Promise<RecentCIRunsResult> {
  const token = process.env.GITHUB_TOKEN?.trim();
  if (!token) return { data: [], missingCred: "GITHUB_TOKEN" };
  const result = await fetchJsonResult<{ workflow_runs?: Array<{
    id: number;
    name: string;
    status: string;
    conclusion: string | null;
    html_url: string;
    created_at: string;
    updated_at: string;
  }> }>(
    `https://api.github.com/repos/paperwork-labs/paperwork/actions/runs?per_page=${limit}&branch=main`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/vnd.github+json",
      },
    },
  );
  if (!result.ok) return { data: [], fetchError: result.error };
  const runs = result.data?.workflow_runs;
  if (!Array.isArray(runs)) {
    return {
      data: [],
      fetchError: "GitHub returned an unexpected response (expected workflow_runs array).",
    };
  }
  return {
    data: runs.map((r) => ({
      id: r.id,
      name: r.name,
      status: r.status,
      conclusion: r.conclusion,
      url: r.html_url,
      createdAt: r.created_at,
      updatedAt: r.updated_at,
    })),
  };
}

async function checkWithLatency(
  service: string,
  category: InfraStatus["category"],
  url: string | undefined,
  dashboardUrl: string | null,
  options?: { headers?: Record<string, string>; validateJson?: boolean; consoleUrl?: string | null }
): Promise<InfraStatus> {
  const consoleUrl = options?.consoleUrl ?? null;
  if (!url) {
    return { service, category, configured: false, healthy: false, detail: "Not configured", latencyMs: null, dashboardUrl, consoleUrl };
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 8000);
  try {
    const start = performance.now();
    const response = await fetch(url, {
      method: "GET",
      cache: "no-store",
      signal: controller.signal,
      headers: options?.headers,
    });
    const latencyMs = Math.round(performance.now() - start);

    let detail = response.ok ? "Reachable" : `HTTP ${response.status}`;
    if (!response.ok && service === "LaunchFree API" && url) {
      try {
        const path = new URL(url).pathname || "/";
        detail = `GET ${path} → HTTP ${response.status}`;
      } catch {
        detail = `HTTP ${response.status}`;
      }
    }

    if (response.ok && options?.validateJson) {
      try {
        const json = await response.json();
        if (json.status === "healthy" || json.success === true || json?.data?.status === "ok") {
          const version = json.version ?? json?.data?.version;
          const dbField = json.db_connected;
          const dbBit =
            typeof dbField === "boolean"
              ? ` (db: ${dbField ? "connected" : "disconnected"})`
              : "";
          detail = `Healthy${version ? ` v${version}` : ""}${dbBit}`;
        }
      } catch {
        // JSON parse failed but endpoint is reachable
      }
    }

    return { service, category, configured: true, healthy: response.ok, detail, latencyMs, dashboardUrl, consoleUrl };
  } catch (err) {
    const detail = err instanceof DOMException && err.name === "AbortError" ? "Timeout (8s)" : "Unreachable";
    return { service, category, configured: true, healthy: false, detail, latencyMs: null, dashboardUrl, consoleUrl };
  } finally {
    clearTimeout(timeout);
  }
}

async function checkTokenApi(
  service: string,
  category: InfraStatus["category"],
  url: string,
  token: string | undefined,
  dashboardUrl: string | null,
): Promise<InfraStatus> {
  if (!token) {
    return { service, category, configured: false, healthy: false, detail: "Missing API token", latencyMs: null, dashboardUrl };
  }

  return checkWithLatency(service, category, url, dashboardUrl, {
    headers: { Authorization: `Bearer ${token}` },
  });
}

// Hetzner Cloud probe — counts running servers via the public Cloud API.
// We split this from the n8n probe because they're answering different
// questions: the n8n card says "is the workflow runtime serving traffic",
// the Hetzner card says "is the underlying VPS healthy and how many
// servers do we own". Without a token we still render the card so the
// user has a one-click link to the console; we just say "no probe".
async function checkHetznerCloud(token: string | undefined): Promise<InfraStatus> {
  const dashboardUrl = "https://console.hetzner.cloud";
  if (!token) {
    return {
      service: "Hetzner Cloud",
      category: "ops",
      configured: false,
      healthy: false,
      detail: "HETZNER_API_TOKEN not set — console link only",
      latencyMs: null,
      dashboardUrl,
    };
  }
  const start = Date.now();
  try {
    const res = await fetch("https://api.hetzner.cloud/v1/servers", {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    const latencyMs = Date.now() - start;
    if (!res.ok) {
      return {
        service: "Hetzner Cloud",
        category: "ops",
        configured: true,
        healthy: false,
        detail: `HTTP ${res.status}`,
        latencyMs,
        dashboardUrl,
      };
    }
    const body = (await res.json()) as {
      servers?: Array<{ name: string; status: string }>;
    };
    const servers = body.servers ?? [];
    const running = servers.filter((s) => s.status === "running").length;
    const total = servers.length;
    const detail = total === 0
      ? "0 servers"
      : `${running}/${total} running` +
        (running === total
          ? ""
          : ` — ${servers
              .filter((s) => s.status !== "running")
              .map((s) => `${s.name}:${s.status}`)
              .join(", ")}`);
    return {
      service: "Hetzner Cloud",
      category: "ops",
      configured: true,
      healthy: running === total && total > 0,
      detail,
      latencyMs,
      dashboardUrl,
    };
  } catch (err) {
    return {
      service: "Hetzner Cloud",
      category: "ops",
      configured: true,
      healthy: false,
      detail: err instanceof Error ? err.message : "Hetzner probe failed",
      latencyMs: null,
      dashboardUrl,
    };
  }
}

// Slack Web API returns HTTP 200 with { ok: false } on auth failure, so the
// generic token probe reports green falsely. Use auth.test and parse the body.
async function checkSlackBot(token: string | undefined): Promise<InfraStatus> {
  const dashboardUrl = "https://app.slack.com/manage";
  if (!token) {
    return {
      service: "Slack (paperwork bot)",
      category: "ops",
      configured: false,
      healthy: false,
      detail: "SLACK_BOT_TOKEN not set",
      latencyMs: null,
      dashboardUrl,
    };
  }
  const start = Date.now();
  try {
    const res = await fetch("https://slack.com/api/auth.test", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/x-www-form-urlencoded",
      },
      cache: "no-store",
    });
    const latencyMs = Date.now() - start;
    const body = (await res.json()) as {
      ok?: boolean;
      error?: string;
      team?: string;
      user?: string;
      bot_id?: string;
    };
    if (!body.ok) {
      return {
        service: "Slack (paperwork bot)",
        category: "ops",
        configured: true,
        healthy: false,
        detail: `auth.test failed: ${body.error ?? "unknown"}`,
        latencyMs,
        dashboardUrl,
      };
    }
    return {
      service: "Slack (paperwork bot)",
      category: "ops",
      configured: true,
      healthy: true,
      detail: `Bot ${body.user ?? "?"} @ ${body.team ?? "?"} (${body.bot_id ?? ""})`,
      latencyMs,
      dashboardUrl,
    };
  } catch (err) {
    return {
      service: "Slack (paperwork bot)",
      category: "ops",
      configured: true,
      healthy: false,
      detail: err instanceof Error ? err.message : "Slack probe failed",
      latencyMs: null,
      dashboardUrl,
    };
  }
}

/**
 * Full infrastructure view: dynamic per-service rows from Render + Vercel APIs,
 * plus optional synthetic HTTP/ops checks (n8n, Slack, etc.).
 * See Q2 Tech Debt Convergence (Track I4) — F-6–style build drift is visible via provider state.
 */
export async function getInfrastructureView(): Promise<InfrastructureView> {
  const n8nUrl = normalizeBaseUrl(process.env.N8N_API_URL || process.env.N8N_HOST);
  const socialUrl = normalizeBaseUrl(process.env.POSTIZ_URL) || "https://social.paperworklabs.com";
  const renderToken = process.env.RENDER_API_KEY?.trim();
  const vercelToken = process.env.VERCEL_API_TOKEN?.trim();
  const teamId = process.env.VERCEL_TEAM_ID?.trim() || process.env.VERCEL_ORG_ID?.trim();
  const vercelTeamSlug = process.env.VERCEL_TEAM_SLUG?.trim() || "paperwork-labs";
  const neonApiKey = process.env.NEON_API_KEY?.trim();
  const upstashUrl = process.env.UPSTASH_REDIS_REST_URL?.trim();
  const upstashToken = process.env.UPSTASH_REDIS_REST_TOKEN?.trim();
  const slackToken = process.env.SLACK_BOT_TOKEN?.trim();
  const hetznerToken = process.env.HETZNER_API_TOKEN?.trim();

  const { rows: platformRows, partial: platformPartial, platformSummary } =
    await collectRenderAndVercelProbes(renderToken, vercelToken, teamId, vercelTeamSlug);

  const checks: Promise<InfraStatus>[] = [
    // Synthetic reachability (complements provider truth above).
    checkWithLatency(
      "Brain API (HTTP /health)",
      "core",
      `${normalizeBaseUrl(process.env.BRAIN_API_URL) || "https://brain-api-zo5t.onrender.com"}/health`,
      "https://dashboard.render.com",
      { validateJson: true },
    ),
    checkWithLatency(
      "FileFree API (HTTP /health)",
      "core",
      `${normalizeBaseUrl(process.env.FILEFREE_API_URL) || "https://api.filefree.ai"}/health`,
      "https://dashboard.render.com",
      { validateJson: true },
    ),
    checkWithLatency(
      "AxiomFolio API (HTTP /health)",
      "core",
      `${normalizeBaseUrl(process.env.AXIOMFOLIO_API_URL) || "https://axiomfolio-api-02ei.onrender.com"}/health`,
      "https://dashboard.render.com",
      { validateJson: true },
    ),
    checkWithLatency(
      "LaunchFree API",
      "core",
      `${normalizeBaseUrl(process.env.LAUNCHFREE_API_URL) || "https://launchfree-api.onrender.com"}/health`,
      "https://dashboard.render.com",
      { validateJson: true },
    ),
    checkWithLatency(
      "Studio (public URL)",
      "frontend",
      `${normalizeBaseUrl(process.env.STUDIO_URL) || "https://www.paperworklabs.com"}/`,
      `https://vercel.com/${vercelTeamSlug}/studio`,
    ),
    checkWithLatency(
      "AxiomFolio static (public URL)",
      "frontend",
      `${normalizeBaseUrl(process.env.AXIOMFOLIO_WEB_URL) || "https://axiomfolio.paperworklabs.com"}/`,
      "https://dashboard.render.com",
    ),
    checkWithLatency(
      "FileFree frontend",
      "frontend",
      `${normalizeBaseUrl(process.env.FILEFREE_URL) || "https://filefree.ai"}/`,
      `https://vercel.com/${vercelTeamSlug}/filefree`,
    ),
    checkWithLatency(
      "LaunchFree frontend",
      "frontend",
      `${normalizeBaseUrl(process.env.LAUNCHFREE_URL) || "https://launchfree.ai"}/`,
      `https://vercel.com/${vercelTeamSlug}/launchfree`,
    ),
    checkWithLatency(
      "Distill frontend",
      "frontend",
      `${normalizeBaseUrl(process.env.DISTILL_URL) || "https://distill.paperworklabs.com"}/`,
      `https://vercel.com/${vercelTeamSlug}/distill`,
    ),
    checkWithLatency(
      "n8n (Hetzner)",
      "ops",
      n8nUrl,
      "https://n8n.paperworklabs.com",
      { consoleUrl: "https://console.hetzner.cloud" },
    ),
    checkHetznerCloud(hetznerToken),
    checkWithLatency("Postiz", "ops", socialUrl, "https://social.paperworklabs.com"),
    checkTokenApi("Neon", "data", "https://console.neon.tech/api/v2/projects", neonApiKey, "https://console.neon.tech"),
  ];

  checks.push(checkSlackBot(slackToken));

  if (upstashUrl && upstashToken) {
    checks.push(
      checkWithLatency(
        "Upstash Redis",
        "cache",
        `${upstashUrl}/ping`,
        "https://console.upstash.com",
        { headers: { Authorization: `Bearer ${upstashToken}` } },
      ),
    );
  } else {
    checks.push(
      Promise.resolve({
        service: "Upstash Redis",
        category: "cache" as const,
        configured: false,
        healthy: false,
        detail: "Not configured",
        latencyMs: null,
        dashboardUrl: "https://console.upstash.com",
      }),
    );
  }

  const other = await Promise.all(checks);
  return {
    services: [...platformRows, ...other],
    platformSummary,
    platformPartial,
  };
}

export async function getInfrastructureStatus(): Promise<InfraStatus[]> {
  return (await getInfrastructureView()).services;
}
