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

export type ReadingPathValidationRow = {
  id: string;
  title: string;
  requestedDocIds: string[];
  resolvedSlugs: string[];
  unresolvedDocIds: string[];
};

/** Resolve a single reading-path doc id to a slug Brain hub entry (after normalize + aliases). */
export function resolveReadingPathDocIdToSlug(rawId: string): string | null {
  let slug = normalizeReadingPathDocId(rawId);
  slug = SLUG_ALIASES[slug] ?? slug;
  return findDocBySlug(slug)?.slug ?? null;
}

export function normalizeReadingPathDocId(id: string): string {
  return id.trim().replace(/_/g, "-").toLowerCase();
}

/**
 * Reports which listed doc ids do not resolve to an indexed doc.
 * Use in tests and tooling to catch drift vs `docs/_index.yaml` / docs snapshot.
 */
export function validateReadingPaths(): ReadingPathValidationRow[] {
  return PATHS.map((path) => {
    const resolvedSlugs: string[] = [];
    const seen = new Set<string>();
    const unresolvedDocIds: string[] = [];

    for (const rawId of path.docs) {
      let slug = normalizeReadingPathDocId(rawId);
      slug = SLUG_ALIASES[slug] ?? slug;
      const entry = findDocBySlug(slug);
      if (!entry) {
        unresolvedDocIds.push(rawId);
      } else if (!seen.has(entry.slug)) {
        seen.add(entry.slug);
        resolvedSlugs.push(entry.slug);
      }
    }

    return {
      id: path.id,
      title: path.title,
      requestedDocIds: [...path.docs],
      resolvedSlugs,
      unresolvedDocIds,
    };
  });
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
