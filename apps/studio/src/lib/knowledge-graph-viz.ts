import graphJson from "@/data/knowledge-graph.json";
import {
  parseKnowledgeGraphFile,
  vizEdgesFromKnowledgeGraph,
  type KnowledgeGraphFileParsed,
} from "@/lib/knowledge-graph-data";
import {
  docKindToHubCategory,
  HUB_CATEGORY_LABEL,
  type FreshnessLevel,
  type HubDocCategory,
} from "./doc-metadata";

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
  freshness: FreshnessLevel;
};

export type KnowledgeGraphVizPayload = {
  nodes: KnowledgeGraphVizNode[];
  links: { source: string; target: string }[];
};

export function isKnowHotZoneNode(node: KnowledgeGraphVizNode): boolean {
  return node.freshness === "stale" && node.links_in >= KNOW_HOT_ZONE_MIN_LINKS;
}

function toVizPayload(parsed: KnowledgeGraphFileParsed): KnowledgeGraphVizPayload {
  const links = vizEdgesFromKnowledgeGraph(parsed).map((e) => ({
    source: e.source,
    target: e.target,
  }));
  const nodes: KnowledgeGraphVizNode[] = parsed.nodes.map((n) => ({
    id: n.id,
    slug: n.slug,
    title: n.title,
    category: docKindToHubCategory(n.kind),
    read_minutes: n.read_time_min,
    links_in: n.links_in,
    freshness: n.freshness,
  }));
  return { nodes, links };
}

let cached: KnowledgeGraphVizPayload | null = null;

export function getKnowledgeGraphVizPayload(): KnowledgeGraphVizPayload {
  if (cached) return cached;
  const parsed = parseKnowledgeGraphFile(graphJson);
  cached = toVizPayload(parsed);
  return cached;
}

export function __resetKnowledgeGraphVizCacheForTests(): void {
  cached = null;
}
