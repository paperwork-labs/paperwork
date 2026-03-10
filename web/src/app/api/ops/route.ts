import { NextResponse } from "next/server";

interface ServiceCheck {
  name: string;
  status: "healthy" | "degraded" | "down" | "unknown";
  latencyMs: number | null;
  details?: Record<string, unknown>;
  checkedAt: string;
}

interface N8nWorkflow {
  id: string;
  name: string;
  active: boolean;
  updatedAt: string;
}

interface OpsResponse {
  services: ServiceCheck[];
  workflows: N8nWorkflow[];
  checkedAt: string;
}

const TIMEOUT_MS = 5000;

async function checkService(
  name: string,
  url: string,
  parseDetails?: (data: unknown) => Record<string, unknown>,
): Promise<ServiceCheck> {
  const start = Date.now();
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), TIMEOUT_MS);

    const res = await fetch(url, { signal: controller.signal, cache: "no-store" });
    clearTimeout(timeout);

    const latencyMs = Date.now() - start;

    if (!res.ok) {
      return {
        name,
        status: "degraded",
        latencyMs,
        details: { httpStatus: res.status },
        checkedAt: new Date().toISOString(),
      };
    }

    let details: Record<string, unknown> = {};
    try {
      const json = await res.json();
      details = parseDetails ? parseDetails(json) : { raw: "ok" };
    } catch {
      details = { raw: "non-json response" };
    }

    return {
      name,
      status: "healthy",
      latencyMs,
      details,
      checkedAt: new Date().toISOString(),
    };
  } catch (err) {
    return {
      name,
      status: "down",
      latencyMs: Date.now() - start,
      details: { error: err instanceof Error ? err.message : "Unknown error" },
      checkedAt: new Date().toISOString(),
    };
  }
}

async function fetchN8nWorkflows(): Promise<N8nWorkflow[]> {
  const n8nUrl = process.env.N8N_URL;
  const n8nApiKey = process.env.N8N_API_KEY;
  if (!n8nUrl || !n8nApiKey) return [];

  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), TIMEOUT_MS);

    const res = await fetch(`${n8nUrl}/api/v1/workflows`, {
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

export async function GET() {
  const apiUrl =
    process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const n8nUrl = process.env.N8N_URL;
  const postizUrl = process.env.POSTIZ_URL;
  const hetznerIp = process.env.HETZNER_IP;

  const checks: Promise<ServiceCheck>[] = [
    checkService("Render API", `${apiUrl}/health`, (data) => {
      const d = data as Record<string, unknown>;
      return {
        dbConnected: d?.data
          ? (d.data as Record<string, unknown>).db_connected
          : undefined,
        version: d?.data
          ? (d.data as Record<string, unknown>).version
          : undefined,
        status: d?.data
          ? (d.data as Record<string, unknown>).status
          : undefined,
      };
    }),

    checkService("Vercel Frontend", "https://filefree.tax", () => ({
      raw: "ok",
    })),
  ];

  if (n8nUrl) {
    checks.push(
      checkService("n8n", `${n8nUrl}/healthz`, () => ({ raw: "ok" })),
    );
  }

  if (postizUrl) {
    checks.push(
      checkService("Postiz", postizUrl, () => ({ raw: "ok" })),
    );
  }

  if (hetznerIp) {
    checks.push(
      checkService(
        "Hetzner VPS",
        `http://${hetznerIp}:80`,
        () => ({ raw: "reachable" }),
      ),
    );
  }

  const [services, workflows] = await Promise.all([
    Promise.all(checks),
    fetchN8nWorkflows(),
  ]);

  const response: OpsResponse = {
    services,
    workflows,
    checkedAt: new Date().toISOString(),
  };

  return NextResponse.json(response);
}
