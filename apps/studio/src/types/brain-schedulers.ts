/**
 * Brain APScheduler introspection proxied via Studio (see apis/brain `GET /internal/schedulers`).
 * Optional fields are forward-compatible with T1.7-followup (SchedulerRun / last-run export).
 */

export type BrainSchedulerClassification = string;

/** One row from Brain `/internal/schedulers` (plus optional follow-up fields). */
export type BrainSchedulerJob = {
  id: string;
  next_run: string | null;
  trigger: string;
  enabled: boolean;
  classification: BrainSchedulerClassification;
  /** Present when Brain exports execution history (T1.7-followup — not yet on `/internal/schedulers`). */
  last_completed_at?: string | null;
  /** Present when Brain exports run totals (T1.7-followup). */
  run_count?: number | null;
};

export type BrainSchedulersSuccessPayload = {
  ok: true;
  jobs: BrainSchedulerJob[];
  /** True when payloads include trustworthy last_completed_at for drift thresholds. */
  lastRunExported: boolean;
  sourcePath: "/internal/schedulers";
};

export type BrainSchedulersEmptyPayload = {
  ok: false;
  empty: true;
  code: "unconfigured" | "no_jobs";
  message: string;
};

export type BrainSchedulersErrorPayload = {
  ok: false;
  empty: false;
  code: "upstream" | "invalid_shape";
  message: string;
  httpStatus?: number;
};

export type BrainSchedulersBffPayload =
  | BrainSchedulersSuccessPayload
  | BrainSchedulersEmptyPayload
  | BrainSchedulersErrorPayload;
