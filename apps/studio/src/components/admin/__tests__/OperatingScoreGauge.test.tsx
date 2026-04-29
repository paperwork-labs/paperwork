import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { OPERATING_SCORE_PILLAR_ORDER } from "@/lib/operating-score-pillars";
import type { OperatingScoreEntry, Pillar, OperatingScoreResponse } from "@/types/operating-score";

import { OperatingScoreGaugeBody } from "../OperatingScoreGaugeBody";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: vi.fn(), push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
}));

afterEach(() => {
  cleanup();
});

const WEIGHTS: Record<string, number> = {
  autonomy: 13,
  dora_elite: 13,
  stack_modernity: 13,
  web_perf_ux: 13,
  a11y_design_system: 9,
  code_quality: 9,
  data_architecture: 9,
  reliability_security: 9,
  knowledge_capital: 6,
  persona_coverage: 6,
};

function entryWithTotal(
  total: number,
  pillarScores?: Partial<Record<string, number>>,
  gates?: { l4_pass: boolean; l5_pass: boolean; lowest_pillar?: string },
): OperatingScoreEntry {
  const pillars: Record<string, Pillar> = {};
  for (const id of OPERATING_SCORE_PILLAR_ORDER) {
    const w = WEIGHTS[id] ?? 10;
    const s = pillarScores?.[id] ?? 75;
    pillars[id] = {
      score: s,
      weight: w,
      weighted: (s * w) / 100,
      measured: false,
      notes: "",
    };
  }
  return {
    computed_at: "2026-04-28T10:00:00Z",
    total,
    pillars,
    gates: {
      l4_pass: gates?.l4_pass ?? false,
      l5_pass: gates?.l5_pass ?? false,
      lowest_pillar: gates?.lowest_pillar ?? "",
    },
  };
}

describe("OperatingScoreGaugeBody", () => {
  it("renders empty state when current is null", () => {
    const data: OperatingScoreResponse = {
      current: null,
      history_last_12: [],
      gates: { l4_pass: false, l5_pass: false, lowest_pillar: "" },
    };
    render(<OperatingScoreGaugeBody data={data} brainConfigured />);
    expect(screen.getByTestId("operating-score-empty")).toBeTruthy();
    expect(
      screen.getByText(/Brain has not yet computed an Operating Score/i),
    ).toBeTruthy();
  });

  it("renders gauge arc amber when score=85", () => {
    const current = entryWithTotal(85);
    const data: OperatingScoreResponse = {
      current,
      history_last_12: [],
      gates: current.gates,
    };
    render(<OperatingScoreGaugeBody data={data} brainConfigured />);
    const arc = screen.getByTestId("operating-score-gauge-arc");
    expect(arc.getAttribute("data-gauge-stroke")).toBe("#fbbf24");
    expect(screen.getByTestId("operating-score-total").textContent).toBe("85.0");
  });

  it("renders gauge arc green when score=92", () => {
    const current = entryWithTotal(92);
    const data: OperatingScoreResponse = {
      current,
      history_last_12: [],
      gates: current.gates,
    };
    render(<OperatingScoreGaugeBody data={data} brainConfigured />);
    expect(screen.getByTestId("operating-score-gauge-arc").getAttribute("data-gauge-stroke")).toBe(
      "#4ade80",
    );
  });

  it("renders L4/L5 pass/fail from gates", () => {
    const current = entryWithTotal(88, undefined, {
      l4_pass: true,
      l5_pass: false,
      lowest_pillar: "autonomy",
    });
    const data: OperatingScoreResponse = {
      current,
      history_last_12: [],
      gates: current.gates,
    };
    render(<OperatingScoreGaugeBody data={data} brainConfigured />);
    const gateRow = screen.getByTestId("operating-score-gates");
    expect(gateRow.textContent).toMatch(/L4:\s*PASS/);
    expect(gateRow.textContent).toMatch(/L5:\s*FAIL/);
  });

  it("pillar table shows 10 rows", () => {
    const current = entryWithTotal(80);
    const data: OperatingScoreResponse = {
      current,
      history_last_12: [],
      gates: current.gates,
    };
    render(<OperatingScoreGaugeBody data={data} brainConfigured />);
    const tbl = screen.getByTestId("operating-score-pillar-table");
    const rows = within(tbl).getAllByRole("row");
    expect(rows.length).toBe(11);
  });

  it("trend arrows from history (last two entries)", () => {
    const older = entryWithTotal(70, { autonomy: 60 });
    const newer = entryWithTotal(72, { autonomy: 72 });
    const current = newer;
    const data: OperatingScoreResponse = {
      current,
      history_last_12: [older, newer],
      gates: current.gates,
    };
    render(<OperatingScoreGaugeBody data={data} brainConfigured />);
    const tbl = screen.getByTestId("operating-score-pillar-table");
    const autonomyRow = within(tbl)
      .getAllByRole("row")
      .find((r) => r.textContent?.includes("Autonomy"));
    expect(autonomyRow).toBeTruthy();
    expect(autonomyRow!.textContent).toContain("↑");
  });
});
