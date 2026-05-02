#!/usr/bin/env node
/**
 * Sync Cursor `.mdc` rules and Brain persona YAML specs from the unified employees table.
 *
 * Required env vars:
 * BRAIN_API_URL — e.g. https://brain-api.onrender.com (with or without trailing /api/v1)
 * BRAIN_API_SECRET — shared secret for Brain admin endpoints (X-Brain-Secret header)
 *
 * Reads `GET …/admin/employees`, then full detail per slug via `GET …/admin/employees/{slug}`.
 *
 * YAML output targets `apis/brain/app/personas/spec.py` (`PersonaSpec`): `name` is the persona slug
 * (matching the `.yaml` stem), `default_model` is the primary model, etc.
 *
 * Run: `pnpm exec tsx scripts/employees-sync.ts [--dry-run] [--diff]`
 */

import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "..");

const PERSONA_KIND = "ai_persona";

const ALLOWED_SLUG = /^[a-z0-9_-]{1,64}$/;

type BrainEnvelope<T> = {
  success: boolean;
  data?: T;
  error?: string | null;
};

type EmployeeListItem = {
  slug: string;
  kind: string;
};

type EmployeeFull = EmployeeListItem & {
  role_title: string;
  team: string;
  display_name: string | null;
  description: string;
  default_model: string;
  escalation_model: string | null;
  escalate_if: string[];
  requires_tools: boolean;
  daily_cost_ceiling_usd: number | null;
  owner_channel: string | null;
  mode: string | null;
  tone_prefix: string | null;
  proactive_cadence: string | null;
  max_output_tokens: number | null;
  requests_per_minute: number | null;
  cursor_description: string | null;
  cursor_globs: string[];
  cursor_always_apply: boolean;
  body_markdown: string | null;
};

type EmployeeListPayload = { employees: EmployeeListItem[] };
type EmployeeDetailPayload = { employee: EmployeeFull };

function sanitizeEnv(val: string | undefined): string {
  if (!val) return "";
  return val.trim().replace(/\\n$/, "").replace(/\/+$/, "");
}

/** Match `apps/studio/src/lib/brain-admin-proxy.ts` — admin routes live under `/api/v1`. */
function brainApiV1Root(): string | null {
  const raw = sanitizeEnv(process.env.BRAIN_API_URL);
  if (!raw) return null;
  return raw.endsWith("/api/v1") ? raw : `${raw}/api/v1`;
}

function die(msg: string): never {
  console.error(msg);
  process.exit(1);
}

function parseFlags(argv: string[]): { dryRun: boolean; diff: boolean } {
  return {
    dryRun: argv.includes("--dry-run"),
    diff: argv.includes("--diff"),
  };
}

async function brainFetchJson<T>(
  url: string,
  secret: string,
  ctx: string
): Promise<T> {
  let res: Response;
  try {
    res = await fetch(url, {
      headers: { "X-Brain-Secret": secret },
    });
  } catch (err) {
    die(`${ctx}: network error — ${err instanceof Error ? err.message : String(err)}`);
  }
  const raw = await res.text();
  let body: BrainEnvelope<T>;
  try {
    body = JSON.parse(raw) as BrainEnvelope<T>;
  } catch {
    die(`${ctx}: invalid JSON (${res.status}) — ${raw.slice(0, 200)}`);
  }
  if (!res.ok || !body.success || body.data === undefined || body.data === null) {
    const detail = body.error ?? raw.slice(0, 400);
    die(`${ctx}: ${res.status} — ${detail}`);
  }
  return body.data as T;
}

function escapeYamlDoubleQuotedScalar(s: string): string {
  return `"${s
    .replace(/\\/g, "\\\\")
    .replace(/"/g, '\\"')
    .replace(/\r/g, "")
    .replace(/\n/g, "\\n")}"`;
}

/** Block scalar safe for YAML `|` blocks (trim trailing newline for consistency). */
function yamlLiteralBlock(body: string): string {
  const lines = body.split("\n").map((ln) =>
    ln.length === 0 ? "" : ln.replace(/\s+$/, "")
  );
  while (lines.length && lines.at(-1) === "") lines.pop();
  const indented =
    lines.length === 0 ? "" : lines.map((ln) => `  ${ln}`).join("\n");
  return `|\n${indented}`;
}

