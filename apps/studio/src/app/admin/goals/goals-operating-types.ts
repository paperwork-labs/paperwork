import type { OperatingScoreResponse } from "@/lib/brain-client";

export type GoalsOperatingScorePayload =
  | { kind: "live"; data: OperatingScoreResponse }
  | { kind: "error"; message: string }
  | { kind: "unconfigured" };

/** Stub used when Brain env is not set — labeled as illustrative, not live. */
export const GOALS_DEMO_OPERATING_SCORE: OperatingScoreResponse = {
  overall_score: 72,
  max_score: 100,
  computed_at: "2026-04-28T15:00:00Z",
  pillars: [
    {
      pillar_id: "reliability",
      label: "Reliability",
      score: 8,
      max_score: 10,
      findings: ["CUJs green on last run"],
    },
    {
      pillar_id: "velocity",
      label: "Velocity",
      score: 7,
      max_score: 10,
      findings: ["PR cycle within target"],
    },
    {
      pillar_id: "clarity",
      label: "Clarity",
      score: 6,
      max_score: 10,
      findings: ["Docs hub synced"],
    },
  ],
};
