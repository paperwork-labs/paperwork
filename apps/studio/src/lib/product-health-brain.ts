/**
 * Server-side Brain reads for `/admin/products/[slug]/health`.
 * PR-PB1 (`/probes/*`) and PR-PB3 (`/errors/*`) shapes are defensive — callers
 * must treat missing fields as empty, but never as “healthy” when fetch failed.
 */

import type { BrainEnvelope } from "@/lib/quota-monitor-types";
import type { RenderQuotaApiPayload, VercelQuotaApiPayload } from "@/lib/quota-monitor-types";
import { getBrainAdminFetchOptions } from "@/lib/brain-admin-proxy";

export type HeroRollup = "healthy" | "degraded" | "down" | "unknown";

/** Compact pulse for product cards (`healthy` → `ok`). */
export type ProductHealthPulse = "ok" | "degraded" | "down";

export function heroRollupToProductPulse(rollup: HeroRollup): ProductHealthPulse | null {
  if (rollup === "healthy") return "ok";
  if (rollup === "degraded") return "degraded";
  if (rollup === "down") return "down";
  return null;
}

export type CujProbeRow = {
  id: string;
  name: string;
  status: "pass" | "fail" | "unknown";
  lastRunAt: string | null;
};

export type ProbeRunRow = {
  at: string;
  assertion: string;
  status: "pass" | "fail" | "unknown";
};

export type ErrorFingerprintRow = {
  fingerprint: string;
  count: number;
  firstSeen: string | null;
};

export type DeployCardVercel = {
  projectName: string;
  deployCount24h: number | null;
  snapshotAt: string | null;
  commitSha: string | null;
  statusLabel: string;
};

export type DeployCardRender = {
  serviceName: string;
  approxMinutes: number | null;
  snapshotRecordedAt: string | null;
  pipelineUsageRatio: number | null;
  statusLabel: string;
};

export type ProductHealthBrainState = {
  slug: string;
  brainConfigured: boolean;
  /** Any core probe/errors fetch failed, misconfigured Brain, or non-2xx. */
  brainDataPlaneError: string | null;
  /** Optional telemetry — failures only affect deploy card + narrative hint. */
  deployTelemetryErrors: string[];
  probesCheckedAt: string | null;
  cujRows: CujProbeRow[];
  probeResultsSpark: { t: string; pass: boolean }[];
  probeRuns: ProbeRunRow[];
  errorTotal24h: number | null;
  errorFingerprints: ErrorFingerprintRow[];
  vercelDeploy: DeployCardVercel | null;
  renderDeploy: DeployCardRender | null;
};

const BRAIN_UNREACHABLE =
  "Brain API unreachable — check BRAIN_API_URL and BRAIN_API_SECRET in the Studio environment.";

function isRecord(x: unknown): x is Record<string, unknown> {
  return typeof x === "object" && x !== null && !Array.isArray(x);
}

function asString(x: unknown): string | null {
  return typeof x === "string" && x.length > 0 ? x : null;
}

function asNumber(x: unknown): number | null {
  if (typeof x === "number" && Number.isFinite(x)) return x;
  if (typeof x === "string" && x.trim() !== "" && Number.isFinite(Number(x))) return Number(x);
  return null;
}

async function brainJsonGet<T>(
  url: string,
  secret: string,
): Promise<{ ok: true; status: number; json: T } | { ok: false; status: number; detail: string }> {
  let res: Response;
  try {
    res = await fetch(url, {
      headers: { "X-Brain-Secret": secret },
      cache: "no-store",
    });
  } catch (e) {
    return {
      ok: false,
      status: 0,
      detail: e instanceof Error ? e.message : "network error",
    };
  }
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    return {
      ok: false,
      status: res.status,
      detail: body ? `HTTP ${res.status}: ${body.slice(0, 200)}` : `HTTP ${res.status}`,
    };
  }
  let json: T;
  try {
    json = (await res.json()) as T;
  } catch {
    return { ok: false, status: res.status, detail: "Invalid JSON from Brain" };
  }
  return { ok: true, status: res.status, json };
}

