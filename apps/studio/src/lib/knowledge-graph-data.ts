import { z } from "zod";

import graphJson from "@/data/knowledge-graph.json";
import { findDocBySlug } from "@/lib/docs";
import {
  extractDocRelations,
  knowledgeNodeIdToSlugGuess,
  slugToKnowledgeNodeId,
} from "@/lib/knowledge-graph-patterns";

export const FreshnessSchema = z.enum(["fresh", "aging", "stale", "unknown"]);

export const KnowledgeEdgeKindSchema = z.enum([
  "explicit-link",
  "runbook-reference",
  "workstream-reference",
  "persona-mention",
]);

export const KnowledgeGraphFacetsSchema = z
  .object({
    runbooks: z.array(z.object({ name: z.string(), slug: z.string().optional() }).strict()).optional(),
    workstreams: z.array(z.string()).optional(),
    personas: z.array(z.string()).optional(),
  })
  .strict();

export const KnowledgeGraphNodeSchema = z
  .object({
    id: z.string(),
    slug: z.string(),
    title: z.string(),
    kind: z.string(),
    category: z.string(),
    read_time_min: z.number(),
    last_reviewed: z.string().nullable().optional(),
    freshness: FreshnessSchema,
    links_in: z.number(),
    links_out: z.number(),
    facets: KnowledgeGraphFacetsSchema.optional(),
  })
  .strict();

export const KnowledgeGraphEdgeSchema = z
  .object({
    source: z.string(),
    target: z.string(),
    kind: KnowledgeEdgeKindSchema,
    strength: z.number(),
  })
  .strict();

export const KnowledgeGraphFileSchema = z
  .object({
    nodes: z.array(KnowledgeGraphNodeSchema),
    edges: z.array(KnowledgeGraphEdgeSchema),
  })
  .strict();

export type KnowledgeGraphNodeRecord = z.infer<typeof KnowledgeGraphNodeSchema>;
export type KnowledgeGraphEdgeRecord = z.infer<typeof KnowledgeGraphEdgeSchema>;
export type KnowledgeGraphFileParsed = z.infer<typeof KnowledgeGraphFileSchema>;

export type KnowledgeDocRef = { id: string; slug: string; title: string };

export type KnowledgeRailModel = {
  nodeId: string;
  slug: string;
  inIndexedGraph: boolean;
  stats: Pick<KnowledgeGraphNodeRecord, "read_time_min" | "freshness" | "links_in" | "links_out">;
  linkedFrom: { count: number; topLinkers: KnowledgeDocRef[] };
  linksOut: KnowledgeDocRef[];
  relatedRunbooks: Array<{ name: string; hrefSlug?: string }>;
  relatedWorkstreams: string[];
};

type IndexedKnowledgeGraph = {
  raw: KnowledgeGraphFileParsed;
  nodeById: Map<string, KnowledgeGraphNodeRecord>;
};

let indexed: IndexedKnowledgeGraph | null = null;

export function parseKnowledgeGraphFile(data: unknown): KnowledgeGraphFileParsed {
  return KnowledgeGraphFileSchema.parse(data);
}

function indexGraph(parsed: KnowledgeGraphFileParsed): IndexedKnowledgeGraph {
  const nodeById = new Map<string, KnowledgeGraphNodeRecord>();
  for (const n of parsed.nodes) {
    nodeById.set(n.id, n);
  }
  return { raw: parsed, nodeById };
}

export function loadKnowledgeGraphIndexed(): IndexedKnowledgeGraph {
  if (!indexed) {
    indexed = indexGraph(parseKnowledgeGraphFile(graphJson));
  }
  return indexed;
}

/** Vitest resets only */
export function __resetKnowledgeGraphCacheForTests(): void {
  indexed = null;
}

export function vizEdgesFromKnowledgeGraph(parsed: KnowledgeGraphFileParsed): KnowledgeGraphEdgeRecord[] {
  const ids = new Set(parsed.nodes.map((n) => n.id));
  return parsed.edges.filter(
    (e) => e.kind === "explicit-link" && ids.has(e.source) && ids.has(e.target),
  );
}

