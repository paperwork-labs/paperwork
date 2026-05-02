#!/usr/bin/env node
/**
 * Seed Brain `employees` from persona YAML specs + `.cursor/rules/*.mdc`.
 *
 * Env:
 *   BRAIN_API_URL — base URL (/api/v1 is appended when missing)
 *   BRAIN_API_SECRET — X-Brain-Secret for admin routes
 *
 * Run: `pnpm seed:employees` or `pnpm exec tsx scripts/seed-employees.ts`
 *
 * Idempotent: GET /admin/employees/{slug}; PATCH if present, else POST.
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import yaml from "js-yaml";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "..");

const TEAM_MAP: Record<string, string> = {
  "agent-ops": "Engineering",
  brand: "Growth",
  cfo: "Finance",
  cpa: "Finance",
  ea: "Executive Council",
  engineering: "Engineering",
  growth: "Growth",
  "infra-ops": "Engineering",
  legal: "Legal & Compliance",
  partnerships: "Growth",
  qa: "Engineering",
  social: "Growth",
  strategy: "Executive Council",
  "tax-domain": "Finance",
  trading: "Trading",
  ux: "Product",
};

/** PersonaSpec YAML uses `name` as slug; these are human-readable titles for People UI. */
const ROLE_TITLE_MAP: Record<string, string> = {
  "agent-ops": "Agent Operations Lead",
  brand: "Brand Lead",
  cfo: "Chief Financial Officer",
  cpa: "CPA Advisor",
  ea: "Executive Assistant",
  engineering: "Engineering Lead",
  growth: "Growth Lead",
  "infra-ops": "Infrastructure & Operations Lead",
  legal: "Legal & Compliance Lead",
  partnerships: "Partnerships Lead",
  qa: "QA & Security Lead",
  social: "Social & Creator Lead",
  strategy: "Strategy Lead",
  "tax-domain": "Tax Domain Lead",
  trading: "Trading Lead",
  ux: "UX Lead",
};

type BrainEnvelope<T> = {
  success: boolean;
  data?: T;
  error?: string | null;
};

type PersonaYaml = {
  name: string;
  description: string;
  default_model: string;
  escalation_model?: string | null;
  escalate_if?: unknown[];
  requires_tools?: boolean;
  daily_cost_ceiling_usd?: number | null;
  owner_channel?: string | null;
  mode?: string | null;
  tone_prefix?: string | null;
  proactive_cadence?: string | null;
  max_output_tokens?: number | null;
  requests_per_minute?: number | null;
};

type MdcParsed = {
  cursor_description: string | null;
  cursor_globs: unknown[];
  cursor_always_apply: boolean;
  body_markdown: string | null;
};

type EmployeeCreatePayload = {
  slug: string;
  kind: string;
  role_title: string;
  team: string;
  description: string;
  default_model: string;
  display_name: string | null;
  tagline: string | null;
  avatar_emoji: string | null;
  voice_signature: string | null;
  named_by_self: boolean;
  reports_to: string | null;
  manages: unknown[];
  escalation_model: string | null;
  escalate_if: unknown[];
  requires_tools: boolean;
  daily_cost_ceiling_usd: number | null;
  owner_channel: string | null;
  mode: string | null;
  tone_prefix: string | null;
  proactive_cadence: string | null;
  max_output_tokens: number | null;
  requests_per_minute: number | null;
  cursor_description: string | null;
  cursor_globs: unknown[];
  cursor_always_apply: boolean;
  owned_rules: unknown[];
  owned_runbooks: unknown[];
  owned_workflows: unknown[];
  owned_skills: unknown[];
  body_markdown: string | null;
  metadata: Record<string, unknown>;
};

function sanitizeEnv(val: string | undefined): string {
  if (!val) return "";
  return val.trim().replace(/\\n$/, "").replace(/\/+$/, "");
}

function brainApiV1Root(): string | null {
  const raw = sanitizeEnv(process.env.BRAIN_API_URL);
  if (!raw) return null;
  return raw.endsWith("/api/v1") ? raw : `${raw}/api/v1`;
}

function die(msg: string, code = 1): never {
  console.error(msg);
  process.exit(code);
}

async function brainFetch(
  apiRoot: string,
  secret: string,
  method: string,
  pathSuffix: string,
  body?: unknown,
): Promise<Response> {
  const url = `${apiRoot}${pathSuffix}`;
  const headers: Record<string, string> = { "X-Brain-Secret": secret };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  return fetch(url, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: "no-store",
  });
}

async function parseSuccessEnvelope<T>(label: string, res: Response): Promise<T> {
  const text = await res.text();
  let json: unknown;
  try {
    json = JSON.parse(text);
  } catch {
    throw new Error(`${label}: response is not JSON (${text.slice(0, 200)})`);
  }
  const env = json as BrainEnvelope<T>;
  if (!res.ok || !env.success || env.data === undefined || env.data === null) {
    throw new Error(`${label}: HTTP ${res.status} — ${env.error ?? text.slice(0, 400)}`);
  }
  return env.data as T;
}

