"use client";

import { useEffect, useId, useMemo, useRef, useState } from "react";
import { TrendingDown, TrendingUp, Minus } from "lucide-react";

import type { OperatingScoreEntry, OperatingScoreResponse } from "@/types/operating-score";

import {
  OPERATING_SCORE_PILLAR_ORDER,
  operatingScorePillarLabel,
} from "@/lib/operating-score-pillars";

import { OperatingScorePillarTable } from "./OperatingScorePillarTable";
import { OperatingScoreRecomputeButton } from "./OperatingScoreRecomputeButton";

function relativeComputedAt(iso?: string): string {
  if (!iso) return "—";
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return "—";
  const diffMs = Date.now() - t;
  const minutes = Math.floor(diffMs / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function easeOutCubic(t: number) {
  return 1 - (1 - t) ** 3;
}

/** Prefer snapshot from ≥7d before current; else most recent prior snapshot. */
function baselineForWeekTrend(
  current: OperatingScoreEntry,
  history: OperatingScoreEntry[],
): OperatingScoreEntry | null {
  const curTs = Date.parse(current.computed_at);
  if (Number.isNaN(curTs)) return null;
  const weekMs = 7 * 24 * 60 * 60 * 1000;
  const targetTs = curTs - weekMs;
  const prior = history.filter((e) => {
    const ts = Date.parse(e.computed_at);
    return !Number.isNaN(ts) && ts < curTs;
  });
  if (prior.length === 0) return null;
  prior.sort((a, b) => Date.parse(b.computed_at) - Date.parse(a.computed_at));
  const olderWeek = prior.filter((e) => Date.parse(e.computed_at) <= targetTs);
  if (olderWeek.length > 0) {
    olderWeek.sort((a, b) => Date.parse(b.computed_at) - Date.parse(a.computed_at));
    return olderWeek[0];
  }
  return prior[0];
}

function weekTrendMeta(
  current: OperatingScoreEntry,
  history: OperatingScoreEntry[],
): { delta: number; baseline: OperatingScoreEntry | null } {
  const baseline = baselineForWeekTrend(current, history);
  if (baseline == null) return { delta: 0, baseline: null };
  return { delta: current.total - baseline.total, baseline };
}

function useAnimatedOperatingTotal(target: number, durationMs = 900) {
  const [display, setDisplay] = useState(0);
  const rafRef = useRef(0);

  useEffect(() => {
    const reduced =
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced || !Number.isFinite(target)) {
      setDisplay(target);
      return;
    }

    let startWall: number | null = null;
    const tick = (now: number) => {
      if (startWall === null) startWall = now;
      const t = Math.min(1, (now - startWall) / durationMs);
      const eased = easeOutCubic(t);
      setDisplay(eased * target);
      if (t < 1) {
        rafRef.current = requestAnimationFrame(tick);
      } else {
        setDisplay(target);
      }
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafRef.current);
  }, [target, durationMs]);

  return display;
}

function GaugeRing({
  score,
  gradientId,
}: {
  score: number;
  gradientId: string;
}) {
  const r = 52;
  const c = 2 * Math.PI * r;
  const pct = Math.min(100, Math.max(0, score)) / 100;
  const dash = pct * c;
  return (
    <svg
      viewBox="0 0 120 120"
      className="h-40 w-40 shrink-0 drop-shadow-[0_0_24px_rgba(34,211,238,0.12)]"
      aria-hidden
      data-testid="operating-score-gauge-svg"
    >
      <defs>
        <linearGradient
          id={gradientId}
          x1="0%"
          y1="100%"
          x2="100%"
          y2="0%"
          gradientUnits="objectBoundingBox"
        >
          <stop offset="0%" stopColor="#ef4444" />
          <stop offset="50%" stopColor="#fbbf24" />
          <stop offset="80%" stopColor="#34d399" />
          <stop offset="100%" stopColor="#22d3ee" />
        </linearGradient>
      </defs>
      <circle cx="60" cy="60" r={r} fill="none" stroke="#18181b" strokeWidth="10" />
      <circle
        cx="60"
        cy="60"
        r={r}
        fill="none"
        stroke={`url(#${gradientId})`}
        strokeWidth="10"
        strokeLinecap="round"
        strokeDasharray={`${dash} ${c}`}
        transform="rotate(-90 60 60)"
        className="motion-safe:transition-[stroke-dasharray] motion-safe:duration-700 motion-safe:ease-out"
        data-testid="operating-score-gauge-arc"
        data-gauge-stroke="gradient"
      />
    </svg>
  );
}

function PillarBars({ current }: { current: OperatingScoreEntry }) {
  return (
    <div
      className="mt-6 space-y-2.5"
      data-testid="operating-score-pillar-bars"
      aria-label="Pillar scores"
    >
      <p className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
        Pillar breakdown
      </p>
      <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
        {OPERATING_SCORE_PILLAR_ORDER.map((id) => {
          const p = current.pillars[id];
          const score = p?.score ?? 0;
          const label = operatingScorePillarLabel(id);
          const w = Math.min(100, Math.max(0, score));
          return (
            <div key={id} className="group">
              <div className="mb-1 flex items-center justify-between gap-2 text-[11px]">
                <span className="truncate text-zinc-400 group-hover:text-zinc-300">{label}</span>
                <span className="shrink-0 tabular-nums text-zinc-200">{score.toFixed(0)}</span>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-zinc-800/90 ring-1 ring-inset ring-zinc-700/40">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-rose-500 via-amber-400 to-cyan-400 motion-safe:transition-[width] motion-safe:duration-500 motion-safe:ease-out"
                  style={{ width: `${w}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function WeekTrendRow({
  delta,
  baseline,
}: {
  delta: number;
  baseline: OperatingScoreEntry | null;
}) {
  if (baseline == null) {
    return (
      <div
        className="flex items-center gap-2 rounded-lg border border-zinc-800/80 bg-zinc-900/40 px-3 py-2 text-xs text-zinc-500"
        data-testid="operating-score-week-trend"
      >
        <Minus className="h-3.5 w-3.5 shrink-0 text-zinc-600" />
        <span>No prior week snapshot to compare.</span>
      </div>
    );
  }

  const up = delta > 0.05;
  const down = delta < -0.05;
  const Icon = up ? TrendingUp : down ? TrendingDown : Minus;
  const tone = up
    ? "text-emerald-400 border-emerald-500/25 bg-emerald-500/5"
    : down
      ? "text-rose-400 border-rose-500/25 bg-rose-500/5"
      : "text-zinc-400 border-zinc-700/80 bg-zinc-900/40";

  const deltaStr =
    delta >= 0 ? `+${delta.toFixed(1)}` : delta.toFixed(1);

  return (
    <div
      className={`flex flex-wrap items-center gap-2 rounded-lg border px-3 py-2 text-xs ${tone}`}
      data-testid="operating-score-week-trend"
    >
      <Icon className="h-3.5 w-3.5 shrink-0" />
      <span className="font-medium tabular-nums">
        {up ? "Up" : down ? "Down" : "Flat"} {deltaStr}
      </span>
      <span className="text-zinc-500">vs prior week</span>
      <span className="ml-auto tabular-nums text-[10px] text-zinc-600">
        baseline {baseline.total.toFixed(1)} ·{" "}
        {relativeComputedAt(baseline.computed_at)}
      </span>
    </div>
  );
}

export type OperatingScoreGaugeBodyProps = {
  data: OperatingScoreResponse;
  brainConfigured: boolean;
};

/** Presentational shell: used by the RSC and by unit tests. */
export function OperatingScoreGaugeBody({ data, brainConfigured }: OperatingScoreGaugeBodyProps) {
  const gradientId = useId().replace(/:/g, "");
  const { current, history_last_12, gates } = data;

  const animatedTotal = useAnimatedOperatingTotal(current?.total ?? 0);

  const trend = useMemo(() => {
    if (current == null) return { delta: 0, baseline: null as OperatingScoreEntry | null };
    return weekTrendMeta(current, history_last_12);
  }, [current, history_last_12]);

  if (!brainConfigured) {
    return (
      <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-5 ring-1 ring-zinc-800">
        <p className="text-xs uppercase tracking-wide text-rose-300/80">Operating score</p>
        <p className="mt-2 text-sm text-rose-200">
          Brain is not configured for Studio (BRAIN_API_URL / BRAIN_API_SECRET).
        </p>
      </div>
    );
  }

  const gateLine = (
    <p className="mt-2 text-center text-sm text-zinc-400 md:text-left" data-testid="operating-score-gates">
      L4:{" "}
      <span className={gates.l4_pass ? "text-emerald-400" : "text-rose-400"}>
        {gates.l4_pass ? "PASS" : "FAIL"}
      </span>
      <span className="mx-2 text-zinc-600">|</span>L5:{" "}
      <span className={gates.l5_pass ? "text-emerald-400" : "text-rose-400"}>
        {gates.l5_pass ? "PASS" : "FAIL"}
      </span>
    </p>
  );

  if (current == null) {
    return (
      <div
        className="rounded-xl border border-zinc-800 bg-zinc-950 p-6 ring-1 ring-zinc-800"
        data-testid="operating-score-empty"
      >
        <div className="flex flex-col gap-1">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
            Operating score
          </p>
          <p className="bg-gradient-to-r from-zinc-100 to-zinc-400 bg-clip-text text-lg font-semibold tracking-tight text-transparent">
            Company OS pulse
          </p>
          <p className="text-xs text-zinc-500">
            Proxied from Brain{" "}
            <code className="text-zinc-400">/api/v1/admin/operating-score</code>
          </p>
        </div>
        <div className="mt-5 space-y-4">
          <p className="text-sm leading-relaxed text-zinc-300">
            Brain has not yet computed an Operating Score. The first run is scheduled for next Monday
            09:00 UTC. Click &apos;Recompute now&apos; to force.
          </p>
          {gateLine}
          <OperatingScoreRecomputeButton />
        </div>
        <div className="mt-5 border-t border-zinc-800/80 pt-4">
          <p className="text-xs text-zinc-500">
            Last computed: {relativeComputedAt(undefined)}
          </p>
        </div>
      </div>
    );
  }

  const totalDisplay = animatedTotal.toFixed(1);

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-6 ring-1 ring-zinc-800">
      <div className="flex flex-col gap-1">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
          Operating score
        </p>
        <p className="bg-gradient-to-r from-zinc-100 via-zinc-200 to-zinc-400 bg-clip-text text-lg font-semibold tracking-tight text-transparent">
          Company OS pulse
        </p>
        <p className="text-xs text-zinc-500">
          Proxied from Brain{" "}
          <code className="text-zinc-400">/api/v1/admin/operating-score</code>
        </p>
      </div>

      <WeekTrendRow delta={trend.delta} baseline={trend.baseline} />

      <div className="mt-5 flex flex-col items-stretch gap-6 lg:flex-row lg:items-start lg:justify-between">
        <div className="relative mx-auto flex flex-col items-center lg:mx-0">
          <GaugeRing score={current.total} gradientId={gradientId} />
          <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center pt-1">
            <span
              className="text-4xl font-semibold tabular-nums tracking-tight text-zinc-50"
              data-testid="operating-score-total"
            >
              {totalDisplay}
            </span>
            <span className="text-[10px] font-medium uppercase tracking-wider text-zinc-500">
              / 100
            </span>
          </div>
        </div>

        <div className="flex min-w-0 flex-1 flex-col gap-4">
          {gateLine}
          <OperatingScoreRecomputeButton />
          <p className="text-xs text-zinc-500">
            Last computed:{" "}
            <span className="text-zinc-400">{relativeComputedAt(current.computed_at)}</span>
          </p>
        </div>
      </div>

      <PillarBars current={current} />

      <details className="group mt-5 rounded-lg border border-zinc-800/80 bg-zinc-900/30 ring-1 ring-inset ring-zinc-800/60">
        <summary className="cursor-pointer select-none px-3 py-2 text-xs font-medium text-zinc-400 transition hover:text-zinc-200">
          Detailed pillar table
          <span className="ml-2 text-[10px] text-zinc-600 group-open:hidden">▼</span>
          <span className="ml-2 hidden text-[10px] text-zinc-600 group-open:inline">▲</span>
        </summary>
        <div className="border-t border-zinc-800/80 px-1 pb-2 pt-2">
          <OperatingScorePillarTable current={current} history={history_last_12} />
        </div>
      </details>
    </div>
  );
}
