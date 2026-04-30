import readingPathsJson from "@/data/reading-paths.json";

import { findDocBySlug, type DocEntry } from "@/lib/docs";

export type ReadingPathDef = {
  id: string;
  title: string;
  docs: string[];
  est_minutes: number;
};

const PATHS = readingPathsJson as ReadingPathDef[];

/** Slug aliases for reading-path ids that do not match `docs/_index.yaml` slugs. */
const SLUG_ALIASES: Record<string, string> = {
  "brain-personas": "brain-personas-generated",
};

export function normalizeReadingPathDocId(id: string): string {
  return id.trim().replace(/_/g, "-").toLowerCase();
}

export function resolveReadingPathDocEntries(docIds: string[]): DocEntry[] {
  const out: DocEntry[] = [];
  const seen = new Set<string>();
  for (const id of docIds) {
    let slug = normalizeReadingPathDocId(id);
    slug = SLUG_ALIASES[slug] ?? slug;
    const entry = findDocBySlug(slug);
    if (entry && !seen.has(entry.slug)) {
      seen.add(entry.slug);
      out.push(entry);
    }
  }
  return out;
}

export function getReadingPathsWithResolvedDocs(): Array<
  ReadingPathDef & { resolved: DocEntry[] }
> {
  return PATHS.map((p) => ({
    ...p,
    resolved: resolveReadingPathDocEntries(p.docs),
  }));
}
