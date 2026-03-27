import * as React from "react"
import { Loader2, SendHorizontal, Zap } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Textarea } from "@/components/ui/textarea"
import { cn } from "@/lib/utils"

import { AgentMessage } from "./AgentMessage"
import type { ChatMessage } from "./types"

interface QuickAction {
  label: string
  prompt: string
}

const QUICK_ACTIONS: QuickAction[] = [
  { label: "Market Breadth", prompt: "What's the stage distribution across the market?" },
  { label: "Sector Leaders", prompt: "Which sectors are strongest right now?" },
  { label: "Trade Ideas", prompt: "Show me the top Set 1 scan picks" },
  { label: "Exit Review", prompt: "Any positions I should review for exits?" },
  { label: "Regime Status", prompt: "What's the current regime and recent history?" },
]

export interface AgentChatPanelProps {
  messages: ChatMessage[]
  onSendMessage: (message: string) => void
  isLoading?: boolean
  onApproveAction?: (actionId: number, approved: boolean) => void
  approvingActionId?: number | null
  className?: string
}

export function AgentChatPanel({
  messages,
  onSendMessage,
  isLoading = false,
  onApproveAction,
  approvingActionId,
  className,
}: AgentChatPanelProps) {
  const [draft, setDraft] = React.useState("")
  const endRef = React.useRef<HTMLDivElement>(null)

  React.useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" })
  }, [messages, isLoading])

  const trySend = React.useCallback(() => {
    const text = draft.trim()
    if (!text || isLoading) return
    onSendMessage(text)
    setDraft("")
  }, [draft, isLoading, onSendMessage])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    trySend()
  }

  return (
    <div
      className={cn(
        "flex min-h-[20rem] flex-1 flex-col rounded-xl border border-border bg-background",
        className
      )}
    >
      <div
        role="log"
        aria-live="polite"
        aria-relevant="additions"
        aria-label="Agent conversation"
        className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto p-4"
      >
        {messages.length === 0 && !isLoading && (
          <div className="flex flex-col items-center justify-center gap-4 py-8">
            <div className="rounded-full bg-primary/10 p-3">
              <Zap className="size-6 text-primary" />
            </div>
            <div className="text-center">
              <h3 className="text-base font-medium text-foreground">
                Welcome to Agent Guru
              </h3>
              <p className="mt-1 max-w-sm text-sm text-muted-foreground">
                I can help you analyze markets, review positions, and monitor system health. Try one of these:
              </p>
            </div>
            <div className="flex flex-wrap justify-center gap-2 max-w-md">
              {QUICK_ACTIONS.map((action) => (
                <button
                  key={action.label}
                  type="button"
                  onClick={() => onSendMessage(action.prompt)}
                  className="rounded-full border border-border bg-muted/50 px-3 py-1.5 text-sm font-medium text-foreground transition-colors hover:bg-muted hover:border-primary/50"
                >
                  {action.label}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m) => (
          <AgentMessage
            key={m.id}
            message={m}
            onApproveAction={onApproveAction}
            approvingActionId={approvingActionId}
          />
        ))}
        {!isLoading && messages.length > 0 && (
          <div className="flex flex-wrap items-center gap-2 border-t border-dashed border-border/50 pt-3 mt-2">
            <Zap className="size-3.5 text-muted-foreground" />
            <span className="text-xs text-muted-foreground mr-1">Quick:</span>
            {QUICK_ACTIONS.map((action) => (
              <button
                key={action.label}
                type="button"
                onClick={() => onSendMessage(action.prompt)}
                className="rounded-full border border-border bg-muted/50 px-2.5 py-1 text-xs font-medium text-foreground transition-colors hover:bg-muted hover:border-primary/50"
              >
                {action.label}
              </button>
            ))}
          </div>
        )}
        {isLoading && (
          <div
            className="flex items-center gap-2 rounded-lg border border-dashed border-border bg-muted/40 px-3 py-2 text-sm text-muted-foreground"
            aria-busy="true"
            aria-label="Agent is thinking"
          >
            <Loader2 className="size-4 shrink-0 animate-spin" aria-hidden />
            <div className="flex flex-1 flex-col gap-2">
              <span>Agent is thinking…</span>
              <Skeleton className="h-3 max-w-xs w-[75%]" />
              <Skeleton className="h-3 w-1/2 max-w-[12rem]" />
            </div>
          </div>
        )}
        <div ref={endRef} aria-hidden />
      </div>
      <form
        onSubmit={handleSubmit}
        className="sticky bottom-0 z-10 border-t border-border bg-background/95 p-3 backdrop-blur supports-backdrop-filter:bg-background/80"
      >
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
          <Textarea
            id="agent-chat-input"
            name="message"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Message the agent…"
            rows={2}
            disabled={isLoading}
            aria-label="Message to agent"
            className="min-h-[4.5rem] resize-y sm:min-h-[2.75rem]"
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault()
                trySend()
              }
            }}
          />
          <Button
            type="submit"
            disabled={isLoading || !draft.trim()}
            className="shrink-0 sm:w-auto"
            aria-label="Send message"
          >
            <SendHorizontal className="size-4 sm:mr-1" aria-hidden />
            <span className="hidden sm:inline">Send</span>
          </Button>
        </div>
        <p className="mt-1 text-xs text-muted-foreground">
          Press Enter to send, Shift+Enter for a new line.
        </p>
      </form>
    </div>
  )
}
