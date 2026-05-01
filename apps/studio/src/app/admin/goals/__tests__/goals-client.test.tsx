import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { GoalsJson, KeyResult } from "@/lib/goals-metrics";

import { GoalsClient } from "../goals-client";

const createGoalAction = vi.fn();
const updateGoalAction = vi.fn();
const archiveGoalAction = vi.fn();
const updateKRProgressAction = vi.fn();

vi.mock("../actions", () => ({
  createGoalAction: (...a: unknown[]) => createGoalAction(...a),
  updateGoalAction: (...a: unknown[]) => updateGoalAction(...a),
  archiveGoalAction: (...a: unknown[]) => archiveGoalAction(...a),
  updateKRProgressAction: (...a: unknown[]) => updateKRProgressAction(...a),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: vi.fn() }),
}));

function fixtureData(): GoalsJson {
  return {
    quarter: "2026-Q2",
    objectives: [
      {
        id: "obj-stall",
        title: "Stalled objective",
        owner: "test",
        key_results: [
          {
            id: "kr-s1",
            title: "KR slow",
            target: 100,
            current: 10,
            unit: "x",
            source_url: null,
          },
        ],
      },
      {
        id: "obj-ok",
        title: "Healthy objective",
        owner: "test",
        key_results: [
          {
            id: "kr-o1",
            title: "KR ok",
            target: 100,
            current: 80,
            unit: "x",
            source_url: null,
          },
        ],
      },
      {
        id: "obj-pct-api",
        title: "Uses API progress_pct",
        owner: "brain",
        key_results: [
          {
            id: "kr-p1",
            title: "Low pct from API",
            target: 100,
            current: 90,
            unit: "x",
            source_url: null,
            progress_pct: 10,
          } as KeyResult & { progress_pct: number },
        ],
      },
    ],
  };
}

describe("GoalsClient", () => {
  it("stalled alert lists objectives with any KR under 25% (current/target or progress_pct)", () => {
    const data = fixtureData();
    render(<GoalsClient data={data} />);

    const alert = screen.getByTestId("goals-stalled-alert");
    expect(alert.textContent).toMatch(/2 objectives with key results under 25% progress/i);
    expect(alert.textContent).toMatch(/Stalled objective/i);
    expect(alert.textContent).toMatch(/Uses API progress_pct/i);
    expect(alert.textContent).not.toMatch(/Healthy objective/i);
  });

  it("clicking KR progress shows input for inline edit", async () => {
    const user = userEvent.setup();
    updateKRProgressAction.mockResolvedValue({ ok: true });
    const data = fixtureData();
    render(<GoalsClient data={data} />);

    await user.click(screen.getAllByTestId("kr-progress-trigger-kr-s1")[0]!);

    expect(screen.getAllByTestId("kr-progress-input-kr-s1")[0]).toBeTruthy();
  });

  it("submitting create dialog calls createGoalAction", async () => {
    const user = userEvent.setup();
    createGoalAction.mockResolvedValue({ ok: true });
    const data = fixtureData();
    render(<GoalsClient data={data} />);

    await user.click(screen.getAllByTestId("goals-add-button")[0]!);

    const dialog = screen.getByRole("dialog", { name: /add objective/i });
    await user.type(within(dialog).getByLabelText(/^objective$/i), "Ship feature");
    await user.type(within(dialog).getByLabelText(/^owner$/i), "founder");

    const krTitles = within(dialog).getAllByPlaceholderText(/^title$/i);
    await user.type(krTitles[0]!, "Endpoints");
    const krTargets = within(dialog).getAllByPlaceholderText(/^target$/i);
    await user.type(krTargets[0]!, "10");
    const krUnits = within(dialog).getAllByPlaceholderText(/^unit$/i);
    await user.type(krUnits[0]!, "ep");

    await user.click(within(dialog).getByRole("button", { name: /^create$/i }));

    expect(createGoalAction).toHaveBeenCalledTimes(1);
    expect(createGoalAction).toHaveBeenCalledWith(
      expect.objectContaining({
        objective: "Ship feature",
        owner: "founder",
        quarter: "2026-Q2",
        key_results: expect.arrayContaining([
          expect.objectContaining({
            title: "Endpoints",
            target: 10,
            unit: "ep",
            current: 0,
          }),
        ]),
      }),
    );
  });

  it("archive asks for confirm before calling archiveGoalAction", async () => {
    const user = userEvent.setup();
    const confirmMock = vi.fn(() => false);
    const prevConfirm = window.confirm;
    window.confirm = confirmMock as typeof window.confirm;
    archiveGoalAction.mockResolvedValue({ ok: true });

    const data: GoalsJson = {
      quarter: "2026-Q2",
      objectives: [
        {
          id: "obj-one",
          title: "Single",
          owner: "x",
          key_results: [
            {
              id: "kr-1",
              title: "KR",
              target: 1,
              current: 1,
              unit: "u",
              source_url: null,
            },
          ],
        },
      ],
    };
    render(<GoalsClient data={data} />);

    await user.click(screen.getAllByTestId("goal-menu-obj-one")[0]!);
    await user.click(screen.getAllByTestId("goal-archive-obj-one")[0]!);

    expect(confirmMock).toHaveBeenCalled();
    expect(archiveGoalAction).not.toHaveBeenCalled();

    confirmMock.mockReturnValue(true);
    await user.click(screen.getAllByTestId("goal-menu-obj-one")[0]!);
    await user.click(screen.getAllByTestId("goal-archive-obj-one")[0]!);

    expect(archiveGoalAction).toHaveBeenCalledWith("obj-one");
    window.confirm = prevConfirm;
  });
});
