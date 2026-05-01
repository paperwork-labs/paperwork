import fs from "fs";
import path from "path";

import matter from "gray-matter";

import { brainApiV1Root, getBrainAdminFetchOptions } from "./brain-admin-proxy";
import { BrainClient, BrainClientError } from "./brain-client";
import { getBrainPersonas } from "./command-center";

import {
  avgTokensFromOutcomes,
  buildActivityTargetLabel,
  dispatchPersonaId,
  extractMainHeading,
  extractModelAssignmentSection,
  inferActivityActionType,
  parseEaTagRouting,
  parseEstRangeUsd,
  parseMarkdownTables,
  parsePersonaEstCostPerRunUsd,
} from "./personas-pure";

export * from "./personas-pure";
export * from "./personas-tab-params";
export * from "./personas-types";

import type {
  ActivityFeedRow,
  AgentDispatchFile,
  BrainDataSourceStatus,
  BrainPersonasFromApi,
  CostTabPayload,
  DispatchRecord,
  EaRoutingRow,
  MarkdownTable,
  OpenRoleRow,
  PeopleDashboardStats,
  PersonaRegistryRow,
  PersonasPagePayload,
  PrOutcomesFile,
  PromotionsQueuePayload,
  SelfMergePromotionsFile,
} from "./personas-types";

// Snapshot bundled at build time by scripts/snapshot-personas.ts
import personasSnapshot from "@/data/personas-snapshot.json";

export function getRepoRoot(): string {
  const cwd = process.cwd();
  const upTwo = path.resolve(cwd, "..", "..");
  if (fs.existsSync(path.join(upTwo, "pnpm-workspace.yaml"))) {
    return upTwo;
  }
  if (fs.existsSync(path.join(cwd, "pnpm-workspace.yaml"))) {
    return cwd;
  }
  throw new Error(`Cannot resolve monorepo root from cwd=${cwd}`);
}

function readRulesDir(repoRoot: string): string {
  return path.join(repoRoot, ".cursor", "rules");
}

export function loadPersonaRegistry(repoRoot: string): PersonaRegistryRow[] {
  const dir = readRulesDir(repoRoot);
  if (!fs.existsSync(dir)) {
    throw new Error(`Missing rules directory: ${dir}`);
  }
  const files = fs.readdirSync(dir).filter((f) => f.endsWith(".mdc"));
  const rows: PersonaRegistryRow[] = [];
  for (const file of files.sort()) {
    const full = path.join(dir, file);
    const raw = fs.readFileSync(full, "utf8");
    const { data, content } = matter(raw);
    const personaId = file.replace(/\.mdc$/i, "");
    const fm = data as Record<string, unknown>;
    const description = typeof fm.description === "string" ? fm.description : null;
    const alwaysApply = fm.alwaysApply === true;
    const heading = extractMainHeading(content);
    const name =
      heading?.replace(/^Paperwork Labs —\s*/i, "").replace(/\s*—.*$/, "").trim() ||
      personaId.replace(/-/g, " ");
    rows.push({
      personaId,
      name,
      description,
      relativePath: path.join(".cursor", "rules", file),
      modelAssignment: extractModelAssignmentSection(content),
      routingActive: alwaysApply,
    });
  }
  return rows;
}

function readJsonIfPresent<T>(filePath: string): { status: BrainDataSourceStatus; data: T | null } {
  if (!fs.existsSync(filePath)) {
    return {
      status: { ok: false, path: filePath, message: "File not found on disk." },
      data: null,
    };
  }
  try {
    const raw = fs.readFileSync(filePath, "utf8");
    const data = JSON.parse(raw) as T;
    return { status: { ok: true, path: filePath }, data };
  } catch (e) {
    return {
      status: {
        ok: false,
        path: filePath,
        message: e instanceof Error ? e.message : "Failed to read JSON",
      },
      data: null,
    };
  }
}

function daysAgoIso(days: number): string {
  const d = new Date();
  d.setUTCDate(d.getUTCDate() - days);
  return d.toISOString();
}

