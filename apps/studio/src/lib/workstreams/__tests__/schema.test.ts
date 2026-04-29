import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import workstreamsJson from "../../../data/workstreams.json";

import {
  WorkstreamsBoardBrainEnvelopeSchema,
  WorkstreamsFileSchema,
  computeKpis,
  dispatchableWorkstreams,
} from "../schema";

describe("workstreams schema", () => {
  it("seed file (apps/studio/src/data/workstreams.json) parses", () => {
    const parsed = WorkstreamsFileSchema.safeParse(workstreamsJson);
    if (!parsed.success) {
      throw new Error(
        `workstreams.json failed schema parse:\n${JSON.stringify(parsed.error.issues, null, 2)}`,
      );
    }
    expect(parsed.success).toBe(true);
  });

  it("rejects duplicate ids", () => {
    const dupe = {
      version: 1 as const,
      updated: "2026-04-27T00:00:00Z",
      workstreams: [
        {
          id: "WS-01-foo",
          title: "Foo",
          track: "I",
          priority: 0,
          status: "pending" as const,
          percent_done: 0,
          owner: "brain" as const,
          brief_tag: "track:foo",
          blockers: [],
          last_pr: null,
          last_activity: "2026-04-27T00:00:00Z",
          last_dispatched_at: null,
          notes: "",
          estimated_pr_count: null,
          github_actions_workflow: null,
          related_plan: null,
        },
        {
          id: "WS-01-foo",
          title: "Foo dupe",
          track: "I",
          priority: 1,
          status: "pending" as const,
          percent_done: 0,
          owner: "brain" as const,
          brief_tag: "track:foo-dupe",
          blockers: [],
          last_pr: null,
          last_activity: "2026-04-27T00:00:00Z",
          last_dispatched_at: null,
          notes: "",
          estimated_pr_count: null,
          github_actions_workflow: null,
          related_plan: null,
        },
      ],
    };
    expect(WorkstreamsFileSchema.safeParse(dupe).success).toBe(false);
  });

  it("rejects completed status with percent_done != 100", () => {
    const inconsistent = {
      version: 1 as const,
      updated: "2026-04-27T00:00:00Z",
      workstreams: [
        {
          id: "WS-09-broken",
          title: "Broken",
          track: "X",
          priority: 0,
          status: "completed" as const,
          percent_done: 80,
          owner: "brain" as const,
          brief_tag: "track:broken",
          blockers: [],
          last_pr: null,
          last_activity: "2026-04-27T00:00:00Z",
          last_dispatched_at: null,
          notes: "",
          estimated_pr_count: null,
          github_actions_workflow: null,
          related_plan: null,
        },
      ],
    };
    expect(WorkstreamsFileSchema.safeParse(inconsistent).success).toBe(false);
  });

  it("dispatchableWorkstreams respects owner=brain + cooldown + blockers", () => {
    const parsed = WorkstreamsFileSchema.parse(workstreamsJson);
    const top = dispatchableWorkstreams(parsed, 5);
    for (const ws of top) {
      expect(ws.owner).toBe("brain");
      expect(["pending", "in_progress"]).toContain(ws.status);
      expect(ws.blockers).toHaveLength(0);
    }
    const priorities = top.map((w) => w.priority);
    const sorted = [...priorities].sort((a, b) => a - b);
    expect(priorities).toEqual(sorted);
  });

  it("computeKpis matches manual count", () => {
    const parsed = WorkstreamsFileSchema.parse(workstreamsJson);
    const kpis = computeKpis(parsed);
    expect(kpis.total).toBe(parsed.workstreams.length);
    expect(kpis.active + kpis.blocked + kpis.completed + kpis.cancelled).toBe(
      kpis.total,
    );
    const inFlightManual = parsed.workstreams.filter(
      (w) => w.status === "pending" || w.status === "in_progress",
    ).length;
    expect(kpis.active).toBe(inFlightManual);
    expect(kpis.avg_percent_done).toBeGreaterThanOrEqual(0);
    expect(kpis.avg_percent_done).toBeLessThanOrEqual(100);
  });

  it("parses Brain workstreams-board envelope", () => {
    const parsed = WorkstreamsBoardBrainEnvelopeSchema.safeParse({
      ...workstreamsJson,
      generated_at: "2026-04-28T12:00:00Z",
      source: "brain-writeback",
      ttl_seconds: 60,
      writeback_last_run_at: null,
    });
    expect(parsed.success).toBe(true);
  });

  it("docs/infra/WORKSTREAMS_BOARD.md exists alongside the schema", () => {
    const repoRoot = join(__dirname, "..", "..", "..", "..", "..", "..");
    const docPath = join(repoRoot, "docs/infra/WORKSTREAMS_BOARD.md");
    const content = readFileSync(docPath, "utf-8");
    expect(content.length).toBeGreaterThan(500);
    expect(content).toMatch(/dispatch/i);
  });
});
