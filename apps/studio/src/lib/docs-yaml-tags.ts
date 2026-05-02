/**
 * Server-only helper: merge live tags from ``docs/_index.yaml`` onto snapshot entries.
 * Imported only from Server Components / routes — do not import from client modules.
 */

import fs from "node:fs";
import path from "node:path";

import yaml from "js-yaml";

import type { DocEntry } from "@/lib/docs";
import { loadDocsIndex } from "@/lib/docs";

function resolveDocsIndexYamlPath(): string | null {
  const candidates = [
    path.join(process.cwd(), "..", "..", "docs", "_index.yaml"),
    path.join(process.cwd(), "docs", "_index.yaml"),
  ];
  for (const candidate of candidates) {
    try {
      if (fs.existsSync(candidate)) return candidate;
    } catch {
      /* ignore */
    }
  }
  return null;
}

function tagsBySlugFromYaml(): Map<string, string[]> | null {
  const yamlPath = resolveDocsIndexYamlPath();
  if (!yamlPath) return null;
  try {
    const doc = yaml.load(fs.readFileSync(yamlPath, "utf8")) as {
      docs?: { slug?: string; tags?: unknown[] }[];
    };
    const rows = doc.docs;
    if (!Array.isArray(rows)) return null;
    const m = new Map<string, string[]>();
    for (const row of rows) {
      if (typeof row.slug !== "string") continue;
      if (!Array.isArray(row.tags)) continue;
      const tags = row.tags.filter((t): t is string => typeof t === "string" && t.trim().length > 0);
      if (tags.length) m.set(row.slug, tags);
    }
    return m.size ? m : null;
  } catch {
    return null;
  }
}

/** When ``docs/_index.yaml`` is present in the monorepo, replace per-slug tags for filtering. */
export function mergeDocEntryTagsFromRepoYaml(entries: DocEntry[]): DocEntry[] {
  const overlay = tagsBySlugFromYaml();
  if (!overlay) return entries;
  return entries.map((e) => {
    const tags = overlay.get(e.slug);
    return tags !== undefined ? { ...e, tags } : e;
  });
}

/** Snapshot doc entries with tags merged from repo ``docs/_index.yaml`` when that file exists. */
export function loadDocsEntriesWithYamlTags(): DocEntry[] {
  return mergeDocEntryTagsFromRepoYaml(loadDocsIndex().entries);
}
