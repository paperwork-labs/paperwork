"use client";

import { AlertTriangle, Sparkles, TrendingUp } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useCandidatesToday } from "@/hooks/useCandidatesToday";
import { actionChipClass } from "@/lib/picks";
import { cn } from "@/lib/utils";
import type { CandidateRow } from "@/types/signals";

function formatDecimal(raw: string | null, fractionDigits: number = 1): string {
  if (raw == null) return "—";
  const n = Number(raw);
  if (!Number.isFinite(n)) return "—";
  return n.toFixed(fractionDigits);
}

function formatTimestamp(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString();
}

function CandidateCard({ row }: { row: CandidateRow }) {
  const regimeMultiplier =
    row.score && typeof row.score.regime_multiplier === "number"
      ? row.score.regime_multiplier
      : null;
  const totalScore =
    row.score && typeof row.score.total_score === "number" ? row.score.total_score : null;

  return (
    <Card>
      <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-2 pb-2">
        <div>
          <p className="font-mono text-xl font-semibold">{row.ticker}</p>
          <p className="text-xs text-muted-foreground">
            {row.generator_name ?? "system"}
            {row.generator_version ? ` · v${row.generator_version}` : ""}
            {row.generated_at ? ` · ${formatTimestamp(row.generated_at)}` : ""}
          </p>
        </div>
        <div className="flex flex-col items-end gap-1">
          <Badge className={cn("uppercase", actionChipClass(row.action))}>{row.action}</Badge>
          {row.pick_quality_score != null ? (
            <span className="text-xs text-muted-foreground">
              Quality {formatDecimal(row.pick_quality_score, 1)}
            </span>
          ) : null}
        </div>
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        <p className="whitespace-pre-wrap text-foreground">{row.thesis ?? "—"}</p>
        <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
          {row.generator_score != null ? (
            <span>Generator score {formatDecimal(row.generator_score, 2)}</span>
          ) : null}
          {totalScore != null ? <span>Composite {totalScore.toFixed(1)}</span> : null}
          {regimeMultiplier != null ? (
            <span>Regime multiplier {regimeMultiplier.toFixed(2)}×</span>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}

export function SignalsCandidatesClient() {
  const q = useCandidatesToday({ limit: 50 });

  return (
    <div className="mx-auto max-w-3xl space-y-4 p-4">
      <header className="space-y-1">
        <div className="flex items-center gap-2">
          <Sparkles className="size-5 text-primary" aria-hidden />
          <h1 className="font-heading text-xl font-semibold tracking-tight">Candidates</h1>
        </div>
        <p className="text-sm text-muted-foreground">
          System-generated trade candidates from today&apos;s scan, ranked by pick-quality score.
        </p>
      </header>

      {q.isPending ? (
        <div className="space-y-3" data-testid="candidates-loading">
          <Skeleton className="h-28 w-full" />
          <Skeleton className="h-28 w-full" />
          <Skeleton className="h-28 w-full" />
        </div>
      ) : q.isError ? (
        <Card
          className="border-destructive/40 bg-destructive/5"
          data-testid="candidates-error"
        >
          <CardHeader className="flex flex-row items-start gap-3 pb-2">
            <AlertTriangle className="mt-0.5 size-5 text-destructive" aria-hidden />
            <div className="space-y-2">
              <p className="font-medium text-foreground">Unable to load candidates</p>
              <p className="text-sm text-muted-foreground">
                {q.error instanceof Error ? q.error.message : "Try again in a moment."}
              </p>
              <Button type="button" size="sm" variant="outline" onClick={() => void q.refetch()}>
                Retry
              </Button>
            </div>
          </CardHeader>
        </Card>
      ) : !q.data || q.data.items.length === 0 ? (
        <Card data-testid="candidates-empty">
          <CardHeader className="flex flex-row items-start gap-3 pb-2">
            <TrendingUp className="mt-0.5 size-5 text-muted-foreground" aria-hidden />
            <div className="space-y-2">
              <p className="font-medium text-foreground">The scanner is resting — nothing cleared the bar today.</p>
              <p className="text-sm text-muted-foreground">
                Fresh candidates usually land right after the close (around 4:15 PM ET) once
                the daily run finishes. If you are early, check back then — or open Strategies
                to see how new names get picked.
              </p>
              <p className="text-xs text-muted-foreground/90">Tip: Most feeds refresh after market close (16:15 ET).</p>
              <Button asChild size="sm" variant="outline">
                <Link href="/lab/strategies">Browse strategies</Link>
              </Button>
            </div>
          </CardHeader>
        </Card>
      ) : (
        <div className="space-y-3" data-testid="candidates-list">
          <p className="text-xs text-muted-foreground">
            Showing {q.data.items.length} of {q.data.total}
          </p>
          {q.data.items.map((row) => (
            <CandidateCard key={row.id} row={row} />
          ))}
        </div>
      )}
    </div>
  );
}
