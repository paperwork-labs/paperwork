import * as React from "react"
import { useQuery } from "@tanstack/react-query"
import { CheckCircle2, Loader2, XCircle, Clock } from "lucide-react"

import api from "@/services/api"
import { cn } from "@/lib/utils"
import { Skeleton } from "@/components/ui/skeleton"

interface TaskStatusResponse {
  task_id: string
  state: string
  result?: unknown
}

export interface AgentJobProgressProps {
  taskId: string
  taskName: string
}

const TERMINAL_STATES = new Set(["SUCCESS", "FAILURE", "REVOKED"])
const INITIAL_INTERVAL_MS = 2_000
const MAX_INTERVAL_MS = 30_000
const MAX_POLL_DURATION_MS = 10 * 60 * 1_000

export function AgentJobProgress({ taskId, taskName }: AgentJobProgressProps) {
  const startedAt = React.useRef(Date.now())
  const prevTaskId = React.useRef(taskId)

  if (prevTaskId.current !== taskId) {
    prevTaskId.current = taskId
    startedAt.current = Date.now()
  }

  const { data, isLoading, isError, error } = useQuery<TaskStatusResponse>({
      queryKey: ["task-status", taskId],
      queryFn: async () => {
        const res = await api.get<TaskStatusResponse>(
          `/accounts/tasks/${taskId}`,
        )
        return res.data
      },
      refetchInterval: (query) => {
        const state = query.state.data?.state
        if (state && TERMINAL_STATES.has(state)) return false
        if (Date.now() - startedAt.current > MAX_POLL_DURATION_MS) return false
        const elapsed = Date.now() - startedAt.current
        const interval = Math.min(
          INITIAL_INTERVAL_MS * Math.pow(1.5, Math.floor(elapsed / 15_000)),
          MAX_INTERVAL_MS,
        )
        return interval
      },
      refetchIntervalInBackground: false,
    })

  if (isLoading) {
    return <Skeleton className="h-10 w-full rounded-md" />
  }

  if (isError) {
    return (
      <div className="flex items-center gap-2 rounded-md bg-destructive/10 p-2 text-sm text-destructive">
        <XCircle className="size-4 shrink-0" aria-hidden />
        <span>
          Failed to check status:{" "}
          {(error as Error)?.message ?? "Unknown error"}
        </span>
      </div>
    )
  }

  const state = data?.state ?? "PENDING"
  const isTerminal = TERMINAL_STATES.has(state)
  const timedOut =
    !isTerminal && Date.now() - startedAt.current > MAX_POLL_DURATION_MS

  return (
    <div
      className={cn(
        "flex items-center gap-2 rounded-md p-2.5 text-sm",
        state === "SUCCESS" &&
          "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
        state === "FAILURE" && "bg-destructive/10 text-destructive",
        state === "REVOKED" && "bg-muted text-muted-foreground",
        !isTerminal && "bg-muted",
      )}
      role="status"
      aria-live="polite"
    >
      {!isTerminal && !timedOut && (
        <Loader2 className="size-4 shrink-0 animate-spin" aria-hidden />
      )}
      {state === "SUCCESS" && (
        <CheckCircle2 className="size-4 shrink-0" aria-hidden />
      )}
      {state === "FAILURE" && (
        <XCircle className="size-4 shrink-0" aria-hidden />
      )}
      {state === "REVOKED" && (
        <Clock className="size-4 shrink-0" aria-hidden />
      )}
      {timedOut && <Clock className="size-4 shrink-0" aria-hidden />}
      <span className="font-medium">{taskName}</span>
      <span className="text-muted-foreground">
        — {timedOut ? "Polling stopped (timeout)" : state}
      </span>
    </div>
  )
}

export default AgentJobProgress
