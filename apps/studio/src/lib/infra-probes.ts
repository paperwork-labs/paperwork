/**
 * Studio /admin/infrastructure — dynamic Render + Vercel platform probes
 * (no hardcoded service IDs; enumerates the workspace from provider APIs).
 */

import type {
  InfraStatus,
  PlatformHealthSummary,
  PlatformState,
} from "@/lib/infra-types";

const RENDER = "https://api.render.com/v1";
const VERCEL = "https://api.vercel.com";
const RENDER_DASH = "https://dashboard.render.com";

type RenderService = {
  id: string;
  name: string;
  type: string;
  suspended: string;
  updatedAt?: string;
};

type RenderDeploy = {
  id: string;
  status: string;
  finishedAt?: string;
  createdAt: string;
  commit?: { id?: string; message?: string };
};

type ResourceWrapper = { service?: RenderService; cursor?: string };

type VercelProject = { id: string; name: string };
type VercelProjectsPage = {
  projects: VercelProject[];
  pagination?: { count?: number; next?: number | null; prev?: number | null };
};

type VercelDeployment = {
  uid?: string;
  readyState?: string;
  state?: string;
  createdAt?: number;
  created?: number;
  ready?: number;
  meta?: { githubCommitSha?: string };
  gitSource?: { sha?: string };
};

function resourceLabel(svcType: string): string {
  if (svcType === "web_service" || svcType === "private_service") return "web";
  if (svcType === "background_worker") return "worker";
  if (svcType === "static_site") return "static";
  if (svcType === "cron") return "cron";
  if (svcType === "keyvalue" || svcType === "key_value") return "keyvalue (redis)";
  return svcType.replace(/_/g, " ");
}

function renderDashboardForService(s: RenderService): string {
  if (s.type === "static_site") return `${RENDER_DASH}/static/${s.id}`;
  if (s.type === "background_worker") return `${RENDER_DASH}/worker/${s.id}`;
  if (s.type === "keyvalue" || s.type === "key_value")
    return `${RENDER_DASH}/redis/${s.id}`;
  if (s.type === "web_service" || s.type === "private_service")
    return `${RENDER_DASH}/web/${s.id}`;
  if (s.type === "cron") return `${RENDER_DASH}/cron/${s.id}`;
  return `${RENDER_DASH}/web/${s.id}`;
}

function mapBucket(st: string, suspended: string, kind: "deploy" | "data"): PlatformState {
  if (suspended === "suspended" || (suspended && suspended !== "not_suspended")) {
    if (suspended === "suspended" || st.toLowerCase() === "suspended") return "suspended";
  }
  if (kind === "data") {
    const a = (st || "").toLowerCase();
    if (a === "available" || a === "running" || a === "live") return "live";
    if (a === "provisioning" || a === "creating" || a === "in_progress" || a === "unknown")
      return "building";
    return "failed";
  }
  const s = (st || "unknown").toLowerCase();
  if (s === "live" || s === "unknown" || s === "updated") return "live";
  if (s === "update_in_progress" || s === "build_in_progress" || s === "build_pending" || s === "queued" || s === "pending" || s === "created")
    return "building";
  if (
    s === "build_failed" ||
    s === "update_failed" ||
    s === "canceled" ||
    s === "rolled_back" ||
    s === "failed" ||
    s === "suspended"
  )
    return "failed";
  if (s === "suspended") return "suspended";
  return "live";
}

function platformHealthyFromBucket(b: PlatformState): boolean {
  return b === "live" || b === "building";
}

function nextCursorFromLinkHeader(link: string | null): string | undefined {
  if (!link) return undefined;
  const nextPart = link.split(",").find((p) => /rel="next"/.test(p) || /rel=next/.test(p));
  if (!nextPart) return undefined;
  const m = nextPart.match(/<([^>]+)>/);
  if (!m?.[1]) return undefined;
  try {
    const u = new URL(m[1]);
    return u.searchParams.get("cursor") ?? undefined;
  } catch {
    return undefined;
  }
}

