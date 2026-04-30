import fs from "node:fs";
import path from "node:path";

import matter from "gray-matter";
import yaml from "js-yaml";

import {
  computeFreshness,
  computeReadTime,
  docKindToHubCategory,
  type FreshnessLevel,
  type HubDocCategory,
} from "@/lib/doc-metadata";

// Track N of the Infra & Automation Hardening Sprint.
// Single source of truth for the Studio /admin/docs hub. Reads
// docs/_index.yaml from the repo root and returns typed entries that the
// admin pages and agents can consume.

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

type IndexFile = {
  categories: Record<
    DocCategory,
    { label: string; description: string; order: number }
  >;
  docs: Array<{
    slug: string;
    path: string;
    title: string;
    summary: string;
    tags?: string[];
    owners?: string[];
    category: DocCategory;
  }>;
};

function repoRoot(): string {
  // apps/studio → monorepo root; turbopackIgnore avoids tracing cwd as a repo-wide glob.
  return path.join(/* turbopackIgnore: true */ process.cwd(), "..", "..");
}

function indexPath(): string {
  return path.join(repoRoot(), "docs", "_index.yaml");
}

let cached: { entries: DocEntry[]; categories: CategoryMeta[] } | null = null;

export function loadDocsIndex(): {
  entries: DocEntry[];
  categories: CategoryMeta[];
} {
  if (cached) return cached;
  const raw = fs.readFileSync(indexPath(), "utf-8");
  const parsed = yaml.load(raw) as IndexFile;

  const categories: CategoryMeta[] = Object.entries(parsed.categories)
    .map(([id, meta]) => ({
      id: id as DocCategory,
      label: meta.label,
      description: meta.description,
      order: meta.order,
    }))
    .sort((a, b) => a.order - b.order);

  const root = repoRoot();
  const entries: DocEntry[] = parsed.docs.map((entry) => {
    const full = path.join(/* turbopackIgnore: true */ root, entry.path);
    let exists = false;
    try {
      exists = fs.statSync(full).isFile();
    } catch {
      exists = false;
    }
    return {
      slug: entry.slug,
      path: entry.path,
      title: entry.title,
      summary: entry.summary,
      tags: entry.tags ?? [],
      owners: entry.owners ?? [],
      category: entry.category,
      exists,
    };
  });

  cached = { entries, categories };
  return cached;
}

export function findDocBySlug(slug: string): DocEntry | undefined {
  return loadDocsIndex().entries.find((d) => d.slug === slug);
}

export type { FreshnessLevel, HubDocCategory };

export type DocHubEntry = DocEntry & {
  docKind: string | null;
  hubCategory: HubDocCategory;
  lastReviewed: string | null;
  wordCount: number;
  readMinutes: number;
  freshness: FreshnessLevel;
};

function parseFrontmatterString(
  fm: Record<string, unknown>,
  snake: string,
  camel: string,
): string | null {
  const v = fm[snake] ?? fm[camel];
  if (typeof v !== "string" || !v.trim()) return null;
  return v.trim();
}

/** Every indexed doc with frontmatter-derived read time, freshness, and hub category. */
export function loadDocHubEntries(): DocHubEntry[] {
  const { entries } = loadDocsIndex();
  const root = repoRoot();
  const rows: DocHubEntry[] = entries.map((entry) => {
    const full = path.join(/* turbopackIgnore: true */ root, entry.path);
    let wordCount = 0;
    let lastReviewed: string | null = null;
    let docKind: string | null = null;
    try {
      const raw = fs.readFileSync(full, "utf-8");
      const { content, data } = matter(raw);
      wordCount = content.split(/\s+/).filter(Boolean).length;
      const fm = data as Record<string, unknown>;
      lastReviewed = parseFrontmatterString(fm, "last_reviewed", "lastReviewed");
      docKind = parseFrontmatterString(fm, "doc_kind", "docKind");
    } catch {
      // Missing or unreadable file — keep zeros / nulls.
    }
    return {
      ...entry,
      docKind,
      hubCategory: docKindToHubCategory(docKind),
      lastReviewed,
      wordCount,
      readMinutes: computeReadTime(wordCount),
      freshness: computeFreshness(lastReviewed),
    };
  });
  rows.sort((a, b) => a.title.localeCompare(b.title));
  return rows;
}

/** Full file on disk (including YAML frontmatter) for Studio editor + PR flow. */
export function loadDocRaw(slug: string): { entry: DocEntry; raw: string } | null {
  const entry = findDocBySlug(slug);
  if (!entry) return null;
  const full = path.join(repoRoot(), entry.path);
  try {
    const raw = fs.readFileSync(full, "utf-8");
    return { entry, raw };
  } catch {
    return null;
  }
}

export type DocContent = {
  entry: DocEntry;
  markdown: string;
  frontmatter: Record<string, unknown>;
  wordCount: number;
  lastModified: string | null;
};

export function loadDocContent(slug: string): DocContent | null {
  const entry = findDocBySlug(slug);
  if (!entry) return null;
  const full = path.join(/* turbopackIgnore: true */ repoRoot(), entry.path);
  let raw: string;
  try {
    raw = fs.readFileSync(full, "utf-8");
  } catch {
    return null;
  }
  let lastModified: string | null = null;
  try {
    lastModified = fs.statSync(full).mtime.toISOString();
  } catch {
    lastModified = null;
  }
  const { content, data } = matter(raw);
  const wordCount = content.split(/\s+/).filter(Boolean).length;
  return {
    entry,
    markdown: content,
    frontmatter: data,
    wordCount,
    lastModified,
  };
}

export type DocsByCategory = Record<DocCategory, DocEntry[]>;

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
