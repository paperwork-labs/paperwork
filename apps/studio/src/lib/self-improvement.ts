/**
 * Server-side helpers for `/admin/brain/self-improvement` — reads Brain JSON/YAML
 * under `apis/brain/data` relative to the monorepo root (discovered from cwd).
 */

import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { basename, dirname, join, relative } from "node:path";

import yaml from "js-yaml";

import { BII_FORMULA } from "@/lib/brain-improvement-formula";
import { getBrainAdminFetchOptions } from "@/lib/brain-admin-proxy";
import type { BrainImprovementResponse } from "@/types/brain-improvement";

export type FileMeta = {
  path: string;
  /** ISO timestamp best-effort: file mtime when present */
  asOfIso: string | null;
  missing: boolean;
};

export type DispatchLogMeta = FileMeta & {
  rawUpdatedAt?: string;
};

export type LearningAggregates = {
  dispatchMeta: DispatchLogMeta;
  volume7d: Record<string, number>;
  volume30d: Record<string, number>;
  /** agent_model -> counts */
  volumeByModel7d: Record<string, number>;
  volumeByModel30d: Record<string, number>;
  successRate7d: number | null;
  successRate30d: number | null;
  /** Top procedural rules by learned_at in last 30d */
  topPatterns30d: Array<{ id: string; learned_at: string; summary: string }>;
  proceduralMeta: FileMeta;
};

export type PromotionRow = {
  currentTier: string;
  promotionThreshold: number;
  cleanMergesCurrentTier: number;
  promotionsMeta: FileMeta;
  reverts: Array<{ pr_number: number; original_pr: number; reverted_at: string; reason: string }>;
  graduationHistory: Array<{
    from_tier: string;
    to_tier: string;
    promoted_at: string;
    clean_merge_count_at_promotion: number;
    notes: string;
  }>;
};

export type OutcomeRow = {
  pr_number: number;
  merged_at: string;
  merged_by_agent: string;
  agent_model: string;
  workstream_ids: string[];
  workstream_types: string[];
  outcomes?: {
    h1?: { ci_pass: boolean; deploy_success: boolean; reverted: boolean } | null;
    h24?: { ci_pass: boolean; deploy_success: boolean; reverted: boolean } | null;
    d7?: unknown | null;
  };
};

export type RetroRow = {
  week_ending: string;
  computed_at: string;
  summaryText: string;
  highlights: string[];
  ruleChanges: Array<{ action: string; rule_id: string; reason: string }>;
};

export type SchedulerJobRow = {
  jobId: string;
  moduleFile: string;
  schedule: string;
  lastRun: string | null;
  lastStatus: string | null;
  nextRun: string | null;
};

export type ProceduralRuleRow = {
  id: string;
  when: string;
  do: string;
  learned_at: string;
  status: string;
  source: string;
  confidence?: string;
};

export type SelfImprovementPayload = {
  repoRoot: string | null;
  learning: LearningAggregates;
  promotions: PromotionRow;
  outcomes: { meta: FileMeta; rows: OutcomeRow[] };
  retros: { meta: FileMeta; rows: RetroRow[] };
  schedulers: { meta: FileMeta; rows: SchedulerJobRow[] };
  procedural: { meta: FileMeta; rows: ProceduralRuleRow[] };
  brainImprovement: BrainImprovementResponse | null;
  brainImprovementError: string | null;
};

function isoFromMtime(p: string): string | null {
  try {
    return statSync(p).mtime.toISOString();
  } catch {
    return null;
  }
}

