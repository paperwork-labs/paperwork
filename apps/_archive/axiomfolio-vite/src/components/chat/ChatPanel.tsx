import * as React from "react"
import { motion, useReducedMotion } from "framer-motion"
import { X } from "lucide-react"

import { useChatContext } from "./ChatProvider"
import { AgentChatPanel } from "@/components/agent/AgentChatPanel"
import { cn } from "@/lib/utils"

export function ChatPanel() {
  const {
    messages,
    isLoading,
    sendMessage,
    approveAction,
    approvingActionId,
    closeChat,
    newChat,
  } = useChatContext()
  const prefersReducedMotion = useReducedMotion()
  const panelRef = React.useRef<HTMLDivElement>(null)
  const previousFocusRef = React.useRef<HTMLElement | null>(null)

  React.useEffect(() => {
    previousFocusRef.current = document.activeElement as HTMLElement | null

    const frame = requestAnimationFrame(() => {
      panelRef.current?.focus()
    })

    return () => {
      cancelAnimationFrame(frame)
      previousFocusRef.current?.focus()
    }
  }, [])

  React.useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") closeChat()
    }
    window.addEventListener("keydown", handler)
    return () => window.removeEventListener("keydown", handler)
  }, [closeChat])

  return (
    <motion.div
      ref={panelRef}
      tabIndex={-1}
      className={cn(
        "fixed bottom-24 right-6 z-50 flex flex-col overflow-hidden rounded-2xl border border-border bg-background shadow-2xl",
        "h-[min(600px,calc(100vh-8rem))] w-[min(400px,calc(100vw-3rem))]",
        "focus:outline-none",
      )}
      initial={
        prefersReducedMotion
          ? { opacity: 0, y: 0, scale: 1 }
          : { opacity: 0, y: 20, scale: 0.95 }
      }
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={
        prefersReducedMotion
          ? { opacity: 0, y: 0, scale: 1 }
          : { opacity: 0, y: 20, scale: 0.95 }
      }
      transition={{ type: "spring", damping: 25, stiffness: 300 }}
      role="dialog"
      aria-label="Agent chat"
    >
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <h3 className="text-sm font-semibold text-foreground">Agent Guru</h3>
        <div className="flex items-center gap-2">
          {messages.length > 0 && (
            <button
              type="button"
              onClick={newChat}
              className="text-xs text-muted-foreground transition-colors hover:text-foreground"
            >
              New Chat
            </button>
          )}
          <button
            type="button"
            onClick={closeChat}
            className="rounded-md p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            aria-label="Close chat"
          >
            <X className="size-4" />
          </button>
        </div>
      </div>
      <AgentChatPanel
        className="min-h-0 flex-1 rounded-none border-0"
        messages={messages}
        onSendMessage={(msg) => void sendMessage(msg)}
        isLoading={isLoading}
        onApproveAction={(id, approved) => void approveAction(id, approved)}
        approvingActionId={approvingActionId}
      />
    </motion.div>
  )
}
