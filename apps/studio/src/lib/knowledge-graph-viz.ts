import { z } from "zod";

import graphJson from "@/data/knowledge-graph.json";
import {
  FreshnessSchema,
  parseKnowledgeGraphFile,
  vizEdgesFromKnowledgeGraph,
} from "@/lib/knowledge-graph-data";
import { docKindToHubCategory, HUB_CATEGORY_LABEL, type HubDocCategory } from "./doc-metadata";

const LegacyNodeSchema = z.object({
  id: z.string(),
  slug: z.string(),
  title: z.string(),
  category: z.string(),
  read_minutes: z.number(),
  freshness: FreshnessSchema,
  links_in: z.number(),
});

type LegacyNode = z.infer<typeof LegacyNodeSchema>;

const LegacyFileSchema = z.object({
  nodes: z.array(LegacyNodeSchema),
  links: z.array(z.object({ source: z.string(), target: z.string() })),
});

export const KNOW_HOT_ZONE_MIN_LINKS = 4;

export const KNOW_CATEGORY_HEX: Record<HubDocCategory, string> = {
  philosophy: "#2563eb",
  architecture: "#9333ea",
  runbook: "#16a34a",
  strategy: "#ca8a04",
  playbook: "#ea580c",
  "decision-log": "#dc2626",
  uncategorized: "#71717a",
};

export const KNOW_GRAPH_CATEGORY_FILTERS: Array<{ id: HubDocCategory; label: string }> = [
  { id: "philosophy", label: HUB_CATEGORY_LABEL.philosophy },
  { id: "architecture", label: HUB_CATEGORY_LABEL.architecture },
  { id: "strategy", label: HUB_CATEGORY_LABEL.strategy },
  { id: "runbook", label: HUB_CATEGORY_LABEL.runbook },
  { id: "playbook", label: HUB_CATEGORY_LABEL.playbook },
  { id: "decision-log", label: HUB_CATEGORY_LABEL["decision-log"] },
  { id: "uncategorized", label: HUB_CATEGORY_LABEL.uncategorized },
];

export type KnowledgeGraphVizNode = {
  id: string;
  slug: string;
  title: string;
  category: HubDocCategory;
  read_minutes: number;
  links_in: number;
  freshness: z.infer<typeof FreshnessSchema>;
};

export type KnowledgeGraphVizPayload = {
  nodes: KnowledgeGraphVizNode[];
  links: { source: string; target: string }[];
};

export function isKnowHotZoneNode(node: KnowledgeGraphVizNode): boolean {
  return node.freshness === "stale" && node.links_in >= KNOW_HOT_ZONE_MIN_LINKS;
}

let cached: KnowledgeGraphVizPayload | null = null;

export function payloadFromModernFile(): KnowledgeGraphVizPayload {
  const parsed = parseKnowledgeGraphFile(graphJson);
  return {
    nodes: parsed.nodes.map((n): KnowledgeGraphVizNode => ({
      id: n.id,
      slug: n.slug,
      title: n.title,
      category: docKindToHubCategory(n.kind),
      read_minutes: n.read_time_min,
      links_in: n.links_in,
      freshness: n.freshness,
    })),
    links: vizEdgesFromKnowledgeGraph(parsed).map((l) => ({ source: l.source, target: l.target })),
  };
}

function vizNodeFromLegacyRow(n: LegacyNode): KnowledgeGraphVizNode {
  return {
    id: n.id,
    slug: n.slug,
    title: n.title,
    category: docKindToHubCategory(n.category),
    read_minutes: n.read_minutes,
    links_in: n.links_in,
    freshness: n.freshness,
  };
}

export function payloadFromLegacyFile(raw: unknown): KnowledgeGraphVizPayload {
  const legacy = LegacyFileSchema.parse(raw);
  return {
    nodes: legacy.nodes.map((n) => vizNodeFromLegacyRow(n)),
    links: legacy.links.map((l) => ({ source: l.source, target: l.target })),
  };
}

export function getKnowledgeGraphVizPayload(): KnowledgeGraphVizPayload {
  if (cached) return cached;

  const hint = graphJson as { edges?: unknown; links?: unknown };
  if (Array.isArray(hint.edges)) {
    cached = payloadFromModernFile();
  } else if (Array.isArray(hint.links)) {
    cached = payloadFromLegacyFile(graphJson);
  } else {
    throw new Error("knowledge-graph.json must include `edges` (modern) or `links` (legacy)");
  }
  return cached;
}

export function __resetKnowledgeGraphVizCacheForTests(): void {
  cached = null;
}