function resolveDocRef(nodeId: string, g: IndexedKnowledgeGraph): KnowledgeDocRef | null {
  const hit = g.nodeById.get(nodeId);
  if (hit) return { id: hit.id, slug: hit.slug, title: hit.title };
  const guessed = knowledgeNodeIdToSlugGuess(nodeId);
  const entry = findDocBySlug(guessed);
  if (entry) return { id: nodeId, slug: entry.slug, title: entry.title };
  return null;
}

function uniqBySlug(rows: KnowledgeDocRef[]): KnowledgeDocRef[] {
  const seen = new Set<string>();
  const out: KnowledgeDocRef[] = [];
  for (const r of rows) {
    if (seen.has(r.slug)) continue;
    seen.add(r.slug);
    out.push(r);
  }
  return out;
}

export function getKnowledgeRailForSlug(slug: string, markdownBody: string): KnowledgeRailModel {
  const g = loadKnowledgeGraphIndexed();
  const nodeId = slugToKnowledgeNodeId(slug);
  const nodeRec = g.nodeById.get(nodeId);
  const live = extractDocRelations(markdownBody);

  const explicitIn = g.raw.edges.filter(
    (e) => e.target === nodeId && e.kind === "explicit-link",
  );
  const explicitSources = explicitIn.map((e) => e.source);
  const linkerRefs = uniqBySlug(
    explicitSources
      .map((src) => resolveDocRef(src, g))
      .filter((x): x is KnowledgeDocRef => x !== null),
  ).sort((a, b) => {
    const aIn = g.nodeById.get(a.id)?.links_in ?? 0;
    const bIn = g.nodeById.get(b.id)?.links_in ?? 0;
    return bIn - aIn || a.title.localeCompare(b.title);
  });

  const explicitOutEdges = g.raw.edges.filter(
    (e) => e.source === nodeId && e.kind === "explicit-link",
  );
  const outRefsFromGraph = explicitOutEdges
    .map((e) => resolveDocRef(e.target, g))
    .filter((x): x is KnowledgeDocRef => x !== null);

  const outRefsFromMarkdown = uniqBySlug(
    live.docSlugs
      .map((s) => {
        const e = findDocBySlug(s);
        if (!e) return null;
        return {
          id: slugToKnowledgeNodeId(s),
          slug: e.slug,
          title: e.title,
        } satisfies KnowledgeDocRef;
      })
      .filter((x): x is KnowledgeDocRef => x !== null),
  );

  const linksOut = uniqBySlug([...outRefsFromGraph, ...outRefsFromMarkdown]).sort((a, b) =>
    a.title.localeCompare(b.title),
  );

  const facetsRunbooks = nodeRec?.facets?.runbooks ?? [];

  type RbRow = { name: string; hrefSlug?: string };
  const mergedRunbooks: RbRow[] = [];
  const seenRb = new Set<string>();

  function addRb(row: RbRow): void {
    const k =
      row.hrefSlug !== undefined && row.hrefSlug !== ""
        ? `slug:${row.hrefSlug}`
        : `raw:${row.name.toLowerCase()}`;
    if (seenRb.has(k)) return;
    seenRb.add(k);
    mergedRunbooks.push(row);
  }

  for (const r of facetsRunbooks) {
    addRb({ name: r.name, hrefSlug: r.slug });
  }
  for (const rb of live.runbooks) {
    const entry = findDocBySlug(rb.slugGuess);
    if (entry) addRb({ name: entry.title, hrefSlug: entry.slug });
    else addRb({ name: rb.raw.replace(/^runbook:\s*/i, "").trim() });
  }

  const wsMerged = new Set([
    ...(nodeRec?.facets?.workstreams ?? []),
    ...live.workstreams,
  ]);

  const countDisplay = linkerRefs.length;
  const topLinkers = linkerRefs.slice(0, 5);

  return {
    nodeId,
    slug,
    inIndexedGraph: Boolean(nodeRec),
    stats: {
      read_time_min: nodeRec?.read_time_min ?? 0,
      freshness: nodeRec?.freshness ?? "unknown",
      links_in: nodeRec?.links_in ?? countDisplay,
      links_out: nodeRec?.links_out ?? linksOut.length,
    },
    linkedFrom: { count: countDisplay, topLinkers },
    linksOut,
    relatedRunbooks: mergedRunbooks,
    relatedWorkstreams: [...wsMerged].sort(),
  };
}
