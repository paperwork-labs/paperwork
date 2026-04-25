"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Info, ShieldCheck } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import api from "@/services/api";

type ShadowStatus =
  | "intended"
  | "would_deny_by_risk_gate"
  | "executed_at_simulation_time"
  | "marked_to_market"
  | "closed";

interface ShadowRow {
  id: number;
  user_id: number;
  account_id: string | null;
  symbol: string;
  side: string;
  order_type: string;
  qty: string | null;
  limit_price: string | null;
  tif: string | null;
  status: ShadowStatus;
  risk_gate_verdict: Record<string, unknown> | null;
  intended_fill_price: string | null;
  intended_fill_at: string | null;
  simulated_pnl: string | null;
  simulated_pnl_as_of: string | null;
  last_mark_price: string | null;
  source_order_id: number | null;
  error_message: string | null;
  created_at: string | null;
}

interface ShadowListResponse {
  items: ShadowRow[];
  total: number;
  limit: number;
  offset: number;
  user_id: number;
}

interface ShadowPnlSummary {
  user_id: number;
  total_orders: number;
  by_status: Record<string, number>;
  marked: number;
  unmarked: number;
  total_simulated_pnl: string;
}

function fmtMoney(raw: string | null | undefined): string {
  if (raw == null || raw === "") return "—";
  const n = Number(raw);
  if (!Number.isFinite(n)) return "—";
  return n.toLocaleString(undefined, {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  });
}

function fmtQty(raw: string | null | undefined): string {
  if (raw == null || raw === "") return "—";
  const n = Number(raw);
  if (!Number.isFinite(n)) return "—";
  return n.toLocaleString(undefined, { maximumFractionDigits: 4 });
}

function statusBadgeClass(status: ShadowStatus): string {
  switch (status) {
    case "executed_at_simulation_time":
      return "bg-primary/15 text-primary";
    case "marked_to_market":
      return "bg-accent text-accent-foreground";
    case "would_deny_by_risk_gate":
      return "bg-destructive/15 text-destructive";
    case "closed":
      return "bg-muted text-muted-foreground";
    default:
      return "bg-muted text-muted-foreground";
  }
}

function statusLabel(status: ShadowStatus): string {
  switch (status) {
    case "intended":
      return "Intended";
    case "would_deny_by_risk_gate":
      return "Risk-gate would deny";
    case "executed_at_simulation_time":
      return "Simulated fill";
    case "marked_to_market":
      return "Marked to market";
    case "closed":
      return "Closed";
    default:
      return status;
  }
}

function pnlToneClass(raw: string | null | undefined): string {
  if (raw == null || raw === "") return "";
  const n = Number(raw);
  if (!Number.isFinite(n) || n === 0) return "";
  return n > 0 ? "text-primary" : "text-destructive";
}

