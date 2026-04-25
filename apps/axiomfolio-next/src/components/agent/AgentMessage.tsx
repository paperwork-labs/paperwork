import * as React from "react"
import { format } from "date-fns"

import { cn } from "@/lib/utils"

import { AgentActionCard } from "./AgentActionCard"
import { AgentMarkdown } from "./AgentMarkdown"
import type { ChatMessage } from "./types"

export interface AgentMessageProps {
  message: ChatMessage
  onApproveAction?: (actionId: number, approved: boolean) => void
  approvingActionId?: number | null
}

export function AgentMessage({
  message,
  onApproveAction,
  approvingActionId,
}: AgentMessageProps) {
  const isUser = message.role === "user"
  const timeLabel = format(message.timestamp, "PPp")

  return (
    <article
      className={cn("flex w-full flex-col gap-2", isUser ? "items-end" : "items-start")}
      aria-label={isUser ? "Your message" : "Agent message"}
    >
      <div
        className={cn(
          "max-w-[min(100%,36rem)] rounded-xl px-3 py-2 text-sm shadow-xs",
          isUser
            ? "bg-blue-600 text-white dark:bg-blue-600"
            : "bg-card text-card-foreground ring-1 ring-border"
        )}
      >
        {isUser ? (
          <p className="whitespace-pre-wrap">{message.content}</p>
        ) : (
          <AgentMarkdown content={message.content} />
        )}
      </div>
      {!isUser && message.actions && message.actions.length > 0 && (
        <div
          className="flex w-full max-w-[min(100%,36rem)] flex-col gap-2"
          role="group"
          aria-label="Proposed actions"
        >
          {message.actions.map((action) => (
            <AgentActionCard
              key={action.id}
              action={action}
              isApproving={approvingActionId === action.id}
              onApprove={
                onApproveAction
                  ? (approved) => onApproveAction(action.id, approved)
                  : undefined
              }
            />
          ))}
        </div>
      )}
      <time
        className="text-xs text-muted-foreground"
        dateTime={message.timestamp.toISOString()}
      >
        {timeLabel}
      </time>
    </article>
  )
}
