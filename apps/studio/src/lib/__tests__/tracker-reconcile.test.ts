import { describe, expect, it } from "vitest";

import type { CriticalDate, Plan, Sprint } from "@/lib/tracker";
import {
  activePlansForUi,
  activeSprintsForUi,
  companyTasksOpenCount,
  shippedPlansForUi,
  shippedSprintsForUi,
  computeEffectiveSprintStatus,
} from "@/lib/tracker-reconcile";

const basePlan = (over: Partial<Plan>): Plan => ({
  slug: "x",
  path: "docs/p.md",
  title: "T",
  status: "in_progress",
  product: "studio",
  ...over,
});

const baseSprint = (over: Partial<Sprint>): Sprint => ({
  slug: "s",
  path: "docs/sprints/x.md",
  title: "S",
  status: "in_progress",
  ...over,
});

describe("tracker-reconcile", () => {
  it("counts in_progress and legacy active as active plans", () => {
    const plans = [
      basePlan({ slug: "a", status: "in_progress" }),
      basePlan({ slug: "b", status: "active" }),
      basePlan({ slug: "c", status: "shipped" }),
    ];
    expect(activePlansForUi(plans)).toHaveLength(2);
    expect(shippedPlansForUi(plans)).toHaveLength(1);
  });

  it("treats paused plans as non-active (rolled into shipped-for-UI bucket)", () => {
    const plans = [basePlan({ status: "paused" })];
    expect(activePlansForUi(plans)).toHaveLength(0);
    expect(shippedPlansForUi(plans)).toHaveLength(1);
  });

  it("computeEffectiveSprintStatus maps stale paused sprints with outcomes toward shipped", () => {
    const sprint = baseSprint({
      status: "paused",
      effective_status: undefined,
      blocker: "",
      end: "2020-01-01",
      last_reviewed: "2020-01-02",
      outcome_bullets: ["a", "b", "c"],
      followups: ["x"],
      related_prs: [1],
    });
    expect(computeEffectiveSprintStatus(sprint, [])).toBe("shipped");
  });

  it("ship-state sprints roll into shippedSprintsForUi (including effective_status)", () => {
    const shipped = baseSprint({ slug: "sh", status: "shipped" });
    const derived = baseSprint({
      slug: "dr",
      status: "paused",
      effective_status: "shipped",
    });
    expect(shippedSprintsForUi([shipped, derived])).toHaveLength(2);
    expect(activeSprintsForUi([shipped, derived])).toHaveLength(0);
  });

  it("companyTasksOpenCount ignores done / complete statuses", () => {
    const dates: CriticalDate[] = [
      { milestone: "m", deadline: "2026-01-01", status: "DONE", notes: "" },
      { milestone: "m2", deadline: "2026-01-02", status: "complete", notes: "" },
      { milestone: "m3", deadline: "2026-01-03", status: "In progress", notes: "" },
    ];
    expect(companyTasksOpenCount(dates)).toBe(1);
  });

  it("companyTasksOpenCount is 0 for empty or missing fields", () => {
    expect(companyTasksOpenCount([])).toBe(0);
    expect(
      companyTasksOpenCount([
        { milestone: "m", deadline: "2026-01-01", status: "", notes: "" },
      ]),
    ).toBe(1);
  });

  it("sprint arrays handle divide-by-zero safe shipped KPI-style filters", () => {
    expect(activeSprintsForUi([])).toEqual([]);
    expect(shippedSprintsForUi([])).toEqual([]);
    expect(activePlansForUi([])).toEqual([]);
    expect(shippedPlansForUi([])).toEqual([]);
  });
});