export function buildCostPayload(
  repoRoot: string,
  registryPersonaIds: string[],
): CostTabPayload {
  const dispatchPath = path.join(repoRoot, "apis", "brain", "data", "agent_dispatch_log.json");
  const outcomesPath = path.join(repoRoot, "apis", "brain", "data", "pr_outcomes.json");
  const registryPath = path.join(repoRoot, "docs", "AI_MODEL_REGISTRY.md");

  const dispatchRead = readJsonIfPresent<AgentDispatchFile>(dispatchPath);
  const outcomesRead = readJsonIfPresent<PrOutcomesFile>(outcomesPath);

  let registryMd = "";
  try {
    registryMd = fs.readFileSync(registryPath, "utf8");
  } catch {
    registryMd = "";
  }
  const personaCostMap = registryMd ? parsePersonaEstCostPerRunUsd(registryMd) : new Map<string, number>();

  const dispatches = dispatchRead.data?.dispatches ?? [];
  const outcomes = outcomesRead.data?.outcomes ?? [];

  const iso7 = daysAgoIso(7);
  const iso30 = daysAgoIso(30);

  let attributed = false;
  for (const d of dispatches) {
    if (dispatchPersonaId(d)) {
      attributed = true;
      break;
    }
  }

  const counts7 = new Map<string, number>();
  const counts30 = new Map<string, number>();
  for (const d of dispatches) {
    const ts = typeof d.dispatched_at === "string" ? d.dispatched_at : null;
    if (!ts) continue;
    const pid = dispatchPersonaId(d);
    if (!pid) continue;
    if (ts >= iso7) counts7.set(pid, (counts7.get(pid) ?? 0) + 1);
    if (ts >= iso30) counts30.set(pid, (counts30.get(pid) ?? 0) + 1);
  }

  let global7 = 0;
  let global30 = 0;
  for (const d of dispatches) {
    const ts = typeof d.dispatched_at === "string" ? d.dispatched_at : null;
    if (!ts) continue;
    if (ts >= iso7) global7 += 1;
    if (ts >= iso30) global30 += 1;
  }

  const avgTokensOverall = avgTokensFromOutcomes(outcomes);
  const avgTokensNote = !outcomesRead.status.ok
    ? null
    : outcomes.length === 0
      ? "No merged PR outcomes — apis/brain/data/pr_outcomes.json has outcomes: []."
      : avgTokensOverall === null
        ? "No token counts — pr_outcomes.json rows omit tokens_input/tokens_output; average tokens cannot be computed."
        : null;

  const attributionNote = attributed
    ? null
    : "Dispatch log entries do not include `persona_slug` / `persona` / `persona_pin`; per-persona dispatch counts cannot be attributed. Add persona fields to `apis/brain/data/agent_dispatch_log.json` entries to populate per-persona columns.";

  const rows = registryPersonaIds.map((personaId) => {
    const pid = personaId.toLowerCase();
    let costNote: string;
    if (!registryMd) {
      costNote = "rate unknown — add or restore docs/AI_MODEL_REGISTRY.md for Est. $ / run hints.";
    } else if (personaCostMap.has(pid)) {
      const mid = personaCostMap.get(pid)!;
      costNote = `~$${mid.toFixed(2)} / run (midpoint of Est. $ / run column in docs/AI_MODEL_REGISTRY.md)`;
    } else {
      costNote =
        "rate unknown — persona not listed in Brain PersonaSpec table in docs/AI_MODEL_REGISTRY.md.";
    }

    return {
      personaId,
      dispatch7d: attributed ? (counts7.get(pid) ?? 0) : null,
      dispatch30d: attributed ? (counts30.get(pid) ?? 0) : null,
      avgTokensPerDispatch: avgTokensOverall,
      costNote,
    };
  });

  return {
    dispatchSource: dispatchRead.status,
    outcomesSource: outcomesRead.status,
    personaHasAttribution: attributed,
    attributionNote,
    avgTokensNote,
    rows,
    globalDispatch7d:
      dispatchRead.status.ok && dispatchRead.data ? global7 : null,
    globalDispatch30d:
      dispatchRead.status.ok && dispatchRead.data ? global30 : null,
  };
}


function utcCalendarDayFromIso(ts: string): string | null {
  const ms = Date.parse(ts);
  if (!Number.isFinite(ms)) return null;
  return new Date(ms).toISOString().slice(0, 10);
}

