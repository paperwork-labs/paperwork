import { describe, expect, it } from "vitest";

import workstreamsJson from "@/data/workstreams.json";
import {
  WorkstreamsFileSchema,
  computeKpis,
} from "@/lib/workstreams/schema";

/**
 * Bundled snapshot: apps/studio/src/data/workstreams.json (same bundle as `/admin/workstreams`).
 * `computeKpis` delegates to `computeWorkstreamsBoardKpis`: merged in-flight `(pending ∪ in_progress)` → `active`;
 * cancelled rows count solely by status (never omitted when `estimated_pr_count` is null).
 */
describe("bundled workstreams KPI parity (/admin/workstreams)", () => {
  const parsed = WorkstreamsFileSchema.parse(workstreamsJson);

  const kpiPartitionOk = (
    kpis: ReturnType<typeof computeKpis>,
    ws: (typeof parsed.workstreams)[number][],
  ) => {
    const inFlight = ws.filter(
      (w) => w.status === "pending" || w.status === "in_progress",
    ).length;
    expect(kpis.active).toBe(inFlight);
    expect(kpis.blocked).toBe(ws.filter((w) => w.status === "blocked").length);
    expect(kpis.completed).toBe(ws.filter((w) => w.status === "completed").length);
    expect(kpis.cancelled).toBe(ws.filter((w) => w.status === "cancelled").length);
    expect(kpis.total).toBe(ws.length);
    expect(
      kpis.active + kpis.blocked + kpis.completed + kpis.cancelled,
    ).toBe(kpis.total);

    const forAvg = ws.filter(
      (w) => w.status === "pending" || w.status === "in_progress",
    );
    const expectedAvg =
      forAvg.length === 0
        ? 0
        : Math.round(
            forAvg.reduce((acc, w) => acc + w.percent_done, 0) / forAvg.length,
          );
    expect(kpis.avg_percent_done).toBe(expectedAvg);
  };

  it("`computeKpis` matches explicit `filter` counts on bundled JSON (bundled snapshot)", () => {
    const ws = parsed.workstreams;
    const kpis = computeKpis(parsed);
    kpiPartitionOk(kpis, ws);

    const cancelled = ws.filter((w) => w.status === "cancelled");
    const cancelledNullEst = cancelled.filter((w) => w.estimated_pr_count === null);
    expect(cancelled.length).toBeGreaterThan(0);
    expect(cancelledNullEst.length).toBeGreaterThan(0);

    expect(
      cancelled.filter((w) => w.estimated_pr_count !== null).length +
        cancelledNullEst.length,
    ).toBe(kpis.cancelled);
    expect(kpis.cancelled).toBe(cancelled.length);
  });
});
