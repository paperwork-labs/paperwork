import { beforeEach, describe, expect, it } from "vitest";

import {
  __resetKnowledgeGraphVizCacheForTests,
  getKnowledgeGraphVizPayload,
  isKnowHotZoneNode,
} from "@/lib/knowledge-graph-viz";

describe("knowledge-graph-viz", () => {
  beforeEach(() => {
    __resetKnowledgeGraphVizCacheForTests();
  });

  it("loads bundled graph with viz links anchored to ids", () => {
    const g = getKnowledgeGraphVizPayload();
    expect(g.nodes.length).toBeGreaterThanOrEqual(20);
    expect(g.links.length).toBeGreaterThanOrEqual(10);

    const ids = new Set(g.nodes.map((n) => n.id));
    for (const l of g.links) {
      expect(ids.has(l.source)).toBe(true);
      expect(ids.has(l.target)).toBe(true);
    }
  });

  it("hot zone = stale and popular by links_in", () => {
    expect(
      isKnowHotZoneNode({
        id: "X",
        slug: "x",
        title: "X",
        category: "philosophy",
        read_minutes: 1,
        links_in: 5,
        freshness: "stale",
      }),
    ).toBe(true);
    expect(
      isKnowHotZoneNode({
        id: "Y",
        slug: "y",
        title: "Y",
        category: "philosophy",
        read_minutes: 1,
        links_in: 5,
        freshness: "fresh",
      }),
    ).toBe(false);
  });
});
