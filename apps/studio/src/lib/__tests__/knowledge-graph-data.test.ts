import { describe, expect, it } from "vitest";

import graphJson from "@/data/knowledge-graph.json";
import {
  getKnowledgeRailForSlug,
  parseKnowledgeGraphFile,
  vizEdgesFromKnowledgeGraph,
} from "@/lib/knowledge-graph-data";

describe("knowledge-graph-data", () => {
  it("parses bundled knowledge-graph.json with nodes + edges referencing known ids", () => {
    const parsed = parseKnowledgeGraphFile(graphJson);
    expect(parsed.nodes.length).toBeGreaterThanOrEqual(20);
    expect(parsed.edges.length).toBeGreaterThanOrEqual(10);
    const ids = new Set(parsed.nodes.map((n) => n.id));
    expect(ids.has("BRAIN_ARCHITECTURE")).toBe(true);

    const vizEdges = vizEdgesFromKnowledgeGraph(parsed);
    expect(vizEdges.length).toBeGreaterThanOrEqual(1);
    for (const edge of vizEdges) {
      expect(ids.has(edge.source)).toBe(true);
      expect(ids.has(edge.target)).toBe(true);
      expect(edge.kind).toBe("explicit-link");
    }
  });

  it("surfaced backlinks + facets for seeded Brain Architecture", () => {
    const rail = getKnowledgeRailForSlug("brain-architecture", "");
    expect(rail.linkedFrom.count).toBeGreaterThanOrEqual(3);
    expect(rail.linkedFrom.topLinkers.length).toBeLessThanOrEqual(5);

    expect(rail.relatedWorkstreams.join(",")).toContain("WS-76");
    expect(rail.relatedRunbooks.some((r) => r.hrefSlug === "brain-deploy-recovery")).toBe(true);

    expect(rail.linksOut.some((x) => x.slug === "brain-personas-generated")).toBe(true);
  });
});
