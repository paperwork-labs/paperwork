export type ByAuthor = {
  founder: number;
  "brain-self-dispatch": number;
  "cheap-agent": number;
};

export type SprintVelocityEntry = {
  week_start: string;
  week_end: string;
  prs_merged: number;
  by_author: ByAuthor;
  workstreams_completed: number;
  workstreams_completed_estimated_pr_count: number;
  story_points_burned: number;
  throughput_per_day: number;
  measured: boolean;
  notes: string;
  computed_at: string;
};

export type SprintVelocityResponse = {
  current: SprintVelocityEntry | null;
  history_last_12: SprintVelocityEntry[];
};
