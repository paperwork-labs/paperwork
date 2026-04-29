/** TypeScript mirror of `apis/brain/app/schemas/brain_improvement.py` (WS-69 PR D). */

export type BrainImprovementCurrent = {
  score: number;
  acceptance_rate_pct: number;
  promotion_progress_pct: number;
  rules_count: number;
  retro_delta_pct: number;
  computed_at: string;
  note: string;
};

export type BrainImprovementHistoryEntry = {
  at: string;
  score: number;
};

export type BrainImprovementResponse = {
  current: BrainImprovementCurrent;
  history_12w: BrainImprovementHistoryEntry[];
};
