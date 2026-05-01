import { N8N_MIRROR_SPEC_META } from "@/lib/n8n-mirror-spec-meta";
import { NODE_VERCEL_PROJECT } from "@/lib/architecture-vercel-projects";
import { getN8nMirrorSchedulerStatus, type N8nMirrorPerJob } from "@/lib/command-center";
import { systemGraph, probeAll, type NodeHealth, type SystemNode } from "@/lib/system-graph";

const ALL_MIRROR_KEYS = Object.keys(N8N_MIRROR_SPEC_META) as string[];

/**
 * System graph node id → n8n mirror job keys to aggregate for schedule/ownership
 * (Brain `/admin/scheduler/n8n-mirror/status` `per_job` entries).
 */
export const NODE_SCHEDULE_MIRROR_KEYS: Record<string, readonly string[] | "all"> = {
  "infra.n8n": "all",
  "brain.api": [
    "n8n_shadow_brain_daily",
    "n8n_shadow_brain_weekly",
    "n8n_shadow_sprint_kickoff",
    "n8n_shadow_sprint_close",
    "n8n_shadow_weekly_strategy",
    "n8n_shadow_infra_heartbeat",
    "n8n_shadow_infra_health",
    "n8n_shadow_credential_expiry",
  ],
};

export type LiveDataMeta = {
  available: boolean;
  fetched_at: string;
  partial_failures: string[];
};

export type NodeLiveView = {
  id: string;
  /** When set, overrides default DAG card ring to reflect schedule/health. */
  liveFrame?: "emerald" | "amber" | "zinc" | "rose";
  /** Compact live signals: health time, deploy, schedule ownership. */
  liveSubtext?: string;
  /** Relative deploy time for Vercel-mapped frontends (from production API). */
  deployRelative?: string | null;
};

type VercelDeployMap = Record<string, string | null>;

function keysForNode(node: SystemNode): string[] {
  const spec = NODE_SCHEDULE_MIRROR_KEYS[node.id];
  if (spec === "all") return [...ALL_MIRROR_KEYS];
  if (Array.isArray(spec)) return [...spec];
  return [];
}

function pickJobs(perJob: N8nMirrorPerJob[], keys: string[]): N8nMirrorPerJob[] {
  const m = new Map(perJob.map((j) => [j.key, j]));
  return keys.map((k) => m.get(k)).filter(Boolean) as N8nMirrorPerJob[];
}

/**
 * Per-node schedule tint from Brain mirror `per_job` rows:
 * - rose: any last_status error
 * - amber: any shadow row enabled (n8n shadow registered)
 * - emerald: mirror rows quiet with a successful / observed run
 * - zinc: mapped jobs but no runs to evaluate yet
 */
export function scheduleFrameForJobs(
  jobs: N8nMirrorPerJob[] | null | undefined,
): "emerald" | "amber" | "zinc" | "rose" | null {
  if (!jobs || jobs.length === 0) return null;
  if (jobs.some((j) => j.last_status === "error")) return "rose";
  if (jobs.some((j) => j.enabled === true)) return "amber";
  const hasSignal = jobs.some(
    (j) => j.last_status != null || (j.success_count_24h ?? 0) > 0 || (j.error_count_24h ?? 0) > 0,
  );
  if (!hasSignal) return "zinc";
  return "emerald";
}

/** Exposed for tests / reuse from refresh route. */
export function buildNodeLiveViews(args: {
  nodes: SystemNode[];
  perJob: N8nMirrorPerJob[] | null;
  health: NodeHealth[];
  deploys: VercelDeployMap;
  liveAvailable: boolean;
  /** When Brain reports `retired: true` for the n8n mirror status endpoint. */
  mirrorRetired?: boolean;
}): NodeLiveView[] {
  const healthById = new Map(args.health.map((h) => [h.id, h]));

  return args.nodes.map((node) => {
    const h = healthById.get(node.id);
    const keys = keysForNode(node);
    const jobs = keys.length > 0 ? pickJobs(args.perJob ?? [], keys) : [];
    const schedule =
      args.liveAvailable && jobs.length > 0 ? scheduleFrameForJobs(jobs) : null;
    const scheduleUnknown = keys.length > 0 && !args.liveAvailable;

    let liveFrame: NodeLiveView["liveFrame"] = undefined;
    if (h?.configured && h.status === "red") {
      liveFrame = "rose";
    } else if (scheduleUnknown) {
      liveFrame = "zinc";
    } else if (schedule) {
      liveFrame = schedule;
    }

    const parts: string[] = [];
    if (h?.configured && h.checkedAt) {
      const rel = relHealth(h.checkedAt);
      parts.push(`Health ${rel}`);
    }
    const proj = NODE_VERCEL_PROJECT[node.id];
    if (keys.length > 0) {
      if (args.mirrorRetired) {
        parts.push("Schedule Brain-first (n8n mirror retired)");
      } else if (args.liveAvailable && jobs.length > 0) {
        const brainOwns = jobs.filter((j) => j.enabled === false).length;
        const shadow = jobs.filter((j) => j.enabled === true).length;
        const err = jobs.filter((j) => j.last_status === "error").length;
        parts.push(
          err > 0
            ? `Schedule ${err} err`
            : shadow > 0
              ? `Schedule n8n·shadow ${shadow}/${jobs.length}`
              : `Schedule Brain-first ${brainOwns}/${jobs.length}`,
        );
      } else {
        parts.push("Schedule n/a");
      }
    }
    const liveSubtext = parts.length > 0 ? parts.join(" · ") : undefined;
    const deployRelative =
      proj != null ? (args.deploys[node.id] ?? null) : undefined;
    return { id: node.id, liveFrame, liveSubtext, deployRelative };
  });
}