/** Emit persona YAML aligned with Brain `PersonaSpec` (`app/personas/spec.py`). */
function buildPersonaYaml(emp: EmployeeFull): string {
  const lines: string[] = [];
  lines.push(`name: ${emp.slug}`);
  lines.push(`description: ${escapeYamlDoubleQuotedScalar(emp.description ?? "")}`);
  lines.push(`default_model: ${emp.default_model}`);

  if (emp.escalation_model !== null && emp.escalation_model !== "") {
    lines.push(`escalation_model: ${emp.escalation_model}`);
  }

  const tags = (emp.escalate_if ?? []).map(String);
  if (tags.length === 0) {
    lines.push("escalate_if: []");
  } else {
    lines.push(`escalate_if:`);
    for (const t of tags) {
      lines.push(`- ${escapeYamlDoubleQuotedScalar(t)}`);
    }
  }

  lines.push(`requires_tools: ${emp.requires_tools ? "true" : "false"}`);

  if (emp.daily_cost_ceiling_usd !== null && emp.daily_cost_ceiling_usd !== undefined) {
    lines.push(`daily_cost_ceiling_usd: ${emp.daily_cost_ceiling_usd}`);
  }

  if (emp.owner_channel !== null && emp.owner_channel !== "") {
    lines.push(`owner_channel: ${emp.owner_channel}`);
  }

  if (emp.mode === "task") {
    lines.push("mode: task");
  }

  const cadenceCandidates = ["never", "daily", "weekly", "monthly"] as const;
  const cadenceRaw = emp.proactive_cadence ?? "never";
  const cadence =
    cadenceCandidates.find((c) => c === cadenceRaw.trim()) ??
    cadenceCandidates[0];
  if (cadence !== "never") {
    lines.push(`proactive_cadence: ${cadence}`);
  }

  if (emp.tone_prefix !== null && emp.tone_prefix !== "") {
    lines.push("tone_prefix: " + yamlLiteralBlock(emp.tone_prefix.trimEnd()));
  }

  if (emp.max_output_tokens !== null && emp.max_output_tokens !== undefined) {
    lines.push(`max_output_tokens: ${emp.max_output_tokens}`);
  }

  if (emp.requests_per_minute !== null && emp.requests_per_minute !== undefined) {
    lines.push(`requests_per_minute: ${emp.requests_per_minute}`);
  }

  return `${lines.join("\n")}\n`;
}

/** Build Cursor `.mdc` frontmatter + body */
function buildMdcContent(emp: EmployeeFull): string {
  const desc =
    emp.cursor_description !== null &&
    emp.cursor_description !== undefined &&
    emp.cursor_description.trim() !== ""
      ? emp.cursor_description
      : emp.description ?? "";

  const fm: string[] = ["---"];

  fm.push(`description: ${escapeYamlDoubleQuotedScalar(desc)}`);

  const globs = (emp.cursor_globs ?? []).filter((g) => typeof g === "string" && g.trim() !== "");
  if (globs.length > 0) {
    fm.push(`globs: ${JSON.stringify(globs)}`);
  }

  if (emp.cursor_always_apply === true) {
    fm.push("alwaysApply: true");
  }

  fm.push("---");

  const body = (emp.body_markdown ?? "").trimEnd();
  return `${fm.join("\n")}\n\n${body}\n`;
}

function slugOk(slug: string): boolean {
  return ALLOWED_SLUG.test(slug);
}

function ensureTrailingNewline(s: string): string {
  return s.endsWith("\n") ? s : `${s}\n`;
}

function unifiedDiff(existing: string | null, next: string, relPath: string): string | null {
  const aText = existing ?? "";
  if (ensureTrailingNewline(aText) === ensureTrailingNewline(next)) return null;

  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "emp-sync-diff-"));
  const a = path.join(dir, "a");
  const b = path.join(dir, "b");

  try {
    fs.writeFileSync(a, ensureTrailingNewline(aText));
    fs.writeFileSync(b, ensureTrailingNewline(next));
    let patch: string;
    try {
      patch = execFileSync("diff", ["-u", a, b], {
        encoding: "utf-8",
        maxBuffer: 1024 * 1024,
      });
    } catch (err: unknown) {
      const typed = err as { status?: number; stdout?: string };
      if (typed.status !== 1 || typeof typed.stdout !== "string") {
        throw err;
      }
      patch = typed.stdout;
    }

    const lines = patch.split("\n");
    if (lines.length >= 2) {
      lines[0] = `--- ${relPath}\t(existing)`;
      lines[1] = `+++ ${relPath}\t(generated)`;
    }
    return lines.join("\n");
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
}

