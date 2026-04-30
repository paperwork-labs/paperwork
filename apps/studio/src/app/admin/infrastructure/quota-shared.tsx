"use client";

import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { AlertTriangle, Loader2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, Skeleton } from "@paperwork-labs/ui";
import type { BrainEnvelope } from "@/lib/quota-monitor-types";
import {
  isStaleIso,
  thresholdToneFromPct,
  toneAccentClass,
  type ThresholdTone,
} from "@/lib/quota-monitor-format";

/** Vendor cron cadence differs — stale banner thresholds per quota panel (minutes). */
export const QUOTA_CRON_STALE_THRESHOLD_MINUTES = {
  /** GH Actions org billing snapshot — daily cron */
  githubActions: 1500,
  vercel: 420,
  render: 420,
  default: 60,
} as const;

export function formatStaleAgeLabel(minutes: number): string {
  if (minutes >= 60 && minutes % 60 === 0) {
    const h = minutes / 60;
    return `${h} hour${h === 1 ? "" : "s"}`;
  }
  return `${minutes} minutes`;
}

export async function fetchBrainEnvelope<T>(
  path: string,
): Promise<{ data: T | null; httpStatus: number; error: string | null }> {
  try {
    const res = await fetch(path, { cache: "no-store" });
    const raw = await res.json();
    const body = raw as BrainEnvelope<T>;
    if (!res.ok) {
      const msg =
        typeof body?.error === "string"
          ? body.error
          : typeof (raw as { message?: unknown })?.message === "string"
            ? ((raw as { message: string }).message as string)
            : `Brain returned HTTP ${res.status}`;
      return { data: null, httpStatus: res.status, error: msg };
    }
    if (!body.success) {
      const msg =
        typeof body?.error === "string" ? body.error : `Brain returned unsuccessful envelope`;
      return { data: body.data ?? null, httpStatus: res.status, error: msg };
    }
    return { data: body.data ?? null, httpStatus: res.status, error: null };
  } catch (e) {
    return {
      data: null,
      httpStatus: 0,
      error: e instanceof Error ? e.message : "Failed to fetch quota snapshot",
    };
  }
}

export function quotaBar(pct: number | null | undefined, tone: ThresholdTone) {
  const p = pct === null || pct === undefined || !Number.isFinite(pct) ? 0 : Math.min(100, pct);
  const { bar } = toneAccentClass(tone);
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-zinc-800">
      <div className={`h-full rounded-full motion-safe:transition-all ${bar}`} style={{ width: `${p}%` }} />
    </div>
  );
}

type QuotaPanelFrameProps = {
  testId: string;
  icon: LucideIcon;
  title: string;
  subtitle: string;
  brainHint: string;
  loading: boolean;
  error: string | null;
  recordedIso: string | null | undefined;
  worstPctGuess: number;
  headline: string;
  /** Minutes before snapshot is treated as stale (cron cadence varies by vendor). */
  staleThresholdMinutes?: number;
  children?: ReactNode;
};

/** Shared chrome: matches infrastructure card tone; founder scan = headline + left accent. */
export function QuotaPanelFrame({
  testId,
  icon: Icon,
  title,
  subtitle,
  brainHint,
  loading,
  error,
  recordedIso,
  worstPctGuess,
  headline,
  staleThresholdMinutes = QUOTA_CRON_STALE_THRESHOLD_MINUTES.default,
  children,
}: QuotaPanelFrameProps) {
  const glanceTone = thresholdToneFromPct(worstPctGuess);
  const { bg, text, dot } = toneAccentClass(glanceTone);

  return (
    <Card
      className="border-zinc-800 bg-zinc-900/60"
      data-testid={testId}
      aria-label={`${title} quota snapshot`}
    >
      <div className={`h-1 w-full rounded-t-xl ${bg}`} />
      <CardHeader className="space-y-1 pb-2">
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2">
            <Icon className="h-4 w-4 text-zinc-500" aria-hidden />
            <CardTitle className="text-base font-medium tracking-tight text-zinc-100">{title}</CardTitle>
          </div>
          <span className={`mt-1 h-3 w-3 shrink-0 rounded-full ${dot}`} title={`${glanceTone} band`} />
        </div>
        <p className="text-xs text-zinc-500">{subtitle}</p>
        <p className="font-mono text-[10px] text-zinc-600">{brainHint}</p>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        {loading ? (
          <div className="space-y-2" aria-busy aria-label="Loading quota data">
            <Skeleton className="h-10 w-full bg-zinc-800" />
            <Skeleton className="h-24 w-full bg-zinc-800" />
            <Skeleton className="h-24 w-full bg-zinc-800" />
            <Loader2 className="h-4 w-4 motion-safe:animate-spin text-zinc-600" aria-hidden />
          </div>
        ) : error ? (
          <p className="rounded-lg border border-rose-900/40 bg-rose-950/30 px-3 py-2 text-xs text-rose-200">
            {error}
          </p>
        ) : (
          <>
            {headline.trim() ? (
              <div className="rounded-lg border border-zinc-800 bg-zinc-950/60 px-3 py-2">
                <p className={`text-sm font-medium tabular-nums ${text}`}>{headline}</p>
              </div>
            ) : null}
            {recordedIso ? (
              <p className="text-[10px] text-zinc-500">
                Last checked: <span className="font-mono text-zinc-400">{recordedIso}</span>
              </p>
            ) : null}
            {isStaleIso(recordedIso ?? null, staleThresholdMinutes) && recordedIso ? (
              <p className="flex items-start gap-1.5 rounded-md border border-amber-900/35 bg-amber-950/25 px-2 py-1.5 text-xs text-amber-200">
                <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
                Snapshot older than {formatStaleAgeLabel(staleThresholdMinutes)} — schedulers may be
                stuck. Verified at <span className="font-mono">{recordedIso}</span>.
              </p>
            ) : null}
            {children}
          </>
        )}
      </CardContent>
    </Card>
  );
}