function parseProbeHealth(data: unknown): {
  checkedAt: string | null;
  rows: CujProbeRow[];
} {
  if (!isRecord(data)) return { checkedAt: null, rows: [] };
  const checkedAt = asString(data.checked_at ?? data.checkedAt ?? data.as_of);
  const cujList = data.cuj_results ?? data.cujs ?? data.results ?? data.items;
  const rows: CujProbeRow[] = [];
  if (Array.isArray(cujList)) {
    for (const raw of cujList) {
      if (!isRecord(raw)) continue;
      const id = asString(raw.cuj_id ?? raw.id ?? raw.slug) ?? "cuj";
      const name = asString(raw.name ?? raw.label ?? raw.cuj_name) ?? id;
      const st = asString(raw.status ?? raw.state)?.toLowerCase();
      let status: CujProbeRow["status"] = "unknown";
      if (st === "pass" || st === "passed" || st === "ok" || st === "success") status = "pass";
      else if (st === "fail" || st === "failed" || st === "error") status = "fail";
      rows.push({
        id,
        name,
        status,
        lastRunAt: asString(raw.last_run_at ?? raw.lastRunAt ?? raw.run_at),
      });
    }
  }
  return { checkedAt, rows };
}

function parseProbeResults(data: unknown): { spark: { t: string; pass: boolean }[]; runs: ProbeRunRow[] } {
  if (!isRecord(data)) return { spark: [], runs: [] };
  const list = data.results ?? data.runs ?? data.items ?? data.records;
  const spark: { t: string; pass: boolean }[] = [];
  const runs: ProbeRunRow[] = [];
  if (!Array.isArray(list)) return { spark, runs };
  for (const raw of list) {
    if (!isRecord(raw)) continue;
    const at =
      asString(raw.at ?? raw.timestamp ?? raw.run_at ?? raw.created_at ?? raw.checked_at) ?? "";
    const passRaw = raw.passed ?? raw.pass ?? raw.ok ?? raw.success;
    const pass =
      passRaw === true ||
      (typeof passRaw === "string" && ["true", "pass", "ok", "1"].includes(passRaw.toLowerCase()));
    const assertion =
      asString(raw.assertion ?? raw.message ?? raw.name ?? raw.cuj_id ?? raw.probe_id) ?? "—";
    const st = asString(raw.status)?.toLowerCase();
    let status: ProbeRunRow["status"] = "unknown";
    if (pass || st === "pass" || st === "passed") status = "pass";
    else if (st === "fail" || st === "failed" || passRaw === false) status = "fail";
    else if (passRaw === true) status = "pass";
    if (at) spark.push({ t: at, pass: status !== "fail" });
    runs.push({ at: at || "—", assertion, status });
  }
  const sparkSorted = [...spark].sort((a, b) => a.t.localeCompare(b.t));
  const runsSorted = [...runs].sort((a, b) => b.at.localeCompare(a.at));
  return {
    spark: sparkSorted.slice(-48),
    runs: runsSorted.slice(0, 20),
  };
}

function parseErrorsAggregate(data: unknown): {
  total: number | null;
  fingerprints: ErrorFingerprintRow[];
} {
  if (!isRecord(data)) return { total: null, fingerprints: [] };
  let totalOut = asNumber(data.total_count ?? data.total ?? data.count);
  const fps: ErrorFingerprintRow[] = [];
  const list = data.fingerprints ?? data.top_fingerprints ?? data.items ?? [];
  if (Array.isArray(list)) {
    for (const raw of list) {
      if (!isRecord(raw)) continue;
      const fingerprint =
        asString(raw.fingerprint ?? raw.fp ?? raw.id ?? raw.key) ?? "unknown";
      const count = asNumber(raw.count ?? raw.n ?? raw.total) ?? 0;
      const firstSeen = asString(raw.first_seen ?? raw.firstSeen ?? raw.first_at);
      fps.push({ fingerprint, count, firstSeen });
    }
  }
  fps.sort((a, b) => b.count - a.count);
  if (totalOut === null && fps.length > 0) {
    totalOut = fps.reduce((s, r) => s + r.count, 0);
  }
  return { total: totalOut, fingerprints: fps.slice(0, 5) };
}

function readEnvelope<T>(json: unknown): { ok: true; data: T | null } | { ok: false; detail: string } {
  if (!isRecord(json)) return { ok: false, detail: "Brain returned non-object JSON" };
  const env = json as BrainEnvelope<T>;
  if (!env.success) return { ok: false, detail: env.error || "Brain success=false" };
  return { ok: true, data: env.data ?? null };
}

function matchVercelRow(rows: VercelQuotaApiPayload["snapshots"], slug: string) {
  const lower = slug.toLowerCase();
  const match = rows.find(
    (r) =>
      r.window_days === 1 &&
      r.project_name &&
      r.project_name !== "(team)" &&
      r.project_name.toLowerCase() === lower,
  );
  return match ?? null;
}

function matchRenderService(
  tops: RenderQuotaApiPayload["top_services_by_minutes"],
  slug: string,
): RenderQuotaApiPayload["top_services_by_minutes"][number] | null {
  const lower = slug.toLowerCase();
  const hit = tops.find((t) => {
    const n = (t.name || "").toLowerCase();
    return n.includes(lower) || lower.includes(n.replace(/-api$/, ""));
  });
  return hit ?? null;
}