function parseMdcFile(absPath: string): MdcParsed | null {
  let raw: string;
  try {
    raw = fs.readFileSync(absPath, "utf-8");
  } catch {
    return null;
  }

  const fmMatch = raw.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n([\s\S]*)$/);
  if (!fmMatch) {
    return {
      cursor_description: null,
      cursor_globs: [],
      cursor_always_apply: false,
      body_markdown: raw.trim() === "" ? null : raw.trimEnd(),
    };
  }

  const fmYaml = fmMatch[1] ?? "";
  const body = (fmMatch[2] ?? "").trimEnd();

  let fm: Record<string, unknown> = {};
  try {
    const loaded = yaml.load(fmYaml);
    if (loaded !== null && typeof loaded === "object" && !Array.isArray(loaded)) {
      fm = loaded as Record<string, unknown>;
    }
  } catch {
    console.warn(`Warning: failed to parse frontmatter YAML in ${absPath}`);
  }

  const desc = fm.description;
  const cursor_description =
    typeof desc === "string" && desc.trim() !== "" ? desc.trim() : null;

  let cursor_globs: unknown[] = [];
  const globsRaw = fm.globs;
  if (Array.isArray(globsRaw)) cursor_globs = globsRaw;
  else if (typeof globsRaw === "string" && globsRaw.trim() !== "") {
    try {
      const parsed = JSON.parse(globsRaw) as unknown;
      if (Array.isArray(parsed)) cursor_globs = parsed;
    } catch {
      cursor_globs = [globsRaw];
    }
  }

  const always = fm.alwaysApply ?? fm.always_apply;
  const cursor_always_apply = always === true;

  return {
    cursor_description,
    cursor_globs,
    cursor_always_apply,
    body_markdown: body.trim() === "" ? null : body,
  };
}

function listPersonaSpecFiles(specsDir: string): string[] {
  if (!fs.existsSync(specsDir)) {
    die(`Persona specs directory missing: ${specsDir}`);
  }
  return fs
    .readdirSync(specsDir)
    .filter((f) => f.endsWith(".yaml") || f.endsWith(".yml"))
    .map((f) => path.join(specsDir, f))
    .sort();
}

function loadPersonaYaml(absPath: string): PersonaYaml {
  const raw = fs.readFileSync(absPath, "utf-8");
  const loaded = yaml.load(raw);
  if (loaded === null || typeof loaded !== "object" || Array.isArray(loaded)) {
    die(`Invalid persona YAML (not an object): ${absPath}`);
  }
  const spec = loaded as PersonaYaml;
  if (typeof spec.name !== "string" || typeof spec.description !== "string") {
    die(`Persona YAML missing name/description: ${absPath}`);
  }
  if (typeof spec.default_model !== "string") {
    die(`Persona YAML missing default_model: ${absPath}`);
  }
  return spec;
}

function asNullableString(v: unknown): string | null {
  if (v === undefined || v === null) return null;
  if (typeof v === "string") return v;
  return String(v);
}

function asNullableNumber(v: unknown): number | null {
  if (v === undefined || v === null) return null;
  if (typeof v === "number" && Number.isFinite(v)) return v;
  return null;
}

function buildAiPersonaPayload(
  slug: string,
  spec: PersonaYaml,
  mdc: MdcParsed | null,
): EmployeeCreatePayload {
  const team = TEAM_MAP[slug];
  if (!team) die(`TEAM_MAP missing entry for slug "${slug}"`);

  const role_title = ROLE_TITLE_MAP[slug];
  if (!role_title) die(`ROLE_TITLE_MAP missing entry for slug "${slug}"`);

  if (spec.name !== slug) {
    console.warn(`Warning: YAML name "${spec.name}" !== filename slug "${slug}" — using filename`);
  }

  const escalate_if = Array.isArray(spec.escalate_if) ? spec.escalate_if : [];

  return {
    slug,
    kind: "ai_persona",
    role_title,
    team,
    description: spec.description,
    default_model: spec.default_model,
    display_name: null,
    tagline: null,
    avatar_emoji: null,
    voice_signature: null,
    named_by_self: true,
    reports_to: null,
    manages: [],
    escalation_model: asNullableString(spec.escalation_model),
    escalate_if,
    requires_tools: Boolean(spec.requires_tools),
    daily_cost_ceiling_usd: asNullableNumber(spec.daily_cost_ceiling_usd),
    owner_channel: asNullableString(spec.owner_channel),
    mode: asNullableString(spec.mode),
    tone_prefix: asNullableString(spec.tone_prefix),
    proactive_cadence: asNullableString(spec.proactive_cadence),
    max_output_tokens:
      spec.max_output_tokens === undefined || spec.max_output_tokens === null
        ? null
        : Number(spec.max_output_tokens),
    requests_per_minute:
      spec.requests_per_minute === undefined || spec.requests_per_minute === null
        ? null
        : Number(spec.requests_per_minute),
    cursor_description: mdc?.cursor_description ?? null,
    cursor_globs: mdc?.cursor_globs ?? [],
    cursor_always_apply: mdc?.cursor_always_apply ?? false,
    owned_rules: [],
    owned_runbooks: [],
    owned_workflows: [],
    owned_skills: [],
    body_markdown: mdc?.body_markdown ?? null,
    metadata: {},
  };
}

