/**
 * Shared types for Admin Agent conversational UI.
 * Aligns with backend `agent_actions` where applicable.
 */

export interface AgentAction {
  id: number
  action_type: string
  action_name: string
  payload: Record<string, unknown> | null
  risk_level: string
  status: string
  reasoning: string | null
  context_summary: string | null
  task_id: string | null
  result: Record<string, unknown> | null
  error: string | null
  created_at: string
  approved_at: string | null
  executed_at: string | null
  completed_at: string | null
  auto_approved: boolean
  session_id: string | null
  confidence_score?: number | null
}

export interface ChatMessage {
  id: string
  role: "user" | "agent"
  content: string
  actions?: AgentAction[]
  timestamp: Date
}

export type HealthSignal = "ok" | "warn" | "error"

export interface HealthData {
  coverage: HealthSignal
  stage: HealthSignal
  jobs: HealthSignal
  audit: HealthSignal
  regime: HealthSignal
}

export interface AgentSession {
  id: string
  startedAt: Date
  actionCount: number
  statusSummary: string
}

export const AUTONOMY_LEVELS = ["Safe", "Full", "Ask"] as const
export type AutonomyLevel = (typeof AUTONOMY_LEVELS)[number]
