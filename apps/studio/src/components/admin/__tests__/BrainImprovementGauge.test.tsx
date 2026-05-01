import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { BrainImprovementCurrent, BrainImprovementResponse } from "@/types/brain-improvement";

import { BrainImprovementGaugeBody } from "../BrainImprovementGaugeBody";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: vi.fn(), push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
}));

afterEach(() => {
  cleanup();
});

function makeCurrent(overrides: Partial<BrainImprovementCurrent> = {}): BrainImprovementCurrent {
  return {
    score: 0,
    acceptance_rate_pct: 0,
    promotion_progress_pct: 0,
    rules_count: 0,
    retro_delta_pct: 0,
    computed_at: "2026-04-28T10:00:00Z",
    note: "",
    ...overrides,
  };
}

function makeResponse(
  current: BrainImprovementCurrent,
  history_12w: BrainImprovementResponse["history_12w"] = [],
): BrainImprovementResponse {
  return { current, history_12w };
}

describe("BrainImprovementGaugeBody", () => {
  describe("not-configured state", () => {
    it("renders not-configured banner when brainConfigured=false", () => {
      const data = makeResponse(makeCurrent());
      render(<BrainImprovementGaugeBody data={data} brainConfigured={false} />);
      expect(screen.getByTestId("brain-improvement-not-configured")).toBeTruthy();
      expect(
        screen.getByText(/Brain is not configured for Studio/i),
      ).toBeTruthy();
    });
  });

  describe("empty / insufficient data state", () => {
    it("renders tile with score=0 and note when data is empty", () => {
      const current = makeCurrent({
        score: 0,
        note: "insufficient data: no PR outcomes measured yet",
      });
      render(<BrainImprovementGaugeBody data={makeResponse(current)} brainConfigured />);
      expect(screen.getByTestId("brain-improvement-tile")).toBeTruthy();
      expect(screen.getByTestId("brain-improvement-score").textContent).toBe("0");
      expect(screen.getByTestId("brain-improvement-note")).toBeTruthy();
      expect(screen.getByText(/insufficient data/i)).toBeTruthy();
    });

    it("renders gradient gauge arc when score=0", () => {
      const current = makeCurrent({ score: 0 });
      render(<BrainImprovementGaugeBody data={makeResponse(current)} brainConfigured />);
      const arc = screen.getByTestId("brain-improvement-gauge-arc");
      expect(arc.getAttribute("data-gauge-stroke")).toBe("gradient");
      expect(arc.getAttribute("stroke")).toMatch(/^url\(#/);
    });
  });

  describe("populated state", () => {
    it("renders gradient gauge arc when score=55", () => {
      const current = makeCurrent({ score: 55 });
      render(<BrainImprovementGaugeBody data={makeResponse(current)} brainConfigured />);
      const arc = screen.getByTestId("brain-improvement-gauge-arc");
      expect(arc.getAttribute("data-gauge-stroke")).toBe("gradient");
    });

    it("renders gradient gauge arc when score=75", () => {
      const current = makeCurrent({ score: 75 });
      render(<BrainImprovementGaugeBody data={makeResponse(current)} brainConfigured />);
      const arc = screen.getByTestId("brain-improvement-gauge-arc");
      expect(arc.getAttribute("data-gauge-stroke")).toBe("gradient");
    });

    it("displays score value correctly", () => {
      const current = makeCurrent({ score: 62 });
      render(<BrainImprovementGaugeBody data={makeResponse(current)} brainConfigured />);
      expect(screen.getByTestId("brain-improvement-score").textContent).toBe("62");
    });

    it("renders pillar table with 4 data rows", () => {
      const current = makeCurrent({
        score: 70,
        acceptance_rate_pct: 90,
        promotion_progress_pct: 40,
        rules_count: 15,
        retro_delta_pct: 1.5,
      });
      render(<BrainImprovementGaugeBody data={makeResponse(current)} brainConfigured />);
      const table = screen.getByTestId("brain-improvement-pillar-table");
      expect(table).toBeTruthy();
      // 4 pillars rendered (v1: acceptance, promotion, rules, retro)
      expect(screen.getByText("Acceptance rate")).toBeTruthy();
      expect(screen.getByText("Promotion progress")).toBeTruthy();
      expect(screen.getByText("Rules learned")).toBeTruthy();
      expect(screen.getByText("Retro POS delta")).toBeTruthy();
    });

    it("renders no note when note is empty", () => {
      const current = makeCurrent({ score: 60, note: "" });
      render(<BrainImprovementGaugeBody data={makeResponse(current)} brainConfigured />);
      expect(screen.queryByTestId("brain-improvement-note")).toBeNull();
    });

    it("renders CTA link to /admin/brain/self-improvement", () => {
      const current = makeCurrent({ score: 50 });
      render(<BrainImprovementGaugeBody data={makeResponse(current)} brainConfigured />);
      const cta = screen.getByTestId("brain-improvement-cta");
      expect(cta.getAttribute("href")).toBe("/admin/brain/self-improvement");
    });
  });

  describe("sparkline", () => {
    it("renders sparkline when history_12w has 2+ entries", () => {
      const current = makeCurrent({ score: 55 });
      const history = [
        { at: "2026-04-14T00:00:00Z", score: 40 },
        { at: "2026-04-21T00:00:00Z", score: 55 },
      ];
      render(<BrainImprovementGaugeBody data={makeResponse(current, history)} brainConfigured />);
      expect(screen.getByTestId("brain-improvement-sparkline")).toBeTruthy();
    });

    it("does not render sparkline when history_12w has fewer than 2 entries", () => {
      const current = makeCurrent({ score: 55 });
      render(
        <BrainImprovementGaugeBody
          data={makeResponse(current, [{ at: "2026-04-21T00:00:00Z", score: 55 }])}
          brainConfigured
        />,
      );
      expect(screen.queryByTestId("brain-improvement-sparkline")).toBeNull();
    });
  });
});
