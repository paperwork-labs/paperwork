import {
  computeFreshness,
  computeReadTime,
  docKindToHubCategory,
  type FreshnessLevel,
  type HubDocCategory,
} from "@/lib/doc-metadata";

// Track N of the Infra & Automation Hardening Sprint.
// Single source of truth for the Studio /admin/docs hub.
//
// Production path: reads from bundled JSON snapshot (built by scripts/snapshot-docs.ts).
// Dev path (BRAIN_API_URL configured): tries Brain API, falls back to snapshot with error.

// ─── Snapshot import ────────────────────────────────────────────────────────
import docsSnapshot from "@/data/docs-snapshot.json";

// ─── Types ──────────────────────────────────────────────────────────────────

export type DocCategory =
  | "philosophy"
  | "architecture"
  | "runbooks"
  | "reference"
  | "plans"
  | "sprints"
  | "generated";

export type DocEntry = {
  slug: string;
  path: string;
  title: string;
  summary: string;
  tags: string[];
  owners: string[];
  category: DocCategory;
  exists: boolean;
};

export type CategoryMeta = {
  id: DocCategory;
  label: string;
  description: string;
  order: number;
};

export type { FreshnessLevel, HubDocCategory };

export type DocHubEntry = DocEntry & {
  docKind: string | null;
  hubCategory: HubDocCategory;
  lastReviewed: string | null;
  wordCount: number;
  readMinutes: number;
  freshness: FreshnessLevel;
};

export type DocContent = {
  entry: DocEntry;
  markdown: string;
  frontmatter: Record<string, unknown>;
  wordCount: number;
  lastModified: string | null;
};

export type DocsByCategory = Record<DocCategory, DocEntry[]>;

// ─── Snapshot shape ──────────────────────────────────────────────────────────

type SnapshotEntry = {
  slug: string;
  path: string;
  title: string;
  summary: string;
  tags: string[];
  owners: string[];
  category: string;
  exists: boolean;
  body: string;
  frontmatter: Record<string, unknown>;
  wordCount: number;
  lastReviewed: string | null;
  docKind: string | null;
  readMinutes: number;
};

type DocsSnapshotShape = {
  categories: Array<{ id: string; label: string; description: string; order: number }>;
  entries: SnapshotEntry[];
};

const SNAPSHOT = docsSnapshot as unknown as DocsSnapshotShape;

// ─── Snapshot → typed helpers ────────────────────────────────────────────────

function snapshotCategories(): CategoryMeta[] {
  return SNAPSHOT.categories.map((c) => ({
    id: c.id as DocCategory,
    label: c.label,
    description: c.description,
    order: c.order,
  }));
}

function snapshotEntries(): DocEntry[] {
  return SNAPSHOT.entries.map((e) => ({
    slug: e.slug,
    path: e.path,
    title: e.title,
    summary: e.summary,
    tags: e.tags,
    owners: e.owners,
    category: e.category as DocCategory,
    exists: e.exists,
  }));
}

// ─── Public API ──────────────────────────────────────────────────────────────

export function loadDocsIndex(): {
  entries: DocEntry[];
  categories: CategoryMeta[];
} {
  return {
    entries: snapshotEntries(),
    categories: snapshotCategories(),
  };
}

export function findDocBySlug(slug: string): DocEntry | undefined {
  return loadDocsIndex().entries.find((d) => d.slug === slug);
}

/** Every indexed doc with frontmatter-derived read time, freshness, and hub category. */
export function loadDocHubEntries(): DocHubEntry[] {
  const rows: DocHubEntry[] = SNAPSHOT.entries.map((e) => ({
    slug: e.slug,
    path: e.path,
    title: e.title,
    summary: e.summary,
    tags: e.tags,
    owners: e.owners,
    category: e.category as DocCategory,
    exists: e.exists,
    docKind: e.docKind,
    hubCategory: docKindToHubCategory(e.docKind),
    lastReviewed: e.lastReviewed,
    wordCount: e.wordCount,
    readMinutes: e.readMinutes,
    // freshness computed at runtime so it ages correctly from lastReviewed
    freshness: computeFreshness(e.lastReviewed),
  }));
  rows.sort((a, b) => a.title.localeCompare(b.title));
  return rows;
}

/** Full file body for Studio editor + PR flow. Served from snapshot. */
export function loadDocRaw(slug: string): { entry: DocEntry; raw: string } | null {
  const snap = SNAPSHOT.entries.find((e) => e.slug === slug);
  if (!snap) return null;
  const entry: DocEntry = {
    slug: snap.slug,
    path: snap.path,
    title: snap.title,
    summary: snap.summary,
    tags: snap.tags,
    owners: snap.owners,
    category: snap.category as DocCategory,
    exists: snap.exists,
  };
  // Reconstruct raw by re-adding frontmatter header so callers get the same shape
  const fmYaml = Object.keys(snap.frontmatter).length
    ? `---\n${Object.entries(snap.frontmatter)
        .map(([k, v]) => `${k}: ${JSON.stringify(v)}`)
        .join("\n")}\n---\n`
    : "";
  return { entry, raw: fmYaml + snap.body };
}

export function loadDocContent(slug: string): DocContent | null {
  const snap = SNAPSHOT.entries.find((e) => e.slug === slug);
  if (!snap) return null;
  const entry: DocEntry = {
    slug: snap.slug,
    path: snap.path,
    title: snap.title,
    summary: snap.summary,
    tags: snap.tags,
    owners: snap.owners,
    category: snap.category as DocCategory,
    exists: snap.exists,
  };
  return {
    entry,
    markdown: snap.body,
    frontmatter: snap.frontmatter,
    wordCount: snap.wordCount,
    lastModified: null,
  };
}

export function groupDocsByCategory(): {
  categories: CategoryMeta[];
  byCategory: DocsByCategory;
} {
  const { entries, categories } = loadDocsIndex();
  const byCategory = {
    philosophy: [],
    architecture: [],
    runbooks: [],
    reference: [],
    plans: [],
    sprints: [],
    generated: [],
  } as DocsByCategory;
  for (const entry of entries) {
    const bucket = byCategory[entry.category];
    if (bucket) {
      bucket.push(entry);
    } else {
      console.warn(
        `[docs] unknown category "${entry.category}" for ${entry.path} — extend DocCategory type`,
      );
    }
  }
  for (const cat of Object.keys(byCategory) as DocCategory[]) {
    byCategory[cat].sort((a, b) => a.title.localeCompare(b.title));
  }
  return { categories, byCategory };
}

export function searchDocs(query: string): DocEntry[] {
  const q = query.trim().toLowerCase();
  if (!q) return [];
  const { entries } = loadDocsIndex();
  return entries
    .map((entry) => {
      const haystack = [
        entry.title,
        entry.summary,
        entry.slug,
        entry.tags.join(" "),
        entry.owners.join(" "),
      ]
        .join(" ")
        .toLowerCase();
      const score = haystack.includes(q) ? 1 : 0;
      return { entry, score };
    })
    .filter((r) => r.score > 0)
    .map((r) => r.entry);
}
