import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import workstreamsJson from "@/data/workstreams.json";

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({ replace: vi.fn(), refresh: vi.fn() }),
  usePathname: () => "/admin/workstreams",
}));

import { WorkstreamsFileSchema, computeKpis } from "@/lib/workstreams/schema";

vi.mock("next/headers", () => ({
  headers: async () =>
    new Headers({
      host: "localhost:3000",
      "x-forwarded-proto": "http",
    }),
}));

function epicHierarchyPayload() {
  return {
    success: true as const,
    data: [
      {
        id: "goal-1",
        objective: "Ship Studio as Company HQ",
        status: "active",
        horizon: "Q2-2026",
        epics: [
          {
            id: "WS-82",
            title: "Studio HQ Complete Overhaul",
            status: "in_progress",
            priority: 1,
            percent_done: 85,
            owner_employee_slug: "dev",
            brief_tag: "hq",
            description: null,
            sprints: [
              {
                id: "sp-1",
                title: "Wave 0: Stop the bleed",
                status: "shipped",
                ordinal: 0,
                tasks: [
                  {
                    id: "t-1",
                    title: "PR-0a Vercel narrow cuts",
                    status: "merged",
                    github_pr: 598,
                    github_pr_url: "https://github.com/paperwork-labs/paperwork/pull/598",
                    owner_employee_slug: "dev",
                    ordinal: 0,
                  },
                ],
              },
            ],
          },
        ],
      },
    ],
  };
}

const fetchMock = vi.fn();

describe("/admin/workstreams page module", () => {
  beforeEach(() => {
    cleanup();
    vi.resetModules();
    vi.unstubAllEnvs();
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockImplementation(async (url: string | URL) => {
      const u = String(url);
      if (u.includes("/admin/goals") && u.includes("include=epics.sprints.tasks")) {
        return new Response(JSON.stringify(epicHierarchyPayload()), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      return new Response("not found", { status: 404 });
    });
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllEnvs();
  });

  it("parses seeded workstreams.json without error", () => {
    const file = WorkstreamsFileSchema.parse(workstreamsJson);
    const kpis = computeKpis(file);
    expect(kpis.total).toBeGreaterThan(0);
  });

  it("default export renders Epics tree when Brain returns hierarchy", async () => {
    vi.stubEnv("BRAIN_API_URL", "http://brain.test");
    vi.stubEnv("BRAIN_API_SECRET", "test-secret");
    const { default: AdminWorkstreamsPage } = await import("../page");
    const tree = await AdminWorkstreamsPage();
    expect(tree).toBeTruthy();
    render(tree);
    expect(screen.getByRole("tab", { name: "Tree" })).toBeTruthy();
    expect(screen.getByRole("tab", { name: "PR Pipeline" })).toBeTruthy();
    expect(screen.queryByRole("tab", { name: "Board" })).toBeNull();
    expect(await screen.findByText(/Ship Studio as Company HQ/)).toBeTruthy();
    expect(await screen.findByTestId("epics-tree")).toBeTruthy();
  });

  it("surfaces error when Brain is configured and goals hierarchy returns 5xx", async () => {
    vi.stubEnv("BRAIN_API_URL", "http://brain.test");
    vi.stubEnv("BRAIN_API_SECRET", "test-secret");
    fetchMock.mockImplementation(async (url: string | URL) => {
      if (String(url).includes("/admin/goals") && String(url).includes("include=epics")) {
        return new Response("", { status: 503 });
      }
      return new Response("not found", { status: 404 });
    });
    const { default: AdminWorkstreamsPage } = await import("../page");
    const tree = await AdminWorkstreamsPage();
    render(tree);
    expect(await screen.findByTestId("epics-brain-error")).toBeTruthy();
    expect(await screen.findByText(/Brain epic-hierarchy: HTTP 503/)).toBeTruthy();
  });
});
