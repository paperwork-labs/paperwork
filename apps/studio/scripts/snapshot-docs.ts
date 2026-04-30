/**
 * Build-time snapshot of the docs/ tree.
 * Reads docs/_index.yaml, then reads frontmatter + body for the first 100
 * docs (in _index.yaml order), and writes apps/studio/src/data/docs-snapshot.json.
 *
 * Run via: tsx scripts/snapshot-docs.ts
 * Auto-run during: prebuild (see package.json)
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import matter from "gray-matter";
import yaml from "js-yaml";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const STUDIO_ROOT = path.join(__dirname, "..");
const REPO_ROOT = path.join(STUDIO_ROOT, "..", "..");
const INDEX_PATH = path.join(REPO_ROOT, "docs", "_index.yaml");
const OUT_PATH = path.join(STUDIO_ROOT, "src/data/docs-snapshot.json");

const MAX_DOCS = 100;

// ─── types ─────────────────────────────────────────────────────────────────

type DocCategory =
  | "philosophy"
  | "architecture"
  | "runbooks"
  | "reference"
  | "plans"
  | "sprints"
  | "generated";

type CategoryMeta = {
  id: DocCategory;
  label: string;
  description: string;
  order: number;
};

type DocSnapshotEntry = {
  slug: string;
  path: string;
  title: string;
  summary: string;
  tags: string[];
  owners: string[];
  category: DocCategory;
  exists: boolean;
  body: string;
  frontmatter: Record<string, unknown>;
  wordCount: number;
  lastReviewed: string | null;
  docKind: string | null;
  readMinutes: number;
};

type DocsSnapshot = {
  generatedFrom: string;
  totalIndexed: number;
  snapshotCount: number;
  categories: CategoryMeta[];
  entries: DocSnapshotEntry[];
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

// ─── helpers ───────────────────────────────────────────────────────────────

function computeReadTime(wordCount: number): number {
  if (wordCount <= 0) return 0;
  return Math.ceil(wordCount / 200);
}

function parseFrontmatterString(
  fm: Record<string, unknown>,
  snake: string,
  camel: string,
): string | null {
  const v = fm[snake] ?? fm[camel];
  if (typeof v !== "string" || !v.trim()) return null;
  return v.trim();
}

// ─── main ──────────────────────────────────────────────────────────────────

function run(): void {
  if (!fs.existsSync(INDEX_PATH)) {
    process.stderr.write(`snapshot-docs: index not found: ${INDEX_PATH}\n`);
    process.exit(1);
  }

  const rawIndex = fs.readFileSync(INDEX_PATH, "utf-8");
  const parsed = yaml.load(rawIndex) as IndexFile;

  const categories: CategoryMeta[] = Object.entries(parsed.categories)
    .map(([id, meta]) => ({
      id: id as DocCategory,
      label: meta.label,
      description: meta.description,
      order: meta.order,
    }))
    .sort((a, b) => a.order - b.order);

  const indexDocs = parsed.docs ?? [];
  const totalIndexed = indexDocs.length;

  const entries: DocSnapshotEntry[] = [];

  for (const doc of indexDocs.slice(0, MAX_DOCS)) {
    const full = path.join(REPO_ROOT, doc.path);
    let exists = false;
    let body = "";
    let frontmatter: Record<string, unknown> = {};
    let wordCount = 0;
    let lastReviewed: string | null = null;
    let docKind: string | null = null;

    try {
      const raw = fs.readFileSync(full, "utf-8");
      exists = true;
      const parsed = matter(raw);
      body = parsed.content;
      frontmatter = parsed.data as Record<string, unknown>;
      wordCount = body.split(/\s+/).filter(Boolean).length;
      lastReviewed = parseFrontmatterString(frontmatter, "last_reviewed", "lastReviewed");
      docKind = parseFrontmatterString(frontmatter, "doc_kind", "docKind");
    } catch {
      // File missing or unreadable — keep zeros/nulls, exists=false.
    }

    entries.push({
      slug: doc.slug,
      path: doc.path,
      title: doc.title,
      summary: doc.summary,
      tags: doc.tags ?? [],
      owners: doc.owners ?? [],
      category: doc.category,
      exists,
      body,
      frontmatter,
      wordCount,
      lastReviewed,
      docKind,
      readMinutes: computeReadTime(wordCount),
    });
  }

  const snapshot: DocsSnapshot = {
    generatedFrom: "docs/_index.yaml",
    totalIndexed,
    snapshotCount: entries.length,
    categories,
    entries,
  };

  fs.mkdirSync(path.dirname(OUT_PATH), { recursive: true });
  fs.writeFileSync(OUT_PATH, JSON.stringify(snapshot, null, 2) + "\n");
  process.stdout.write(
    `snapshot-docs: wrote ${OUT_PATH} (${entries.length}/${totalIndexed} docs)\n`,
  );
}

run();
