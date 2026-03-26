import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import type { AxiosResponse } from "axios"

import api from "@/services/api"

import type { AgentAction, AgentSession, AutonomyLevel } from "@/components/agent/types"

// --- API response shapes (admin agent routes) ---

export interface AgentSettingsResponse {
  autonomy_level: string
  available_levels: string[]
}

export interface AgentSessionApiRow {
  session_id: string
  started_at: string
  last_action_at: string
  action_count: number
  statuses: string[]
}

export interface AgentRunResult {
  mode: string
  session_id: string | null
  analysis: string | null
  actions_taken: Record<string, unknown>[]
  actions_pending: Record<string, unknown>[]
  health_input: string | null
}

export interface AgentStats {
  total_actions: number
  pending_approval: number
  completed: number
  failed: number
  auto_approved_rate: number
  by_risk_level: Record<string, number>
  top_actions: Record<string, number>
}

export interface UseAgentActionsOptions {
  limit?: number
  sessionId?: string | null
}

function mapSessionRow(row: AgentSessionApiRow): AgentSession {
  const summary =
    row.statuses && row.statuses.length > 0
      ? row.statuses.slice(0, 4).join(", ") +
        (row.statuses.length > 4 ? "…" : "")
      : "—"
  return {
    id: row.session_id,
    startedAt: new Date(row.started_at),
    actionCount: row.action_count,
    statusSummary: summary,
  }
}

export function useAgentActions(options?: UseAgentActionsOptions) {
  const limit = options?.limit ?? 100
  const sessionId = options?.sessionId ?? null

  return useQuery<AgentAction[]>({
    queryKey: ["agent", "actions", { limit, sessionId }],
    queryFn: async () => {
      const res = await api.get<AgentAction[]>("/admin/agent/actions", {
        params: {
          limit,
          ...(sessionId ? { session_id: sessionId } : {}),
        },
      })
      return res.data ?? []
    },
  })
}

export function useAgentPendingActions() {
  return useQuery<AgentAction[]>({
    queryKey: ["agent", "actions", "pending"],
    queryFn: async () => {
      const res = await api.get<AgentAction[]>("/admin/agent/actions/pending")
      return res.data ?? []
    },
  })
}

export function useAgentSessions() {
  return useQuery<AgentSession[]>({
    queryKey: ["agent", "sessions"],
    queryFn: async () => {
      const res = await api.get<AgentSessionApiRow[]>("/admin/agent/sessions", {
        params: { limit: 30 },
      })
      return (res.data ?? []).map(mapSessionRow)
    },
  })
}

export function useAgentSettings() {
  return useQuery<AgentSettingsResponse>({
    queryKey: ["agent", "settings"],
    queryFn: async () => {
      const res = await api.get<AgentSettingsResponse>("/admin/agent/settings")
      return res.data
    },
  })
}

export function useAgentStats() {
  return useQuery<AgentStats>({
    queryKey: ["agent", "stats"],
    queryFn: async () => {
      const res = await api.get<AgentStats>("/admin/agent/stats")
      return res.data
    },
  })
}

export function usePatchAgentSettings() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (autonomy_level: string) =>
      api.patch<AgentSettingsResponse>("/admin/agent/settings", {
        autonomy_level,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["agent", "settings"] })
    },
  })
}

export function useAgentRun() {
  const queryClient = useQueryClient()
  return useMutation<AgentRunResult, unknown, string | undefined>({
    mutationFn: async (context?: string) => {
      const res: AxiosResponse<AgentRunResult> = await api.post(
        "/admin/agent/run",
        null,
        { params: context ? { context } : {} }
      )
      return res.data
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["agent"] })
    },
  })
}

export function useApproveAgentAction() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      id,
      approved,
      reason,
    }: {
      id: number
      approved: boolean
      reason?: string
    }) =>
      api.post<AgentAction>(`/admin/agent/actions/${id}/approve`, {
        approved,
        reason,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["agent"] })
    },
  })
}

/** Map backend autonomy_level to AgentHealthPanel tab labels. */
export function autonomyApiToLabel(level: string): AutonomyLevel {
  const m: Record<string, AutonomyLevel> = {
    safe: "Safe",
    full: "Full",
    ask: "Ask",
  }
  return m[level.toLowerCase()] ?? "Safe"
}

export function autonomyLabelToApi(label: string): string {
  return label.toLowerCase()
}