function relHealth(iso: string): string {
  const diffMs = Date.now() - Date.parse(iso);
  if (Number.isNaN(diffMs)) return "—";
  const s = Math.floor(diffMs / 1000);
  if (s < 60) return "<1m";
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m`;
  return `${Math.floor(m / 60)}h`;
}

function relDeploy(iso: string): string {
  const diffMs = Date.now() - Date.parse(iso);
  if (Number.isNaN(diffMs)) return "unknown";
  const m = Math.floor(diffMs / 60000);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 48) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

async function fetchVercelProductionDeployedAgo(
  projectName: string,
  token: string,
  teamId: string | undefined,
  partial: string[],
): Promise<string | null> {
  try {
    const projUrl = new URL(
      `https://api.vercel.com/v9/projects/${encodeURIComponent(projectName)}`,
    );
    if (teamId) projUrl.searchParams.set("teamId", teamId);
    const pRes = await fetch(projUrl, {
      headers: { Authorization: `Bearer ${token}` },
      next: { revalidate: 30 },
    });
    if (!pRes.ok) {
      partial.push(`vercel:project:${projectName}`);
      return null;
    }
    const proj = (await pRes.json()) as { id?: string };
    if (!proj.id) {
      partial.push(`vercel:project:${projectName}:no-id`);
      return null;
    }
    const dUrl = new URL("https://api.vercel.com/v6/deployments");
    dUrl.searchParams.set("projectId", proj.id);
    dUrl.searchParams.set("limit", "1");
    dUrl.searchParams.set("target", "production");
    if (teamId) dUrl.searchParams.set("teamId", teamId);
    const dRes = await fetch(dUrl, {
      headers: { Authorization: `Bearer ${token}` },
      next: { revalidate: 30 },
    });
    if (!dRes.ok) {
      partial.push(`vercel:deployments:${projectName}`);
      return null;
    }
    const dJson = (await dRes.json()) as {
      deployments?: Array<{
        ready?: number;
        created?: number;
        createdAt?: number;
        createdAtString?: string;
        buildingAt?: number;
      }>;
    };
    const dep = dJson.deployments?.[0];
    const ms =
      typeof dep?.ready === "number" && dep.ready
        ? dep.ready
        : typeof dep?.createdAt === "number" && dep.createdAt
          ? dep.createdAt
          : typeof dep?.created === "number" && dep.created
            ? dep.created
            : dep?.createdAtString
              ? Date.parse(dep.createdAtString)
              : NaN;
    if (typeof ms === "number" && !Number.isNaN(ms) && ms > 0) {
      return relDeploy(new Date(ms).toISOString());
    }
    return null;
  } catch {
    partial.push(`vercel:${projectName}`);
    return null;
  }
}

export type ArchitecturePayload = {
  health: NodeHealth[];
  checkedAt: string;
  nodeLive: NodeLiveView[];
  live_data: LiveDataMeta;
};

export async function getArchitecturePayload(): Promise<ArchitecturePayload> {
  const partial_failures: string[] = [];
  const checkedAt = new Date().toISOString();

  const [health, mirrorStatus] = await Promise.all([
    probeAll(systemGraph),
    getN8nMirrorSchedulerStatus(),
  ]);

  const hasSecret = Boolean(
    process.env.BRAIN_API_URL?.trim() && process.env.BRAIN_API_SECRET?.trim(),
  );
  const live_data: LiveDataMeta = {
    available: mirrorStatus != null,
    fetched_at: checkedAt,
    partial_failures,
  };
  if (!hasSecret) {
    partial_failures.push("brain:not-configured");
  } else if (mirrorStatus == null) {
    partial_failures.push("n8n-mirror:unreachable");
  }

  const token = process.env.VERCEL_API_TOKEN?.trim();
  const teamId = process.env.VERCEL_TEAM_ID?.trim() || process.env.VERCEL_ORG_ID?.trim();
  const deploys: VercelDeployMap = {};
  const vercelByProject = new Map<string, string | null>();
  if (token) {
    const uniqueProjects = [
      ...new Set(
        Object.values(NODE_VERCEL_PROJECT).filter(
          (p): p is string => typeof p === "string" && p.length > 0,
        ),
      ),
    ];
    await Promise.all(
      uniqueProjects.map(async (projName) => {
        const label = await fetchVercelProductionDeployedAgo(
          projName,
          token,
          teamId,
          partial_failures,
        );
        vercelByProject.set(projName, label);
      }),
    );
    for (const [nodeId, projName] of Object.entries(NODE_VERCEL_PROJECT)) {
      if (!projName) continue;
      deploys[nodeId] = vercelByProject.get(projName) ?? null;
    }
  } else {
    partial_failures.push("vercel:token-missing");
  }

  const perJob = mirrorStatus?.per_job ?? null;
  const nodeLive = buildNodeLiveViews({
    nodes: systemGraph.nodes,
    perJob,
    health,
    deploys,
    liveAvailable: live_data.available,
    mirrorRetired: Boolean(mirrorStatus?.retired),
  });

  return { health, checkedAt, nodeLive, live_data };
}
