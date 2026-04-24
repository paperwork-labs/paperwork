import { NextResponse } from "next/server";
import { cached, getN8nWorkflows, getN8nExecutions, WORKFLOW_META } from "@/lib/command-center";

export const dynamic = "force-dynamic";

const CACHE_TTL = 60_000;

type ServiceToken = {
  service: string;
  configured: boolean;
  verified: boolean;
  detail: string;
};

async function checkSlackToken(): Promise<ServiceToken> {
  const token = process.env.SLACK_BOT_TOKEN?.trim();
  if (!token) return { service: "Slack", configured: false, verified: false, detail: "No token" };
  try {
    const res = await fetch("https://slack.com/api/auth.test", {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/x-www-form-urlencoded" },
      cache: "no-store",
    });
    const json = await res.json();
    return {
      service: "Slack",
      configured: true,
      verified: !!json.ok,
      detail: json.ok ? `Connected as ${json.user || "bot"}` : (json.error || "Auth failed"),
    };
  } catch {
    return { service: "Slack", configured: true, verified: false, detail: "Request failed" };
  }
}

async function checkGithubToken(): Promise<ServiceToken> {
  const token = process.env.GITHUB_TOKEN?.trim();
  if (!token) return { service: "GitHub", configured: false, verified: false, detail: "No token" };
  try {
    const res = await fetch("https://api.github.com/user", {
      headers: { Authorization: `Bearer ${token}`, Accept: "application/vnd.github+json" },
      cache: "no-store",
    });
    if (!res.ok) return { service: "GitHub", configured: true, verified: false, detail: `HTTP ${res.status}` };
    const json = await res.json();
    return { service: "GitHub", configured: true, verified: true, detail: `Authenticated as ${json.login}` };
  } catch {
    return { service: "GitHub", configured: true, verified: false, detail: "Request failed" };
  }
}

async function checkGoogleDrive(): Promise<ServiceToken> {
  const brainUrl = process.env.BRAIN_API_URL?.trim();
  const brainSecret = process.env.BRAIN_API_SECRET?.trim();
  if (!brainUrl || !brainSecret) {
    return {
      service: "Google Drive",
      configured: false,
      verified: false,
      detail: "Brain not wired (BRAIN_API_URL / BRAIN_API_SECRET missing)",
    };
  }
  try {
    const root = brainUrl.replace(/\/+$/, "");
    const res = await fetch(`${root}/api/v1/admin/tools`, {
      headers: { "X-Brain-Secret": brainSecret },
      cache: "no-store",
    });
    if (!res.ok) {
      return {
        service: "Google Drive",
        configured: true,
        verified: false,
        detail: `Brain tools HTTP ${res.status}`,
      };
    }
    const json = (await res.json()) as { data?: { tools?: Array<{ name?: string }> } };
    const tools = json?.data?.tools ?? [];
    const gdriveTool = tools.find((t) =>
      typeof t?.name === "string" && /gdrive|google.*drive/i.test(t.name),
    );
    if (!gdriveTool) {
      return {
        service: "Google Drive",
        configured: false,
        verified: false,
        detail: "No gdrive tool registered in Brain",
      };
    }
    return {
      service: "Google Drive",
      configured: true,
      verified: true,
      detail: `Registered as ${gdriveTool.name}`,
    };
  } catch (err) {
    return {
      service: "Google Drive",
      configured: true,
      verified: false,
      detail: err instanceof Error ? err.message : "Brain request failed",
    };
  }
}

async function checkVercelToken(): Promise<ServiceToken> {
  const token = process.env.VERCEL_API_TOKEN?.trim();
  if (!token) return { service: "Vercel", configured: false, verified: false, detail: "No token" };
  try {
    const res = await fetch("https://api.vercel.com/v2/user", {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    if (!res.ok) return { service: "Vercel", configured: true, verified: false, detail: `HTTP ${res.status}` };
    const json = await res.json();
    return { service: "Vercel", configured: true, verified: true, detail: `Authenticated as ${json.user?.username || "user"}` };
  } catch {
    return { service: "Vercel", configured: true, verified: false, detail: "Request failed" };
  }
}

export async function GET() {
  const data = await cached("admin:ops", CACHE_TTL, async () => {
    const [workflows, executions, slack, github, vercel, gdrive] = await Promise.all([
      getN8nWorkflows(),
      getN8nExecutions(50),
      checkSlackToken(),
      checkGithubToken(),
      checkVercelToken(),
      checkGoogleDrive(),
    ]);

    return {
      workflows,
      executions,
      serviceTokens: [slack, github, vercel, gdrive],
      workflowMeta: WORKFLOW_META,
    };
  });

  return NextResponse.json({
    ...data,
    fetchedAt: new Date().toISOString(),
  });
}
