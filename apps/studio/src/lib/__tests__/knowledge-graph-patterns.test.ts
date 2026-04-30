import { describe, expect, it } from "vitest";

import { extractDocRelations } from "@/lib/knowledge-graph-patterns";

describe("knowledge-graph-patterns", () => {
  it("extracts wiki slugs runbooks ws and personas", () => {
    const md = `
See [[brain-architecture]] and [[philosophy-index|phil index]] plus [[runbook:brain-deploy-recovery]]
for [[runbook: bogus-name]] gaps.
Track [[ws:WS-76]] with @agent-ops.
`;
    const r = extractDocRelations(md);

    expect(r.docSlugs).toContain("brain-architecture");
    expect(r.docSlugs).toContain("philosophy-index");
    expect(r.workstreams).toContain("WS-76");
    expect(r.runbooks.map((x) => x.slugGuess)).toEqual(
      expect.arrayContaining(["brain-deploy-recovery", "bogus-name"]),
    );

    expect(r.personas).toContain("agent-ops");
  });
});
