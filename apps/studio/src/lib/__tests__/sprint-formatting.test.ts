import { describe, expect, it } from "vitest";

import { normalizeSprintSource } from "../normalize-sprint-source";
import { buildTracker } from "../sprint-tracker";
import type { Sprint } from "../tracker";

describe("normalizeSprintSource", () => {
  it("normalizes whitespace, tables, and odd code fences", () => {
    const raw = [
      "Intro line",
      "",
      "",
      "",
      "| col | val |",
      "|---|---|",
      "| a | b |",
      "",
      "```ts",
      "const x = 1",
      "",
    ].join("\n");
    expect(normalizeSprintSource(raw)).toMatchSnapshot();
  });
});

describe("buildTracker shipped follow-ups", () => {
  it("reclassifies pending work to deferred / keeps dropped", () => {
    const sprint: Sprint = {
      slug: "fixture",
      path: "docs/sprints/TEST.md",
      title: "Test",
      status: "shipped",
      effective_status: "shipped",
      outcome_bullets: ["shipped: Landed the thing in #123", "active: not done yet in outcomes"],
      followups: ["dropped: cut scope for Q3", "Need to finish wiring"],
    };
    const items = buildTracker(sprint);
    expect(items.map((i) => i.status)).toMatchSnapshot();
  });
});