export function resolveMonorepoRoot(cwd = process.cwd()): string | null {
  let dir = cwd;
  for (let i = 0; i < 10; i += 1) {
    if (existsSync(join(dir, "pnpm-workspace.yaml")) && existsSync(join(dir, "apis", "brain"))) {
      return dir;
    }
    if (existsSync(join(dir, "apis", "brain", "data"))) {
      return dir;
    }
    const parent = dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  return null;
}

function brainDataDir(root: string): string {
  return join(root, "apis", "brain", "data");
}

function schedulersDir(root: string): string {
  return join(root, "apis", "brain", "app", "schedulers");
}

function readJson(path: string): unknown | null {
  try {
    return JSON.parse(readFileSync(path, "utf-8")) as unknown;
  } catch {
    return null;
  }
}

function fileMeta(path: string): FileMeta {
  if (!path || !existsSync(path)) {
    return { path, asOfIso: null, missing: true };
  }
  return { path, asOfIso: isoFromMtime(path), missing: false };
}

function emptyLearning(): LearningAggregates {
  return {
    dispatchMeta: { path: "apis/brain/data/agent_dispatch_log.json", asOfIso: null, missing: true },
    volume7d: {},
    volume30d: {},
    volumeByModel7d: {},
    volumeByModel30d: {},
    successRate7d: null,
    successRate30d: null,
    topPatterns30d: [],
    proceduralMeta: { path: "apis/brain/data/procedural_memory.yaml", asOfIso: null, missing: true },
  };
}

function daysAgo(iso: string, days: number): boolean {
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return false;
  return t >= Date.now() - days * 86400000;
}

export function aggregateLearning(root: string): LearningAggregates {
  const dataDir = brainDataDir(root);
  const dispatchPath = join(dataDir, "agent_dispatch_log.json");
  const proceduralPath = join(dataDir, "procedural_memory.yaml");

  const dispatchMeta: DispatchLogMeta = {
    ...fileMeta(dispatchPath),
    rawUpdatedAt: undefined,
  };

  const procMeta = fileMeta(proceduralPath);

  const topPatterns30d: LearningAggregates["topPatterns30d"] = [];
  if (!procMeta.missing) {
    type YamlRoot = { rules?: Array<{ id: string; learned_at?: string; when?: string; do?: string }> };
    const doc = yaml.load(readFileSync(proceduralPath, "utf-8")) as YamlRoot;
    const rules = doc.rules ?? [];
    const recent = rules
      .filter((r) => r.learned_at && daysAgo(r.learned_at, 30))
      .sort((a, b) => Date.parse(b.learned_at!) - Date.parse(a.learned_at!));
    for (const r of recent.slice(0, 3)) {
      topPatterns30d.push({
        id: r.id,
        learned_at: r.learned_at!,
        summary: `${(r.when ?? "").slice(0, 120)}${(r.when ?? "").length > 120 ? "…" : ""}`,
      });
    }
  }

  const volume7d: Record<string, number> = {};
  const volume30d: Record<string, number> = {};
  const volumeByModel7d: Record<string, number> = {};
  const volumeByModel30d: Record<string, number> = {};
  let success7 = { ok: 0, total: 0 };
  let success30 = { ok: 0, total: 0 };

  if (!dispatchMeta.missing) {
    const raw = readJson(dispatchPath) as {
      updated_at?: string;
      dispatches?: Array<{
        dispatched_at?: string;
        agent_model?: string;
        workstream_id?: string;
        outcome?: { merged_at?: string | null; reverted?: boolean | null };
      }>;
    } | null;
    if (raw?.updated_at) {
      dispatchMeta.rawUpdatedAt = raw.updated_at;
    }
    const list = raw?.dispatches ?? [];
    for (const d of list) {
      const at = d.dispatched_at;
      if (!at) continue;
      const k = d.workstream_id ?? "unknown";
      const m = d.agent_model ?? "unknown";
      if (daysAgo(at, 7)) {
        volume7d[k] = (volume7d[k] ?? 0) + 1;
        volumeByModel7d[m] = (volumeByModel7d[m] ?? 0) + 1;
      }
      if (daysAgo(at, 30)) {
        volume30d[k] = (volume30d[k] ?? 0) + 1;
        volumeByModel30d[m] = (volumeByModel30d[m] ?? 0) + 1;
      }
      const rev = d.outcome?.reverted;
      if (rev !== undefined && rev !== null) {
        if (daysAgo(at, 7)) {
          success7.total += 1;
          if (!rev) success7.ok += 1;
        }
        if (daysAgo(at, 30)) {
          success30.total += 1;
          if (!rev) success30.ok += 1;
        }
      }
    }
  }

  return {
    dispatchMeta,
    volume7d,
    volume30d,
    volumeByModel7d,
    volumeByModel30d,
    successRate7d: success7.total ? Math.round((success7.ok / success7.total) * 1000) / 10 : null,
    successRate30d: success30.total ? Math.round((success30.ok / success30.total) * 1000) / 10 : null,
    topPatterns30d,
    proceduralMeta: procMeta,
  };
}

export function loadPromotions(root: string): PromotionRow {
  const p = join(brainDataDir(root), "self_merge_promotions.json");
  const meta = fileMeta(p);
  if (meta.missing) {
    return {
      currentTier: "—",
      promotionThreshold: BII_FORMULA.PROMOTION_THRESHOLD,
      cleanMergesCurrentTier: 0,
      promotionsMeta: meta,
      reverts: [],
      graduationHistory: [],
    };
  }
  const raw = readJson(p) as {
    current_tier?: string;
    merges?: Array<{ pr_number: number; tier?: string; merged_at?: string }>;
    reverts?: Array<{ pr_number: number; original_pr: number; reverted_at: string; reason: string }>;
    promotions?: Array<{
      from_tier: string;
      to_tier: string;
      promoted_at: string;
      clean_merge_count_at_promotion: number;
      notes: string;
    }>;
  } | null;
  const tier = raw?.current_tier ?? "—";
  const cutoff = Date.now() - 30 * 86400000;
  const revertedOriginals = new Set<number>();
  for (const r of raw?.reverts ?? []) {
    const t = Date.parse(r.reverted_at);
    if (!Number.isNaN(t) && t >= cutoff) {
      revertedOriginals.add(r.original_pr);
    }
  }
  const clean = (raw?.merges ?? []).filter(
    (m) => m.tier === tier && !revertedOriginals.has(m.pr_number),
  ).length;
  return {
    currentTier: tier,
    promotionThreshold: BII_FORMULA.PROMOTION_THRESHOLD,
    cleanMergesCurrentTier: clean,
    promotionsMeta: meta,
    reverts: [...(raw?.reverts ?? [])]
      .sort((a, b) => Date.parse(b.reverted_at) - Date.parse(a.reverted_at))
      .slice(0, 20),
    graduationHistory: [...(raw?.promotions ?? [])].sort(
      (a, b) => Date.parse(b.promoted_at) - Date.parse(a.promoted_at),
    ),
  };
}

export function loadOutcomes(root: string): { meta: FileMeta; rows: OutcomeRow[] } {
  const p = join(brainDataDir(root), "pr_outcomes.json");
  const meta = fileMeta(p);
  if (meta.missing) return { meta, rows: [] };
  const raw = readJson(p) as { outcomes?: OutcomeRow[] } | null;
  const all = raw?.outcomes ?? [];
  const rows = [...all]
    .sort((a, b) => Date.parse(b.merged_at) - Date.parse(a.merged_at))
    .slice(0, 50);
  return { meta, rows };
}

export function loadRetros(root: string): { meta: FileMeta; rows: RetroRow[] } {
  const p = join(brainDataDir(root), "weekly_retros.json");
  const meta = fileMeta(p);
  if (meta.missing) return { meta, rows: [] };
  const raw = readJson(p) as {
    retros?: Array<{
      week_ending: string;
      computed_at: string;
      summary?: { merges?: number; reverts?: number; pos_total_change?: number };
      highlights?: string[];
      rule_changes?: Array<{ action: string; rule_id: string; reason: string }>;
    }>;
  } | null;
  const list = raw?.retros ?? [];
  const rows: RetroRow[] = [...list]
    .sort((a, b) => Date.parse(b.week_ending) - Date.parse(a.week_ending))
    .slice(0, 12)
    .map((r) => ({
      week_ending: r.week_ending,
      computed_at: r.computed_at,
      summaryText: summarizeRetroSummary(r.summary),
      highlights: r.highlights ?? [],
      ruleChanges: r.rule_changes ?? [],
    }));
  return { meta, rows };
}

function summarizeRetroSummary(s?: {
  merges?: number;
  reverts?: number;
  pos_total_change?: number;
}): string {
  if (!s) return "—";
  const parts: string[] = [];
  if (s.merges != null) parts.push(`${s.merges} merges`);
  if (s.reverts != null) parts.push(`${s.reverts} reverts`);
  if (s.pos_total_change != null) parts.push(`POS Δ ${s.pos_total_change}`);
  return parts.join(" · ") || "—";
}

export function loadSchedulerState(root: string): FileMeta {
  const candidates = [
    join(brainDataDir(root), "scheduler_state.json"),
    join(brainDataDir(root), "scheduler_runs.json"),
  ];
  for (const p of candidates) {
    const m = fileMeta(p);
    if (!m.missing) return m;
  }
  return { path: candidates[0]!, asOfIso: null, missing: true };
}

/** Best-effort parse of Brain scheduler modules — static source scan only. */
function listSchedulerPyFiles(schedulersRoot: string): string[] {
  const out: string[] = [];
  if (!existsSync(schedulersRoot)) return out;
  for (const name of readdirSync(schedulersRoot)) {
    const full = join(schedulersRoot, name);
    let st: ReturnType<typeof statSync>;
    try {
      st = statSync(full);
    } catch {
      continue;
    }
    if (st.isFile() && name.endsWith(".py") && !name.startsWith("_")) {
      out.push(full);
    } else if (st.isDirectory() && name !== "__pycache__") {
      for (const sub of readdirSync(full)) {
        if (sub.endsWith(".py") && !sub.startsWith("_")) {
          out.push(join(full, sub));
        }
      }
    }
  }
  return out.sort();
}

export function parseSchedulerModules(root: string): SchedulerJobRow[] {
  const dir = schedulersDir(root);
  const paths = listSchedulerPyFiles(dir);
  const rows: SchedulerJobRow[] = [];
  const statePath = join(brainDataDir(root), "scheduler_state.json");
  const stateRaw = !fileMeta(statePath).missing ? readJson(statePath) : null;
  const byId =
    stateRaw && typeof stateRaw === "object" && stateRaw !== null && "jobs" in stateRaw
      ? (stateRaw as { jobs: Record<string, { last_run?: string; last_status?: string; next_run?: string }> }).jobs
      : null;

  for (const full of paths) {
    let text: string;
    try {
      text = readFileSync(full, "utf-8");
    } catch {
      continue;
    }
    const rel = relative(dir, full) || basename(full);
    const jobs = extractJobsFromSchedulerSource(text, rel.replace(/\\/g, "/"));
    for (const j of jobs) {
      const st = byId?.[j.jobId];
      rows.push({
        ...j,
        lastRun: st?.last_run ?? null,
        lastStatus: st?.last_status ?? null,
        nextRun: st?.next_run ?? null,
      });
    }
  }
  return rows.sort((a, b) => a.jobId.localeCompare(b.jobId));
}

/**
 * Pull job blocks from scheduler Python source.
 */
export function extractJobsFromSchedulerSource(source: string, moduleFile: string): Omit<
  SchedulerJobRow,
  "lastRun" | "lastStatus" | "nextRun"
>[] {
  const constMap = new Map<string, string>();
  for (const m of source.matchAll(/_JOB[_A-Z0-9]*\s*=\s*["']([^"']+)["']/g)) {
    const line = m[0] ?? "";
    const key = line.split("=")[0]?.trim();
    if (key) constMap.set(key, m[1]!);
  }

  const results: Omit<SchedulerJobRow, "lastRun" | "lastStatus" | "nextRun">[] = [];
  const blocks = source.split(/scheduler\.add_job\(|sched\.add_job\(/);
  for (let i = 1; i < blocks.length; i += 1) {
    const block = blocks[i] ?? "";
    const idExpr = /id\s*=\s*([^,\n]+)/.exec(block)?.[1]?.trim();
    let jobId: string | null = null;
    if (idExpr) {
      if (idExpr.startsWith('"') || idExpr.startsWith("'")) {
        jobId = idExpr.replace(/^["']|["']$/g, "");
      } else if (constMap.has(idExpr)) {
        jobId = constMap.get(idExpr)!;
      }
    }
    if (!jobId) continue;

    let schedule = "—";
    const fc = /from_crontab\(\s*["']([^"']+)["']/.exec(block);
    if (fc) {
      schedule = fc[1]!;
    } else {
      const cm = /CronTrigger\(\s*minute\s*=\s*(\d+)/.exec(block)?.[1];
      const ch = /CronTrigger\([^)]*?\bhour\s*=\s*(\d+)/.exec(block)?.[1];
      const intervalH = /IntervalTrigger\(\s*hours\s*=\s*(\d+)/.exec(block)?.[1];
      if (cm !== undefined && ch !== undefined) schedule = `${cm} ${ch} * * *`;
      else if (cm !== undefined && ch === undefined) schedule = `${cm} * * * * (cron minute)`;
      else if (intervalH) schedule = `every ${intervalH}h (interval)`;
    }

    results.push({
      jobId,
      moduleFile,
      schedule,
    });
  }

  if (results.length === 0 && source.includes("def install(")) {
    const fc = /from_crontab\(\s*["']([^"']+)["']/.exec(source);
    const jid = constMap.get("_JOB_ID") ?? [...constMap.values()][0];
    if (jid && fc) {
      results.push({ jobId: jid, moduleFile, schedule: fc[1]! });
    }
  }

  return results;
}

export function loadProceduralRules(root: string): { meta: FileMeta; rows: ProceduralRuleRow[] } {
  const p = join(brainDataDir(root), "procedural_memory.yaml");
  const meta = fileMeta(p);
  if (meta.missing) return { meta, rows: [] };
  type R = {
    id: string;
    when?: string;
    do?: string;
    learned_at?: string;
    confidence?: string;
    source?: string;
    applies_to?: string[];
    status?: string;
  };
  const doc = yaml.load(readFileSync(p, "utf-8")) as { rules?: R[] };
  const rows: ProceduralRuleRow[] = (doc.rules ?? []).map((r) => ({
    id: r.id,
    when: r.when ?? "",
    do: r.do ?? "",
    learned_at: r.learned_at ?? "",
    status: r.status ?? r.confidence ?? "—",
    source: r.source ?? "",
    confidence: r.confidence,
  }));
  return { meta, rows };
}

export async function fetchBrainImprovementIndex(): Promise<{
  data: BrainImprovementResponse | null;
  error: string | null;
}> {
  const auth = getBrainAdminFetchOptions();
  if (!auth.ok) {
    return { data: null, error: null };
  }
  const res = await fetch(`${auth.root}/admin/brain-improvement-index`, {
    headers: { "X-Brain-Secret": auth.secret },
    cache: "no-store",
  });
  if (!res.ok) {
    return { data: null, error: `HTTP ${res.status}` };
  }
  const json = (await res.json()) as {
    success?: boolean;
    data?: BrainImprovementResponse;
    error?: string;
  };
  if (json.success === false || json.data == null) {
    return { data: null, error: json.error ?? "invalid payload" };
  }
  return { data: json.data, error: null };
}

export async function loadSelfImprovementPayload(): Promise<SelfImprovementPayload> {
  const repoRoot = resolveMonorepoRoot();
  if (!repoRoot) {
    const bi = await fetchBrainImprovementIndex();
    return {
      repoRoot: null,
      learning: emptyLearning(),
      promotions: {
        currentTier: "—",
        promotionThreshold: BII_FORMULA.PROMOTION_THRESHOLD,
        cleanMergesCurrentTier: 0,
        promotionsMeta: fileMeta(""),
        reverts: [],
        graduationHistory: [],
      },
      outcomes: { meta: fileMeta(""), rows: [] },
      retros: { meta: fileMeta(""), rows: [] },
      schedulers: { meta: fileMeta(""), rows: [] },
      procedural: { meta: fileMeta(""), rows: [] },
      brainImprovement: bi.data,
      brainImprovementError: bi.error,
    };
  }

  const learning = aggregateLearning(repoRoot);
  const promotions = loadPromotions(repoRoot);
  const outcomes = loadOutcomes(repoRoot);
  const retros = loadRetros(repoRoot);
  const schedRows = parseSchedulerModules(repoRoot);
  const procedural = loadProceduralRules(repoRoot);
  const schedMeta = loadSchedulerState(repoRoot);
  const bi = await fetchBrainImprovementIndex();

  return {
    repoRoot,
    learning,
    promotions,
    outcomes,
    retros,
    schedulers: { meta: schedMeta, rows: schedRows },
    procedural,
    brainImprovement: bi.data,
    brainImprovementError: bi.error,
  };
}

export { BII_FORMULA } from "@/lib/brain-improvement-formula";
