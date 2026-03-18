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
        Authorization: `token ${token}`,
        Accept: "application/vnd.github+json",
      },
    },
  );
  return data ?? [];
}

