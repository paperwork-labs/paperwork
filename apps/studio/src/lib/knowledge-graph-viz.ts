import { z } from "zod";

import graphJson from "@/data/knowledge-graph.json";
import { docKindToHubCategory, HUB_CATEGORY_LABEL, type HubDocCategory } from "./doc-metadata";

const FreshnessSchema = z.enum(["fresh", "aging", "stale", "unknown"]);

const RawNodeSchema = z.object({
  id: z.string(),
  slug: z.string(),
  title: z.string(),
  category: z.string(),
  read_minutes: z.number(),
  links_in: z.number(),
  freshness: FreshnessSchema,
});

const LinkSchema = z.object({
  source: z.string(),
  target: z.string(),
});

const FileSchema = z.object({
  nodes: z.array(RawNodeSchema),
  links: z.array(LinkSchema),
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

export function getKnowledgeGraphVizPayload(): KnowledgeGraphVizPayload {
  if (cached) return cached;
  const parsed = FileSchema.parse(graphJson);
  cached = {
    nodes: parsed.nodes.map((n) => ({
      id: n.id,
      slug: n.slug,
      title: n.title,
      category: docKindToHubCategory(n.category),
      read_minutes: n.read_minutes,
      links_in: n.links_in,
      freshness: n.freshness,
    })),
    links: parsed.links,
  };
  return cached;
}
