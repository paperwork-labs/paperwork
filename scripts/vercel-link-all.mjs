#!/usr/bin/env node
/**
 * Implementation for vercel-link-all.sh (JSON mapping, link loop, summary).
 */
import { readFileSync, existsSync } from "node:fs";
import { join } from "node:path";
import { spawnSync } from "node:child_process";

const repoRoot = process.env.REPO_ROOT ?? "";
const mapPath = process.env.MAP_JSON ?? join(repoRoot, "scripts", "vercel-projects.json");
const checkOnly = process.env.VERCEL_LINK_CHECK_ONLY === "1";
const quiet = process.env.VERCEL_LINK_QUIET === "1";

/** Vercel CLI may prefix/suffix human lines around JSON when stdout is not a TTY. */
function extractFirstJsonObject(s) {
  const start = s.indexOf("{");
  if (start === -1) return null;
  let depth = 0;
  for (let i = start; i < s.length; i++) {
    const c = s[i];
    if (c === "{") depth++;
    else if (c === "}") {
      depth--;
      if (depth === 0) return s.slice(start, i + 1);
    }
  }
  return null;
}

function log(msg) {
  if (!quiet) console.log(msg);
}

function logErr(msg) {
  console.error(msg);
}

if (!repoRoot) {
  logErr("error: REPO_ROOT is not set");
  process.exit(1);
}

const map = JSON.parse(readFileSync(mapPath, "utf8"));
const teamSlugOrId = map.team;
const apps = map.apps ?? [];

/**
 * `vercel link --scope <slug>` can mis-resolve some slugs to a personal account.
 * Resolve the mapping `team` field (slug or id) to a team id via `vercel teams list`.
 */
function resolveScopeForLink() {
  const proc = spawnSync("vercel", ["teams", "list", "--format", "json", "--no-color"], {
    encoding: "utf8",
    maxBuffer: 5 * 1024 * 1024,
  });
  if (proc.status !== 0) {
    logErr(`vercel teams list failed: ${(proc.stderr || proc.stdout || "").trim()}`);
    process.exit(1);
  }
  const raw = `${proc.stdout || ""}${proc.stderr || ""}`;
  const jsonText = extractFirstJsonObject(raw);
  let data;
  try {
    data = JSON.parse(jsonText ?? "{}");
  } catch {
    logErr("could not parse vercel teams list JSON");
    process.exit(1);
  }
  const teams = data.teams ?? [];
  const hit =
    teams.find((t) => t.slug === teamSlugOrId) ||
    teams.find((t) => t.id === teamSlugOrId);
  if (!hit) {
    logErr(
      `No Vercel team matches "${teamSlugOrId}" in vercel-projects.json. Try: vercel teams list`,
    );
    process.exit(1);
  }
  return hit.id;
}

const linkScope = checkOnly ? teamSlugOrId : resolveScopeForLink();

/** @type {{ dir: string; project: string; linked: string; note: string }[]} */
const rows = [];
let failures = 0;
let unlinked = 0;

for (const app of apps) {
  if (app.deploys === false) {
    rows.push({
      dir: app.dir,
      project: app.project,
      linked: "—",
      note: "skip (not on Vercel)",
    });
    continue;
  }

  const appPath = join(repoRoot, "apps", app.dir);
  if (!existsSync(appPath)) {
    rows.push({
      dir: app.dir,
      project: app.project,
      linked: "—",
      note: "skip (no apps/" + app.dir + ")",
    });
    continue;
  }

  const projFile = join(appPath, ".vercel", "project.json");
  const linked = existsSync(projFile);

  if (linked) {
    rows.push({
      dir: app.dir,
      project: app.project,
      linked: "yes",
      note: "",
    });
    if (!checkOnly) log(`✓ ${app.dir} already linked`);
    continue;
  }

  unlinked++;
  rows.push({
    dir: app.dir,
    project: app.project,
    linked: "no",
    note: "",
  });

  if (checkOnly) {
    if (!quiet) {
      log(
        `○ ${app.dir} not linked — would run: vercel link --cwd apps/${app.dir} --yes --project ${app.project} --scope <team-from-vercel-projects.json>`,
      );
    }
    continue;
  }

  log(`→ linking ${app.dir} → project ${app.project} (team ${teamSlugOrId})…`);
  const r = spawnSync(
    "vercel",
    ["link", "--cwd", appPath, "--yes", "--project", app.project, "--scope", linkScope],
    { stdio: quiet ? "pipe" : "inherit", encoding: "utf8" },
  );
  if (r.status !== 0) {
    failures++;
    logErr(`✗ vercel link failed for ${app.dir} (exit ${r.status ?? "unknown"})`);
  } else if (existsSync(projFile)) {
    rows[rows.length - 1].linked = "yes";
    rows[rows.length - 1].note = "";
    log(`✓ ${app.dir} linked`);
  } else {
    failures++;
    logErr(`✗ link command exited 0 but .vercel/project.json missing for ${app.dir}`);
  }
}

if (quiet && checkOnly) {
  process.stdout.write(`UNLINKED=${unlinked}\n`);
} else if (!quiet) {
  console.log("");
  console.log("Summary");
  console.log("────────────────────────────────────────────────────────────────────────────");
  const wDir = 18;
  const wL = 8;
  const wProj = 22;
  console.log(
    `${"app".padEnd(wDir)} ${"linked?".padEnd(wL)} ${"project".padEnd(wProj)} team / notes`,
  );
  console.log("────────────────────────────────────────────────────────────────────────────");
  for (const row of rows) {
    const note = row.note ? `${teamSlugOrId} — ${row.note}` : teamSlugOrId;
    console.log(
      `${row.dir.padEnd(wDir)} ${row.linked.padEnd(wL)} ${row.project.padEnd(wProj)} ${note}`,
    );
  }
  console.log("────────────────────────────────────────────────────────────────────────────");
}

if (checkOnly) {
  process.exit(0);
}

process.exit(failures > 0 ? 1 : 0);
