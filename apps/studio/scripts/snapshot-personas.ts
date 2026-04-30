/**
 * Build-time snapshot of Brain persona data:
 * - .cursor/rules/*.mdc  (persona registry)
 * - apis/brain/data/agent_dispatch_log.json
 * - apis/brain/data/pr_outcomes.json
 * - apis/brain/data/self_merge_promotions.json
 * - docs/AI_MODEL_REGISTRY.md
 *
 * Writes apps/studio/src/data/personas-snapshot.json with a
 * PersonasPagePayload-compatible shape (minus runtime-only fields).
 *
 * Run via: tsx scripts/snapshot-personas.ts
 * Auto-run during: prebuild (see package.json)
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

// gray-matter is a runtime dep so available here too
import matter from "gray-matter";
// js-yaml v4 is a runtime dep (in package.json); use it as the gray-matter engine
// to avoid gray-matter's bundled js-yaml v3 choking on glob patterns like **/*.{ts,tsx}
import yaml from "js-yaml";

const matterOpts: matter.GrayMatterOption<string, matter.GrayMatterOption<string, never>> = {
  engines: {
    yaml: {
      parse: (s: string) => yaml.load(s) as Record<string, unknown>,
      stringify: (o: object) => yaml.dump(o),
    },
  },
};

/**
 * Some .mdc files have frontmatter with unquoted glob patterns (e.g. globs: **\/*.ts)
 * which both js-yaml v3 and v4 reject as alias syntax. This pre-processes the raw
 * file content to quote those values before passing to gray-matter.
 */
