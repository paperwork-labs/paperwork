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

function getN8nAuthHeader() {
  const raw = process.env.N8N_BASIC_AUTH;
  if (!raw) return undefined;
  return `Basic ${Buffer.from(raw).toString("base64")}`;
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
  const apiUrl = process.env.N8N_API_URL;
  const auth = getN8nAuthHeader();
  if (!apiUrl || !auth) return [] as N8nWorkflow[];
  const data = await fetchJson<{ data?: N8nWorkflow[] }>(`${apiUrl}/api/v1/workflows`, {
    headers: { Authorization: auth },
  });
  return data?.data ?? [];
}

export async function getN8nExecutions(limit = 20) {
  const apiUrl = process.env.N8N_API_URL;
  const auth = getN8nAuthHeader();
  if (!apiUrl || !auth) return [] as N8nExecution[];
  const data = await fetchJson<{ data?: N8nExecution[] }>(
    `${apiUrl}/api/v1/executions?limit=${limit}`,
    { headers: { Authorization: auth } },
  );
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

