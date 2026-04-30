import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ProductHealthShell } from "@/app/admin/products/[slug]/health/product-health-shell";
import {
  deriveHeroRollup,
  loadProductHealthBrainState,
  type ProductHealthBrainState,
} from "@/lib/product-health-brain";

function emptyState(over: Partial<ProductHealthBrainState> = {}): ProductHealthBrainState {
  return {
    slug: "filefree",
    brainConfigured: true,
    brainDataPlaneError: null,
    deployTelemetryErrors: [],
    probesCheckedAt: null,
    cujRows: [],
    probeResultsSpark: [],
    probeRuns: [],
    errorTotal24h: null,
    errorFingerprints: [],
    vercelDeploy: null,
    renderDeploy: null,
    ...over,
  };
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  delete process.env.BRAIN_API_URL;
  delete process.env.BRAIN_API_SECRET;
});

describe("deriveHeroRollup", () => {
  it("returns healthy when probes pass and no errors", () => {
    const state = emptyState({
      cujRows: [
        { id: "a", name: "Login", status: "pass", lastRunAt: "2026-04-30T12:00:00Z" },
      ],
      probeResultsSpark: [{ t: "2026-04-30T10:00:00Z", pass: true }],
      probeRuns: [{ at: "2026-04-30T10:00:00Z", assertion: "ok", status: "pass" }],
      errorTotal24h: 0,
      probesCheckedAt: "2026-04-30T12:00:00Z",
    });
    expect(deriveHeroRollup(state).rollup).toBe("healthy");
  });

  it("returns degraded when errors present", () => {
    const state = emptyState({
      cujRows: [{ id: "a", name: "Login", status: "pass", lastRunAt: null }],
      probeResultsSpark: [{ t: "2026-04-30T10:00:00Z", pass: true }],
      probeRuns: [{ at: "2026-04-30T10:00:00Z", assertion: "ok", status: "pass" }],
      errorTotal24h: 3,
    });
    expect(deriveHeroRollup(state).rollup).toBe("degraded");
  });

  it("returns down when a CUJ fails", () => {
    const state = emptyState({
      cujRows: [
        { id: "a", name: "Login", status: "pass", lastRunAt: null },
        { id: "b", name: "Checkout", status: "fail", lastRunAt: null },
      ],
      probeResultsSpark: [{ t: "2026-04-30T10:00:00Z", pass: true }],
      probeRuns: [{ at: "2026-04-30T10:00:00Z", assertion: "ok", status: "pass" }],
      errorTotal24h: 0,
    });
    expect(deriveHeroRollup(state).rollup).toBe("down");
  });

  it("returns down when brain data plane error", () => {
    const state = emptyState({
      brainDataPlaneError: "Brain API unreachable — check BRAIN_API_URL and BRAIN_API_SECRET in the Studio environment. (probes/health: HTTP 500)",
    });
    expect(deriveHeroRollup(state).rollup).toBe("down");
  });
});

describe("ProductHealthShell", () => {
  it("renders error banner when brainDataPlaneError is set (5xx path)", () => {
    const state = emptyState({
      brainDataPlaneError:
        "Brain API unreachable — check BRAIN_API_URL and BRAIN_API_SECRET in the Studio environment. (probes/health: HTTP 500: err)",
    });
    const { rollup, narrative } = deriveHeroRollup(state);
    render(
      <ProductHealthShell
        productName="FileFree"
        state={state}
        heroRollup={rollup}
        narrative={narrative}
        lastCheckedLabel={null}
      />,
    );
    expect(screen.getByTestId("brain-api-error-banner")).toBeTruthy();
    const banner = screen.getByTestId("brain-api-error-banner");
    expect(within(banner).getByText("Brain API unreachable — check BRAIN_API_URL / BRAIN_API_SECRET")).toBeTruthy();
    expect(screen.getByTestId("health-status-pill").textContent?.trim()).toBe("Down");
  });

  it("renders healthy pill when probes pass", () => {
    const state = emptyState({
      cujRows: [{ id: "x", name: "CUJ", status: "pass", lastRunAt: "2026-04-30T12:00:00Z" }],
      probeResultsSpark: [{ t: "2026-04-30T11:00:00Z", pass: true }],
      probeRuns: [{ at: "2026-04-30T11:00:00Z", assertion: "smoke", status: "pass" }],
      errorTotal24h: 0,
    });
    const { rollup, narrative } = deriveHeroRollup(state);
    render(
      <ProductHealthShell
        productName="FileFree"
        state={state}
        heroRollup={rollup}
        narrative={narrative}
        lastCheckedLabel="Apr 30, 2026, 12:00 PM UTC"
      />,
    );
    expect(screen.queryByTestId("brain-api-error-banner")).toBeNull();
    expect(screen.getByTestId("health-status-pill").textContent?.trim()).toBe("Healthy");
  });
});

describe("loadProductHealthBrainState", () => {
  it("surfaces brainDataPlaneError when probes/health returns 500", async () => {
    process.env.BRAIN_API_URL = "https://brain.test";
    process.env.BRAIN_API_SECRET = "secret";

    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const u = typeof input === "string" ? input : input.toString();
        if (u.includes("/probes/health")) {
          return new Response("Internal Server Error", { status: 500 });
        }
        if (u.includes("/errors/aggregates")) {
          return new Response(JSON.stringify({ success: true, data: { total_count: 0, fingerprints: [] } }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }
        if (u.includes("/probes/results")) {
          return new Response(JSON.stringify({ success: true, data: { results: [] } }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }
        if (u.includes("/vercel-quota")) {
          return new Response(JSON.stringify({ success: true, data: { batch_at: null, count: 0, snapshots: [] } }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }
        if (u.includes("/render-quota")) {
          return new Response(JSON.stringify({ success: true, data: { snapshot: null, top_services_by_minutes: [] } }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }
        return new Response("not found", { status: 404 });
      }),
    );

    const state = await loadProductHealthBrainState("filefree");
    expect(state.brainDataPlaneError).toMatch(/Brain API unreachable/);
    expect(state.brainDataPlaneError).toMatch(/probes\/health/);
  });
});
