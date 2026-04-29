import type { OperatingScoreResponse } from "@/types/operating-score";

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

function gaugeStrokeColor(score: number): string {
  if (score < 70) return "#f87171";
  if (score < 90) return "#fbbf24";
  return "#4ade80";
}

function GaugeRing({ score }: { score: number }) {
  const r = 52;
  const c = 2 * Math.PI * r;
  const pct = Math.min(100, Math.max(0, score)) / 100;
  const dash = pct * c;
  const color = gaugeStrokeColor(score);
  return (
    <svg
      viewBox="0 0 120 120"
      className="h-36 w-36 shrink-0"
      aria-hidden
      data-testid="operating-score-gauge-svg"
    >
      <circle cx="60" cy="60" r={r} fill="none" stroke="#27272a" strokeWidth="8" />
      <circle
        cx="60"
        cy="60"
        r={r}
        fill="none"
        stroke={color}
        strokeWidth="8"
        strokeLinecap="round"
        strokeDasharray={`${dash} ${c}`}
        transform="rotate(-90 60 60)"
        data-testid="operating-score-gauge-arc"
        data-gauge-stroke={color}
      />
    </svg>
  );
}

export type OperatingScoreGaugeBodyProps = {
  data: OperatingScoreResponse;
  brainConfigured: boolean;
};

/** Presentational shell: used by the RSC and by unit tests. */
export function OperatingScoreGaugeBody({ data, brainConfigured }: OperatingScoreGaugeBodyProps) {
  const { current, history_last_12, gates } = data;

  if (!brainConfigured) {
    return (
      <div className="rounded-xl border border-rose-900/40 bg-rose-950/20 p-5">
        <p className="text-xs uppercase tracking-wide text-rose-300/80">Operating score</p>
        <p className="mt-2 text-sm text-rose-200">
          Brain is not configured for Studio (BRAIN_API_URL / BRAIN_API_SECRET).
        </p>
      </div>
    );
  }

  const gateLine = (
    <p className="mt-2 text-center text-sm text-zinc-400" data-testid="operating-score-gates">
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
        className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5"
        data-testid="operating-score-empty"
      >
        <p className="text-xs uppercase tracking-wide text-zinc-400">Operating score</p>
        <p className="mt-1 text-xs text-zinc-500">
          Proxied from Brain{" "}
          <code className="text-zinc-400">/api/v1/admin/operating-score</code>
        </p>
        <div className="mt-4 space-y-4">
          <p className="text-sm leading-relaxed text-zinc-300">
            Brain has not yet computed an Operating Score. The first run is scheduled for next
            Monday 09:00 UTC. Click &apos;Recompute now&apos; to force.
          </p>
          {gateLine}
          <OperatingScoreRecomputeButton />
        </div>
        <div className="mt-4 border-t border-zinc-800 pt-3">
          <p className="text-xs text-zinc-500">
            Last computed: {relativeComputedAt(undefined)}
          </p>
        </div>
      </div>
    );
  }

  const totalDisplay = current.total.toFixed(1);

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
      <p className="text-xs uppercase tracking-wide text-zinc-400">Operating score</p>
      <p className="mt-1 text-xs text-zinc-500">
        Proxied from Brain{" "}
        <code className="text-zinc-400">/api/v1/admin/operating-score</code>
      </p>

      <div className="mt-4 flex flex-col items-center gap-2 md:flex-row md:items-start md:justify-center md:gap-10">
        <div className="relative flex flex-col items-center">
          <GaugeRing score={current.total} />
          <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center pt-1">
            <span
              className="text-3xl font-semibold tabular-nums text-zinc-100"
              data-testid="operating-score-total"
            >
              {totalDisplay}
            </span>
          </div>
        </div>
        <div className="flex min-w-0 flex-1 flex-col items-center md:items-stretch md:pt-4">
          {gateLine}
          <div className="mt-4 flex justify-center md:justify-start">
            <OperatingScoreRecomputeButton />
          </div>
        </div>
      </div>

      <p className="mt-4 text-center text-xs text-zinc-500 md:text-left">
        Last computed:{" "}
        <span className="text-zinc-400">{relativeComputedAt(current.computed_at)}</span>
      </p>

      <OperatingScorePillarTable current={current} history={history_last_12} />
    </div>
  );
}