function metaCommitSha(meta: Record<string, unknown>): string | null {
  const v = meta.latest_commit_sha ?? meta.commit_sha ?? meta.sha;
  return asString(v);
}

export function deriveHeroRollup(state: ProductHealthBrainState): {
  rollup: HeroRollup;
  narrative: string;
} {
  if (state.brainDataPlaneError) {
    return {
      rollup: "down",
      narrative:
        "Production health data is unavailable until the Brain API responds successfully for probes and errors.",
    };
  }
  const noProbeCoverage =
    state.cujRows.length === 0 &&
    state.probeResultsSpark.length === 0 &&
    state.probeRuns.length === 0;
  if (noProbeCoverage) {
    return {
      rollup: "degraded",
      narrative:
        "Brain responded but returned no probe rows for this product in the last 24h — CUJs may not be scheduled yet.",
    };
  }
  const anyFail = state.cujRows.some((r) => r.status === "fail");
  const errs = state.errorTotal24h ?? 0;
  const deployHints = state.deployTelemetryErrors.length;

  const probeOk = state.cujRows.length === 0 || state.cujRows.every((r) => r.status !== "fail");
  const lastProbe =
    state.probesCheckedAt ||
    state.cujRows.map((r) => r.lastRunAt).filter(Boolean).sort().at(-1) ||
    null;

  const deployBits: string[] = [];
  if (state.vercelDeploy) {
    deployBits.push(
      `${state.vercelDeploy.projectName} · ${state.vercelDeploy.deployCount24h ?? "—"} deploys (24h)`,
    );
  }
  if (state.renderDeploy) {
    deployBits.push(`Render · ${state.renderDeploy.serviceName}`);
  }
  if (deployHints) deployBits.push("deploy quota fetch incomplete");

  let rollup: HeroRollup = "healthy";
  if (anyFail) rollup = "down";
  else if (errs > 0 || deployHints) rollup = "degraded";

  const parts: string[] = [];
  if (state.cujRows.length === 0) {
    parts.push("CUJ summary missing from health payload (runs/spark may still show activity)");
  } else {
    parts.push(probeOk ? "UX probes pass" : "UX probes reporting failures");
  }
  parts.push(errs === 0 ? "0 errors in last 24h" : `${errs} error(s) in last 24h`);
  if (lastProbe) parts.push(`last probe check ${formatRelativeHint(lastProbe)}`);
  if (state.vercelDeploy?.snapshotAt) {
    parts.push(`Vercel quota snapshot ${formatRelativeHint(state.vercelDeploy.snapshotAt)}`);
  } else if (state.renderDeploy?.snapshotRecordedAt) {
    parts.push(`Render snapshot ${formatRelativeHint(state.renderDeploy.snapshotRecordedAt)}`);
  }

  return { rollup, narrative: parts.join(" · ") };
}

function formatRelativeHint(iso: string): string {
  const t = Date.parse(iso);
  if (!Number.isFinite(t)) return iso;
  const diffMs = Date.now() - t;
  const mins = Math.round(diffMs / 60_000);
  if (mins < 2) return "just now";
  if (mins < 120) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 48) return `${hrs}h ago`;
  return `${Math.round(hrs / 24)}d ago`;
}

