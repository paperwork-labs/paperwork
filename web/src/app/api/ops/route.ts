import { NextResponse } from "next/server";

interface ServiceCheck {
  name: string;
  url: string;
  dashboardUrl: string;
  accessHint: string;
  status: "healthy" | "degraded" | "down" | "unknown";
  latencyMs: number | null;
  details?: Record<string, unknown>;
  checkedAt: string;
  category: "core" | "ops" | "analytics" | "ci";
}

interface N8nWorkflow {
  id: string;
  name: string;
  active: boolean;
  updatedAt: string;
}

interface CIRun {
  name: string;
  conclusion: string | null;
  status: string;
  updatedAt: string;
  url: string;
}

interface OpsResponse {
  services: ServiceCheck[];
  workflows: N8nWorkflow[];
  ciRuns: CIRun[];
  checkedAt: string;
}

const TIMEOUT_MS = 8000;

const PRODUCTION_SERVICES: {
  name: string;
  url: string;
  dashboardUrl: string;
  accessHint: string;
  category: ServiceCheck["category"];
  parseDetails?: (data: unknown) => Record<string, unknown>;
}[] = [
  {
    name: "Render API",
    url: "https://api.filefree.tax/health",
    dashboardUrl: "https://dashboard.render.com",
    accessHint: "Render dashboard > filefree-api service. Manage deploys, env vars, logs.",
    category: "core",
    parseDetails: (data) => {
      const d = data as Record<string, unknown>;
      const inner = d?.data as Record<string, unknown> | undefined;
      return {
        dbConnected: inner?.db_connected,
        redisConnected: inner?.redis_connected,
        version: inner?.version,
        status: inner?.status,
      };
    },
  },
  {
    name: "Vercel Frontend",
    url: "https://filefree.tax",
    dashboardUrl: "https://vercel.com/dashboard",
    accessHint: "Vercel dashboard > filefree project. Auto-deploys from main.",
    category: "core",
  },
  {
    name: "n8n (Agents)",
    url: "https://n8n.filefree.tax/healthz",
    dashboardUrl: "https://n8n.filefree.tax",
    accessHint: "Login with N8N_USER / N8N_PASSWORD from Hetzner env. Manage AI agent workflows.",
    category: "ops",
  },
  {
    name: "Postiz (Social)",
    url: "https://social.filefree.tax",
    dashboardUrl: "https://social.filefree.tax",
    accessHint: "Login, then connect TikTok / IG / X / YouTube accounts to start posting.",
    category: "ops",
  },
  {
    name: "PostHog (Analytics)",
    url: "https://us.i.posthog.com/decide?v=3",
    dashboardUrl: "https://us.posthog.com",
    accessHint: "Login to view funnels, events, and dashboards. API key in web/.env.production.",
    category: "analytics",
    parseDetails: () => ({ raw: "reachable" }),
  },
];

async function checkService(
  service: (typeof PRODUCTION_SERVICES)[number],
): Promise<ServiceCheck> {
  const start = Date.now();
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), TIMEOUT_MS);

    const res = await fetch(service.url, {
      signal: controller.signal,
      cache: "no-store",
      headers: { "User-Agent": "FileFree-Ops/1.0" },
    });
    clearTimeout(timeout);

    const latencyMs = Date.now() - start;

    const base = {
      name: service.name,
      url: service.url,
      dashboardUrl: service.dashboardUrl,
      accessHint: service.accessHint,
      category: service.category,
    };

    if (!res.ok && res.status >= 500) {
      return {
        ...base,
        status: "down" as const,
        latencyMs,
        details: { httpStatus: res.status },
        checkedAt: new Date().toISOString(),
      };
    }

    if (!res.ok) {
      return {
        ...base,
        status: "degraded" as const,
        latencyMs,
        details: { httpStatus: res.status },
        checkedAt: new Date().toISOString(),
      };
    }

    let details: Record<string, unknown> = {};
    try {
      const json = await res.json();
      details = service.parseDetails ? service.parseDetails(json) : {};
    } catch {
      // Non-JSON response is fine for health checks (e.g., Vercel returns HTML)
    }

    return {
      ...base,
      status: "healthy" as const,
      latencyMs,
      details,
      checkedAt: new Date().toISOString(),
    };
  } catch (err) {
    return {
      name: service.name,
      url: service.url,
      dashboardUrl: service.dashboardUrl,
      accessHint: service.accessHint,
      category: service.category,
      status: "down" as const,
      latencyMs: Date.now() - start,
      details: {
        error:
          err instanceof Error
            ? err.name === "AbortError"
              ? "Timeout (>8s)"
              : err.message
            : "Unknown error",
      },
      checkedAt: new Date().toISOString(),
    };
  }
}

async function fetchN8nWorkflows(): Promise<N8nWorkflow[]> {
  const n8nApiKey = process.env.N8N_API_KEY;
  if (!n8nApiKey) return [];

  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), TIMEOUT_MS);

    const res = await fetch("https://n8n.filefree.tax/api/v1/workflows", {
      headers: { "X-N8N-API-KEY": n8nApiKey },
      signal: controller.signal,
      cache: "no-store",
    });
    clearTimeout(timeout);

    if (!res.ok) return [];

    const json = await res.json();
    const workflows = json.data ?? json;

    if (!Array.isArray(workflows)) return [];

    return workflows.map((w: Record<string, unknown>) => ({
      id: String(w.id ?? ""),
      name: String(w.name ?? "Unknown"),
      active: Boolean(w.active),
      updatedAt: String(w.updatedAt ?? w.updated_at ?? ""),
    }));
  } catch {
    return [];
  }
}

async function fetchGitHubCI(): Promise<CIRun[]> {
  const ghToken = process.env.GITHUB_TOKEN;
  if (!ghToken) return [];

  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), TIMEOUT_MS);

    const res = await fetch(
      "https://api.github.com/repos/sankalp404/fileFree/actions/runs?per_page=5&branch=main",
      {
        headers: {
          Authorization: `Bearer ${ghToken}`,
          Accept: "application/vnd.github+json",
        },
        signal: controller.signal,
        cache: "no-store",
      },
    );
    clearTimeout(timeout);

    if (!res.ok) return [];

    const json = await res.json();
    const runs = json.workflow_runs;
    if (!Array.isArray(runs)) return [];

    return runs.slice(0, 5).map((r: Record<string, unknown>) => ({
      name: String(r.name ?? "Unknown"),
      conclusion: r.conclusion as string | null,
      status: String(r.status ?? "unknown"),
      updatedAt: String(r.updated_at ?? ""),
      url: String(r.html_url ?? ""),
    }));
  } catch {
    return [];
  }
}

export async function GET() {
  const [services, workflows, ciRuns] = await Promise.all([
    Promise.all(PRODUCTION_SERVICES.map(checkService)),
    fetchN8nWorkflows(),
    fetchGitHubCI(),
  ]);

  const response: OpsResponse = {
    services,
    workflows,
    ciRuns,
    checkedAt: new Date().toISOString(),
  };

  return NextResponse.json(response);
}
