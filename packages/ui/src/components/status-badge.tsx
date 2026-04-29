import * as React from "react";

import { cn } from "../lib/utils";

export type StatusTone =
  | "urgency-critical"
  | "urgency-high"
  | "urgency-normal"
  | "urgency-info"
  | "expense-pending"
  | "expense-approved"
  | "expense-reimbursed"
  | "expense-flagged"
  | "expense-rejected"
  | "audit-finding-error"
  | "audit-finding-warn"
  | "audit-finding-info"
  | "strategy-active"
  | "strategy-paused"
  | "strategy-draft"
  | "strategy-stopped"
  | "strategy-archived";

const TONE_CLASS: Record<StatusTone, string> = {
  "urgency-critical":
    "border-destructive/50 bg-destructive/15 text-destructive dark:text-destructive-foreground",
  "urgency-high": "border-amber-500/50 bg-amber-500/15 text-amber-950 dark:text-amber-100",
  "urgency-normal": "border-border bg-muted/70 text-foreground",
  "urgency-info": "border-sky-500/40 bg-sky-500/10 text-sky-950 dark:text-sky-100",
  "expense-pending": "border-amber-500/40 bg-amber-500/10 text-amber-900 dark:text-amber-100",
  "expense-approved": "border-emerald-500/40 bg-emerald-500/10 text-emerald-900 dark:text-emerald-100",
  "expense-reimbursed": "border-emerald-600/40 bg-emerald-600/10 text-emerald-950 dark:text-emerald-50",
  "expense-flagged": "border-orange-500/40 bg-orange-500/10 text-orange-950 dark:text-orange-100",
  "expense-rejected": "border-destructive/40 bg-destructive/10 text-destructive",
  "audit-finding-error": "border-destructive/50 bg-destructive/15 text-destructive",
  "audit-finding-warn": "border-amber-500/50 bg-amber-500/15 text-amber-950 dark:text-amber-100",
  "audit-finding-info": "border-muted-foreground/40 bg-muted/50 text-muted-foreground",
  "strategy-active": "border-emerald-500/40 bg-emerald-500/10 text-emerald-800 dark:text-emerald-200",
  "strategy-paused": "border-amber-500/40 bg-amber-500/10 text-amber-900 dark:text-amber-100",
  "strategy-draft": "border-border bg-muted/60 text-muted-foreground",
  "strategy-stopped": "border-destructive/40 bg-destructive/10 text-destructive",
  "strategy-archived": "border-destructive/40 bg-destructive/10 text-destructive",
};

export type StatusBadgeProps = {
  tone: StatusTone;
  children: React.ReactNode;
  className?: string;
};

export function StatusBadge({ tone, children, className }: StatusBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md border px-2.5 py-0.5 text-xs font-medium",
        TONE_CLASS[tone],
        className,
      )}
      role="status"
    >
      {children}
    </span>
  );
}
