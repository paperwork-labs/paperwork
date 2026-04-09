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

export interface PipelineRunMeta {
  run_id: string;
  status: "queued" | "running" | "ok" | "error" | "partial" | "unknown";
  started_at: string | null;
  finished_at: string | null;
  triggered_by: string | null;
  updated_at?: string;
  error?: string | null;
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
