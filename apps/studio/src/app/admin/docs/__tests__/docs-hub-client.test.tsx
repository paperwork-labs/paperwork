import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { DocHubEntry } from "@/lib/docs";

import { DocsHubClient } from "../docs-hub-client";

let mockSearchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useSearchParams: () => mockSearchParams,
  useRouter: () => ({ replace: vi.fn() }),
  usePathname: () => "/admin/docs",
}));

function hubEntry(partial: Partial<DocHubEntry> & Pick<DocHubEntry, "slug" | "title">): DocHubEntry {
  return {
    path: `docs/${partial.slug}.md`,
    summary: "",
    tags: [],
    owners: [],
    category: "reference",
    exists: true,
    docKind: null,
    hubCategory: "uncategorized",
    lastReviewed: null,
    wordCount: 0,
    readMinutes: 0,
    freshness: "unknown",
    ...partial,
  };
}

describe("DocsHubClient", () => {
  afterEach(() => {
    cleanup();
  });

  it("defaults to category view", () => {
    mockSearchParams = new URLSearchParams();
    render(
      <DocsHubClient
        entries={[hubEntry({ slug: "a", title: "Alpha" })]}
        readingPaths={[]}
      />,
    );
    expect(screen.getByTestId("docs-hub-view-category").getAttribute("aria-pressed")).toBe(
      "true",
    );
    expect(screen.getByTestId("docs-hub-filter-all")).toBeTruthy();
  });

  it("shows persona grouping when view=persona", () => {
    mockSearchParams = new URLSearchParams("view=persona");
    render(
      <DocsHubClient
        entries={[
          hubEntry({
            slug: "budget",
            title: "Budget doc",
            owners: ["cfo"],
          }),
        ]}
        readingPaths={[]}
      />,
    );
    const personaToggles = screen.getAllByTestId("docs-hub-view-persona");
    expect(personaToggles.filter((el) => el.getAttribute("aria-pressed") === "true")).toHaveLength(
      1,
    );
    expect(screen.getByRole("heading", { name: /executive council/i })).toBeTruthy();
    expect(screen.getByText("cfo")).toBeTruthy();
  });
});
