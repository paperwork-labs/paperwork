import * as React from "react"
import { format } from "date-fns"
import { ChevronDown, History } from "lucide-react"

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { cn } from "@/lib/utils"

import type { AgentSession } from "./types"

export interface AgentSessionListProps {
  sessions: AgentSession[]
  selectedSessionId?: string
  onSelectSession: (sessionId: string) => void
  className?: string
}

export function AgentSessionList({
  sessions,
  selectedSessionId,
  onSelectSession,
  className,
}: AgentSessionListProps) {
  const [open, setOpen] = React.useState(true)
  const listId = React.useId()

  return (
    <Card className={cn("gap-0 overflow-hidden py-0", className)} size="sm">
      <CardHeader className="border-b border-border py-3">
        <button
          type="button"
          id={`${listId}-toggle`}
          aria-expanded={open}
          aria-controls={`${listId}-panel`}
          onClick={() => setOpen((v) => !v)}
          className="flex w-full items-center justify-between gap-2 rounded-md text-left outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
        >
          <div className="flex items-center gap-2">
            <History className="size-4 shrink-0 text-muted-foreground" aria-hidden />
            <div>
              <CardTitle className="text-base">Sessions</CardTitle>
              <CardDescription>Past agent conversations</CardDescription>
            </div>
          </div>
          <ChevronDown
            className={cn(
              "size-4 shrink-0 text-muted-foreground transition-transform",
              open && "rotate-180"
            )}
            aria-hidden
          />
        </button>
      </CardHeader>
      {open && (
        <CardContent
          id={`${listId}-panel`}
          role="region"
          aria-labelledby={`${listId}-toggle`}
          className="max-h-72 overflow-y-auto px-0 py-0"
        >
          {sessions.length === 0 ? (
            <p className="px-4 py-6 text-center text-sm text-muted-foreground">
              No sessions yet.
            </p>
          ) : (
            <ul className="flex flex-col" role="listbox" aria-label="Session history">
              {sessions.map((session) => {
                const selected = session.id === selectedSessionId
                return (
                  <li key={session.id}>
                    <button
                      type="button"
                      role="option"
                      aria-selected={selected}
                      onClick={() => onSelectSession(session.id)}
                      className={cn(
                        "flex w-full flex-col items-start gap-0.5 border-b border-border px-4 py-3 text-left text-sm transition-colors last:border-b-0",
                        "hover:bg-muted/60 focus-visible:bg-muted/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring",
                        selected && "bg-muted/80"
                      )}
                    >
                      <span className="font-medium text-foreground">
                        {format(session.startedAt, "PPp")}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {session.actionCount}{" "}
                        {session.actionCount === 1 ? "action" : "actions"} ·{" "}
                        {session.statusSummary}
                      </span>
                    </button>
                  </li>
                )
              })}
            </ul>
          )}
        </CardContent>
      )}
    </Card>
  )
}
