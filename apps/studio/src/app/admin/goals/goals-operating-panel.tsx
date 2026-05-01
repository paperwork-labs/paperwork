"use client";

import { Radar } from "lucide-react";

import type { OperatingScoreResponse } from "@/lib/brain-client";

import type { GoalsOperatingScorePayload } from "./goals-operating-types";
import { GOALS_DEMO_OPERATING_SCORE } from "./goals-operating-types";
import { progressBarToneClass } from "@/lib/goals-metrics";

function OkrProgressBar({
  label,
  progressPct,
  detail,
}: {
  label: string;
  progressPct: number;
  detail: string;
}) {
  const width = Math.min(100, Math.max(0, progressPct));
  const tone = progressBarToneClass(progressPct);
  return (
    <div className="space-y-1" data-testid="okr-progress-bar">
      <div className="flex items-center justify-between gap-2 text-xs">
        <span className="min-w-0 truncate text-zinc-300">{label}</span>
        <span className="shrink-0 tabular-nums text-zinc-500">{detail}</span>
      </div>
      <div
        className="h-2 w-full overflow-hidden rounded-full bg-zinc-800/80"
        role="progressbar"
        aria-valuenow={Math.round(width)}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={label}
      >
        <div
          className={`h-full rounded-full transition-[width] duration-500 ${tone}`}
          style={{ width: `${width}%` }}
        />
      </div>
    </div>
  );
}

function formatComputedAt(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    });
  } catch {
    return iso;
  }
}

function pillarPct(score: number, max: number): number {
  if (max <= 0) return 0;
  return Math.round((score / max) * 100);
}

function OperatingScoreFromBrain({ data }: { data: OperatingScoreResponse }) {
  const pct =
    data.max_score > 0
      ? Math.round((data.overall_score / data.max_score) * 100)
      : 0;
  return (
    <div className="space-y-4" data-testid="goals-operating-score-live">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-2xl font-semibold tabular-nums text-zinc-100">
            {data.overall_score}
            <span className="text-base font-normal text-zinc-500">
              {" "}
              / {data.max_score}
            </span>
          </p>
          <p className="mt-0.5 text-xs text-zinc-500">
            Last computed: {formatComputedAt(data.computed_at)}
          </p>
        </div>
        <span className="text-xs tabular-nums text-zinc-400">{pct}% of max</span>
      </div>
      {data.pillars.length > 0 ? (
        <ul className="space-y-2 border-t border-zinc-800/60 pt-3">
          {data.pillars.slice(0, 5).map((p) => (
            <li key={p.pillar_id}>
              <OkrProgressBar
                label={p.label}
                progressPct={pillarPct(p.score, p.max_score)}
                detail={`${p.score} / ${p.max_score}`}
              />
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

export function GoalsOperatingScorePanel({ payload }: { payload: GoalsOperatingScorePayload }) {
  if (payload.kind === "error") {
    return (
      <div
        className="rounded-2xl border border-rose-900/40 bg-rose-950/20 p-5"
        data-testid="goals-operating-score-error"
      >
        <p className="text-xs uppercase tracking-wide text-rose-300/80">Operating score</p>
        <p className="mt-2 text-sm text-rose-200">{payload.message}</p>
        <p className="mt-2 text-xs text-rose-300/70">
          OKRs below are unchanged; fix Brain connectivity to align goals with live operating score.
        </p>
      </div>
    );
  }

  const isDemo = payload.kind === "unconfigured";
  const data = isDemo ? GOALS_DEMO_OPERATING_SCORE : payload.data;

  return (
    <div
      className="rounded-2xl border border-zinc-800/80 bg-zinc-900/50 p-5 shadow-sm ring-1 ring-black/5"
      data-testid="goals-operating-score-section"
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <Radar className="h-4 w-4 text-zinc-500" aria-hidden />
          <h2 className="text-sm font-semibold text-zinc-100">Operating score</h2>
        </div>
        {isDemo ? (
          <span className="rounded-full border border-amber-500/35 bg-amber-500/10 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-amber-200">
            Illustrative — configure Brain for live
          </span>
        ) : (
          <span className="rounded-full border border-emerald-500/35 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-emerald-200">
            Live (Brain)
          </span>
        )}
      </div>
      <p className="mt-1 text-xs text-zinc-500">
        Pulled via{" "}
        <code className="text-zinc-400">BrainClient.getOperatingScore()</code> — ties OKR execution to
        how the org is running day to day.
      </p>
      <div className="mt-4">
        <OperatingScoreFromBrain data={data} />
      </div>
    </div>
  );
}
