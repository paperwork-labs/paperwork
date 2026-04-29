"use client";

import { ChatProvider } from "@/components/chat/ChatProvider"

import * as React from "react"
import { useQueryClient } from "@tanstack/react-query"
import { AnimatePresence, motion, useReducedMotion } from "framer-motion"
import { ChevronRight, Info, RefreshCw, X } from "lucide-react"
import axios from "axios"

import { CAPABILITY_GROUPS } from "@/components/admin/AdminAgentCapabilities"

import {
  AgentChatPanel,
  AgentSessionList,
} from "@/components/agent"
import { AUTONOMY_LEVELS } from "@/components/agent/types"
import { useChatContext } from "@/components/chat/ChatProvider"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@paperwork-labs/ui"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"
import {
  autonomyApiToLabel,
  autonomyLabelToApi,
  useAgentSessions,
  useAgentSettings,
  useAgentStats,
  usePatchAgentSettings,
} from "@/hooks/useAgent"
import useAdminHealth from "@/hooks/useAdminHealth"
import type {
  CoverageDimension,
  StageQualityDimension,
  JobsDimension,
  AuditDimension,
  RegimeDimension,
  FundamentalsDimension,
  PortfolioSyncDimension,
  IbkrGatewayDimension,
  ProviderUsage,
} from "@/types/adminHealth"

type DimensionValue =
  | CoverageDimension
  | StageQualityDimension
  | JobsDimension
  | AuditDimension
  | RegimeDimension
  | FundamentalsDimension
  | PortfolioSyncDimension
  | IbkrGatewayDimension

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

function getDimensionHint(key: string, dim: DimensionValue): string | null {
  const { status } = dim
  if (status === "green" || status === "ok") return null
  switch (key) {
    case "coverage": {
      const d = dim as CoverageDimension
      return `${d.stale_daily ?? 0} stale symbol(s)`
    }
    case "stage_quality": {
      const d = dim as StageQualityDimension
      return `${d.invalid_count ?? 0} invalid`
    }
    case "audit":
      return "Fill below threshold"
    case "jobs": {
      const d = dim as JobsDimension
      return `${d.error_count ?? 0} failures`
    }
    case "regime": {
      const d = dim as RegimeDimension
      return d.age_hours > 24 ? "Regime stale" : null
    }
    case "fundamentals": {
      const d = dim as FundamentalsDimension
      return status === "warning"
        ? `Fill at ${d.fundamentals_fill_pct?.toFixed(0) ?? "?"}%`
        : "Data incomplete"
    }
    case "portfolio_sync": {
      const d = dim as PortfolioSyncDimension
      return d.stale_accounts > 0 ? `${d.stale_accounts} stale` : null
    }
    case "ibkr_gateway": {
      const d = dim as IbkrGatewayDimension
      return d.note || "Status unknown"
    }
    default:
      return null
  }
}

