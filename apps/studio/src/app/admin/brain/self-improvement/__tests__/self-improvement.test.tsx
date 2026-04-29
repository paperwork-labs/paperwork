import { Suspense } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mockSearch = new URLSearchParams("tab=index");

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    replace: vi.fn((url: string) => {
      mockSearch.set("tab", new URL(url, "http://localhost").searchParams.get("tab") ?? "index");
    }),
  }),
  usePathname: () => "/admin/brain/self-improvement",
  useSearchParams: () => mockSearch,
}));

const fetchMock = vi.fn();

describe("Brain self-improvement page", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    mockSearch.set("tab", "index");
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockImplementation(async (url: string | URL) => {
      const u = String(url);
      if (u.includes("/api/admin/operating-score")) {
        return new Response(
          JSON.stringify({
            success: true,
            data: {
              current: null,
              history_last_12: [],
              gates: { l4_pass: false, l5_pass: false, lowest_pillar: "" },
            },
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (u.includes("/api/admin/brain/self-improvement/summary")) {
        return new Response(
          JSON.stringify({
            success: true,
            data: {
              current_tier: "data-only",
              clean_merge_count: 2,
              progress_to_next_tier_pct: 4.0,
              positive_retro_streak_weeks: 0,
              spotlight_rule: { id: "r1", when: "when x", confidence: "high", note: "n" },
            },
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (u.includes("/api/admin/brain/self-improvement/learning-state")) {
        return new Response(
          JSON.stringify({
            success: true,
            data: {
              ok: true,
              error: null,
              open_candidates: 3,
              accepted_candidates: 10,
              declined_candidates: 2,
              superseded_candidates: 1,
              conversion_rate: 83.33,
              generated_at: "2026-04-29T00:00:00Z",
            },
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (u.includes("/api/admin/brain/self-improvement/promotions")) {
        return new Response(
          JSON.stringify({
            success: true,
            data: {
              current_tier: "data-only",
              clean_merge_count: 5,
              eligible_for_promotion: false,
              progress_to_next_tier_pct: 10.0,
              merges_required_for_next_tier: 50,
              recent_merges_last_10: [],
              recent_reverts_last_5: [],
              graduation_rules_doc_slug: "brain-self-merge-graduation",
            },
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (u.includes("/api/admin/brain/self-improvement/outcomes")) {
        return new Response(
          JSON.stringify({
            success: true,
            data: {
              count: 1,
              buckets: {
                reverted: [],
                "7d_still_passing": [],
                "24h_still_passing": [],
                "1h_pass": [{ pr_number: 400, merged_at: "2026-04-28T12:00:00Z" }],
                pending_observation: [],
              },
            },
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (u.includes("/api/admin/brain/self-improvement/retros")) {
        return new Response(
          JSON.stringify({
            success: true,
            data: {
              count: 1,
              retros: [
                {
                  week_ending: "2026-04-28T00:00:00Z",
                  computed_at: "2026-04-29T08:30:00Z",
                  summary: {
                    pos_total_change: 1.2,
                    merges: 3,
                    reverts: 0,
                    incidents: 0,
                    candidates_proposed: 1,
                    candidates_promoted: 0,
                  },
                  highlights: ["h"],
                  notes: "",
                },
              ],
            },
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (u.includes("/api/admin/brain/self-improvement/automation-state")) {
        return new Response(
          JSON.stringify({
            success: true,
            data: {
              scheduler_running: false,
              jobs: [],
              note: "test note",
            },
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (u.includes("/api/admin/brain/self-improvement/procedural-memory")) {
        return new Response(
          JSON.stringify({
            success: true,
            data: {
              count: 2,
              applies_to_values: ["cheap-agents"],
              rules: [
                {
                  id: "rule_a",
                  when: "when",
                  do: "do",
                  source: "src",
                  learned_at: "2026-04-28T00:00:00Z",
                  confidence: "high",
                  applies_to: ["cheap-agents"],
                },
                {
                  id: "rule_b",
                  when: "other",
                  do: "act",
                  source: "src2",
                  learned_at: "2026-04-27T00:00:00Z",
                  confidence: "medium",
                  applies_to: ["orchestrator"],
                },
              ],
              error: null,
            },
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      return new Response("not found", { status: 404 });
    });
  });

  it("deep-links to retros tab", async () => {
    mockSearch.set("tab", "retros");
    const { SelfImprovementClient } = await import("../self-improvement-client");
    render(
      <Suspense fallback={null}>
        <SelfImprovementClient />
      </Suspense>,
    );
    await waitFor(() => expect(screen.getByTestId("retros-tab")).toBeTruthy());
    expect(screen.getByTestId("retro-card")).not.toBeNull();
  });

  it("learning tab shows populated counts", async () => {
    mockSearch.set("tab", "learning");
    const { SelfImprovementClient } = await import("../self-improvement-client");
    render(
      <Suspense fallback={null}>
        <SelfImprovementClient />
      </Suspense>,
    );
    await waitFor(() => expect(screen.getByTestId("open-candidates").textContent).toBe("3"));
    expect(screen.getByTestId("accepted-candidates").textContent).toBe("10");
  });

  it("exposes correct tab link hrefs for deep-linking", async () => {
    mockSearch.set("tab", "index");
    const { SelfImprovementClient } = await import("../self-improvement-client");
    render(
      <Suspense fallback={null}>
        <SelfImprovementClient />
      </Suspense>,
    );
    await waitFor(() => expect(screen.getAllByRole("link", { name: /^Retros$/i }).length).toBeGreaterThan(0));
    const retrosLinks = screen.getAllByRole("link", { name: /^Retros$/i });
    expect(retrosLinks[0]?.getAttribute("href")).toBe("/admin/brain/self-improvement?tab=retros");
  });
});

describe("Self-improvement tab empty states", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", async (url: string | URL) => {
      const u = String(url);
      if (u.includes("outcomes")) {
        return new Response(
          JSON.stringify({
            success: true,
            data: {
              count: 0,
              buckets: {
                reverted: [],
                "7d_still_passing": [],
                "24h_still_passing": [],
                "1h_pass": [],
                pending_observation: [],
              },
            },
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (u.includes("retros")) {
        return new Response(
          JSON.stringify({ success: true, data: { count: 0, retros: [] } }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (u.includes("automation-state")) {
        return new Response(
          JSON.stringify({ success: true, data: { scheduler_running: false, jobs: [], note: "x" } }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      return new Response("", { status: 404 });
    });
  });

  it("outcomes empty message", async () => {
    const { OutcomesTab } = await import("../tabs/outcomes-tab");
    render(<OutcomesTab />);
    await waitFor(() => expect(screen.getByTestId("outcomes-empty")).not.toBeNull());
  });

  it("retros empty message", async () => {
    const { RetrosTab } = await import("../tabs/retros-tab");
    render(<RetrosTab />);
    await waitFor(() => expect(screen.getByTestId("retros-empty")).not.toBeNull());
  });

  it("automation empty message", async () => {
    const { AutomationStateTab } = await import("../tabs/automation-state-tab");
    render(<AutomationStateTab />);
    await waitFor(() => expect(screen.getByTestId("automation-empty")).not.toBeNull());
  });
});

describe("ProceduralMemoryTab filter", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", async () =>
      new Response(
        JSON.stringify({
          success: true,
          data: {
            count: 2,
            applies_to_values: ["cheap-agents", "orchestrator"],
            rules: [
              {
                id: "rule_a",
                when: "w",
                do: "d",
                source: "s",
                learned_at: "2026-04-28T00:00:00Z",
                confidence: "high",
                applies_to: ["cheap-agents"],
              },
              {
                id: "rule_b",
                when: "w2",
                do: "d2",
                source: "s2",
                learned_at: "2026-04-27T00:00:00Z",
                confidence: "medium",
                applies_to: ["orchestrator"],
              },
            ],
            error: null,
          },
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
  });

  it("filters by applies_to chip", async () => {
    const { ProceduralMemoryTab } = await import("../tabs/procedural-memory-tab");
    const user = (await import("@testing-library/user-event")).default.setup();
    render(<ProceduralMemoryTab />);
    await waitFor(() => expect(screen.getAllByTestId("procedural-rule").length).toBe(2));
    await user.click(screen.getByTestId("chip-orchestrator"));
    await waitFor(() => expect(screen.getAllByTestId("procedural-rule").length).toBe(1));
    expect(screen.getByText("rule_b")).not.toBeNull();
  });
});
