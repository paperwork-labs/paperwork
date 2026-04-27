#!/usr/bin/env node
/**
 * Runs after pnpm install. Fast path: no Vercel CLI unless tips are shown.
 * Never fails the install.
 */
import { readFileSync, existsSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const __dirname = dirname(fileURLToPath(import.meta.url));
const repoRoot = join(__dirname, "..");

function countUnlinked() {
  const mapPath = join(repoRoot, "scripts", "vercel-projects.json");
  if (!existsSync(mapPath)) return 0;
  const map = JSON.parse(readFileSync(mapPath, "utf8"));
  let n = 0;
  for (const app of map.apps ?? []) {
    if (app.deploys === false) continue;
    const appPath = join(repoRoot, "apps", app.dir);
    if (!existsSync(appPath)) continue;
    if (!existsSync(join(appPath, ".vercel", "project.json"))) n++;
  }
  return n;
}

try {
  if (process.env.CI === "true" || process.env.VERCEL_LINK_SKIP === "1") {
    process.exit(0);
  }

  const unlinked = countUnlinked();
  if (unlinked === 0) {
    process.exit(0);
  }

  // Optional: align with vercel-link-all.sh --check --quiet (same count)
  const sh = spawnSync(
    "bash",
    [join(repoRoot, "scripts", "vercel-link-all.sh"), "--check", "--quiet"],
    {
      cwd: repoRoot,
      encoding: "utf8",
      timeout: 500,
    },
  );
  const m = (sh.stdout ?? "").match(/UNLINKED=(\d+)/);
  const count = m ? parseInt(m[1], 10) : unlinked;

  const who = spawnSync("vercel", ["whoami"], {
    encoding: "utf8",
    timeout: 400,
    stdio: ["ignore", "pipe", "ignore"],
  });

  if (who.status === 0) {
    console.error(
      `\n💡 ${count} Vercel apps aren't locally linked. Run: pnpm vercel:link\n   (Skip with VERCEL_LINK_SKIP=1)\n`,
    );
  }
} catch {
  /* never block install */
}

process.exit(0);
