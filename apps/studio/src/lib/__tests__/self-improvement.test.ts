import { describe, expect, it } from "vitest";

import { BII_FORMULA } from "../brain-improvement-formula";
import { aggregateLearning, extractJobsFromSchedulerSource, resolveMonorepoRoot } from "../self-improvement";

describe("resolveMonorepoRoot", () => {
  it("finds repo root from package cwd", () => {
    const root = resolveMonorepoRoot(process.cwd());
    expect(root).toBeTruthy();
    expect(root!.includes("paperwork")).toBe(true);
  });
});

describe("BII_FORMULA", () => {
  it("matches Brain self_improvement.py weights", () => {
    expect(BII_FORMULA.W_ACCEPTANCE).toBe(0.4);
    expect(BII_FORMULA.W_PROMOTION).toBe(0.3);
    expect(BII_FORMULA.W_RULES).toBe(0.2);
    expect(BII_FORMULA.W_RETRO).toBe(0.1);
    expect(
      BII_FORMULA.W_ACCEPTANCE + BII_FORMULA.W_PROMOTION + BII_FORMULA.W_RULES + BII_FORMULA.W_RETRO,
    ).toBeCloseTo(1);
  });
});

describe("aggregateLearning", () => {
  it("returns empty aggregates when repo root invalid", () => {
    const agg = aggregateLearning("/nonexistent/path/that/has/no/brain/data");
    expect(agg.dispatchMeta.missing).toBe(true);
    expect(agg.successRate7d).toBeNull();
  });
});

describe("extractJobsFromSchedulerSource", () => {
  it("parses from_crontab + job id", () => {
    const src = `
_JOB_ID = "brain_daily_briefing"
def install(scheduler):
    scheduler.add_job(
        _tick,
        trigger=CronTrigger.from_crontab("0 7 * * *", timezone=UTC),
        id=_JOB_ID,
    )
`;
    const rows = extractJobsFromSchedulerSource(src, "brain_daily_briefing.py");
    expect(rows.length).toBe(1);
    expect(rows[0]?.jobId).toBe("brain_daily_briefing");
    expect(rows[0]?.schedule).toBe("0 7 * * *");
  });
});
