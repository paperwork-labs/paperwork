#!/usr/bin/env node
// Verify every apps/*/vercel.json uses the canonical install command.
// Failure modes: drift, hardcoded pnpm versions, missing the shared script.

import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

const ROOT = process.cwd();
const APPS_DIR = join(ROOT, "apps");

// Apps temporarily exempted from the canon (must be empty in steady state):
const EXEMPT = new Set([
  // axiomfolio is mid-cutover (see chore/axiomfolio-vercel-cutover, PR #306).
  // Remove this entry once that PR lands.
  "axiomfolio",
  // _archive is a tombstone for legacy apps; not deployed.
  "_archive",
]);

const offenders = [];

for (const dir of readdirSync(APPS_DIR)) {
  if (EXEMPT.has(dir)) continue;
  const appDir = join(APPS_DIR, dir);
  let stats;
  try { stats = statSync(appDir); } catch { continue; }
  if (!stats.isDirectory()) continue;
  const vercelJsonPath = join(appDir, "vercel.json");
  let raw;
  try {
    raw = readFileSync(vercelJsonPath, "utf-8");
  } catch {
    // No vercel.json -> not deployed via Vercel matrix; skip silently.
    continue;
  }
  let parsed;
  try {
    parsed = JSON.parse(raw);
  } catch (err) {
    offenders.push(`${dir}/vercel.json: not valid JSON (${err.message})`);
    continue;
  }
  const expected = `bash ../../scripts/vercel-install.sh @paperwork-labs/${dir}`;
  if (parsed.installCommand !== expected) {
    offenders.push(
      `${dir}/vercel.json: installCommand drift\n    expected: ${expected}\n    got:      ${parsed.installCommand}`
    );
  }
}

if (offenders.length > 0) {
  console.error("vercel.json canon violations:");
  for (const o of offenders) console.error("  " + o);
  console.error(
    "\nFix: set installCommand to the canonical form. The shared script is scripts/vercel-install.sh."
  );
  process.exit(1);
}
console.log("OK: every apps/*/vercel.json matches the canonical install pattern.");
