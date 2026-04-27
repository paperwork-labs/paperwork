/**
 * Sprint status audit for docs/sprints-derived `tracker-index.json`.
 * Run: `pnpm exec tsx scripts/sprints/normalize-statuses.ts [--check]`
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import type { Sprint, TrackerIndex } from "../../apps/studio/src/lib/tracker";
import { computeEffectiveSprintStatus } from "../../apps/studio/src/lib/sprint-reconcile";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "../..");
const indexPath = path.join(root, "apps/studio/src/data/tracker-index.json");

function main() {
  const check = process.argv.includes("--check");
  const raw = fs.readFileSync(indexPath, "utf-8");
  const data = JSON.parse(raw) as TrackerIndex;
  const issues: string[] = [];
  for (const s of data.sprints) {
    const want = computeEffectiveSprintStatus(
      { ...s, effective_status: undefined } as Sprint,
      data.sprints
    );
    const have = s.effective_status ?? s.status;
    if (want !== have) {
      issues.push(`${s.slug}: effective ${JSON.stringify(have)} !== recomputed ${JSON.stringify(want)}`);
    }
  }
  if (issues.length) {
    console.error("Sprint status reconciliation drift:\n" + issues.join("\n"));
    if (check) process.exit(1);
  } else {
    console.log(
      `OK — ${data.sprints.length} sprints match computeEffectiveSprintStatus vs tracker-index.`
    );
  }
}

main();
