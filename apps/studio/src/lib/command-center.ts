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
  category: "core" | "ops" | "data" | "cache" | "hosting";
  configured: boolean;
  healthy: boolean;
  detail: string;
  latencyMs: number | null;
  dashboardUrl: string | null;
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

  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 8000);
    const start = performance.now();
    const response = await fetch(url, {
      method: "GET",
      cache: "no-store",
      signal: controller.signal,
      headers: options?.headers,
    });
    const latencyMs = Math.round(performance.now() - start);
    clearTimeout(timeout);

    let detail = response.ok ? "Reachable" : `HTTP ${response.status}`;

    if (response.ok && options?.validateJson) {
      try {
        const json = await response.json();
        if (json.status === "healthy") {
          detail = `Healthy (db: ${json.db_connected ? "connected" : "disconnected"})`;
        }
      } catch {
        // JSON parse failed but endpoint is reachable
      }
    }

    return { service, category, configured: true, healthy: response.ok, detail, latencyMs, dashboardUrl };
  } catch (err) {
    const detail = err instanceof DOMException && err.name === "AbortError" ? "Timeout (8s)" : "Unreachable";
    return { service, category, configured: true, healthy: false, detail, latencyMs: null, dashboardUrl };
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

export async function getInfrastructureStatus(): Promise<InfraStatus[]> {
  const n8nUrl = normalizeBaseUrl(process.env.N8N_API_URL || process.env.N8N_HOST);
  const socialUrl = normalizeBaseUrl(process.env.POSTIZ_URL) || "https://social.paperworklabs.com";
  const renderToken = process.env.RENDER_API_KEY?.trim();
  const vercelToken = process.env.VERCEL_API_TOKEN?.trim();
  const neonApiKey = process.env.NEON_API_KEY?.trim();
  const upstashUrl = process.env.UPSTASH_REDIS_REST_URL?.trim();
  const upstashToken = process.env.UPSTASH_REDIS_REST_TOKEN?.trim();

  const checks: Promise<InfraStatus>[] = [
    // Core services
    checkWithLatency(
      "FileFree API",
      "core",
      "https://api.filefree.tax/health",
      "https://dashboard.render.com",
      { validateJson: true },
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
    checkTokenApi("Vercel", "hosting", "https://api.vercel.com/v9/projects", vercelToken, "https://vercel.com/paperwork-labs"),
    checkTokenApi("Neon", "data", "https://console.neon.tech/api/v2/projects", neonApiKey, "https://console.neon.tech"),
  ];

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
