import * as React from "react"
import axios from "axios"
import { useQueryClient } from "@tanstack/react-query"
import { RefreshCw } from "lucide-react"

import api from "@/services/api"

import {
  AgentChatPanel,
  AgentHealthPanel,
  AgentSessionList,
  type AgentAction,
  type ChatMessage,
  type HealthData,
  type HealthSignal,
} from "@/components/agent"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import StatCard from "@/components/admin/StatCard"
import {
  autonomyApiToLabel,
  autonomyLabelToApi,
  useAgentChat,
  useAgentSessions,
  useAgentSettings,
  useAgentStats,
  useApproveAgentAction,
  usePatchAgentSettings,
} from "@/hooks/useAgent"
import useAdminHealth from "@/hooks/useAdminHealth"
import type { AdminHealthResponse } from "@/types/adminHealth"

function newMessageId(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID()
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`
}

function getAxiosErrorMessage(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const data = err.response?.data as { detail?: unknown } | undefined
    if (data?.detail != null) {
      const d = data.detail
      return typeof d === "string" ? d : JSON.stringify(d)
    }
    return err.message
  }
  if (err instanceof Error) return err.message
  return "Something went wrong."
}

function dimensionToSignal(status: "green" | "red"): HealthSignal {
  return status === "green" ? "ok" : "error"
}

function adminHealthToAgentHealth(
  health: AdminHealthResponse | null
): HealthData | undefined {
  if (!health?.dimensions) return undefined
  const d = health.dimensions
  return {
    coverage: dimensionToSignal(d.coverage.status),
    stage: dimensionToSignal(d.stage_quality.status),
    jobs: dimensionToSignal(d.jobs.status),
    audit: dimensionToSignal(d.audit.status),
    regime: dimensionToSignal(d.regime.status),
  }
}

/** Run response action payloads are a subset of persisted AgentAction rows. */
function normalizeRunAction(raw: Record<string, unknown>): AgentAction {
  const id = Number(raw.id)
  const created =
    typeof raw.created_at === "string" && raw.created_at
      ? raw.created_at
      : new Date().toISOString()
  return {
    id: Number.isFinite(id) ? id : 0,
    action_type: String(raw.action_type ?? ""),
    action_name: String(raw.action_name ?? raw.action_type ?? "Action"),
    payload: null,
    risk_level: String(raw.risk_level ?? "moderate"),
    status: String(raw.status ?? "pending_approval"),
    reasoning: typeof raw.reasoning === "string" ? raw.reasoning : null,
    context_summary: null,
    task_id: typeof raw.task_id === "string" ? raw.task_id : null,
    result: null,
    error: null,
    created_at: created,
    approved_at: null,
    executed_at: null,
    completed_at: null,
    auto_approved: Boolean(raw.auto_approved),
    session_id: typeof raw.session_id === "string" ? raw.session_id : null,
    confidence_score:
      typeof raw.confidence_score === "number" ? raw.confidence_score : null,
  }
}

const AdminAgent: React.FC = () => {
  const queryClient = useQueryClient()
  const { health } = useAdminHealth()
  const settingsQuery = useAgentSettings()
  const sessionsQuery = useAgentSessions()
  const statsQuery = useAgentStats()
  const chatMutation = useAgentChat()
  const approveMutation = useApproveAgentAction()
  const patchSettings = usePatchAgentSettings()

  const [messages, setMessages] = React.useState<ChatMessage[]>([])
  const [currentSessionId, setCurrentSessionId] = React.useState<string | null>(null)
  const [selectedSessionId, setSelectedSessionId] = React.useState<
    string | undefined
  >()
  const [approvingActionId, setApprovingActionId] = React.useState<
    number | null
  >(null)
  const [settingsError, setSettingsError] = React.useState<string | null>(null)
  const [approveError, setApproveError] = React.useState<string | null>(null)

  const healthData = React.useMemo(
    () => adminHealthToAgentHealth(health),
    [health]
  )

  const autonomyLabel = autonomyApiToLabel(
    settingsQuery.data?.autonomy_level ?? "safe"
  )

  const showSidebarSkeleton =
    (settingsQuery.isPending && !settingsQuery.data) ||
    (sessionsQuery.isPending && !sessionsQuery.data)

  const [refreshing, setRefreshing] = React.useState(false)

  const handleRefresh = React.useCallback(async () => {
    setRefreshing(true)
    try {
      await queryClient.refetchQueries({ queryKey: ["agent"] })
      await queryClient.refetchQueries({ queryKey: ["admin-health"] })
    } finally {
      setRefreshing(false)
    }
  }, [queryClient])

  const handleAutonomyChange = React.useCallback(
    (label: string) => {
      const apiLevel = autonomyLabelToApi(label)
      if (settingsQuery.data?.autonomy_level === apiLevel) return
      setSettingsError(null)
      patchSettings.mutate(apiLevel, {
        onError: (err) => {
          setSettingsError(getAxiosErrorMessage(err))
        },
      })
    },
    [patchSettings, settingsQuery.data?.autonomy_level]
  )

  const handleSendMessage = React.useCallback(
    async (message: string) => {
      const userMsg: ChatMessage = {
        id: newMessageId(),
        role: "user",
        content: message,
        timestamp: new Date(),
      }
      setMessages((prev) => [...prev, userMsg])

      try {
        const data = await chatMutation.mutateAsync({
          message,
          session_id: currentSessionId,
        })
        
        // Track session for conversation continuity
        if (data.session_id) {
          setCurrentSessionId(data.session_id)
        }
        
        const actions = (data.actions ?? []).map((a) =>
          normalizeRunAction(a as Record<string, unknown>)
        )
        
        const responseText =
          (data.response && data.response.trim()) || "No response."

        const agentMsg: ChatMessage = {
          id: newMessageId(),
          role: "agent",
          content: responseText,
          actions: actions.length > 0 ? actions : undefined,
          timestamp: new Date(),
        }
        setMessages((prev) => [...prev, agentMsg])
      } catch (err) {
        if (axios.isAxiosError(err) && err.response?.status === 404) {
          setCurrentSessionId(null)
        }
        const agentErr: ChatMessage = {
          id: newMessageId(),
          role: "agent",
          content: `Chat failed.\n\n${getAxiosErrorMessage(err)}`,
          timestamp: new Date(),
        }
        setMessages((prev) => [...prev, agentErr])
      }
    },
    [chatMutation, currentSessionId]
  )
  
  const handleNewChat = React.useCallback(() => {
    setMessages([])
    setCurrentSessionId(null)
    setSelectedSessionId(undefined)
  }, [])

  const handleSelectSession = React.useCallback(
    async (sessionId: string) => {
      const previousSessionId = currentSessionId
      setSelectedSessionId(sessionId)
      setCurrentSessionId(sessionId)
      try {
        const res = await api.get<{
          session_id: string
          messages: Array<{ role: string; content: string }>
          found: boolean
        }>(`/admin/agent/sessions/${sessionId}/messages`)

        if (res.data.found && res.data.messages.length > 0) {
          // Filter to only user/assistant roles, normalize assistant->agent
          const loadedMessages: ChatMessage[] = res.data.messages
            .filter((m) => m.role === "user" || m.role === "assistant")
            .map((m: { role: string; content: string }, i: number) => ({
              id: `${sessionId}-${i}`,
              role: m.role === "assistant" ? "agent" : "user",
              content: m.content,
              timestamp: new Date(),
            }))
          setMessages(loadedMessages)
        } else {
          setMessages([])
        }
      } catch (err) {
        // Revert session on error
        setCurrentSessionId(previousSessionId)
        setSelectedSessionId(previousSessionId ?? undefined)
        const errMsg: ChatMessage = {
          id: newMessageId(),
          role: "agent",
          content: `Could not load session: ${getAxiosErrorMessage(err)}`,
          timestamp: new Date(),
        }
        setMessages((prev) => [...prev, errMsg])
      }
    },
    [currentSessionId]
  )

  const handleApproveAction = React.useCallback(
    async (actionId: number, approved: boolean) => {
      setApproveError(null)
      setApprovingActionId(actionId)
      try {
        const res = await approveMutation.mutateAsync({
          id: actionId,
          approved,
        })
        const updated = res.data
        setMessages((prev) =>
          prev.map((m) => {
            if (!m.actions?.some((a) => a.id === actionId)) return m
            return {
              ...m,
              actions: m.actions.map((a) =>
                a.id === actionId ? { ...a, ...updated } : a
              ),
            }
          })
        )
      } catch (err) {
        setApproveError(getAxiosErrorMessage(err))
      } finally {
        setApprovingActionId(null)
      }
    },
    [approveMutation]
  )

  const stats = statsQuery.data
  const statsError =
    statsQuery.isError && getAxiosErrorMessage(statsQuery.error)

  return (
    <div className="flex flex-col gap-6 p-0">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-foreground">
            Agent Dashboard
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            LLM-powered auto-ops agent for intelligent system monitoring and
            remediation.
          </p>
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="shrink-0"
          onClick={() => {
            void handleRefresh()
          }}
          disabled={refreshing}
          aria-busy={refreshing}
          aria-label="Reload agent data and health"
        >
          <RefreshCw
            className={`mr-2 size-4 ${refreshing ? "animate-spin" : ""}`}
            aria-hidden
          />
          Reload
        </Button>
      </header>

      {(settingsQuery.isError ||
        sessionsQuery.isError ||
        statsQuery.isError) && (
        <Alert variant="destructive" role="alert">
          <AlertTitle>Could not load agent data</AlertTitle>
          <AlertDescription className="space-y-1">
            {settingsQuery.isError ? (
              <p>Settings: {getAxiosErrorMessage(settingsQuery.error)}</p>
            ) : null}
            {sessionsQuery.isError ? (
              <p>Sessions: {getAxiosErrorMessage(sessionsQuery.error)}</p>
            ) : null}
            {statsQuery.isError ? (
              <p>Stats: {getAxiosErrorMessage(statsQuery.error)}</p>
            ) : null}
          </AlertDescription>
        </Alert>
      )}

      {settingsError ? (
        <Alert variant="destructive" role="alert">
          <AlertTitle>Could not update autonomy</AlertTitle>
          <AlertDescription>{settingsError}</AlertDescription>
        </Alert>
      ) : null}

      {approveError ? (
        <Alert variant="destructive" role="alert">
          <AlertTitle>Could not update action</AlertTitle>
          <AlertDescription>{approveError}</AlertDescription>
        </Alert>
      ) : null}

      <section
        aria-label="Agent statistics"
        className="flex flex-wrap gap-4"
      >
        {statsQuery.isPending && !statsQuery.data ? (
          <>
            <Skeleton className="h-[5.5rem] min-w-[140px] flex-1 rounded-lg" />
            <Skeleton className="h-[5.5rem] min-w-[140px] flex-1 rounded-lg" />
            <Skeleton className="h-[5.5rem] min-w-[140px] flex-1 rounded-lg" />
            <Skeleton className="h-[5.5rem] min-w-[140px] flex-1 rounded-lg" />
          </>
        ) : (
          <>
            <StatCard
              label="Pending Approval"
              value={stats?.pending_approval ?? "—"}
              helpText="Actions requiring review"
              color={stats?.pending_approval ? "status.warning" : undefined}
              variant="full"
            />
            <StatCard
              label="Total Actions"
              value={stats?.total_actions ?? "—"}
              helpText="All time"
              variant="full"
            />
            <StatCard
              label="Auto-Approved Rate"
              value={
                stats?.auto_approved_rate != null
                  ? `${stats.auto_approved_rate.toFixed(1)}%`
                  : "—"
              }
              helpText="Safe/moderate actions"
              variant="full"
            />
            <StatCard
              label="Failed Actions"
              value={stats?.failed ?? "—"}
              helpText="Execution errors"
              color={stats?.failed ? "status.danger" : undefined}
              variant="full"
            />
          </>
        )}
      </section>

      {statsError && statsQuery.data ? (
        <p className="text-sm text-destructive" role="status">
          Stats refresh failed: {statsError}
        </p>
      ) : null}

      <div className="flex flex-col gap-6 lg:flex-row lg:items-stretch">
        <aside
          className="flex w-full shrink-0 flex-col gap-4 lg:max-w-sm"
          aria-label="Agent health and sessions"
        >
          {showSidebarSkeleton ? (
            <div className="flex flex-col gap-4">
              <Skeleton className="h-72 w-full rounded-xl" />
              <Skeleton className="h-56 w-full rounded-xl" />
            </div>
          ) : (
            <>
              <AgentHealthPanel
                health={healthData}
                autonomyLevel={autonomyLabel}
                onAutonomyChange={handleAutonomyChange}
              />
              <AgentSessionList
                sessions={sessionsQuery.data ?? []}
                selectedSessionId={selectedSessionId}
                onSelectSession={handleSelectSession}
              />
            </>
          )}
        </aside>

        <section
          className="flex h-[calc(100vh-14rem)] min-h-[24rem] min-w-0 flex-1 flex-col overflow-hidden"
          aria-labelledby="agent-chat-heading"
        >
          <div className="mb-2 flex items-center justify-between">
            <h2
              id="agent-chat-heading"
              className="text-lg font-semibold text-foreground"
            >
              Conversation
              {currentSessionId && (
                <span className="ml-2 text-sm font-normal text-muted-foreground">
                  (Session: {currentSessionId})
                </span>
              )}
            </h2>
            {messages.length > 0 && (
              <Button
                variant="outline"
                size="sm"
                onClick={handleNewChat}
                disabled={chatMutation.isPending}
              >
                New Chat
              </Button>
            )}
          </div>
          <AgentChatPanel
            className="min-h-0 flex-1"
            messages={messages}
            onSendMessage={(msg) => {
              void handleSendMessage(msg)
            }}
            isLoading={chatMutation.isPending}
            onApproveAction={(id, approved) => {
              void handleApproveAction(id, approved)
            }}
            approvingActionId={approvingActionId}
          />
        </section>
      </div>
    </div>
  )
}

export default AdminAgent