function formatDimKey(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

function HealthChip({
  name,
  status,
  hint,
}: {
  name: string
  status: string
  hint: string | null
}) {
  const isPass = status === "green" || status === "ok"
  const isWarn = status === "yellow" || status === "warning"

  return (
    <div
      className={cn(
        "flex shrink-0 items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium transition-colors",
        isPass && "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
        isWarn && "bg-amber-500/10 text-amber-700 dark:text-amber-300",
        !isPass &&
          !isWarn &&
          "bg-destructive/10 text-destructive",
      )}
      role="listitem"
      title={hint ?? undefined}
    >
      <span
        className={cn(
          "size-1.5 rounded-full",
          isPass && "bg-emerald-500",
          isWarn && "bg-amber-500",
          !isPass && !isWarn && "bg-destructive",
        )}
      />
      <span>{formatDimKey(name)}</span>
    </div>
  )
}

interface CapabilitiesSidebarProps {
  onClose: () => void
  onCapabilityClick?: (toolName: string) => void
}

const CapabilitiesSidebar: React.FC<CapabilitiesSidebarProps> = ({
  onClose,
  onCapabilityClick,
}) => {
  const [openGroups, setOpenGroups] = React.useState<Set<string>>(new Set())

  const toggleGroup = (title: string) => {
    setOpenGroups((prev) => {
      const next = new Set(prev)
      if (next.has(title)) {
        next.delete(title)
      } else {
        next.add(title)
      }
      return next
    })
  }

  const totalCapabilities = CAPABILITY_GROUPS.reduce(
    (sum, g) => sum + g.capabilities.length,
    0,
  )

  return (
    <div className="flex h-full w-72 flex-col border-l border-border bg-card">
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <div>
          <h3 className="text-sm font-semibold text-foreground">
            Capabilities
          </h3>
          <p className="text-xs text-muted-foreground">
            {totalCapabilities} tools available
          </p>
        </div>
        <Button
          variant="ghost"
          size="icon"
          className="size-7"
          onClick={onClose}
          aria-label="Close capabilities panel"
        >
          <X className="size-4" />
        </Button>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="p-2">
          {CAPABILITY_GROUPS.map((group) => {
            const Icon = group.icon
            const isOpen = openGroups.has(group.title)
            return (
              <Collapsible
                key={group.title}
                open={isOpen}
                onOpenChange={() => toggleGroup(group.title)}
              >
                <CollapsibleTrigger asChild>
                  <button
                    type="button"
                    className="flex w-full items-center gap-2 rounded-md px-2 py-2 text-left transition-colors hover:bg-muted/50"
                  >
                    <ChevronRight
                      className={cn(
                        "size-4 shrink-0 text-muted-foreground transition-transform",
                        isOpen && "rotate-90",
                      )}
                    />
                    <Icon className="size-4 shrink-0 text-primary" />
                    <span className="flex-1 text-sm font-medium text-foreground">
                      {group.title}
                    </span>
                    <Badge variant="secondary" className="text-[10px]">
                      {group.capabilities.length}
                    </Badge>
                  </button>
                </CollapsibleTrigger>
                <CollapsibleContent>
                  <ul className="ml-6 space-y-1 pb-2 pl-2">
                    {group.capabilities.map((cap) => (
                      <li key={cap.name}>
                        <button
                          type="button"
                          className="w-full cursor-pointer rounded-md px-2 py-1.5 text-left text-xs transition-colors hover:bg-accent focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                          onClick={() => onCapabilityClick?.(cap.name)}
                          aria-label={`Run ${cap.name}: ${cap.description}`}
                        >
                          <div className="flex items-start gap-1.5">
                            <Badge
                              variant={
                                cap.risk === "safe" ? "secondary" : "outline"
                              }
                              className="mt-0.5 shrink-0 text-[9px] capitalize"
                            >
                              {cap.risk}
                            </Badge>
                            <div className="min-w-0">
                              <code className="text-[11px] font-medium text-primary">
                                {cap.name}
                              </code>
                              <p className="text-[11px] leading-tight text-muted-foreground">
                                {cap.description}
                              </p>
                            </div>
                          </div>
                        </button>
                      </li>
                    ))}
                  </ul>
                </CollapsibleContent>
              </Collapsible>
            )
          })}
        </div>
      </div>
    </div>
  )
}

const AdminAgentInner: React.FC = () => {
  const queryClient = useQueryClient()
  const chat = useChatContext()
  const { health, loading: healthLoading } = useAdminHealth()
  const settingsQuery = useAgentSettings()
  const sessionsQuery = useAgentSessions()
  const statsQuery = useAgentStats()
  const patchSettings = usePatchAgentSettings()
  const prefersReducedMotion = useReducedMotion()

  const [settingsError, setSettingsError] = React.useState<string | null>(null)
  const [approveError, setApproveError] = React.useState<string | null>(null)
  const [showCapabilities, setShowCapabilities] = React.useState(false)
  const [refreshing, setRefreshing] = React.useState(false)

  const autonomyLabel = autonomyApiToLabel(
    settingsQuery.data?.autonomy_level ?? "safe",
  )

  const showSidebarSkeleton =
    (settingsQuery.isPending && !settingsQuery.data) ||
    (sessionsQuery.isPending && !sessionsQuery.data)

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
    [patchSettings, settingsQuery.data?.autonomy_level],
  )

  const handleApproveAction = React.useCallback(
    async (id: number, approved: boolean) => {
      setApproveError(null)
      try {
        await chat.approveAction(id, approved)
      } catch (err) {
        setApproveError(getAxiosErrorMessage(err))
      }
    },
    [chat],
  )

  const handleCapabilityClick = React.useCallback(
    (toolName: string) => {
      void chat.sendMessage(`Run ${toolName}`)
      setShowCapabilities(false)
    },
    [chat],
  )

  const stats = statsQuery.data
  const statsError =
    statsQuery.isError && getAxiosErrorMessage(statsQuery.error)

  const healthEntries = React.useMemo(() => {
    if (!health?.dimensions) return []
    return Object.entries(health.dimensions) as [
      string,
      DimensionValue,
    ][]
  }, [health?.dimensions])

  return (
    <div className="flex flex-col gap-4 p-0">
      {/* Compact header: title + inline stats + action buttons */}
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-xl font-semibold tracking-tight text-foreground">
            Agent Dashboard
          </h1>
          {statsQuery.isPending && !stats ? (
            <div className="flex items-center gap-1.5">
              {[1, 2, 3, 4].map((i) => (
                <Skeleton key={i} className="h-5 w-16 rounded-full" />
              ))}
            </div>
          ) : (
            <div className="flex flex-wrap items-center gap-1.5">
              <Badge
                variant={stats?.pending_approval ? "default" : "secondary"}
                className="text-xs"
              >
                Pending: {stats?.pending_approval ?? 0}
              </Badge>
              <Badge variant="secondary" className="text-xs">
                Total: {stats?.total_actions ?? 0}
              </Badge>
              <Badge variant="secondary" className="text-xs">
                Rate:{" "}
                {stats?.auto_approved_rate != null
                  ? `${stats.auto_approved_rate.toFixed(0)}%`
                  : "—"}
              </Badge>
              {(stats?.failed ?? 0) > 0 && (
                <Badge variant="destructive" className="text-xs">
                  Failed: {stats?.failed}
                </Badge>
              )}
            </div>
          )}
        </div>
        <div className="flex shrink-0 gap-2">
          <Button
            type="button"
            variant={showCapabilities ? "secondary" : "outline"}
            size="sm"
            onClick={() => setShowCapabilities(!showCapabilities)}
            aria-pressed={showCapabilities}
            aria-label="Toggle capabilities panel"
          >
            <Info className="mr-2 size-4" aria-hidden />
            Capabilities
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => void handleRefresh()}
            disabled={refreshing}
            aria-busy={refreshing}
            aria-label="Reload agent data and health"
          >
            <RefreshCw
              className={cn("mr-2 size-4", refreshing && "animate-spin")}
              aria-hidden
            />
            Reload
          </Button>
        </div>
      </header>

      {/* Error alerts */}
      {(settingsQuery.isError ||
        sessionsQuery.isError ||
        statsQuery.isError) && (
        <Alert variant="destructive" role="alert">
          <AlertTitle>Could not load agent data</AlertTitle>
          <AlertDescription className="space-y-1">
            {settingsQuery.isError && (
              <p>Settings: {getAxiosErrorMessage(settingsQuery.error)}</p>
            )}
            {sessionsQuery.isError && (
              <p>Sessions: {getAxiosErrorMessage(sessionsQuery.error)}</p>
            )}
            {statsQuery.isError && (
              <p>Stats: {getAxiosErrorMessage(statsQuery.error)}</p>
            )}
          </AlertDescription>
        </Alert>
      )}

      {settingsError && (
        <Alert variant="destructive" role="alert">
          <AlertTitle>Could not update autonomy</AlertTitle>
          <AlertDescription>{settingsError}</AlertDescription>
        </Alert>
      )}

      {approveError && (
        <Alert variant="destructive" role="alert">
          <AlertTitle>Could not update action</AlertTitle>
          <AlertDescription>{approveError}</AlertDescription>
        </Alert>
      )}

      {statsError && stats && (
        <p className="text-sm text-destructive" role="status">
          Stats refresh failed: {statsError}
        </p>
      )}

      {/* Horizontal health chips */}
      <div
        className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-1"
        role="list"
        aria-label="Health dimensions"
      >
        {healthLoading ? (
          <>
            {[1, 2, 3, 4, 5].map((i) => (
              <Skeleton
                key={i}
                className="h-7 w-24 shrink-0 rounded-full"
              />
            ))}
          </>
        ) : (
          healthEntries.map(([key, dim]) => (
            <HealthChip
              key={key}
              name={key}
              status={dim.status}
              hint={getDimensionHint(key, dim)}
            />
          ))
        )}
      </div>

      {health?.provider_metrics && health.provider_metrics.providers && Object.keys(health.provider_metrics.providers).length > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-medium text-muted-foreground">Providers:</span>
          {health.provider_metrics.providers && Object.entries(health.provider_metrics.providers).map(([name, data]) => {
            const usage = data as ProviderUsage
            const color = usage.pct > 90 ? 'bg-destructive/10 text-destructive' : usage.pct > 70 ? 'bg-amber-100 text-amber-700' : 'bg-emerald-100 text-emerald-700'
            return (
              <Badge key={name} variant="outline" className={cn('text-xs', color)}>
                {name} {usage.pct}%
              </Badge>
            )
          })}
          <Badge variant="outline" className="text-xs bg-blue-100 text-blue-700">
            L2 {health.provider_metrics.l2_hit_rate ?? 0}%
          </Badge>
        </div>
      )}

      {/* Main content: sidebar + chat + capabilities */}
      <div className="flex flex-col gap-6 lg:flex-row lg:items-stretch">
        <aside
          className="flex w-full shrink-0 flex-col gap-4 lg:max-w-xs"
          aria-label="Agent settings and sessions"
        >
          {showSidebarSkeleton ? (
            <div className="flex flex-col gap-4">
              <Skeleton className="h-48 w-full rounded-xl" />
              <Skeleton className="h-56 w-full rounded-xl" />
            </div>
          ) : (
            <>
              <Card size="sm" className="gap-4">
                <CardHeader className="pb-0">
                  <CardTitle className="text-sm">Autonomy</CardTitle>
                </CardHeader>
                <CardContent>
                  <Tabs
                    value={autonomyLabel}
                    onValueChange={handleAutonomyChange}
                    className="w-full"
                    aria-label="Autonomy level"
                  >
                    <TabsList
                      variant="default"
                      className="grid w-full grid-cols-3"
                      aria-label="Autonomy level"
                    >
                      {AUTONOMY_LEVELS.map((level) => (
                        <TabsTrigger
                          key={level}
                          value={level}
                          className="text-xs sm:text-sm"
                        >
                          {level}
                        </TabsTrigger>
                      ))}
                    </TabsList>
                    <TabsContent
                      value="Safe"
                      className="mt-2 text-xs text-muted-foreground"
                    >
                      <p>
                        Low-risk automation only; approvals for anything
                        sensitive.
                      </p>
                    </TabsContent>
                    <TabsContent
                      value="Full"
                      className="mt-2 text-xs text-muted-foreground"
                    >
                      <p>
                        Agent may act within policy without asking, where
                        allowed.
                      </p>
                    </TabsContent>
                    <TabsContent
                      value="Ask"
                      className="mt-2 text-xs text-muted-foreground"
                    >
                      <p>
                        Confirm each substantive step before execution.
                      </p>
                    </TabsContent>
                  </Tabs>
                </CardContent>
              </Card>
              <AgentSessionList
                sessions={sessionsQuery.data ?? []}
                selectedSessionId={chat.selectedSessionId}
                onSelectSession={(id) => void chat.selectSession(id)}
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
              {chat.currentSessionId && (
                <span className="ml-2 text-sm font-normal text-muted-foreground">
                  (Session: {chat.currentSessionId})
                </span>
              )}
            </h2>
            {chat.messages.length > 0 && (
              <Button
                variant="outline"
                size="sm"
                onClick={chat.newChat}
                disabled={chat.isLoading}
              >
                New Chat
              </Button>
            )}
          </div>
          <AgentChatPanel
            className="min-h-0 flex-1"
            messages={chat.messages}
            onSendMessage={(msg) => void chat.sendMessage(msg)}
            isLoading={chat.isLoading}
            onApproveAction={(id, approved) =>
              void handleApproveAction(id, approved)
            }
            approvingActionId={chat.approvingActionId}
          />
        </section>

        <AnimatePresence>
          {showCapabilities && (
            <motion.div
              initial={
                prefersReducedMotion
                  ? { opacity: 0, x: 0 }
                  : { opacity: 0, x: 20 }
              }
              animate={{ opacity: 1, x: 0 }}
              exit={
                prefersReducedMotion
                  ? { opacity: 0, x: 0 }
                  : { opacity: 0, x: 20 }
              }
              transition={{ duration: 0.2, ease: "easeOut" }}
            >
              <CapabilitiesSidebar
                onClose={() => setShowCapabilities(false)}
                onCapabilityClick={handleCapabilityClick}
              />
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}

export default function AdminAgentClient() {
  return (
    <ChatProvider>
      <AdminAgentInner />
    </ChatProvider>
  )
}
