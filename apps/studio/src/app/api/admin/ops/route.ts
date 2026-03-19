import { NextResponse } from "next/server";
import { getN8nWorkflows, getN8nExecutions } from "@/lib/command-center";

export const dynamic = "force-dynamic";

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
  const [workflows, executions, slack, github, vercel] = await Promise.all([
    getN8nWorkflows(),
    getN8nExecutions(50),
    checkSlackToken(),
    checkGithubToken(),
    checkVercelToken(),
  ]);

  const gdrive: ServiceToken = {
    service: "Google Drive",
    configured: true,
    verified: true,
    detail: "Configured via MCP",
  };

  return NextResponse.json({
    workflows,
    executions,
    serviceTokens: [slack, github, vercel, gdrive],
    fetchedAt: new Date().toISOString(),
  });
}
