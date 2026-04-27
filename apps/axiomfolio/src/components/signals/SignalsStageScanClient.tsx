"use client";

import { AlertTriangle, Compass, TrendingUp } from "lucide-react";
import Link from "next/link";
import * as React from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useSnapshotTable } from "@/hooks/useSnapshotTable";
import { actionChipClass } from "@/lib/picks";
import { cn } from "@/lib/utils";
import type { MarketSnapshotRow } from "@/types/market";

type StagePreset = {
  key: string;
  label: string;
  description: string;
  filter_stage: string;
};

const STAGE_PRESETS: StagePreset[] = [
  {
    key: "2A",
    label: "Stage 2A — Early trend",
    description: "Fresh breakouts above SMA150. Base count typically 1–2.",
    filter_stage: "2A",
  },
  {
    key: "2B",
    label: "Stage 2B — Established trend",
    description: "Above all MAs, RS confirming. Base count 2–3, best reward/risk.",
    filter_stage: "2B",
  },
  {
    key: "2C",
    label: "Stage 2C — Late trend",
    description: "Still uptrending but extended; favour reductions over new entries.",
    filter_stage: "2C",
  },
];

function formatPrice(v: unknown): string {
  if (typeof v !== "number" || !Number.isFinite(v)) return "—";
  return v.toFixed(2);
}

function formatPct(v: unknown, digits: number = 1): string {
  if (typeof v !== "number" || !Number.isFinite(v)) return "—";
  return `${v.toFixed(digits)}%`;
}

function ScanRow({ row }: { row: MarketSnapshotRow }) {
  const rs = typeof row.rs_mansfield_pct === "number" ? row.rs_mansfield_pct : null;
  const perf20d = typeof row.perf_20d === "number" ? row.perf_20d : null;
  const stageDays =
    typeof row.current_stage_days === "number" ? row.current_stage_days : null;
  const stage = row.stage_label ?? "—";
  const action = row.action_label ?? "WATCH";

  return (
    <Link
      href={`/holding/${encodeURIComponent(row.symbol)}`}
      className="block border-b border-border px-4 py-3 transition-colors last:border-b-0 hover:bg-accent/40"
    >
      <div className="flex items-center justify-between gap-3">
        <div className="flex min-w-0 flex-col">
          <span className="font-mono text-sm font-semibold">{row.symbol}</span>
          <span className="truncate text-xs text-muted-foreground">
            {row.sector ?? "—"}
            {row.industry ? ` · ${row.industry}` : ""}
          </span>
        </div>
        <div className="flex items-center gap-4 text-xs">
          <div className="flex flex-col items-end">
            <span className="text-[10px] text-muted-foreground">Stage</span>
            <span className="font-semibold">{stage}</span>
          </div>
          <div className="flex flex-col items-end">
            <span className="text-[10px] text-muted-foreground">Days</span>
            <span className="font-semibold tabular-nums">
              {stageDays != null ? stageDays : "—"}
            </span>
          </div>
          <div className="flex flex-col items-end">
            <span className="text-[10px] text-muted-foreground">Price</span>
            <span className="font-semibold tabular-nums">{formatPrice(row.current_price)}</span>
          </div>
          <div className="flex flex-col items-end">
            <span className="text-[10px] text-muted-foreground">20D</span>
            <span className="font-semibold tabular-nums">{formatPct(perf20d)}</span>
          </div>
          <div className="flex flex-col items-end">
            <span className="text-[10px] text-muted-foreground">RS</span>
            <span className="font-semibold tabular-nums">{formatPct(rs)}</span>
          </div>
          <Badge className={cn("uppercase", actionChipClass(action))}>{action}</Badge>
        </div>
      </div>
    </Link>
  );
}

export function SignalsStageScanClient() {
  const [activePreset, setActivePreset] = React.useState<StagePreset>(STAGE_PRESETS[1]);

  const q = useSnapshotTable({
    filter_stage: activePreset.filter_stage,
    sort_by: "rs_mansfield_pct",
    sort_dir: "desc",
    limit: 50,
  });

  return (
    <div className="mx-auto max-w-4xl space-y-4 p-4">
      <header className="space-y-1">
        <div className="flex items-center gap-2">
          <Compass className="size-5 text-primary" aria-hidden />
          <h1 className="font-heading text-xl font-semibold tracking-tight">Stage Scan</h1>
        </div>
        <p className="text-sm text-muted-foreground">
          Leaders by Weinstein stage, sorted by Mansfield relative strength. Switch stages to
          surface the setups most relevant to the current regime.
        </p>
      </header>

      <div className="flex flex-wrap gap-2" role="group" aria-label="Stage filter">
        {STAGE_PRESETS.map((preset) => {
          const isActive = preset.key === activePreset.key;
          return (
            <Button
              key={preset.key}
              type="button"
              size="sm"
              variant={isActive ? "default" : "outline"}
              onClick={() => setActivePreset(preset)}
              aria-pressed={isActive}
            >
              {preset.label}
            </Button>
          );
        })}
      </div>
      <p className="text-xs text-muted-foreground">{activePreset.description}</p>

      {q.isPending ? (
        <div className="space-y-2" data-testid="scan-loading">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
        </div>
      ) : q.isError ? (
        <Card className="border-destructive/40 bg-destructive/5" data-testid="scan-error">
          <CardHeader className="flex flex-row items-start gap-3 pb-2">
            <AlertTriangle className="mt-0.5 size-5 text-destructive" aria-hidden />
            <div className="space-y-2">
              <p className="font-medium text-foreground">Unable to load scan results</p>
              <p className="text-sm text-muted-foreground">
                {q.error instanceof Error ? q.error.message : "Try again in a moment."}
              </p>
              <Button type="button" size="sm" variant="outline" onClick={() => void q.refetch()}>
                Retry
              </Button>
            </div>
          </CardHeader>
        </Card>
      ) : !q.data || q.data.rows.length === 0 ? (
        <Card data-testid="scan-empty">
          <CardHeader className="flex flex-row items-start gap-3 pb-2">
            <TrendingUp className="mt-0.5 size-5 text-muted-foreground" aria-hidden />
            <div className="space-y-2">
              <p className="font-medium text-foreground">
                No symbols in {activePreset.label.toLowerCase()} right now
              </p>
              <p className="text-sm text-muted-foreground">
                Try a different stage, or review the full tracked universe for broader context.
              </p>
              <Button asChild size="sm" variant="outline">
                <Link href="/market/tracked">Open Tracked universe</Link>
              </Button>
            </div>
          </CardHeader>
        </Card>
      ) : (
        <Card data-testid="scan-list">
          <CardContent className="p-0">
            <div className="flex items-center justify-between border-b border-border px-4 py-2">
              <p className="text-xs text-muted-foreground">
                Showing {q.data.rows.length} of {q.data.total}
              </p>
              <Link
                href="/market/tracked"
                className="text-xs font-medium text-primary hover:underline"
              >
                Full scanner →
              </Link>
            </div>
            {q.data.rows.map((row) => (
              <ScanRow key={row.symbol} row={row} />
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
