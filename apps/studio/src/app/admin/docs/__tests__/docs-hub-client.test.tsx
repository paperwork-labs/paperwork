import type { ReactElement } from "react";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DocsHubClient } from "../docs-hub-client";
import type { DocHubEntry } from "@/lib/docs";

let mockSearchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  usePathname: () => "/admin/docs",
  useRouter: () => ({
    replace: vi.fn(),
    push: vi.fn(),
    prefetch: vi.fn(),
  }),
  useSearchParams: () => mockSearchParams,
}));

const baseEntry = (overrides: Partial<DocHubEntry>): DocHubEntry => ({
  slug: "sample",
  path: "docs/sample.md",
  title: "Sample",
  summary: "Summary",
  tags: [],
  owners: ["cfo"],
  category: "philosophy",
  exists: true,
  docKind: "philosophy",
  hubCategory: "philosophy",
  lastReviewed: null,
  wordCount: 100,
  readMinutes: 1,
  freshness: "fresh",
  ...overrides,
});

function renderHub(ui: ReactElement) {
  return render(ui);
}

afterEach(() => {
  cleanup();
});

describe("DocsHubClient — view toggle & persona grouping", () => {
  beforeEach(() => {
    mockSearchParams = new URLSearchParams();
  });

  it("defaults to category view (no view param)", () => {
    renderHub(
      <DocsHubClient
        entries={[baseEntry({ slug: "a", owners: ["cfo"] })]}
        readingPaths={[]}
      />,
    );
    expect(screen.getByTestId("docs-hub-view-toggle-category").getAttribute("data-active")).toBe(
      "true",
    );
    expect(screen.getByTestId("docs-hub-filter-all")).toBeTruthy();
    expect(screen.queryByTestId("docs-hub-persona-view")).toBeNull();
  });

  it("view=persona shows team groupings including Executive Council", () => {
    mockSearchParams = new URLSearchParams("view=persona");
    renderHub(
      <DocsHubClient
        entries={[baseEntry({ slug: "tax-doc", title: "Tax", owners: ["cfo", "tax"] })]}
        readingPaths={[]}
      />,
    );
    const personaRoot = screen.getByTestId("docs-hub-persona-view");
    expect(personaRoot).toBeTruthy();
    expect(screen.getByText("Executive Council")).toBeTruthy();
    const execSection = personaRoot.querySelector('[data-team="Executive Council"]');
    expect(execSection).not.toBeNull();
    expect(execSection?.getAttribute("data-team")).toBe("Executive Council");
  });
});
