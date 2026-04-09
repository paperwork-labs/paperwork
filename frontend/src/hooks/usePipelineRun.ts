import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { pipelineApi } from '../services/api';
import type {
  ActiveTasksResponse,
  PipelineDAGDefinition,
  PipelineRunMeta,
  PipelineRunState,
  PipelineRunsResponse,
  PipelineTriggerResponse,
  StopAllResponse,
} from '../types/pipeline';

const LIVE_POLL_MS = 3_000;
const IDLE_POLL_MS = 60_000;
const RUNS_TURBO_POLL_MS = 3_000;
const RUNS_IDLE_POLL_MS = 30_000;

export const PIPELINE_RUNS_QUERY_KEY = 'pipeline-runs';

export const pipelineRunsQueryKey = (limit: number, turboUntilMs: number) =>
  [PIPELINE_RUNS_QUERY_KEY, limit, turboUntilMs] as const;

export function usePipelineDAG() {
  return useQuery<PipelineDAGDefinition>({
    queryKey: ['pipeline-dag'],
    queryFn: async () => {
      const body = await pipelineApi.getDAG();
      if (!body || !Array.isArray((body as PipelineDAGDefinition).nodes)) {
        throw new Error('Invalid pipeline DAG response');
      }
      return body as PipelineDAGDefinition;
    },
    staleTime: Infinity,
  });
}

export function usePipelineRuns(limit = 20, turboUntilMs: number | null = null) {
  const turboKey = turboUntilMs ?? 0;
  return useQuery<PipelineRunMeta[]>({
    queryKey: pipelineRunsQueryKey(limit, turboKey),
    queryFn: async () => {
      const body = await pipelineApi.getRuns(limit);
      return (body as PipelineRunsResponse)?.runs ?? [];
    },
    refetchInterval: (query) => {
      const until = query.queryKey[2] as number;
      if (until > 0 && Date.now() < until) return RUNS_TURBO_POLL_MS;
      return RUNS_IDLE_POLL_MS;
    },
  });
}

function isRunLive(data: PipelineRunState | null | undefined): boolean {
  if (!data) return false;
  const meta = data.status;
  if (meta === 'running' || meta === 'queued') return true;
  return Object.values(data.steps).some((s) => s.status === 'running');
}

export function usePipelineRun(runId: string | null) {
  return useQuery<PipelineRunState | null>({
    queryKey: runId ? ['pipeline-run', runId] : ['pipeline-run-none'],
    queryFn: async () => {
      if (!runId) return null;
      const body = await pipelineApi.getRun(runId);
      return body as PipelineRunState;
    },
    enabled: !!runId,
    refetchInterval: (query) => {
      const id = query.queryKey[1];
      if (!query.state.data) {
        if (typeof id === 'string' && id.length > 0) return LIVE_POLL_MS;
        return false;
      }
      return isRunLive(query.state.data) ? LIVE_POLL_MS : IDLE_POLL_MS;
    },
  });
}

export function useRetryStep() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ runId, step }: { runId: string; step: string }) =>
      pipelineApi.retryStep(runId, step),
    onSuccess: (_data, variables) => {
      void qc.invalidateQueries({ queryKey: [PIPELINE_RUNS_QUERY_KEY] });
      void qc.invalidateQueries({ queryKey: ['pipeline-run', variables.runId] });
    },
  });
}

export function useTriggerPipeline() {
  const qc = useQueryClient();
  return useMutation<PipelineTriggerResponse, unknown, void>({
    mutationFn: () => pipelineApi.trigger(),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: [PIPELINE_RUNS_QUERY_KEY] });
    },
  });
}

const AMBIENT_POLL_MS = 60_000;

export function usePipelineAmbient() {
  return useQuery<PipelineRunState>({
    queryKey: ['pipeline-ambient'],
    queryFn: async () => {
      const body = await pipelineApi.getAmbient();
      return body as PipelineRunState;
    },
    staleTime: 30_000,
    refetchInterval: AMBIENT_POLL_MS,
  });
}

export function useActiveTasks(enabled = true) {
  return useQuery<ActiveTasksResponse>({
    queryKey: ['pipeline-active-tasks'],
    queryFn: async () => {
      const body = await pipelineApi.getActiveTasks();
      return body as ActiveTasksResponse;
    },
    enabled,
    refetchInterval: 10_000,
  });
}

export function useStopAllTasks() {
  const qc = useQueryClient();
  return useMutation<StopAllResponse, unknown, void>({
    mutationFn: () => pipelineApi.stopAll(),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['pipeline-active-tasks'] });
      void qc.invalidateQueries({ queryKey: [PIPELINE_RUNS_QUERY_KEY] });
    },
  });
}
