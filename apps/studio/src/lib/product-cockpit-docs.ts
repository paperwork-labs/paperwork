import fs from "node:fs";
import path from "node:path";

import { loadDocsIndex } from "@/lib/docs";

function repoRoot(): string {
  // apps/studio → monorepo root; turbopackIgnore avoids tracing cwd as a repo-wide glob.
  return path.join(/* turbopackIgnore: true */ process.cwd(), "..", "..");
}

function humanizeMdFilename(base: string): string {
  const spaced = base.replace(/[_-]+/g, " ").trim();
  if (!spaced) return base;
  return spaced.replace(/\b\w/g, (c) => c.toUpperCase());
}

/** Walk docs/<productSlug>/ for .md files; returns repo-relative POSIX paths. */
function walkMarkdownFiles(absDir: string, relPosixBase: string): string[] {
  const out: string[] = [];
  if (!fs.existsSync(absDir)) return out;
  for (const name of fs.readdirSync(absDir)) {
    if (name.startsWith(".")) continue;
    const abs = path.join(/* turbopackIgnore: true */ absDir, name);
    const rel = path.posix.join(relPosixBase, name);
    let st: fs.Stats;
    try {
      st = fs.statSync(abs);
    } catch {
      continue;
    }
    if (st.isDirectory()) {
      out.push(...walkMarkdownFiles(abs, rel));
    } else if (name.toLowerCase().endsWith(".md")) {
      out.push(rel);
    }
  }
  return out;
}

export type ProductPlanDocRef = {
  /** e.g. docs/axiomfolio/plans/MASTER_PLAN_2026.md */
  path: string;
  title: string;
  hubSlug: string | null;
};

export function listProductMarkdownDocs(productSlug: string): ProductPlanDocRef[] {
  const root = repoRoot();
  const relRoot = path.posix.join("docs", productSlug);
  const absDir = path.join(/* turbopackIgnore: true */ root, relRoot);
  const relPaths = walkMarkdownFiles(absDir, relRoot);

  const byPath = new Map(loadDocsIndex().entries.map((e) => [e.path, e]));

  return relPaths
    .sort((a, b) => a.localeCompare(b))
    .map((p) => {
      const normalized = p.replace(/\\/g, "/");
      const hub = byPath.get(normalized);
      const base = path.basename(normalized, path.extname(normalized));
      return {
        path: normalized,
        title: hub?.title ?? humanizeMdFilename(base),
        hubSlug: hub?.slug ?? null,
      };
    });
}
