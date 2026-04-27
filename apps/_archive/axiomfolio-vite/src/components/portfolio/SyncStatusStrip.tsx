import * as React from "react";
import * as Popover from "@radix-ui/react-popover";
import { ChevronDown, Loader2, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { usePortfolioAccounts, usePortfolioSync } from "@/hooks/usePortfolio";
import { cn } from "@/lib/utils";
import { semanticTextColorClass } from "@/lib/semantic-text-color";
import { brokerAccountStableReactKey, timeAgo } from "@/utils/portfolio";

const STALE_HOURS = 6;
const STALE_MS = STALE_HOURS * 60 * 60 * 1000;

export type SyncHealthKind = "healthy" | "stale" | "failed";

type AccountListRow = {
  id: number;
  broker: string;
  account_number: string;
  last_successful_sync?: string | null;
  sync_status?: string | null;
  sync_error_message?: string | null;
};

function parseAccountRows(data: unknown): AccountListRow[] {
  if (!Array.isArray(data)) return [];
  return data
    .filter((a) => a != null && typeof a === "object" && Number.isFinite((a as { id?: number }).id))
    .map((raw) => {
      const a = raw as AccountListRow;
      return {
        id: a.id,
        broker: String(a.broker ?? "Unknown"),
        account_number: String(a.account_number ?? ""),
        last_successful_sync: a.last_successful_sync,
        sync_status: a.sync_status,
        sync_error_message: a.sync_error_message,
      };
    });
}

function isRowFailed(a: AccountListRow): boolean {
  if (!a.last_successful_sync) return true;
  const s = (a.sync_status ?? "").toLowerCase();
  return s === "error" || s === "failed";
}

function ageMs(iso: string | null | undefined): number {
  if (!iso) return Number.POSITIVE_INFINITY;
  const t = new Date(iso).getTime();
  if (!Number.isFinite(t)) return Number.POSITIVE_INFINITY;
  return Date.now() - t;
}

function isRowStale(a: AccountListRow, age: number): boolean {
  if (isRowFailed(a)) return false;
  return age > STALE_MS;
}

function rowDotClass(a: AccountListRow, age: number): string {
  if (isRowFailed(a)) return "bg-[rgb(var(--status-danger)/1)]";
  if (isRowStale(a, age)) return "bg-[rgb(var(--status-warning)/1)]";
  return "bg-[rgb(var(--status-success)/1)]";
}

function rowStatusLabel(a: AccountListRow, age: number): string {
  if (isRowFailed(a)) {
    if (a.sync_error_message) return a.sync_error_message;
    if ((a.sync_status ?? "").toLowerCase() === "error") return "Sync error";
    return "Not synced";
  }
  if (isRowStale(a, age)) return "Sync stale";
  return "Synced";
}

function summarizeAccounts(rows: AccountListRow[]): {
  kind: SyncHealthKind;
  summary: string;
  liveMessage: string;
} {
  const failed = rows.filter(isRowFailed);
  if (failed.length > 0) {
    let worst: AccountListRow | null = null;
    let worstAge = -1;
    for (const a of failed) {
      const m = ageMs(a.last_successful_sync);
      if (m < Number.POSITIVE_INFINITY && m > worstAge) {
        worstAge = m;
        worst = a;
      }
    }
    const n = failed.length;
    const countLabel = n === 1 ? "1 account sync failed" : `${n} accounts sync failed`;
    const summary =
      worst != null && worst.last_successful_sync
        ? `${countLabel} · ${timeAgo(worst.last_successful_sync)}`
        : countLabel;
    return {
      kind: "failed",
      summary,
      liveMessage: `Sync status: ${n} account${n === 1 ? "" : "s"} need attention`,
    };
  }
  const ages = rows.map((a) => ({ a, ms: ageMs(a.last_successful_sync) }));
  const max = ages.reduce((w, x) => (x.ms > w.ms ? x : w), ages[0]!);
  if (max.ms > STALE_MS) {
    const b = (max.a.broker || "").toUpperCase() || "Account";
    const part = timeAgo(max.a.last_successful_sync);
    return {
      kind: "stale",
      summary: `${b} stale · ${part}`,
      liveMessage: `Sync status: ${b} is stale`,
    };
  }
  const min = ages.reduce((w, x) => (x.ms < w.ms ? x : w), ages[0]!);
  return {
    kind: "healthy",
    summary: `All synced · ${timeAgo(min.a.last_successful_sync)}`,
    liveMessage: "All accounts synced",
  };
}

const summaryDotByKind: Record<SyncHealthKind, string> = {
  healthy: "bg-[rgb(var(--status-success)/1)]",
  stale: "bg-[rgb(var(--status-warning)/1)]",
  failed: "bg-[rgb(var(--status-danger)/1)]",
};

export interface SyncStatusStripProps {
  className?: string;
  showSyncButton?: boolean;
}

export function SyncStatusStrip({ className, showSyncButton = true }: SyncStatusStripProps) {
  const accountsQuery = usePortfolioAccounts();
  const syncMutation = usePortfolioSync();

  const refetch = () => {
    void accountsQuery.refetch();
  };

  if (accountsQuery.isPending) {
    return (
      <div
        className={cn("flex w-full min-w-0 max-w-2xl items-center gap-2", className)}
        data-testid="sync-status-strip"
        data-state="loading"
        aria-busy
      >
        <Skeleton className="h-8 flex-1 rounded-md" />
        {showSyncButton ? <Skeleton className="h-8 w-20 shrink-0 rounded-md" /> : null}
      </div>
    );
  }

  if (accountsQuery.isError) {
    return (
      <div
        className={cn("flex flex-wrap items-center gap-2", className)}
        data-testid="sync-status-strip"
        data-state="error"
      >
        <span className={cn("text-sm", semanticTextColorClass("status.danger"))}>
          Sync status unavailable
        </span>
        <Button type="button" size="sm" variant="outline" onClick={refetch}>
          Retry
        </Button>
      </div>
    );
  }

  const rows = parseAccountRows(accountsQuery.data);
  if (rows.length === 0) {
    return null;
  }

  const { kind, summary, liveMessage } = summarizeAccounts(rows);
  const pending = syncMutation.isPending;
  const announce = pending ? "Syncing all brokers" : liveMessage;

  return (
    <div
      className={cn("flex w-full min-w-0 max-w-2xl flex-wrap items-center gap-2", className)}
      data-testid="sync-status-strip"
      data-state="ready"
      data-overall={kind}
    >
      <div aria-live="polite" aria-atomic="true" className="sr-only">
        {announce}
      </div>

      <div className="flex min-w-0 flex-1 items-center gap-2 sm:flex-initial">
        <Popover.Root>
          <Popover.Trigger asChild>
            <button
              type="button"
              className={cn(
                "inline-flex max-w-full min-w-0 items-center gap-2 rounded-md border border-border bg-muted/50 px-3 py-1.5 text-left text-sm shadow-xs",
                "cursor-pointer transition-colors outline-none focus-visible:ring-2 focus-visible:ring-ring",
              )}
              aria-label="Account sync details, open menu"
            >
              {pending ? (
                <Loader2 className="size-2.5 shrink-0 animate-spin text-muted-foreground" aria-hidden />
              ) : (
                <span
                  className={cn("size-1.5 shrink-0 rounded-full", summaryDotByKind[kind])}
                  aria-hidden
                />
              )}
              <span className="min-w-0 flex-1 truncate text-muted-foreground">
                <span className="tabular-nums text-foreground">{summary}</span>
              </span>
              <ChevronDown className="size-3.5 shrink-0 text-muted-foreground" aria-hidden />
            </button>
          </Popover.Trigger>
          <Popover.Portal>
            <Popover.Content
              side="bottom"
              align="end"
              sideOffset={6}
              className="z-50 w-80 max-w-[calc(100vw-1.5rem)] rounded-md border border-border bg-popover p-3 text-popover-foreground shadow-md outline-none data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95"
            >
              <p className="mb-2 text-xs font-semibold text-muted-foreground">Accounts</p>
              <ul className="flex flex-col gap-2">
                {rows.map((a) => {
                  const ms = ageMs(a.last_successful_sync);
                  const key = brokerAccountStableReactKey(a.broker, a.account_number, a.id);
                  const last4 = a.account_number.length >= 4 ? a.account_number.slice(-4) : a.account_number;
                  return (
                    <li
                      key={key}
                      className="flex flex-col gap-0.5 border-b border-border/60 pb-2 last:border-0 last:pb-0"
                    >
                      <div className="flex items-center gap-2">
                        <span
                          className={cn("size-1.5 shrink-0 rounded-full", rowDotClass(a, ms))}
                          aria-hidden
                        />
                        <span className="text-sm text-foreground">
                          {(a.broker || "").toUpperCase()} ···{last4} ·{" "}
                          <span className="tabular-nums text-muted-foreground">
                            {a.last_successful_sync ? timeAgo(a.last_successful_sync) : "Never"}
                          </span>
                        </span>
                      </div>
                      <span
                        className={cn(
                          "pl-3.5 text-xs",
                          isRowFailed(a) ? semanticTextColorClass("status.danger") : "text-muted-foreground",
                        )}
                      >
                        {rowStatusLabel(a, ms)}
                      </span>
                    </li>
                  );
                })}
              </ul>
            </Popover.Content>
          </Popover.Portal>
        </Popover.Root>
      </div>

      {showSyncButton ? (
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="shrink-0 gap-1.5"
          onClick={() => syncMutation.mutate()}
          disabled={pending}
          aria-busy={pending}
        >
          {pending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <RefreshCw className="size-4" aria-hidden />}
          Sync
        </Button>
      ) : null}
    </div>
  );
}

export default SyncStatusStrip;
