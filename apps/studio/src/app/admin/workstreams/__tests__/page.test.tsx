import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import workstreamsJson from "@/data/workstreams.json";

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({ replace: vi.fn() }),
  usePathname: () => "/admin/workstreams",
}));
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

function brainEnvelopePayload() {
  return {
    ...workstreamsJson,
    generated_at: "2026-04-28T12:00:00Z",
    source: "brain-writeback" as const,
    ttl_seconds: 60,
    writeback_last_run_at: null,
  };
}

const fetchMock = vi.fn();

describe("/admin/workstreams page module", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.unstubAllEnvs();
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockImplementation(async (url: string | URL) => {
      if (String(url).includes("/api/admin/workstreams")) {
        return new Response(JSON.stringify(brainEnvelopePayload()), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      return new Response("not found", { status: 404 });
    });
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("parses seeded workstreams.json without error", () => {
    const file = WorkstreamsFileSchema.parse(workstreamsJson);
    const kpis = computeKpis(file);
    expect(kpis.total).toBeGreaterThan(0);
  });

  it("default export resolves to rendered markup when Brain proxy returns JSON", async () => {
    vi.stubEnv("BRAIN_API_URL", "http://brain.test");
    vi.stubEnv("BRAIN_API_SECRET", "test-secret");
    const { default: AdminWorkstreamsPage } = await import("../page");
    const tree = await AdminWorkstreamsPage();
    expect(tree).toBeTruthy();
    render(tree);
    expect(screen.queryByTestId("workstreams-stale-banner")).toBeNull();
    expect(screen.getByTestId("workstreams-brain-freshness-banner").textContent).toMatch(
      /Last sync:/,
    );
  });

  it("surfaces error when Brain is configured and proxy returns 5xx", async () => {
    vi.stubEnv("BRAIN_API_URL", "http://brain.test");
    vi.stubEnv("BRAIN_API_SECRET", "test-secret");
    fetchMock.mockImplementation(async () => new Response("", { status: 503 }));
    const { default: AdminWorkstreamsPage } = await import("../page");
    const tree = await AdminWorkstreamsPage();
    render(tree);
    expect(screen.getByRole("alert").textContent).toMatch(/Brain workstreams unavailable \(HTTP 503\)/);
  });
});