function utcTodayCalendarDay(): string {
  return new Date().toISOString().slice(0, 10);
}

/**
 * Approval rate over dispatches from the last 30d with terminal-ish outcomes:
 * merged counts toward pass; revert / CI fail / explicit review fail toward fail.
 */
function approvalRateLast30dLabel(dispatches: DispatchRecord[]): string {
  const iso30 = daysAgoIso(30);
  let pass = 0;
  let fail = 0;
  for (const d of dispatches) {
    const ts = typeof d.dispatched_at === "string" ? d.dispatched_at : null;
    if (!ts || ts < iso30) continue;
    const o = d.outcome;
    if (!o || typeof o !== "object") continue;
    if (o.reverted === true) {
      fail++;
      continue;
    }
    if (typeof o.merged_at === "string" && o.merged_at.length > 0) {
      pass++;
      continue;
    }
    if (o.ci_initial_pass === false) {
      fail++;
      continue;
    }
    if (o.review_pass === false) {
      fail++;
      continue;
    }
  }
  const decided = pass + fail;
  if (decided === 0) return "—";
  return `${Math.round((pass / decided) * 100)}%`;
}

export function buildPeopleDashboardStats(
  dispatchRead: { status: BrainDataSourceStatus; data: AgentDispatchFile | null },
  activePersonas: number,
): PeopleDashboardStats {
  const today = utcTodayCalendarDay();
  let dispatchesToday = 0;
  if (dispatchRead.status.ok && dispatchRead.data?.dispatches) {
    for (const d of dispatchRead.data.dispatches) {
      const ts = typeof d.dispatched_at === "string" ? d.dispatched_at : null;
      if (!ts) continue;
      const day = utcCalendarDayFromIso(ts);
      if (day === today) dispatchesToday++;
    }
  }

  const dispatches = dispatchRead.data?.dispatches ?? [];
  const approvalRateLabel =
    dispatchRead.status.ok && dispatches.length > 0
      ? approvalRateLast30dLabel(dispatches)
      : "—";

  return {
    activePersonas,
    dispatchesToday,
    approvalRateLabel,
    dailyCostStatLabel: "—",
  };
}

function loadPromotionsQueue(repoRoot: string): PromotionsQueuePayload {
  const p = path.join(repoRoot, "apis", "brain", "data", "self_merge_promotions.json");
  const read = readJsonIfPresent<SelfMergePromotionsFile>(p);
  if (!read.status.ok || read.data == null) {
    return { source: read.status, promotions: [] };
  }
  const raw = read.data.promotions;
  const promotions: Record<string, unknown>[] = [];
  if (Array.isArray(raw)) {
    for (const item of raw) {
      if (item && typeof item === "object" && !Array.isArray(item)) {
        promotions.push(item as Record<string, unknown>);
      }
    }
  }
  return { source: read.status, promotions };
}

export function loadEaRoutingTable(repoRoot: string): {
  source: BrainDataSourceStatus;
  rows: EaRoutingRow[];
} {
  const p = path.join(repoRoot, ".cursor", "rules", "ea.mdc");
  if (!fs.existsSync(p)) {
    return {
      source: { ok: false, path: p, message: "ea.mdc not found." },
      rows: [],
    };
  }
  try {
    const raw = fs.readFileSync(p, "utf8");
    const { content } = matter(raw);
    return { source: { ok: true, path: p }, rows: parseEaTagRouting(content) };
  } catch (e) {
    return {
      source: {
        ok: false,
        path: p,
        message: e instanceof Error ? e.message : "Read failed",
      },
      rows: [],
    };
  }
}

function buildPersonaDisplayNameMap(registry: PersonaRegistryRow[]): Map<string, string> {
  const m = new Map<string, string>();
  for (const r of registry) {
    m.set(r.personaId.toLowerCase(), r.name);
  }
  return m;
}

