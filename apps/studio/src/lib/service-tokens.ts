/**
 * Service token verifiers for Studio's operational dashboards.
 *
 * Extracted from `/admin/ops/page.tsx` so both the old Ops page and the
 * merged `/admin/workflows` page can share the exact probe logic. Each
 * function is tolerant of a missing token — it just reports
 * `configured: false` and keeps rendering.
 */

export type ServiceTokenStatus = {
  service: string;
  configured: boolean;
  verified: boolean;
  detail: string;
};

export async function checkSlackToken(): Promise<ServiceTokenStatus> {
  const token = process.env.SLACK_BOT_TOKEN?.trim();
  if (!token)
    return { service: "Slack", configured: false, verified: false, detail: "No token" };
  try {
    const res = await fetch("https://slack.com/api/auth.test", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/x-www-form-urlencoded",
      },
      cache: "no-store",
    });
    const json = (await res.json()) as { ok?: boolean; user?: string; error?: string };
    return {
      service: "Slack",
      configured: true,
      verified: !!json.ok,
      detail: json.ok ? `Connected as ${json.user ?? "bot"}` : (json.error ?? "Auth failed"),
    };
  } catch {
    return { service: "Slack", configured: true, verified: false, detail: "Request failed" };
  }
}

export async function checkGithubToken(): Promise<ServiceTokenStatus> {
  const token = process.env.GITHUB_TOKEN?.trim();
  if (!token)
    return { service: "GitHub", configured: false, verified: false, detail: "No token" };
  try {
    const res = await fetch("https://api.github.com/user", {
      headers: { Authorization: `Bearer ${token}`, Accept: "application/vnd.github+json" },
      cache: "no-store",
    });
    if (!res.ok)
      return {
        service: "GitHub",
        configured: true,
        verified: false,
        detail: `HTTP ${res.status}`,
      };
    const json = (await res.json()) as { login?: string };
    return {
      service: "GitHub",
      configured: true,
      verified: true,
      detail: `Authenticated as ${json.login ?? "?"}`,
    };
  } catch {
    return { service: "GitHub", configured: true, verified: false, detail: "Request failed" };
  }
}

export async function checkVercelToken(): Promise<ServiceTokenStatus> {
  const token = process.env.VERCEL_API_TOKEN?.trim();
  if (!token)
    return { service: "Vercel", configured: false, verified: false, detail: "No token" };
  try {
    const res = await fetch("https://api.vercel.com/v2/user", {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    if (!res.ok)
      return {
        service: "Vercel",
        configured: true,
        verified: false,
        detail: `HTTP ${res.status}`,
      };
    const json = (await res.json()) as { user?: { username?: string } };
    return {
      service: "Vercel",
      configured: true,
      verified: true,
      detail: `Authenticated as ${json.user?.username ?? "user"}`,
    };
  } catch {
    return { service: "Vercel", configured: true, verified: false, detail: "Request failed" };
  }
}

export async function checkGoogleDrive(): Promise<ServiceTokenStatus> {
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
    const json = (await res.json()) as {
      data?: { tools?: Array<{ name?: string }> };
    };
    const tools = json?.data?.tools ?? [];
    const gdriveTool = tools.find(
      (t) => typeof t?.name === "string" && /gdrive|google.*drive/i.test(t.name),
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
