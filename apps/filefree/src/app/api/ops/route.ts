import { NextResponse } from "next/server";
import { serverConfig } from "@/lib/server-config";
import type { ServiceCheck, N8nWorkflow, CIRun, OpsData } from "@/types/ops";

const TIMEOUT_MS = 8000;

function getProductionServices(): {
  name: string;
  url: string;
  dashboardUrl: string;
  accessHint: string;
  category: ServiceCheck["category"];
  parseDetails?: (data: unknown) => Record<string, unknown>;
}[] {
  const n8nHost = serverConfig.N8N_HOST;
  const postizHost = serverConfig.POSTIZ_HOST;

  return [
    {
      name: "Render API",
      url: "https://api.filefree.ai/health",
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
      url: "https://filefree.ai",
      dashboardUrl: "https://vercel.com/dashboard",
      accessHint: "Vercel dashboard > filefree project. Auto-deploys from main.",
      category: "core",
    },
    {
      name: "n8n (Agents)",
      url: `${n8nHost}/healthz`,
      dashboardUrl: n8nHost,
      accessHint: "Login with N8N_USER / N8N_PASSWORD from Hetzner env. Manage AI agent workflows.",
      category: "ops",
    },
    {
      name: "Postiz (Social)",
      url: postizHost,
      dashboardUrl: postizHost,
      accessHint: "Login, then connect TikTok / IG / X / YouTube accounts to start posting.",
      category: "ops",
    },
    {
      name: "PostHog (Analytics)",
      url: "https://us.i.posthog.com/decide?v=3",
      dashboardUrl: "https://us.posthog.com",
      accessHint: "Login to view funnels, events, and dashboards. API key in Vercel dashboard (prod) or .env.local (dev).",
      category: "analytics",
      parseDetails: () => ({ raw: "reachable" }),
    },
  ];
}

type ProductionService = ReturnType<typeof getProductionServices>[number];

async function checkService(
  service: ProductionService,
): Promise<ServiceCheck> {
  const start = Date.now();
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), TIMEOUT_MS);

  try {
    const res = await fetch(service.url, {
      signal: controller.signal,
      cache: "no-store",
      headers: { "User-Agent": "FileFree-Ops/1.0" },
    });

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
  } finally {
    clearTimeout(timeout);
  }
}

async function fetchN8nWorkflows(): Promise<N8nWorkflow[]> {
  const n8nApiKey = serverConfig.N8N_API_KEY;
  if (!n8nApiKey) return [];

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), TIMEOUT_MS);

  try {
    const n8nHost = serverConfig.N8N_HOST;
    const res = await fetch(`${n8nHost}/api/v1/workflows`, {
      headers: { "X-N8N-API-KEY": n8nApiKey },
      signal: controller.signal,
      cache: "no-store",
    });

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
  } finally {
    clearTimeout(timeout);
  }
}

async function fetchGitHubCI(): Promise<CIRun[]> {
  const ghToken = serverConfig.GITHUB_TOKEN;
  if (!ghToken) return [];

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), TIMEOUT_MS);

  try {
    const res = await fetch(
      "https://api.github.com/repos/paperwork-labs/paperwork/actions/runs?per_page=5&branch=main",
      {
        headers: {
          Authorization: `Bearer ${ghToken}`,
          Accept: "application/vnd.github+json",
        },
        signal: controller.signal,
        cache: "no-store",
      },
    );

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
  } finally {
    clearTimeout(timeout);
  }
}

const ADMIN_EMAILS = (process.env.ADMIN_EMAILS ?? "").split(",").map((e) => e.trim().toLowerCase()).filter(Boolean);
const OPS_API_KEY = process.env.OPS_API_KEY;

export async function GET(req: Request) {
  if (process.env.NODE_ENV === "production") {
    const authHeader = req.headers.get("authorization");
    if (OPS_API_KEY && authHeader === `Bearer ${OPS_API_KEY}`) {
      // API key auth passes
    } else if (ADMIN_EMAILS.length > 0) {
      const cookieHeader = req.headers.get("cookie") ?? "";
      const sessionToken = cookieHeader.split(";").map((c) => c.trim()).find((c) => c.startsWith("session="))?.split("=")[1];
      if (!sessionToken) {
        return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
      }
    } else {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }
  }

  const [services, workflows, ciRuns] = await Promise.all([
    Promise.all(getProductionServices().map(checkService)),
    fetchN8nWorkflows(),
    fetchGitHubCI(),
  ]);

  const response: OpsData = {
    services,
    workflows,
    ciRuns,
    checkedAt: new Date().toISOString(),
  };

  return NextResponse.json(response);
}
