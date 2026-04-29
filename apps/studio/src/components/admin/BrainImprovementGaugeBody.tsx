import Link from "next/link";

import type { BrainImprovementCurrent, BrainImprovementHistoryEntry, BrainImprovementResponse } from "@/types/brain-improvement";

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
  if (score < 40) return "#f87171";
  if (score < 70) return "#fbbf24";
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
      data-testid="brain-improvement-gauge-svg"
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
        data-testid="brain-improvement-gauge-arc"
        data-gauge-stroke={color}
      />
    </svg>
  );
}

/**
 * Array-driven pillar definition — extensible for PR P's 4th sub-metric (audit_freshness).
 * Each entry maps a field on BrainImprovementCurrent to a display label + formatter.
 */
type Pillar = {
  label: string;
  weight: string;
  getValue: (c: BrainImprovementCurrent) => string;
};

const PILLARS: Pillar[] = [
  {
    label: "Acceptance rate",
    weight: "40%",
    getValue: (c) => `${c.acceptance_rate_pct.toFixed(1)}%`,
  },
  {
    label: "Promotion progress",
    weight: "30%",
    getValue: (c) => `${c.promotion_progress_pct.toFixed(1)}%`,
  },
  {
    label: "Rules learned",
    weight: "20%",
    getValue: (c) => String(c.rules_count),
  },
  {
    label: "Retro POS delta",
    weight: "10%",
    getValue: (c) =>
      c.retro_delta_pct === 0 && !c.note ? "—" : `${c.retro_delta_pct >= 0 ? "+" : ""}${c.retro_delta_pct.toFixed(2)}`,
  },
  // PR P appends audit_freshness here — array-driven, no hardcoded column count.
];

function PillarTable({ current }: { current: BrainImprovementCurrent }) {
  return (
    <div className="mt-4" data-testid="brain-improvement-pillar-table">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-zinc-800">
            <th className="py-1 text-left font-medium text-zinc-500">Sub-metric</th>
            <th className="py-1 text-right font-medium text-zinc-500">Weight</th>
            <th className="py-1 text-right font-medium text-zinc-500">Value</th>
          </tr>
        </thead>
        <tbody>
          {PILLARS.map((p) => (
            <tr key={p.label} className="border-b border-zinc-800/40">
              <td className="py-1 text-zinc-300">{p.label}</td>
              <td className="py-1 text-right text-zinc-500">{p.weight}</td>
              <td className="py-1 text-right tabular-nums text-zinc-100">{p.getValue(current)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Sparkline({ history }: { history: BrainImprovementHistoryEntry[] }) {
  if (history.length < 2) return null;
  const w = 200;
  const h = 36;
  const pad = 4;
  const scores = history.map((e) => e.score);
  const min = Math.min(...scores);
  const max = Math.max(...scores);
  const range = max - min || 1;
  const points = scores
    .map((s, i) => {
      const x = pad + (i / (scores.length - 1)) * (w - pad * 2);
      const y = h - pad - ((s - min) / range) * (h - pad * 2);
      return `${x},${y}`;
    })
    .join(" ");
  return (
    <div className="mt-3" data-testid="brain-improvement-sparkline">
      <p className="mb-1 text-xs text-zinc-500">12-week trend</p>
      <svg viewBox={`0 0 ${w} ${h}`} className="w-full" aria-hidden>
        <polyline points={points} fill="none" stroke="#6366f1" strokeWidth="1.5" />
      </svg>
    </div>
  );
}

export type BrainImprovementGaugeBodyProps = {
  data: BrainImprovementResponse;
  brainConfigured: boolean;
};

/** Presentational shell: used by the RSC wrapper and by unit tests. */
export function BrainImprovementGaugeBody({ data, brainConfigured }: BrainImprovementGaugeBodyProps) {
  const { current, history_12w } = data;

  if (!brainConfigured) {
    return (
      <div
        className="rounded-xl border border-rose-900/40 bg-rose-950/20 p-5"
        data-testid="brain-improvement-not-configured"
      >
        <p className="text-xs uppercase tracking-wide text-rose-300/80">Brain growth</p>
        <p className="mt-2 text-sm text-rose-200">
          Brain is not configured for Studio (BRAIN_API_URL / BRAIN_API_SECRET).
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5" data-testid="brain-improvement-tile">
      <p className="text-xs uppercase tracking-wide text-zinc-400">Brain growth</p>
      <p className="mt-1 text-xs text-zinc-500">
        Proxied from Brain{" "}
        <code className="text-zinc-400">/api/v1/admin/brain-improvement-index</code>
      </p>

      <div className="mt-4 flex flex-col items-center gap-2 md:flex-row md:items-start md:justify-center md:gap-10">
        <div className="relative flex flex-col items-center">
          <GaugeRing score={current.score} />
          <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center pt-1">
            <span
              className="text-3xl font-semibold tabular-nums text-zinc-100"
              data-testid="brain-improvement-score"
            >
              {current.score}
            </span>
          </div>
        </div>
        <div className="flex min-w-0 flex-1 flex-col items-center md:items-stretch md:pt-4">
          {current.note ? (
            <p className="text-xs text-amber-400/80" data-testid="brain-improvement-note">
              {current.note}
            </p>
          ) : null}
          <div className="mt-2 flex justify-center md:justify-start">
            <Link
              href="/admin/brain/self-improvement"
              className="text-xs text-indigo-400 hover:text-indigo-300 hover:underline"
              data-testid="brain-improvement-cta"
            >
              Brain growth →
            </Link>
          </div>
        </div>
      </div>

      <p className="mt-4 text-center text-xs text-zinc-500 md:text-left">
        Last computed:{" "}
        <span className="text-zinc-400">{relativeComputedAt(current.computed_at)}</span>
      </p>

      <PillarTable current={current} />
      <Sparkline history={history_12w} />
    </div>
  );
}
