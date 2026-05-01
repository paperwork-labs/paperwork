"use client";

import {
  AlertTriangle,
  Crosshair,
  ListTree,
  Target,
  TrendingUp,
} from "lucide-react";

import { HqPageHeader } from "@/components/admin/hq/HqPageHeader";
import { HqStatCard } from "@/components/admin/hq/HqStatCard";
import type { GoalsJson } from "@/lib/goals-metrics";
import { GoalsOperatingScorePanel } from "./goals-operating-panel";
import type { GoalsOperatingScorePayload } from "./goals-operating-types";
import {
  computeGoalsRollup,
  krProgressPct,
  objectiveProgressPct,
  progressBarToneClass,
} from "@/lib/goals-metrics";

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

function ownerBadgeClass(owner: string): string {
  const o = owner.toLowerCase();
  if (o === "brain") {
    return "border-fuchsia-500/35 bg-fuchsia-500/10 text-fuchsia-200";
  }
  return "border-zinc-600 bg-zinc-800/80 text-zinc-300";
}

export function GoalsClient({
  data,
  operatingScore,
}: {
  data: GoalsJson;
  operatingScore: GoalsOperatingScorePayload;
}) {
  const { objectives } = data;
  const rollup = computeGoalsRollup(objectives);

  return (
    <div className="space-y-8">
      <HqPageHeader
        title="Goals & OKRs"
        subtitle="Q2 2026 objectives and key results"
        breadcrumbs={[
          { label: "Admin", href: "/admin" },
          { label: "Goals & OKRs" },
        ]}
      />

      <GoalsOperatingScorePanel payload={operatingScore} />

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <HqStatCard
          label="Objectives"
          value={rollup.objectiveCount}
          icon={<Crosshair className="h-3.5 w-3.5 text-zinc-500" />}
        />
        <HqStatCard
          label="KRs on track"
          value={rollup.krOnTrack}
          status="success"
          helpText=">50% progress"
          icon={<TrendingUp className="h-3.5 w-3.5 text-zinc-500" />}
        />
        <HqStatCard
          label="KRs at risk"
          value={rollup.krAtRisk}
          status={rollup.krAtRisk > 0 ? "warning" : "neutral"}
          helpText="<25% progress"
          icon={<AlertTriangle className="h-3.5 w-3.5 text-zinc-500" />}
        />
        <HqStatCard
          label="Overall progress"
          value={`${rollup.overallPct}%`}
          icon={<Target className="h-3.5 w-3.5 text-zinc-500" />}
        />
      </div>

      <div className="space-y-5">
        {objectives.map((obj) => {
          const objPct = objectiveProgressPct(obj);
          return (
            <section
              key={obj.id}
              data-testid="okr-objective-card"
              className="rounded-2xl border border-zinc-800/80 bg-zinc-900/50 p-5 shadow-sm ring-1 ring-black/5"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0 space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="text-base font-semibold text-zinc-100">{obj.title}</h2>
                    <span
                      className={`rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide ${ownerBadgeClass(obj.owner)}`}
                    >
                      {obj.owner}
                    </span>
                  </div>
                  <p className="text-[10px] uppercase tracking-wide text-zinc-500">
                    Objective progress (avg. of key results)
                  </p>
                </div>
                <span className="tabular-nums text-sm font-medium text-zinc-400">
                  {Math.round(objPct)}%
                </span>
              </div>
              <div className="mt-3">
                <OkrProgressBar
                  label="Objective"
                  progressPct={objPct}
                  detail={`${obj.key_results.length} key result${obj.key_results.length === 1 ? "" : "s"}`}
                />
              </div>

              <div className="mt-5 space-y-4 border-t border-zinc-800/60 pt-5">
                <p className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
                  <ListTree className="h-3 w-3" /> Key results
                </p>
                <ul className="space-y-4">
                  {obj.key_results.map((kr) => {
                    const pct = krProgressPct(kr);
                    return (
                      <li key={kr.id}>
                        <OkrProgressBar
                          label={kr.title}
                          progressPct={pct}
                          detail={`${kr.current} / ${kr.target} ${kr.unit}`}
                        />
                      </li>
                    );
                  })}
                </ul>
              </div>
            </section>
          );
        })}
      </div>
    </div>
  );
}
