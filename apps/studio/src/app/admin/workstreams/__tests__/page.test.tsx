import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import workstreamsJson from "@/data/workstreams.json";
import {
  WorkstreamsFileSchema,
  computeKpis,
} from "@/lib/workstreams/schema";

vi.mock("next/headers", () => ({
  headers: async () =>
    new Headers({
      host: "localhost:3000",
      "x-forwarded-proto": "http",
    }),
}));

const fetchMock = vi.fn();

describe("/admin/workstreams page module", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockImplementation(async (url: string | URL) => {
      if (String(url).includes("/api/admin/workstreams")) {
        return new Response(JSON.stringify(workstreamsJson), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      return new Response("not found", { status: 404 });
    });
  });

  it("parses seeded workstreams.json without error", () => {
    const file = WorkstreamsFileSchema.parse(workstreamsJson);
    const kpis = computeKpis(file);
    expect(kpis.total).toBeGreaterThan(0);
  });

  it("default export resolves to rendered markup when Brain proxy returns JSON", async () => {
    const { default: AdminWorkstreamsPage } = await import("../page");
    const tree = await AdminWorkstreamsPage();
    expect(tree).toBeTruthy();
    render(tree);
    expect(screen.queryByTestId("workstreams-stale-banner")).toBeNull();
  });

  it("shows stale snapshot banner when Brain proxy returns 5xx", async () => {
    fetchMock.mockImplementation(async () => new Response("", { status: 503 }));
    const { default: AdminWorkstreamsPage } = await import("../page");
    const tree = await AdminWorkstreamsPage();
    render(tree);
    expect(screen.getByTestId("workstreams-stale-banner").textContent).toMatch(
      /Live Brain unavailable/,
    );
  });
});