function readIfExists(abs: string): string | null {
  try {
    return fs.readFileSync(abs, "utf-8");
  } catch {
    return null;
  }
}

async function main(): Promise<void> {
  const { dryRun, diff } = parseFlags(process.argv);

  const apiRoot = brainApiV1Root();
  const secret = sanitizeEnv(process.env.BRAIN_API_SECRET);

  if (!apiRoot) {
    die(
      "BRAIN_API_URL is not set or empty. Export the Brain base URL " +
        "(e.g. https://brain-api.onrender.com — /api/v1 is appended automatically)."
    );
  }
  if (!secret) {
    die("BRAIN_API_SECRET is not set or empty.");
  }

  const listUrl = `${apiRoot}/admin/employees`;

  const listData = await brainFetchJson<EmployeeListPayload>(
    listUrl,
    secret,
    "GET /admin/employees"
  );

  const employeesFull: EmployeeFull[] = [];

  for (const item of listData.employees) {
    const detailUrl = `${apiRoot}/admin/employees/${encodeURIComponent(item.slug)}`;
    const detail = await brainFetchJson<EmployeeDetailPayload>(
      detailUrl,
      secret,
      `GET /admin/employees/${item.slug}`
    );
    employeesFull.push(detail.employee);
  }

  let wouldMdc = 0;
  let wouldYaml = 0;
  let skippedEmptyBody = 0;

  const ops: {
    slug: string;
    relPath: string;
    absPath: string;
    content: string;
    skipWrite: boolean;
  }[] = [];

  for (const emp of employeesFull) {
    if (!slugOk(emp.slug)) {
      console.warn(`Skipping unsafe slug "${emp.slug}" (allowed: ${ALLOWED_SLUG})`);
      continue;
    }

    const mdPath = `.cursor/rules/${emp.slug}.mdc`;
    const absMd = path.join(root, mdPath);

    const bodyEmpty =
      emp.body_markdown === null ||
      emp.body_markdown === undefined ||
      String(emp.body_markdown).trim() === "";

    if (bodyEmpty) {
      skippedEmptyBody++;
      ops.push({
        slug: emp.slug,
        relPath: mdPath,
        absPath: absMd,
        content: "",
        skipWrite: true,
      });
    } else {
      const mdcContent = buildMdcContent(emp);
      ops.push({
        slug: emp.slug,
        relPath: mdPath,
        absPath: absMd,
        content: mdcContent,
        skipWrite: false,
      });
      wouldMdc++;
    }

    if (emp.kind === PERSONA_KIND) {
      const yPath = `apis/brain/app/personas/specs/${emp.slug}.yaml`;
      const absY = path.join(root, yPath);
      ops.push({
        slug: emp.slug,
        relPath: yPath,
        absPath: absY,
        content: buildPersonaYaml(emp),
        skipWrite: false,
      });
      wouldYaml++;
    }
  }

  if (dryRun) {
    console.log(
      `[dry-run] Would sync ${wouldMdc} .mdc file(s); ${wouldYaml} persona YAML spec(s). ` +
        `Skipped ${skippedEmptyBody} employee(s) with empty body_markdown for .mdc.`
    );
    for (const op of ops) {
      if (op.skipWrite) {
        console.log(`  skip: ${op.relPath} — empty body_markdown`);
      } else {
        console.log(`  write: ${op.relPath} (${op.content.split("\n").length} lines)`);
      }
    }
  }

  const diffChunks: string[] = [];

  for (const op of ops) {
    if (op.skipWrite) continue;
    if (dryRun || diff) {
      const have = readIfExists(op.absPath);
      const d = unifiedDiff(have, op.content, op.relPath);
      if (d !== null && diff) {
        diffChunks.push(d.endsWith("\n") ? d : `${d}\n`);
      }
    }
  }

  if (diff && diffChunks.length === 0) {
    console.log("[diff] No differences — generated content matches disk.");
  }
  if (diff && diffChunks.length > 0) {
    process.stdout.write(diffChunks.join("\n"));
  }

  if (!dryRun) {
    for (const op of ops) {
      if (op.skipWrite) continue;
      fs.mkdirSync(path.dirname(op.absPath), { recursive: true });
      fs.writeFileSync(op.absPath, op.content, "utf-8");
    }
    console.log(`Synced ${wouldMdc} .mdc files, ${wouldYaml} persona specs`);
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
