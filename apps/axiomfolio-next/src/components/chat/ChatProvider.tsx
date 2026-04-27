"use client";

import * as React from "react"
import { usePathname } from "next/navigation"
import axios from "axios"

import api from "@/services/api"
import { useAgentChat, useApproveAgentAction } from "@/hooks/useAgent"
import type { AgentAction, ChatMessage } from "@/components/agent/types"

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

const AGENT_SESSION_STORAGE_KEY = "agent_session_id"

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

export interface ChatContextValue {
  messages: ChatMessage[]
  currentSessionId: string | null
  selectedSessionId: string | undefined
  isOpen: boolean
  isOnAgentPage: boolean
  isLoading: boolean
  approvingActionId: number | null
  toggleChat: () => void
  openChat: () => void
  closeChat: () => void
  sendMessage: (message: string) => Promise<void>
  approveAction: (actionId: number, approved: boolean) => Promise<void>
  newChat: () => void
  selectSession: (sessionId: string) => Promise<void>
}

const ChatContext = React.createContext<ChatContextValue | null>(null)

export function useChatContext(): ChatContextValue {
  const ctx = React.useContext(ChatContext)
  if (!ctx) {
    throw new Error("useChatContext must be used within ChatProvider")
  }
  return ctx
}

export function ChatProvider({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const chatMutation = useAgentChat()
  const approveMutation = useApproveAgentAction()

  const [messages, setMessages] = React.useState<ChatMessage[]>([])
  const [currentSessionId, setCurrentSessionId] = React.useState<string | null>(
    () => {
      try {
        return sessionStorage.getItem(AGENT_SESSION_STORAGE_KEY)
      } catch {
        return null
      }
    },
  )
  const [selectedSessionId, setSelectedSessionId] = React.useState<
    string | undefined
  >()
  const [approvingActionId, setApprovingActionId] = React.useState<
    number | null
  >(null)
  const [isOpen, setIsOpen] = React.useState(false)

  const isOnAgentPage = pathname.startsWith("/settings/admin/agent")

  React.useEffect(() => {
    try {
      if (currentSessionId) {
        sessionStorage.setItem(AGENT_SESSION_STORAGE_KEY, currentSessionId)
      } else {
        sessionStorage.removeItem(AGENT_SESSION_STORAGE_KEY)
      }
    } catch {
      // ignore quota / private mode
    }
  }, [currentSessionId])

  React.useEffect(() => {
    if (isOnAgentPage && isOpen) {
      setIsOpen(false)
    }
  }, [isOnAgentPage, isOpen])

  const toggleChat = React.useCallback(() => setIsOpen((prev) => !prev), [])
  const openChat = React.useCallback(() => setIsOpen(true), [])
  const closeChat = React.useCallback(() => setIsOpen(false), [])

  const sendMessage = React.useCallback(
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

        if (data.session_id) {
          setCurrentSessionId(data.session_id)
        }

        const actions = (data.actions ?? []).map((a) =>
          normalizeRunAction(a as Record<string, unknown>),
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
    [chatMutation, currentSessionId],
  )

  const approveAction = React.useCallback(
    async (actionId: number, approved: boolean) => {
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
                a.id === actionId ? { ...a, ...updated } : a,
              ),
            }
          }),
        )
      } catch (err) {
        const errMsg: ChatMessage = {
          id: newMessageId(),
          role: "agent",
          content: `Action approval failed.\n\n${getAxiosErrorMessage(err)}`,
          timestamp: new Date(),
        }
        setMessages((prev) => [...prev, errMsg])
      } finally {
        setApprovingActionId(null)
      }
    },
    [approveMutation],
  )

  const newChat = React.useCallback(() => {
    setMessages([])
    try {
      sessionStorage.removeItem(AGENT_SESSION_STORAGE_KEY)
    } catch {
      // ignore
    }
    setCurrentSessionId(null)
    setSelectedSessionId(undefined)
  }, [])

  const selectSession = React.useCallback(
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
          const loadedMessages: ChatMessage[] = res.data.messages
            .filter((m) => m.role === "user" || m.role === "assistant")
            .map((m, i) => ({
              id: `${sessionId}-${i}`,
              role:
                m.role === "assistant"
                  ? ("agent" as const)
                  : ("user" as const),
              content: m.content,
              timestamp: new Date(),
            }))
          setMessages(loadedMessages)
        } else if (!res.data.found) {
          setMessages([
            {
              id: newMessageId(),
              role: "agent",
              content:
                "This conversation history is no longer available. " +
                "The session record exists, but the messages were not preserved. " +
                "You can start a new conversation using the **New Chat** button.",
              timestamp: new Date(),
            },
          ])
        } else {
          setMessages([])
        }
      } catch (err) {
        setCurrentSessionId(previousSessionId)
        setSelectedSessionId(previousSessionId ?? undefined)
        setMessages((prev) => [
          ...prev,
          {
            id: newMessageId(),
            role: "agent",
            content: `Could not load session: ${getAxiosErrorMessage(err)}`,
            timestamp: new Date(),
          },
        ])
      }
    },
    [currentSessionId],
  )

  const value = React.useMemo<ChatContextValue>(
    () => ({
      messages,
      currentSessionId,
      selectedSessionId,
      isOpen,
      isOnAgentPage,
      isLoading: chatMutation.isPending,
      approvingActionId,
      toggleChat,
      openChat,
      closeChat,
      sendMessage,
      approveAction,
      newChat,
      selectSession,
    }),
    [
      messages,
      currentSessionId,
      selectedSessionId,
      isOpen,
      isOnAgentPage,
      chatMutation.isPending,
      approvingActionId,
      toggleChat,
      openChat,
      closeChat,
      sendMessage,
      approveAction,
      newChat,
      selectSession,
    ],
  )

  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>
}
