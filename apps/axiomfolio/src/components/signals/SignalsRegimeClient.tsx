"use client";

import { AlertTriangle, Gauge } from "lucide-react";

import RegimeBanner from "@/components/market/RegimeBanner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { REGIME_HEX } from "@/constants/chart";
import { useRegimeHistory } from "@/hooks/useRegimeHistory";
import type { RegimeHistoryRow } from "@/types/signals";

const REGIME_LABELS: Record<string, string> = {
  R1: "Bull",
  R2: "Bull Extended",
  R3: "Chop",
  R4: "Bear Rally",
  R5: "Bear",
};

function formatDay(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "2-digit" });
}

function HistoryRow({ row }: { row: RegimeHistoryRow }) {
  const regimeHex = row.regime_state ? REGIME_HEX[row.regime_state] : undefined;
  const label = row.regime_state ? REGIME_LABELS[row.regime_state] ?? row.regime_state : "—";
  const score =
    typeof row.composite_score === "number" ? row.composite_score.toFixed(1) : "—";
  return (
    <div className="flex items-center justify-between border-b border-border py-2 last:border-b-0">
      <div className="flex items-center gap-3">
        {regimeHex ? (
          <span
            className="inline-block size-2.5 shrink-0 rounded-full"
            style={{ backgroundColor: regimeHex }}
            aria-hidden
          />
        ) : (
          <span
            className="inline-block size-2.5 shrink-0 rounded-full bg-muted-foreground"
            aria-hidden
          />
        )}
        <span className="font-mono text-xs text-muted-foreground">{formatDay(row.as_of_date)}</span>
      </div>
      <div className="flex items-center gap-3 text-xs">
        <span className="font-semibold tabular-nums">{row.regime_state ?? "—"}</span>
        <span className="text-muted-foreground">{label}</span>
        <span className="tabular-nums text-muted-foreground">Score {score}</span>
      </div>
    </div>
  );
}

export function SignalsRegimeClient() {
  const history = useRegimeHistory(60);

  return (
    <div className="mx-auto max-w-3xl space-y-4 p-4">
      <header className="space-y-1">
        <div className="flex items-center gap-2">
          <Gauge className="size-5 text-primary" aria-hidden />
          <h1 className="font-heading text-xl font-semibold tracking-tight">Market Regime</h1>
        </div>
        <p className="text-sm text-muted-foreground">
          The Regime Engine composites six breadth and volatility inputs (VIX spot, VIX3M/VIX,
          VVIX/VIX, NH−NL, % above 200D, % above 50D) into a single R1–R5 state that governs
          position sizing and long exposure.
        </p>
      </header>

      <RegimeBanner />

      <section className="space-y-2">
        <h2 className="text-sm font-semibold">History</h2>
        {history.isPending ? (
          <div className="space-y-2" data-testid="regime-history-loading">
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
          </div>
        ) : history.isError ? (
          <Card
            className="border-destructive/40 bg-destructive/5"
            data-testid="regime-history-error"
          >
            <CardHeader className="flex flex-row items-start gap-3 pb-2">
              <AlertTriangle className="mt-0.5 size-5 text-destructive" aria-hidden />
              <div className="space-y-2">
                <p className="font-medium text-foreground">Unable to load regime history</p>
                <p className="text-sm text-muted-foreground">
                  {history.error instanceof Error
                    ? history.error.message
                    : "Try again in a moment."}
                </p>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() => void history.refetch()}
                >
                  Retry
                </Button>
              </div>
            </CardHeader>
          </Card>
        ) : !history.data || history.data.history.length === 0 ? (
          <Card data-testid="regime-history-empty">
            <CardContent className="py-6 text-center text-sm text-muted-foreground">
              No regime history computed yet. The Regime Engine backfills on the next scheduled
              run.
            </CardContent>
          </Card>
        ) : (
          <Card data-testid="regime-history-list">
            <CardContent className="p-4">
              {[...history.data.history].reverse().map((row, idx) => (
                <HistoryRow
                  key={`${row.as_of_date ?? "null"}-${idx}`}
                  row={row}
                />
              ))}
            </CardContent>
          </Card>
        )}
      </section>
    </div>
  );
}
