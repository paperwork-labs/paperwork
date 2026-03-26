import * as React from "react"
import { AlertCircle, CheckCircle2, Circle } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { cn } from "@/lib/utils"

import { AUTONOMY_LEVELS, type HealthData, type HealthSignal } from "./types"

export interface AgentHealthPanelProps {
  health?: HealthData
  autonomyLevel: string
  onAutonomyChange: (level: string) => void
  className?: string
}

const DIMENSIONS: { key: keyof HealthData; label: string }[] = [
  { key: "coverage", label: "Coverage" },
  { key: "stage", label: "Stage" },
  { key: "jobs", label: "Jobs" },
  { key: "audit", label: "Audit" },
  { key: "regime", label: "Regime" },
]

function signalIcon(signal: HealthSignal) {
  switch (signal) {
    case "ok":
      return (
        <CheckCircle2
          className="size-4 text-emerald-600 dark:text-emerald-400"
          aria-hidden
        />
      )
    case "warn":
      return (
        <AlertCircle
          className="size-4 text-amber-600 dark:text-amber-400"
          aria-hidden
        />
      )
    case "error":
      return (
        <AlertCircle className="size-4 text-destructive" aria-hidden />
      )
    default:
      return <Circle className="size-4 text-muted-foreground" aria-hidden />
  }
}

function signalBadge(signal: HealthSignal) {
  const label =
    signal === "ok" ? "Healthy" : signal === "warn" ? "Attention" : "Critical"
  const variant =
    signal === "ok"
      ? "secondary"
      : signal === "warn"
        ? "outline"
        : "destructive"
  return (
    <Badge
      variant={variant}
      className={cn(
        signal === "ok" &&
          "border-emerald-500/30 bg-emerald-500/10 text-emerald-800 dark:text-emerald-300",
        signal === "warn" &&
          "border-amber-500/40 bg-amber-500/10 text-amber-900 dark:text-amber-200"
      )}
    >
      {label}
    </Badge>
  )
}

export function AgentHealthPanel({
  health,
  autonomyLevel,
  onAutonomyChange,
  className,
}: AgentHealthPanelProps) {
  const resolved = health ?? {
    coverage: "warn" as const,
    stage: "ok" as const,
    jobs: "ok" as const,
    audit: "ok" as const,
    regime: "warn" as const,
  }

  return (
    <Card className={cn("gap-4", className)} size="sm">
      <CardHeader className="pb-0">
        <CardTitle>Health</CardTitle>
        <CardDescription>
          Live signals across intelligence and operations.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <ul className="flex flex-col gap-3" aria-label="Health dimensions">
          {DIMENSIONS.map(({ key, label }) => {
            const signal = resolved[key]
            return (
              <li
                key={key}
                className="flex items-center justify-between gap-2 rounded-lg border border-border bg-muted/30 px-3 py-2"
              >
                <div className="flex items-center gap-2">
                  {signalIcon(signal)}
                  <span className="text-sm font-medium text-foreground">
                    {label}
                  </span>
                </div>
                {signalBadge(signal)}
              </li>
            )
          })}
        </ul>

        <div className="border-t border-border pt-4">
          <p
            id="autonomy-heading"
            className="mb-2 text-sm font-medium text-foreground"
          >
            Autonomy
          </p>
          <Tabs
            value={autonomyLevel}
            onValueChange={onAutonomyChange}
            className="w-full"
            aria-labelledby="autonomy-heading"
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
            <TabsContent value="Safe" className="mt-2 text-xs text-muted-foreground">
              <p>Low-risk automation only; approvals for anything sensitive.</p>
            </TabsContent>
            <TabsContent value="Full" className="mt-2 text-xs text-muted-foreground">
              <p>Agent may act within policy without asking, where allowed.</p>
            </TabsContent>
            <TabsContent value="Ask" className="mt-2 text-xs text-muted-foreground">
              <p>Confirm each substantive step before execution.</p>
            </TabsContent>
          </Tabs>
        </div>
      </CardContent>
    </Card>
  )
}
