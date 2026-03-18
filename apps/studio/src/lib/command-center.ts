type N8nWorkflow = {
  id: string;
  name: string;
  active: boolean;
};

type N8nExecution = {
  id: string;
  finished: boolean;
  mode: string;
  startedAt?: string;
  stoppedAt?: string;
  workflowId?: string;
};

export type InfraStatus = {
  service: string;
  configured: boolean;
  healthy: boolean;
  detail: string;
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
  const data = await fetchJson<Array<{ number: number; title: string; html_url: string }>>(
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

async function checkPublicUrl(
  service: string,
  url: string | undefined
): Promise<InfraStatus> {
  if (!url) {
    return { service, configured: false, healthy: false, detail: "Missing URL" };
  }

  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 8000);
    const response = await fetch(url, { method: "GET", cache: "no-store", signal: controller.signal });
    clearTimeout(timeout);
    return {
      service,
      configured: true,
      healthy: response.ok,
      detail: response.ok ? "Reachable" : `HTTP ${response.status}`,
    };
  } catch (err) {
    const detail = err instanceof DOMException && err.name === "AbortError" ? "Timeout (8s)" : "Unreachable";
    return { service, configured: true, healthy: false, detail };
  }
}

async function checkTokenBackedApi(
  service: string,
  url: string,
  token: string | undefined
): Promise<InfraStatus> {
  if (!token) {
    return {
      service,
      configured: false,
      healthy: false,
      detail: "Missing API token",
    };
  }

  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 8000);
    const response = await fetch(url, {
      cache: "no-store",
      headers: { Authorization: `Bearer ${token}` },
      signal: controller.signal,
    });
    clearTimeout(timeout);
    return {
      service,
      configured: true,
      healthy: response.ok,
      detail: response.ok ? "API reachable" : `HTTP ${response.status}`,
    };
  } catch (err) {
    const detail = err instanceof DOMException && err.name === "AbortError" ? "Timeout (8s)" : "API unreachable";
    return { service, configured: true, healthy: false, detail };
  }
}

export async function getInfrastructureStatus() {
  const n8nUrl = normalizeBaseUrl(process.env.N8N_API_URL || process.env.N8N_HOST);
  const socialUrl = normalizeBaseUrl(process.env.POSTIZ_URL) || "https://social.paperworklabs.com";
  const renderToken = process.env.RENDER_API_KEY?.trim();
  const vercelToken = process.env.VERCEL_TOKEN?.trim();
  const neonApiKey = process.env.NEON_API_KEY?.trim();
  const upstashUrl = process.env.UPSTASH_REDIS_REST_URL?.trim();
  const upstashToken = process.env.UPSTASH_REDIS_REST_TOKEN?.trim();

  const checks: Promise<InfraStatus>[] = [
    checkPublicUrl("n8n", n8nUrl),
    checkPublicUrl("Postiz", socialUrl),
    checkTokenBackedApi("Render", "https://api.render.com/v1/services", renderToken),
    checkTokenBackedApi("Vercel", "https://api.vercel.com/v9/projects", vercelToken),
    checkTokenBackedApi("Neon", "https://console.neon.tech/api/v2/projects", neonApiKey),
  ];

  if (upstashUrl && upstashToken) {
    checks.push(
      checkTokenBackedApi("Upstash Redis", `${upstashUrl}/ping`, upstashToken)
    );
  } else {
    checks.push(
      Promise.resolve({
        service: "Upstash Redis",
        configured: false,
        healthy: false,
        detail: "Missing REST URL or token",
      })
    );
  }

  return Promise.all(checks);
}

