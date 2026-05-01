import { describe, expect, it } from "vitest";

import { groupDocsByPersona } from "../docs-hub-persona";

describe("groupDocsByPersona", () => {
  it("places cfo under Executive Council", () => {
    const groups = groupDocsByPersona([
      { slug: "x", title: "X", owners: ["cfo"] },
    ]);
    const council = groups.find((g) => g.team === "Executive Council");
    expect(council).toBeTruthy();
    expect(council?.personas.some((p) => p.slug === "cfo")).toBe(true);
  });

  it("routes docs with no owners to unowned under Other", () => {
    const groups = groupDocsByPersona([{ slug: "n", title: "N", owners: [] }]);
    const other = groups.find((g) => g.team === "Other");
    expect(other?.personas.some((p) => p.slug === "unowned")).toBe(true);
  });

  it("lists a doc under each owner persona when multiple owners", () => {
    const groups = groupDocsByPersona([
      {
        slug: "shared",
        title: "Shared",
        owners: ["cfo", "engineering"],
      },
    ]);
    let hits = 0;
    for (const g of groups) {
      for (const p of g.personas) {
        hits += p.docs.filter((d) => d.slug === "shared").length;
      }
    }
    expect(hits).toBe(2);
  });
});
