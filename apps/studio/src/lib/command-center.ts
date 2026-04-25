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

export type InfraStatus = {
  service: string;
  category: "core" | "frontend" | "ops" | "data" | "cache" | "hosting";
  configured: boolean;
  healthy: boolean;
  detail: string;
  latencyMs: number | null;
  dashboardUrl: string | null;
};

export type WorkflowMeta = {
  model: string | null;
  costPerRun: string;
  trigger: string;
  role: string;
  deviation?: string;
};

// Source: docs/AI_MODEL_REGISTRY.md + infra/hetzner/workflows/*.json
export const WORKFLOW_META: Record<string, WorkflowMeta> = {
  "Agent Thread Handler": {
    model: "gpt-4o-mini",
    costPerRun: "~$0.002",
    trigger: "Slack webhook",
    role: "Intern",
  },
  "EA Daily Briefing": {
    model: "gpt-4o-mini",
    costPerRun: "~$0.003",
    trigger: "Cron 7am PT",
    role: "Intern",
  },
  "EA Weekly Plan": {
    model: "gpt-4o-mini",
    costPerRun: "~$0.005",
    trigger: "Cron Sun 6pm PT",
    role: "Intern",
  },
  "PR Summary": {
    model: "gpt-4o-mini",
    costPerRun: "~$0.001",
    trigger: "GitHub webhook",
    role: "Intern",
  },
  "Decision Logger": {
    model: null,
    costPerRun: "$0",
    trigger: "Slack webhook",
    role: "No AI",
  },
  "Social Content Generator": {
    model: "gpt-4o",
    costPerRun: "~$0.05",
    trigger: "POST webhook",
    role: "Creative Director",
  },
  "Growth Content Writer": {
    model: "gpt-4o",
    costPerRun: "~$0.05",
    trigger: "POST webhook",
    role: "Creative Director",
  },
  "Partnership Outreach Drafter": {
    model: "gpt-4o",
    costPerRun: "~$0.03",
    trigger: "POST webhook",
    role: "Creative Director",
  },
  "CPA Tax Review": {
    model: "gpt-4o",
    costPerRun: "~$0.04",
    trigger: "POST webhook",
    role: "Creative Director",
    deviation: "Should be Claude Sonnet (compliance)",
  },
  "QA Security Scan": {
    model: "gpt-4o",
    costPerRun: "~$0.04",
    trigger: "POST webhook",
    role: "Creative Director",
    deviation: "Should be Claude Sonnet (code/security)",
  },
  "Weekly Strategy Check-in": {
    model: "gpt-4o",
    costPerRun: "~$0.04",
    trigger: "Cron Mon 9am PT",
    role: "Creative Director",
  },
  "Sprint Kickoff": {
    model: "gpt-4o",
    costPerRun: "~$0.04",
    trigger: "Cron Mon 7am PT",
    role: "Creative Director",
  },
  "Sprint Close": {
    model: "gpt-4o",
    costPerRun: "~$0.04",
    trigger: "Cron Fri 9pm PT",
    role: "Creative Director",
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

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T | null> {
  try {
    const res = await fetch(url, { ...init, cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
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

export async function getBrainPersonas(): Promise<BrainPersonaSpec[]> {
  const apiRoot = getBrainApiRoot();
  const secret = process.env.BRAIN_API_SECRET?.trim();
  if (!apiRoot || !secret) return [];
  const data = await fetchJson<{
    success?: boolean;
    data?: { count: number; personas: BrainPersonaSpec[] };
  }>(`${apiRoot}/admin/personas`, {
    headers: { "X-Brain-Secret": secret },
  });
  return data?.data?.personas ?? [];
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

export async function getRecentPullRequests(limit = 5) {
  const token = process.env.GITHUB_TOKEN;
  if (!token) return [];
  const data = await fetchJson<PullRequestSummary[]>(
    `https://api.github.com/repos/paperwork-labs/paperwork/pulls?state=open&per_page=${limit}`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/vnd.github+json",
      },
    },
  );
  return data ?? [];
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

export type CIRun = {
  id: number;
  name: string;
  status: string;
  conclusion: string | null;
  url: string;
  createdAt: string;
  updatedAt: string;
};

export async function getRecentCIRuns(limit = 10): Promise<CIRun[]> {
  const token = process.env.GITHUB_TOKEN;
  if (!token) return [];
  const data = await fetchJson<{ workflow_runs?: Array<{
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
  return (data?.workflow_runs ?? []).map((r) => ({
    id: r.id,
    name: r.name,
    status: r.status,
    conclusion: r.conclusion,
    url: r.html_url,
    createdAt: r.created_at,
    updatedAt: r.updated_at,
  }));
}

async function checkWithLatency(
  service: string,
  category: InfraStatus["category"],
  url: string | undefined,
  dashboardUrl: string | null,
  options?: { headers?: Record<string, string>; validateJson?: boolean }
): Promise<InfraStatus> {
  if (!url) {
    return { service, category, configured: false, healthy: false, detail: "Not configured", latencyMs: null, dashboardUrl };
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

    return { service, category, configured: true, healthy: response.ok, detail, latencyMs, dashboardUrl };
  } catch (err) {
    const detail = err instanceof DOMException && err.name === "AbortError" ? "Timeout (8s)" : "Unreachable";
    return { service, category, configured: true, healthy: false, detail, latencyMs: null, dashboardUrl };
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

export async function getInfrastructureStatus(): Promise<InfraStatus[]> {
  const n8nUrl = normalizeBaseUrl(process.env.N8N_API_URL || process.env.N8N_HOST);
  const socialUrl = normalizeBaseUrl(process.env.POSTIZ_URL) || "https://social.paperworklabs.com";
  const renderToken = process.env.RENDER_API_KEY?.trim();
  const vercelToken = process.env.VERCEL_API_TOKEN?.trim();
  const neonApiKey = process.env.NEON_API_KEY?.trim();
  const upstashUrl = process.env.UPSTASH_REDIS_REST_URL?.trim();
  const upstashToken = process.env.UPSTASH_REDIS_REST_TOKEN?.trim();
  const slackToken = process.env.SLACK_BOT_TOKEN?.trim();

  const checks: Promise<InfraStatus>[] = [
    // Core services
    checkWithLatency(
      "Brain API",
      "core",
      `${normalizeBaseUrl(process.env.BRAIN_API_URL) || "https://brain-api-zo5t.onrender.com"}/health`,
      "https://dashboard.render.com/web/srv-d74f3cmuk2gs73a4013g",
      { validateJson: true },
    ),
    checkWithLatency(
      "FileFree API",
      "core",
      `${normalizeBaseUrl(process.env.FILEFREE_API_URL) || "https://api.filefree.ai"}/health`,
      "https://dashboard.render.com/web/srv-d70o3jvkijhs73a0ee7g",
      { validateJson: true },
    ),
    checkWithLatency(
      "AxiomFolio API",
      "core",
      `${normalizeBaseUrl(process.env.AXIOMFOLIO_API_URL) || "https://axiomfolio-api-02ei.onrender.com"}/health`,
      "https://dashboard.render.com/web/srv-d7lg0o77f7vs73b2k7m0",
      { validateJson: true },
    ),
    checkWithLatency(
      "LaunchFree API",
      "core",
      `${normalizeBaseUrl(process.env.LAUNCHFREE_API_URL) || "https://launchfree-api.onrender.com"}/health`,
      "https://dashboard.render.com",
      { validateJson: true },
    ),

    // Frontends
    checkWithLatency(
      "Studio (Vercel)",
      "frontend",
      `${normalizeBaseUrl(process.env.STUDIO_URL) || "https://www.paperworklabs.com"}/`,
      "https://vercel.com/paperwork-labs/studio",
    ),
    checkWithLatency(
      "AxiomFolio frontend (Vite)",
      "frontend",
      `${normalizeBaseUrl(process.env.AXIOMFOLIO_WEB_URL) || "https://axiomfolio.paperworklabs.com"}/`,
      "https://dashboard.render.com/static/srv-d7lg0dv7f7vs73b2k1u0",
    ),
    checkWithLatency(
      "FileFree frontend",
      "frontend",
      `${normalizeBaseUrl(process.env.FILEFREE_URL) || "https://filefree.ai"}/`,
      "https://vercel.com/paperwork-labs/filefree",
    ),
    checkWithLatency(
      "LaunchFree frontend",
      "frontend",
      `${normalizeBaseUrl(process.env.LAUNCHFREE_URL) || "https://launchfree.ai"}/`,
      "https://vercel.com/paperwork-labs/launchfree",
    ),
    checkWithLatency(
      "Distill frontend",
      "frontend",
      `${normalizeBaseUrl(process.env.DISTILL_URL) || "https://distill.paperworklabs.com"}/`,
      "https://vercel.com/paperwork-labs/distill",
    ),

    checkWithLatency(
      "Hetzner VPS (n8n)",
      "ops",
      n8nUrl,
      "https://n8n.paperworklabs.com",
    ),
    checkWithLatency(
      "Postiz",
      "ops",
      socialUrl,
      "https://social.paperworklabs.com",
    ),

    // Provider APIs
    checkTokenApi("Render", "hosting", "https://api.render.com/v1/services", renderToken, "https://dashboard.render.com"),
    // Use /v2/user (always accessible to any valid token) instead of /v9/projects
    // which 403s for team-scoped tokens without a ?teamId= query param.
    checkTokenApi("Vercel", "hosting", "https://api.vercel.com/v2/user", vercelToken, "https://vercel.com/paperwork-labs"),
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
      )
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
      })
    );
  }

  return Promise.all(checks);
}