export function ShadowTradesClient() {
  const listQuery = useQuery<ShadowListResponse, Error>({
    queryKey: ["shadow-trades", "list"],
    queryFn: async () => {
      const res = await api.get<ShadowListResponse>("/shadow-trades?limit=100&offset=0");
      return res.data;
    },
  });

  const summaryQuery = useQuery<ShadowPnlSummary, Error>({
    queryKey: ["shadow-trades", "pnl-summary"],
    queryFn: async () => {
      const res = await api.get<ShadowPnlSummary>("/shadow-trades/pnl-summary");
      return res.data;
    },
  });

  if (listQuery.isPending) {
    return (
      <div
        className="mx-auto max-w-5xl space-y-3 p-4"
        data-testid="shadow-trades-loading"
      >
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  if (listQuery.isError) {
    return (
      <div className="mx-auto max-w-5xl p-4" data-testid="shadow-trades-error">
        <Alert variant="destructive">
          <AlertTriangle className="size-4" aria-hidden />
          <AlertTitle>Unable to load shadow trades</AlertTitle>
          <AlertDescription>
            We couldn&apos;t reach the shadow-trades service. Refresh to try again;
            if the problem persists, check the admin health panel.
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  const data = listQuery.data;
  const items = data?.items ?? [];
  const summary = summaryQuery.data;

  return (
    <TooltipProvider>
      <div className="mx-auto max-w-5xl space-y-4 p-4" data-testid="shadow-trades-data">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="font-heading text-xl font-semibold tracking-tight">
              Shadow (paper) trades
            </h1>
            <p className="text-sm text-muted-foreground">
              Every order submitted while shadow mode is on is recorded here
              instead of being routed to a broker. P&amp;L is marked to market
              every 15 minutes using the latest market snapshot.
            </p>
          </div>
          <Tooltip>
            <TooltipTrigger asChild>
              <span>
                <Button
                  type="button"
                  variant="outline"
                  disabled
                  aria-disabled="true"
                  data-testid="promote-to-live"
                >
                  <ShieldCheck className="mr-1 size-4" aria-hidden />
                  Promote to live
                </Button>
              </span>
            </TooltipTrigger>
            <TooltipContent>
              Live trading disabled — contact admin
            </TooltipContent>
          </Tooltip>
        </div>

        <Alert>
          <Info className="size-4" aria-hidden />
          <AlertTitle>Paper trading is on</AlertTitle>
          <AlertDescription>
            Orders submitted through the platform are intercepted by the
            shadow recorder. No real broker calls are made while this mode is
            active.
          </AlertDescription>
        </Alert>

        <Card data-testid="shadow-pnl-summary">
          <CardHeader className="pb-2">
            <p className="text-xs uppercase text-muted-foreground">
              Simulated P&amp;L summary
            </p>
          </CardHeader>
          <CardContent>
            {summaryQuery.isPending ? (
              <div
                className="grid grid-cols-2 gap-3 sm:grid-cols-4"
                data-testid="shadow-pnl-summary-loading"
              >
                {[0, 1, 2, 3].map((i) => (
                  <Skeleton key={i} className="h-12 w-full" />
                ))}
              </div>
            ) : summaryQuery.isError ? (
              <Alert
                variant="destructive"
                data-testid="shadow-pnl-summary-error"
              >
                <AlertTriangle className="size-4" aria-hidden />
                <AlertTitle>Summary unavailable</AlertTitle>
                <AlertDescription>
                  Could not load the simulated P&amp;L aggregates.
                </AlertDescription>
              </Alert>
            ) : summary && summary.total_orders > 0 ? (
              <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <div>
                  <dt className="text-xs text-muted-foreground">Total orders</dt>
                  <dd className="font-heading text-xl tabular-nums">
                    {summary.total_orders}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-muted-foreground">Marked</dt>
                  <dd className="font-heading text-xl tabular-nums">
                    {summary.marked}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-muted-foreground">Awaiting mark</dt>
                  <dd className="font-heading text-xl tabular-nums">
                    {summary.unmarked}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-muted-foreground">Simulated P&amp;L</dt>
                  <dd
                    className={cn(
                      "font-heading text-xl tabular-nums",
                      pnlToneClass(summary.total_simulated_pnl),
                    )}
                  >
                    {fmtMoney(summary.total_simulated_pnl)}
                  </dd>
                </div>
              </dl>
            ) : (
              <p
                className="text-sm text-muted-foreground"
                data-testid="shadow-pnl-summary-empty"
              >
                No simulated trades yet.
              </p>
            )}
          </CardContent>
        </Card>

        {items.length === 0 ? (
          <Card data-testid="shadow-trades-empty">
            <CardContent className="space-y-2 py-8 text-center text-sm text-muted-foreground">
              <p>No shadow orders yet.</p>
              <p className="text-xs">
                Submit any order while shadow mode is on (default) and it will
                land here instead of going to a broker.
              </p>
            </CardContent>
          </Card>
        ) : (
          <Card>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-muted/40 text-xs uppercase text-muted-foreground">
                    <tr>
                      <th className="px-3 py-2 text-left">Symbol</th>
                      <th className="px-3 py-2 text-left">Side</th>
                      <th className="px-3 py-2 text-right">Qty</th>
                      <th className="px-3 py-2 text-right">Fill price</th>
                      <th className="px-3 py-2 text-right">Mark</th>
                      <th className="px-3 py-2 text-right">P&amp;L</th>
                      <th className="px-3 py-2 text-left">Status</th>
                      <th className="px-3 py-2 text-left">Created</th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((row) => (
                      <tr
                        key={row.id}
                        className="border-t border-border"
                        data-testid={`shadow-row-${row.id}`}
                      >
                        <td className="px-3 py-2 font-mono">{row.symbol}</td>
                        <td className="px-3 py-2 uppercase">{row.side}</td>
                        <td className="px-3 py-2 text-right tabular-nums">
                          {fmtQty(row.qty)}
                        </td>
                        <td className="px-3 py-2 text-right tabular-nums">
                          {fmtMoney(row.intended_fill_price)}
                        </td>
                        <td className="px-3 py-2 text-right tabular-nums">
                          {fmtMoney(row.last_mark_price)}
                        </td>
                        <td
                          className={cn(
                            "px-3 py-2 text-right tabular-nums",
                            pnlToneClass(row.simulated_pnl),
                          )}
                        >
                          {fmtMoney(row.simulated_pnl)}
                        </td>
                        <td className="px-3 py-2">
                          <Badge className={cn(statusBadgeClass(row.status))}>
                            {statusLabel(row.status)}
                          </Badge>
                        </td>
                        <td className="px-3 py-2 text-xs text-muted-foreground">
                          {row.created_at
                            ? new Date(row.created_at).toLocaleString()
                            : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </TooltipProvider>
  );
}