function founderPayload(): EmployeeCreatePayload {
  return {
    slug: "founder",
    kind: "human",
    role_title: "Founder & CEO",
    team: "Executive Council",
    description: "Sets company direction, product vision, and capital allocation.",
    display_name: null,
    tagline: null,
    avatar_emoji: null,
    voice_signature: null,
    named_by_self: true,
    reports_to: null,
    manages: [],
    default_model: "claude-opus-4",
    escalation_model: null,
    escalate_if: [],
    requires_tools: false,
    daily_cost_ceiling_usd: null,
    owner_channel: null,
    mode: null,
    tone_prefix: null,
    proactive_cadence: null,
    max_output_tokens: null,
    requests_per_minute: null,
    cursor_description: null,
    cursor_globs: [],
    cursor_always_apply: false,
    owned_rules: [],
    owned_runbooks: [],
    owned_workflows: [],
    owned_skills: [],
    body_markdown: null,
    metadata: {},
  };
}

function stripSlugForPatch(p: EmployeeCreatePayload): Omit<EmployeeCreatePayload, "slug"> {
  const { slug: _slug, ...rest } = p;
  return rest;
}

type EmployeeDetailEnvelope = { employee: Record<string, unknown> };

async function employeeExists(
  apiRoot: string,
  secret: string,
  slug: string,
): Promise<boolean> {
  const res = await brainFetch(
    apiRoot,
    secret,
    "GET",
    `/admin/employees/${encodeURIComponent(slug)}`,
  );
  const text = await res.text();
  let json: BrainEnvelope<EmployeeDetailEnvelope>;
  try {
    json = JSON.parse(text) as BrainEnvelope<EmployeeDetailEnvelope>;
  } catch {
    throw new Error(`GET /admin/employees/${slug}: invalid JSON`);
  }
  if (res.status === 404) return false;
  if (!json.success) return false;
  return Boolean(json.data?.employee);
}

async function upsertEmployee(
  apiRoot: string,
  secret: string,
  payload: EmployeeCreatePayload,
): Promise<void> {
  const exists = await employeeExists(apiRoot, secret, payload.slug);
  if (exists) {
    const patchBody = stripSlugForPatch(payload);
    const res = await brainFetch(
      apiRoot,
      secret,
      "PATCH",
      `/admin/employees/${encodeURIComponent(payload.slug)}`,
      patchBody,
    );
    await parseSuccessEnvelope<EmployeeDetailEnvelope>(
      `PATCH /admin/employees/${payload.slug}`,
      res,
    );
    console.log(`Updated employee: ${payload.slug}`);
    return;
  }

  const res = await brainFetch(apiRoot, secret, "POST", `/admin/employees`, payload);
  await parseSuccessEnvelope<EmployeeDetailEnvelope>(
    `POST /admin/employees (${payload.slug})`,
    res,
  );
  console.log(`Created employee: ${payload.slug}`);
}

async function main(): Promise<void> {
  const apiRoot = brainApiV1Root();
  const secret = sanitizeEnv(process.env.BRAIN_API_SECRET);

  if (!apiRoot) {
    die(
      "BRAIN_API_URL is not set or empty. Set it to your Brain base URL " +
        "(e.g. https://brain-api.example.com — /api/v1 is appended automatically).",
    );
  }
  if (!secret) {
    die(
      "BRAIN_API_SECRET is not set or empty. Admin routes require X-Brain-Secret.",
    );
  }

  const specsDir = path.join(root, "apis/brain/app/personas/specs");
  const rulesDir = path.join(root, ".cursor/rules");

  const payloads: EmployeeCreatePayload[] = [];

  for (const absYaml of listPersonaSpecFiles(specsDir)) {
    const slug = path.basename(absYaml, path.extname(absYaml));
    const spec = loadPersonaYaml(absYaml);
    const mdcPath = path.join(rulesDir, `${slug}.mdc`);
    const mdc = parseMdcFile(mdcPath);
    if (mdc === null) {
      console.warn(`Warning: missing .mdc for ${slug}, cursor fields left empty`);
    }
    payloads.push(buildAiPersonaPayload(slug, spec, mdc));
  }

  payloads.push(founderPayload());

  try {
    for (const p of payloads) {
      await upsertEmployee(apiRoot, secret, p);
    }
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    die(
      `Brain API error — ${msg}\n` +
        `Check BRAIN_API_URL / BRAIN_API_SECRET and network reachability.`,
    );
  }

  console.log(`Done. Upserted ${payloads.length} employee record(s).`);
}

main().catch((e) => {
  console.error(e instanceof Error ? e.message : e);
  process.exit(1);
});