async function fetchRenderServices(token: string, partial: string[]): Promise<RenderService[]> {
  const out: RenderService[] = [];
  let cursor: string | undefined;
  for (let n = 0; n < 20; n++) {
    const u = new URL(`${RENDER}/services`);
    u.searchParams.set("limit", "100");
    if (cursor) u.searchParams.set("cursor", cursor);
    const res = await fetch(u, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    if (!res.ok) {
      partial.push(`render:services:${res.status}`);
      return out;
    }
    const raw = (await res.json()) as unknown;
    const rows: ResourceWrapper[] = Array.isArray(raw)
      ? (raw as ResourceWrapper[])
      : Array.isArray((raw as { services?: ResourceWrapper[] }).services)
        ? (raw as { services: ResourceWrapper[] }).services
        : [];
    for (const row of rows) {
      const s = (row as ResourceWrapper).service ?? (row as { service?: RenderService }).service;
      if (s?.id) out.push(s);
    }
    if (rows.length < 1) break;
    const next = nextCursorFromLinkHeader(res.headers.get("link")) ?? undefined;
    if (!next || next === cursor) break;
    cursor = next;
  }
  return out;
}

export async function fetchLatestRenderDeploy(
  serviceId: string,
  token: string,
  partial: string[],
): Promise<RenderDeploy | null> {
  try {
    const u = new URL(`${RENDER}/services/${serviceId}/deploys`);
    u.searchParams.set("limit", "1");
    const res = await fetch(u, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    if (!res.ok) {
      partial.push(`render:deploys:${serviceId}:${res.status}`);
      return null;
    }
    const data = (await res.json()) as { deploy: RenderDeploy }[] | { deploy?: RenderDeploy }[];
    const rows = Array.isArray(data) ? data : [];
    const d0 = rows[0] as { deploy?: RenderDeploy } | undefined;
    return d0?.deploy ?? (rows[0] as { deploy: RenderDeploy } | undefined)?.deploy ?? null;
  } catch {
    partial.push(`render:deploys:${serviceId}:err`);
    return null;
  }
}

type NamedDataResource = { id: string; name: string; status: string; suspended?: string; updatedAt?: string };

async function fetchRenderPostgres(token: string, partial: string[]): Promise<NamedDataResource[]> {
  const out: NamedDataResource[] = [];
  let cursor: string | undefined;
  for (let n = 0; n < 20; n++) {
    const u = new URL(`${RENDER}/postgres`);
    u.searchParams.set("limit", "100");
    if (cursor) u.searchParams.set("cursor", cursor);
    const res = await fetch(u, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    if (!res.ok) {
      if (res.status === 404) return out;
      partial.push(`render:postgres:${res.status}`);
      return out;
    }
    const data = (await res.json()) as { postgres: NamedDataResource }[];
    const rows = Array.isArray(data) ? data : [];
    for (const row of rows) {
      const p = (row as { postgres?: NamedDataResource }).postgres;
      if (p?.id) out.push(p);
    }
    if (rows.length < 1) break;
    const next = nextCursorFromLinkHeader(res.headers.get("link")) ?? undefined;
    if (!next || next === cursor) break;
    cursor = next;
  }
  return out;
}

async function fetchRenderKeyValue(token: string, partial: string[]): Promise<NamedDataResource[]> {
  const out: NamedDataResource[] = [];
  let cursor: string | undefined;
  for (let n = 0; n < 20; n++) {
    const u = new URL(`${RENDER}/key-value`);
    u.searchParams.set("limit", "100");
    if (cursor) u.searchParams.set("cursor", cursor);
    const res = await fetch(u, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    if (!res.ok) {
      if (res.status === 404) return out;
      partial.push(`render:key-value:${res.status}`);
      return out;
    }
    const data = (await res.json()) as { keyValue?: NamedDataResource; redis?: NamedDataResource }[];
    const rows = Array.isArray(data) ? data : [];
    for (const row of rows) {
      const o = row as Record<string, unknown>;
      const r =
        (o.keyValue as NamedDataResource | undefined) ??
        (o.key_value as NamedDataResource | undefined) ??
        (o.redis as NamedDataResource | undefined) ??
        (Object.values(o).find(
          (v): v is NamedDataResource =>
            typeof v === "object" &&
            v != null &&
            "id" in v &&
            typeof (v as NamedDataResource).id === "string" &&
            (v as NamedDataResource).name != null,
        ) as NamedDataResource | undefined);
      if (r?.id) out.push(r);
    }
    if (rows.length < 1) break;
    const next = nextCursorFromLinkHeader(res.headers.get("link")) ?? undefined;
    if (!next || next === cursor) break;
    cursor = next;
  }
  return out;
}

function emptySummary(): { render: PlatformHealthSummary["render"]; vercel: PlatformHealthSummary["vercel"] } {
  const e = { live: 0, building: 0, failed: 0, suspended: 0, total: 0 };
  return { render: { ...e }, vercel: { ...e } };
}

function bump(
  c: { live: number; building: number; failed: number; suspended: number; total: number },
  b: PlatformState,
) {
  c.total++;
  if (b === "live") c.live++;
  else if (b === "building") c.building++;
  else if (b === "failed") c.failed++;
  else c.suspended++;
}

function vercelState(dep: VercelDeployment | undefined): PlatformState {
  if (!dep) return "failed";
  const rs = (dep.readyState || dep.state || "").toUpperCase();
  if (rs === "READY" || rs === "PROMOTED") return "live";
  if (rs === "ERROR" || rs === "CANCELED" || rs === "FAILED") return "failed";
  if (rs === "QUEUED" || rs === "BUILDING" || rs === "INITIALIZING" || rs === "ANALYZING" || rs === "DEPLOYING")
    return "building";
  return "failed";
}

export async function collectRenderAndVercelProbes(
  renderToken: string | undefined,
  vercelToken: string | undefined,
  teamId: string | undefined,
  vercelTeamSlug: string,
): Promise<{
  rows: InfraStatus[];
  partial: string[];
  platformSummary: PlatformHealthSummary;
}> {
  const partial: string[] = [];
  const rows: InfraStatus[] = [];
  const s = emptySummary();
  const seen = new Set<string>();

  if (renderToken) {
    const [services, pgList, kvList] = await Promise.all([
      fetchRenderServices(renderToken, partial),
      fetchRenderPostgres(renderToken, partial),
      fetchRenderKeyValue(renderToken, partial),
    ]);

    for (const svc of services) {
      if (seen.has(svc.id)) continue;
      seen.add(svc.id);
      const deploy = await fetchLatestRenderDeploy(svc.id, renderToken, partial);
      const st = deploy?.status || (svc.suspended === "suspended" ? "suspended" : "unknown");
      const b = mapBucket(st, svc.suspended, "deploy");
      bump(s.render, b);
      const healthy = platformHealthyFromBucket(b);
      const short = deploy?.commit?.id?.slice(0, 7) ?? "—";
      const when = deploy?.finishedAt ?? deploy?.createdAt;
      const detail = `Render · ${resourceLabel(svc.type)} · ${(st || "?").toLowerCase()}${short !== "—" ? ` · ${short}` : ""}${when ? ` · ${when}` : ""}`.replace(/\s+/g, " ");
      rows.push({
        service: svc.name,
        category: "hosting",
        configured: true,
        healthy,
        detail: detail.trim(),
        latencyMs: null,
        dashboardUrl: renderDashboardForService(svc),
        probeKind: "render",
        platformType: resourceLabel(svc.type),
        stateLabel: b,
        deployState: (st || "").toLowerCase(),
        commitSha: deploy?.commit?.id ?? null,
        lastDeployedAt: when ?? null,
        anchorId: `render-${svc.id.replace(/[^a-z0-9-]/gi, "-")}`,
      });
    }
    for (const pg of pgList) {
      if (seen.has(pg.id)) continue;
      seen.add(pg.id);
      const b = mapBucket(
        (pg.status || "unknown").toLowerCase(),
        pg.suspended === "suspended" ? "suspended" : "not_suspended",
        "data",
      );
      bump(s.render, b);
      rows.push({
        service: pg.name,
        category: "hosting",
        configured: true,
        healthy: platformHealthyFromBucket(b),
        detail: `Render postgres · ${(pg.status || "?").toLowerCase()}${pg.updatedAt ? ` · updated ${pg.updatedAt}` : ""}`,
        latencyMs: null,
        dashboardUrl: `${RENDER_DASH}/database/${pg.id}`,
        probeKind: "render",
        platformType: "postgres",
        stateLabel: b,
        deployState: (pg.status || "").toLowerCase(),
        commitSha: null,
        lastDeployedAt: null,
        anchorId: `pg-${pg.id.replace(/[^a-z0-9-]/gi, "-")}`,
      });
    }
    for (const kv of kvList) {
      if (seen.has(kv.id)) continue;
      seen.add(kv.id);
      const b = mapBucket(
        (kv.status || "unknown").toLowerCase(),
        kv.suspended === "suspended" ? "suspended" : "not_suspended",
        "data",
      );
      bump(s.render, b);
      rows.push({
        service: kv.name,
        category: "hosting",
        configured: true,
        healthy: platformHealthyFromBucket(b),
        detail: `Render key value · ${(kv.status || "?").toLowerCase()}${kv.updatedAt ? ` · updated ${kv.updatedAt}` : ""}`,
        latencyMs: null,
        dashboardUrl: `${RENDER_DASH}/redis/${kv.id}`,
        probeKind: "render",
        platformType: "redis",
        stateLabel: b,
        deployState: (kv.status || "").toLowerCase(),
        commitSha: null,
        lastDeployedAt: null,
        anchorId: `kv-${kv.id.replace(/[^a-z0-9-]/gi, "-")}`,
      });
    }
  } else {
    partial.push("render:token-missing");
  }

  if (vercelToken) {
    let until: number | undefined;
    for (let page = 0; page < 30; page++) {
      const u = new URL(`${VERCEL}/v9/projects`);
      u.searchParams.set("limit", "100");
      if (teamId) u.searchParams.set("teamId", teamId);
      if (typeof until === "number") u.searchParams.set("until", String(until));
      const res = await fetch(u, {
        headers: { Authorization: `Bearer ${vercelToken}` },
        cache: "no-store",
      });
      if (!res.ok) {
        partial.push(`vercel:projects:${res.status}`);
        break;
      }
      const pageJson = (await res.json()) as VercelProjectsPage;
      const projects = pageJson.projects ?? [];
      for (const proj of projects) {
        if (!proj.id || !proj.name) continue;
        const dUrl = new URL(`${VERCEL}/v6/deployments`);
        dUrl.searchParams.set("projectId", proj.id);
        dUrl.searchParams.set("limit", "1");
        dUrl.searchParams.set("target", "production");
        if (teamId) dUrl.searchParams.set("teamId", teamId);
        const dRes = await fetch(dUrl, {
          headers: { Authorization: `Bearer ${vercelToken}` },
          cache: "no-store",
        });
        let dep: VercelDeployment | undefined;
        if (dRes.ok) {
          const dJson = (await dRes.json()) as { deployments: VercelDeployment[] };
          dep = dJson.deployments?.[0];
        } else {
          partial.push(`vercel:deployments:${proj.name}:${dRes.status}`);
        }
        const b = vercelState(dep);
        bump(s.vercel, b);
        const healthy = platformHealthyFromBucket(b);
        const sha = dep?.meta?.githubCommitSha || dep?.gitSource?.sha;
        const created =
          dep?.ready && dep.ready > 0
            ? dep.ready
            : dep?.createdAt
              ? dep.createdAt
              : dep?.created
                ? dep.created * 1000
                : null;
        const stLabel = (dep?.readyState || dep?.state || "?").toLowerCase();
        const detail = `Vercel production · ${stLabel}${sha ? ` · ${sha.slice(0, 7)}` : ""}${created ? ` · ${new Date(created).toISOString()}` : ""}`.replace(/\s+/g, " ");
        rows.push({
          service: proj.name,
          category: "hosting",
          configured: true,
          healthy,
          detail: detail.trim(),
          latencyMs: null,
          dashboardUrl: `https://vercel.com/${vercelTeamSlug}/${encodeURIComponent(proj.name)}`,
          probeKind: "vercel",
          platformType: "vercel-project",
          stateLabel: b,
          deployState: stLabel,
          commitSha: sha ?? null,
          lastDeployedAt: created ? new Date(created).toISOString() : null,
          anchorId: `vercel-${proj.id.replace(/[^a-z0-9-]/gi, "-")}`,
        });
      }
      if (pageJson.pagination?.next == null) break;
      const nxt = pageJson.pagination.next;
      if (typeof nxt === "number" && nxt > 0) until = nxt;
      else break;
      if (projects.length < 1) break;
    }
  } else {
    partial.push("vercel:token-missing");
  }

  rows.sort((a, b) => {
    const k = (x: InfraStatus) => `${x.probeKind ?? "z"}|${(x.service || "").toLowerCase()}`;
    return k(a).localeCompare(k(b));
  });

  return {
    rows,
    partial,
    platformSummary: { render: s.render, vercel: s.vercel },
  };
}
