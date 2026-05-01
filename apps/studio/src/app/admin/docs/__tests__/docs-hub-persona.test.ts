import { describe, expect, it } from "vitest";

import {
  buildTeamSections,
  teamForPersonaSlug,
  type PersonaTeamSection,
} from "../docs-hub-persona";
import type { DocHubEntry } from "@/lib/docs";

const entry = (owners: string[], slug = "x"): DocHubEntry => ({
  slug,
  path: `docs/${slug}.md`,
  title: `Title ${slug}`,
  summary: "S",
  tags: [],
  owners,
  category: "philosophy",
  exists: true,
  docKind: "philosophy",
  hubCategory: "philosophy",
  lastReviewed: null,
  wordCount: 1,
  readMinutes: 1,
  freshness: "fresh",
});

describe("docs hub persona teams", () => {
  it("maps cfo to Executive Council", () => {
    expect(teamForPersonaSlug("cfo")).toBe("Executive Council");
  });

  it("buildTeamSections places cfo under Executive Council", () => {
    const sections = buildTeamSections([entry(["cfo"], "doc-one")]);
    const exec = sections.find((s: PersonaTeamSection) => s.team === "Executive Council");
    expect(exec).toBeDefined();
    const cfo = exec?.personas.find((p: { slug: string }) => p.slug === "cfo");
    expect(cfo?.docs.map((d: DocHubEntry) => d.slug)).toEqual(["doc-one"]);
  });
});
