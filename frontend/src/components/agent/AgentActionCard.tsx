import * as React from "react"
import { Check, Loader2, X } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
} from "@/components/ui/card"
import { cn } from "@/lib/utils"

import type { AgentAction } from "./types"

export interface AgentActionCardProps {
  action: AgentAction
  onApprove?: (approved: boolean) => void
  isApproving?: boolean
}

function riskBadgeClass(risk: string): string {
  switch (risk) {
    case "safe":
      return "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400"
    case "moderate":
      return "border-blue-500/40 bg-blue-500/10 text-blue-700 dark:text-blue-400"
    case "risky":
      return "border-amber-500/50 bg-amber-500/10 text-amber-800 dark:text-amber-300"
    case "critical":
      return ""
    default:
      return ""
  }
}

function statusBadgeVariant(
  status: string
): React.ComponentProps<typeof Badge>["variant"] {
  if (status === "failed" || status === "rejected") return "destructive"
  if (status === "completed") return "secondary"
  return "outline"
}

export function AgentActionCard({
  action,
  onApprove,
  isApproving,
}: AgentActionCardProps) {
  if (action.status === "completed") {
    return (
      <div
        className="flex items-center gap-2 rounded-md border border-border/50 bg-muted/30 px-3 py-1.5 text-sm"
        data-action-id={action.id}
      >
        <Check
          className="size-3.5 shrink-0 text-emerald-500"
          aria-hidden
        />
        <span className="min-w-0 font-medium">{action.action_name}</span>
        <Badge variant="outline" className="ml-auto shrink-0 text-xs capitalize">
          {action.risk_level}
        </Badge>
      </div>
    )
  }

  const isPendingApproval = action.status === "pending_approval"
  const isExecuting = action.status === "executing"
  const riskExtra = riskBadgeClass(action.risk_level)
  const riskIsCritical = action.risk_level === "critical"

  return (
    <Card
      size="sm"
      className="gap-0 py-0 shadow-none ring-1 ring-border"
      data-action-id={action.id}
    >
      <CardHeader className="flex flex-row flex-wrap items-center gap-2 border-b border-border py-3">
        <Badge variant={statusBadgeVariant(action.status)} className="capitalize">
          {action.status.replace(/_/g, " ")}
        </Badge>
        <Badge
          variant={riskIsCritical ? "destructive" : "outline"}
          className={cn("capitalize", !riskIsCritical && riskExtra)}
        >
          {action.risk_level}
        </Badge>
        <span className="min-w-0 flex-1 font-medium text-card-foreground">
          {action.action_name}
        </span>
        {isExecuting && (
          <Loader2
            className="size-4 shrink-0 animate-spin text-muted-foreground"
            aria-hidden
          />
        )}
      </CardHeader>
      {action.reasoning ? (
        <CardContent className="py-3">
          <p className="text-sm text-muted-foreground">{action.reasoning}</p>
        </CardContent>
      ) : null}
      {isPendingApproval && onApprove && (
        <CardFooter className="flex flex-wrap gap-2 border-t border-border py-3">
          <Button
            type="button"
            size="sm"
            variant="default"
            disabled={isApproving}
            aria-label={`Approve action: ${action.action_name}`}
            onClick={() => onApprove(true)}
          >
            {isApproving ? (
              <>
                <Loader2 className="size-4 animate-spin" aria-hidden />
                <span className="sr-only">Approving</span>
              </>
            ) : (
              <>
                <Check className="size-4" aria-hidden />
                Approve
              </>
            )}
          </Button>
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={isApproving}
            aria-label={`Reject action: ${action.action_name}`}
            onClick={() => onApprove(false)}
          >
            <X className="size-4" aria-hidden />
            Reject
          </Button>
        </CardFooter>
      )}
    </Card>
  )
}
