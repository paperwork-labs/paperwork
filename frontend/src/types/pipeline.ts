/** Typed contract for the Pipeline DAG REST API. */

export type PipelineStepStatus = "pending" | "running" | "ok" | "error" | "skipped";

export interface PipelineStepState {
  status: PipelineStepStatus;
  started_at: string | null;
  finished_at: string | null;
  duration_s: number | null;
  error: string | null;
  counters: Record<string, unknown> | null;
}

/**
 * ``waiting`` is computed-on-read by the backend when a run has been queued
 * for >30s and at least one Celery worker is reachable AND busy with another
 * task.  When ``waiting`` is set, ``current_task`` describes the longest-
 * running task on any worker (the most likely thing blocking the run) and
 * ``waiting_for_s`` is the run's age in seconds.  See backend
 * ``_classify_stale_queued`` for the full truth table.
 */
export interface CurrentTaskInfo {
  id: string | null;
  name: string | null;
  worker: string | null;
  running_for_s: number | null;
}

export interface PipelineRunMeta {
  run_id: string;
  status:
    | "queued"
    | "running"
    | "waiting"
    | "ok"
    | "error"
    | "partial"
    | "unknown";
  started_at: string | null;
  finished_at: string | null;
  triggered_by: string | null;
  updated_at?: string;
  error?: string | null;
  /** Only set when ``status === "waiting"``. */
  waiting_for_s?: number;
  /** Only set when ``status === "waiting"``. */
  current_task?: CurrentTaskInfo | null;
}

export interface PipelineRunState extends PipelineRunMeta {
  steps: Record<string, PipelineStepState>;
}

export interface PipelineDAGNode {
  name: string;
  display_name: string;
  deps: string[];
  timeout_s: number;
}

export interface PipelineDAGEdge {
  source: string;
  target: string;
}

export interface PipelineDAGDefinition {
  nodes: PipelineDAGNode[];
  edges: PipelineDAGEdge[];
}

export interface PipelineRunsResponse {
  runs: PipelineRunMeta[];
}

export interface PipelineTriggerResponse {
  run_id: string;
  status: string;
  message: string;
}

export interface PipelineRetryResponse {
  run_id: string;
  step: string;
  status: string;
  message: string;
}

export interface ActiveTaskInfo {
  id: string;
  name: string | null;
  worker: string | null;
  started: number | null;
  dag_step: string | null;
}

export interface ActiveTasksResponse {
  tasks: ActiveTaskInfo[];
  total: number;
  inspect_ok?: boolean;
}

export interface StopAllResponse {
  revoked: number;
  purged: number;
  message: string;
}