function sanitizeMdcGlobs(raw: string): string {
  if (!raw.startsWith("---")) return raw;
  const end = raw.indexOf("\n---\n", 4);
  if (end === -1) return raw;
  const frontmatter = raw.slice(0, end + 5);
  const rest = raw.slice(end + 5);
  // Quote any unquoted value that starts with * (glob patterns)
  const sanitized = frontmatter.replace(
    /^(\s*\w[^:]*:\s)(\*[^\n'"]+)$/gm,
    (_match, key: string, val: string) => `${key}"${val}"`,
  );
  return sanitized + rest;
}

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const STUDIO_ROOT = path.join(__dirname, "..");
const REPO_ROOT = path.join(STUDIO_ROOT, "..", "..");
const OUT_PATH = path.join(STUDIO_ROOT, "src/data/personas-snapshot.json");

// ─── tiny local copies of helpers from personas-pure (no import from src/) ──

function extractMainHeading(content: string): string | null {
  const m = content.match(/^#\s+(.+)/m);
  return m ? m[1].trim() : null;
}

function extractModelAssignmentSection(content: string): string | null {
  const m = content.match(/#+\s*Model\s+Assignment[\s\S]*?(?=\n#+\s|\n---|\s*$)/i);
  return m ? m[0].trim() : null;
}

// ─── type stubs ────────────────────────────────────────────────────────────

type BrainDataSourceStatus =
  | { ok: true; path: string }
  | { ok: false; path: string; message: string };

type PersonaRegistryRow = {
  personaId: string;
  name: string;
  description: string | null;
  relativePath: string;
  modelAssignment: string | null;
  routingActive: boolean;
};

type MarkdownTable = {
  title: string;
  headers: string[];
  rows: string[][];
};

type EaRoutingRow = {
  tag: string;
  routingTarget: string;
};

type PersonasSnapshot = {
  generatedFrom: string[];
  registry: PersonaRegistryRow[];
  openRoles: Pick<PersonaRegistryRow, "personaId" | "name" | "relativePath">[];
  cost: {
    dispatchSource: BrainDataSourceStatus;
    outcomesSource: BrainDataSourceStatus;
    personaHasAttribution: boolean;
    attributionNote: string | null;
    avgTokensNote: string | null;
    rows: {
      personaId: string;
      dispatch7d: number | null;
      dispatch30d: number | null;
      avgTokensPerDispatch: number | null;
      costNote: string;
    }[];
    globalDispatch7d: number | null;
    globalDispatch30d: number | null;
  };
  routing: { source: BrainDataSourceStatus; rows: EaRoutingRow[] };
  activity: {
    source: BrainDataSourceStatus;
    rows: {
      dispatchedAt: string;
      persona: string;
      workstreamTag: string;
      successLabel: string;
      costLabel: string;
    }[];
    note: string | null;
  };
  modelRegistry: { source: BrainDataSourceStatus; tables: MarkdownTable[] };
  promotions: {
    source: BrainDataSourceStatus;
    promotions: Record<string, unknown>[];
  };
};

// ─── helpers ───────────────────────────────────────────────────────────────

function readJsonIfPresent<T>(
  filePath: string,
): { status: BrainDataSourceStatus; data: T | null } {
  if (!fs.existsSync(filePath)) {
    return {
      status: { ok: false, path: filePath, message: "File not found on disk." },
      data: null,
    };
  }
  try {
    const raw = fs.readFileSync(filePath, "utf8");
    return { status: { ok: true, path: filePath }, data: JSON.parse(raw) as T };
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

function parseMarkdownTables(content: string): MarkdownTable[] {
  const sections = content.split(/\n(?=#+\s)/);
  const tables: MarkdownTable[] = [];
  for (const section of sections) {
    const headingMatch = section.match(/^#+\s+(.+)/);
    const title = headingMatch ? headingMatch[1].trim() : "Untitled";
    const tableLines = section
      .split("\n")
      .filter((l) => l.trim().startsWith("|"));
    if (tableLines.length < 2) continue;
    const headerCells = tableLines[0]
      .split("|")
      .map((c) => c.trim())
      .filter(Boolean);
    const dataLines = tableLines.slice(2);
    const rows = dataLines
      .map((l) =>
        l
          .split("|")
          .map((c) => c.trim())
          .filter(Boolean),
      )
      .filter((r) => r.length > 0);
    tables.push({ title, headers: headerCells, rows });
  }
  return tables;
}

function parseEaTagRouting(content: string): EaRoutingRow[] {
  const rows: EaRoutingRow[] = [];
  const lines = content.split("\n").filter((l) => l.trim().startsWith("|"));
  for (const line of lines) {
    const cells = line
      .split("|")
      .map((c) => c.trim())
      .filter(Boolean);
    if (cells.length < 2) continue;
    const tag = cells[0];
    if (tag.toLowerCase().startsWith("tag") || /^[-:]+$/.test(tag)) continue;
    rows.push({ tag, routingTarget: cells[1] });
  }
  return rows;
}

// ─── main ──────────────────────────────────────────────────────────────────

function run(): void {
  const rulesDir = path.join(REPO_ROOT, ".cursor", "rules");
  const dispatchPath = path.join(REPO_ROOT, "apis", "brain", "data", "agent_dispatch_log.json");
  const outcomesPath = path.join(REPO_ROOT, "apis", "brain", "data", "pr_outcomes.json");
  const promotionsPath = path.join(REPO_ROOT, "apis", "brain", "data", "self_merge_promotions.json");
  const registryMdPath = path.join(REPO_ROOT, "docs", "AI_MODEL_REGISTRY.md");
  const eaMdcPath = path.join(rulesDir, "ea.mdc");

  // ── Registry ─────────────────────────────────────────────────────────────
  const registry: PersonaRegistryRow[] = [];
  if (!fs.existsSync(rulesDir)) {
    process.stderr.write(`snapshot-personas: rules dir not found: ${rulesDir}\n`);
    process.exit(1);
  }
  for (const file of fs.readdirSync(rulesDir).sort()) {
    if (!file.endsWith(".mdc")) continue;
    const full = path.join(rulesDir, file);
    const raw = fs.readFileSync(full, "utf8");
    const { data, content } = matter(sanitizeMdcGlobs(raw), matterOpts);
    const personaId = file.replace(/\.mdc$/i, "");
    const fm = data as Record<string, unknown>;
    const description = typeof fm.description === "string" ? fm.description : null;
    const alwaysApply = fm.alwaysApply === true;
    const heading = extractMainHeading(content);
    const name =
      heading?.replace(/^Paperwork Labs —\s*/i, "").replace(/\s*—.*$/, "").trim() ||
      personaId.replace(/-/g, " ");
    registry.push({
      personaId,
      name,
      description,
      relativePath: path.join(".cursor", "rules", file),
      modelAssignment: extractModelAssignmentSection(content),
      routingActive: alwaysApply,
    });
  }

  // ── Dispatch & outcomes ──────────────────────────────────────────────────
  type DispatchRecord = {
    dispatch_id?: string;
    dispatched_at?: string;
    agent_model?: string;
    persona_slug?: string;
    persona?: string;
    persona_pin?: string;
    workstream_id?: string;
    workstream_type?: string;
    outcome?: {
      ci_initial_pass?: boolean | null;
      review_pass?: boolean | null;
      merged_at?: string | null;
      reverted?: boolean | null;
      [key: string]: unknown;
    };
    [key: string]: unknown;
  };
  type PrOutcomeRecord = {
    tokens_input?: number;
    tokens_output?: number;
    [key: string]: unknown;
  };
  const dispatchRead = readJsonIfPresent<{ dispatches?: DispatchRecord[] }>(dispatchPath);
  const outcomesRead = readJsonIfPresent<{ outcomes?: PrOutcomeRecord[] }>(outcomesPath);
  const promotionsRead = readJsonIfPresent<{ promotions?: unknown[] }>(promotionsPath);

  const dispatches = dispatchRead.data?.dispatches ?? [];
  const outcomes = outcomesRead.data?.outcomes ?? [];

  // ── Model registry ────────────────────────────────────────────────────────
  let registryMd = "";
  if (fs.existsSync(registryMdPath)) {
    try {
      registryMd = fs.readFileSync(registryMdPath, "utf8");
    } catch {
      registryMd = "";
    }
  }

  let modelRegistrySource: BrainDataSourceStatus;
  let modelRegistryTables: MarkdownTable[];
  if (!registryMd) {
    modelRegistrySource = {
      ok: false,
      path: registryMdPath,
      message: "docs/AI_MODEL_REGISTRY.md not found at snapshot time.",
    };
    modelRegistryTables = [];
  } else {
    const { content } = matter(registryMd);
    modelRegistrySource = { ok: true, path: registryMdPath };
    modelRegistryTables = parseMarkdownTables(content);
  }

  // ── Routing ───────────────────────────────────────────────────────────────
  let routingSource: BrainDataSourceStatus;
  let routingRows: EaRoutingRow[] = [];
  if (!fs.existsSync(eaMdcPath)) {
    routingSource = { ok: false, path: eaMdcPath, message: "ea.mdc not found." };
  } else {
    try {
      const raw = fs.readFileSync(eaMdcPath, "utf8");
      const { content } = matter(sanitizeMdcGlobs(raw), matterOpts);
      routingRows = parseEaTagRouting(content);
      routingSource = { ok: true, path: eaMdcPath };
    } catch (e) {
      routingSource = {
        ok: false,
        path: eaMdcPath,
        message: e instanceof Error ? e.message : "Read failed",
      };
    }
  }

  // ── Cost payload ──────────────────────────────────────────────────────────
  const dispatchPersonaId = (d: DispatchRecord): string | null =>
    (typeof d.persona_slug === "string" && d.persona_slug) ||
    (typeof d.persona === "string" && d.persona) ||
    (typeof d.persona_pin === "string" && d.persona_pin) ||
    null;

  let attributed = false;
  for (const d of dispatches) {
    if (dispatchPersonaId(d)) {
      attributed = true;
      break;
    }
  }

  // Strip dispatch counts that depend on current date — snapshot is static.
  // Consumers can recompute from the raw dispatches array if needed.
  const costRows = registry.map((r) => ({
    personaId: r.personaId,
    dispatch7d: null as number | null,
    dispatch30d: null as number | null,
    avgTokensPerDispatch: null as number | null,
    costNote: !registryMd
      ? "rate unknown — docs/AI_MODEL_REGISTRY.md not present at snapshot time."
      : "see docs/AI_MODEL_REGISTRY.md",
  }));

  let avgTokensNote: string | null = null;
  if (!outcomesRead.status.ok) {
    avgTokensNote = null;
  } else if (outcomes.length === 0) {
    avgTokensNote =
      "No merged PR outcomes — apis/brain/data/pr_outcomes.json has outcomes: [].";
  } else {
    const withTokens = outcomes.filter(
      (o) => typeof o.tokens_input === "number" && typeof o.tokens_output === "number",
    );
    if (withTokens.length === 0) {
      avgTokensNote =
        "No token counts — pr_outcomes.json rows omit tokens_input/tokens_output; average tokens cannot be computed.";
    }
  }

  const attributionNote = attributed
    ? null
    : "Dispatch log entries do not include `persona_slug` / `persona` / `persona_pin`; per-persona dispatch counts cannot be attributed.";

  // ── Activity feed ─────────────────────────────────────────────────────────
  const sortedDispatches = [...dispatches].sort((a, b) => {
    const ta = typeof a.dispatched_at === "string" ? a.dispatched_at : "";
    const tb = typeof b.dispatched_at === "string" ? b.dispatched_at : "";
    return tb.localeCompare(ta);
  });

  const activityRows = sortedDispatches.slice(0, 50).map((d) => {
    const ts = typeof d.dispatched_at === "string" ? d.dispatched_at : "—";
    const persona =
      dispatchPersonaId(d) ??
      (typeof d.agent_model === "string" ? `model:${d.agent_model}` : "not attributed");
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
    return { dispatchedAt: ts, persona, workstreamTag: ws, successLabel, costLabel: "—" };
  });

  const activityNote =
    dispatches.length === 0
      ? "Dispatch log is empty — no rows in apis/brain/data/agent_dispatch_log.json yet."
      : null;

  // ── Promotions ────────────────────────────────────────────────────────────
  const rawPromotions = promotionsRead.data?.promotions ?? [];
  const promotions: Record<string, unknown>[] = [];
  if (Array.isArray(rawPromotions)) {
    for (const item of rawPromotions) {
      if (item && typeof item === "object" && !Array.isArray(item)) {
        promotions.push(item as Record<string, unknown>);
      }
    }
  }

  // ── Open roles ────────────────────────────────────────────────────────────
  const openRoles = registry
    .filter((r) => r.modelAssignment === null || r.modelAssignment.trim() === "")
    .map((r) => ({
      personaId: r.personaId,
      name: r.name,
      relativePath: r.relativePath,
    }));

  // ── Assemble snapshot ─────────────────────────────────────────────────────
  const snapshot: PersonasSnapshot = {
    generatedFrom: [
      ".cursor/rules/*.mdc",
      "apis/brain/data/agent_dispatch_log.json",
      "apis/brain/data/pr_outcomes.json",
      "apis/brain/data/self_merge_promotions.json",
      "docs/AI_MODEL_REGISTRY.md",
    ],
    registry,
    openRoles,
    cost: {
      dispatchSource: dispatchRead.status,
      outcomesSource: outcomesRead.status,
      personaHasAttribution: attributed,
      attributionNote,
      avgTokensNote,
      rows: costRows,
      globalDispatch7d: null,
      globalDispatch30d: null,
    },
    routing: { source: routingSource, rows: routingRows },
    activity: {
      source: dispatchRead.status,
      rows: activityRows,
      note: activityNote,
    },
    modelRegistry: {
      source: modelRegistrySource,
      tables: modelRegistryTables,
    },
    promotions: {
      source: promotionsRead.status,
      promotions,
    },
  };

  fs.mkdirSync(path.dirname(OUT_PATH), { recursive: true });
  fs.writeFileSync(OUT_PATH, JSON.stringify(snapshot, null, 2) + "\n");
  process.stdout.write(
    `snapshot-personas: wrote ${OUT_PATH} (${registry.length} personas, ${activityRows.length} activity rows)\n`,
  );
}

run();
