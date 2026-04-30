import { describe, expect, it } from "vitest";

import {
  extractModelAssignmentSection,
  parseEaTagRouting,
  parseMarkdownTables,
  parsePersonaEstCostPerRunUsd,
} from "../personas-pure";
import { resolvePersonasTab } from "../personas-tab-params";

describe("resolvePersonasTab", () => {
  it("defaults to registry for missing or invalid tab params", () => {
    expect(resolvePersonasTab(undefined)).toBe("registry");
    expect(resolvePersonasTab("bogus")).toBe("registry");
  });

  it("accepts all People dashboard tab ids", () => {
    expect(resolvePersonasTab("registry")).toBe("registry");
    expect(resolvePersonasTab("activity")).toBe("activity");
    expect(resolvePersonasTab("promotions-queue")).toBe("promotions-queue");
    expect(resolvePersonasTab("open-roles")).toBe("open-roles");
    expect(resolvePersonasTab("cost")).toBe("cost");
    expect(resolvePersonasTab("routing")).toBe("routing");
    expect(resolvePersonasTab("model-registry")).toBe("model-registry");
  });
});

describe("extractModelAssignmentSection", () => {
  it("returns null when section missing", () => {
    expect(extractModelAssignmentSection("# Hello\n\nBody")).toBeNull();
  });

  it("extracts body until next heading", () => {
    const md = "## Model Assignment\n\nUse Claude.\n\n## Next\n\nNo";
    expect(extractModelAssignmentSection(md)).toContain("Use Claude");
    expect(extractModelAssignmentSection(md)).not.toContain("Next");
  });
});

describe("parseEaTagRouting", () => {
  it("merges tag directory rows with smart routing overrides", () => {
    const md = `
### Tag Directory

| Historical Slack channel | Channel ID | Canonical tag | Role |
|---|---|---|---|
| \`#daily-briefing\` | \`C0\` | \`daily-briefing\` | EA morning briefing |
| \`#engineering\` | \`C1\` | \`pr-review\` | PR summaries |

### Smart Persona Routing

1. **Tag and conversation context**: \`pr-review\` → Engineering, \`decision\` → Strategy
`;
    const rows = parseEaTagRouting(md);
    expect(rows.some((r) => r.tag === "daily-briefing")).toBe(true);
    const pr = rows.find((r) => r.tag === "pr-review");
    expect(pr?.routingTarget).toBe("engineering");
  });
});

describe("parseMarkdownTables", () => {
  it("parses a basic pipe table after a heading", () => {
    const md = `## Example\n\n| A | B |\n|---|---|\n| 1 | 2 |\n`;
    const tables = parseMarkdownTables(md);
    expect(tables.length).toBeGreaterThanOrEqual(1);
    expect(tables[0].headers).toEqual(["A", "B"]);
    expect(tables[0].rows[0]).toEqual(["1", "2"]);
  });
});

describe("parsePersonaEstCostPerRunUsd", () => {
  it("reads midpoint estimates from the Brain PersonaSpec table", () => {
    const md = `
### Brain PersonaSpec (default → escalation on \`escalate_if\` match)

| Persona | Entry / trigger | Default model | Escalation model | Est. $ / run |
| --- | --- | --- | --- | --- |
| agent-ops | Brain \`process\` | \`claude-sonnet-4-20250514\` | \`claude-opus-4-20250618\` | $0.05–0.60 |
`;
    const map = parsePersonaEstCostPerRunUsd(md);
    expect(map.get("agent-ops")).toBeCloseTo(0.325, 5);
  });
});
