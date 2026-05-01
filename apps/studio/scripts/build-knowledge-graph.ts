/**
 * Build `src/data/knowledge-graph.json` from `docs/_index.yaml` plus wiki patterns
 * in each markdown body ([[slug]], [[runbook:x]], [[ws:WS-NN]], @persona mentions).
 *
 * From repo root:
 *   pnpm --filter @paperwork-labs/studio exec tsx scripts/build-knowledge-graph.ts
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import matter from "gray-matter";
import yaml from "js-yaml";

import { computeFreshness, computeReadTime } from "../src/lib/doc-metadata";
import { extractDocRelations, slugToKnowledgeNodeId } from "../src/lib/knowledge-graph-patterns";

type DocCategory =
  | "philosophy"
  | "architecture"
  | "runbooks"
  | "reference"
  | "plans"
  | "sprints"
  | "generated";

type IndexFile = {
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

type KGEdge = {
  source: string;
  target: string;
  kind: "explicit-link" | "runbook-reference" | "workstream-reference" | "persona-mention";
  strength: number;
};

type KGNode = {
  id: string;
  slug: string;
  title: string;
  kind: string;
  category: DocCategory;
  read_time_min: number;
  last_reviewed: string | null;
  freshness: "fresh" | "aging" | "stale" | "unknown";
  links_in: number;
  links_out: number;
  facets?: {
    runbooks?: Array<{ name: string; slug?: string }>;
    workstreams?: string[];
    personas?: string[];
  };
};

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const STUDIO_ROOT = path.join(__dirname, "..");
const REPO_ROOT = path.join(STUDIO_ROOT, "..", "..");
const OUTPUT = path.join(STUDIO_ROOT, "src", "data", "knowledge-graph.json");
const INDEX_PATH = path.join(REPO_ROOT, "docs", "_index.yaml");

function defaultDocKind(cat: DocCategory): string {
  if (cat === "plans" || cat === "sprints") return "strategy";
  if (cat === "runbooks") return "runbook";
  if (cat === "philosophy") return "philosophy";
  if (cat === "architecture") return "architecture";
  if (cat === "generated") return "architecture";
  return "handbook";
}

function readFrontmatterString(fm: Record<string, unknown>, snake: string, camel: string): string | null {
  const v = fm[snake] ?? fm[camel];
  if (typeof v !== "string" || !v.trim()) return null;
  return v.trim();
}

function main(): void {
  const rawIdx = fs.readFileSync(INDEX_PATH, "utf-8");
  const parsed = yaml.load(rawIdx) as IndexFile;

  const slugSet = new Set(parsed.docs.map((d) => d.slug));
  const pathToSlug = new Map(parsed.docs.map((d) => [d.path, d.slug]));

  const edgeMap = new Map<string, KGEdge>();
  const facetsBySlug = new Map<
    string,
    { runbooks: Array<{ name: string; slug?: string }>; workstreams: string[]; personas: string[] }
  >();

  function mergeFacet(slug: string, rel: ReturnType<typeof extractDocRelations>): void {
    const cur = facetsBySlug.get(slug) ?? { runbooks: [], workstreams: [], personas: [] };
    facetsBySlug.set(slug, cur);

    for (const rb of rel.runbooks) {
      const hrefSlug = slugSet.has(rb.slugGuess) ? rb.slugGuess : undefined;
      const docMeta = parsed.docs.find((d) => d.slug === rb.slugGuess);
      const cleaned = rb.raw.replace(/^runbook:\s*/i, "").trim();
      const nm = (docMeta?.title ?? cleaned) || rb.slugGuess || rb.raw;
      const dup =
        cur.runbooks.some((x) => (hrefSlug && x.slug ? x.slug === hrefSlug : false)) ||
        cur.runbooks.some((x) => x.name === nm);
      if (!dup) cur.runbooks.push({ name: nm, slug: hrefSlug });
    }

    cur.workstreams = [...new Set([...cur.workstreams, ...rel.workstreams])];
    cur.personas = [...new Set([...cur.personas, ...rel.personas])];
  }

  function addEdge(e: KGEdge): void {
    const k = `${e.source}|${e.target}|${e.kind}`;
    if (!edgeMap.has(k)) edgeMap.set(k, e);
  }

  const nodes: KGNode[] = [];

  for (const doc of parsed.docs) {
    const abs = path.join(REPO_ROOT, doc.path);
    let exists = false;
    try {
      exists = fs.statSync(abs).isFile();
    } catch {
      exists = false;
    }
    if (!exists) continue;

    const rawMd = fs.readFileSync(abs, "utf-8");
    const { content, data } = matter(rawMd);
    const fm = data as Record<string, unknown>;
    const fmKind = readFrontmatterString(fm, "doc_kind", "docKind");
    const lastReviewed = readFrontmatterString(fm, "last_reviewed", "lastReviewed");
    const wc = content.split(/\s+/).filter(Boolean).length;

    const rel = extractDocRelations(content, { sourcePath: doc.path, pathToSlug });
    mergeFacet(doc.slug, rel);

    const sourceId = slugToKnowledgeNodeId(doc.slug);
    for (const tg of rel.docSlugs) {
      if (!slugSet.has(tg)) continue;
      addEdge({
        source: sourceId,
        target: slugToKnowledgeNodeId(tg),
        kind: "explicit-link",
        strength: 1,
      });
    }

    nodes.push({
      id: sourceId,
      slug: doc.slug,
      title: doc.title,
      kind: fmKind ?? defaultDocKind(doc.category),
      category: doc.category,
      read_time_min: computeReadTime(wc),
      last_reviewed: lastReviewed,
      freshness: computeFreshness(lastReviewed),
      links_in: 0,
      links_out: 0,
    });
  }

  const nodeIds = new Set(nodes.map((n) => n.id));

  const edges = [...edgeMap.values()].filter((e) => nodeIds.has(e.source) && nodeIds.has(e.target));

  for (const n of nodes) {
    n.links_in = edges.filter((e) => e.target === n.id && e.kind === "explicit-link").length;
    n.links_out = edges.filter((e) => e.source === n.id && e.kind === "explicit-link").length;
    const f = facetsBySlug.get(n.slug);
    if (
      f &&
      (f.runbooks.length > 0 || f.workstreams.length > 0 || f.personas.length > 0)
    ) {
      n.facets = {
        ...(f.runbooks.length ? { runbooks: f.runbooks } : {}),
        ...(f.workstreams.length ? { workstreams: f.workstreams } : {}),
        ...(f.personas.length ? { personas: f.personas } : {}),
      };
    }
  }

  nodes.sort((a, b) => a.slug.localeCompare(b.slug));

  const outPayload = JSON.stringify({ nodes, edges }, null, 2) + "\n";
  fs.mkdirSync(path.dirname(OUTPUT), { recursive: true });
  fs.writeFileSync(OUTPUT, outPayload, "utf-8");

  console.log(
    `[build-knowledge-graph] wrote ${nodes.length} nodes / ${edges.length} edges → ${path.relative(REPO_ROOT, OUTPUT)}`,
  );
}

main();
