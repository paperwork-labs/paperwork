#!/usr/bin/env node
// Fail CI if any *.stories.tsx exists outside apps/design/.
import { readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";

const ROOT = process.cwd();
const ALLOW_DIR = join(ROOT, "apps", "design");

const offenders = [];
function walk(dir) {
  for (const entry of readdirSync(dir)) {
    if (entry === "node_modules" || entry === ".next" || entry === ".turbo" || entry === "dist" || entry === "storybook-static" || entry === ".git" || entry === "_archive") continue;
    const full = join(dir, entry);
    let st;
    try { st = statSync(full); } catch { continue; }
    if (st.isDirectory()) {
      walk(full);
      continue;
    }
    if (entry.endsWith(".stories.tsx") || entry.endsWith(".stories.ts")) {
      if (!full.startsWith(ALLOW_DIR + "/")) {
        offenders.push(relative(ROOT, full));
      }
    }
  }
}

walk(join(ROOT, "apps"));
walk(join(ROOT, "packages"));

if (offenders.length > 0) {
  console.error("Stories must live under apps/design/ only. Offending files:");
  for (const f of offenders) console.error("  " + f);
  console.error("\nMove them to apps/design/src/stories/<area>/ and import the component via its package export.");
  process.exit(1);
}
console.log("OK: no stray stories outside apps/design/");