/** Mid-band model $/run hints keyed by model substring (Brain PersonaSpec table). */
function loadModelCostLookupFromRegistryMd(repoRoot: string): Map<string, number> {
  const registryPath = path.join(repoRoot, "docs", "AI_MODEL_REGISTRY.md");
  let registryMd = "";
  try {
    registryMd = fs.readFileSync(registryPath, "utf8");
  } catch {
    registryMd = "";
  }
  const modelCost = new Map<string, number>();
  if (!registryMd) return modelCost;
  const block = registryMd.match(/### Brain PersonaSpec[\s\S]*?(?=### |\n## [^#]|$)/);
  if (!block) return modelCost;
  const lines = block[0].split("\n").filter((l) => l.startsWith("|"));
  for (const line of lines) {
    const cells = line
      .split("|")
      .map((c) => c.trim())
      .filter(Boolean);
    if (cells.length < 2) continue;
    const modelCell = cells.find(
      (c) => c.includes("claude-") || c.includes("gpt-") || c.includes("gemini"),
    );
    if (!modelCell) continue;
    const est = cells[cells.length - 1];
    const mid = parseEstRangeUsd(est);
    const modelKey = modelCell.replace(/`/g, "").toLowerCase();
    if (mid !== null) modelCost.set(modelKey, mid);
  }
  return modelCost;
}

function activityFeedRowFromDispatchRecord(
  d: DispatchRecord,
  modelCost: Map<string, number>,
  personaNames: Map<string, string>,
): ActivityFeedRow {
  const ts = typeof d.dispatched_at === "string" ? d.dispatched_at : "—";
  const personaKey =
    dispatchPersonaId(d) ??
    (typeof d.agent_model === "string" ? `model:${d.agent_model}` : "not attributed");
  const slug = dispatchPersonaId(d);
  const personaDisplayName =
    slug != null
      ? (personaNames.get(slug) ?? slug.replace(/-/g, " "))
      : personaKey.startsWith("model:")
        ? personaKey.replace(/^model:/, "")
        : personaKey;
  const ws =
    (typeof d.workstream_type === "string" && d.workstream_type) ||
    (typeof d.workstream_id === "string" && d.workstream_id) ||
    "—";
  let successLabel = "unknown";
  const o = d.outcome;
  if (o && typeof o === "object") {
    if (o.reverted === true) successLabel = "reverted";
    else if (typeof o.merged_at === "string" && o.merged_at.length > 0) successLabel = "merged";
    else if (o.review_pass === true) successLabel = "review ok";
    else if (o.ci_initial_pass === true) successLabel = "CI pass";
    else if (o.ci_initial_pass === false) successLabel = "CI fail";
  }

  const am = typeof d.agent_model === "string" ? d.agent_model.toLowerCase() : "";
  let costLabel = "—";
  if (am) {
    let found: number | undefined;
    for (const [k, v] of modelCost) {
      if (am.includes(k) || k.includes(am)) {
        found = v;
        break;
      }
    }
    costLabel = found !== undefined ? `~$${found.toFixed(2)} est.` : "rate unknown";
  }

  const actionType = inferActivityActionType(d);
  const targetLabel = buildActivityTargetLabel(d);
  const summaryRaw = typeof d.task_summary === "string" ? d.task_summary.trim() : "";
  const actionPhrase =
    actionType === "dispatch"
      ? "Agent dispatch"
      : actionType === "review"
        ? "PR review"
        : actionType === "escalate"
          ? "Escalation"
          : "Persona event";
  const description =
    summaryRaw.length > 0
      ? summaryRaw.length > 220
        ? `${summaryRaw.slice(0, 220)}…`
        : summaryRaw
      : `${actionPhrase} · ${successLabel} · ${targetLabel}`;
  const prNum = typeof d.pr_number === "number" ? d.pr_number : null;

  return {
    dispatchedAt: ts,
    persona: personaKey,
    personaDisplayName,
    workstreamTag: ws,
    successLabel,
    costLabel,
    actionType,
    targetLabel,
    description,
    prNumber: prNum,
  };
}

export function buildActivityFeed(repoRoot: string, limit: number): {
  source: BrainDataSourceStatus;
  rows: ActivityFeedRow[];
  note: string | null;
} {
  const dispatchPath = path.join(repoRoot, "apis", "brain", "data", "agent_dispatch_log.json");
  const read = readJsonIfPresent<AgentDispatchFile>(dispatchPath);
  if (!read.status.ok || !read.data) {
    return {
      source: read.status,
      rows: [],
      note: null,
    };
  }

  const registryRows = loadPersonaRegistry(repoRoot);
  const personaNames = buildPersonaDisplayNameMap(registryRows);
  const modelCost = loadModelCostLookupFromRegistryMd(repoRoot);

  const dispatches = [...(read.data.dispatches ?? [])].sort((a, b) => {
    const ta = typeof a.dispatched_at === "string" ? a.dispatched_at : "";
    const tb = typeof b.dispatched_at === "string" ? b.dispatched_at : "";
    return tb.localeCompare(ta);
  });

  const rows: ActivityFeedRow[] = [];
  for (const d of dispatches.slice(0, limit)) {
    rows.push(activityFeedRowFromDispatchRecord(d, modelCost, personaNames));
  }

  const note =
    dispatches.length === 0
      ? "Dispatch log is empty — no rows in apis/brain/data/agent_dispatch_log.json yet."
      : null;

  return { source: read.status, rows, note };
}

/** Assemble People HQ payload from the local monorepo checkout (rules + brain data files). */
export function buildPersonasPagePayloadFromRepo(repoRoot: string): PersonasPagePayload {
  const registry = loadPersonaRegistry(repoRoot);
  const personaIds = registry.map((r) => r.personaId);
  const dispatchPath = path.join(repoRoot, "apis", "brain", "data", "agent_dispatch_log.json");
  const dispatchRead = readJsonIfPresent<AgentDispatchFile>(dispatchPath);
  const dashboard = buildPeopleDashboardStats(dispatchRead, registry.length);
  const openRoles: OpenRoleRow[] = registry
    .filter((r) => r.modelAssignment === null || !r.modelAssignment.trim())
    .map((r) => ({
      personaId: r.personaId,
      name: r.name,
      relativePath: r.relativePath,
    }));

  return {
    repoRoot,
    dashboard,
    registry,
    openRoles,
    promotions: loadPromotionsQueue(repoRoot),
    cost: buildCostPayload(repoRoot, personaIds),
    routing: loadEaRoutingTable(repoRoot),
    activity: buildActivityFeed(repoRoot, 100),
    modelRegistry: loadModelRegistryTables(repoRoot),
    brainApiError: null,
  };
}

export function loadModelRegistryTables(repoRoot: string): {
  source: BrainDataSourceStatus;
  tables: MarkdownTable[];
} {
  const p = path.join(repoRoot, "docs", "AI_MODEL_REGISTRY.md");
  if (!fs.existsSync(p)) {
    return {
      source: {
        ok: false,
        path: p,
        message: "Add docs/AI_MODEL_REGISTRY.md to populate this tab.",
      },
      tables: [],
    };
  }
  try {
    const raw = fs.readFileSync(p, "utf8");
    const { content } = matter(raw);
    return {
      source: { ok: true, path: p },
      tables: parseMarkdownTables(content),
    };
  } catch (e) {
    return {
      source: {
        ok: false,
        path: p,
        message: e instanceof Error ? e.message : "Read failed",
      },
      tables: [],
    };
  }
}

// ---------------------------------------------------------------------------
// Snapshot → PersonasPagePayload converter
// ---------------------------------------------------------------------------

type PersonasSnapshotShape = {
  registry: PersonaRegistryRow[];
  openRoles: OpenRoleRow[];
  cost: CostTabPayload;
  routing: { source: BrainDataSourceStatus; rows: EaRoutingRow[] };
  activity: {
    source: BrainDataSourceStatus;
    rows: ActivityFeedRow[];
    note: string | null;
  };
  modelRegistry: { source: BrainDataSourceStatus; tables: MarkdownTable[] };
  promotions: PromotionsQueuePayload;
};

function snapshotToDashboard(snap: PersonasSnapshotShape): PeopleDashboardStats {
  const today = new Date().toISOString().slice(0, 10);
  let dispatchesToday = 0;
  for (const row of snap.activity.rows) {
    if (typeof row.dispatchedAt === "string") {
      const day = row.dispatchedAt.slice(0, 10);
      if (day === today) dispatchesToday++;
    }
  }
  return {
    activePersonas: snap.registry.length,
    dispatchesToday,
    approvalRateLabel: "—",
    dailyCostStatLabel: "—",
  };
}

function snapshotToPayload(
  snap: PersonasSnapshotShape,
  brainApiError?: string | null,
): PersonasPagePayload {
  return {
    repoRoot: "snapshot",
    dashboard: snapshotToDashboard(snap),
    registry: snap.registry,
    openRoles: snap.openRoles,
    promotions: snap.promotions,
    cost: snap.cost,
    routing: snap.routing,
    activity: snap.activity,
    modelRegistry: snap.modelRegistry,
    brainApiError: brainApiError ?? null,
  };
}

// ---------------------------------------------------------------------------
// Main entry point
// ---------------------------------------------------------------------------

/**
 * Returns personas page data.
 *
 * - BRAIN_API_URL not set → bundled snapshot (bootstrap path).
 * - BRAIN_API_URL set → repo-derived registry/tabs plus persona dispatch activity from
 *   Brain (`GET /admin/agent-dispatch-log`). Missing credentials or API failure surfaces
 *   an explicit error on the activity stream (no silent fallback to local dispatch rows).
 */
export async function loadPersonasPageData(): Promise<PersonasPagePayload> {
  const brainApiUrl = process.env.BRAIN_API_URL?.trim();

  if (!brainApiUrl) {
    return snapshotToPayload(personasSnapshot as unknown as PersonasSnapshotShape);
  }

  let base: PersonasPagePayload;
  try {
    base = buildPersonasPagePayloadFromRepo(getRepoRoot());
  } catch (e) {
    return snapshotToPayload(
      personasSnapshot as unknown as PersonasSnapshotShape,
      e instanceof Error ? e.message : "Failed to load personas data from repo.",
    );
  }

  const brainPersonasLive = await getBrainPersonas();
  const brainPersonasFromApi: BrainPersonasFromApi = {
    specs: brainPersonasLive.personas,
    ...(brainPersonasLive.error ? { error: brainPersonasLive.error } : {}),
  };

  const auth = getBrainAdminFetchOptions();
  const apiRoot = brainApiV1Root() ?? `${brainApiUrl.replace(/\/+$/, "")}/api/v1`;
  const dispatchEndpoint = `${apiRoot}/admin/agent-dispatch-log`;

  if (!auth.ok) {
    return {
      ...base,
      brainPersonasFromApi,
      activity: {
        source: {
          ok: false,
          path: dispatchEndpoint,
          message:
            "Brain admin credentials incomplete — set BRAIN_API_URL and BRAIN_API_SECRET to load live persona dispatch activity.",
        },
        rows: [],
        note: null,
      },
      brainApiError: null,
    };
  }

  const client = new BrainClient(auth.root, auth.secret);
  try {
    const log = await client.getDispatchLog(100);
    const records = log.dispatches as unknown as DispatchRecord[];
    const modelCost = loadModelCostLookupFromRegistryMd(base.repoRoot);
    const personaNames = buildPersonaDisplayNameMap(base.registry);
    const rows = records.map((d) =>
      activityFeedRowFromDispatchRecord(d, modelCost, personaNames),
    );

    const dispatchRead: { status: BrainDataSourceStatus; data: AgentDispatchFile | null } = {
      status: { ok: true, path: dispatchEndpoint },
      data: { dispatches: records },
    };
    const dashboard = buildPeopleDashboardStats(dispatchRead, base.registry.length);

    const note =
      records.length === 0
        ? "Brain returned an empty dispatch log (agent_dispatch_log.json has no entries)."
        : null;

    return {
      ...base,
      brainPersonasFromApi,
      dashboard,
      activity: {
        source: { ok: true, path: dispatchEndpoint },
        rows,
        note,
      },
      brainApiError: null,
    };
  } catch (e) {
    const message =
      e instanceof BrainClientError ? e.message : e instanceof Error ? e.message : String(e);
    return {
      ...base,
      brainPersonasFromApi,
      activity: {
        source: {
          ok: false,
          path: dispatchEndpoint,
          message,
        },
        rows: [],
        note: null,
      },
      brainApiError: null,
    };
  }
}