export async function loadProductHealthBrainState(slug: string): Promise<ProductHealthBrainState> {
  const auth = getBrainAdminFetchOptions();
  if (!auth.ok) {
    return {
      slug,
      brainConfigured: false,
      brainDataPlaneError: BRAIN_UNREACHABLE,
      deployTelemetryErrors: [BRAIN_UNREACHABLE],
      probesCheckedAt: null,
      cujRows: [],
      probeResultsSpark: [],
      probeRuns: [],
      errorTotal24h: null,
      errorFingerprints: [],
      vercelDeploy: null,
      renderDeploy: null,
    };
  }

  const { root, secret } = auth;
  const sinceIso = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();
  const urls = {
    probesHealth: `${root}/probes/health?product=${encodeURIComponent(slug)}`,
    errorsAgg: `${root}/errors/aggregates?since=${encodeURIComponent(sinceIso)}&product=${encodeURIComponent(slug)}`,
    probeResults: `${root}/probes/results?product=${encodeURIComponent(slug)}&since=${encodeURIComponent(sinceIso)}`,
    vercelQuota: `${root}/admin/vercel-quota`,
    renderQuota: `${root}/admin/render-quota`,
  };

  const [hRes, eRes, rRes, vRes, rrRes] = await Promise.all([
    brainJsonGet<unknown>(urls.probesHealth, secret),
    brainJsonGet<unknown>(urls.errorsAgg, secret),
    brainJsonGet<unknown>(urls.probeResults, secret),
    brainJsonGet<unknown>(urls.vercelQuota, secret),
    brainJsonGet<unknown>(urls.renderQuota, secret),
  ]);

  const planeErrors: string[] = [];
  if (!hRes.ok) planeErrors.push(`probes/health: ${hRes.detail}`);
  if (!eRes.ok) planeErrors.push(`errors/aggregates: ${eRes.detail}`);
  if (!rRes.ok) planeErrors.push(`probes/results: ${rRes.detail}`);

  let cujRows: CujProbeRow[] = [];
  let probesCheckedAt: string | null = null;
  let probeResultsSpark: { t: string; pass: boolean }[] = [];
  let probeRuns: ProbeRunRow[] = [];
  let errorTotal24h: number | null = null;
  let errorFingerprints: ErrorFingerprintRow[] = [];

  if (hRes.ok) {
    const env = readEnvelope(hRes.json);
    if (!env.ok) planeErrors.push(`probes/health envelope: ${env.detail}`);
    else {
      const parsed = parseProbeHealth(env.data);
      probesCheckedAt = parsed.checkedAt;
      cujRows = parsed.rows;
    }
  }
  if (eRes.ok) {
    const env = readEnvelope(eRes.json);
    if (!env.ok) planeErrors.push(`errors/aggregates envelope: ${env.detail}`);
    else {
      const parsed = parseErrorsAggregate(env.data);
      errorTotal24h = parsed.total;
      errorFingerprints = parsed.fingerprints;
    }
  }
  if (rRes.ok) {
    const env = readEnvelope(rRes.json);
    if (!env.ok) planeErrors.push(`probes/results envelope: ${env.detail}`);
    else {
      const parsed = parseProbeResults(env.data);
      probeResultsSpark = parsed.spark;
      probeRuns = parsed.runs;
    }
  }

  const deployTelemetryErrors: string[] = [];
  let vercelDeploy: DeployCardVercel | null = null;
  let renderDeploy: DeployCardRender | null = null;

  if (vRes.ok) {
    const env = readEnvelope<VercelQuotaApiPayload>(vRes.json);
    if (!env.ok) deployTelemetryErrors.push(`vercel-quota: ${env.detail}`);
    else if (env.data?.snapshots?.length) {
      const row = matchVercelRow(env.data.snapshots, slug);
      if (row) {
        vercelDeploy = {
          projectName: row.project_name,
          deployCount24h: row.deploy_count,
          snapshotAt: env.data.batch_at ?? row.created_at,
          commitSha: metaCommitSha(row.meta || {}),
          statusLabel: "Quota snapshot",
        };
      } else {
        vercelDeploy = {
          projectName: slug,
          deployCount24h: null,
          snapshotAt: env.data.batch_at,
          commitSha: null,
          statusLabel: "No matching Vercel project row",
        };
      }
    } else {
      deployTelemetryErrors.push("vercel-quota: empty snapshots");
    }
  } else {
    deployTelemetryErrors.push(`vercel-quota: ${vRes.detail}`);
  }

  if (rrRes.ok) {
    const env = readEnvelope<RenderQuotaApiPayload>(rrRes.json);
    if (!env.ok) deployTelemetryErrors.push(`render-quota: ${env.detail}`);
    else if (env.data?.snapshot) {
      const tops = env.data.top_services_by_minutes || [];
      const svc = matchRenderService(tops, slug);
      renderDeploy = {
        serviceName: svc?.name ?? (tops[0]?.name || "—"),
        approxMinutes: svc?.approx_minutes ?? tops[0]?.approx_minutes ?? null,
        snapshotRecordedAt: env.data.snapshot.recorded_at,
        pipelineUsageRatio: env.data.snapshot.usage_ratio,
        statusLabel: env.data.snapshot.derived_from,
      };
    } else {
      deployTelemetryErrors.push("render-quota: no snapshot");
    }
  } else {
    deployTelemetryErrors.push(`render-quota: ${rrRes.detail}`);
  }

  const brainDataPlaneError = planeErrors.length ? `${BRAIN_UNREACHABLE} (${planeErrors.join(" · ")})` : null;

  return {
    slug,
    brainConfigured: true,
    brainDataPlaneError,
    deployTelemetryErrors,
    probesCheckedAt,
    cujRows,
    probeResultsSpark,
    probeRuns,
    errorTotal24h,
    errorFingerprints,
    vercelDeploy,
    renderDeploy,
  };
}
