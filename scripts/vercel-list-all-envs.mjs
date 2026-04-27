#!/usr/bin/env node
/**
 * For each linked app in vercel-projects.json, run `vercel env ls --format json`
 * and print a Markdown table (app | variable | scopes).
 */
import { readFileSync, existsSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const __dirname = dirname(fileURLToPath(import.meta.url));
const repoRoot = join(__dirname, "..");
const mapPath = join(repoRoot, "scripts", "vercel-projects.json");

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

if (!existsSync(mapPath)) {
  console.error("missing scripts/vercel-projects.json");
  process.exit(1);
}

const map = JSON.parse(readFileSync(mapPath, "utf8"));
const apps = map.apps ?? [];

const who = spawnSync("vercel", ["whoami"], {
  encoding: "utf8",
  stdio: ["ignore", "pipe", "pipe"],
});
if (who.status !== 0) {
  console.error("error: not logged in to Vercel (vercel whoami failed). Run: vercel login");
  process.exit(1);
}

/** @type {{ app: string; key: string; scopes: string }[]} */
const table = [];

for (const app of apps) {
  if (app.deploys === false) continue;
  const appPath = join(repoRoot, "apps", app.dir);
  if (!existsSync(appPath)) continue;
  if (!existsSync(join(appPath, ".vercel", "project.json"))) {
    console.error(`skip ${app.dir}: not linked (no .vercel/project.json)`);
    continue;
  }

  const proc = spawnSync(
    "vercel",
    ["env", "ls", "--format", "json", "--cwd", appPath, "--no-color"],
    {
      encoding: "utf8",
      maxBuffer: 50 * 1024 * 1024,
    },
  );

  if (proc.status !== 0) {
    console.error(`skip ${app.dir}: vercel env ls failed — ${(proc.stderr || "").trim()}`);
    continue;
  }

  const raw = `${proc.stdout || ""}${proc.stderr || ""}`;
  let data;
  try {
    data = JSON.parse(extractFirstJsonObject(raw) ?? "{}");
  } catch {
    console.error(`skip ${app.dir}: could not parse JSON from vercel env ls`);
    continue;
  }

  const envs = data.envs ?? [];
  for (const row of envs) {
    const target = Array.isArray(row.target) ? row.target : [];
    const scopes = target.length ? target.join(", ") : "—";
    table.push({ app: app.dir, key: row.key ?? "?", scopes });
  }
}

table.sort((a, b) => (a.app + a.key).localeCompare(b.app + b.key));

console.log("| app | env var | scopes (production / preview / development) |");
console.log("| --- | --- | --- |");
for (const row of table) {
  console.log(`| ${row.app} | \`${row.key}\` | ${row.scopes} |`);
}
